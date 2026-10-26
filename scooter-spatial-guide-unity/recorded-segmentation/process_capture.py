#!/usr/bin/env python3
"""Create reviewed SAM2 masks and lift their captured depth into world-space PLYs.

This task-specific recipe uses OpenClaw's MRUK camera poses and registered-depth
derivation from the upstream quest-spatial-studio editor tools. It only uses the
selected keyframes listed below; it does not claim full-video object tracking.
"""
from __future__ import annotations

import argparse, csv, json, os, subprocess, sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

SAM2_SRC_VALUE = os.environ.get("SAM2_SRC", "")
if not SAM2_SRC_VALUE:
    raise SystemExit("Set SAM2_SRC to the installed SAM 2 source folder.")
SAM2_SRC = Path(SAM2_SRC_VALUE)
sys.path.insert(0, str(SAM2_SRC))
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


def quat_matrix(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]], dtype=np.float64)


def write_ply(path, points, colors):
    points = np.asarray(points, dtype=np.float32)
    colors = np.asarray(colors, dtype=np.uint8)
    header = ("ply\nformat binary_little_endian 1.0\n"
              f"element vertex {len(points)}\n"
              "property float x\nproperty float y\nproperty float z\n"
              "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
    dtype = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                      ("red", "u1"), ("green", "u1"), ("blue", "u1")])
    data = np.empty(len(points), dtype=dtype)
    data["x"], data["y"], data["z"] = points.T
    data["red"], data["green"], data["blue"] = colors.T
    with path.open("wb") as f:
        f.write(header.encode("ascii")); data.tofile(f)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("capture", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--model-config", default="configs/sam2.1/sam2.1_hiera_t.yaml")
    a = p.parse_args()
    src, out = a.capture.resolve(), a.output.resolve()
    keydir = out / "keyframes"; maskdir = out / "masks"; previewdir = out / "previews"; partdir = out / "parts"
    for d in (keydir, maskdir, previewdir, partdir): d.mkdir(parents=True, exist_ok=True)
    frame_ids = [0, 40, 80, 120, 160, 200, 240, 280, 320, 360]
    seq = out / "_selected"
    seq.mkdir(exist_ok=True)
    select = "+".join(f"eq(n,{i})" for i in frame_ids)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src / "left_camera.mp4"),
                    "-vf", f"select='{select}'", "-fps_mode", "passthrough", "-start_number", "0",
                    str(seq / "%03d.png")], check=True)
    images = {}
    for ordinal, frame_id in enumerate(frame_ids):
        image_path = seq / f"{ordinal:03d}.png"
        if not image_path.is_file(): raise RuntimeError(f"Could not decode sampled video frame {frame_id}")
        rgb = np.asarray(Image.open(image_path).convert("RGB"))
        images[frame_id] = rgb
        Image.fromarray(rgb).save(keydir / f"frame-{frame_id:06d}.jpg", quality=94)
    for f in seq.glob("*.png"): f.unlink()
    seq.rmdir()

    # Keyframe-specific boxes and points were reviewed against these exact source frames.
    entries = [
        dict(frame=40, id="pliers-on-mat", label="Needle-nose pliers · on mat", box=[400,160,595,440],
             points=[[435,225,1],[565,230,1],[515,330,1],[515,405,1],[400,185,0],[592,300,0],[460,430,0],[520,165,0]], candidate=1, color="#42e5d0"),
        dict(frame=40, id="screwdriver", label="Screwdriver", box=[710,130,810,470], points=[[760,300,1]], candidate=2, color="#ffbd59"),
        dict(frame=40, id="seat", label="Seat", box=[480,680,930,1020], points=[[705,850,1]], candidate=2, color="#69a8ff"),
        dict(frame=120, id="deck", label="Deck / body panel", box=[380,100,660,650], points=[[520,375,1]], candidate=2, color="#ff7c8e"),
        dict(frame=120, id="steering-stem", label="Steering stem", box=[500,645,600,965],
             points=[[545,720,1],[545,800,1],[555,900,1],[500,750,0],[610,800,0],[600,940,0]], candidate=1, color="#d18cff"),
        dict(frame=120, id="folding-joint", label="Folding joint / collar", box=[500,575,630,700],
             points=[[560,620,1],[600,615,1],[490,660,0],[630,660,0]], candidate=2, color="#f5e66b"),
        dict(frame=280, id="rear-wheel", label="Rear wheel / hub", box=[640,0,940,390], points=[[790,155,1]], candidate=2, color="#75e69e"),
        dict(frame=320, id="left-grip", label="Left handlebar grip", box=[240,550,435,675], points=[[330,612,1]], candidate=2, color="#69a8ff"),
        dict(frame=320, id="left-brake", label="Left brake lever", box=[330,635,465,715], points=[[395,675,1]], candidate=2, color="#ffbd59"),
        dict(frame=320, id="handlebar-tube", label="Handlebar center tube", box=[675,470,1050,590],
             points=[[750,550,1],[850,530,1],[980,500,1],[800,480,0],[850,585,0],[1040,560,0]], candidate=1, color="#ff7c8e"),
        dict(frame=320, id="right-display", label="Right control / display", box=[985,390,1175,560], points=[[1080,475,1]], candidate=2, color="#42e5d0"),
        dict(frame=320, id="right-grip", label="Right grip / throttle", box=[1130,370,1278,510],
             points=[[1200,430,1],[1250,445,1],[1130,430,0],[1200,510,0]], candidate=0, color="#d18cff"),
        dict(frame=320, id="right-brake", label="Right brake lever", box=[1030,515,1260,615],
             points=[[1100,555,1],[1180,565,1],[1080,610,0],[1160,525,0]], candidate=1, color="#f5e66b"),
        dict(frame=360, id="pliers-in-hand", label="Needle-nose pliers · in hand", box=[580,450,900,900], points=[[740,675,1]], candidate=2, color="#42e5d0"),
    ]

    model = build_sam2(a.model_config, str(a.checkpoint), device="mps" if torch.backends.mps.is_available() else "cpu")
    predictor = SAM2ImagePredictor(model)
    masks = {}
    for item in entries:
        rgb = images[item["frame"]]
        predictor.set_image(rgb)
        b = item["box"]
        pts = np.asarray([[q[0], q[1]] for q in item["points"]], dtype=np.float32)
        labs = np.asarray([q[2] for q in item["points"]], dtype=np.int32)
        with torch.inference_mode():
            mm, scores, _ = predictor.predict(point_coords=pts, point_labels=labs, box=np.asarray(b, np.float32), multimask_output=True)
        cand = int(item["candidate"])
        mask = np.asarray(mm[cand]).squeeze().astype(bool)
        score = float(np.asarray(scores).reshape(-1)[cand])
        if not mask.any(): raise RuntimeError(f"Empty SAM mask: {item['id']}")
        masks[item["id"]] = mask
        item["score"] = score
        item["areaFraction"] = float(mask.mean())
        item["mask"] = f"masks/{item['id']}.png"
        item["pointCloud"] = f"parts/{item['id']}.ply"
        Image.fromarray(mask.astype(np.uint8) * 255).save(out / item["mask"])

    # Merge source-time masks into transparent review overlays; mask pixels stay off the MP4.
    packet_rows = list(csv.DictReader((src / "left_camera.mp4.packets.csv").open()))
    packet_times = {i: int(row["pts_us"]) / 1_000_000 for i, row in enumerate(packet_rows)}
    by_frame = {}
    for item in entries:
        item["timeSeconds"] = packet_times[item["frame"]]
        by_frame.setdefault(item["frame"], []).append(item)
    for frame_id, group in by_frame.items():
        base = Image.fromarray(images[frame_id]).convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0,0,0,0))
        for item in group:
            color = tuple(bytes.fromhex(item["color"][1:])) + (105,)
            layer = Image.new("RGBA", base.size, color)
            layer.putalpha(Image.fromarray((masks[item["id"]] * 105).astype(np.uint8)))
            overlay = Image.alpha_composite(overlay, layer)
        merged = Image.alpha_composite(base, overlay)
        d = ImageDraw.Draw(merged)
        for item in group:
            x0,y0,x1,y1 = item["box"]
            d.rounded_rectangle((x0,y0,x1,y1), radius=6, outline=item["color"], width=3)
            tw = d.textbbox((0,0), item["label"])[2]
            lx = max(0, min(merged.width - tw - 16, (x0+x1)//2-tw//2))
            ly = max(4, y0-30)
            d.rounded_rectangle((lx-6,ly-3,lx+tw+8,ly+22),radius=5,fill=(8,25,27,235),outline=item["color"],width=2)
            d.text((lx,ly),item["label"],fill="white")
        preview = f"previews/frame-{frame_id:06d}.png"
        merged.convert("RGB").save(out / preview, quality=93)
        for item in group: item["preview"] = preview

    # Deproject registered depth through each source RGB camera pose into the take's world frame.
    intr = json.loads((src / "left_camera_mruk_intrinsics.json").read_text())
    fx, fy = float(intr["focalLength"]["x"]), float(intr["focalLength"]["y"])
    cx, cy = float(intr["principalPoint"]["x"]), float(intr["principalPoint"]["y"])
    meta = [r for r in csv.DictReader((src / "left_camera_mruk_frame_metadata.csv").open()) if r["file_name"] == "left_camera.mp4"]
    if len(meta) != len(packet_rows): raise RuntimeError("Encoded-frame / camera-pose count mismatch")
    cloud_index = []
    registered = out / "registered" / "registered-depth"
    for item in entries:
        i = item["frame"]
        depth_path = registered / f"{i:06d}.bin"
        if not depth_path.is_file():
            raise FileNotFoundError(f"Run the upstream registered-depth derivation first: {depth_path}")
        depth = np.fromfile(depth_path, dtype="<u2").reshape(320,320)
        # The upstream RGB registration is upright; source MP4 rows are bottom-up.
        mask = np.asarray(Image.fromarray(np.flipud(masks[item["id"]].astype(np.uint8)*255)).resize((320,320), Image.Resampling.NEAREST)) > 127
        valid = mask & (depth > 0)
        y, x = np.where(valid)
        z = depth[y,x].astype(np.float64) / 1000.0
        u = (x + .5) * 4.0; v = (y + .5) * 4.0
        xyz_cam = np.column_stack(((u-cx)*z/fx, (cy-v)*z/fy, -z))
        r = meta[i]
        pos = np.array([float(r[f"pose_pos_{c}"]) for c in "xyz"]) * [1,1,-1]
        q = np.array([float(r[f"pose_rot_{c}"]) for c in "xyzw"]) * [-1,-1,1,1]
        xyz_world = xyz_cam @ quat_matrix(q).T + pos
        source_rgb = np.flipud(images[i])
        small_rgb = np.asarray(Image.fromarray(source_rgb).resize((320,320), Image.Resampling.BOX))
        rgb = small_rgb[y,x]
        if len(xyz_world) > 10000:
            rng = np.random.default_rng(20261025 + i)
            keep = rng.choice(len(xyz_world), 10000, replace=False)
            xyz_world, rgb = xyz_world[keep], rgb[keep]
        write_ply(out / item["pointCloud"], xyz_world, rgb)
        item["pointCount"] = len(xyz_world)
        item["center"] = np.mean(xyz_world, axis=0).round(4).tolist() if len(xyz_world) else None
        item["captureCoordinateFrame"] = "OpenXR tracking-space-derived, right-handed metres; not aligned to a later session"
        cloud_index.append({k:item[k] for k in ["id","label","pointCloud","pointCount","center","color","frame","timeSeconds","score","areaFraction"]})

    json.dump({"capture":"20261025_192936","durationSeconds":packet_times[max(packet_times)],"video":"left_camera.mp4",
               "coordinateFrame":"Quest capture tracking space (right-handed metres)","maskMethod":"SAM 2.1 Hiera Tiny; prompted and visually reviewed keyframes",
               "surfaceMethod":"Quest environment depth deprojected with MRUK per-frame camera pose and registered to MP4 frame coordinates",
               "objects":entries,"parts":cloud_index}, (out / "annotations.json").open("w"), indent=2)
    print(json.dumps({"keyframes":len(by_frame),"observations":len(entries),"withDepthPoints":sum(x["pointCount"]>0 for x in cloud_index),
                      "points":sum(x["pointCount"] for x in cloud_index),"meanSAMScore":round(float(np.mean([x["score"] for x in entries])),3)},indent=2))


if __name__ == "__main__": main()
