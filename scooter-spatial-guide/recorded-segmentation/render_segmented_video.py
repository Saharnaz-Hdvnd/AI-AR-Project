#!/usr/bin/env python3
"""Burn transparent, per-frame segmentation overlays into an MP4 using FFmpeg."""
from __future__ import annotations
import argparse
import csv
import json
import subprocess
import tempfile
from pathlib import Path


def ffconcat_list(paths: list[Path], timestamps: list[int], tmp: Path, name: str) -> Path:
    """Build a VFR image sequence keyed to source MP4 packet timestamps."""
    if len(paths) != len(timestamps):
        raise ValueError(f"{name}: got {len(paths)} overlay frames for {len(timestamps)} video frames")
    lines = ["ffconcat version 1.0"]
    for i, image in enumerate(paths):
        lines.append(f"file '{image.as_posix()}'")
        delta = (timestamps[i + 1] - timestamps[i]) if i + 1 < len(paths) else (timestamps[i] - timestamps[i - 1])
        if delta <= 0:
            raise ValueError("Packet timestamps must be strictly increasing")
        lines.append(f"duration {delta / 1_000_000:.9f}")
    target = tmp / name
    target.write_text("\n".join(lines) + "\n")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=Path(__file__).resolve().parent,
                        help="Folder containing capture-metadata and overlay folders")
    parser.add_argument("--video", type=Path, default=None, help="Source MP4 (default: WORK_DIR/left_camera.mp4)")
    parser.add_argument("--packets", type=Path, default=None,
                        help="CSV with pts_us column (default: WORK_DIR/capture-metadata/left_camera.mp4.packets.csv)")
    parser.add_argument("--parts", type=Path, default=None,
                        help="Transparent part overlays (default: WORK_DIR/capture-part-overlays)")
    parser.add_argument("--tracking", type=Path, default=None,
                        help="Optional transparent tracking overlays (default: WORK_DIR/tracked-overlays if present)")
    parser.add_argument("--output", type=Path, default=None, help="Output MP4 path")
    parser.add_argument("--keep-orientation", action="store_true", help="Do not rotate the Quest source 180 degrees")
    args = parser.parse_args()
    root = args.work_dir.expanduser().resolve()
    video = (args.video or root / "left_camera.mp4").expanduser().resolve()
    packets_csv = (args.packets or root / "capture-metadata/left_camera.mp4.packets.csv").expanduser().resolve()
    parts_dir = (args.parts or root / "capture-part-overlays").expanduser().resolve()
    tracking_dir = (args.tracking or root / "tracked-overlays").expanduser().resolve()
    output = (args.output or root / "QuestSpatialSegmentation.mp4").expanduser().resolve()
    rows = list(csv.DictReader(packets_csv.open(newline="")))
    timestamps = [int(row["pts_us"]) for row in rows]
    part_frames = sorted(parts_dir.glob("*.png"))
    expected = [f"{i:06d}.png" for i in range(len(timestamps))]
    if [p.name for p in part_frames] != expected:
        raise RuntimeError("Part overlays must be named 000000.png, ... and cover every video frame")
    tracking_frames = sorted(tracking_dir.glob("*.png")) if tracking_dir.is_dir() else []
    if tracking_frames and [p.name for p in tracking_frames] != expected:
        raise RuntimeError("Tracking overlays must be named 000000.png, ... and cover every video frame")

    with tempfile.TemporaryDirectory(prefix="quest-spatial-mp4-") as temp:
        tmp = Path(temp)
        parts = ffconcat_list(part_frames, timestamps, tmp, "parts.ffconcat")
        graph = "[0:v]setpts=PTS-STARTPTS[base];"
        if not args.keep_orientation:
            graph = "[0:v]hflip,vflip,setpts=PTS-STARTPTS[base];"
        graph += "[1:v]format=rgba[parts];[base][parts]overlay=eof_action=repeat:format=auto[outv]"
        command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning", "-i", str(video),
                   "-f", "concat", "-safe", "0", "-i", str(parts)]
        if tracking_frames:
            tracking = ffconcat_list(tracking_frames, timestamps, tmp, "tracking.ffconcat")
            graph = graph.replace("[outv]", "[withparts];[2:v]format=rgba[tracking];[withparts][tracking]overlay=eof_action=repeat:format=auto[outv]")
            command += ["-f", "concat", "-safe", "0", "-i", str(tracking)]
        command += ["-filter_complex", graph, "-map", "[outv]", "-an", "-c:v", "libx264",
                    "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-fps_mode", "vfr",
                    "-movflags", "+faststart", str(output)]
        subprocess.run(command, check=True)
    print(json.dumps({"output": str(output), "frames": len(timestamps), "rotation180": not args.keep_orientation,
                      "trackingOverlayFrames": len(tracking_frames), "audio": "not included"}, indent=2))


if __name__ == "__main__":
    main()
