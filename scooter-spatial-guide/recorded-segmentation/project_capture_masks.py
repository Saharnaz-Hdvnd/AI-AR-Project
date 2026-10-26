#!/usr/bin/env python3
"""Project reviewed scooter-part depth points into every recorded camera frame."""
from __future__ import annotations

import json, re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "capture-part-overlays"
W = H = 1280
DEPTH_W = DEPTH_H = 320


def quaternion_matrix(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def read_ply(path):
    content = path.read_bytes()
    end = content.index(b"end_header\n") + len(b"end_header\n")
    count = int(re.search(rb"element vertex (\d+)", content[:end]).group(1))
    dtype = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                      ("red", "u1"), ("green", "u1"), ("blue", "u1")])
    rows = np.frombuffer(content[end:], dtype=dtype, count=count)
    return np.column_stack((rows["x"], rows["y"], rows["z"])).astype(np.float64)


def main():
    annotations = json.loads((ROOT / "annotations.json").read_text())
    poses = json.loads((ROOT / "capture-metadata/camera-poses.json").read_text())["poses"]
    intr = json.loads((ROOT / "capture-metadata/left_camera_mruk_intrinsics.json").read_text())
    fx, fy = float(intr["focalLength"]["x"]), float(intr["focalLength"]["y"])
    cx, cy = float(intr["principalPoint"]["x"]), float(intr["principalPoint"]["y"])
    # Limit each depth-lifted annotation to the part of the take where it was
    # reviewed. Re-projecting an old observation through the whole take makes
    # labels appear detached when the camera or the object has moved.
    active_frames = {
        "pliers-on-mat": (0, 95),
        "screwdriver": (0, 95),
        "rear-shock": (145, 220),
        "seatpost-clamp": (150, 210),
        "deck": (80, 230),
        "steering-stem": (80, 230),
        "folding-joint": (80, 230),
        "rear-wheel": (220, 325),
        "left-grip": (275, 384),
        "left-brake": (275, 384),
        "handlebar-tube": (275, 384),
        "right-display": (275, 384),
        "right-grip": (275, 384),
        "right-brake": (275, 384),
        "pliers-in-hand": (335, 384),
    }
    priority = {"rear-shock": 0, "seatpost-clamp": 1}
    parts = sorted((p for p in annotations["parts"] if p["id"] in active_frames),
                   key=lambda p: priority.get(p["id"], 10))
    clouds = {p["id"]: read_ply(ROOT / p["pointCloud"]) for p in parts}
    labels = {p["id"]: p["label"] for p in parts}
    colors = {p["id"]: tuple(bytes.fromhex(p["color"].lstrip("#"))) for p in parts}
    frames = len(poses)
    OUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=30)
    records = {}

    for i, pose in enumerate(poses):
        position = np.asarray(pose["position"], dtype=np.float64)
        rotation = quaternion_matrix(pose["quaternion"])
        depth_path = ROOT / f"registered/registered-depth/{i:06d}.bin"
        depth = np.fromfile(depth_path, dtype="<u2").reshape(DEPTH_H, DEPTH_W) if depth_path.exists() else None
        image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image, "RGBA")
        frame_parts = []
        placed_tags = []
        for part in parts:
            first_frame, last_frame = active_frames[part["id"]]
            if not first_frame <= i <= last_frame:
                continue
            world = clouds[part["id"]]
            # Inverse of process_capture.py's camera-to-capture-space transform.
            camera = (world - position) @ rotation
            distance = -camera[:, 2]
            valid = distance > 0.12
            if not np.any(valid):
                continue
            camera, distance = camera[valid], distance[valid]
            u = fx * camera[:, 0] / distance + cx
            v = cy - fy * camera[:, 1] / distance
            px, py = np.rint(u).astype(np.int32), np.rint(v).astype(np.int32)
            valid = (px >= 0) & (px < W) & (py >= 0) & (py < H)
            px, py, distance = px[valid], py[valid], distance[valid]
            if depth is not None and len(px):
                observed = depth[np.clip(py // 4, 0, DEPTH_H-1), np.clip(px // 4, 0, DEPTH_W-1)].astype(np.float32) / 1000.0
                visible = (observed <= 0) | (distance <= observed + 0.09)
                px, py = px[visible], py[visible]
            if len(px) < 8:
                continue
            # PLY projections use the upright registered-depth image coordinates.
            # The displayed video is rotated 180 degrees, so flip horizontal only
            # here: the source PLY's vertical coordinate already has the video flip.
            sx = W - 1 - px
            sy = py
            color = colors[part["id"]]
            is_tool = part["id"] in {"pliers-on-mat", "screwdriver", "pliers-in-hand"}
            radius = 5 if is_tool else 4
            alpha = 128 if is_tool else 88
            for x, y in zip(sx.tolist(), sy.tolist()):
                draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(*color, alpha))
            # Use a robust center rather than the full point-cloud bounds. A
            # few depth outliers can otherwise pull a tag far away from the
            # visible object.
            anchor_x = int(np.median(sx))
            anchor_y = int(np.median(sy))
            label = labels[part["id"]]
            text_box = draw.textbbox((0, 0), label, font=font)
            tw, th = text_box[2]-text_box[0], text_box[3]-text_box[1]
            lx = max(3, min(W-tw-11, anchor_x-tw//2))
            top = max(2, anchor_y-th-15)
            candidate = (lx-3, top, lx+tw+4, top+th+7)
            if any(candidate[0] < old[2]+3 and candidate[2] > old[0]-3 and
                   candidate[1] < old[3]+3 and candidate[3] > old[1]-3
                   for old in placed_tags):
                # Keep labels attached to their own mask. If two annotations
                # are too crowded, omit the duplicate tag in this frame
                # instead of pushing it into empty space.
                continue
            tag_box = (lx-4, top, lx+tw+5, top+th+8)
            placed_tags.append(tag_box)
            draw.line(((tag_box[0]+tag_box[2])//2, tag_box[3], anchor_x,
                       anchor_y), fill=(*color, 220), width=2)
            draw.rounded_rectangle(tag_box, radius=5, fill=(7, 23, 24, 236),
                                   outline=(*color, 245), width=2)
            draw.text((lx, top+3), label, font=font, fill=(255, 255, 255, 255))
            frame_parts.append({"id": part["id"], "label": label, "visiblePoints": len(px)})
        image.save(OUT / f"{i:06d}.png", optimize=True)
        records[str(i)] = frame_parts
        if i % 50 == 0:
            print(f"projected {i+1}/{frames}", flush=True)

    (ROOT / "capture-part-overlays.json").write_text(json.dumps({
        "method": "Reviewed scooter-part depth point clouds projected with the recorded camera pose and current depth occlusion",
        "frameCount": frames,
        "coordinateFrame": "OpenXR tracking space from this take; not a persistent room anchor",
        "frameParts": records,
        "excludedDynamicObjects": ["seat (SAM 2 tracked overlay is separate)"],
        "activeFrameRanges": active_frames,
        "warning": "Depth-lifted point-surface overlays are limited to reviewed visibility windows; they can remain sparse because the capture has no dense depth for every pixel."
    }, indent=2))
    print(json.dumps({"frames": frames, "parts": [p["id"] for p in parts]}, indent=2))


if __name__ == "__main__":
    main()
