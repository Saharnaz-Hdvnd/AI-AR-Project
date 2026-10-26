import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { PLYLoader } from './vendor/PLYLoader.js';

const [doc, poseDoc, intrinsics] = await Promise.all([
  fetch('./annotations.json').then(r=>r.json()),
  fetch('./capture-metadata/camera-poses.json').then(r=>r.json()),
  fetch('./capture-metadata/left_camera_mruk_intrinsics.json').then(r=>r.json())
]);
const video = document.querySelector('#video');
const overlay = document.querySelector('#overlay');
const octx = overlay.getContext('2d');
const playButton = document.querySelector('#play');
const scrub = document.querySelector('#scrub');
const elapsed = document.querySelector('#elapsed');
const canvas = document.querySelector('#scene');
const renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:false});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor('#071012');
const scene = new THREE.Scene();
scene.background = new THREE.Color('#071012');
scene.add(new THREE.HemisphereLight(0xd5f1ff,0x263033,2));
const light = new THREE.DirectionalLight(0xffffff,2.1); light.position.set(2,4,3); scene.add(light);
const camera = new THREE.PerspectiveCamera(48,1,0.01,100);
camera.fov=2*Math.atan(intrinsics.resolution.height/(2*intrinsics.focalLength.y))*180/Math.PI;
camera.updateProjectionMatrix();
const controls = new OrbitControls(camera,renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = .08;
const root = new THREE.Group(); scene.add(root);
const loader = new PLYLoader();
const bundles = new Map();

function tagTexture(text,color) {
  const c=document.createElement('canvas'); c.width=640; c.height=128;
  const x=c.getContext('2d'); x.fillStyle='#071716e8'; x.strokeStyle=color; x.lineWidth=7;
  x.beginPath(); x.roundRect(5,5,630,118,22); x.fill(); x.stroke();
  x.fillStyle='#f3fff9'; x.font='bold 44px system-ui'; x.fillText(text,24,78,585);
  const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace;
  return t;
}

for (const part of doc.parts) {
  const geometry=await new Promise((resolve,reject)=>loader.load('./'+part.pointCloud,resolve,undefined,reject));
  const points=new THREE.Points(geometry,new THREE.PointsMaterial({size:.009,vertexColors:true,sizeAttenuation:true}));
  points.name=part.id; root.add(points);
  const p=part.center;
  const label=new THREE.Sprite(new THREE.SpriteMaterial({map:tagTexture(part.label,part.color),depthTest:false,transparent:true}));
  label.position.set(p[0],p[1]+.075,p[2]); label.scale.set(.32,.064,1); label.renderOrder=5; root.add(label);
  bundles.set(part.id,{part,points,label,visible:true});
}

const roomGeometry=await new Promise((resolve,reject)=>loader.load('./capture-space-room.ply',resolve,undefined,reject));
const roomPoints=new THREE.Points(roomGeometry,new THREE.PointsMaterial({size:.006,vertexColors:true,sizeAttenuation:true,transparent:true,opacity:.42}));
roomPoints.name='capture-space-depth-map';root.add(roomPoints);
document.querySelector('#showRoom').addEventListener('change',e=>{roomPoints.visible=e.target.checked;});

const bounds=new THREE.Box3().setFromObject(root);
const center=bounds.getCenter(new THREE.Vector3());
const size=bounds.getSize(new THREE.Vector3());
const extent=Math.max(size.x,size.y,size.z,.5);
const grid=new THREE.GridHelper(Math.max(2,Math.ceil(extent*2)),Math.max(10,Math.ceil(extent*20)),0x406057,0x1b302c);
grid.position.set(center.x,bounds.min.y-.12,center.z); scene.add(grid);
controls.target.copy(center);
camera.position.set(center.x+extent*1.25,center.y+extent*.8,center.z+extent*1.6);
camera.near=Math.max(.01,extent/100); camera.far=extent*30; camera.updateProjectionMatrix();
controls.update();

const list=document.querySelector('#parts');
for (const [id,b] of bundles) {
  const label=document.createElement('label');
  const input=document.createElement('input'); input.type='checkbox'; input.checked=true;
  const swatch=document.createElement('span'); swatch.style.cssText=`width:11px;height:11px;border-radius:50%;background:${b.part.color};display:inline-block`;
  label.append(input,swatch,document.createTextNode(`${b.part.label} · ${b.part.pointCount.toLocaleString()} depth points`));
  input.addEventListener('change',()=>{b.visible=input.checked;b.points.visible=input.checked;b.label.visible=input.checked;drawOverlay();});
  list.append(label);
}
document.querySelector('#count').textContent=`${doc.parts.length} part observations · ${(doc.parts.reduce((n,p)=>n+p.pointCount,0)+roomGeometry.attributes.position.count).toLocaleString()} 3D points`;

const follow=document.querySelector('#follow');
const cameraRoll=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),Math.PI);
function followRecordedPose(){
  if(!follow.checked)return;
  let best=poseDoc.poses[0],delta=Math.abs(best.timeSeconds-video.currentTime);
  for(const p of poseDoc.poses){const d=Math.abs(p.timeSeconds-video.currentTime);if(d<delta){best=p;delta=d;}}
  camera.position.fromArray(best.position);
  camera.quaternion.set(...best.quaternion).multiply(cameraRoll);
  camera.updateMatrixWorld(true);
}
follow.addEventListener('change',()=>{controls.enabled=!follow.checked;if(follow.checked)followRecordedPose();});
controls.enabled=!follow.checked;
followRecordedPose();

