import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {setPose,frameAt} from './math.js';
import {createTwin,roomFromGeometry} from './twin.js';
const $=id=>document.getElementById(id),params=new URLSearchParams(location.search);
const defaultSession='sessions/20261011_153014/session.json';
const picker=$('take-picker');
if(picker){picker.value=params.get('session')||defaultSession;picker.addEventListener('change',()=>{location.href='?session='+encodeURIComponent(picker.value);});}
const sessionURL=new URL(params.get('session')||defaultSession,location.href);
const renderer=new THREE.WebGLRenderer({canvas:$('stage'),antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(1);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;
const maskCanvas=$('object-mask'),maskCtx=maskCanvas.getContext('2d');let objectTrack=null;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(),anchor=new THREE.Group();scene.add(anchor);
const pmrem=new THREE.PMREMGenerator(renderer);const roomEnv=new RoomEnvironment();scene.environment=pmrem.fromScene(roomEnv,.04).texture;roomEnv.dispose();pmrem.dispose();
scene.add(new THREE.HemisphereLight(0xddefff,0x485442,2));const sun=new THREE.DirectionalLight(0xffe5c8,3);sun.position.set(2,5,3);scene.add(sun);
// A grounded, recognizable calibration object. Not a claim of final AR art direction.
const body=new THREE.Mesh(new THREE.BoxGeometry(.45,.45,.45),new THREE.MeshStandardMaterial({color:0xd99c56,metalness:.3,roughness:.25}));body.position.y=.225;anchor.add(body);
const ring=new THREE.Mesh(new THREE.TorusGeometry(.34,.018,16,100),new THREE.MeshStandardMaterial({color:0xa8ddcb,metalness:.65,roughness:.22}));ring.rotation.x=Math.PI/2;ring.position.y=.035;anchor.add(ring);
let session,index=0,playing=false,start=0,startT=0,requested=0,room=null,modelName='calibration-cube',roomName=null,modelData=null,roomData=null;
const textures=new Map();
let roomGeometry=null,audioTrack=null;
const twin=createTwin({canvas:$('twin'),scene,camera,anchor,getRoom:()=>room,renderVideo:()=>renderer.render(scene,camera),togglePlayback:()=> $('play').click(),onMove:pos=>{['x','y','z'].forEach((k,i)=>$(k).value=pos.toArray()[i].toFixed(4));update();}});
function placement(){return {version:1,position:['x','y','z'].map(k=>Number($(k).value)),scale:Number($('scale').value),yaw:Number($('yaw').value),visible:$('visible').checked,model:modelName,room:roomName,modelData,roomData,roomGeometry,occlude:$('occlude').checked,roomWireframe:$('room-wireframe').checked};}
function applyPlacement(p){if(p.version!==1||!Array.isArray(p.position)||p.position.length!==3||![...p.position,p.scale,p.yaw].every(Number.isFinite)||p.scale<=0)throw Error('Invalid placement');['x','y','z'].forEach((k,i)=>$(k).value=p.position[i]);$('scale').value=p.scale;$('yaw').value=p.yaw;$('visible').checked=p.visible!==false;update();}
function update(){const p=placement();anchor.position.fromArray(p.position);anchor.scale.setScalar(Math.max(.001,p.scale));anchor.rotation.y=THREE.MathUtils.degToRad(p.yaw);anchor.visible=p.visible;twin.helper.visible=false;renderer.render(scene,camera);twin.render();}
async function texture(i){if(textures.has(i))return textures.get(i);const tx=await new THREE.TextureLoader().loadAsync(new URL(session.frames[i].image,sessionURL).href);tx.colorSpace=THREE.SRGBColorSpace;textures.set(i,tx);while(textures.size>8){const key=textures.keys().next().value;if(key===i)break;textures.get(key).dispose();textures.delete(key);}return tx;}
function drawObjectTrack(i){maskCtx.clearRect(0,0,maskCanvas.width,maskCanvas.height);const instances=objectTrack?.frames?.[i]||[];for(const obj of instances){const pts=obj.points;if(!pts||pts.length<3)continue;const hue=(obj.id*67)%360,stroke=`hsl(${hue} 95% 65%)`;maskCtx.save();maskCtx.lineJoin='round';maskCtx.lineWidth=4;maskCtx.strokeStyle=stroke;maskCtx.shadowColor=stroke;maskCtx.shadowBlur=10;maskCtx.fillStyle=`hsl(${hue} 90% 55% / .19)`;maskCtx.beginPath();pts.forEach(([x,y],n)=>n?maskCtx.lineTo(x,y):maskCtx.moveTo(x,y));maskCtx.closePath();maskCtx.fill();maskCtx.stroke();maskCtx.shadowBlur=0;const minX=Math.min(...pts.map(p=>p[0])),minY=Math.min(...pts.map(p=>p[1]));const label=`${obj.label} · ${obj.id}`;maskCtx.font='bold 20px system-ui';const w=maskCtx.measureText(label).width+20,x=Math.max(6,Math.min(maskCanvas.width-w-6,minX)),y=Math.max(28,minY-8);maskCtx.fillStyle=`hsl(${hue} 38% 16% / .94)`;maskCtx.fillRect(x,y-26,w,30);maskCtx.strokeStyle=stroke;maskCtx.lineWidth=1.5;maskCtx.strokeRect(x,y-26,w,30);maskCtx.fillStyle='#fff';maskCtx.fillText(label,x+10,y-6);maskCtx.restore();}}
async function setFrame(i){const ticket=++requested;const tx=await texture(i);if(ticket!==requested)return;index=i;scene.background=tx;twin.setHandTime(session.frames[i].timestampUs);setPose(camera,session.frames[i],session.intrinsics);drawObjectTrack(i);const maskCount=objectTrack?.frames?.[i]?.length||0;$('pose-status').textContent=`Frame ${i+1}/${session.frames.length} · ${maskCount} object masks · camera XYZ (m): ${session.frames[i].position.map(v=>v.toFixed(3)).join(', ')}`;$('timeline').value=session.frames[i].t;$('time').textContent=session.frames[i].t.toFixed(2)+' s';update();}
async function at(t){return setFrame(frameAt(session.frames,t));}
function pause(){audioTrack?.pause();playing=false;$('play').textContent='Play';}
$('play').onclick=()=>{if(playing){pause();return;}playing=true;start=performance.now();startT=Number($('timeline').value);if(startT>=session.frames.at(-1).t)startT=0;$('play').textContent='Pause';tick();};
function syncAudio(t){if(!audioTrack)return;const target=t-session.audio.startRelativeToVideoSeconds;if(target<0||!$('audio-enabled').checked){audioTrack.pause();return;}if(Math.abs(audioTrack.currentTime-target)>.3)audioTrack.currentTime=target;if(audioTrack.paused)audioTrack.play().catch(()=>{});}
async function tick(){if(!playing)return;const t=startT+(performance.now()-start)/1000;await at(Math.min(t,session.frames.at(-1).t));syncAudio(t);if(t>=session.duration){pause();return;}requestAnimationFrame(tick);}
for(const key of ['trajectory','frustum','hands','video'])$('debug-'+key).onchange=()=>twin.setDebug({[key]:$('debug-'+key).checked});
$('reset-view').onclick=()=>twin.resetView();
$('audio-enabled').onchange=()=>{if(!$('audio-enabled').checked)audioTrack?.pause();};
$('timeline').oninput=()=>{pause();at(Number($('timeline').value)).catch(fail);};
['x','y','z','scale','yaw','visible'].forEach(k=>$(k).oninput=update);
$('stage').onclick=e=>{pause();const r=e.target.getBoundingClientRect();const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2((e.clientX-r.left)/r.width*2-1,1-(e.clientY-r.top)/r.height*2),camera);const point=new THREE.Vector3();const plane=new THREE.Plane(new THREE.Vector3(0,1,0),-Number($('plane').value));if(ray.ray.intersectPlane(plane,point)){['x','y','z'].forEach((k,i)=>$(k).value=point.toArray()[i].toFixed(4));update();}};
const loader=new GLTFLoader();
async function glb(file,isRoom){pause();const data=await file.arrayBuffer();const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});const g=await loader.parseAsync(data,'');if(isRoom){if(room)scene.remove(room);room=g.scene;roomName=file.name;roomData=encoded;roomGeometry=null;scene.add(room);occlusion();}else{anchor.clear();anchor.add(g.scene);modelName=file.name;modelData=encoded;}update();}
function occlusion(){if(!room)return;room.traverse(o=>{if(o.isMesh){o.material=new THREE.MeshBasicMaterial({color:0x648c83,wireframe:!$('occlude').checked,colorWrite:!$('occlude').checked&&$('room-wireframe').checked,depthWrite:$('occlude').checked,side:THREE.DoubleSide});o.renderOrder=-1;}});update();}
$('room-json').onchange=async e=>{try{const doc=JSON.parse(await e.target.files[0].text());loadRoomGeometry(doc);roomName=e.target.files[0].name;}catch(err){fail(err);}};
function loadRoomGeometry(doc){const next=roomFromGeometry(doc);if(room)scene.remove(room);room=next;scene.add(room);roomGeometry=doc;roomData=null;roomName='Quest room geometry';occlusion();}
$('occlude').onchange=occlusion;$('room-wireframe').onchange=occlusion;for(const [id,isRoom]of [['model',false],['room',true]])$(id).onchange=e=>glb(e.target.files[0],isRoom).catch(fail);
$('save').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify(placement(),null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='placement.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
async function loadPlacement(p){for(const [key,name,isRoom] of [['modelData','model',false],['roomData','room',true]]){if(p[key]){if(!p[key].startsWith('data:'))throw Error('Only embedded local GLBs accepted');const b=await(await fetch(p[key])).blob();await glb(new File([b],p[name]||'asset.glb'),isRoom);}}if(p.roomGeometry)loadRoomGeometry(p.roomGeometry);applyPlacement(p);$('occlude').checked=!!p.occlude;$('room-wireframe').checked=!!p.roomWireframe;occlusion();}
$('load').onchange=async e=>{try{await loadPlacement(JSON.parse(await e.target.files[0].text()));}catch(err){fail(err);}};
function fail(e){$('status').textContent='Error: '+e.message;console.error(e);}
try{const res=await fetch(sessionURL);if(!res.ok)throw Error('Session not found — run the importer or demo generator.');session=await res.json();if(session.version!==1||!session.frames.length)throw Error('Unsupported/empty session');renderer.setSize(session.intrinsics.width,session.intrinsics.height,false);maskCanvas.width=session.intrinsics.width;maskCanvas.height=session.intrinsics.height;$('timeline').max=session.frames.at(-1).t;$('badge').textContent=session.synthetic?'Synthetic pipeline test':'Quest recording · calibration pending';$('details').textContent=`${session.frames.length} frames · ${session.duration.toFixed(2)} seconds · ${session.intrinsics.width} × ${session.intrinsics.height}`;$('status').textContent=session.synthetic?'Synthetic input, not a recording of your home. Physical Quest alignment has not been tested.':`Orientation: ${session.sourceRowOrder}. Verify a static target before trusting alignment. Maximum frame gap: ${session.report.maxGapSeconds.toFixed(3)} s.`;twin.setSession(session);try{const trackRes=await fetch(new URL('object-tracks.json',sessionURL));if(trackRes.ok){const doc=await trackRes.json();if(doc.session===session.name&&doc.imageSize?.[0]===maskCanvas.width&&doc.imageSize?.[1]===maskCanvas.height)objectTrack=doc;}}catch(e){console.warn('Object track sidecar unavailable',e);}
if(session.roomGeometryFile){loadRoomGeometry(await(await fetch(new URL(session.roomGeometryFile,sessionURL))).json());}
if(session.handsFile&&session.captureSchemaFile){
  const sampleText=await(await fetch(new URL(session.handsFile,sessionURL))).text();
  const schema=await(await fetch(new URL(session.captureSchemaFile,sessionURL))).json();
  const skeletons={};for(const side of ['left','right']){const file=session[side+'SkeletonFile'];if(file)skeletons[side]=await(await fetch(new URL(file,sessionURL))).json();}
  const shown=twin.setHands(sampleText.trim().split('\n').filter(Boolean).map(s=>JSON.parse(s)),schema,skeletons);
  $('hands-status').textContent=shown?'Hand joints loaded · timing alignment requires verification':'Raw hand log retained; this skeleton convention is not visualized.';
}
if(session.audio){audioTrack=new Audio(new URL(session.audio.file,sessionURL).href);$('audio-enabled').disabled=false;$('audio-status').textContent='Audio available · sync estimate; verify with a clap';}
if(params.has('placement')){const u=new URL(params.get('placement'),location.href);if(u.origin!==location.origin)throw Error('Placement URL must use this server');const response=await fetch(u);if(!response.ok)throw Error('Placement not found');await loadPlacement(await response.json());}
await setFrame(0);window.replay={ready:true,setFrame,at,placement,applyPlacement,loadPlacement,loadRoomGeometry,session,renderer,camera,anchor,twin};}catch(e){fail(e);window.replay={ready:false,error:e.message};}
