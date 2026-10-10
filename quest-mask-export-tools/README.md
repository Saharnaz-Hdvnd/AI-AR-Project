# Quest Spatial Mask Video Exporter

A small local helper that renders an existing Quest Spatial Studio replay as an H.264 MP4, drawing the object masks and labels stored in that replay's `object-tracks.json`. If the session contains audio, the exporter includes it in the MP4.

This folder contains only the standalone export helper. It does not include the professor's Quest Spatial Studio app, a recording, tracking data, model weights, or a generated MP4.

## Requirements

- Python 3.10 or newer
- Python packages in `requirements.txt`
- `ffmpeg` available on your PATH
- A replay folder containing `session.json`, its referenced frame/audio files, and `object-tracks.json`

Install Python packages:

```sh
python3 -m pip install -r requirements.txt
```

Export a replay:

```sh
python3 export-mask-video.py /path/to/session-folder /path/to/output.mp4
```

The default output frame rate is 10 fps. Change it with `--fps`, for example `--fps 15`.

`object-tracks.json` must use the schema produced by the companion object segmentation/tracking pass: it includes the matching session name, image dimensions, and per-frame polygon points with labels and IDs. The exporter checks that the track file belongs to the selected session.

## Scope and limitations

The MP4 is a 2D video with colored mask overlays and labels. The displayed IDs are short-term image-space tracking IDs; this does not recover a persistent real-world identity or metric 3D object position. Detection quality depends on the segmentation output supplied in `object-tracks.json`.
