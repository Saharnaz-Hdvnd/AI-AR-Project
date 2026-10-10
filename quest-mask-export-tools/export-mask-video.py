#!/usr/bin/env python3
"""Export a replay session as H.264 MP4 with tracked object masks and audio."""
import argparse
import bisect
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np


def color_for(track_id):
    hue = (int(track_id) * 67) % 180
    return tuple(int(x) for x in cv2.cvtColor(np.uint8([[[hue, 220, 255]]]), cv2.COLOR_HSV2BGR)[0, 0])


def draw_masks(frame, objects):
    if not objects:
        return frame
    overlay = frame.copy()
    for obj in objects:
        points = np.asarray(obj.get("points", []), dtype=np.int32)
        if points.ndim != 2 or len(points) < 3:
            continue
        color = color_for(obj.get("id", 0))
        cv2.fillPoly(overlay, [points], color, lineType=cv2.LINE_AA)
    frame = cv2.addWeighted(overlay, .20, frame, .80, 0)
    for obj in objects:
        points = np.asarray(obj.get("points", []), dtype=np.int32)
        if points.ndim != 2 or len(points) < 3:
            continue
        color = color_for(obj.get("id", 0))
        cv2.polylines(frame, [points], True, color, 4, lineType=cv2.LINE_AA)
        x, y = points.min(axis=0)
        label = f"{obj.get('label', 'object')} · {obj.get('id', '?')}"
        (w, h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .62, 2)
        x = max(4, min(int(x), frame.shape[1] - w - 14))
        y = max(h + 10, int(y) - 7)
        cv2.rectangle(frame, (x, y - h - 9), (x + w + 14, y + baseline - 5), color, -1)
        cv2.putText(frame, label, (x + 7, y - 3), cv2.FONT_HERSHEY_SIMPLEX, .62, (255, 255, 255), 2, cv2.LINE_AA)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, help="Session folder containing session.json and object-tracks.json")
    parser.add_argument("output", type=Path, help="Destination MP4 file")
    parser.add_argument("--fps", type=int, default=10)
    args = parser.parse_args()

    session_dir = args.session.expanduser().resolve()
    session = json.loads((session_dir / "session.json").read_text())
    tracks = json.loads((session_dir / "object-tracks.json").read_text())
    if tracks.get("session") != session.get("name"):
        raise SystemExit("Object-track file belongs to a different session.")
    if len(tracks.get("imageSize", [])) != 2:
        raise SystemExit("Object-track file has no valid image dimensions.")

    width, height = tracks["imageSize"]
    times = [float(frame["t"]) for frame in session["frames"]]
    audio = session.get("audio")
    audio_path = session_dir / audio["file"] if audio else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "bgr24", "-video_size", f"{width}x{height}",
        "-framerate", str(args.fps), "-i", "-",
    ]
    if audio_path and audio_path.exists():
        cmd += ["-itsoffset", str(float(audio.get("startRelativeToVideoSeconds", 0))), "-i", str(audio_path)]
    cmd += ["-map", "0:v:0"]
    if audio_path and audio_path.exists():
        cmd += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += ["-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(args.output)]

    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames_out = int(np.ceil(float(session["duration"]) * args.fps))
    counts = tracks.get("frames", {})
    try:
        for out_index in range(frames_out):
            t = out_index / args.fps
            source_index = bisect.bisect_right(times, t) - 1
            source_index = max(0, min(source_index, len(times) - 1))
            source = cv2.imread(str(session_dir / session["frames"][source_index]["image"]), cv2.IMREAD_COLOR)
            if source is None:
                raise RuntimeError(f"Could not read source frame {source_index}")
            objects = counts.get(str(source_index), [])
            process.stdin.write(draw_masks(source, objects).tobytes())
            if out_index % (args.fps * 10) == 0 or out_index == frames_out - 1:
                print(f"Rendered {out_index + 1}/{frames_out} frames", flush=True)
        process.stdin.close()
        status = process.wait()
        if status:
            raise SystemExit(f"ffmpeg exited with status {status}")
    except Exception:
        if process.poll() is None:
            process.kill()
        raise
    total_masks = sum(len(v) for v in counts.values())
    print(f"Saved {args.output} ({frames_out} frames at {args.fps} fps; {total_masks} source masks)")


if __name__ == "__main__":
    main()
