#!/bin/sh
# ./build.sh -> ../QuotaCrux.pptx and ../QuotaCrux.pdf (the PDF is LibreOffice's render of the same file)
cd "$(dirname "$0")" && mkdir -p preview
uv run -q --with python-pptx --with lxml --with pillow python build.py ../QuotaCrux.pptx || exit 1
FONTCONFIG_FILE=/opt/homebrew/etc/fonts/fonts.conf soffice --headless --convert-to pdf --outdir .. ../QuotaCrux.pptx >/dev/null 2>&1
ls -la ../QuotaCrux.pptx ../QuotaCrux.pdf