const maskImages=new Map();
async function maskImage(part) {
  if(maskImages.has(part.id)) return maskImages.get(part.id);
  const img=new Image(); img.src='./'+part.mask; await img.decode(); maskImages.set(part.id,img); return img;
}
const frameGroups=new Map();
for(const a of doc.objects) { if(!frameGroups.has(a.frame)) frameGroups.set(a.frame,[]); frameGroups.get(a.frame).push(a); }
const frames=[...frameGroups.entries()].map(([frame,items])=>({frame,items,time:items[0].timeSeconds})).sort((a,b)=>a.time-b.time);
const markers=document.querySelector('#markers');
for(const f of frames) {
  const btn=document.createElement('button');
  btn.textContent=`${f.time.toFixed(1)}s · ${f.items.length} masks`;
  btn.title=f.items.map(x=>x.label).join(', ');
  btn.onclick=()=>{video.currentTime=f.time;video.pause();syncVideoTime();drawOverlay();}; markers.append(btn);
}

const formatTime = seconds => `${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;
playButton.addEventListener('click',()=>video.paused?video.play():video.pause());
video.addEventListener('click',()=>video.paused?video.play():video.pause());
video.addEventListener('play',()=>playButton.textContent='Pause');
video.addEventListener('pause',()=>playButton.textContent='Play');
video.addEventListener('loadedmetadata',()=>{scrub.max=video.duration;});
scrub.addEventListener('input',()=>{video.currentTime=Number(scrub.value);syncVideoTime();});
function syncVideoTime(){
  scrub.value=video.currentTime;
  elapsed.textContent=`${formatTime(video.currentTime)} / ${formatTime(video.duration||0)}`;
}
video.addEventListener('timeupdate',syncVideoTime);
video.addEventListener('seeked',syncVideoTime);

async function drawOverlay() {
  const rect=video.getBoundingClientRect();
  const w=Math.max(1,Math.round(rect.width*devicePixelRatio)); const h=Math.max(1,Math.round(rect.height*devicePixelRatio));
  if(overlay.width!==w||overlay.height!==h){overlay.width=w;overlay.height=h;}
  octx.clearRect(0,0,w,h);
  if(!video.videoWidth||!video.videoHeight)return;
  // Select overlays by the nearest recorded capture frame. The previous code
  // only rendered the five prompted instants and cleared the canvas between them.
  let frame=poseDoc.poses[0];
  for(const p of poseDoc.poses) if(Math.abs(p.timeSeconds-video.currentTime)<Math.abs(frame.timeSeconds-video.currentTime)) frame=p;
  const sx=w/1280, sy=h/1280;
  const frameId=String(frame.frame).padStart(6,'0');
  for(const [enabled,path] of [
    [document.querySelector('#showParts').checked,`./capture-part-overlays/${frameId}.png`],
    [document.querySelector('#showTracking').checked,`./tracked-overlays/${frameId}.png`]
  ]) {
    if(!enabled) continue;
    let img=overlayImageCache.get(path);
    if(!img) {
      img=new Image(); overlayImageCache.set(path,img);
      if(overlayImageCache.size>8) overlayImageCache.delete(overlayImageCache.keys().next().value);
      img.onload=()=>{if(frameId===currentOverlayFrame)drawOverlay();};
      img.onerror=()=>{}; img.src=path;
    }
    if(img.complete&&img.naturalWidth) octx.drawImage(img,0,0,1280*sx,1280*sy);
  }
}
const overlayImageCache=new Map();
let currentOverlayFrame='';
const previousDrawOverlay=drawOverlay;
drawOverlay=async function(){
  let frame=poseDoc.poses[0];
  for(const p of poseDoc.poses) if(Math.abs(p.timeSeconds-video.currentTime)<Math.abs(frame.timeSeconds-video.currentTime)) frame=p;
  currentOverlayFrame=String(frame.frame).padStart(6,'0');
  return previousDrawOverlay();
};
document.querySelector('#showParts').addEventListener('change',drawOverlay);
document.querySelector('#showTracking').addEventListener('change',drawOverlay);

function resize(){
  const r=canvas.getBoundingClientRect();renderer.setSize(r.width,r.height,false);
  camera.aspect=r.width/r.height;camera.updateProjectionMatrix();drawOverlay();
}
new ResizeObserver(resize).observe(canvas);new ResizeObserver(drawOverlay).observe(video);
video.addEventListener('timeupdate',()=>{drawOverlay();followRecordedPose();});
video.addEventListener('seeked',()=>{drawOverlay();followRecordedPose();});
document.querySelector('#reset').onclick=()=>{controls.target.copy(center);camera.position.set(center.x+extent*1.25,center.y+extent*.8,center.z+extent*1.6);controls.update();};
function animate(){requestAnimationFrame(animate);controls.update();renderer.render(scene,camera);} animate();

