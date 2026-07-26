export const fullscreenVertex = `#version 300 es
precision highp float;
const vec2 P[3]=vec2[3](vec2(-1.,-1.),vec2(3.,-1.),vec2(-1.,3.));
out vec2 uv;void main(){vec2 p=P[gl_VertexID];uv=p*.5+.5;gl_Position=vec4(p,0,1);}`;

export const sceneFragment = `#version 300 es
precision highp float;out vec4 outColor;in vec2 uv;
uniform vec2 resolution;uniform float time;uniform float seed;
#define PI 3.14159265
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7))+seed)*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*noise(p);p=p*2.03+17.1;a*=.48;}return v;}
float sdBox(vec2 p,vec2 b){vec2 d=abs(p)-b;return length(max(d,0.))+min(max(d.x,d.y),0.);}
float line(float d,float w){return smoothstep(w,0.,abs(d));}
vec3 sky(vec2 p){float h=clamp(p.y,0.,1.);vec3 c=mix(vec3(.11,.012,.18),vec3(.003,.004,.018),smoothstep(.22,1.,h));float hz=exp(-abs(p.y-.19)*10.);c+=vec3(.38,.025,.24)*hz;float stars=step(.9965,hash(floor(p*resolution*.35)))*(smoothstep(.3,.8,p.y));c+=stars*vec3(.35,.55,.8);return c;}
float mountain(float x,float layer){return .205+layer*.035+fbm(vec2(x*(2.2+layer),layer*13.))*(.11-layer*.025);}
float palm(vec2 p,float x,float y,float s,float lean){p-=vec2(x,y);p/=s;p.x-=lean*(p.y+.2);float trunk=line(p.x+.045*sin(p.y*4.),.018)*step(-.02,p.y)*step(p.y,.42);vec2 q=p-vec2(lean*.42,.43);float leaves=0.;for(int i=0;i<7;i++){float a=-2.85+float(i)*.78;vec2 d=vec2(cos(a),sin(a));vec2 z=vec2(dot(q,d),dot(q,vec2(-d.y,d.x)));leaves=max(leaves,step(0.,z.x)*smoothstep(.032,0.,abs(z.y+.10*z.x*z.x))*smoothstep(.48,.08,z.x));}return max(trunk,leaves);}
void main(){vec2 p=(gl_FragCoord.xy-.5*resolution)/resolution.y;p.y+=.03;vec3 col=sky(p+vec2(0,.5));
 float sunD=length((p-vec2(.18,.19))/vec2(1.,1.));float cuts=step(.025,mod((p.y-.115)*32.,1.));float sun=smoothstep(.125,.118,sunD)*cuts;col+=vec3(1.3,.18,.32)*exp(-sunD*14.)+sun*vec3(1.5,.48,.18);
 for(int l=2;l>=0;l--){float fl=float(l);float m=mountain(p.x+time*.001*(fl+1.),fl);float mask=step(p.y,m);vec3 mc=mix(vec3(.018,.01,.038),vec3(.065,.012,.09),fl*.35);col=mix(col,mc,mask*.94);}
 float skyline=step(p.y,.202+hash(vec2(floor(p.x*95.),3.))* .055)*step(.19,p.y);col=mix(col,vec3(.025,.008,.045),skyline);
 float horizon=.19;float ground=step(p.y,horizon);float depth=(horizon-p.y)/max(.001,p.y+.54);float z=1./max(.014,horizon-p.y);float sway=.008*noise(vec2(time*.13,4.))-.004;float roadHalf=.095+depth*.58;float road=ground*step(abs(p.x-sway),roadHalf);vec2 wp=vec2((p.x-sway)/roadHalf,z+time*1.35);
 vec3 asphalt=vec3(.006,.006,.013);float wet=fbm(wp*vec2(3.,.10));asphalt+=vec3(.025,.018,.04)*wet;float center=line(wp.x,.008+z*.00004)*step(.54,fract(wp.y*.038));asphalt+=center*vec3(.3,.18,.27);
 float edge=line(abs(wp.x)-.94,.025);asphalt+=edge*vec3(.04,.65,.85)*(1.2+.4*sin(wp.y*.8));
 float rip=fbm(vec2(wp.x*11.,wp.y*.17));float puddles=smoothstep(.58,.78,fbm(wp*vec2(5.,.08)));float tailRefl=exp(-pow((wp.x+.08)/.19,2.))*exp(-depth*.42)*(step(.48,rip));asphalt+=tailRefl*vec3(1.15,.012,.035)*(puddles+.25);float cyanRefl=exp(-pow((abs(wp.x)-.88)/.1,2.))*exp(-depth*.16);asphalt+=cyanRefl*vec3(0.,.42,.62)*(1.-rip*.55);float sunRefl=exp(-pow((wp.x-.22)/.13,2.))*exp(-depth*.65);asphalt+=sunRefl*vec3(.55,.16,.07)*(puddles+.12);col=mix(col,asphalt,road);
 float lamps=pow(max(0.,1.-abs(fract(wp.y*.075)-.5)*32.),3.);float lampMask=line(abs(wp.x)-1.02,.035)*lamps*ground;col+=lampMask*mix(vec3(0.,1.2,1.8),vec3(1.1,.02,.45),step(.82,hash(vec2(floor(wp.y*.075),2.))));
 vec3 verge=vec3(.005,.008,.012)+vec3(.025,.004,.03)*fbm(vec2(p.x*30.,z*.05));col=mix(col,verge,ground*(1.-road));
 for(int i=0;i<9;i++){float fi=float(i);float cell=floor((time*.11+fi)/9.);float h=hash(vec2(fi,cell));float zz=fract(fi/9.+time*.011+h*.08);float py=horizon-(zz*zz)*.66;float sc=.055+zz*.24;float side=mod(fi,2.)<1.?-1.:1.;float px=side*(.12+zz*.72)+sway;float pm=palm(p,px,py,sc,(h-.5)*.2);col=mix(col,vec3(.003,.008,.012)+vec3(0.,.035,.05)*zz,pm);}
 float fog=exp(-abs(p.y-horizon)*15.)*.34;col=mix(col,vec3(.26,.025,.25),fog);float grain=(hash(gl_FragCoord.xy+time)-.5)*.025;col+=grain;outColor=vec4(max(col,0.),1.);}`;

