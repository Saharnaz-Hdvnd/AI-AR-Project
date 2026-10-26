#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Create the venv and install requirements first; see README.md."
  exit 1
fi
if [ ! -d sam2-src ]; then
  echo "Clone and install the official Meta SAM 2 repository first; see README.md."
  exit 1
fi
if [ ! -f sam2-src/checkpoints/sam2.1_hiera_tiny.pt ]; then
  echo "SAM 2.1 Tiny checkpoint is missing; see README.md to download it."
  exit 1
fi

source .venv/bin/activate
if [ ! -f .env ]; then
  printf 'SAM_TOKEN=%s\n' "$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" > .env
  chmod 600 .env
  echo "Created a private token in this folder's ignored .env file."
fi
set -a
source .env
set +a
export SAM2_ROOT="$PWD/sam2-src"
export SAM2_CHECKPOINT="$PWD/sam2-src/checkpoints/sam2.1_hiera_tiny.pt"
export SAM2_MODEL_CFG="configs/sam2.1/sam2.1_hiera_t.yaml"
echo "SAM bearer token is stored in this folder's ignored .env file; enter it privately in Unity."
SAM_HOST="${SAM_HOST:-127.0.0.1}"
echo "Service listening at http://${SAM_HOST}:8765 (local network; bearer-token protected)"
exec uvicorn app:app --host "$SAM_HOST" --port 8765
