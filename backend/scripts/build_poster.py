"""Build the 80 x 180 cm QuotaCrux (枢决) poster (PDF) from stored records; the illustration comes from docs/poster/assets.

    uv run --with segno python scripts/build_poster.py [--out ../docs/poster/QuotaCrux-poster.pdf]

Every number is read from the SQLite store or a comparison summary when the poster is built. The illustration was
generated with gpt-image-2 and contains no text; the route map, figures and chart are typeset here as vectors.

Colour carries one meaning throughout: amber = verified-program reuse (no model call), teal = local small model,
violet = cloud large model. Pairwise colour distance stays >= 18 (OKLab x100) under simulated deuteranopia.
"""

from __future__ import annotations

import argparse
import base64
import io
import subprocess
from pathlib import Path

import segno

from routeevo import compare, db, live, report

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "poster" / "assets"
REPO = "https://github.com/bohack-2026-hw/RouteEvo"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

BG, INK, MUTED, RULE = "#F5F0EB", "#1D2133", "#5F6476", "#DCD5CC"
AMBER, TEAL, VIOLET = "#E8962A", "#0FA38A", "#6D5BF6"
AMBER_T, TEAL_T, VIOLET_T = "#B26A0E", "#0A7E6B", "#5442E0"  # darker text shades for the light background
SLATE = "#8A8FA3"  # the "without experience" line in the cost chart


def find(prefix: str) -> dict:
    row = next(r for r in db.all_rows("SELECT comparison_id, label FROM comparisons WHERE status = 'completed' ORDER BY created_at DESC")
               if (r["label"] or "").startswith(prefix))
    return compare.summarize(row["comparison_id"])


def ablation() -> dict:
    out = {}
    for arm in ("on", "off"):
        ids = [r["run_id"] for r in db.all_rows("SELECT run_id FROM runs WHERE json_extract(config_json, '$.label') = ?"
                                                " AND status != 'running'", (f"router ablation · {arm}",))]
        out[arm] = compare._side([report.build(i) for i in ids])
    return out


def numbers() -> dict:
    sysm = live.system_summary()
    s = find("S online stream")
    F, M = s["sides"]["fresh"], s["sides"]["memory"]
    d = find("D final held-out")
    A, B = d["sides"][d["snapshot_a"]], d["sides"][d["snapshot_b"]]
    ab = ablation()
    small, large = sysm["calls"]["small"]["requests"], sysm["calls"]["large"]["requests"]
    no_cloud = sysm["runs"] - sysm["split"]["large_used"]
    mean = {arm: [sum(s["series"][arm][r]["cost_usd"][i] for r in s["series"][arm]) / len(s["series"][arm])
                  for i in range(len(s["positions"]))] for arm in ("fresh", "memory")}
    return {
        "runs": sysm["runs"], "no_cloud": no_cloud, "no_cloud_pct": round(100 * no_cloud / sysm["runs"]),
        "small_pct": round(100 * small / (small + large)), "small": small, "large": large,
        "s_tasks": len(s["tasks"]), "s_rep": s["repeats"],
        "s_large": (F["large_model_requests_total"], M["large_model_requests_total"]),
        "s_large_cut": round(100 * (1 - M["large_model_requests_total"] / F["large_model_requests_total"])),
        "s_cost": (F["cost_usd_total"], M["cost_usd_total"]),
        "s_loop": (F["agent_loop_s_median"], M["agent_loop_s_median"]), "s_goal": (F["goal_met"], F["runs"], M["goal_met"], M["runs"]),
        "s_mean": mean, "s_first": [p["first_of_family"] for p in s["positions"]],
        "d_goal": (A["goal_met"], A["runs"], B["goal_met"], B["runs"]), "d_speed": (A["final_speedup_median"], B["final_speedup_median"]),
        "d_cost": (A["cost_usd_total"], B["cost_usd_total"]), "d_tasks": len(d["tasks"]), "d_rep": d["repeats"],
        "ab_loop": (ab["off"]["agent_loop_s_median"], ab["on"]["agent_loop_s_median"]),
        "ab_speed": (ab["off"]["final_speedup_median"], ab["on"]["final_speedup_median"]),
        "ab_extra": ((ab["on"]["cost_usd_total"] or 0) - (ab["off"]["cost_usd_total"] or 0)) / max(1, ab["on"]["runs"]),
    }


