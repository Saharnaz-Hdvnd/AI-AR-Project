"""Small local HTTP adapter from the Guided Reality client to Meta SAM 2."""

from __future__ import annotations

import base64
import hmac
import io
import os
import threading
from pathlib import Path
from typing import Literal

import numpy as np
import torch
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from PIL import Image
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


ROOT = Path(os.environ.get("SAM2_ROOT", "./sam2")).expanduser().resolve()
CHECKPOINT = Path(
    os.environ.get("SAM2_CHECKPOINT", str(ROOT / "checkpoints/sam2.1_hiera_tiny.pt"))
).expanduser().resolve()
MODEL_CONFIG = os.environ.get("SAM2_MODEL_CFG", "configs/sam2.1/sam2.1_hiera_t.yaml")
TOKEN = os.environ.get("SAM_TOKEN", "")
MAX_IMAGE_BYTES = 12 * 1024 * 1024

if not TOKEN:
    raise RuntimeError("Set SAM_TOKEN to a long random local bearer token before starting the service.")
if not CHECKPOINT.is_file():
    raise RuntimeError(f"SAM 2 checkpoint not found: {CHECKPOINT}")

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
MODEL = build_sam2(MODEL_CONFIG, str(CHECKPOINT), device=DEVICE)
PREDICTOR = SAM2ImagePredictor(MODEL)
PREDICTOR_LOCK = threading.Lock()
app = FastAPI(title="Local SAM 2 adapter", docs_url=None, redoc_url=None)


class SegmentRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    visual_type: Literal[2] = 2
    image_base64: str
    # [y_min, x_min, y_max, x_max], normalized to 0..1000, origin top-left.
    box_2d: list[float] = Field(min_length=4, max_length=4)


def authorize(authorization: str | None) -> None:
    expected = f"Bearer {TOKEN}"
    if authorization is None or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


@app.get("/health")
def health(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return {"ok": True, "model": "SAM 2.1 Hiera Tiny", "device": DEVICE}


@app.post("/segment")
def segment(body: SegmentRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    try:
        raw = base64.b64decode(body.image_base64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="image_base64 is invalid") from exc
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 12 MiB limit")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            rgb = np.array(source.convert("RGB"), copy=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not decode image") from exc

    height, width = rgb.shape[:2]
    y0, x0, y1, x1 = body.box_2d
    if not all(np.isfinite(v) and 0 <= v <= 1000 for v in body.box_2d):
        raise HTTPException(status_code=400, detail="box_2d values must be finite and within 0..1000")
    left = int(round(x0 * width / 1000))
    top = int(round(y0 * height / 1000))
    right = int(round(x1 * width / 1000))
    bottom = int(round(y1 * height / 1000))
    if left >= right or top >= bottom:
        raise HTTPException(status_code=400, detail="box_2d has zero or reversed area")

    # The client currently sends one still frame per request, so each call is
    # an independent prompted mask. It is not stateful SAM 2 video tracking.
    try:
        # Predictor keeps the current image in mutable state; serialize requests
        # so concurrent clients cannot swap images between set_image/predict.
        with PREDICTOR_LOCK:
            PREDICTOR.set_image(rgb)
            with torch.inference_mode():
                masks, scores, _ = PREDICTOR.predict(
                    point_coords=np.array([[(left + right) * 0.5, (top + bottom) * 0.5]], dtype=np.float32),
                    point_labels=np.array([1], dtype=np.int32),
                    box=np.array([left, top, right, bottom], dtype=np.float32),
                    multimask_output=True,
                )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SAM 2 inference failed: {exc}") from exc

    # Prefer a high-scoring candidate that contains the prompt point and stays
    # local. Reject whole-assembly masks rather than painting them as a part.
    flat_scores = np.asarray(scores).reshape(-1)
    flat_masks = np.asarray(masks).reshape((-1, height, width)).astype(bool)
    center_x, center_y = (left + right) // 2, (top + bottom) // 2
    candidates = []
    for index, candidate in enumerate(flat_masks):
        area = int(candidate.sum())
        if area and candidate[center_y, center_x] and area <= int(height * width * 0.18):
            candidates.append((float(flat_scores[index]), index))
    if not candidates:
        raise HTTPException(
            status_code=422,
            detail="SAM 2 could not isolate a small mask at the target center. Aim closer at one part and retry.",
        )
    _, best = max(candidates)
    mask = flat_masks[best]
    yy, xx = np.where(mask)
    if len(xx) == 0:
        raise HTTPException(status_code=422, detail="SAM 2 returned an empty mask")
    crop_left, crop_top = int(xx.min()), int(yy.min())
    crop_right, crop_bottom = int(xx.max()) + 1, int(yy.max()) + 1
    rgba = np.zeros((crop_bottom - crop_top, crop_right - crop_left, 4), dtype=np.uint8)
    rgba[:, :, :3] = rgb[crop_top:crop_bottom, crop_left:crop_right]
    rgba[:, :, 3] = mask[crop_top:crop_bottom, crop_left:crop_right].astype(np.uint8) * 255
    output = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(output, format="PNG", optimize=True)

    return {
        "request_id": body.request_id,
        "image_width": width,
        "image_height": height,
        "crop_rect": [crop_left, crop_top, crop_right - crop_left, crop_bottom - crop_top],
        "png_base64": base64.b64encode(output.getvalue()).decode("ascii"),
        "score": float(flat_scores[best]),
    }
