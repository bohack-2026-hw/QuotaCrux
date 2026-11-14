#!/bin/bash
# Rebuild the deck: ./build.sh -> ../QuotaCrux.pdf (vector) and ../QuotaCrux.pptx (editable text over rendered slides)
set -e
cd "$(dirname "$0")"
ROOT=$(git rev-parse --show-toplevel)
PORT=8767
python3 -m http.server $PORT --directory "$ROOT" >/dev/null 2>&1 &
SERVER=$!
trap 'kill $SERVER' EXIT
sleep 1
node export.cjs "http://localhost:$PORT/docs/presentation/slides/index.html" ..
uv run -q --with python-pptx --with pillow python build_pptx.py ../build ../QuotaCrux.pptx
rm -rf ../build
