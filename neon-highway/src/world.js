export class ProceduralWorld{
 constructor(){this.elapsed=0;this.paused=false;this.last=performance.now()}
 tick(now){const dt=Math.min(.05,(now-this.last)/1000);this.last=now;if(!this.paused)this.elapsed+=dt;return this.elapsed}
 toggle(){this.paused=!this.paused;return this.paused}
}
