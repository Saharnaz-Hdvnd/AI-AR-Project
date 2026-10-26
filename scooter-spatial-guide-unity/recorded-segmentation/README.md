# Quest spatial video segmentation pipeline

Python tools used to make the `Quest Scooter Spatial Segmentation` prototype. This folder contains code only; it does not include a capture, video, mask images, point clouds, SAM weights, or API keys.

## What is reusable

- `process_capture.py` runs prompted SAM 2.1 masks on reviewed frames, associates masks with the Quest registered depth, and lifts visible depth pixels into colored 3D PLY point samples using camera intrinsics and recorded poses.
- `track_video_masks.py` propagates selected reviewed masks through video with SAM 2.1 Video Predictor and produces frame overlays.
- `project_capture_masks.py` reprojects reviewed 3D point samples into recorded camera views to create per-frame transparent overlays.
- `render_segmented_video.py` composites per-frame overlays onto an upright MP4. The saved result is a normal MP4 with masks and labels burned into its pixels.
- `index.html` and `viewer.js` are the source for the interactive video + 3D point-cloud viewer. They expect the per-capture JSON, masks, PLY files, and video alongside them; those capture assets are not included here. Install the Three.js ES modules (`three.module.js`, `OrbitControls.js`, and `PLYLoader.js`) under `vendor/` from an official Three.js distribution.
- `build_capture_map.py` builds a sparse background point cloud and a camera path from a Quest take.
- `add_scooter_components.py` is a scooter-specific example for adding the rear shock and seatpost clamp.

## Requirements and data

Use Python 3.10 or 3.11, FFmpeg, NumPy, Pillow, and PyTorch. Install SAM 2.1 from Meta's official `facebookresearch/sam2` repository and obtain its `sam2.1_hiera_tiny.pt` checkpoint according to that repository's instructions. These scripts do not download model weights. On Apple Silicon, PyTorch MPS is used when available; CPU is the fallback.

The 3D workflow requires an OpenClaw/Quest capture with the RGB video, packet timestamps, camera intrinsics, per-frame camera poses, and registered depth. A plain MP4 by itself has no depth or camera poses, so it can support 2D SAM masks and an overlaid MP4, but cannot produce spatially positioned 3D observations.

## Adapting it to another take

1. Copy a Quest capture's required source files into a working folder. Keep the capture MP4, metadata, and registered-depth files together using the folder structure expected by the scripts.
2. In `process_capture.py`, review and edit `frame_ids` and the `entries` list for the new video. Each entry needs the frame index, object id and label, a bounding box, positive/negative SAM prompt points, candidate mask index, and display color. These coordinates are specific to the example scooter video.
3. Run the registered-depth derivation for that capture before the 3D lifting step. Point the commands to the SAM 2 source and checkpoint on your computer; never commit those model weights.
4. Review the generated masks and PLYs. Adjust prompts and active frame ranges in `project_capture_masks.py`; do not assume that masks follow a moving object automatically. The included video tracking example propagates the scooter seat only.
5. Generate overlays and render them with FFmpeg. Update the video rotation setting if the Quest export orientation differs. The renderer accepts `--work-dir`, `--video`, `--packets`, `--parts`, `--tracking`, and `--output`; use `--keep-orientation` if that source MP4 is already upright.
6. To open the 3D viewer for another take, put `index.html`, `viewer.js`, the required Three.js modules, and that take's generated video, annotations, camera poses, intrinsics, per-frame overlays, point clouds, and depth-map PLY in the same expected relative layout. Serve the folder over HTTP; browsers may block local module/data loading from `file://`.

The viewer source is a starter for the same generated asset schema; its 1280×1280 overlay projection and Quest coordinate conventions may need adjustment for other capture formats. The current scripts use the capture-local layout from the scooter prototype (`left_camera.mp4`, `capture-metadata/`, `registered/registered-depth/`, and overlay folders). They are a research prototype and need per-recording prompt and path edits; this is not a one-click detector for arbitrary objects.

## Limitations

3D points are lifted from the Quest depth measurements and stay in the recording's tracking coordinate frame. Without a valid room scan and a cross-session alignment transform, they are not persistent physical-room anchors. Depth is sparse and low resolution, and only visible surfaces can be reconstructed. SAM masks and 3D projections require human review; this code does not verify screw torque or repair completion.

## Attribution

The capture data format is from Ryo Suzuki's OpenClaw/Quest spatial capture project. This folder contains the project-specific post-processing scripts, not a copy of the upstream recorder or SAM 2 implementation. Check the upstream projects' licenses before redistributing their code or data.
