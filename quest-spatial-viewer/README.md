# Quest Spatial Viewer

Source code for the hosted, unmasked Quest spatial recording viewer.

## Watch the recordings

Open the public [project resources page](https://quest-spatial-viewer-saharnaz.snowypearl.chatgpt.site/resources.html). It links to three interactive spatial takes and provides browser playback and downloads for these original MP4 files:

- `QuestSpatialTake-20261011_175129-original.mp4`
- `QuestSpatialTake-20261011_181252-original.mp4`
- `QuestSpatialTake-20261011_182103-original.mp4`

The three MP4s are plain original recordings. The interactive viewer currently loads the three spatial takes listed on the resources page; their session manifests and associated room and hand data are hosted alongside the viewer.

## Source files

- `index.html` — viewer layout, recording selector, controls, and import map.
- `src/app.js` — recording playback, session loading, and augmentation UI.
- `src/math.js` — camera and coordinate math.
- `src/twin.js` — Three.js room and trajectory viewer.

The deployed viewer also serves the Three.js runtime. For watching, use the hosted resources page; no local installation is required. These files are the viewer source, not the professor's original Quest recorder project.
