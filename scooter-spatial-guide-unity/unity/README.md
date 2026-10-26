# Unity contribution

`patches/` contains the scooter-specific source and instruction-data changes against the Guided Reality Unity starter supplied for this project. Apply each patch from the root of a matching starter checkout:

```sh
for patch_file in /path/to/AI-AR-Project/scooter-spatial-guide-unity/unity/patches/*.patch; do
  patch -p1 < "$patch_file"
done
```

`SCOOTER_DEMO_NOTES.md` describes the demo. `guidedreality.local.json` is deliberately excluded because it contains private Gemini/SAM credentials; configure your own keys locally using the starter's example settings file.

This directory contains the Unity changes as patches; it is not a standalone Unity project. The starter code is based on Guided Reality by Ada Yi Zhao, Aditya Gunturu, Ellen Yi-Luen Do, and Ryo Suzuki. The local starter copy did not include a redistribution license; this bundle does not rehost the whole starter or grant a new license for it. Ask its authors before redistributing their base project.
