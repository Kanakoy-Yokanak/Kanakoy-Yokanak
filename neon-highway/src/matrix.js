export const mat4={
 identity:()=>new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]),
 perspective(fov,aspect,near,far){const f=1/Math.tan(fov/2),nf=1/(near-far);return new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)*nf,-1,0,0,2*far*near*nf,0])},
 lookAt(eye,target,up=[0,1,0]){let z=norm(sub(eye,target)),x=norm(cross(up,z)),y=cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1])},
 model(position=[0,0,0],rotation=[0,0,0],scale=[1,1,1]){let[x,y,z]=rotation,cx=Math.cos(x),sx=Math.sin(x),cy=Math.cos(y),sy=Math.sin(y),cz=Math.cos(z),sz=Math.sin(z);return new Float32Array([(cy*cz)*scale[0],(sx*sy*cz+cx*sz)*scale[0],(-cx*sy*cz+sx*sz)*scale[0],0,(-cy*sz)*scale[1],(-sx*sy*sz+cx*cz)*scale[1],(cx*sy*sz+sx*cz)*scale[1],0,sy*scale[2],-sx*cy*scale[2],cx*cy*scale[2],0,position[0],position[1],position[2],1])}
};
const sub=(a,b)=>a.map((v,i)=>v-b[i]),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],norm=a=>{let l=Math.hypot(...a);return a.map(v=>v/l)};
