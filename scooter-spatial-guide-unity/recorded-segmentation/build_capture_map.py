#!/usr/bin/env python3
"""Build a sparse capture-space background point cloud and recorded camera path."""
import csv,json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent
CAP=Path(__import__('os').environ.get('QUEST_CAPTURE_DIR', ROOT)).expanduser().resolve()
FRAMES=Path(__import__('os').environ.get('QUEST_VIDEO_FRAMES_DIR', CAP / 'frames')).expanduser().resolve()
def rot(q):
 x,y,z,w=q
 return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def write_ply(path,p,c):
 dt=np.dtype([('x','<f4'),('y','<f4'),('z','<f4'),('red','u1'),('green','u1'),('blue','u1')]);a=np.empty(len(p),dt)
 a['x'],a['y'],a['z']=p.T;a['red'],a['green'],a['blue']=c.T
 with open(path,'wb') as f:f.write((f"ply\nformat binary_little_endian 1.0\nelement vertex {len(a)}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n").encode());a.tofile(f)

intr=json.loads((ROOT/'capture-metadata/left_camera_mruk_intrinsics.json').read_text());fx=intr['focalLength']['x'];fy=intr['focalLength']['y'];cx=intr['principalPoint']['x'];cy=intr['principalPoint']['y']
meta=[r for r in csv.DictReader(open(ROOT/'capture-metadata/left_camera_mruk_frame_metadata.csv')) if r['file_name']=='left_camera.mp4']
pack=list(csv.DictReader(open(ROOT/'capture-metadata/left_camera.mp4.packets.csv')))
poses=[]
for i,(m,p) in enumerate(zip(meta,pack)):
 pos=[float(m[f'pose_pos_{c}'])*(1 if c!='z' else -1) for c in 'xyz'];q=[float(m[f'pose_rot_{c}'])*(-1 if c in 'xy' else 1) for c in 'xyzw']
 poses.append({'frame':i,'timeSeconds':int(p['pts_us'])/1e6,'position':pos,'quaternion':q})
json.dump({'frame':'OpenXR tracking space from this take, right-handed metres; not a room anchor','poses':poses},open(ROOT/'capture-metadata/camera-poses.json','w'),indent=2)

rng=np.random.default_rng(20261025);P=[];C=[];depdir=ROOT/'registered/registered-depth'
for i in range(0,len(meta),3):
 path=depdir/f'{i:06d}.bin'
 if not path.exists():continue
 d=np.fromfile(path,dtype='<u2').reshape(320,320);yy,xx=np.where(d>0)
 if len(xx)>2200:
  keep=rng.choice(len(xx),2200,replace=False);xx,yy=xx[keep],yy[keep]
 if not len(xx):continue
 img=np.asarray(Image.open(FRAMES/f'{i:05d}.jpg').convert('RGB'));small=np.asarray(Image.fromarray(np.flipud(img)).resize((320,320),Image.Resampling.BOX))
 z=d[yy,xx].astype(np.float64)/1000.;u=(xx+.5)*4.;v=(yy+.5)*4.
 cam=np.column_stack(((u-cx)*z/fx,(cy-v)*z/fy,-z));r=meta[i]
 pos=np.array([float(r[f'pose_pos_{c}']) for c in 'xyz'])*[1,1,-1];q=np.array([float(r[f'pose_rot_{c}']) for c in 'xyzw'])*[-1,-1,1,1]
 P.append(cam@rot(q).T+pos);C.append(small[yy,xx]);
pts=np.concatenate(P).astype(np.float32);cols=np.concatenate(C).astype(np.uint8);write_ply(ROOT/'capture-space-room.ply',pts,cols)
print(json.dumps({'cameraPoses':len(poses),'backgroundPoints':len(pts),'sampledEveryFrames':3,'physicalRoomAnchor':'not available; take exported no MRUK room geometry'},indent=2))