def img(name: str) -> str:
    return "data:image/png;base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


def qr_svg() -> str:
    buf = io.BytesIO()
    segno.make(REPO, error="m").save(buf, kind="svg", scale=1, border=0, dark=INK, light=None, xmldecl=False, svgns=True, omitsize=True)
    return buf.getvalue().decode()


# ---------- route map ----------

def _station(x: float, y: float, color: str, big: bool = False) -> str:
    if big:
        return f'<circle cx="{x}" cy="{y}" r="12" fill="#fff" stroke="{color}" stroke-width="4.5"/><circle cx="{x}" cy="{y}" r="4.5" fill="{color}"/>'
    return f'<circle cx="{x}" cy="{y}" r="8.5" fill="#fff" stroke="{color}" stroke-width="3.6"/>'


def _label(x: float, y: float, name: str, desc: list[str], anchor: str = "middle", below: bool = False) -> str:
    """Station name plus short description lines, stacked above (or below) the station at (x, y)."""
    rows = [(name, "nm", INK)] + [(d, "ds", MUTED) for d in desc]
    if below:
        ys = [y + 30 + i * 12.5 for i in range(len(rows))]
    else:
        ys = [y - 20 - (len(rows) - 1 - i) * 12.5 for i in range(len(rows))]
        ys[0] -= 2
    return "".join(f'<text x="{x}" y="{yy:.1f}" class="{cls}" fill="{c}" text-anchor="{anchor}">{t}</text>' for (t, cls, c), yy in zip(rows, ys))


def _badge(x: float, y: float, text: str, color: str) -> str:
    return (f'<circle cx="{x}" cy="{y}" r="9.5" fill="{color}" stroke="{BG}" stroke-width="2"/>'
            f'<text x="{x}" y="{y + 4.2}" class="bd" fill="#fff" text-anchor="middle">{text}</text>')


def route_map() -> str:
    W, H = 700, 440
    ox, oy = 72, 200          # origin: a new research task
    ya, yt, yv = 60, 200, 340   # amber / teal / violet rows
    mx = 612                  # merge: acceptance and delivery
    curve = lambda yr: (f"M{ox},{oy} C{ox + 50},{oy} {ox + 44},{yr} {ox + 98},{yr} L{mx - 98},{yr} "  # noqa: E731
                        f"C{mx - 44},{yr} {mx - 50},{oy} {mx},{oy}")
    teal = [(178, "规划"), (250, "取证"), (322, "假设"), (394, "实验"), (466, "验证"), (538, "修正")]
    p = [f'<svg viewBox="0 0 {W} {H}" width="{W}mm" height="{H}mm" xmlns="http://www.w3.org/2000/svg">']
    for path, color in ((curve(ya), AMBER), (curve(yv), VIOLET), (f"M{ox},{oy} L{mx},{oy}", TEAL)):
        p.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>')
    # transfer from the local line to the cloud line, with its conditions written next to it
    p.append(f'<path d="M466,{yt + 12} L466,{yv - 12}" stroke="{VIOLET}" stroke-width="4" stroke-dasharray="6 6" fill="none"/>')
    mid = (yt + yv) / 2
    p.append(f'<text x="452" y="{mid - 14}" class="cd" fill="{INK}" text-anchor="end">连续 2 次没达标</text>')
    p.append(f'<text x="452" y="{mid + 3}" class="cd" fill="{INK}" text-anchor="end">或 3 次请求没达标</text>')
    p.append(f'<text x="452" y="{mid + 22}" class="tr" fill="{VIOLET_T}" text-anchor="end">↓ 换乘大模型</text>')
    # which tasks take the two branches, written where the branch starts
    p.append(f'<text x="{ox + 40}" y="{ya - 18}" class="cd" fill="{AMBER_T}">做过同类题 →</text>')
    p.append(f'<text x="{ox + 40}" y="{yv + 32}" class="cd" fill="{VIOLET_T}">全新问题 →</text>')
    for x, name in teal:
        p.append(_station(x, yt, TEAL) + _label(x, yt, name, []))
    for x, name in ((330, "复验已验证的程序"), (488, "达标直接交付")):
        p.append(_station(x, ya, AMBER) + _label(x, ya, name, []))
    for x, name in ((330, "大模型接手研究"), (500, "做对后写入经验")):
        p.append(_station(x, yv, VIOLET) + _label(x, yv, name, [], below=True))
    p.append(_station(ox, oy, INK, big=True) + f'<text x="{ox - 22}" y="{oy + 5}" class="nm" fill="{INK}" text-anchor="end">新任务</text>')
    p.append(_station(mx, oy, INK, big=True))
    p.append(f'<text x="{mx + 22}" y="{oy - 4}" class="nm" fill="{INK}">验收</text>')
    p.append(f'<text x="{mx + 22}" y="{oy + 14}" class="nm" fill="{INK}">交付</text>')
    p.append("</svg>")
    return "".join(p)


