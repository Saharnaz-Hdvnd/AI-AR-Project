#!/usr/bin/env python3
"""Add reviewed seat-area components to this scooter spatial take."""
from __future__ import annotations
import csv, json, sys
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SERVICE = Path(__import__('os').environ['SAM_SERVICE_ROOT']).expanduser().resolve()
sys.path.insert(0, str(SERVICE / 'sam2-src'))
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

FRAME = 160
ITEMS = [
    {
        "id": "rear-shock", "label": "Rear shock absorber", "box": [480, 220, 650, 430],
        "points": [[545, 310, 1], [570, 365, 1], [490, 230, 0], [635, 350, 0], [620, 410, 0]],
        "candidate": 2, "color": "#79d8ff"
    },
    {
        "id": "seatpost-clamp", "label": "Seatpost clamp", "box": [565, 365, 810, 535],
        "points": [[650, 435, 1], [730, 450, 1], [605, 405, 0], [680, 515, 0], [795, 475, 0]],
        "candidate": 1, "color": "#ffc46b"
    },
]


def quat_matrix(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]], dtype=np.float64)


def write_ply(path, points, colors):
    points=np.asarray(points,dtype=np.float32); colors=np.asarray(colors,dtype=np.uint8)
    header=("ply\nformat binary_little_endian 1.0\n" f"element vertex {len(points)}\n"
            "property float x\nproperty float y\nproperty float z\n"
            "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
    dtype=np.dtype([("x","<f4"),("y","<f4"),("z","<f4"),("red","u1"),("green","u1"),("blue","u1")])
    data=np.empty(len(points),dtype=dtype); data["x"],data["y"],data["z"]=points.T
    data["red"],data["green"],data["blue"]=colors.T
    with path.open("wb") as f: f.write(header.encode("ascii")); data.tofile(f)


def main():
    annotations=json.loads((ROOT/"annotations.json").read_text())
    image=np.asarray(Image.open(ROOT/f"keyframes/frame-{FRAME:06d}.jpg").convert("RGB")).copy()
    predictor=SAM2ImagePredictor(build_sam2(
        "configs/sam2.1/sam2.1_hiera_t.yaml",
        str(SERVICE/"sam2-src/checkpoints/sam2.1_hiera_tiny.pt"),
        device="mps" if torch.backends.mps.is_available() else "cpu"))
    predictor.set_image(image)
    meta=[r for r in csv.DictReader((ROOT/"capture-metadata/left_camera_mruk_frame_metadata.csv").open())
          if r["file_name"]=="left_camera.mp4"]
    packets=list(csv.DictReader((ROOT/"capture-metadata/left_camera.mp4.packets.csv").open()))
    packet_time=int(packets[FRAME]["pts_us"])/1_000_000
    intr=json.loads((ROOT/"capture-metadata/left_camera_mruk_intrinsics.json").read_text())
    fx,fy=float(intr["focalLength"]["x"]),float(intr["focalLength"]["y"])
    cx,cy=float(intr["principalPoint"]["x"]),float(intr["principalPoint"]["y"])
    depth=np.fromfile(ROOT/f"registered/registered-depth/{FRAME:06d}.bin",dtype="<u2").reshape(320,320)
    preview=Image.fromarray(image).convert("RGBA")
    new_parts=[]; new_objects=[]; results=[]
    for item in ITEMS:
        pts=np.asarray([[p[0],p[1]] for p in item["points"]],np.float32)
        labs=np.asarray([p[2] for p in item["points"]],np.int32)
        with torch.inference_mode():
            masks,scores,_=predictor.predict(point_coords=pts,point_labels=labs,
                box=np.asarray(item["box"],np.float32),multimask_output=True)
        cand=item["candidate"]; mask=np.asarray(masks[cand]).squeeze().astype(bool)
        if not mask.any(): raise RuntimeError(f"SAM returned empty mask for {item['id']}")
        item.update(frame=FRAME,timeSeconds=packet_time,score=float(scores[cand]),areaFraction=float(mask.mean()),
                    mask=f"masks/{item['id']}.png",pointCloud=f"parts/{item['id']}.ply",
                    captureCoordinateFrame="OpenXR tracking-space-derived, right-handed metres; not aligned to a later session")
        Image.fromarray(mask.astype(np.uint8)*255).save(ROOT/item["mask"])
        registered_mask=np.asarray(Image.fromarray(np.flipud(mask.astype(np.uint8)*255)).resize((320,320),Image.Resampling.NEAREST))>127
        valid=registered_mask & (depth>0)
        y,x=np.where(valid); z=depth[y,x].astype(np.float64)/1000.0
        u=(x+.5)*4.; v=(y+.5)*4.
        xyz_cam=np.column_stack(((u-cx)*z/fx,(cy-v)*z/fy,-z))
        row=meta[FRAME]
        pos=np.array([float(row[f"pose_pos_{c}"]) for c in "xyz"])*[1,1,-1]
        q=np.array([float(row[f"pose_rot_{c}"]) for c in "xyzw"])*[-1,-1,1,1]
        xyz_world=xyz_cam@quat_matrix(q).T+pos
        rgb=np.flipud(image)[y,x]
        write_ply(ROOT/item["pointCloud"],xyz_world,rgb)
        item["pointCount"]=int(len(xyz_world)); item["center"]=xyz_world.mean(axis=0).round(4).tolist() if len(xyz_world) else None
        new_objects.append(item)
        new_parts.append({k:item[k] for k in ["id","label","pointCloud","pointCount","center","color","frame","timeSeconds","score","areaFraction"]})
        color=tuple(bytes.fromhex(item["color"].lstrip("#")))
        layer=Image.new("RGBA",preview.size,(*color,0)); layer.putalpha(Image.fromarray((mask*105).astype(np.uint8)))
        preview=Image.alpha_composite(preview,layer)
        results.append({"id":item["id"],"score":round(item["score"],3),"areaPixels":int(mask.sum()),"depthPoints":len(xyz_world)})
    # Store the reviewed source-frame preview for auditing and the new timeline marker.
    draw=ImageDraw.Draw(preview); font=ImageFont.load_default(size=30)
    for item in new_objects:
        draw.rectangle(item["box"],outline=item["color"],width=3)
        tb=draw.textbbox((0,0),item["label"],font=font); tw=tb[2]-tb[0]; th=tb[3]-tb[1]
        x0,y0,x1,y1=item["box"]
        lx=max(3,min(1277-tw,(x0+x1)//2-tw//2)); top=max(3,y0-th-14)
        draw.rounded_rectangle((lx-5,top,lx+tw+5,top+th+8),radius=5,fill=(7,23,24,236),outline=item["color"],width=2)
        draw.text((lx,top+2),item["label"],font=font,fill="white")
    preview.save(ROOT/f"previews/frame-{FRAME:06d}-new-parts.png")
    annotations["objects"].extend(new_objects)
    annotations["parts"].extend(new_parts)
    (ROOT/"annotations.json").write_text(json.dumps(annotations,indent=2)+"\n")
    print(json.dumps({"frame":FRAME,"timeSeconds":round(packet_time,2),"newParts":results},indent=2))

if __name__=="__main__": main()
