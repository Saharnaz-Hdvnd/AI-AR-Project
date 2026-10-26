# Local SAM 2 adapter

This adapter is the student-side HTTP bridge between the Unity client and Meta SAM 2.1 Hiera Tiny. It contains no model implementation or weights; install them from the official [facebookresearch/sam2](https://github.com/facebookresearch/sam2) repository.

## Setup on macOS

Use Python 3.10–3.12 with a PyTorch/torchvision build supported by your Mac. Then run:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
git clone https://github.com/facebookresearch/sam2.git sam2-src
python -m pip install -e ./sam2-src
mkdir -p sam2-src/checkpoints
curl -L https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt -o sam2-src/checkpoints/sam2.1_hiera_tiny.pt
cp .env.example .env
# Replace the placeholder SAM_TOKEN in .env with a long random value.
./start.sh
```

The service defaults to `127.0.0.1:8765`, which is suitable for the USB development tunnel. With the Quest connected over USB, run `adb reverse tcp:8765 tcp:8765`. Configure Unity to use `http://127.0.0.1:8765` and the same local token. `start.sh` creates `.env` if missing; keep `.env` private.

The service uses one image and a prompted bounding box per request. It is not temporal SAM 2 video tracking, and the Unity client repeats still-image requests. It is a prototype, not repair or torque verification.
