#!/bin/sh
# usage: ./preview.sh -> preview/m1.jpg … (LibreOffice render with this Mac's fonts; for checking layout only)
cd "$(dirname "$0")" && mkdir -p preview
uv run -q --with python-pptx --with lxml python build.py preview/_preview.pptx >/dev/null || exit 1
rm -rf preview/pdf && mkdir -p preview
FONTCONFIG_FILE=/opt/homebrew/etc/fonts/fonts.conf soffice --headless --convert-to pdf --outdir preview/pdf preview/_preview.pptx >/dev/null 2>&1
uv run -q --with pymupdf --with pillow python - <<'PY'
import pymupdf
from PIL import Image
d = pymupdf.open("preview/pdf/_preview.pdf")
ims = []
for pg in d:
    z = 960 / pg.rect.width
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(z, z))
    ims.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
for k in range(0, len(ims), 6):
    S = Image.new("RGB", (1920, 540 * 3), "white")
    for i, im in enumerate(ims[k:k + 6]):
        S.paste(im, ((i % 2) * 960, (i // 2) * 540))
    S.save(f"preview/m{k // 6 + 1}.jpg", quality=85)
print(len(ims), "slides rendered")
PY
