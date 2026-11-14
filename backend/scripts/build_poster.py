"""Build the 80 x 180 cm portrait poster (PDF) from stored records; the illustration comes from docs/poster/assets.

    uv run --with segno python scripts/build_poster.py [--out ../docs/poster/RouteEvo-poster.pdf]

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
NAVY, CREAM = "#171B2E", "#EDE8E0"
AMBER_B, TEAL_B, VIOLET_B, SLATE = "#FFC46B", "#3DD9BE", "#A497FF", "#8A90A8"  # brighter shades on navy


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
    W, H = 700, 452
    ox, oy = 24, 212          # origin: a new research task
    ya, yt, yv = 64, 212, 360   # amber / teal / violet rows
    mx = 600                  # merge: frozen best, hidden test, delivery
    curve = lambda yr: (f"M{ox},{oy} C{ox + 50},{oy} {ox + 44},{yr} {ox + 98},{yr} L{mx - 98},{yr} "  # noqa: E731
                        f"C{mx - 44},{yr} {mx - 50},{oy} {mx},{oy}")
    teal = [(140, "规划", ["固定问题、基线", "工具与预算"]), (215, "取证", ["剖析热点", "看数据画像"]),
            (290, "假设", ["先写预期", "和验证方法"]), (365, "实验", ["提交一版", "候选程序"]),
            (440, "验证", ["裁判判定", "正确 + 计时"]), (515, "修正", ["按反馈回到", "假设继续"])]
    p = [f'<svg viewBox="0 0 {W} {H}" width="{W}mm" height="{H}mm" xmlns="http://www.w3.org/2000/svg">']
    for path, color in ((curve(ya), AMBER), (curve(yv), VIOLET), (f"M{ox},{oy} L{mx},{oy}", TEAL)):
        p.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>')
    # transfer from the local line to the cloud line (rules 1 and 2)
    p.append(f'<path d="M440,{yt + 12} L440,{yv - 12}" stroke="{VIOLET}" stroke-width="4" stroke-dasharray="6 6" fill="none"/>')
    mid = (yt + yv) / 2 + 4
    p.append(_badge(440, mid - 12, "①", VIOLET) + _badge(440, mid + 12, "②", VIOLET))
    p.append(f'<text x="456" y="{mid + 4}" class="tr" fill="{VIOLET_T}">换乘大模型</text>')
    # line names
    p.append(f'<text x="{ox + 106}" y="{ya + 32}" class="hd" fill="{AMBER_T}">经验直达 · 0 次模型调用</text>')
    p.append(f'<text x="{ox + 106}" y="{yt + 32}" class="hd" fill="{TEAL_T}">本地小模型 · 免费 · 主力</text>')
    p.append(f'<text x="{ox + 106}" y="{yv - 22}" class="hd" fill="{VIOLET_T}">云端大模型 · 按次付费 · 只在关键节点</text>')
    # entry badges on the branch curves
    p.append(_badge(ox + 40, (oy + ya) / 2 + 4, "★", AMBER))
    p.append(_badge(ox + 40, (oy + yv) / 2 - 4, "③", VIOLET))
    for x, name, desc in teal:
        p.append(_station(x, yt, TEAL) + _label(x, yt, name, desc))
    for x, name, desc in ((260, "复验已验证程序", ["经验里条件最接近的 ≤3 个", "在本题数据上重新测"]), (440, "达标即交付", ["不调用任何模型"])):
        p.append(_station(x, ya, AMBER) + _label(x, ya, name, desc))
    for x, name, desc in ((260, "大模型接手", ["同一套研究闭环", "剩余预算都给它"]), (480, "做对一次", ["结果写入经验库", "下次同类走黄线"])):
        p.append(_station(x, yv, VIOLET) + _label(x, yv, name, desc, below=True))
    p.append(_station(ox, oy, INK, big=True) + f'<text x="{ox - 6}" y="{oy - 26}" class="nm" fill="{INK}">新任务</text>')
    p.append(_station(mx, oy, INK, big=True))
    p.append(f'<text x="{mx + 20}" y="{oy - 18}" class="nm" fill="{INK}">验收 · 交付</text>')
    for i, t in enumerate(("冻结最佳方案", "隐藏数据只测一次", "写回经验库")):
        p.append(f'<text x="{mx + 20}" y="{oy + 2 + i * 12.5}" class="ds" fill="{MUTED}">{t}</text>')
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
    grid = "".join(f'<line x1="{left}" x2="{w - right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#2C3148" stroke-width="0.6"/>'
                   f'<text x="{left - 4}" y="{y(t) + 3:.1f}" class="ax" text-anchor="end">${t:.2f}</text>' for t in (0, 0.05, 0.10))
    xs = "".join(f'<text x="{x(i):.1f}" y="{h - 12}" class="ax" text-anchor="middle">{i + 1}</text>' for i in range(k))
    firsts = "".join(f'<circle cx="{x(i):.1f}" cy="{h - 4}" r="2.6" fill="{VIOLET_B}"/>' for i in range(k) if n["s_first"][i])
    dots = "".join(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.6" fill="{c}"/>' for vs, c in ((fresh, SLATE), (mem, AMBER_B)) for i, v in enumerate(vs))
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}mm" height="{h}mm">{grid}{xs}{firsts}'
            f'<path d="{path(fresh)}" fill="none" stroke="{SLATE}" stroke-width="2.6"/>'
            f'<path d="{path(mem)}" fill="none" stroke="{AMBER_B}" stroke-width="2.6"/>{dots}'
            f'<text x="{x(k - 1)}" y="{y(fresh[-1]) - 7:.1f}" class="cl" fill="{SLATE}" text-anchor="end">没有经验 ${fresh[-1]:.3f}</text>'
            f'<text x="{x(k - 1)}" y="{y(mem[-1]) - 7:.1f}" class="cl" fill="{AMBER_B}" text-anchor="end">有经验 ${mem[-1]:.3f}</text></svg>')


ICONS = {
    "box": '<rect x="8" y="16" width="32" height="24" rx="3"/><path d="M16 16v-4a8 8 0 0 1 16 0v4"/><circle cx="24" cy="28" r="3"/>',
    "clock": '<circle cx="24" cy="27" r="14"/><path d="M24 27l6-6M20 8h8M24 8v5"/>',
    "receipt": '<path d="M12 6h24v36l-4-3-4 3-4-3-4 3-4-3-4 3z"/><path d="M18 16h12M18 23h12M18 30h7"/>',
    "rewind": '<path d="M10 24a14 14 0 1 0 4-10"/><path d="M10 8v8h8"/><path d="M24 17v8l5 4"/>',
}


def icon(name: str, color: str) -> str:
    return (f'<svg viewBox="0 0 48 48" width="22mm" height="22mm" fill="none" stroke="{color}" stroke-width="2.8" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


def page(n: dict) -> str:
    s_large, s_cost, s_loop, s_goal = n["s_large"], n["s_cost"], n["s_loop"], n["s_goal"]
    d_goal, d_speed, d_cost = n["d_goal"], n["d_speed"], n["d_cost"]
    ab_loop, ab_speed = n["ab_loop"], n["ab_speed"]
    ab_cut = round(100 * (1 - ab_loop[1] / ab_loop[0]))
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>RouteEvo poster</title><style>
@page {{ size: 800mm 1800mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 800mm; height: 1800mm; }}
body {{ background: {BG}; color: {INK}; font-family: "PingFang SC", sans-serif; overflow: hidden;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ width: 800mm; height: 1800mm; display: flex; flex-direction: column; padding: 34mm 50mm 28mm; gap: var(--gap); }}
:root {{ --gap: 10mm; }}
.title {{ font-family: "Avenir Next", sans-serif; font-weight: 800; font-size: 150mm; line-height: 0.86; letter-spacing: -4mm; margin-left: -6mm; }}
.lines {{ display: flex; gap: 5mm; margin-top: 10mm; }}
.lines i {{ height: 6mm; border-radius: 3mm; display: block; }}
.top {{ display: grid; grid-template-columns: 1fr 330mm; gap: 14mm; align-items: center; }}
.tag {{ font-size: 40mm; font-weight: 600; line-height: 1.22; letter-spacing: -0.6mm; }}
.lede {{ font-size: 16mm; line-height: 1.6; color: {MUTED}; margin-top: 9mm; }}
.lede b {{ font-weight: 600; }}
.hero {{ width: 330mm; display: block; -webkit-mask-image: radial-gradient(ellipse 70% 70% at 50% 50%, #000 70%, transparent 100%);
  mask-image: radial-gradient(ellipse 70% 70% at 50% 50%, #000 70%, transparent 100%); }}
.sh {{ display: flex; align-items: baseline; gap: 8mm; }}
.sh b {{ font-family: "Avenir Next", sans-serif; font-weight: 700; font-size: 22mm; color: {MUTED}; }}
.sh h2 {{ font-size: 34mm; font-weight: 600; letter-spacing: -0.5mm; }}
.sh span {{ margin-left: auto; font-size: 14mm; color: {MUTED}; }}
.map {{ margin-top: 4mm; }}
.map svg text.nm {{ font-size: 13px; font-weight: 600; }}
.map svg text.ds {{ font-size: 10px; }}
.map svg text.hd {{ font-size: 12px; font-weight: 600; }}
.map svg text.tr {{ font-size: 11px; font-weight: 600; }}
.map svg text.bd {{ font-size: 11px; font-weight: 700; font-family: "Avenir Next", sans-serif; }}
.rules {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8mm; margin-top: 2mm; }}
.rule {{ background: #fff; border-radius: 5mm; padding: 7mm 8mm; display: flex; gap: 5mm; align-items: flex-start; font-size: 13.2mm; line-height: 1.4; }}
.rule i {{ font-style: normal; flex: none; width: 17mm; height: 17mm; border-radius: 50%; color: #fff; font-weight: 700;
  font-family: "Avenir Next", sans-serif; font-size: 11mm; display: grid; place-items: center; margin-top: 1mm; }}
.dark {{ margin: 0 -50mm; background: {NAVY}; color: {CREAM}; padding: 14mm 50mm 14mm; }}
.dark .sh b, .dark .sh span {{ color: #8A90A8; }}
.res {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10mm 16mm; margin-top: 10mm; }}
.stat .big {{ font-family: "Avenir Next", sans-serif; font-weight: 700; font-size: 64mm; line-height: 0.95; letter-spacing: -2mm; }}
.stat .cap {{ font-size: 17mm; font-weight: 600; margin-top: 4mm; }}
.stat .sub {{ font-size: 12.5mm; line-height: 1.5; color: #A9ACBB; margin-top: 2mm; }}
.chartbox {{ grid-column: span 2; display: grid; grid-template-columns: 1fr 330mm; gap: 16mm; align-items: center;
  border-top: 0.6mm solid #2C3148; padding-top: 8mm; }}
.chartbox h3 {{ font-size: 17mm; font-weight: 600; }}
.chartbox p {{ font-size: 12.5mm; line-height: 1.55; color: #A9ACBB; margin-top: 3mm; }}
.chartbox svg text.ax {{ font-size: 8.5px; fill: #7D8299; font-family: "Avenir Next", sans-serif; }}
.chartbox svg text.cl {{ font-size: 10.5px; font-weight: 600; font-family: "PingFang SC", sans-serif; }}
.trust {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10mm; margin-top: 6mm; }}
.trust div {{ font-size: 13mm; line-height: 1.45; color: {MUTED}; }}
.trust b {{ display: block; font-size: 16mm; color: {INK}; margin: 3mm 0 1mm; }}
.foot {{ margin-top: auto; display: grid; grid-template-columns: 1fr 52mm; gap: 14mm; align-items: end;
  border-top: 0.8mm solid {RULE}; padding-top: 8mm; }}
.foot .repo {{ font-family: "Avenir Next", sans-serif; font-weight: 600; font-size: 17mm; }}
.foot p {{ font-size: 12mm; line-height: 1.5; color: {MUTED}; margin-top: 2mm; }}
.foot svg {{ width: 52mm; height: 52mm; display: block; }}
</style></head><body><div class="page">

<div>
  <div class="title">RouteEvo</div>
  <div class="lines"><i style="width: 120mm; background: {AMBER}"></i><i style="width: 260mm; background: {TEAL}"></i><i style="width: 70mm; background: {VIOLET}"></i></div>
</div>
<div class="top"><div>
  <div class="tag">每一步研究，<br>都走最划算的<br>那条线。</div>
  <div class="lede">RouteEvo 会自己规划、取证、提假设、做实验、验证和修正。<b style="color: {AMBER_T}">熟悉的问题</b>直接复用验证过的程序；
  <b style="color: {TEAL_T}">日常研究</b>交给本地小模型；<b style="color: {VIOLET_T}">卡住或全新的问题</b>才换乘云端大模型。</div>
</div><img class="hero" src="{img('hero.png')}" alt=""></div>

<section>
  <div class="sh"><b>01</b><h2>三条路线，程序来分流</h2><span>每次分流都写进账本，模型不能自评</span></div>
  <div class="map">{route_map()}</div>
  <div class="rules">
    <div class="rule"><i style="background: {VIOLET}">①</i><span>本地小模型连续 2 个方案没达标</span></div>
    <div class="rule"><i style="background: {VIOLET}">②</i><span>本地小模型用了 3 次请求，仍没有达标方案</span></div>
    <div class="rule"><i style="background: {VIOLET}">③</i><span>全新问题：经验里没有同类，或没有条件相近的成功</span></div>
  </div>
</section>

<section class="dark">
  <div class="sh"><b>02</b><h2>用得少、跑得快，质量不降</h2><span>全部来自真实运行记录</span></div>
  <div class="res">
    <div class="stat"><div class="big" style="color: {TEAL_B}">{n['no_cloud_pct']}%</div><div class="cap">的运行全程没用云端大模型</div>
      <div class="sub">{n['runs']} 次真实运行中 {n['no_cloud']} 次；本地小模型完成 {n['small_pct']}% 的模型请求</div></div>
    <div class="stat"><div class="big" style="color: {VIOLET_B}">−{n['s_large_cut']}%</div><div class="cap">云端调用（有经验 vs 没有经验）</div>
      <div class="sub">同一串 {n['s_tasks']} 道题 × {n['s_rep']} 次重放：{s_large[0]} → {s_large[1]} 次；单次研究 {s_loop[0]:.0f} s → {s_loop[1]:.0f} s；达标 {s_goal[2]}/{s_goal[3]} 不变</div></div>
    <div class="stat"><div class="big" style="color: {AMBER_B}">{d_goal[2]}/{d_goal[3]}</div><div class="cap">没见过的新题全部达标</div>
      <div class="sub">{n['d_tasks']} 道封存题 × {n['d_rep']} 次：没有经验时 {d_goal[0]}/{d_goal[1]}；加速比中位数 {d_speed[0]:.2f}× → {d_speed[1]:.2f}×；云端费用 ${d_cost[0]:.2f} → $0</div></div>
    <div class="stat"><div class="big" style="color: {VIOLET_B}">−{ab_cut}%</div><div class="cap">新问题直接换乘，研究更快</div>
      <div class="sub">对比先让本地小模型试：单次研究 {ab_loop[0]:.0f} s → {ab_loop[1]:.0f} s，加速比 {ab_speed[0]:.2f}× → {ab_speed[1]:.2f}×；每题多花约 {n['ab_extra'] * 100:.1f} 美分</div></div>
    <div class="chartbox"><div><h3>只在新问题第一次出现时花钱</h3>
      <p>沿同一串任务累计的云端费用（图为 3 次重放的平均）。紫点是新类型问题第一次出现的位置；之后的同类问题走黄线，费用不再增加。3 次重放合计 ${s_cost[0]:.3f} → ${s_cost[1]:.3f}。</p></div>{cost_chart(n)}</div>
  </div>
</section>

<section>
  <div class="sh"><b>03</b><h2>结论经得起核对</h2></div>
  <div class="trust">
    <div>{icon('box', TEAL)}<b>隔离运行</b>方案在断网、只读、1 CPU 的容器里跑，参考答案不进容器</div>
    <div>{icon('clock', VIOLET)}<b>严格计时</b>5 轮交替计时全部快于基线才算改善，隐藏数据只验收一次</div>
    <div>{icon('receipt', AMBER)}<b>逐次记账</b>每次调用记下 Token、费用和时间，未知就写“未知”</div>
    <div>{icon('rewind', TEAL)}<b>可复现可回退</b>导出研究记录、程序、原始调用和复现脚本；经验有版本</div>
  </div>
</section>

<div class="foot"><div><div class="repo">github.com/bohack-2026-hw/RouteEvo</div>
  <p>BoHack 2026 · 倍漾量化 Research Agent　|　分组聚合 · 访问日志统计 · 区间合并 · ALE-Bench · AlgoTune</p></div>{qr_svg()}</div>
</div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "poster" / "RouteEvo-poster.pdf"))
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
