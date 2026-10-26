# Scooter Spatial Guide demo

This working copy changes Guided Reality's starter flow to a scooter-oriented spatial guidance demo. The instruction list is in `Assets/Resources/ScooterRepair.json`. Press right B to load it, use the right stick left/right to change steps, and press right A to recapture the current target.

Each step asks the app to locate and segment a named target in a newly captured camera frame. A nearby label shows the part/tool name and the Find, Align, Work, or Recover phase. The overlay is placed at the captured pose; it does **not** track an object after it moves, recognize repair completion, or validate a fastener or torque. Recapture after moving or reframing.

This is a demo scaffold, not a validated scooter repair procedure. Use the scooter maker's service instructions for the correct tool, sequence, and torque specification. The current example references a clamp bolt and wrench because those were part of the provided scooter demo context; verify the actual target and procedure against your scooter before following it.

The app still depends on the existing Gemini locator and separate SAM-2 segmentation service, configured locally as described in `README.md`. Keep service credentials private.


## Head-directed scan and 3D mask

After loading the steps with right B, press right B again to start/pause scanning. The center of the headset camera view acts as a head-direction selector. Each cycle requests one fresh image from Gemini for a centered scooter part/tool label, then sends that still image to SAM-2 for a segmentation. The mask alpha is sampled against Quest environment-depth hits, connected into a coarse surface mesh, and parented under an `OVRSpatialAnchor`.

This is repeated still-image re-detection, not a continuous video/SAM tracking session. The app's current SAM endpoint only exposes `POST /segment`; accurate temporal instance tracking needs a stateful video endpoint or an on-device tracker, and network round trips limit refresh speed. After SAM returns a crop, the app adds a target-local 48-by-variable-resolution depth ray pass before meshing. This is denser than the room-wide grid, but still uses Quest environment raycasts rather than native per-pixel depth, so tiny screws or occluded parts may remain too sparse.

The app identifies a visible target and reminds you to consult the service manual. It does not infer that a repair is complete. A camera cannot measure applied torque; torque verification requires a calibrated torque tool/sensor and the scooter manufacturer's specification.