def cost_chart(n: dict, w: float = 330, h: float = 128) -> str:
    """Mean cumulative cloud cost along the stream, without vs with experience; vector, sized in mm."""
    fresh, mem = n["s_mean"]["fresh"], n["s_mean"]["memory"]
    k = len(fresh)
    left, right, top, bottom = 30, 8, 12, 26
    hi = max(fresh) * 1.12
    x = lambda i: left + i * (w - left - right) / (k - 1)  # noqa: E731
    y = lambda v: top + (1 - v / hi) * (h - top - bottom)  # noqa: E731
    path = lambda vs: " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vs))  # noqa: E731
    grid = "".join(f'<line x1="{left}" x2="{w - right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="{RULE}" stroke-width="0.6"/>'
                   f'<text x="{left - 4}" y="{y(t) + 3:.1f}" class="ax" text-anchor="end">${t:.2f}</text>' for t in (0, 0.05, 0.10))
    xs = "".join(f'<text x="{x(i):.1f}" y="{h - 12}" class="ax" text-anchor="middle">{i + 1}</text>' for i in range(k))
    firsts = "".join(f'<circle cx="{x(i):.1f}" cy="{h - 4}" r="2.6" fill="{VIOLET}"/>' for i in range(k) if n["s_first"][i])
    dots = "".join(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.6" fill="{c}"/>' for vs, c in ((fresh, SLATE), (mem, AMBER)) for i, v in enumerate(vs))
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}mm" height="{h}mm">{grid}{xs}{firsts}'
            f'<path d="{path(fresh)}" fill="none" stroke="{SLATE}" stroke-width="2.6"/>'
            f'<path d="{path(mem)}" fill="none" stroke="{AMBER}" stroke-width="2.6"/>{dots}'
            f'<text x="{x(k - 1)}" y="{y(fresh[-1]) - 7:.1f}" class="cl" fill="{SLATE}" text-anchor="end">没有经验 ${fresh[-1]:.3f}</text>'
            f'<text x="{x(k - 1)}" y="{y(mem[-1]) - 7:.1f}" class="cl" fill="{AMBER_T}" text-anchor="end">有经验 ${mem[-1]:.3f}</text></svg>')


ICONS = {
    "box": '<rect x="8" y="16" width="32" height="24" rx="3"/><path d="M16 16v-4a8 8 0 0 1 16 0v4"/><circle cx="24" cy="28" r="3"/>',
    "clock": '<circle cx="24" cy="27" r="14"/><path d="M24 27l6-6M20 8h8M24 8v5"/>',
    "receipt": '<path d="M12 6h24v36l-4-3-4 3-4-3-4 3-4-3-4 3z"/><path d="M18 16h12M18 23h12M18 30h7"/>',
    "rewind": '<path d="M10 24a14 14 0 1 0 4-10"/><path d="M10 8v8h8"/><path d="M24 17v8l5 4"/>',
}


