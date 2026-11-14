"""Build the 80 x 180 cm QuotaCrux (枢决) poster (PDF). Everything on it is typeset here: type, numbers and charts.

    uv run --with segno python scripts/build_poster.py [--out ../docs/poster/QuotaCrux-poster.pdf]

Data: the QuotaCrux research report v1.1 (PR #19, docs/research/analysis-report-20261114, generated/analysis.json,
deep-analysis.json, mac-analysis.json and sections 04-07). Values are copied below with their source so the poster
can be rebuilt before that branch is merged.
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
from pathlib import Path

import segno

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/bohack-2026-hw/QuotaCrux"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

# Latin text and numbers in Inter; Chinese in Noto Sans SC (any machine) or PingFang SC (Mac, --cjk "PingFang SC")
LATIN, CJK = "Inter", "Noto Sans SC"

BG, INK, GREY, LINE, ACCENT = "#F3F2EE", "#111113", "#8E8D88", "#D8D6CF", "#FF4D1F"

# ahc026 box moving, sum over the 15 final cases (deep-analysis.json ahc026_movement_energy)
ENERGY_C0, ENERGY_BEST = 18136, 10028
# action-decisions run run-20261114T085616-894b: (validation end s, dev score, label) — section 05 table
CASE = [(12.851, 44120, "c1"), (22.792, 44120, "c2"), (94.286, 46506, "c3"), (178.438, 46798, "c4"),
        (244.796, 46725, "c5"), (311.463, 46800, "c6"), (357.026, 46849, "c7")]
# routing short batch on ahc026: (name, final gain %, total s) — section 04 table
ROUTING = [("规则调度", 5.970, 392.039), ("决策模型选动作", 6.149, 389.380), ("决策模型选模型", 5.836, 389.913),
           ("全部交给决策模型", 0.513, 112.910)]
# Mac AlgoTune exploration, best candidate per task (section 07 table, ms over the two dev cases)
ALGO = [("PageRank", 25.041935, 11.147868, 0.445168, "稀疏矩阵直接迭代"), ("一维卷积", 2.669288, 1.117265, 0.418563, "float32 实数 FFT")]
# ledger, from docs/project-description.md: S task stream with vs without memory (12 tasks x 3 replays):
# model cost $0.402 -> $0.086, pass 36/36; sealed D batch: median final speedup 1.20x -> 1.73x
COST_BEFORE, COST_AFTER = 0.402, 0.086
SPEEDUP_BEFORE, SPEEDUP_AFTER = 1.20, 1.73


def qr_svg() -> str:
    buf = io.BytesIO()
    segno.make(REPO, error="m").save(buf, kind="svg", scale=1, border=0, dark=INK, light=None, xmldecl=False, svgns=True, omitsize=True)
    return buf.getvalue().decode()


def energy_bars() -> str:
    w, h = 700, 74
    full = 600
    best = full * ENERGY_BEST / ENERGY_C0
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}mm" height="{h}mm">'
            f'<rect x="0" y="4" width="{full}" height="26" fill="{LINE}"/>'
            f'<text x="{full + 10}" y="25" class="bv" fill="{GREY}">{ENERGY_C0:,}</text>'
            f'<text x="8" y="23" class="bl" fill="{INK}">初始程序</text>'
            f'<rect x="0" y="42" width="{best:.1f}" height="26" fill="{ACCENT}"/>'
            f'<text x="{best + 10:.1f}" y="63" class="bv" fill="{INK}">{ENERGY_BEST:,}</text>'
            f'<text x="8" y="61" class="bl" fill="#fff">QuotaCrux</text></svg>')


def case_chart() -> str:
    """Kept-best step line over the seven candidates of one research run, with each candidate's own score."""
    w, h = 700, 260
    left, right, top, bottom = 58, 20, 18, 34
    lo, hi = 43700, 47100
    x = lambda t: left + t / 360 * (w - left - right)  # noqa: E731
    y = lambda v: top + (1 - (v - lo) / (hi - lo)) * (h - top - bottom)  # noqa: E731
    best, pts = CASE[0][1], []
    for t, v, _ in CASE:
        best = max(best, v)
        pts.append((t, best))
    step = f"M{x(0)},{y(44120)} L{x(CASE[0][0])},{y(44120)}"
    for (t, b), (t2, _) in zip(pts, pts[1:] + [(360, 0)]):
        step += f" L{x(t)},{y(b)} L{x(t2)},{y(b)}"
    grid = "".join(f'<line x1="{left}" x2="{w - right}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{LINE}" stroke-width="0.8"/>'
                   f'<text x="{left - 8}" y="{y(v) + 4:.1f}" class="ax" text-anchor="end">{v:,}</text>' for v in (44000, 45000, 46000, 47000))
    xs = "".join(f'<text x="{x(t):.1f}" y="{h - 8}" class="ax" text-anchor="middle">{t}s</text>' for t in (0, 60, 120, 180, 240, 300, 360))
    up = x((22.792 + 94.286) / 2)
    marks = (f'<line x1="{up:.1f}" x2="{up:.1f}" y1="{top}" y2="{y(44120) - 14:.1f}" stroke="{INK}" stroke-width="1.2" stroke-dasharray="5 5"/>'
             f'<text x="{up + 8:.1f}" y="{top + 16}" class="an">换用大模型</text>')
    dots = ""
    for t, v, c in CASE:
        kept = v >= max(s for tt, s, _ in CASE if tt <= t)
        fill = ACCENT if kept and c not in ("c1", "c2") else "#fff"
        stroke = INK if c in ("c1", "c2", "c5") else ACCENT
        dots += f'<circle cx="{x(t):.1f}" cy="{y(v):.1f}" r="7" fill="{fill}" stroke="{stroke}" stroke-width="2.4"/>'
    notes = [(CASE[0][0], 44120, "小模型两次交了同一份代码", "start", -6, 26),
             (CASE[2][0], 46506, "分段规划 +2,386", "start", 12, 30),
             (CASE[4][0], 46725, "这一版退步，没被采纳", "middle", 0, 34),
             (CASE[6][0], 46849, "复用相同后缀 · 最高 46,849", "end", -4, -20)]
    ann = "".join(f'<text x="{x(t) + dx:.1f}" y="{y(v) + dy:.1f}" class="an" text-anchor="{a}">{s}</text>' for t, v, s, a, dx, dy in notes)
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}mm" height="{h}mm">{grid}{xs}{marks}'
            f'<path d="{step}" fill="none" stroke="{ACCENT}" stroke-width="4" stroke-linejoin="round"/>{dots}{ann}</svg>')


