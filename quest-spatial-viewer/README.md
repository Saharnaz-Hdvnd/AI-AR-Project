# Quest Spatial Viewer

Source code for the hosted, unmasked Quest spatial recording viewer.

## Watch the recordings

Open the public [project resources page](https://quest-spatial-viewer-saharnaz.snowypearl.chatgpt.site/resources.html). Choose a take, then use the viewer timeline and playback controls. The page links to the three hosted original recordings and their session data.

## Source files

- `index.html` — viewer layout, recording selector, controls, and import map.
- `src/app.js` — recording playback, session loading, and augmentation UI.
- `src/math.js` — camera and coordinate math.
- `src/twin.js` — Three.js room and trajectory viewer.

The deployed viewer also serves the Three.js runtime and the associated session manifests, image frames, audio, room geometry, and hand data. For watching the recordings, use the hosted page; no local installation is required. These files are the viewer source, not the professor's original Quest recorder project.