def icon(name: str, color: str) -> str:
    return (f'<svg viewBox="0 0 48 48" width="28mm" height="28mm" fill="none" stroke="{color}" stroke-width="2.8" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


def page(n: dict) -> str:
    s_large, s_cost, s_loop, s_goal = n["s_large"], n["s_cost"], n["s_loop"], n["s_goal"]
    d_goal, d_speed, d_cost = n["d_goal"], n["d_speed"], n["d_cost"]
    ab_loop, ab_speed = n["ab_loop"], n["ab_speed"]
    ab_cut = round(100 * (1 - ab_loop[1] / ab_loop[0]))
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>QuotaCrux 枢决 poster</title><style>
@page {{ size: 800mm 1800mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 800mm; height: 1800mm; }}
body {{ background: {BG}; color: {INK}; font-family: "PingFang SC", sans-serif; overflow: hidden;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ width: 800mm; height: 1800mm; display: flex; flex-direction: column; justify-content: space-between; padding: 40mm 50mm 34mm; gap: var(--gap); }}
:root {{ --gap: 10mm; --title: 132mm; }}
.title {{ font-family: "Avenir Next", sans-serif; font-weight: 800; font-size: var(--title); line-height: 0.86; letter-spacing: -4mm; margin-left: -6mm; white-space: nowrap; }}
.namerow {{ display: flex; align-items: center; gap: 12mm; margin-top: 10mm; }}
.cn {{ font-size: 46mm; font-weight: 600; letter-spacing: 4mm; margin-left: auto; line-height: 1; }}
.lines {{ display: flex; gap: 5mm; }}
.lines i {{ height: 6mm; border-radius: 3mm; display: block; }}
.top {{ display: grid; grid-template-columns: 1fr 330mm; gap: 14mm; align-items: center; }}
.tag {{ font-size: 50mm; font-weight: 600; line-height: 1.22; letter-spacing: -0.6mm; }}
.lede {{ font-size: 16mm; line-height: 1.6; color: {MUTED}; margin-top: 9mm; }}
.lede b {{ font-weight: 600; }}
.hero {{ width: 330mm; display: block; -webkit-mask-image: radial-gradient(ellipse 70% 70% at 50% 50%, #000 70%, transparent 100%);
  mask-image: radial-gradient(ellipse 70% 70% at 50% 50%, #000 70%, transparent 100%); }}
.sh {{ display: flex; align-items: baseline; gap: 8mm; }}
.sh b {{ font-family: "Avenir Next", sans-serif; font-weight: 700; font-size: 22mm; color: {MUTED}; }}
.sh h2 {{ font-size: 34mm; font-weight: 600; letter-spacing: -0.5mm; }}
.sh span {{ margin-left: auto; font-size: 14mm; color: {MUTED}; }}
.map {{ margin-top: 4mm; }}
.map svg text.nm {{ font-size: 15px; font-weight: 600; }}
.map svg text.ds {{ font-size: 10px; }}
.map svg text.hd {{ font-size: 14px; font-weight: 600; }}
.map svg text.tr {{ font-size: 14px; font-weight: 700; }}
.map svg text.cd {{ font-size: 14px; font-weight: 600; }}
.legend {{ display: flex; gap: 16mm; margin-top: 8mm; font-size: 15mm; font-weight: 600; }}
.legend span {{ display: flex; align-items: center; gap: 4mm; }}
.legend i {{ width: 22mm; height: 5mm; border-radius: 3mm; display: block; }}
.map svg text.bd {{ font-size: 11px; font-weight: 700; font-family: "Avenir Next", sans-serif; }}
.rules {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8mm; margin-top: 2mm; }}
.rule {{ background: #fff; border-radius: 5mm; padding: 8mm 9mm; display: flex; gap: 5mm; align-items: flex-start; font-size: 14mm; line-height: 1.4; font-weight: 600; }}
.rule i {{ font-style: normal; flex: none; width: 17mm; height: 17mm; border-radius: 50%; color: #fff; font-weight: 700;
  font-family: "Avenir Next", sans-serif; font-size: 11mm; display: grid; place-items: center; margin-top: 1mm; }}

.res {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14mm 16mm; margin-top: 12mm; }}
.stat .big {{ font-family: "Avenir Next", sans-serif; font-weight: 700; font-size: 76mm; line-height: 0.95; letter-spacing: -2mm; }}
.stat .cap {{ font-size: 21mm; font-weight: 600; margin-top: 4mm; line-height: 1.3; }}
.stat .sub {{ font-size: 12.5mm; line-height: 1.5; color: {MUTED}; margin-top: 2mm; }}
.chartbox {{ grid-column: span 2; display: grid; grid-template-columns: 1fr 330mm; gap: 16mm; align-items: center;
  border-top: 0.6mm solid {RULE}; padding-top: 8mm; }}
.chartbox h3 {{ font-size: 24mm; font-weight: 600; line-height: 1.3; }}
.chartbox p {{ font-size: 12.5mm; line-height: 1.55; color: {MUTED}; margin-top: 3mm; }}
.chartbox svg text.ax {{ font-size: 8.5px; fill: {MUTED}; font-family: "Avenir Next", sans-serif; }}
.chartbox svg text.cl {{ font-size: 10.5px; font-weight: 600; font-family: "PingFang SC", sans-serif; }}
.trust {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10mm; margin-top: 6mm; }}
.trust div {{ font-size: 13mm; line-height: 1.45; }}
.trust b {{ display: block; font-size: 19mm; color: {INK}; margin: 4mm 0 0; line-height: 1.35; }}
.foot {{ display: grid; grid-template-columns: 1fr 52mm; gap: 14mm; align-items: end;
  border-top: 0.8mm solid {RULE}; padding-top: 8mm; }}
.foot .repo {{ font-size: 20mm; font-weight: 600; }}
.foot p {{ font-size: 12mm; line-height: 1.5; color: {MUTED}; margin-top: 2mm; }}
.foot svg {{ width: 52mm; height: 52mm; display: block; }}
</style></head><body><div class="page">

<div>
  <div class="title">QuotaCrux</div>
  <div class="namerow"><div class="lines"><i style="width: 100mm; background: {AMBER}"></i><i style="width: 220mm; background: {TEAL}"></i><i style="width: 60mm; background: {VIOLET}"></i></div><div class="cn">枢决</div></div>
</div>
<div class="top"><div>
  <div class="tag">每一步研究，<br>都走最划算的<br>那条线。</div>
</div><img class="hero" src="{img('hero.png')}" alt=""></div>

<section>
  <div class="sh"><b>01</b><h2>三条路线，由程序分流</h2></div>
  <div class="legend"><span style="color: {AMBER_T}"><i style="background: {AMBER}"></i>经验直达 · 不调用模型</span>
    <span style="color: {TEAL_T}"><i style="background: {TEAL}"></i>本地小模型 · 免费主力</span>
    <span style="color: {VIOLET_T}"><i style="background: {VIOLET}"></i>云端大模型 · 关键时刻</span></div>
  <div class="map">{route_map()}</div>
</section>

<section>
  <div class="sh"><b>02</b><h2>用得少、跑得快，质量不降</h2></div>
  <div class="res">
    <div class="stat"><div class="big" style="color: {TEAL_T}">{n['no_cloud_pct']}%</div><div class="cap">的运行全程没用云端大模型</div></div>
    <div class="stat"><div class="big" style="color: {VIOLET_T}">−{n['s_large_cut']}%</div><div class="cap">有经验后，云端大模型调用减少</div></div>
    <div class="stat"><div class="big" style="color: {AMBER_T}">{d_goal[2]}/{d_goal[3]}</div><div class="cap">没见过的新题全部达标</div></div>
    <div class="stat"><div class="big" style="color: {VIOLET_T}">−{ab_cut}%</div><div class="cap">新问题直接交给大模型，研究更快</div></div>
    <div class="chartbox"><div><h3>云端费用只在新问题<br>第一次出现时增加</h3></div>{cost_chart(n)}</div>
  </div>
</section>

<section>
  <div class="sh"><b>03</b><h2>结论经得起核对</h2></div>
  <div class="trust">
    <div>{icon('box', TEAL)}<b>方案在断网的<br>隔离容器里运行</b></div>
    <div>{icon('clock', VIOLET)}<b>每次计时都快于<br>基线才算改善</b></div>
    <div>{icon('receipt', AMBER)}<b>每次模型调用<br>都记账</b></div>
    <div>{icon('rewind', TEAL)}<b>全程可复现、<br>经验可回退</b></div>
  </div>
</section>

<div class="foot"><div><div class="repo">QuotaCrux 枢决 · 扫码查看代码与实验记录</div></div>{qr_svg()}</div>
</div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "poster" / "QuotaCrux-poster.pdf"))
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    src = out.with_suffix(".html")
    src.write_text(page(numbers()))
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=5000",
                    f"--print-to-pdf={out}", src.as_uri()], check=True, capture_output=True)
    print(f"wrote {out} and {src}")


if __name__ == "__main__":
    main()
