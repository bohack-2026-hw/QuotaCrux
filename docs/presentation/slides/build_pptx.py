"""Assemble the PPTX from export.cjs output: each slide is its rendered background plus editable text boxes.

    uv run --with python-pptx --with pillow python build_pptx.py <build-dir> <out.pptx>
"""

import json
import re
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

PX = 6350  # EMU per CSS px on a 1920-px-wide 16:9 slide
BG = (12, 13, 15)
ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT, "justify": PP_ALIGN.LEFT}


def color(css: str) -> RGBColor:
    v = [float(x) for x in re.findall(r"[\d.]+", css)]
    r, g, b, a = (v + [1.0])[:4]
    # text never sits on transparent ground here, so fold alpha into the dark slide background
    mix = lambda c, k: round(c * a + k * (1 - a))  # noqa: E731
    return RGBColor(mix(r, BG[0]), mix(g, BG[1]), mix(b, BG[2]))


def latin_font(family: str) -> str:
    f = family.lower()
    if "avenir" in f:
        return "Avenir Next"
    if "menlo" in f or "mono" in f:
        return "Menlo"
    return "PingFang SC"


def style_run(run, r: dict) -> None:
    font = run.font
    font.size = Pt(r["size"] * 0.5)
    font.bold = r["weight"] >= 600
    font.color.rgb = color(r["color"])
    font.name = latin_font(r["family"])
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {})
            rpr.append(el)
        el.set("typeface", "PingFang SC")
    if r.get("ls"):
        rpr.set("spc", str(round(r["ls"] * 0.5 * 100)))


def add_block(slide, b: dict) -> None:
    single = b["h"] < b["lh"] * 1.6 and not b["pre"]
    slack = 1.0 if single else 1.04
    w = b["w"] * slack + (6 if single else 0)
    x = b["x"] - (w - b["w"]) / 2 if b["align"] == "center" else b["x"] - (w - b["w"]) if b["align"] == "right" else b["x"]
    tb = slide.shapes.add_textbox(Emu(round(x * PX)), Emu(round(b["y"] * PX)), Emu(round(w * PX)), Emu(round(max(b["h"], b["lh"]) * PX)))
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.word_wrap = not single
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE if b["valign"] == "middle" else MSO_ANCHOR.TOP
    # split runs into paragraphs on newlines
    paras, cur = [], []
    for r in b["runs"]:
        parts = r["text"].split("\n")
        for k, part in enumerate(parts):
            if k:
                paras.append(cur)
                cur = []
            if part:
                cur.append({**r, "text": part})
    paras.append(cur)
    for k, runs in enumerate(paras):
        para = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        para.alignment = ALIGN.get(b["align"], PP_ALIGN.LEFT)
        para.line_spacing = Pt(b["lh"] * 0.5)
        para.space_before = para.space_after = Pt(0)
        for r in runs:
            run = para.add_run()
            run.text = r["text"]
            style_run(run, r)


def main(build: Path, out: Path) -> None:
    deck = json.loads((build / "deck.json").read_text())
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(1920 * PX), Emu(1080 * PX)
    blank = prs.slide_layouts[6]
    for s in deck:
        slide = prs.slides.add_slide(blank)
        jpg = build / s["bg"].replace(".png", ".jpg")
        Image.open(build / s["bg"]).convert("RGB").save(jpg, quality=90, optimize=True)
        slide.shapes.add_picture(str(jpg), 0, 0, prs.slide_width, prs.slide_height)
        for b in s["blocks"]:
            add_block(slide, b)
        if s["notes"]:
            slide.notes_slide.notes_text_frame.text = s["notes"]
    prs.core_properties.title = "QuotaCrux 枢决 · 技术演示"
    prs.save(out)
    print(f"{len(deck)} slides, {sum(len(s['blocks']) for s in deck)} text boxes -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
