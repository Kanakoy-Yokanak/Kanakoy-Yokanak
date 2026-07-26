const cubeVertices=new Float32Array([
 -1,-1, 1,0,0,1, 1,-1, 1,0,0,1, 1,1, 1,0,0,1,-1,1, 1,0,0,1,
  1,-1,-1,0,0,-1,-1,-1,-1,0,0,-1,-1,1,-1,0,0,-1,1,1,-1,0,0,-1,
 -1,-1,-1,-1,0,0,-1,-1, 1,-1,0,0,-1,1, 1,-1,0,0,-1,1,-1,-1,0,0,
  1,-1, 1,1,0,0,1,-1,-1,1,0,0,1,1,-1,1,0,0,1,1, 1,1,0,0,
 -1, 1, 1,0,1,0,1, 1, 1,0,1,0,1,1,-1,0,1,0,-1,1,-1,0,1,0,
 -1,-1,-1,0,-1,0,1,-1,-1,0,-1,0,1,-1,1,0,-1,0,-1,-1,1,0,-1,0]);
const cubeIndices=new Uint16Array(Array.from({length:6},(_,f)=>[0,1,2,0,2,3].map(i=>i+f*4)).flat());
export function cube(gl){return upload(gl,cubeVertices,cubeIndices)}
export function cylinder(gl,segments=20){const v=[],idx=[];for(let i=0;i<=segments;i++){let a=i/segments*Math.PI*2,c=Math.cos(a),s=Math.sin(a);v.push(c,-1,s,c,0,s,c,1,s,c,0,s)}for(let i=0;i<segments;i++){let a=i*2;idx.push(a,a+1,a+2,a+1,a+3,a+2)}return upload(gl,new Float32Array(v),new Uint16Array(idx))}
export function palm(gl,segments=7){const v=[],idx=[];let cursor=0;const vertex=(p,n)=>{v.push(...p,...n);return cursor++};for(let y=0;y<segments;y++){let y0=y/segments*3.4,y1=(y+1)/segments*3.4,r0=.14*(1-y/segments*.55),r1=.14*(1-(y+1)/segments*.55),bend0=.18*Math.pow(y/segments,2),bend1=.18*Math.pow((y+1)/segments,2);for(let s=0;s<6;s++){let a=s/6*Math.PI*2,b=(s+1)/6*Math.PI*2,n0=[Math.cos(a),.04,Math.sin(a)],n1=[Math.cos(b),.04,Math.sin(b)],p0=[Math.cos(a)*r0+bend0,y0,Math.sin(a)*r0],p1=[Math.cos(b)*r0+bend0,y0,Math.sin(b)*r0],p2=[Math.cos(a)*r1+bend1,y1,Math.sin(a)*r1],p3=[Math.cos(b)*r1+bend1,y1,Math.sin(b)*r1];let a0=vertex(p0,n0),a1=vertex(p1,n1),a2=vertex(p2,n0),a3=vertex(p3,n1);idx.push(a0,a1,a2,a1,a3,a2)}}for(let leaf=0;leaf<9;leaf++){let a=leaf/9*Math.PI*2+.31,len=1.25+(leaf%3)*.18,width=.10,origin=[.18,3.35,0],tip=[origin[0]+Math.cos(a)*len,3.15-(leaf%2)*.18,Math.sin(a)*len],side=[-Math.sin(a)*width,0,Math.cos(a)*width],mid=[origin[0]+Math.cos(a)*len*.55,3.48,Math.sin(a)*len*.55],n=[0,1,0];let q0=vertex([origin[0]+side[0],origin[1],origin[2]+side[2]],n),q1=vertex([origin[0]-side[0],origin[1],origin[2]-side[2]],n),q2=vertex([mid[0]+side[0]*.65,mid[1],mid[2]+side[2]*.65],n),q3=vertex([mid[0]-side[0]*.65,mid[1],mid[2]-side[2]*.65],n),q4=vertex(tip,n);idx.push(q0,q1,q2,q1,q3,q2,q2,q3,q4)}return upload(gl,new Float32Array(v),new Uint16Array(idx))}
export function upload(gl,vertices,indices){const vao=gl.createVertexArray();gl.bindVertexArray(vao);const vbo=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vbo);gl.bufferData(gl.ARRAY_BUFFER,vertices,gl.STATIC_DRAW);const ebo=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ebo);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,indices,gl.STATIC_DRAW);gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,3,gl.FLOAT,false,24,0);gl.enableVertexAttribArray(1);gl.vertexAttribPointer(1,3,gl.FLOAT,false,24,12);return{vao,count:indices.length,vbo,ebo}}
export function carParts(){return[
 {shape:'cube',p:[-.55,.56,-1.2],r:[0,-.10,-.01],s:[1.35,.25,2.18],c:[.018,.022,.03],metal:1},
 {shape:'cube',p:[-.50,.87,-1.25],r:[-.05,-.10,-.01],s:[1.02,.20,1.22],c:[.025,.032,.043],metal:1},
 {shape:'cube',p:[-.48,1.10,-1.34],r:[-.10,-.10,-.01],s:[.76,.17,.72],c:[.008,.022,.034],metal:.75},
 {shape:'cube',p:[-.55,.34,-.72],r:[0,-.10,0],s:[1.30,.14,.45],c:[.006,.007,.01],metal:.6},
 {shape:'cube',p:[-.55,.27,-.40],r:[0,-.10,0],s:[1.05,.06,.16],c:[.012,.012,.016],metal:.9},
 {shape:'cube',p:[-.58,.62,.88],r:[0,-.10,0],s:[1.08,.055,.08],c:[5.8,.015,.012],emissive:1},
 {shape:'cube',p:[-.57,.43,.90],r:[0,-.10,0],s:[.26,.075,.06],c:[.015,.017,.022],metal:.4},
 {shape:'cube',p:[-.58,.27,.91],r:[0,-.10,0],s:[.82,.045,.07],c:[.015,.018,.021],metal:.9},
 ...[-1,1].flatMap(side=>[-.85,.72].map((z,i)=>({shape:'wheel',p:[-.55+side*1.18,.31,z],r:[0,0,Math.PI/2],s:[.36,.16,.36],c:[.004,.004,.005],metal:.1,wheel:true,side,i}))),
 ...[-1,1].flatMap(side=>[-.85,.72].map(z=>({shape:'wheel',p:[-.55+side*1.185,.31,z],r:[0,0,Math.PI/2],s:[.21,.165,.21],c:[.10,.12,.14],metal:1,wheel:true}))),
 ...[-1,1].map(side=>({shape:'cube',p:[-.55+side*.77,.63,.90],r:[0,-.10,0],s:[.30,.045,.085],c:[7.,.018,.012],emissive:1}))
 ,...[-1,1].flatMap(side=>[0,1,2].map(spoke=>({shape:'cube',p:[-.55+side*1.185,.31,.72],r:[0,0,Math.PI/2+spoke*Math.PI/3],s:[.17,.025,.025],c:[.09,.10,.12],metal:1})))
 ]}
