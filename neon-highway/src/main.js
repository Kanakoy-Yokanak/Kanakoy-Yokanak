import {Renderer} from './renderer.js';
import {ProceduralWorld} from './world.js';

const canvas=document.querySelector('#scene'),controls=document.querySelector('#controls'),debug=document.querySelector('#debug'),status=document.querySelector('#status');
let renderer;
try{renderer=new Renderer(canvas)}catch(error){console.error(error);document.querySelector('#fallback').hidden=false;status.hidden=true;throw error}
const world=new ProceduralWorld();
let idleTimer,debugOn=false,lastFrame=performance.now(),smoothedFrame=16.7;
function wake(){controls.classList.remove('idle');clearTimeout(idleTimer);idleTimer=setTimeout(()=>controls.classList.add('idle'),4200)}
function updateDebug(){const i=renderer.info();debug.textContent=`RENDER PIPELINE // LIVE
FPS                    ${(1000/smoothedFrame).toFixed(1)}
frame time             ${smoothedFrame.toFixed(2)} ms
requested resolution  ${i.requested.join(' × ')}
actual framebuffer    ${i.actual.join(' × ')}
devicePixelRatio      ${i.dpr}
WebGL version         ${i.version}
HDR target            ${i.hdr}
estimated GPU buffers ${i.estimatedMB.toFixed(0)} MB
MAX_TEXTURE_SIZE      ${i.limits.texture}
MAX_RENDERBUFFER_SIZE ${i.limits.renderbuffer}
MAX_VIEWPORT_DIMS     ${i.limits.viewport.join(' × ')}
draw calls            ${i.drawCalls}
triangles             ${Math.round(i.triangles)}
active preset         ${i.preset.toUpperCase()}
world time            ${world.elapsed.toFixed(2)} s
state                 ${world.paused?'PAUSED':'RUNNING'}`}
function setPreset(name){const supported=renderer.setPreset(name);document.querySelectorAll('[data-preset]').forEach(b=>b.classList.toggle('active',b.dataset.preset===name));status.textContent=supported?'FRAMEBUFFER READY':`GPU FALLBACK ${renderer.actual.join(' × ')}`;status.style.opacity=1;setTimeout(()=>status.style.opacity=0,1800);updateDebug();wake()}
function togglePause(){const paused=world.toggle();document.querySelector('#pause').textContent=paused?'RESUME':'PAUSE';wake()}
function toggleDebug(){debugOn=!debugOn;debug.hidden=!debugOn;document.querySelector('#debug-toggle').classList.toggle('active',debugOn);updateDebug();wake()}
function toggleFullscreen(){document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen?.();wake()}
document.querySelectorAll('[data-preset]').forEach(button=>button.onclick=()=>setPreset(button.dataset.preset));
document.querySelector('#pause').onclick=togglePause;document.querySelector('#debug-toggle').onclick=toggleDebug;document.querySelector('#fullscreen').onclick=toggleFullscreen;
addEventListener('keydown',event=>{if(event.repeat)return;const key=event.key.toLowerCase();if(key==='d')toggleDebug();else if(key==='f')toggleFullscreen();else if(key===' '){event.preventDefault();togglePause()}else if(['1','2','3','4'].includes(key))setPreset(['performance','high','4k','8k'][Number(key)-1])});
['pointermove','pointerdown','touchstart'].forEach(event=>addEventListener(event,wake,{passive:true}));addEventListener('resize',()=>{updateDebug();wake()});addEventListener('contextmenu',event=>event.preventDefault());
function frame(now){const frameMs=Math.min(100,now-lastFrame);lastFrame=now;smoothedFrame=smoothedFrame*.92+frameMs*.08;renderer.render(world.tick(now),frameMs);if(debugOn)updateDebug();requestAnimationFrame(frame)}
status.style.opacity=0;wake();requestAnimationFrame(frame);
