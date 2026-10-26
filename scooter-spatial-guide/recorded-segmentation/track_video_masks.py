#!/usr/bin/env python3
"""Propagate reviewed moving-object masks through this take with SAM2."""
from __future__ import annotations

import json, os, sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SERVICE = Path(os.environ["SAM_SERVICE_ROOT"]).expanduser().resolve()
FRAMES = Path(os.environ.get("SAM2_VIDEO_FRAMES", str(ROOT / "sam2-frames")))
sys.path.insert(0, str(SERVICE / "sam2-src"))
from sam2.build_sam import build_sam2_video_predictor

CHECKPOINT = SERVICE / "sam2-src/checkpoints/sam2.1_hiera_tiny.pt"
CONFIG = "configs/sam2.1/sam2.1_hiera_t.yaml"
OUT = ROOT / "tracked-overlays"
W = H = 1280


def tid(oid: str) -> str:
    # The two reviewed pliers masks are the same tool, first resting and later held.
    return "pliers" if oid.startswith("pliers-") else oid


def main() -> None:
    entries = json.loads((ROOT / "annotations.json").read_text())["objects"]
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        key = tid(entry["id"])
        # The seat is the moving assembly component in this take. The two pliers
        # prompts occur at opposite ends of a long sequence and can refer to
        # different placements, so do not let SAM bridge that gap as one object.
        if key == "seat":
            grouped.setdefault(key, []).append(entry)
    if not grouped:
        raise RuntimeError("No moving-object prompt masks were found")
    names = sorted(FRAMES.glob("*.jpg"), key=lambda p: int(p.stem))
    if not names:
        raise FileNotFoundError(FRAMES)

    object_ids = {key: index + 1 for index, key in enumerate(grouped)}
    id_to_key = {value: key for key, value in object_ids.items()}
    labels = {"seat": "Scooter seat"}
    colors = {key: tuple(bytes.fromhex(items[0]["color"].lstrip("#")))
              for key, items in grouped.items()}
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    torch.set_num_threads(min(6, torch.get_num_threads()))
    model = build_sam2_video_predictor(CONFIG, str(CHECKPOINT), device=device)

    # This Mac's SAM2/PyTorch build can return BF16 attention tensors beside
    # FP32 weights. Normalize attention inputs and Linear inputs at the module
    # boundary to avoid the reported BF16/FP32 matrix multiply crash.
    def cast_attention(module, args, kwargs):
        dtype = module.linear1.weight.dtype
        values = list(args)
        for index, value in enumerate(values[:4]):
            if torch.is_tensor(value) and value.is_floating_point():
                values[index] = value.to(dtype=dtype)
        for name in ("tgt", "memory", "pos", "query_pos"):
            value = kwargs.get(name)
            if torch.is_tensor(value) and value.is_floating_point():
                kwargs[name] = value.to(dtype=dtype)
        return tuple(values), kwargs

    def cast_linear(module, args):
        if args and torch.is_tensor(args[0]) and args[0].is_floating_point():
            return (args[0].to(dtype=module.weight.dtype), *args[1:])
        return args

    for layer in model.memory_attention.layers:
        layer.register_forward_pre_hook(cast_attention, with_kwargs=True)
    for module in model.memory_attention.modules():
        if isinstance(module, torch.nn.Linear):
            module.register_forward_pre_hook(cast_linear)

    state = model.init_state(video_path=str(FRAMES), offload_video_to_cpu=True,
                             offload_state_to_cpu=True)
    prompt_frames = []
    for key, prompts in grouped.items():
        for entry in prompts:
            raw = np.asarray(Image.open(ROOT / entry["mask"]).convert("L"))
            if raw.shape != (H, W):
                raise ValueError(f"Expected {(H, W)} mask, got {raw.shape}: {entry['mask']}")
            model.add_new_mask(state, int(entry["frame"]), object_ids[key], raw > 127)
            prompt_frames.append(int(entry["frame"]))

    # The seat is held close to the camera around frame 160 and changes scale
    # dramatically from the table view. Re-anchor SAM with one positive click
    # on its foam and negatives on the hand/background at that close-up.
    # Coordinates are in the original 1280x1280 recorded frame.
    if "seat" in object_ids and len(names) > 160:
        model.add_new_points_or_box(
            state, frame_idx=160, obj_id=object_ids["seat"],
            points=np.asarray([[500, 1030], [1130, 990], [690, 600], [85, 1170]], dtype=np.float32),
            labels=np.asarray([1, 0, 0, 0], dtype=np.int32),
            normalize_coords=True)
        prompt_frames.append(160)

    OUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=30)
    records: dict[str, list[dict]] = {}

    def write_frame(frame_index, ids, logits):
        rgba = np.zeros((H, W, 4), dtype=np.uint8)
        bounds = []
        masks = logits[:, 0].detach().float().cpu().numpy() > 0
        for numeric_id, mask in zip(ids, masks):
            key = id_to_key.get(int(numeric_id))
            if key is None:
                continue
            area = int(mask.sum())
            # The seat is deliberately shown close to the camera and can occupy
            # nearly half of a frame. Reject only an implausible near-full-frame
            # failure; the old 30% cutoff erased those useful close-up masks.
            if area < 12 or area > int(H * W * .75):
                continue
            yy, xx = np.where(mask)
            rgba[mask, :3] = colors[key]
            rgba[mask, 3] = 104
            bounds.append((key, int(xx.min()), int(yy.min()), int(xx.max()) + 1,
                           int(yy.max()) + 1, area))
        canvas = Image.fromarray(rgba, "RGBA").transpose(Image.Transpose.ROTATE_180)
        draw = ImageDraw.Draw(canvas)
        saved = []
        for key, x0, y0, x1, y1, area in bounds:
            x0, y0, x1, y1 = W - x1, H - y1, W - x0, H - y0
            color = "#" + "".join(f"{c:02x}" for c in colors[key])
            draw.rectangle((x0, y0, x1, y1), outline=color, width=2)
            label = labels[key]
            box = draw.textbbox((0, 0), label, font=font)
            tw, th = box[2] - box[0], box[3] - box[1]
            lx, ly = max(2, min(W - tw - 12, x0)), max(th + 6, y0 - 5)
            draw.rounded_rectangle((lx - 4, ly - th - 4, lx + tw + 5, ly + 4),
                                   radius=4, fill=(7, 23, 24, 236), outline=color, width=2)
            draw.text((lx, ly - th - 1), label, font=font, fill="white")
            saved.append({"id": key, "label": label, "box": [x0, y0, x1, y1],
                          "areaPixels": area})
        canvas.save(OUT / f"{frame_index:06d}.png", optimize=True)
        records[str(frame_index)] = saved

    with torch.autocast(device_type="cpu", enabled=False), torch.inference_mode():
        # Track backward only from the first prompt to the beginning. The
        # forward pass starts there and uses the later close-up correction too.
        reverse_start = min(prompt_frames)
        for frame_index, ids, logits in model.propagate_in_video(
                state, start_frame_idx=reverse_start, reverse=True):
            write_frame(frame_index, ids, logits)
        forward_start = min(prompt_frames)
        for frame_index, ids, logits in model.propagate_in_video(
                state, start_frame_idx=forward_start, reverse=False):
            write_frame(frame_index, ids, logits)

    metadata = {
        "method": "SAM2.1 Hiera Tiny video mask propagation from reviewed prompts",
        "frameCount": len(names), "sourceVideoUnmodified": True,
        "objects": [{"id": key, "label": labels[key], "objectId": object_ids[key],
                     "promptFrames": sorted(set(int(item["frame"]) for item in prompts) |
                                             ({160} if key == "seat" and len(names) > 160 else set()))}
                    for key, prompts in grouped.items()],
        "frameObjects": records,
        "warning": "Moving-object 2D masks propagated through recorded video; review for drift at occlusion or rapid motion. They are not persistent physical-room anchors."
    }
    (ROOT / "tracked-overlays.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps({"frames": len(names), "trackedObjects": list(grouped),
                      "overlayCount": len(list(OUT.glob("*.png"))), "device": device}, indent=2))


if __name__ == "__main__":
    main()