def routing_chart() -> str:
    """Final score gain per routing combination as bars, with the round's wall time at the end of each row."""
    w, row = 700, 46
    h = row * len(ROUTING) + 6
    lab, bar0, barw = 0, 230, 330
    out = []
    best = max(g for _, g, _ in ROUTING)
    for i, (name, g, t) in enumerate(ROUTING):
        y = 6 + i * row
        hot = g == best or t == min(tt for _, _, tt in ROUTING)
        out.append(f'<text x="{lab}" y="{y + 25}" class="rl">{name}</text>'
                   f'<rect x="{bar0}" y="{y + 6}" width="{barw * g / 7:.1f}" height="26" fill="{ACCENT if g == best else INK}"/>'
                   f'<text x="{bar0 + barw * g / 7 + 10:.1f}" y="{y + 26}" class="bv">+{g:.2f}%</text>'
                   f'<text x="{w}" y="{y + 26}" class="bv" text-anchor="end" fill="{ACCENT if t == min(tt for _, _, tt in ROUTING) else INK}">{t:.0f} 秒</text>')
    head = (f'<text x="{bar0}" y="-8" class="ax">最终得分提升</text><text x="{w}" y="-8" class="ax" text-anchor="end">单轮用时</text>')
    return f'<svg viewBox="0 -24 {w} {h + 24}" width="{w}mm" height="{h + 24}mm">{head}{"".join(out)}</svg>'