export const meshVertex = `#version 300 es
precision highp float;layout(location=0)in vec3 position;layout(location=1)in vec3 normal;
uniform mat4 projection,view,model;out vec3 worldPosition;out vec3 worldNormal;
void main(){vec4 w=model*vec4(position,1.);worldPosition=w.xyz;worldNormal=normalize(mat3(model)*normal);gl_Position=projection*view*w;}`;
export const meshFragment = `#version 300 es
precision highp float;in vec3 worldPosition;in vec3 worldNormal;out vec4 outColor;
uniform vec3 baseColor;uniform float metallic;uniform float emissive;uniform vec3 cameraPosition;uniform float time;
void main(){vec3 n=normalize(worldNormal),v=normalize(cameraPosition-worldPosition);vec3 warm=normalize(vec3(.35,.42,-1.));vec3 cyan=normalize(vec3(-1.,.25,.35));vec3 magenta=normalize(vec3(1.,.18,.2));float ndw=max(dot(n,warm),0.),ndc=max(dot(n,cyan),0.),ndm=max(dot(n,magenta),0.);float fres=pow(1.-max(dot(n,v),0.),4.);vec3 env=vec3(1.,.20,.11)*ndw*.32+vec3(0.,.48,.72)*ndc*.22+vec3(.64,.015,.30)*ndm*.20;vec3 h=normalize(warm+v);float spec=pow(max(dot(n,h),0.),mix(24.,110.,metallic));vec3 c=baseColor*(.20+ndw*.22)+env*metallic+spec*vec3(1.,.62,.48)*1.6+fres*mix(vec3(.04),vec3(.05,.40,.58),metallic);if(emissive>.5)c=baseColor*(1.+.08*sin(time*2.3));float fog=smoothstep(8.,48.,length(worldPosition-cameraPosition));c=mix(c,vec3(.07,.008,.09),fog);outColor=vec4(c,1.);}`;

export const thresholdFragment = `#version 300 es
precision highp float;out vec4 o;in vec2 uv;uniform sampler2D image;void main(){vec3 c=texture(image,uv).rgb;float l=max(max(c.r,c.g),c.b);o=vec4(c*smoothstep(.58,1.15,l),1);}`;
export const blurFragment = `#version 300 es
precision highp float;out vec4 o;in vec2 uv;uniform sampler2D image;uniform vec2 direction;uniform vec2 texel;void main(){vec3 c=texture(image,uv).rgb*.227027;c+=texture(image,uv+direction*texel*1.384615).rgb*.316216;c+=texture(image,uv-direction*texel*1.384615).rgb*.316216;c+=texture(image,uv+direction*texel*3.230769).rgb*.070270;c+=texture(image,uv-direction*texel*3.230769).rgb*.070270;o=vec4(c,1);}`;
export const compositeFragment = `#version 300 es
precision highp float;out vec4 o;in vec2 uv;uniform sampler2D scene;uniform sampler2D bloom;uniform float time;void main(){vec3 c=texture(scene,uv).rgb+texture(bloom,uv).rgb*.72;c=1.-exp(-c*1.18);c=pow(c,vec3(.92,1.,1.04));float v=pow(16.*uv.x*uv.y*(1.-uv.x)*(1.-uv.y),.18);c*=mix(.52,1.,v);o=vec4(c,1);}`;
