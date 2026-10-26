# Scooter Spatial Guide — project source

This folder shares the code needed to inspect the student-built scooter demo:

- [`unity/`](unity/): patch for the scooter-specific Unity changes and demo notes. Apply it to the Guided Reality starter supplied for this project.
- [`sam-service/`](sam-service/): the local authenticated HTTP adapter that calls upstream Meta SAM 2.1 Hiera Tiny. The SAM 2 model implementation and checkpoint are installed separately and are not bundled.
- [Quest spatial viewer JavaScript source](../quest-spatial-viewer/) is already in this repository.

The Unity starter originated with Guided Reality by Ada Yi Zhao, Aditya Gunturu, Ellen Yi-Luen Do, and Ryo Suzuki. This bundle identifies the student changes and does not claim authorship of the starter. Obtain permission from the starter authors before redistributing their full project. SAM 2 is a separate upstream project under its own license.

This is a public repository. It contains source and documentation, not Gemini keys, SAM tokens, model weights, APKs, personal recordings, or Quest capture logs. To run the app, supply your own API credentials locally and follow the setup instructions in the subfolders. The app currently detects and segments one centered part per still-image request; it does not provide frame-rate object tracking, torque measurement, or repair verification.