def algo_bars(base: float, cand: float) -> str:
    w, h = 320, 46
    full = 230
    c = max(3, full * cand / base)
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}mm" height="{h}mm">'
            f'<rect x="0" y="2" width="{full}" height="16" fill="{LINE}"/><text x="{full + 8}" y="15" class="ax">{base:.2f} ms</text>'
            f'<rect x="0" y="26" width="{c:.1f}" height="16" fill="{ACCENT}"/><text x="{c + 8:.1f}" y="39" class="ax">{cand:.2f} ms</text></svg>')


def page() -> str:
    CJK_WEB = "&family=Noto+Sans+SC:wght@400..900" if CJK == "Noto Sans SC" else ""
    cut = round(100 * (1 - ENERGY_BEST / ENERGY_C0), 1)
    both = ROUTING[3]
    time_cut = round(100 * (1 - both[2] / ROUTING[0][2]))
    fmt_x = lambda v: f"{v:.1f}×" if v >= 10 else f"{v:.2f}×"  # noqa: E731
    algo = "".join(f'<div class="algo"><div class="big">{fmt_x(sp)}</div><div class="cap">{name} 提速</div>'
                   f'<div class="how">{how}</div>{algo_bars(b, c)}</div>' for name, sp, b, c, how in ALGO)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>QuotaCrux 枢决 poster</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400..900{CJK_WEB}&display=block"><style>
@page {{ size: 800mm 1800mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 800mm; height: 1800mm; }}
body {{ background: {BG}; color: {INK}; font-family: "{LATIN}", "{CJK}", sans-serif; overflow: hidden;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ width: 800mm; height: 1800mm; display: flex; flex-direction: column; justify-content: space-between; padding: 40mm 50mm 34mm; }}
.head {{ display: flex; align-items: flex-end; justify-content: space-between; border-bottom: 2.4mm solid {INK}; padding-bottom: 8mm; }}
.title {{ font-family: "{LATIN}", "{CJK}", sans-serif; font-weight: 800; font-size: 112mm; line-height: 0.82; letter-spacing: -4mm; margin-left: -5mm; }}
.cn {{ font-size: 56mm; font-weight: 600; line-height: 1; letter-spacing: 3mm; white-space: nowrap; }}
.sub {{ display: flex; justify-content: space-between; align-items: baseline; margin-top: 7mm; font-size: 24mm; font-weight: 600; }}
.sub span {{ color: {ACCENT}; }}
.kicker {{ font-size: 19mm; font-weight: 600; letter-spacing: 0.5mm; display: flex; gap: 6mm; align-items: baseline; }}
.kicker b {{ font-family: "{LATIN}", "{CJK}", sans-serif; font-weight: 700; color: {ACCENT}; }}
.hero {{ display: flex; align-items: flex-end; gap: 14mm; margin-top: 6mm; }}
.hero .num {{ font-family: "{LATIN}", "{CJK}", sans-serif; font-weight: 800; font-size: 150mm; line-height: 0.8; letter-spacing: -8mm; color: {ACCENT}; }}
.hero .cap {{ font-size: 32mm; font-weight: 600; line-height: 1.25; padding-bottom: 2mm; white-space: nowrap; }}
.bars {{ margin-top: 12mm; }}
svg text.bl {{ font-size: 15px; font-weight: 600; }}
svg text.bv {{ font-size: 17px; font-weight: 700; font-family: "{LATIN}", "{CJK}", sans-serif; }}
svg text.ax {{ font-size: 11px; fill: {GREY}; font-family: "{LATIN}", "{CJK}", sans-serif; }}
svg text.an {{ font-size: 13.5px; font-weight: 600; fill: {INK}; }}
svg text.rl {{ font-size: 17px; font-weight: 600; fill: {INK}; }}
h2 {{ font-size: 36mm; font-weight: 600; letter-spacing: -0.5mm; margin-top: 5mm; line-height: 1.25; }}
.algos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20mm; margin-top: 10mm; }}
.algo .big {{ font-family: "{LATIN}", "{CJK}", sans-serif; font-weight: 800; font-size: 96mm; line-height: 0.9; letter-spacing: -4mm; }}
.algo .cap {{ font-size: 28mm; font-weight: 600; margin-top: 4mm; }}
.algo .how {{ font-size: 21mm; color: {ACCENT}; font-weight: 600; margin: 3mm 0 7mm; }}
.route {{ margin-top: 10mm; }}
.callout {{ border-top: 1.2mm solid {INK}; padding-top: 6mm; margin-bottom: 16mm; }}
.callout .big {{ font-family: "{LATIN}", "{CJK}", sans-serif; font-weight: 800; font-size: 76mm; line-height: 0.9; letter-spacing: -2mm; }}
.callout .cap {{ font-size: 21mm; font-weight: 600; margin-top: 3mm; line-height: 1.3; }}
.ledger {{ display: grid; grid-template-columns: repeat(3, 1fr); border-top: 2.4mm solid {INK}; border-bottom: 1.2mm solid {INK}; }}
.ledger > div {{ padding: 9mm 0 10mm; }}
.ledger > div + div {{ border-left: 1.2mm solid {INK}; padding-left: 12mm; }}
.ledger .big {{ font-family: "{LATIN}", "{CJK}", sans-serif; font-weight: 800; font-size: 62mm; line-height: 0.9; letter-spacing: -2mm; }}
.ledger .cap {{ font-size: 20mm; font-weight: 600; margin-top: 4mm; line-height: 1.3; }}
.foot {{ display: flex; justify-content: space-between; align-items: center; }}
.foot .t {{ font-size: 22mm; font-weight: 600; }}
.foot svg {{ width: 56mm; height: 56mm; display: block; }}
</style></head><body><div class="page">

