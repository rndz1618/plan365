#!/bin/bash
set -e
# Plan365 quick deploy from source zip
# Usage: ./deploy.sh plan365-source.zip
ZIP="${1:-plan365-source.zip}"
if [ ! -f "$ZIP" ]; then
  echo "Put plan365-source.zip next to this script (download from build artifacts)"
  exit 1
fi
unzip -o "$ZIP"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed_demo.py || true
python main.py
