"""Build the 80 x 180 cm portrait poster (PDF) from stored records; illustrations come from docs/poster/assets.

    uv run --with segno python scripts/build_poster.py [--out ../docs/poster/RouteEvo-poster.pdf]

Every number is read from the SQLite store or a comparison summary when the poster is built. The illustrations were
generated with gpt-image-2 and contain no text; all text, figures and the chart are typeset here as vectors.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import subprocess
from pathlib import Path

import segno

from routeevo import compare, db, live, report

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "poster" / "assets"
REPO = "https://github.com/bohack-2026-hw/RouteEvo"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


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
        "s_cost": (F["cost_usd_total"], M["cost_usd_total"]), "s_cost_cut": round(100 * (1 - M["cost_usd_total"] / F["cost_usd_total"])),
        "s_loop": (F["agent_loop_s_median"], M["agent_loop_s_median"]), "s_goal": (F["goal_met"], F["runs"], M["goal_met"], M["runs"]),
        "s_speed": (F["final_speedup_median"], M["final_speedup_median"]), "s_mean": mean,
        "s_first": [p["first_of_family"] for p in s["positions"]],
        "d_goal": (A["goal_met"], A["runs"], B["goal_met"], B["runs"]), "d_speed": (A["final_speedup_median"], B["final_speedup_median"]),
        "d_cost": (A["cost_usd_total"], B["cost_usd_total"]), "d_tasks": len(d["tasks"]), "d_rep": d["repeats"],
        "ab_loop": (ab["off"]["agent_loop_s_median"], ab["on"]["agent_loop_s_median"]),
        "ab_speed": (ab["off"]["final_speedup_median"], ab["on"]["final_speedup_median"]),
        "ab_extra": ((ab["on"]["cost_usd_total"] or 0) - (ab["off"]["cost_usd_total"] or 0)) / max(1, ab["on"]["runs"]),
        "ab_goal": (ab["off"]["goal_met"], ab["off"]["runs"], ab["on"]["goal_met"], ab["on"]["runs"]),
    }


def img(name: str) -> str:
    return "data:image/png;base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


def qr_svg() -> str:
    buf = io.BytesIO()
    segno.make(REPO, error="m").save(buf, kind="svg", scale=1, border=0, dark="#141412", light=None, xmldecl=False, svgns=True, omitsize=True)
    return buf.getvalue().decode()


def cost_chart(n: dict, w: float = 700, h: float = 76) -> str:
    """Mean cumulative cloud cost along the stream, fresh vs memory; vector, sized in mm."""
    fresh, mem = n["s_mean"]["fresh"], n["s_mean"]["memory"]
    k = len(fresh)
    left, right, top, bottom = 42, 160, 8, 18
    hi = max(fresh) * 1.1
    x = lambda i: left + i * (w - left - right) / (k - 1)  # noqa: E731
    y = lambda v: top + (1 - v / hi) * (h - top - bottom)  # noqa: E731
    path = lambda vs: " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vs))  # noqa: E731
    ticks = "".join(f'<line x1="{left}" x2="{w - right}" y1="{y(t):.1f}" y2="{y(t):.1f}" class="g"/>'
                    f'<text x="{left - 4}" y="{y(t) + 3:.1f}" class="ax" text-anchor="end">${t:.2f}</text>' for t in (0, 0.05, 0.10))
    xs = "".join(f'<text x="{x(i):.1f}" y="{h - 6}" class="ax" text-anchor="middle">{i + 1}{"*" if n["s_first"][i] else ""}</text>' for i in range(k))
    dots = "".join(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" class="{c}"/>' for vs, c in ((fresh, "df"), (mem, "dm")) for i, v in enumerate(vs))
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}mm" height="{h}mm">{ticks}{xs}'
            f'<path d="{path(fresh)}" class="lf"/><path d="{path(mem)}" class="lm"/>{dots}'
            f'<text x="{x(k - 1) + 6:.1f}" y="{y(fresh[-1]) + 3:.1f}" class="lab f">不带经验 ${fresh[-1]:.3f}</text>'
            f'<text x="{x(k - 1) + 6:.1f}" y="{y(mem[-1]) + 3:.1f}" class="lab m">带经验 ${mem[-1]:.3f}</text></svg>')


def page(n: dict) -> str:
    e = html.escape
    s_large, s_cost, s_loop, s_goal, s_speed = n["s_large"], n["s_cost"], n["s_loop"], n["s_goal"], n["s_speed"]
    d_goal, d_speed, d_cost = n["d_goal"], n["d_speed"], n["d_cost"]
    ab_loop, ab_speed = n["ab_loop"], n["ab_speed"]
    ab_cut = round(100 * (1 - ab_loop[1] / ab_loop[0]))
    steps = ["规划", "取证", "假设", "实验", "验证", "修正", "交付"]
    chips = "".join(f'<div class="chip">{t}</div>' + ('<div class="arr">→</div>' if i < len(steps) - 1 else "") for i, t in enumerate(steps))
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>RouteEvo poster</title><style>
@page {{ size: 800mm 1800mm; margin: 0; }}
:root {{ --gap: 8mm; --tag: 43mm; --body: 17.5mm; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 800mm; height: 1800mm; }}
body {{ background: #F0E7DB; color: #141412; font-family: "PingFang SC", sans-serif; overflow: hidden;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ width: 800mm; height: 1800mm; display: flex; flex-direction: column; padding: 38mm 50mm 30mm; gap: var(--gap); }}
.kicker {{ font-size: 17mm; font-weight: 600; letter-spacing: 1.2mm; color: #E8452C; border-bottom: 1.2mm solid #141412; padding-bottom: 8mm; }}
.title {{ font-family: Georgia, serif; font-size: 146mm; line-height: 0.92; letter-spacing: -2mm; margin-left: -5mm; }}
.title em {{ color: #E8452C; }}
.top {{ display: grid; grid-template-columns: 1fr 250mm; gap: 16mm; align-items: center; }}
.tag p {{ font-size: var(--tag); font-weight: 600; line-height: 1.2; letter-spacing: -0.5mm; }}
.tag .cloud {{ color: #E8452C; }} .tag .loop {{ color: #1F6F5C; }}
.lede {{ font-size: var(--body); line-height: 1.55; color: #4A4843; margin-top: 10mm; }}
.hero {{ width: 250mm; display: block; }}
.hero, .reuse img, .trust img {{ -webkit-mask-image: radial-gradient(ellipse 72% 72% at 50% 50%, #000 78%, transparent 100%); mask-image: radial-gradient(ellipse 72% 72% at 50% 50%, #000 78%, transparent 100%); }}
.sh {{ display: flex; align-items: baseline; gap: 9mm; border-top: 1.2mm solid #141412; padding-top: 7mm; }}
.sh b {{ font-family: "DIN Alternate", sans-serif; font-size: 27mm; color: #E8452C; }}
.sh h2 {{ font-size: 33mm; font-weight: 600; letter-spacing: -0.4mm; }}
.lane {{ border-radius: 5mm; padding: 7mm 10mm; }}
.cloudlane {{ background: #FBE3DC; border: 0.8mm solid #E8452C; margin-top: 9mm; }}
.lane h3 {{ font-size: 18mm; font-weight: 600; }}
.cloudlane h3 {{ color: #B8301A; }}
.nodes {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 7mm; margin-top: 6mm; }}
.node {{ background: #FBF9F4; border-radius: 4mm; padding: 6mm 7mm; font-size: 14.5mm; line-height: 1.35; display: flex; gap: 4mm; }}
.node i {{ font-style: normal; font-family: "DIN Alternate", sans-serif; font-size: 19mm; color: #E8452C; line-height: 1; }}
.drops {{ display: flex; justify-content: space-around; padding: 0 60mm; color: #E8452C; font-size: 18mm; line-height: 1; height: 12mm; }}
.locallane {{ background: #1F6F5C; color: #F2EEE5; }}
.locallane h3 {{ color: #F2EEE5; }}
.row {{ display: flex; align-items: center; gap: 3mm; margin-top: 6mm; }}
.chip {{ background: #F2EEE5; color: #141412; border-radius: 3mm; padding: 3mm 0; font-size: 17mm; font-weight: 600; flex: 1; text-align: center; }}
.arr {{ font-size: 16mm; color: #BFD8CF; }}
.loopnote {{ font-size: 13.5mm; margin-top: 5mm; color: #D6E8E1; }}
.reuse {{ display: grid; grid-template-columns: 150mm 1fr; gap: 11mm; align-items: center; margin-top: 9mm; background: #FBF9F4;
  border: 0.8mm dashed #1F6F5C; border-radius: 5mm; padding: 6mm 10mm 6mm 6mm; }}
.reuse img {{ width: 150mm; display: block; }}
.reuse h3 {{ font-size: 19mm; font-weight: 600; color: #1F6F5C; }}
.reuse p {{ font-size: 14.5mm; line-height: 1.5; margin-top: 3mm; color: #4A4843; }}
.fine {{ font-size: 14mm; color: #807C72; margin-top: 7mm; }}
.dark {{ margin: 0 -50mm; background: #141412; color: #F2EEE5; padding: 10mm 50mm 10mm; }}
.dark .sh {{ border-top-color: #F2EEE5; }}
.tiles {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8mm 16mm; margin-top: 8mm; }}
.tile {{ border-top: 0.6mm solid #4A4843; padding-top: 5mm; }}
.tile .big {{ font-family: "DIN Alternate", sans-serif; font-size: 66mm; line-height: 0.95; letter-spacing: -1mm; }}
.tile .cap {{ font-size: 18mm; font-weight: 600; margin-top: 2mm; }}
.tile .sub {{ font-size: 13mm; line-height: 1.45; color: #B8B2A3; margin-top: 2mm; }}
.c-teal {{ color: #5FC7A4; }} .c-red {{ color: #FF6B4A; }}
.chart {{ margin-top: 8mm; }}
.chart .t {{ font-size: 13mm; color: #B8B2A3; margin-bottom: 2mm; }}
svg .g {{ stroke: #3A3833; stroke-width: 0.4; }}
svg .ax {{ fill: #A39E92; font-size: 9px; font-family: "DIN Alternate", sans-serif; }}
svg .lf {{ fill: none; stroke: #6FA8E8; stroke-width: 2.4; }}
svg .lm {{ fill: none; stroke: #FF6B4A; stroke-width: 2.4; }}
svg .df {{ fill: #6FA8E8; }} svg .dm {{ fill: #FF6B4A; }}
svg .lab {{ font-size: 11px; font-weight: 600; font-family: "PingFang SC", sans-serif; }} svg .lab.f {{ fill: #6FA8E8; }} svg .lab.m {{ fill: #FF6B4A; }}
.trust {{ display: grid; grid-template-columns: 185mm 1fr; gap: 14mm; align-items: center; margin-top: 8mm; }}
.trust img {{ width: 185mm; display: block; }}
.trust ul {{ list-style: none; display: grid; gap: 5mm; }}
.trust li {{ font-size: 15mm; line-height: 1.45; padding-left: 8mm; position: relative; }}
.trust li::before {{ content: ""; position: absolute; left: 0; top: 5.5mm; width: 3.5mm; height: 3.5mm; background: #E8452C; }}
.foot {{ margin-top: auto; display: grid; grid-template-columns: 1fr 58mm; gap: 14mm; align-items: end;
  border-top: 1.2mm solid #141412; padding-top: 9mm; }}
.foot .repo {{ font-family: "DIN Alternate", sans-serif; font-size: 19mm; }}
.foot p {{ font-size: 13mm; line-height: 1.5; color: #4A4843; margin-top: 2mm; }}
.foot svg {{ width: 58mm; height: 58mm; display: block; }}
</style></head><body>
<div class="page">
<div class="kicker">BOHACK 2026 · 倍漾量化 RESEARCH AGENT 赛道</div>
<div class="title">Route<em>Evo</em></div>
<div class="top"><div><div class="tag"><p>本地小模型干主力</p><p>只在关键节点</p><p>调用<span class="cloud">云端大模型</span></p><p class="loop">自主跑完研究闭环</p></div>
<div class="lede">给定研究问题、数据、工具、质量约束和预算，RouteEvo 自己规划、取证、提出假设、做实验、验证、修正，交付经过独立检验、可复现的研究成果；做过的研究沉淀为经验，同类问题直接复用。</div></div>
<img class="hero" src="{img('hero.png')}" alt=""></div>

<section>
  <div class="sh"><b>01</b><h2>什么时候才叫大模型</h2></div>
  <div class="lane cloudlane"><h3>云端大模型 GPT · 只在这些节点出手（程序规则，写进账本，模型不能自评）</h3>
    <div class="nodes">
      <div class="node"><i>①</i><span>本地小模型连续 2 个方案没达标</span></div>
      <div class="node"><i>②</i><span>本地小模型用了 3 次请求仍没有达标方案</span></div>
      <div class="node"><i>③</i><span>全新的问题：经验里没有同类、或没有条件相近的成功</span></div>
    </div>
  </div>
  <div class="drops"><span>↓</span><span>↓</span><span>↓</span></div>
  <div class="lane locallane"><h3>本地小模型 Qwen · 免费 · 干日常研究</h3>
    <div class="row">{chips}</div>
    <div class="loopnote">每个实验先写下假设、预期和验证方法；裁判程序给出判定，反馈决定下一步。</div>
  </div>
  <div class="reuse"><img src="{img('memory.png')}" alt=""><div><h3>熟悉的问题：一次模型都不调用</h3>
    <p>先由程序复验经验里条件最接近的已验证程序，达标就直接交付；全新的问题由大模型做对一次，结果在线写入经验，下一个同类问题直接复用。</p></div></div>
</section>

<section class="dark">
  <div class="sh"><b>02</b><h2>结果：用得少、跑得快、质量不降</h2></div>
  <div class="tiles">
    <div class="tile"><div class="big c-teal">{n['no_cloud_pct']}%</div><div class="cap">的运行全程没用云端大模型</div>
      <div class="sub">{n['runs']} 次真实运行中 {n['no_cloud']} 次；本地 Qwen 完成 {n['small_pct']}% 的模型请求（{n['small']} / {n['small'] + n['large']} 次）</div></div>
    <div class="tile"><div class="big c-red">−{n['s_large_cut']}%</div><div class="cap">云端大模型调用（有经验 vs 无经验）</div>
      <div class="sub">同一串 {n['s_tasks']} 道题 × {n['s_rep']} 次重放：{s_large[0]} → {s_large[1]} 次；费用 ${s_cost[0]:.3f} → ${s_cost[1]:.3f}；单次研究 {s_loop[0]:.0f} s → {s_loop[1]:.0f} s；达标 {s_goal[0]}/{s_goal[1]} → {s_goal[2]}/{s_goal[3]}</div></div>
    <div class="tile"><div class="big">{d_goal[2]}/{d_goal[3]}</div><div class="cap">封存新题全部达标</div>
      <div class="sub">学习时看不到的 {n['d_tasks']} 道题 × {n['d_rep']} 次：无经验 {d_goal[0]}/{d_goal[1]}；加速比中位数 {d_speed[0]:.2f}× → {d_speed[1]:.2f}×；云端费用 ${d_cost[0]:.3f} → ${d_cost[1]:.0f}</div></div>
    <div class="tile"><div class="big">−{ab_cut}%</div><div class="cap">新问题直接交大模型，研究更快</div>
      <div class="sub">对比先试本地小模型：单次研究 {ab_loop[0]:.0f} s → {ab_loop[1]:.0f} s，加速比 {ab_speed[0]:.2f}× → {ab_speed[1]:.2f}×，每题多花约 {n['ab_extra'] * 100:.1f} 美分</div></div>
  </div>
  <div class="chart"><div class="t">沿任务流累计的云端费用（3 次重放平均；* = 该类问题第一次出现）：只有新问题第一次出现时花钱</div>{cost_chart(n)}</div>
</section>

<section>
  <div class="sh"><b>03</b><h2>可信、可复现</h2></div>
  <div class="trust"><img src="{img('judge.png')}" alt=""><ul>
    <li>方案在断网、只读、1 CPU 的容器里运行；参考答案和最终测试数据不进容器</li>
    <li>5 轮交替计时全部快于基线才算改善；最佳方案冻结后，在隐藏数据上只验收一次</li>
    <li>每次调用记录 Token、费用和时间，未知记“未知”不记 0；经验有版本、可回退</li>
  </ul></div>
</section>

<div class="foot"><div><div class="repo">{e(REPO.removeprefix('https://'))}</div>
  <p>任务：分组聚合 · 访问日志统计 · 区间合并（另接入 ALE-Bench、AlgoTune 长任务基准）· 每次研究导出记录、最佳程序、原始模型调用与复现脚本</p></div>{qr_svg()}</div>
</div>
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "poster" / "RouteEvo-poster.pdf"))
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = numbers()
    src = out.with_suffix(".html")
    src.write_text(page(n))
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=5000",
                    f"--print-to-pdf={out}", src.as_uri()], check=True, capture_output=True)
    print(f"wrote {out} and {src}")


if __name__ == "__main__":
    main()
