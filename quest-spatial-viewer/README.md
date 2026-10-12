# Quest recordings: viewer, JavaScript, and MP4s

This project has a public interactive viewer, JavaScript source, and five original, unmasked MP4 recordings.

## Start here

- **Interactive viewer and session data:** [Open the project resources page](https://quest-spatial-viewer-saharnaz.snowypearl.chatgpt.site/resources). Use the two spatial takes listed there: October 9 at 18:37 and October 11 at 15:30.
- **All five downloadable MP4 videos:** [Open the public GitHub Release](https://github.com/Saharnaz-Hdvnd/AI-AR-Project/releases/tag/quest-spatial-originals-2026-10-11). Select a filename under Assets to download it. The videos are unmasked originals.

## Five MP4 recordings

- October 9 · 18:37 — `QuestSpatialTake-20261009_183717-original.mp4`
- October 11 · 15:30 — `QuestSpatialTake-20261011_153014-original.mp4`
- October 11 · 17:51 — `QuestSpatialTake-20261011_175129-original.mp4`
- October 11 · 18:12 — `QuestSpatialTake-20261011_181252-original.mp4`
- October 11 · 18:21 — `QuestSpatialTake-20261011_182103-original.mp4`

The October 9 and October 11 15:30 takes also have spatial session data for the interactive viewer. The three later MP4s are plain video recordings.

## JavaScript viewer code

- [Browse the viewer source folder](https://github.com/Saharnaz-Hdvnd/AI-AR-Project/tree/main/quest-spatial-viewer)
- [Download the full project as a ZIP](https://github.com/Saharnaz-Hdvnd/AI-AR-Project/archive/refs/heads/main.zip)

The `quest-spatial-viewer` folder contains:

- `index.html` — viewer layout, recording selector, controls, and module import map.
- `src/app.js` — recording playback, session loading, and augmentation controls.
- `src/math.js` — camera and coordinate math.
- `src/twin.js` — Three.js room and trajectory view.
- `README.md` — this guide.

To use the spatial recordings, open the hosted resources page; it already serves the required session data and Three.js runtime. The source ZIP is for downloading and inspecting the JavaScript and project files. It does not bundle the five MP4 assets or the hosted spatial-session dataset.

No masked scooter video is included.
