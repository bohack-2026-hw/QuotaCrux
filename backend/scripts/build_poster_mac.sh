#!/usr/bin/env bash
# Build the QuotaCrux poster on a Mac with PingFang SC for Chinese (Latin text stays Inter, from Google Fonts).
#   scripts/build_poster_mac.sh [--out ../docs/poster/QuotaCrux-poster.pdf]
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --with segno python scripts/build_poster.py --cjk "PingFang SC" "$@"
