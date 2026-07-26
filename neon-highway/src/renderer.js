import {fullscreenVertex,sceneFragment,meshVertex,meshFragment,thresholdFragment,blurFragment,compositeFragment} from './shaders.js';
import {cube,cylinder,palm,carParts} from './geometry.js';
import {mat4} from './matrix.js';

const PRESETS={performance:[1920,1080],high:[2560,1440],'4k':[3840,2160],'8k':[7680,4320]};
export class Renderer{
  constructor(canvas){
    this.canvas=canvas;
    this.gl=canvas.getContext('webgl2',{antialias:false,alpha:false,powerPreference:'high-performance'});
    if(!this.gl)throw Error('WebGL2 unavailable');
    const g=this.gl;
    this.floatColor=Boolean(g.getExtension('EXT_color_buffer_float'));
    this.limits={texture:g.getParameter(g.MAX_TEXTURE_SIZE),renderbuffer:g.getParameter(g.MAX_RENDERBUFFER_SIZE),viewport:Array.from(g.getParameter(g.MAX_VIEWPORT_DIMS))};
    this.programs={scene:this.program(fullscreenVertex,sceneFragment),mesh:this.program(meshVertex,meshFragment),threshold:this.program(fullscreenVertex,thresholdFragment),blur:this.program(fullscreenVertex,blurFragment),composite:this.program(fullscreenVertex,compositeFragment)};
    this.screenVao=g.createVertexArray();
    this.geometry={cube:cube(g),wheel:cylinder(g,24),palm:palm(g)};
    this.parts=carParts();
    this.seed=417.73;
    this.stats={drawCalls:0,triangles:0,fps:0,frameMs:0};
    this.setPreset(innerWidth<700?'performance':'high');
  }
  shader(type,source){const g=this.gl,s=g.createShader(type);g.shaderSource(s,source);g.compileShader(s);if(!g.getShaderParameter(s,g.COMPILE_STATUS))throw Error(g.getShaderInfoLog(s));return s}
  program(vertex,fragment){const g=this.gl,p=g.createProgram(),vs=this.shader(g.VERTEX_SHADER,vertex),fs=this.shader(g.FRAGMENT_SHADER,fragment);g.attachShader(p,vs);g.attachShader(p,fs);g.linkProgram(p);g.deleteShader(vs);g.deleteShader(fs);if(!g.getProgramParameter(p,g.LINK_STATUS))throw Error(g.getProgramInfoLog(p));return p}
  target(w,h,depth=false){
    const g=this.gl,t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.CLAMP_TO_EDGE);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.CLAMP_TO_EDGE);g.texImage2D(g.TEXTURE_2D,0,this.floatColor?g.RGBA16F:g.RGBA8,w,h,0,g.RGBA,this.floatColor?g.HALF_FLOAT:g.UNSIGNED_BYTE,null);
    const f=g.createFramebuffer();g.bindFramebuffer(g.FRAMEBUFFER,f);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,t,0);let rb=null;if(depth){rb=g.createRenderbuffer();g.bindRenderbuffer(g.RENDERBUFFER,rb);g.renderbufferStorage(g.RENDERBUFFER,g.DEPTH_COMPONENT24,w,h);g.framebufferRenderbuffer(g.FRAMEBUFFER,g.DEPTH_ATTACHMENT,g.RENDERBUFFER,rb)}
    if(g.checkFramebufferStatus(g.FRAMEBUFFER)!==g.FRAMEBUFFER_COMPLETE){g.deleteTexture(t);g.deleteFramebuffer(f);if(rb)g.deleteRenderbuffer(rb);throw Error(`Framebuffer incomplete at ${w}x${h}`)}return{texture:t,fbo:f,depth:rb,w,h}
  }
  setPreset(name){
    const req=PRESETS[name]||PRESETS.high,maxW=Math.min(this.limits.texture,this.limits.renderbuffer,this.limits.viewport[0]),maxH=Math.min(this.limits.texture,this.limits.renderbuffer,this.limits.viewport[1]);
    let scale=Math.min(1,maxW/req[0],maxH/req[1]);this.requested=[...req];this.preset=name;
    for(let attempts=0;attempts<5;attempts++){this.actual=[Math.max(2,Math.floor(req[0]*scale/2)*2),Math.max(2,Math.floor(req[1]*scale/2)*2)];try{this.rebuild();break}catch(error){console.warn(error.message,'— reducing framebuffer');scale*=.75;if(attempts===4)throw error}}
    return this.actual[0]===req[0]&&this.actual[1]===req[1];
  }
  destroyTargets(){const g=this.gl;if(!this.targets)return;Object.values(this.targets).forEach(t=>{g.deleteTexture(t.texture);g.deleteFramebuffer(t.fbo);if(t.depth)g.deleteRenderbuffer(t.depth)})}
  rebuild(){this.destroyTargets();const[w,h]=this.actual,bw=Math.max(2,Math.floor(w/4)),bh=Math.max(2,Math.floor(h/4));this.targets={scene:this.target(w,h,true),bright:this.target(bw,bh),ping:this.target(bw,bh)};this.canvas.width=w;this.canvas.height=h}
  uniforms(program,values){const g=this.gl;for(const[name,v]of Object.entries(values)){const l=g.getUniformLocation(program,name);if(l===null)continue;if(v instanceof Float32Array)g.uniformMatrix4fv(l,false,v);else if(Array.isArray(v)){if(v.length===3)g.uniform3fv(l,v);else g.uniform2fv(l,v)}else g.uniform1f(l,v)}}
  screenPass(program,target,textures={},values={},clear=false){const g=this.gl;g.bindFramebuffer(g.FRAMEBUFFER,target?.fbo||null);g.viewport(0,0,target?.w||this.actual[0],target?.h||this.actual[1]);g.disable(g.DEPTH_TEST);if(clear){g.clearColor(0,0,0,1);g.clear(g.COLOR_BUFFER_BIT|g.DEPTH_BUFFER_BIT)}g.useProgram(program);g.bindVertexArray(this.screenVao);let unit=0;for(const[name,texture]of Object.entries(textures)){g.activeTexture(g.TEXTURE0+unit);g.bindTexture(g.TEXTURE_2D,texture);g.uniform1i(g.getUniformLocation(program,name),unit++)}this.uniforms(program,values);g.drawArrays(g.TRIANGLES,0,3);this.stats.drawCalls++;this.stats.triangles++}
  drawCar(t){
    const g=this.gl,p=this.programs.mesh,aspect=this.actual[0]/this.actual[1];
    const organic=Math.sin(t*.73)*.007+Math.sin(t*1.91+1.4)*.004+Math.sin(t*4.17)*.0015;
    const eye=[.15,1.48,5.65],projection=mat4.perspective(33*Math.PI/180,aspect,.05,100),view=mat4.lookAt(eye,[-.48,.62,-1.15],[0,1,0]);
    g.bindFramebuffer(g.FRAMEBUFFER,this.targets.scene.fbo);g.viewport(0,0,...this.actual);g.enable(g.DEPTH_TEST);g.depthFunc(g.LEQUAL);g.useProgram(p);this.uniforms(p,{projection,view,cameraPosition:eye,time:t});
    for(const part of this.parts){let shape=this.geometry[part.shape],rotation=[...part.r];if(part.wheel)rotation[1]+=t*9.4;const model=mat4.model([part.p[0]+organic*.5,part.p[1]+organic,part.p[2]],[rotation[0],rotation[1]-.018*Math.sin(t*.43),rotation[2]+organic*.4],part.s);this.uniforms(p,{model,baseColor:part.c,metallic:part.metal||0,emissive:part.emissive||0});g.bindVertexArray(shape.vao);g.drawElements(g.TRIANGLES,shape.count,g.UNSIGNED_SHORT,0);this.stats.drawCalls++;this.stats.triangles+=shape.count/3}
  }
  drawPalms(t){const g=this.gl,p=this.programs.mesh,eye=[.15,1.48,5.65],projection=mat4.perspective(33*Math.PI/180,this.actual[0]/this.actual[1],.05,100),view=mat4.lookAt(eye,[-.48,.62,-1.15],[0,1,0]);g.bindFramebuffer(g.FRAMEBUFFER,this.targets.scene.fbo);g.enable(g.DEPTH_TEST);g.useProgram(p);this.uniforms(p,{projection,view,cameraPosition:eye,time:t,baseColor:[.004,.011,.012],metallic:.05,emissive:0});for(let i=0;i<10;i++){const side=i%2?-1:1,cycle=Math.floor(t*.42+i*.83),z=4-((t*5.8+i*8.7)%76),variance=(Math.sin((i+cycle)*91.17)*.5+.5),x=side*(3.6+variance*2.1),scale=.72+variance*.42,model=mat4.model([x,-.05,z],[0,(variance-.5)*.5,side*(variance-.5)*.05],[scale,scale,scale]);this.uniforms(p,{model});g.bindVertexArray(this.geometry.palm.vao);g.drawElements(g.TRIANGLES,this.geometry.palm.count,g.UNSIGNED_SHORT,0);this.stats.drawCalls++;this.stats.triangles+=this.geometry.palm.count/3}}
  render(t,frameMs=0){
    this.stats.drawCalls=0;this.stats.triangles=0;this.stats.frameMs=frameMs;
    this.screenPass(this.programs.scene,this.targets.scene,{}, {resolution:this.actual,time:t,seed:this.seed},true);this.drawPalms(t);this.drawCar(t);
    this.screenPass(this.programs.threshold,this.targets.bright,{image:this.targets.scene.texture});
    for(let i=0;i<4;i++){this.screenPass(this.programs.blur,this.targets.ping,{image:this.targets.bright.texture},{direction:[1,0],texel:[1/this.targets.bright.w,1/this.targets.bright.h]});this.screenPass(this.programs.blur,this.targets.bright,{image:this.targets.ping.texture},{direction:[0,1],texel:[1/this.targets.bright.w,1/this.targets.bright.h]})}
    this.screenPass(this.programs.composite,null,{scene:this.targets.scene.texture,bloom:this.targets.bright.texture},{time:t});
  }
  info(){const bytesPerColor=this.floatColor?8:4,estimatedMB=this.actual[0]*this.actual[1]*(bytesPerColor+4+bytesPerColor/8)/1048576;return{preset:this.preset,requested:this.requested,actual:this.actual,dpr:devicePixelRatio,hdr:this.floatColor?'RGBA16F':'RGBA8 fallback',estimatedMB,version:this.gl.getParameter(this.gl.VERSION),limits:this.limits,...this.stats}}
}
