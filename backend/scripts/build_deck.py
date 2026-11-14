"""Build the presentation deck from stored records (no hand-typed results).

    uv run --with python-pptx --with matplotlib python scripts/build_deck.py [--out ../docs/RouteEvo.pptx]

Charts follow the dashboard palette (validated with the dataviz validator on #fbf9f4): old snapshot #2a78d6,
new snapshot #eb6834. Every number on a slide is read from the SQLite store or a comparison summary.
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.ticker  # noqa: F401

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402
from pptx.util import Emu, Pt  # noqa: E402

from routeevo import compare, db, memory, narrative, report, research  # noqa: E402

PAPER, CARD, INK, INK2, INK3 = "F2EEE5", "FBF9F4", "141412", "4A4843", "807C72"
ACCENT, GOOD, BAD, OLD, NEW, RULE = "E8452C", "0A7A0A", "A12B2B", "2A78D6", "EB6834", "D9D2C2"
HEAD_FONT, BODY_FONT = "Songti SC", "PingFang SC"
W, H = Emu(12192000), Emu(6858000)  # 16:9

for path in ("/System/Library/Fonts/Hiragino Sans GB.ttc",):
    if Path(path).exists():
        font_manager.fontManager.addfont(path)
plt.rcParams["font.family"] = ["Hiragino Sans GB", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.blank = self.prs.slide_layouts[6]
        self.n = 0

    def slide(self, title: str | None = None, kicker: str | None = None):
        s = self.prs.slides.add_slide(self.blank)
        self.n += 1
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = rgb(PAPER)
        if title:
            if kicker:
                self.text(s, kicker, 0.6, 0.35, 10, 0.4, size=12, color=ACCENT, bold=True)
            self.text(s, title, 0.6, 0.62, 12, 0.9, size=30, font=HEAD_FONT, bold=True)
            line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(int(0.6 * 914400)), Emu(int(1.45 * 914400)), Emu(int(12.1 * 914400)), Emu(22860))
            line.fill.solid()
            line.fill.fore_color.rgb = rgb(INK)
            line.line.fill.background()
        self.text(s, f"RouteEvo · {self.n}", 11.6, 7.05, 1.6, 0.3, size=9, color=INK3, align=PP_ALIGN.RIGHT)
        return s

    @staticmethod
    def text(s, text: str, x: float, y: float, w: float, h: float, *, size: int = 16, color: str = INK, bold: bool = False,
             font: str = BODY_FONT, align=PP_ALIGN.LEFT, italic: bool = False):
        box = s.shapes.add_textbox(Emu(int(x * 914400)), Emu(int(y * 914400)), Emu(int(w * 914400)), Emu(int(h * 914400)))
        tf = box.text_frame
        tf.word_wrap = True
        for i, para in enumerate(text.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            r = p.add_run()
            r.text = para
            r.font.size, r.font.bold, r.font.italic, r.font.name = Pt(size), bold, italic, font
            r.font.color.rgb = rgb(color)
        return box

    def bullets(self, s, items: list[str], x: float, y: float, w: float, h: float, size: int = 17, color: str = INK):
        box = s.shapes.add_textbox(Emu(int(x * 914400)), Emu(int(y * 914400)), Emu(int(w * 914400)), Emu(int(h * 914400)))
        tf = box.text_frame
        tf.word_wrap = True
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(8)
            r = p.add_run()
            r.text = f"■  {item}" if not item.startswith("  ") else f"     {item.strip()}"
            r.font.size, r.font.name = Pt(size if not item.startswith("  ") else size - 3), BODY_FONT
            r.font.color.rgb = rgb(color if not item.startswith("  ") else INK2)
        return box

    def card(self, s, x: float, y: float, w: float, h: float, edge: str | None = None):
        c = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(int(x * 914400)), Emu(int(y * 914400)), Emu(int(w * 914400)), Emu(int(h * 914400)))
        c.fill.solid()
        c.fill.fore_color.rgb = rgb(CARD)
        c.line.color.rgb = rgb(RULE)
        c.shadow.inherit = False
        if edge:
            e = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(int(x * 914400)), Emu(int(y * 914400)), Emu(45720), Emu(int(h * 914400)))
            e.fill.solid()
            e.fill.fore_color.rgb = rgb(edge)
            e.line.fill.background()
        return c

    def stat(self, s, k: str, v: str, x: float, y: float, w: float = 2.8, sub: str | None = None, color: str = INK):
        self.text(s, k, x, y, w, 0.35, size=12, color=INK3)
        self.text(s, v, x, y + 0.3, w, 0.7, size=30, bold=True, color=color)
        if sub:
            self.text(s, sub, x, y + 0.98, w, 0.5, size=11, color=INK3)

    def table(self, s, rows: list[list[str]], x: float, y: float, w: float, col_w: list[float] | None = None, size: int = 12):
        shape = s.shapes.add_table(len(rows), len(rows[0]), Emu(int(x * 914400)), Emu(int(y * 914400)), Emu(int(w * 914400)), Emu(int(0.36 * 914400 * len(rows))))
        tbl = shape.table
        if col_w:
            for i, cw in enumerate(col_w):
                tbl.columns[i].width = Emu(int(cw * 914400))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                cell = tbl.cell(r, c)
                cell.fill.solid()
                cell.fill.fore_color.rgb = rgb(INK if r == 0 else (CARD if r % 2 else PAPER))
                tf = cell.text_frame
                tf.paragraphs[0].text = ""
                run = tf.paragraphs[0].add_run()
                run.text = val
                run.font.size, run.font.name = Pt(size), BODY_FONT
                run.font.bold = r == 0
                run.font.color.rgb = rgb(PAPER if r == 0 else INK)
        return shape

    def image(self, s, path: Path, x: float, y: float, w: float):
        s.shapes.add_picture(str(path), Emu(int(x * 914400)), Emu(int(y * 914400)), width=Emu(int(w * 914400)))


# ---------- data ----------

V1_LEARN, V2_LEARN = ("formal A learning",), ("reuse A learning r1", "reuse A learning r2")


def learn_rows(labels=V1_LEARN) -> list[dict]:
    q = ",".join("?" * len(labels))
    sql = (f"SELECT run_id FROM runs WHERE mode = 'learn' AND status != 'running' AND json_extract(config_json, '$.label') IN ({q})"
           " ORDER BY started_at")
    return [report.build(r["run_id"]) for r in db.all_rows(sql, tuple(labels))]


def learned_snapshot(labels=V2_LEARN) -> str:
    """The snapshot published by the last formal learning run (a later demo session may publish a newer branch)."""
    q = ",".join("?" * len(labels))
    row = db.one("SELECT published_snapshot_id FROM runs WHERE mode = 'learn' AND published_snapshot_id IS NOT NULL"
                 f" AND json_extract(config_json, '$.label') IN ({q}) ORDER BY started_at DESC LIMIT 1", tuple(labels))
    return row["published_snapshot_id"] if row else "v0"


def path_of(rep: dict) -> str:
    """Q/G per model request in order, plus R per re-validated program, e.g. 'RRR' or 'QQGG'."""
    up = rep["iterations"]["upgrade_at_step"]
    out = []
    for st in rep["steps"]:
        if st["action"] == "reuse_candidate":
            out.append("R")
        elif st["actor"] == "model":
            out.append("G" if up and st["seq"] > up else "Q")
    return "".join(out) or "—"


def retyped_program() -> tuple[dict, dict] | None:
    """Version 1 evidence: a model candidate whose program equals one an earlier learning run had already verified."""
    seen: dict[str, tuple[str, str]] = {}
    for r in db.all_rows("SELECT c.run_id, c.candidate_id, c.code_path, r.task_id FROM candidates c JOIN runs r USING (run_id)"
                         " WHERE r.mode = 'learn' AND json_extract(r.config_json, '$.label') = 'formal A learning' AND c.origin = 'model'"
                         " ORDER BY r.started_at, c.seq"):
        code = memory.normalized_code(Path(r["code_path"]).read_text())
        if code in seen and seen[code][0] != r["task_id"]:
            return ({"task_id": seen[code][0], "candidate_id": seen[code][1]}, {"task_id": r["task_id"], "candidate_id": r["candidate_id"], "run_id": r["run_id"]})
        seen.setdefault(code, (r["task_id"], r["candidate_id"]))
    return None


def g(v) -> str:
    return "—" if v is None else f"{v:g}"


def gpt_split(c: dict) -> dict:
    """Final speedups of goal-met runs, split by whether the run upgraded to GPT (both snapshots pooled)."""
    out = {"gpt": [], "qwen": []}
    for t in c["tasks"]:
        for s in (c["snapshot_a"], c["snapshot_b"]):
            for r in c["per_task"][t][s]["runs"]:
                if r["goal_met"] and r["final_speedup"] is not None:
                    up = report.build(r["run_id"])["iterations"]["upgrades"]
                    out["gpt" if up else "qwen"].append(r["final_speedup"])
    return out


def find_comparison(prefix: str, exact: bool = False) -> dict | None:
    for r in db.all_rows("SELECT comparison_id, label FROM comparisons WHERE status != 'running' ORDER BY created_at DESC"):
        label = r["label"] or ""
        if label == prefix if exact else label.startswith(prefix):
            return compare.summarize(r["comparison_id"])
    return None


def ratchet_chart(rounds: list[tuple[str, list[dict]]], out: Path) -> Path:
    """Final speedup per A task after each learning round (hollow = goal not met)."""
    tasks = sorted({r["task"]["task_id"] for _, reps in rounds for r in reps})
    fig, ax = plt.subplots(figsize=(7.6, 0.55 * len(tasks) + 1.6), dpi=200)
    fig.patch.set_facecolor("#" + CARD)
    ax.set_facecolor("#" + CARD)
    cols = ["#" + INK3, "#" + NEW, "#" + OLD]
    h = 0.8 / max(1, len(rounds))
    for k, (name, reps) in enumerate(rounds):
        by = {r["task"]["task_id"]: r for r in reps}
        for i, t in enumerate(tasks):
            r = by.get(t)
            if not r:
                continue
            v = r["outcome"]["final_speedup"] or 1.0
            y = len(tasks) - 1 - i + 0.4 - h * (k + 0.5)
            met = r["outcome"]["goal_met"]
            ax.barh(y, v - 0.0, height=h * 0.85, left=0, color=cols[k] if met else "#" + CARD, edgecolor=cols[k], linewidth=1.5)
            ax.text(v + 0.02, y, f"{v:.2f}×" + ("" if met else " ✕"), va="center", fontsize=9, color="#" + INK2)
    ax.axvline(1.1, color="#" + ACCENT, lw=1.3)
    ax.axvline(1.0, color="#" + RULE, lw=1)
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels(list(reversed(tasks)), fontsize=11)
    xs = [r["outcome"]["final_speedup"] or 1 for _, reps in rounds for r in reps]
    ax.set_xlim(0.6, max(1.8, max(xs) + 0.25))
    ax.grid(axis="x", color="#" + RULE, lw=0.6)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#" + RULE)
    ax.tick_params(colors="#" + INK2, length=0)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=cols[k], label=name) for k, (name, _) in enumerate(rounds)] +
              [Patch(facecolor="#" + CARD, edgecolor="#" + INK3, label="空心 / ✕ = 最终测试未达标")],
              loc="upper left", frameon=False, fontsize=9.5, ncol=3, bbox_to_anchor=(0, -0.08))
    ax.set_title("每轮学习后各任务的最终加速比（隐藏最终数据）", loc="left", fontsize=12, color="#" + INK, pad=10)
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def dots_chart(c: dict, out: Path, title: str) -> Path:
    a, b = c["snapshot_a"], c["snapshot_b"]
    tasks = c["tasks"]
    fig, ax = plt.subplots(figsize=(10, 0.62 * len(tasks) + 1.7), dpi=200)
    fig.patch.set_facecolor("#" + CARD)
    ax.set_facecolor("#" + CARD)
    speeds = [r["final_speedup"] for t in tasks for s in (a, b) for r in c["per_task"][t][s]["runs"] if r["final_speedup"]]
    lo, hi = min([0.6] + [v - 0.05 for v in speeds]), max([1.8] + [v + 0.05 for v in speeds])
    fail_x = lo - (hi - lo) * 0.12
    for i, t in enumerate(tasks):
        y = len(tasks) - 1 - i
        for si, (s, col) in enumerate(((a, "#" + OLD), (b, "#" + NEW))):
            runs = c["per_task"][t][s]["runs"]
            for k, r in enumerate(runs):
                x = r["final_speedup"] if r["final_speedup"] is not None else fail_x + k * (hi - lo) * 0.025
                yy = y + (0.14 if si == 0 else -0.14)
                ax.scatter([x], [yy], s=70, color=col if r["goal_met"] else "#" + CARD, edgecolors=col, linewidths=2, zorder=3)
    ax.axvline(1.1, color="#" + ACCENT, lw=1.5, zorder=1)
    ax.text(1.1, len(tasks) - 0.35, " 目标 1.10×", color="#" + ACCENT, fontsize=10, va="bottom")
    ax.axvline(lo - (hi - lo) * 0.03, color="#" + RULE, lw=1)
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels(list(reversed(tasks)), fontsize=11)
    ax.set_xlim(fail_x - (hi - lo) * 0.05, hi)
    ticks = [round(lo + k * 0.25, 2) for k in range(int((hi - lo) / 0.25) + 2) if lo + k * 0.25 <= hi]
    ax.set_xticks([fail_x + (hi - lo) * 0.025] + ticks)
    ax.set_xticklabels(["未计时"] + [f"{t:.2f}×" for t in ticks], fontsize=10)
    ax.grid(axis="x", color="#" + RULE, lw=0.8)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#" + RULE)
    ax.tick_params(colors="#" + INK2, length=0)
    ax.set_title(title, loc="left", fontsize=13, color="#" + INK, pad=12)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", ls="", color="#" + OLD, markersize=8, label=f"{a}（{'无经验' if a == 'v0' else '旧经验'}）"),
               Line2D([], [], marker="o", ls="", color="#" + NEW, markersize=8, label=f"{b}（新经验）"),
               Line2D([], [], marker="o", ls="", markerfacecolor="#" + CARD, markeredgecolor="#" + INK3, markersize=8, label="空心 = 未达标")]
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=10, ncol=3, bbox_to_anchor=(0, -0.09))
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


FAM_LETTER = {"groupagg": "G", "logstats": "L", "intervals": "I"}
FAM_ZH = {"groupagg": "分组聚合", "logstats": "访问日志", "intervals": "区间合并"}


def stream_chart(st: dict, out: Path, metric: str = "cost_usd") -> Path:
    """Cumulative large-model cost along the S stream: one thin line per repeat and arm; dots where GPT was used."""
    pos = st["positions"]
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=200)
    fig.patch.set_facecolor("#" + CARD)
    ax.set_facecolor("#" + CARD)
    xs = list(range(1, len(pos) + 1))
    for arm, col, name in (("fresh", "#" + OLD, "不带记忆（每个任务都从起点出发）"), ("memory", "#" + NEW, "带记忆（在线写入，下一个任务读取）")):
        for rep in range(1, st["repeats"] + 1):
            ser = st["series"][arm].get(str(rep))
            if not ser or not ser[metric]:
                continue
            ys = ser[metric]
            ax.plot(xs[:len(ys)], ys, color=col, lw=1.8, alpha=0.85, label=name if rep == 1 else None)
            used = [i for i in range(len(ys)) if ser["large_model_requests"][i] > (ser["large_model_requests"][i - 1] if i else 0)]
            ax.scatter([xs[i] for i in used], [ys[i] for i in used], s=28, color=col, zorder=3, edgecolors="#" + CARD, linewidths=1)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{p['task_id'].replace('S-', '')}\n{FAM_LETTER.get(p['family'], '?')}{'*' if p['first_of_family'] else ''}" for p in pos], fontsize=9.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:.2f}" if metric == "cost_usd" else f"{v:.0f}"))
    ax.grid(axis="y", color="#" + RULE, lw=0.7)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#" + RULE)
    ax.tick_params(colors="#" + INK2, length=0)
    ax.set_title("沿任务流累计的大模型费用（每条线是一次重放；圆点 = 该任务用了大模型）", loc="left", fontsize=12, color="#" + INK, pad=10)
    ax.text(0, -0.25, "G 分组聚合 · L 访问日志 · I 区间合并 · * 该任务族在任务流中首次出现", transform=ax.transAxes, fontsize=9, color="#" + INK3)
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def ablation_sides() -> dict | None:
    out = {}
    for arm in ("on", "off"):
        ids = [r["run_id"] for r in db.all_rows("SELECT run_id FROM runs WHERE json_extract(config_json, '$.label') = ? AND status != 'running'"
                                                " ORDER BY started_at", (f"router ablation · {arm}",))]
        if not ids:
            return None
        reps = [report.build(i) for i in ids]
        out[arm] = {**compare._side(reps), "small": sum(r["iterations"].get("small_model_requests", 0) for r in reps)}
    return out


def side_rows(c: dict) -> list[list[str]]:
    a, b = c["snapshot_a"], c["snapshot_b"]
    A, B = c["sides"][a], c["sides"][b]
    usd = lambda v: "未知" if v is None else f"${v:.3f}"  # noqa: E731
    x = lambda v: "—" if v is None else f"{v:.2f}×"  # noqa: E731
    n = lambda v: "—" if v is None else f"{v:,}"  # noqa: E731
    return [
        ["指标", f"{a}（{'无经验' if a == 'v0' else '旧经验'}）", f"{b}（新经验）"],
        ["达标 / 运行", f"{A['goal_met']} / {A['runs']}", f"{B['goal_met']} / {B['runs']}"],
        ["最终加速比中位数", x(A["final_speedup_median"]), x(B["final_speedup_median"])],
        ["模型请求中位数", g(A["model_requests_median"]), g(B["model_requests_median"])],
        *([["未调用模型的运行", str(A.get("runs_without_model_request", 0)), str(B.get("runs_without_model_request", 0))]]
          if "runs_without_model_request" in B and B.get("programs_reused_total") else []),
        ["升级到 GPT 次数", str(A["upgrades_total"]), str(B["upgrades_total"])],
        ["失败候选", str(A["candidates_failed_total"]), str(B["candidates_failed_total"])],
        ["输出 Token 合计", n(A["output_tokens"]["total"]), n(B["output_tokens"]["total"])],
        ["模型费用合计", usd(A["cost_usd_total"]), usd(B["cost_usd_total"])],
        ["总耗时 / 循环中位数", f"{A['wall_clock_s_total']:.0f}s / {A['agent_loop_s_median']:.0f}s", f"{B['wall_clock_s_total']:.0f}s / {B['agent_loop_s_median']:.0f}s"],
    ]


# ---------- slides ----------

def build(out: Path, shots: Path) -> None:
    d = Deck()
    charts = out.parent / "deck"
    charts.mkdir(parents=True, exist_ok=True)
    learn1 = learn_rows(V1_LEARN)
    learn2 = learn_rows(V2_LEARN)
    v1_b, v1_c = find_comparison("B dev comparison", exact=True), find_comparison("C final held-out", exact=True)
    cmp_b, cmp_d = find_comparison("B dev comparison · reuse"), find_comparison("D final held-out · reuse")
    final_snap = learned_snapshot(V2_LEARN) if learn2 else learned_snapshot(V1_LEARN)
    snap = memory.snapshot(final_snap)
    headline = cmp_d if cmp_d and cmp_d["finished_runs"] else cmp_b
    x = lambda v: "—" if v is None else f"{v:.2f}×"  # noqa: E731
    usd = lambda v: "未知" if v is None else f"${v:.3f}"  # noqa: E731

    # 1 cover
    s = d.slide()
    s.background.fill.fore_color.rgb = rgb(INK)
    box = d.text(s, "Route", 0.9, 2.0, 8, 1.4, size=80, color=PAPER, font="Georgia")
    evo = box.text_frame.paragraphs[0].add_run()
    evo.text = "Evo"
    evo.font.size, evo.font.italic, evo.font.name = Pt(80), True, "Georgia"
    evo.font.color.rgb = rgb(ACCENT)
    d.text(s, "把已验证的研究成果，变成下一次研究的起点", 0.95, 3.5, 11.5, 0.7, size=28, color=PAPER, font=HEAD_FONT, bold=True)
    d.text(s, "取证 → 假设 → 实验 → 验证 → 修正 → 已验证成果入库 → 熟悉的复用，全新的交给大模型，做完都记下来", 0.95, 4.3, 11.5, 0.5, size=16, color="B8B2A3")
    st0 = find_comparison("S online stream")
    if st0 and st0["finished_runs"]:
        F0, M0 = st0["sides"]["fresh"], st0["sides"]["memory"]
        d.text(s, (f"S 任务流（3 个任务族）不带 → 带记忆：GPT 请求 {F0['large_model_requests_total']} → {M0['large_model_requests_total']} · "
                   f"费用 {usd(F0['cost_usd_total'])} → {usd(M0['cost_usd_total'])} · 循环时长中位数 {F0['agent_loop_s_median']:.0f}s → {M0['agent_loop_s_median']:.0f}s · "
                   f"达标 {F0['goal_met']}/{F0['runs']} → {M0['goal_met']}/{M0['runs']}"),
               0.95, 4.85, 11.8, 0.45, size=14, color=PAPER)
    if headline and headline["finished_runs"]:
        A, B = headline["sides"][headline["snapshot_a"]], headline["sides"][headline["snapshot_b"]]
        d.text(s, (f"{'D 封存留出（分组聚合）' if headline is cmp_d else 'B 开发对照'}：最终加速比中位数 {x(A['final_speedup_median'])} → {x(B['final_speedup_median'])} · "
                   f"模型请求中位数 {g(A['model_requests_median'])} → {g(B['model_requests_median'])} · GPT 费用 {usd(A['cost_usd_total'])} → {usd(B['cost_usd_total'])} · "
                   f"循环时长中位数 {A['agent_loop_s_median']:.0f}s → {B['agent_loop_s_median']:.0f}s"),
               0.95, 5.35, 11.8, 0.45, size=14, color=PAPER)
    d.text(s, "BoHack 2026 · 倍漾量化 Research Agent 赛道", 0.95, 6.3, 8, 0.4, size=12, color="9A9485")

    # 2 questions
    s = d.slide("我们要回答的两个问题", "问题定义")
    d.card(s, 0.6, 1.8, 5.9, 2.6, ACCENT)
    d.text(s, "① 研究闭环能否成立", 0.9, 2.0, 5.4, 0.5, size=20, bold=True, font=HEAD_FONT)
    d.text(s, "在预算内完成“取证—假设—实验—验证—修正”：每个实验有事前假设，判定来自独立评测，反馈改变下一步；交付可复现的成果。", 0.9, 2.6, 5.4, 1.6, size=15, color=INK2)
    d.card(s, 6.8, 1.8, 5.9, 2.6, ACCENT)
    d.text(s, "② 系统能否自我改进", 7.1, 2.0, 5.4, 0.5, size=20, bold=True, font=HEAD_FONT)
    d.text(s, "同样的模型、提示词、预算和评测，只换经验快照：在没参与学习的任务上，是否更快、更省、结果更好？", 7.1, 2.6, 5.4, 1.6, size=15, color=INK2)
    d.bullets(s, ["学习发生在系统层：不训练模型、不改提示词，程序把经过评测的执行事实与程序写成不可变的经验快照",
                  "结论只来自留出任务上的对照数据，全部运行（包括失败与无收益）都计入"], 0.6, 4.8, 12, 2, size=16)

    # 3 task
    n_tasks = db.one("SELECT COUNT(*) AS n FROM tasks WHERE task_id NOT LIKE 't-%'")["n"]
    s = d.slide("研究任务：在正确性约束下优化程序（3 个任务族）", "研究任务")
    d.bullets(s, ["分组聚合：按字符串 key 分组 CSV，输出每组数量与整数和（csv + dict + sorted）",
                  "访问日志统计：按小时 × 接口统计请求数、5xx 数、延迟和与最大值（正则 + strptime）",
                  "区间合并：合并重叠或相接的闭区间，取值跨 ±10¹²（csv + 元组排序）",
                  "  初始程序都正确、正常，不人为削弱；每族 7 个公开契约用例挡住只对当前数据正确的程序",
                  "主指标：加速比 = 初始程序耗时中位数 / 候选耗时中位数；达标：输出全对 + 5 次候选样本全部快于基线 + ≥ 1.10",
                  f"{n_tasks} 个冻结任务包（哈希锁定）：分组聚合 A/B/C/D 各 6 · 新任务族调优 T 4 · 封存任务流 S 12（混合 3 族）· smoke"], 0.6, 1.75, 7.2, 5, size=15)
    d.card(s, 8.1, 1.8, 4.6, 4.6)
    d.text(s, "同一个优化，效果相反", 8.35, 1.95, 4.2, 0.4, size=14, bold=True, color=ACCENT)
    d.text(s, "按字节解析 + 单字典：\n  中等基数（A-01）≈ 1.44×\n  高基数（A-05）≈ 0.82×\n\n带有序检查的 groupby：\n  所有 A 任务 ≈ 0.7×\n\n只用 groupby 不检查：\n  有序数据上正确，\n  但违反契约用例 → 判失败", 8.35, 2.45, 4.2, 3.9, size=14, color=INK2)

    # 4 loop
    s = d.slide("研究循环：先复验已知成果，再分流给合适的模型", "架构")
    steps = [("复验已知成果", "经验中条件最接近的\n已验证程序 ≤ 3 个\n不调用模型"), ("分流 · 模型选行动", "相近 → Qwen；全新 → GPT\n分析 · 取证 · 提出候选\n验证 · 结束"),
             ("程序检查", "动作参数 · 预算\n仅标准库 · 代码大小"), ("沙箱 + 评测器", "正确性 · 契约用例\n交替计时 · 最佳产物"),
             ("反馈", "状态 · 加速比 · 反例\n→ 下一步")]
    for i, (k, v) in enumerate(steps):
        xx = 0.6 + i * 2.5
        d.card(s, xx, 2.0, 2.2, 1.8, ACCENT if i in (0, 1) else None)
        d.text(s, k, xx + 0.2, 2.15, 1.9, 0.45, size=16, bold=True, font=HEAD_FONT)
        d.text(s, v, xx + 0.2, 2.65, 1.9, 1.1, size=11.5, color=INK2)
        if i < 4:
            d.text(s, "→", xx + 2.2, 2.6, 0.3, 0.5, size=20, color=ACCENT, bold=True)
    d.bullets(s, ["评测运行：复验已达标就交付，不调用模型；没达标，复验结果作为证据交给模型。学习运行：复验已达标时把本次目标提高到超过已知最佳 5%",
                  "分流（第三版）：有相近成功经验 → 本地 Qwen（qwen3.8:27b）先做，连续未达标按规则升级到 GPT-6.1 Sol（xhigh）；全新任务族或新条件 → 直接交给 GPT",
                  "每次运行最多 6 次模型请求、4 个模型候选、300 秒（复验也计时）；预算耗尽后不再为总结调用模型"], 0.6, 4.2, 12.1, 2.7, size=15)

    # 5 trust
    s = d.slide("可信的验证：模型碰不到裁判", "验证")
    d.bullets(s, ["每个样本一个全新容器：禁网、只读根文件系统、非 root、1 CPU / 1 GB、64 进程；只挂载候选文件，输入走 stdin",
                  "参考输出、最终测试数据、评测程序都留在宿主机；候选自报的“通过”或“耗时”不算数",
                  "每个任务族 7 个公开契约用例：分组聚合（交错重复 key、ASCII 排序、几乎有序陷阱…）、访问日志（跨小时与跨日、乱序、状态码 499/500）、区间合并（相接与间隔 1、嵌套传递、±10¹²）",
                  "计时：容器内启动器就绪后才开始；基线与候选各预热一次，交替 5 轮，取中位数之比",
                  "“改善”= 全部候选样本快于全部基线样本（单侧 Mann-Whitney U=0，p≈0.004）；同一程序靠噪声测出 1.05× 也不算",
                  "复用的程序和模型候选走同一个评测器；循环结束后最佳候选冻结，在隐藏最终数据上测一次，结果不回流"], 0.6, 1.75, 12.1, 5, size=16)

    # 6 one real research chain (version 1, no experience): hypothesis → measurement → program verdict
    first = learn1[0] if learn1 else None
    if first:
        s = d.slide(f"一条真实的研究链：{first['task']['task_id']}（无经验 v0）", "反馈驱动")
        up = first["iterations"]["upgrade_at_step"]
        labels = first["research"]["verdict_labels"]
        rows = [["候选", "执行者", "事前假设", "实测", "判定"]]
        for e in first["research"]["experiments"]:
            res = e["result"]
            rows.append([e["candidate_id"], "GPT" if up and e["step"] > up else "Qwen", (e["hypothesis"] or e["purpose"] or "")[:64] + "…",
                         (res["status"] or "—") + (f" · {res['speedup']:.2f}×" if res["speedup"] is not None else ""),
                         labels[e["verdict"]].split("（")[0]])
        d.table(s, rows, 0.6, 1.8, 7.6, [0.6, 0.8, 3.9, 1.3, 1.0], size=11)
        d.card(s, 8.5, 1.8, 4.2, 4.7, ACCENT)
        d.text(s, "反馈如何改变下一步", 8.75, 1.95, 3.8, 0.4, size=15, bold=True, color=ACCENT)
        d.text(s, ("c1 实测 0.90×，假设被反驳 → Qwen 写下“c1 慢是因为 bytes key”，改用 str key，但输出格式错误。\n\n"
                   "连续两次未达标 → 程序按固定规则升级到 GPT。\n\n"
                   "GPT 读到表头错误与 c1 的慢因，提出批量分行 + 单字典：1.45×，假设得到支持，达标后停止。\n\n"
                   f"冻结 c3，隐藏最终数据上测一次：{first['outcome']['final_speedup']:.2f}×。"
                   f"{first['iterations']['model_requests']} 次请求 · ${first['usage']['total']['cost_usd'] or 0:.3f}"),
               8.75, 2.4, 3.8, 4, size=12.5, color=INK2)
        d.text(s, "判定由程序依据评测给出：改善且达标 = 支持；正确但没有改善 = 反驳；候选出错 = 未能检验。模型不能自评。",
               0.6, 6.3, 7.6, 0.5, size=11, color=INK3)

    # 7 version 1 finding: cheaper, but stopping at a smaller speedup
    if v1_c and v1_c["finished_runs"]:
        a, b = v1_c["snapshot_a"], v1_c["snapshot_b"]
        A, B = v1_c["sides"][a], v1_c["sides"][b]
        s = d.slide("第一版的发现：更省了，但停在更低的加速比", "第一版 · 只有文字经验")
        rows = [["任务", f"{a} 加速比", f"{b} 加速比", f"{a} 请求", f"{b} 请求"]]
        for t in v1_c["tasks"]:
            cells = []
            for sn in (a, b):
                runs = v1_c["per_task"][t][sn]["runs"]
                cells.append(" ".join(("—" if r["final_speedup"] is None else f"{r['final_speedup']:.2f}") + ("" if r["goal_met"] else "✕") for r in runs))
            rows.append([t, *cells, *(" ".join(str(r["model_requests"]) for r in v1_c["per_task"][t][sn]["runs"]) for sn in (a, b))])
        d.table(s, rows, 0.6, 1.8, 7.4, [0.9, 2.0, 2.0, 1.25, 1.25], size=12)
        split = gpt_split(v1_c)
        med = lambda v: f"{statistics.median(v):.2f}×" if v else "—"  # noqa: E731
        d.card(s, 8.3, 1.8, 4.4, 4.7, ACCENT)
        d.text(s, f"C 最终留出（{a} → {b}）", 8.55, 1.95, 4, 0.4, size=15, bold=True, color=ACCENT)
        d.text(s, (f"达标 {A['goal_met']}/{A['runs']} → {B['goal_met']}/{B['runs']}\n请求中位数 {g(A['model_requests_median'])} → {g(B['model_requests_median'])}"
                   f" · 升级 {A['upgrades_total']} → {B['upgrades_total']}\nGPT 费用 {usd(A['cost_usd_total'])} → {usd(B['cost_usd_total'])}\n"
                   f"最终加速比中位数 {x(A['final_speedup_median'])} → {x(B['final_speedup_median'])}\n\n"
                   f"达标运行里，用过 GPT 的中位数 {med(split['gpt'])}，只用 Qwen 的 {med(split['qwen'])}。"
                   f"有经验后 Qwen 一次达标就停，GPT 找到的更快方案用不上。"),
               8.55, 2.4, 4, 4, size=12.5, color=INK2)
        d.text(s, "✕ = 未达标；— = 没有计时结果。这批数字来自第一版配置（经验只有文字记录与 diff），是第二版修改的依据。", 0.6, 6.3, 7.4, 0.5, size=11, color=INK3)

    # 8 diagnosis → change (the system's own research loop)
    s = d.slide("对系统本身做研究：诊断 → 修改 → 封存验收", "第二版")
    rt = retyped_program()
    cause1 = ("经验里已有完整的好程序，模型却要花一次请求把它重新写一遍"
              + (f"：第一版学习中，{rt[1]['task_id']} 的 Qwen 候选 {rt[1]['candidate_id']} 与 {rt[0]['task_id']} 的 {rt[0]['candidate_id']} 去掉空白后逐字相同。" if rt else "。"))
    cols3 = [("发现（第一版 C）", "有经验后请求、升级、费用都下降，达标率不变，最终加速比中位数却下降。"),
             ("原因", f"① {cause1}\n② 达标即停：Qwen 写出约 1.27× 就停止，GPT 找到的约 1.5× 方案不会被再次使用。"),
             ("修改（第二版）", "① 经验保存完整程序；新任务首次请求前，由程序复验条件最接近的 ≤ 3 个已验证程序，评测运行达标即交付。\n"
                              "② 学习运行复验达标时，把目标提高到超过已知最佳 5%，模型只做“超越”。\n"
                              "③ 复验结果也写成经验：哪些程序在哪些条件下成立。")]
    for i, (k, v) in enumerate(cols3):
        xx = 0.6 + i * 4.1
        d.card(s, xx, 1.8, 3.85, 3.9, ACCENT if i == 2 else None)
        d.text(s, k, xx + 0.25, 1.95, 3.4, 0.45, size=17, bold=True, font=HEAD_FONT)
        d.text(s, v, xx + 0.25, 2.5, 3.4, 3.1, size=12.5, color=INK2)
    d.text(s, ("公平性：修改改变了配置指纹，所以第二版重新学习、重新对照（v0 与学习后的快照用同一配置）。"
               "第一版 C 的结果是修改的依据，不能再当留出集；为此在实现第二版之前新建并封存了 D 批 6 个任务（提交 d542906），只在 B 上定型后运行一次。"),
           0.6, 5.95, 12.1, 0.9, size=12.5, color=INK2)

    # 9 version 2 research chain: re-use → raised target → beat the known best
    # the learning run that moved furthest beyond the best re-used program (same rule as scripts/export_research.py)
    def gain(r):
        raised = next((st for st in r["steps"] if st["action"] == "set_target"), None)
        won = [e["result"]["speedup"] for e in r["research"]["experiments"] if e["kind"] == "model" and e["verdict"] == "supported"]
        return max(won) - raised["result"]["best_dev_speedup"] if raised and won else 0.0
    chain = max(learn2, key=gain) if learn2 and max(map(gain, learn2)) > 0 else None
    if chain:
        s = d.slide(f"站在已知最佳上继续研究：{chain['task']['task_id']}（读取 {chain['snapshot_id']}）", "第二版 · 研究链")
        up = chain["iterations"]["upgrade_at_step"]
        labels = chain["research"]["verdict_labels"]
        rows = [["候选", "执行者", "事前假设", "实测", "判定（当时目标）"]]
        for e in chain["research"]["experiments"]:
            res = e["result"]
            who = "程序复用" if e["kind"] == "reuse" else ("GPT" if up and e["step"] > up else "Qwen")
            rows.append([e["candidate_id"], who, (e["hypothesis"] or e["purpose"] or "")[:62] + "…",
                         (res["status"] or "—") + (f" · {res['speedup']:.2f}×" if res["speedup"] is not None else ""),
                         f"{labels[e['verdict']].split('（')[0]}（{e['target']:g}×）"])
        d.table(s, rows, 0.6, 1.8, 7.8, [0.6, 1.0, 3.7, 1.3, 1.2], size=11)
        raised = next(st for st in chain["steps"] if st["action"] == "set_target")
        d.card(s, 8.6, 1.8, 4.1, 4.7, ACCENT)
        d.text(s, "发生了什么", 8.85, 1.95, 3.7, 0.4, size=15, bold=True, color=ACCENT)
        reuse = [e for e in chain["research"]["experiments"] if e["kind"] == "reuse"]
        d.text(s, (f"程序先复验 {len(reuse)} 个已验证程序，没有调用模型；最好的 {raised['result']['best_candidate_id']} 在本任务上 "
                   f"{raised['result']['best_dev_speedup']:.2f}×，已达标。\n\n"
                   f"学习运行据此把目标提高到 {raised['result']['run_target_speedup']:g}×，模型以它为父候选改进。\n\n"
                   f"最终：{chain['outcome']['summary']}；{chain['iterations']['model_requests']} 次请求 · "
                   f"${chain['usage']['total']['cost_usd'] or 0:.3f} · 发布 {chain['experience']['published_snapshot_id'] or '—'}，"
                   "下一个任务从这个更快的程序起步。"), 8.85, 2.4, 3.7, 4, size=12.5, color=INK2)

    # 10 research statistics over every formal run
    groups = [("第二版 · A 学习", [r["run_id"] for r in learn2])] if learn2 else []
    for c, key in ((cmp_b, "第二版 · B"), (cmp_d, "第二版 · D")):
        if c and c["finished_runs"]:
            for side in (c["snapshot_a"], c["snapshot_b"]):
                groups.append((f"{key} · {side}", [r["run_id"] for t in c["tasks"] for r in c["per_task"][t][side]["runs"]]))
    groups.append(("第一版 · A 学习", [r["run_id"] for r in learn1]))
    for c, key in ((v1_b, "第一版 · B"), (v1_c, "第一版 · C")):
        if c and c["finished_runs"]:
            for side in (c["snapshot_a"], c["snapshot_b"]):
                groups.append((f"{key} · {side}", [r["run_id"] for t in c["tasks"] for r in c["per_task"][t][side]["runs"]]))
    aggs = [(name, research.aggregate([report.build(i) for i in ids])) for name, ids in groups if ids]
    keys = ("runs", "experiments", "reuse_experiments", "reuse_supported", "supported", "partial", "refuted", "untestable", "follow_ups", "follow_ups_citing_prior")
    rtotal = {k: sum(a[k] for _, a in aggs) for k in keys}
    s = d.slide(f"研究过程统计：{rtotal['runs']} 次运行、{rtotal['experiments']} 个实验，全部如实判定", "研究过程")
    rows = [["批次 · 快照", "运行", "实验", "其中复用", "支持", "部分", "反驳", "未能检验", "引用此前候选"]]
    for name, a in aggs:
        rows.append([name, str(a["runs"]), str(a["experiments"]), f"{a['reuse_experiments']}（{a['reuse_supported']}）", str(a["supported"]),
                     str(a["partial"]), str(a["refuted"]), str(a["untestable"]), f"{a['follow_ups_citing_prior']} / {a['follow_ups']}"])
    d.table(s, rows, 0.6, 1.7, 12.1, [2.6, 0.9, 0.9, 1.4, 0.9, 0.9, 0.9, 1.4, 2.2], size=10.5)
    d.text(s, (f"合计：支持 {rtotal['supported']} · 部分支持 {rtotal['partial']} · 反驳 {rtotal['refuted']} · 未能检验 {rtotal['untestable']}；"
               f"其中复用实验 {rtotal['reuse_experiments']} 个（得到支持 {rtotal['reuse_supported']}）。被反驳和出错的实验同样保留。"
               "“引用此前候选”只统计模型假设里点名同一运行更早的候选，是反馈驱动的文字下限。"),
           0.6, 1.7 + 0.36 * len(rows) + 0.2, 12.1, 0.9, size=12, color=INK2)

    # 11 deliverables
    s = d.slide("研究成果：可运行、可复核、可追溯", "交付")
    d.bullets(s, ["export-run --bundle：研究记录（研究任务 · 过程 · 假设与实验 · 最终测试 · 资源 · 复现）",
                  "best.py 最佳已验证程序 · 全部候选代码 · 原始模型请求与回复 · report.json",
                  "reproduce.sh：在同一评测器、全新容器中复核最终数据；可选重跑整个研究循环",
                  "没有验证出改进时，交付初始程序并写明“无改进”，不包装成提升"], 0.6, 1.75, 7.0, 3.2, size=15)
    d.card(s, 8.0, 1.8, 4.7, 4.5, ACCENT)
    d.text(s, "docs/research/ 中的样例", 8.25, 1.95, 4.3, 0.4, size=15, bold=True, color=ACCENT)
    readme = Path(__file__).resolve().parents[2] / "docs" / "research" / "README.md"
    cases = [ln.split("](")[0].lstrip("| [") for ln in readme.read_text().splitlines() if ln.startswith("| [")] if readme.exists() else []
    d.text(s, "按规则从正式运行中选出：\n\n" + "\n".join(f"{i}. {c}" for i, c in enumerate(cases, 1))
           + "\n\nreproduce.sh 复核：A-01 1.44×（记录 1.4367×）；D-01 1.4473×（记录 1.4481×）", 8.25, 2.4, 4.3, 3.8, size=12.5, color=INK2)

    # 12 experience
    s = d.slide("经验是什么：已验证的程序，加上它成立的条件", "经验")
    succ = sorted([e for e in snap["experiences"] if e["outcome"] == "success"], key=lambda e: -(e["result"]["speedup"] or 0))[:1]
    other = [e for e in snap["experiences"] if e["outcome"] != "success" and e["action"].get("kind") == "reuse_candidate"] or \
            [e for e in snap["experiences"] if e["outcome"] != "success"]
    for i, e in enumerate(succ + other[:1]):
        xx = 0.6 + i * 6.2
        d.card(s, xx, 1.8, 5.9, 4.0, GOOD if e["outcome"] == "success" else BAD)
        label = {"success": "✓ 成功", "no_gain": "– 无收益", "failure": "✕ 失败"}[e["outcome"]]
        kind = "复验已有程序" if e["action"].get("kind") == "reuse_candidate" else "模型提出"
        d.text(s, f"{label} · {e['conditions']['task_id']} · {kind}", xx + 0.3, 1.95, 5.4, 0.4, size=16, bold=True)
        b = e["conditions"]["buckets"]
        res = e["result"]
        claim = (f"条件：{b['rows']} 行 · key {b['distinct_keys']} · {b['order']} · 偏斜 {b['skew']}\n"
                 f"程序：{len((e['action'].get('code') or '').splitlines())} 行，调用 {', '.join(e['action']['code_features'].get('calls', [])[:6])}\n"
                 f"实测：{res['status']}" + (f"，{res['speedup']:.2f}×" if res["speedup"] else "")
                 + (f"（{', '.join(res['failure_kinds'] or [])}）" if res.get("failure_kinds") else "")
                 + f"\n来源：{e['source']['run_id']} 第 {e['source']['step_seq']} 步 {e['source']['candidate_id']}\n\n"
                 f"解释（未验证）：{(e['hypothesis'] or '—')[:90]}")
        d.text(s, claim, xx + 0.3, 2.45, 5.4, 3.3, size=12.5, color=INK2)
    counts = snap["counts"]
    progs = {memory.normalized_code(e["action"]["code"]) for e in snap["experiences"] if e["outcome"] == "success" and e["action"].get("code")}
    d.text(s, (f"{final_snap} 共 {len(snap['experiences'])} 条：成功 {counts.get('success', 0)} · 无收益 {counts.get('no_gain', 0)} · 失败 {counts.get('failure', 0)}；"
               f"可复验的不同程序 {len(progs)} 个。程序从评测记录中提取，不额外调用模型；有更接近当前负载的无收益或失败记录时，该程序不会被复验。"),
           0.6, 6.05, 12.1, 0.8, size=13, color=INK2)

    # 13 learning in two rounds
    if learn2:
        rounds = [(f"第 {lbl[-1]} 轮", [r for r in learn2 if r["label"] == lbl]) for lbl in V2_LEARN]
        rounds = [(n_, reps) for n_, reps in rounds if reps]
        s = d.slide(f"学习：A 批 {len(rounds)} 轮，v0 → {final_snap}，方案库越学越快", "第二版 · 学习")
        img = ratchet_chart(rounds, charts / "ratchet.png")
        d.image(s, img, 0.5, 1.65, 6.9)
        rows = [["轮次", "达标", "请求", "复验", "费用", "耗时"]]
        for name, reps in rounds:
            rows.append([name, f"{sum(r['outcome']['goal_met'] for r in reps)}/{len(reps)}",
                         str(sum(r["iterations"]["model_requests"] for r in reps)),
                         str(sum(r["iterations"]["programs_reused"] for r in reps)),
                         f"${sum(r['usage']['total']['cost_usd'] or 0 for r in reps):.3f}",
                         f"{sum(r['timing']['wall_clock_total_s'] or 0 for r in reps):.0f}s"])
        d.table(s, rows, 7.7, 1.8, 5.0, [1.0, 0.8, 0.8, 0.8, 0.8, 0.8], size=12)
        d.text(s, ("每个学习运行先复验已有程序：已达标就把目标提高 5%，模型只做超越；没达标（如高基数任务）就照常研究。"
                   "第 2 轮在第 1 轮的成果上重学同样 6 个任务。这些是学习过程的观察，效果以留出对照为准。"),
               7.7, 1.8 + 0.36 * len(rows) + 0.3, 5.0, 2.5, size=12.5, color=INK2)

    # 14/15 comparisons (version 2)
    for c, name, key in ((cmp_b, "B 开发对照", "B2"), (cmp_d, "D 封存留出（最终验收）", "D")):
        s = d.slide(f"{name}：v0 vs {c['snapshot_b'] if c else final_snap}", "第二版 · 对照结果")
        if not c or c["finished_runs"] == 0:
            d.text(s, "对照尚未完成。", 0.6, 2.0, 10, 1, size=20, color=INK3)
            continue
        img = dots_chart(c, charts / f"{key}-dots.png", f"每个任务 × 每个快照 × {c['repeats']} 次的最终加速比（实心 = 达标）")
        d.image(s, img, 0.5, 1.65, 7.3)
        d.table(s, side_rows(c), 8.0, 1.75, 4.8, [1.9, 1.45, 1.45], size=11)
        lc = c["learning_cost"]
        foot = (f"{c['finished_runs']}/{c['planned_runs']} 次运行 · 配置一致性{'通过' if c['fair'] else '未通过'} · "
                + (f"学习成本另计 ${lc['cost_usd']:.3f} / {lc['wall_clock_s']:.0f}s（{len(lc['learn_runs'])} 次学习运行）" if lc.get("in_lineage") and lc.get("cost_usd") is not None else ""))
        d.text(s, foot, 8.0, 5.55, 4.8, 0.8, size=11, color=INK3)

    # 16 behaviour pair on the headline comparison
    if headline and headline["finished_runs"]:
        pt = headline["per_task"]
        a, b = headline["snapshot_a"], headline["snapshot_b"]
        task = max(headline["tasks"], key=lambda t: (pt[t][a]["runs"][0]["model_requests"] - pt[t][b]["runs"][0]["model_requests"],
                                                     -(pt[t][b]["runs"][0]["agent_loop_s"] or 0)))
        ra, rb = report.build(pt[task][a]["runs"][0]["run_id"]), report.build(pt[task][b]["runs"][0]["run_id"])
        s = d.slide(f"行为对照：{task} 第 1 轮，同一任务两版经验各做了什么", "RA-08 系统对照")
        for i, (rep, sn, col) in enumerate(((ra, a, OLD), (rb, b, NEW))):
            xx = 0.6 + i * 6.2
            d.card(s, xx, 1.75, 5.9, 4.9, col)
            up = rep["iterations"]["upgrade_at_step"]
            lines = [f"{sn}（{'无' if i == 0 else '有'}经验）· 复验程序 {rep['iterations']['programs_reused']} 个",
                     f"{rep['outcome']['summary']}",
                     f"请求 {rep['iterations']['model_requests']} · 升级 {rep['iterations']['upgrades']} · 费用 ${rep['usage']['total']['cost_usd'] or 0:.3f} · "
                     f"循环 {rep['timing']['agent_loop_s']:.0f}s", ""]
            for st in rep["steps"][:14]:
                who = "程序" if st["actor"] == "program" else ("GPT" if up and st["seq"] > up else "Qwen")
                sp = st["result"].get("speedup")
                lines.append(f"{st['seq']:>2}  {who:<4} {narrative.ACTION_ZH.get(st['action'], st['action'])} "
                             f"{st['candidate_id'] or ''} {narrative.STATUS_ZH.get(st['status'], st['status'])}"
                             + (f" {sp:.2f}×" if isinstance(sp, (int, float)) else ""))
            d.text(s, "\n".join(lines), xx + 0.3, 1.9, 5.4, 4.7, size=11.5, color=INK)

    # 17 where re-use did not help: the task (in B or D) where re-used programs least often carried the run
    pool = [(c, t) for c in (cmp_b, cmp_d) if c and c["finished_runs"] for t in c["tasks"]]
    wins = lambda c, t: sum(r.get("best_from_reuse", False) for r in c["per_task"][t][c["snapshot_b"]]["runs"])  # noqa: E731
    worst_pair = min(pool, key=lambda ct: wins(*ct)) if pool else None
    if worst_pair and wins(*worst_pair) < worst_pair[0]["repeats"]:
        cx, worst = worst_pair
        a, b = cx["snapshot_a"], cx["snapshot_b"]
        pt = cx["per_task"]
        s = d.slide(f"复用不适用的地方：{worst}（{'B 开发对照' if cx is cmp_b else 'D 封存留出'}）", "反例")
        rows = [["运行", f"{a} 结果", "路径 · 费用", f"{b} 结果", "路径 · 费用"]]
        for k in range(cx["repeats"]):
            cells = []
            for sn in (a, b):
                r = pt[worst][sn]["runs"][k]
                rep = report.build(r["run_id"])
                cells += [("达标 " if r["goal_met"] else "未达标 ") + (f"{r['final_speedup']:.2f}×" if r["final_speedup"] else ""),
                          f"{path_of(rep)} · ${r['cost_usd'] or 0:.3f}"]
            rows.append([f"第 {k + 1} 轮", *cells])
        d.table(s, rows, 0.6, 1.8, 7.2, [1.0, 1.7, 1.5, 1.7, 1.3], size=12)
        rep_b = report.build(pt[worst][b]["runs"][0]["run_id"])
        sel = (json.loads(db.one("SELECT payload_json FROM events WHERE run_id = ? AND type = 'reuse_selected'", (rep_b["run_id"],))["payload_json"])
               if db.one("SELECT 1 FROM events WHERE run_id = ? AND type = 'reuse_selected'", (rep_b["run_id"],)) else {})
        params = db.one("SELECT manifest_json FROM tasks WHERE task_id = ?", (worst,))
        dev = json.loads(params["manifest_json"])["dev_params"]
        d.card(s, 8.1, 1.8, 4.6, 4.6, ACCENT)
        d.text(s, f"{worst}：{dev['rows']:,} 行 · {dev['keys']:,} 个 key · {dev['order']}", 8.35, 1.95, 4.2, 0.4, size=14, bold=True, color=ACCENT)
        d.text(s, (f"复验选中 {len(sel.get('selected', []))} 个程序、跳过 {len(sel.get('skipped', []))} 个（有更接近的无收益/失败记录）。"
                   "R = 程序复验，Q = Qwen 请求，G = GPT 请求。\n\n"
                   "复验没有达标时，复验结果作为证据交给模型，照常研究；复用帮不了经验覆盖不到的工作负载。\n\n"
                   "代价：复验过的程序都留在提示词里，GPT 单次请求更长、更贵——这是这一侧费用高于 v0 的原因，"
                   "只保留最佳一个程序是已知的下一步改进。"),
               8.35, 2.45, 4.2, 3.9, size=12.5, color=INK2)
        d.text(s, "全部运行计入；路径按发生顺序。", 0.6, 6.3, 7.2, 0.4, size=11, color=INK3)

    # 18 cost ledger
    if headline and headline["finished_runs"]:
        s = d.slide("成本账：学习花了多少，使用经验省了多少", "效率")
        rows = [["批次", "v0 费用", "新经验 费用", "少花", "v0 循环中位数", "新经验 循环中位数", "请求中位数", "最终加速比中位数"]]
        for c, name in ((cmp_b, "第二版 · B 开发"), (cmp_d, "第二版 · D 封存"), (v1_c, "第一版 · C 留出")):
            if not c or not c["finished_runs"]:
                continue
            A, B = c["sides"][c["snapshot_a"]], c["sides"][c["snapshot_b"]]
            rows.append([name, usd(A["cost_usd_total"]), usd(B["cost_usd_total"]), (lambda v: f"${v:.3f}" if v >= 0 else f"−${-v:.3f}")((A["cost_usd_total"] or 0) - (B["cost_usd_total"] or 0)),
                         f"{A['agent_loop_s_median']:.0f}s", f"{B['agent_loop_s_median']:.0f}s",
                         f"{g(A['model_requests_median'])} → {g(B['model_requests_median'])}",
                         f"{x(A['final_speedup_median'])} → {x(B['final_speedup_median'])}"])
        d.table(s, rows, 0.6, 1.8, 12.1, [2.1, 1.2, 1.4, 1.1, 1.6, 1.8, 1.4, 1.5], size=12)
        lc = headline["learning_cost"]
        saved = [((c["sides"][c["snapshot_a"]]["cost_usd_total"] or 0) - (c["sides"][c["snapshot_b"]]["cost_usd_total"] or 0)) / c["sides"][c["snapshot_b"]]["runs"]
                 for c in (cmp_b, cmp_d) if c and c["finished_runs"]]
        txt = ""
        if lc.get("in_lineage") and lc.get("cost_usd") is not None:
            txt = (f"第二版学习（{len(lc['learn_runs'])} 次学习运行）另计 ${lc['cost_usd']:.3f}、{lc['wall_clock_s']:.0f}s，不摊进任何一侧。")
            if saved and min(saved) > 0:
                txt += (f"每次运行少花 {' / '.join(f'${v:.4f}' for v in saved)}（B / D），约 "
                        f"{' / '.join(f'{lc['cost_usd'] / v:.0f}' for v in saved)} 次运行收回学习费用。")
        for c, name in ((cmp_b, "B"), (cmp_d, "D")):
            if not c or not c["finished_runs"]:
                continue
            sb = c["snapshot_b"]
            per = {t: sum(r["cost_usd"] or 0 for r in c["per_task"][t][sb]["runs"]) for t in c["tasks"]}
            tot = sum(per.values())
            top = max(per, key=per.get)
            if tot and per[top] / tot >= 0.5:
                txt += (f"{name} 中新经验一侧的 GPT 费用有 {per[top] / tot:.0%} 来自 {top}（复验未达标，交给模型研究；"
                        f"提示词里带着复验过的程序，单次请求更长），其余任务合计 ${tot - per[top]:.3f}。")
        txt += "费用是 GPT 按官方价表的估算；本地 Qwen 没有 API 费用，机器成本未核算；复验的评测时间计入循环时长。"
        d.text(s, txt, 0.6, 1.8 + 0.36 * len(rows) + 0.3, 12.1, 1.6, size=13.5, color=INK2)

    # v3: router, the online stream, the router ablation, boundaries
    st = find_comparison("S online stream")
    s = d.slide("第三版：遇到全新问题怎么办——分流器", "第三版 · 分流")
    rows = [["路线", "什么时候走", "怎么做", "留下什么"],
            ["↺ 复用直接交付", "经验里有同族已验证程序，在本任务上复验达标", "不调用模型，直接交付", "复验结果写入经验"],
            ["○ 相近 → 本地小模型", "复验未达标，但有同族成功经验与本任务 ≥ 3/5 项条件相同", "先用 Qwen，连续未达标按规则升级到 GPT", "验证过的候选写入经验"],
            ["★ 全新任务族 → 大模型", "经验里没有这个任务族的任何记录", "直接交给 GPT，全部预算给它", "首次结果写入经验，下次同类先复用"],
            ["◆ 新条件 → 大模型", "有同族记录，但没有条件相近的成功经验", "直接交给 GPT", "同上"]]
    d.table(s, rows, 0.6, 1.8, 12.1, [2.5, 4.3, 3.0, 2.3], size=13)
    d.bullets(s, ["判断只用记录中的事实（任务族、5 个条件分桶的匹配数、结果是成功 / 无收益 / 失败），由程序执行，不交给模型自评；分流原因写进账本",
                  "新增两个任务族：访问日志统计（正则 + strptime 的旧式实现）、区间合并（取值跨 ±10¹²）；其他任务族的经验不算数",
                  "新增在线模式：像评测一样交付，交付后把验证过的结果写入经验——全新问题第一次付费做对，之后的相似任务免费复用",
                  "规则版本 router-v1 写进配置指纹；分流器可以关闭做对照，关闭后指纹改变"], 0.6, 3.95, 12.1, 3, size=14.5)

    if st and st["finished_runs"]:
        F, M = st["sides"]["fresh"], st["sides"]["memory"]
        lf, lm = st["repeats_of_family"]["fresh"], st["repeats_of_family"]["memory"]
        s = d.slide("S 任务流：带记忆 vs 不带记忆", f"第三版 · 封存任务流 · {len(st['tasks'])} 任务 × {st['repeats']} 次重放 · 3 个任务族")
        d.image(s, stream_chart(st, charts / "S-stream.png"), 0.5, 1.65, 7.7)
        rows = [["", "不带记忆", "带记忆"],
                ["达标", f"{F['goal_met']}/{F['runs']}", f"{M['goal_met']}/{M['runs']}"],
                ["大模型请求", str(F["large_model_requests_total"]), str(M["large_model_requests_total"])],
                ["模型费用", usd(F["cost_usd_total"]), usd(M["cost_usd_total"])],
                ["未调用模型", f"{F['runs_without_model_request']} 次", f"{M['runs_without_model_request']} 次"],
                ["循环时长中位数", f"{F['agent_loop_s_median']:.0f}s", f"{M['agent_loop_s_median']:.0f}s"],
                ["总耗时", f"{F['wall_clock_s_total']:.0f}s", f"{M['wall_clock_s_total']:.0f}s"],
                ["最终加速比中位数", x(F["final_speedup_median"]), x(M["final_speedup_median"])]]
        d.table(s, rows, 8.4, 1.75, 4.3, [1.7, 1.3, 1.3], size=12)
        g0 = st["growth"][0]
        d.text(s, (f"从 {st['start_snapshot']} 出发（只有分组聚合的经验）；每次重放都从起点重新学起，重复的是学习过程本身；"
                   f"每个任务都在从它学到东西之前运行。新任务族首次出现时两侧条件相同，都直接交给大模型；其余任务带记忆时 "
                   f"{lm['runs_without_model_request']}/{lm['runs']} 次没有调用模型（不带记忆 {lf['runs_without_model_request']}/{lf['runs']}）。"
                   f"经验 {g0['experiences_start']} → {'/'.join(str(x_['experiences_end']) for x_ in st['growth'])} 条。配置指纹{'一致' if st['fair'] else '不一致'}。"),
               0.6, 5.75, 12.1, 1.2, size=12.5, color=INK2)

    ab = ablation_sides()
    if ab:
        on, off = ab["on"], ab["off"]
        s = d.slide("为什么全新问题直接交给大模型：分流器开 / 关对照", "第三版 · 分流器对照")
        rows = [["指标", "分流关闭（先用本地 Qwen）", "分流开启（直接用 GPT）"],
                ["达标 / 运行", f"{off['goal_met']}/{off['runs']}", f"{on['goal_met']}/{on['runs']}"],
                ["最终加速比中位数", x(off["final_speedup_median"]), x(on["final_speedup_median"])],
                ["模型请求（小 / 大）", f"{off['small']} / {off['large_model_requests_total']}", f"{on['small']} / {on['large_model_requests_total']}"],
                ["失败候选", str(off["candidates_failed_total"]), str(on["candidates_failed_total"])],
                ["模型费用", usd(off["cost_usd_total"]), usd(on["cost_usd_total"])],
                ["循环时长中位数", f"{off['agent_loop_s_median']:.0f}s", f"{on['agent_loop_s_median']:.0f}s"],
                ["总耗时", f"{off['wall_clock_s_total']:.0f}s", f"{on['wall_clock_s_total']:.0f}s"]]
        d.table(s, rows, 0.6, 1.8, 8.0, [2.4, 2.8, 2.8], size=13)
        d.text(s, ("4 个 T 任务（两个新任务族，相近条件与新条件各一），都从 v19 出发、没有该族经验；评测模式不写经验；"
                   f"开 / 关各 {on['runs']} 次，按任务交替先后。两侧配置只差分流器一项。\n\n"
                   "全新问题的第一个答案会成为之后所有相似任务复用的起点，所以第一次值得交给更强的模型。"),
               8.9, 1.8, 3.8, 4.5, size=13, color=INK2)

    s = d.slide("边界条件：每种情况系统怎么做", "边界")
    rows = [["情况", "系统行为"],
            ["无法用程序验证的任务（开放问答等）", "不做：经验只存经过评测器验证的事实"],
            ["其他任务族的经验", "不算数：检索、复用、分流都只看同族记录"],
            ["留出批次", "只能评测；对照前检查任务是否为快照贡献过经验"],
            ["复验达标", "评测 / 在线：直接交付；学习：目标提高 5% 继续超越"],
            ["模型请求 6 次 / 候选 4 个 / 300 s 用完", "停止，交付当前最佳，不再为总结调用模型"],
            ["连续 2 次接口错误、配置错误或 4xx", "停止（model_api_error）"],
            ["输出错误、违反契约、超时、内存超限", "不替换最佳，候选与反例保留，计一次未达标"],
            ["沙箱或基线自身失败", "停止（environment_error），不发布经验"],
            ["学习 / 在线运行进行中", "拒绝切换生效版本；快照不可变，回退只切指针"]]
    d.table(s, rows, 0.6, 1.75, 12.1, [4.6, 7.5], size=12.5)
    d.text(s, "完整列表与对应测试见 docs/boundaries.md", 0.6, 6.55, 12, 0.4, size=11, color=INK3)

    # 19 self-iteration: one real two-round session, end to end
    ses = db.one("SELECT * FROM sessions WHERE status = 'completed' AND comparison_id IS NOT NULL ORDER BY created_at DESC LIMIT 1")
    if ses:
        sc = compare.summarize(ses["comparison_id"])
        lr = report.build(ses["learn_run_id"])
        a, b = sc["snapshot_a"], sc["snapshot_b"]
        s = d.slide("自我迭代：学习 → 自动发布 → 在没见过的任务上对照", "自我改进")
        phases = [("第一轮 学习", f"{ses['learn_task']} 读取 {ses['base_snapshot_id']}\n{'达标' if lr['outcome']['goal_met'] else '未达标'} {lr['outcome']['final_speedup'] or 0:.2f}×\n"
                                f"{lr['iterations']['model_requests']} 次请求 · {lr['timing']['wall_clock_total_s']:.0f}s"),
                  ("自动发布", f"{ses['new_snapshot_id']}（父版本 {ses['base_snapshot_id']}）\n"
                              f"{len(lr['experience']['published_experiences'] or [])} 条经验，程序核对来源后原子发布"),
                  ("第二轮 对照", f"{ses['eval_task']}：{a} 与 {b} 各 1 次\n配置一致性{'通过' if sc['fair'] else '未通过'}"),
                  ("三行说明", "由对照数据自动填写\n可回退到任一版本")]
        for i, (k, v) in enumerate(phases):
            xx = 0.6 + i * 3.1
            d.card(s, xx, 1.8, 2.8, 1.9, ACCENT if i == 1 else None)
            d.text(s, f"✓ {k}", xx + 0.2, 1.95, 2.5, 0.45, size=15, bold=True, font=HEAD_FONT)
            d.text(s, v, xx + 0.2, 2.45, 2.5, 1.2, size=11.5, color=INK2)
        rows = [["", f"{a}（{'无经验' if a == 'v0' else '旧经验'}）", f"{b}（新经验）"]]
        A, B = sc["sides"][a], sc["sides"][b]
        rows += [["结果", f"{'达标' if A['goal_met'] else '未达标'} {A['final_speedup_median'] or 0:.2f}×", f"{'达标' if B['goal_met'] else '未达标'} {B['final_speedup_median'] or 0:.2f}×"],
                 ["模型请求 / 升级", f"{g(A['model_requests_median'])} / {A['upgrades_total']}", f"{g(B['model_requests_median'])} / {B['upgrades_total']}"],
                 ["费用 / 耗时", f"${A['cost_usd_total'] or 0:.3f} / {A['wall_clock_s_total']:.0f}s", f"${B['cost_usd_total'] or 0:.3f} / {B['wall_clock_s_total']:.0f}s"]]
        d.table(s, rows, 0.6, 4.1, 7.4, [2.0, 2.7, 2.7], size=13)
        t0 = datetime.fromisoformat(ses["created_at"]); t1 = datetime.fromisoformat(ses["ended_at"])
        d.text(s, (f"实测一次（{ses['session_id']}，第一版配置），全程 {(t1 - t0).total_seconds() / 60:.1f} 分钟，中间无人工操作；"
                   "模型、提示词、预算、评测器不变，只换快照。\n\n单次结果只验证流程是否走通，不作为效果证据——效果见留出对照。"),
               8.3, 4.1, 4.4, 2.6, size=12.5, color=INK2)

    # 20 three lines
    if headline and headline["finished_runs"]:
        note = narrative.evolution_note(headline["comparison_id"])
        s = d.slide("经验带来的变化（由对照数据自动填写）", "系统评估")
        for i, line in enumerate(note["lines"]):
            d.card(s, 0.6, 1.8 + i * 1.65, 12.1, 1.45, ACCENT)
            d.text(s, line, 0.9, 1.9 + i * 1.65, 11.6, 1.3, size=13, color=INK)

    # 21 RA-AC acceptance at a glance
    s = d.slide("Research Agent 验收对照", "RA-AC")
    rows = [["编号", "要求", "证据"],
            ["RA-AC-01", "问题、目标、约束、预算、基线事前确定", "任务包哈希锁定；运行配置指纹；“研究任务”在开始前固定；D 批在第二版实现前封存"],
            ["RA-AC-02", "关键实验有事前假设与验证方法", f"{rtotal['experiments']} 个实验都有事前预期与验证方法（复用实验由程序写明来源与条件差异），判定引用评测 ID"],
            ["RA-AC-03", "可核验的反馈驱动决策", "A-01：反驳 → 修正 → 升级 → 支持；复验达标 → 提高目标 → 超越；" + f"引用此前候选 {rtotal['follow_ups_citing_prior']}/{rtotal['follow_ups']}"],
            ["RA-AC-04", "错误、退化、证据不足如实记录", f"反驳 {rtotal['refuted']}、未能检验 {rtotal['untestable']}；无改进的运行交付初始程序"],
            ["RA-AC-05", "独立最终评价，通过与未通过都报告", "开发达标但最终未达标的运行如实记为未达标"],
            ["RA-AC-06", "总成本覆盖全过程，预算不足正确结束", "逐调用账本，未知不记 0；复验时间计入循环；学习成本单列"],
            ["RA-AC-07", "从固定输入重跑方案与评价", "reproduce.sh 复核 A-01 1.44×、D-01 1.4473×、S-01 6.69×（记录 6.35×），结果正确；scripts/experiment.sh 重跑全流程"],
            ["RA-AC-08", "有无经验的完整对照", "第三版 S 任务流带 / 不带记忆各 36 次（重放 3 次学习过程）；第二版 B、D 与第一版 B、C 各 36 次；配置一致，全部计入"]]
    d.table(s, rows, 0.6, 1.75, 12.1, [1.4, 4.0, 6.7], size=12)

    # 22 limits
    s = d.slide("诚实声明与下一步", "边界")
    d.bullets(s, ["3 个任务族，都是单文件、仅标准库、stdin 输入的程序；经验只在同族内复用，跨族迁移不做",
                  "复用达标即交付，不再为单个任务追求最优；想继续提高用学习模式。条件分桶是人工定义的 5 个特征，阈值固定",
                  "无法用程序验证的任务（开放问答等）刻意不做：没有验证器就没有可信的经验",
                  "计时在一台 Mac（OrbStack 虚拟化）上；交替测量与“全部样本更快”规则压低噪声，小输入任务固定开销仍占约一半",
                  "模型不支持固定种子：每个配置重复 3 次，报告全部结果；3 次重复衡量运行波动，不等于学习过程被重复验证",
                  "Qwen 自部署机器成本未核算；GPT 费用按 2026-11-13 官方价表估算",
                  "后置：专用决策模型对照、多个独立 Agent、开放式文献检索；下一步：自动学习条件分桶、程序库的合并与淘汰"], 0.6, 1.75, 12.1, 5, size=15)

    # 23 reproduce
    s = d.slide("复现与界面", "交付")
    d.bullets(s, ["cd backend && uv sync && cp .env.example .env",
                  "scripts/experiment.sh   # 重建任务包 → A 学习两轮 → B、D 对照 → S 任务流",
                  "uv run routeevo serve   # 界面：总览 · 研究运行 · 经验查看 · 对照结果 · 版本管理 · 实时进度",
                  "uv run routeevo export-run <run_id> --bundle <目录>   # 研究成果交付包",
                  "uv run routeevo snapshots activate v0 --reason 回退   # 回退只切换指针，历史保留"], 0.6, 1.75, 6.4, 5, size=14)
    shot = shots / "home.png"
    if shot.exists():
        d.image(s, shot, 7.0, 1.75, 5.8)

    out.parent.mkdir(parents=True, exist_ok=True)
    d.prs.save(out)
    print(f"wrote {out} ({d.n} slides)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "RouteEvo.pptx"))
    ap.add_argument("--shots", default=str(Path(__file__).resolve().parents[2] / "docs" / "deck" / "shots"))
    args = ap.parse_args()
    build(Path(args.out), Path(args.shots))