<div>
  <div class="head"><div class="title">QuotaCrux</div><div class="cn">枢决</div></div>
  <div class="sub"><div>预算有限的研究 Agent：小模型先跑，卡住才升级</div><span>●</span></div>
</div>

<section>
  <div class="kicker"><b>01</b>搬箱子难题 · 15 个最终用例全部通过</div>
  <div class="hero"><div class="num">−{cut}%</div><div class="cap">箱子搬运<br>能耗</div></div>
  <div class="bars">{energy_bars()}</div>
</section>

<section>
  <div class="kicker"><b>02</b>一次研究的全过程</div>
  <h2>7 个方案逐个验证，只保留更好的那个</h2>
  <div style="margin-top: 8mm">{case_chart()}</div>
</section>

<section>
  <div class="kicker"><b>03</b>函数级优化</div>
  <div class="algos">{algo}</div>
</section>

<section>
  <div class="kicker"><b>04</b>谁来决定下一步</div>
  <h2>决策模型全权调度：快 {time_cut}%</h2>
  <div class="route">{routing_chart()}</div>
</section>

<div class="ledger">
  <div><div class="big" style="color: {ACCENT}">−{100 * (1 - COST_AFTER / COST_BEFORE):.0f}%</div><div class="cap">云端花费</div></div>
  <div><div class="big">+{100 * (SPEEDUP_AFTER / SPEEDUP_BEFORE - 1):.0f}%</div><div class="cap">典型加速比</div></div>
  <div><div class="big">&gt;99%</div><div class="cap">合格率</div></div>
</div>

<div class="foot"><div class="t">QuotaCrux 枢决 · 扫码查看代码与实验报告</div>{qr_svg()}</div>
</div></body></html>"""


def main() -> None:
    global CJK
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "poster" / "QuotaCrux-poster.pdf"))
    ap.add_argument("--cjk", default=CJK, help='Chinese font, e.g. "PingFang SC" on a Mac')
    args = ap.parse_args()
    CJK = args.cjk
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    src = out.with_suffix(".html")
    src.write_text(page(), encoding="utf-8")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=5000",
                    f"--print-to-pdf={out}", src.as_uri()], check=True, capture_output=True)
    print(f"wrote {out} and {src}")


if __name__ == "__main__":
    main()
