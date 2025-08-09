
import streamlit as st
from textwrap import dedent

st.set_page_config(page_title="Flock & Flow – Streamlit", layout="wide")

st.title("🌀 Flock & Flow — Boids + Perlin (Streamlit, single file)")
st.caption("A lightweight demo you can run locally or deploy on Streamlit Cloud.")

with st.sidebar:
    st.header("Controls")
    boids = st.slider("Boids", 50, 700, 300, 10)
    trail = st.slider("Trail persistence", 0.02, 0.90, 0.15, 0.01)
    noise_scale = st.slider("Noise scale", 0.0008, 0.01, 0.002, 0.0002, format="%.4f")
    flow_strength = st.slider("Flow strength", 0.05, 1.50, 0.35, 0.05)
    show_vectors = st.toggle("Show flow vectors", False)
    dark = st.toggle("Dark mode", True)
    seed = st.number_input("Seed", min_value=0, max_value=999999, value=1337, step=1)

# Build an HTML/JS app that renders inside Streamlit (no extra packages)
html = f"""
<!doctype html>
<html>
<head>
<meta charset='utf-8' />
<meta name='viewport' content='width=device-width, initial-scale=1' />
<style>
  :root {{
    --bg-dark: #0b1220;
    --bg-light: #f9fafb;
    --ink-dark: #e5e7eb;
    --ink-light: #0f172a;
  }}
  html, body {{ margin:0; padding:0; height:100%; }}
  body {{
    background: {{'#0b1220' if dark else '#f9fafb'}};
    color: {{'#e5e7eb' if dark else '#0f172a'}};
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
  }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 8px; }}
  .canvas-shell {{
    border-radius: 16px; overflow: hidden;
    border: 1px solid #e2e8f0;
    box-shadow: 0 6px 18px rgba(0,0,0,0.08);
  }}
  .legend {{ opacity: .7; font-size: 12px; margin-top: 8px; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="canvas-shell">
      <canvas id="c" style="width:100%; display:block;"></canvas>
    </div>
    <div class="legend">
      Flocking (alignment/cohesion/separation) + Perlin flow field. Seed: {seed}. Boids: {boids}.
    </div>
  </div>

<script>
// PRNG + Perlin
function mulberry32(a){{
  return function(){{
    let t = a += 0x6d2b79f5;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }}
}
class Perlin {{
  constructor(seed=1){{
    const rand = mulberry32(seed);
    this.p = new Array(512);
    const perm = Array.from({{length:256}},(_,i)=>i).sort(()=>rand()-0.5);
    for(let i=0;i<512;i++) this.p[i]=perm[i&255];
  }}
  fade(t){{return t*t*t*(t*(t*6-15)+10);}}
  lerp(t,a,b){{return a+t*(b-a);}}
  grad(hash,x,y,z){{
    const h=hash&15; const u=h<8?x:y; const v=h<4?y:h===12||h===14?x:z;
    return ((h&1)===0?u:-u)+((h&2)===0?v:-v);
  }}
  noise(x,y,z=0){{
    let X=Math.floor(x)&255, Y=Math.floor(y)&255, Z=Math.floor(z)&255;
    x-=Math.floor(x); y-=Math.floor(y); z-=Math.floor(z);
    const u=this.fade(x), v=this.fade(y), w=this.fade(z);
    const p=this.p;
    const A=p[X]+Y, AA=p[A]+Z, AB=p[A+1]+Z, B=p[X+1]+Y, BA=p[B]+Z, BB=p[B+1]+Z;
    return this.lerp(w,
      this.lerp(v,
        this.lerp(u, this.grad(p[AA],x,y,z), this.grad(p[BA],x-1,y,z)),
        this.lerp(u, this.grad(p[AB],x,y-1,z), this.grad(p[BB],x-1,y-1,z))
      ),
      this.lerp(v,
        this.lerp(u, this.grad(p[AA+1],x,y,z-1), this.grad(p[BA+1],x-1,y,z-1)),
        this.lerp(u, this.grad(p[AB+1],x,y-1,z-1), this.grad(p[BB+1],x-1,y-1,z-1))
      )
    );
  }}
}}

// Boid
class Boid {{
  constructor(x,y){{
    const a = Math.random()*Math.PI*2;
    this.pos={{x,y}}; this.vel={{x:Math.cos(a), y:Math.sin(a)}}; this.acc={{x:0,y:0}};
    this.maxSpeed=2.2; this.maxForce=0.05;
  }}
  applyForce(f){{ this.acc.x+=f.x; this.acc.y+=f.y; }}
  edges(w,h){{ if(this.pos.x<0) this.pos.x=w; if(this.pos.x>w) this.pos.x=0; if(this.pos.y<0) this.pos.y=h; if(this.pos.y>h) this.pos.y=0; }}
  update(){{
    this.vel.x+=this.acc.x; this.vel.y+=this.acc.y;
    const s=Math.hypot(this.vel.x,this.vel.y);
    if(s>this.maxSpeed){{ this.vel.x=(this.vel.x/s)*this.maxSpeed; this.vel.y=(this.vel.y/s)*this.maxSpeed; }}
    this.pos.x+=this.vel.x; this.pos.y+=this.vel.y; this.acc.x=this.acc.y=0;
  }}
  flock(boids, params){{
    const {{alignDist, cohesionDist, separationDist, separationWeight, alignWeight, cohesionWeight}} = params;
    let steerA={{x:0,y:0}}, steerC={{x:0,y:0}}, steerS={{x:0,y:0}};
    let ta=0, tc=0, ts=0;
    for(const other of boids){{
      if(other===this) continue;
      const dx=other.pos.x-this.pos.x, dy=other.pos.y-this.pos.y; const d=Math.hypot(dx,dy);
      if(d<alignDist){{ steerA.x+=other.vel.x; steerA.y+=other.vel.y; ta++; }}
      if(d<cohesionDist){{ steerC.x+=other.pos.x; steerC.y+=other.pos.y; tc++; }}
      if(d<separationDist){{ steerS.x-=dx/(d*d+0.0001); steerS.y-=dy/(d*d+0.0001); ts++; }}
    }}
    if(ta){{ steerA.x/=ta; steerA.y/=ta; const m=Math.hypot(steerA.x,steerA.y)||1; steerA.x=(steerA.x/m)*this.maxSpeed-this.vel.x; steerA.y=(steerA.y/m)*this.maxSpeed-this.vel.y; }}
    if(tc){{ steerC.x=steerC.x/tc - this.pos.x; steerC.y=steerC.y/tc - this.pos.y; const d=Math.hypot(steerC.x,steerC.y)||1; steerC.x=(steerC.x/d)*this.maxSpeed-this.vel.x; steerC.y=(steerC.y/d)*this.maxSpeed-this.vel.y; }}
    const limit=(v,mf=this.maxForce)=>{{ const m=Math.hypot(v.x,v.y)||1; return m>mf?{{x:(v.x/m)*mf,y:(v.y/m)*mf}}:v; }};
    this.applyForce(limit({{x:steerA.x*alignWeight,y:steerA.y*alignWeight}}));
    this.applyForce(limit({{x:steerC.x*cohesionWeight,y:steerC.y*cohesionWeight}}));
    this.applyForce(limit({{x:steerS.x*separationWeight,y:steerS.y*separationWeight}}));
  }}
}}

// params from sidebar
const SETTINGS = {{
  BOIDS: {boids},
  TRAIL: {trail},
  NOISE_SCALE: {noise_scale},
  FLOW_STRENGTH: {flow_strength},
  SHOW_VECTORS: {str(show_vectors).lower()},
  DARK: {str(dark).lower()},
  SEED: {seed}
}};

const perlin = new Perlin(SETTINGS.SEED);
const params = {{ alignDist: 36, cohesionDist: 48, separationDist: 24, alignWeight: 0.7, cohesionWeight: 0.35, separationWeight: 0.85 }};

const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
function fit(){{
  const w = canvas.parentElement.clientWidth || 900;
  canvas.width = w;
  canvas.height = Math.min(720, w*0.55);
}}
fit(); window.addEventListener('resize', fit);

const boids = [];
for(let i=0;i<SETTINGS.BOIDS;i++) boids.push(new Boid(Math.random()*canvas.width, Math.random()*canvas.height));

let t=0, running=true;
function loop(){{
  const w=canvas.width, h=canvas.height;
  ctx.fillStyle = SETTINGS.DARK ? `rgba(2,4,8,${{1-SETTINGS.TRAIL}})` : `rgba(250,250,255,${{1-SETTINGS.TRAIL}})`;
  ctx.fillRect(0,0,w,h);

  for(const b of boids){{
    const angle = perlin.noise(b.pos.x*SETTINGS.NOISE_SCALE, b.pos.y*SETTINGS.NOISE_SCALE, t*0.003) * Math.PI * 4;
    b.applyForce({{x: Math.cos(angle)*SETTINGS.FLOW_STRENGTH, y: Math.sin(angle)*SETTINGS.FLOW_STRENGTH}});
    b.flock(boids, params);
    b.update();
    b.edges(w,h);
  }}

  ctx.save(); ctx.translate(0.5,0.5);
  for(const b of boids){{
    const ang=Math.atan2(b.vel.y,b.vel.x);
    ctx.beginPath();
    ctx.moveTo(b.pos.x + Math.cos(ang)*8, b.pos.y + Math.sin(ang)*8);
    ctx.lineTo(b.pos.x + Math.cos(ang+2.5)*6, b.pos.y + Math.sin(ang+2.5)*6);
    ctx.lineTo(b.pos.x + Math.cos(ang-2.5)*6, b.pos.y + Math.sin(ang-2.5)*6);
    ctx.closePath();
    ctx.globalAlpha=0.9;
    ctx.fillStyle = SETTINGS.DARK ? "#10b981" : "#1e3a8a";
    ctx.fill();
  }}
  ctx.restore();

  if(SETTINGS.SHOW_VECTORS){{
    ctx.save(); ctx.globalAlpha=0.2; ctx.strokeStyle = SETTINGS.DARK ? "#60A5FA" : "#111827";
    for(let y=0;y<h;y+=26){{
      for(let x=0;x<w;x+=26){{
        const a=perlin.noise(x*SETTINGS.NOISE_SCALE, y*SETTINGS.NOISE_SCALE, t*0.003)*Math.PI*4;
        ctx.beginPath(); ctx.moveTo(x,y); ctx.lineTo(x+Math.cos(a)*10, y+Math.sin(a)*10); ctx.stroke();
      }}
    }}
    ctx.restore();
  }}

  t+=1; if(running) requestAnimationFrame(loop);
}}
requestAnimationFrame(loop);
</script>
</body>
</html>
"""

from streamlit.components.v1 import html as st_html
st_html(html, height=560, scrolling=False)
