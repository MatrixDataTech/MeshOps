#!/usr/bin/env bash

set -e

source .venv/bin/activate

python -m uvicorn \
    meshops.main:app \
    --reload \
    --host 0.0.0.0 \
    --port 8000
