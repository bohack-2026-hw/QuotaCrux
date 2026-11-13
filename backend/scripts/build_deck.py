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

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402
from pptx.util import Emu, Pt  # noqa: E402

from routeevo import compare, db, memory, narrative, report  # noqa: E402

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

def learn_rows() -> list[dict]:
    sql = ("SELECT run_id FROM runs WHERE mode = 'learn' AND json_extract(config_json, '$.label') = 'formal A learning'"
           " ORDER BY started_at")
    return [report.build(r["run_id"]) for r in db.all_rows(sql)]


def learned_snapshot() -> str:
    """The snapshot published by the last formal A learning run (a later demo session may publish a newer branch)."""
    row = db.one("SELECT published_snapshot_id FROM runs WHERE mode = 'learn' AND published_snapshot_id IS NOT NULL"
                 " AND json_extract(config_json, '$.label') = 'formal A learning' ORDER BY started_at DESC LIMIT 1")
    return row["published_snapshot_id"] if row else "v0"


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


def find_comparison(prefix: str) -> dict | None:
    for r in db.all_rows("SELECT comparison_id, label FROM comparisons ORDER BY created_at DESC"):
        if (r["label"] or "").startswith(prefix):
            return compare.summarize(r["comparison_id"])
    return None


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
    handles = [Line2D([], [], marker="o", ls="", color="#" + OLD, markersize=8, label=f"{a}（旧经验）"),
               Line2D([], [], marker="o", ls="", color="#" + NEW, markersize=8, label=f"{b}（新经验）"),
               Line2D([], [], marker="o", ls="", markerfacecolor="#" + CARD, markeredgecolor="#" + INK3, markersize=8, label="空心 = 未达标")]
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=10, ncol=3, bbox_to_anchor=(0, -0.09))
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def side_rows(c: dict) -> list[list[str]]:
    a, b = c["snapshot_a"], c["snapshot_b"]
    A, B = c["sides"][a], c["sides"][b]
    usd = lambda v: "未知" if v is None else f"${v:.3f}"  # noqa: E731
    x = lambda v: "—" if v is None else f"{v:.2f}×"  # noqa: E731
    n = lambda v: "—" if v is None else f"{v:,}"  # noqa: E731
    return [
        ["指标", f"{a}（旧经验）", f"{b}（新经验）"],
        ["达标 / 运行", f"{A['goal_met']} / {A['runs']}", f"{B['goal_met']} / {B['runs']}"],
        ["最终加速比中位数", x(A["final_speedup_median"]), x(B["final_speedup_median"])],
        ["模型请求中位数", g(A["model_requests_median"]), g(B["model_requests_median"])],
        ["升级到 GPT 次数", str(A["upgrades_total"]), str(B["upgrades_total"])],
        ["失败候选", str(A["candidates_failed_total"]), str(B["candidates_failed_total"])],
        ["输出 Token 合计", n(A["output_tokens"]["total"]), n(B["output_tokens"]["total"])],
        ["模型费用合计", usd(A["cost_usd_total"]), usd(B["cost_usd_total"])],
        ["总耗时", f"{A['wall_clock_s_total']:.0f}s", f"{B['wall_clock_s_total']:.0f}s"],
    ]


# ---------- slides ----------

def build(out: Path, shots: Path) -> None:
    d = Deck()
    charts = out.parent / "deck"
    charts.mkdir(parents=True, exist_ok=True)
    learn = learn_rows()
    cmp_b, cmp_c = find_comparison("B"), find_comparison("C")
    final_snap = learned_snapshot()
    snap = memory.snapshot(final_snap)

    # 1 cover
    s = d.slide()
    s.background.fill.fore_color.rgb = rgb(INK)
    box = d.text(s, "Route", 0.9, 2.0, 8, 1.4, size=80, color=PAPER, font="Georgia")
    evo = box.text_frame.paragraphs[0].add_run()
    evo.text = "Evo"
    evo.font.size, evo.font.italic, evo.font.name = Pt(80), True, "Georgia"
    evo.font.color.rgb = rgb(ACCENT)
    d.text(s, "从已验证的执行结果中进化的 Agent", 0.95, 3.5, 11, 0.7, size=28, color=PAPER, font=HEAD_FONT, bold=True)
    d.text(s, "决策 → 执行 → 验证 → 修正 → 经验 → 更好的下一次决策", 0.95, 4.3, 11, 0.5, size=16, color="B8B2A3")
    d.text(s, "BoHack 2026 · 共用核心实测版", 0.95, 6.3, 6, 0.4, size=12, color="9A9485")

    # 2 questions
    s = d.slide("我们要回答的两个问题", "问题定义")
    d.card(s, 0.6, 1.8, 5.9, 2.6, ACCENT)
    d.text(s, "① 闭环能否成立", 0.9, 2.0, 5.4, 0.5, size=20, bold=True, font=HEAD_FONT)
    d.text(s, "在预算内完成“决策—执行—验证—修正”，留下可追溯、可复现的结果；运行完成、验证通过、指标改善、达到目标分开记录。", 0.9, 2.6, 5.4, 1.6, size=15, color=INK2)
    d.card(s, 6.8, 1.8, 5.9, 2.6, ACCENT)
    d.text(s, "② 经验能否让下一次更好", 7.1, 2.0, 5.4, 0.5, size=20, bold=True, font=HEAD_FONT)
    d.text(s, "同样的模型、提示词、预算和评测，只换经验快照：在未参与学习的任务上，质量、成本或耗时是否改善？", 7.1, 2.6, 5.4, 1.6, size=15, color=INK2)
    d.bullets(s, ["学习发生在系统层：不训练模型、不改提示词，程序把经过评测的执行事实写成不可变的经验快照",
                  "结论只来自留出任务上的对照数据，全部运行（包括失败与无收益）都计入"], 0.6, 4.8, 12, 2, size=16)

    # 3 task
    s = d.slide("首个任务：在正确性约束下优化程序", "任务")
    d.bullets(s, ["按字符串 key 分组 CSV，输出每组数量与整数和，按 key 升序",
                  "初始程序：csv + 两个 dict + sorted，正确、正常，不人为削弱",
                  "主指标：加速比 = 初始程序耗时中位数 / 候选耗时中位数",
                  "达标：输出全对 + 5 次候选样本全部快于 5 次基线样本 + 加速比 ≥ 1.10",
                  "19 个冻结任务包（哈希锁定）：A 学习 6 · B 开发对照 6 · C 最终留出 6 · smoke 1",
                  "  覆盖随机、有序、成簇、几乎有序陷阱、低基数、高基数、小输入——A 的经验不必处处成立"], 0.6, 1.75, 7.2, 5, size=16)
    d.card(s, 8.1, 1.8, 4.6, 4.6)
    d.text(s, "同一个优化，效果相反", 8.35, 1.95, 4.2, 0.4, size=14, bold=True, color=ACCENT)
    d.text(s, "按字节解析 + 单字典：\n  中等基数（A-01）≈ 1.44×\n  高基数（A-05）≈ 0.82×\n\n带有序检查的 groupby：\n  所有 A 任务 ≈ 0.7×\n\n只用 groupby 不检查：\n  有序数据上正确，\n  但违反契约用例 → 判失败", 8.35, 2.45, 4.2, 3.9, size=14, color=INK2)

    # 4 loop
    s = d.slide("执行循环：模型选行动，程序执行并验证", "架构")
    steps = [("构造状态", "契约 · 数据画像 · 候选\n反馈 · 预算 · 经验"), ("模型选行动", "分析 · 取证 · 提出候选\n验证 · 结束"),
             ("程序检查", "动作参数 · 预算\n仅标准库 · 代码大小"), ("沙箱 + 评测器", "正确性 · 契约用例\n交替计时 · 最佳产物"),
             ("反馈", "状态 · 加速比 · 反例\n→ 下一步")]
    for i, (k, v) in enumerate(steps):
        x = 0.6 + i * 2.5
        d.card(s, x, 2.0, 2.2, 1.8, ACCENT if i == 1 else None)
        d.text(s, k, x + 0.2, 2.15, 1.9, 0.45, size=16, bold=True, font=HEAD_FONT)
        d.text(s, v, x + 0.2, 2.65, 1.9, 1.1, size=11.5, color=INK2)
        if i < 4:
            d.text(s, "→", x + 2.2, 2.6, 0.3, 0.5, size=20, color=ACCENT, bold=True)
    d.bullets(s, ["本地 Qwen（qwen3.8:27b，关闭思考）先执行；连续两个候选未“正确且达标”，或 Qwen 请求 3 次仍无达标候选 → 固定规则升级到 GPT-6.1 Sol（xhigh），本次运行不再切回",
                  "每次运行最多 6 次模型请求、4 个候选、300 秒；预算耗尽后不再为总结调用模型",
                  "终止原因分开记录：目标达成 · 预算耗尽 · Agent 结束 · 用户停止 · 接口错误 · 环境错误"], 0.6, 4.3, 12.1, 2.6, size=15)

    # 5 trust
    s = d.slide("可信的验证：模型碰不到裁判", "验证")
    d.bullets(s, ["每个样本一个全新容器：禁网、只读根文件系统、非 root、1 CPU / 1 GB、64 进程；只挂载候选文件，输入走 stdin",
                  "参考输出、最终测试数据、评测程序都留在宿主机；候选自报的“通过”或“耗时”不算数",
                  "7 个公开契约用例：空输入、交错重复 key、ASCII 排序、超大整数、几乎有序陷阱、32 字符 key",
                  "计时：容器内启动器就绪后才开始；基线与候选各预热一次，交替 5 轮，取中位数之比",
                  "“改善”= 全部候选样本快于全部基线样本（单侧 Mann-Whitney U=0，p≈0.004）；同一程序靠噪声测出 1.05× 也不算",
                  "循环结束后最佳候选冻结，在隐藏最终数据上测一次，结果不回流"], 0.6, 1.75, 12.1, 5, size=16)

    # 6 feedback chain
    first = learn[0] if learn else None
    if first:
        s = d.slide(f"一条真实的决策链：{first['task']['task_id']}（无经验 v0）", "反馈驱动")
        rows = [["#", "执行者", "动作", "结果", "下一步"]]
        for st in first["steps"]:
            res = st["result"]
            out_s = narrative.STATUS_ZH.get(st["status"], st["status"]) + (f" · {res['speedup']:.2f}×" if isinstance(res.get("speedup"), (int, float)) else "")
            who = "程序" if st["actor"] == "program" else ("GPT" if first["iterations"]["upgrade_at_step"] and st["seq"] > first["iterations"]["upgrade_at_step"] else "Qwen")
            rows.append([str(st["seq"]), who, narrative.ACTION_ZH.get(st["action"], st["action"]), out_s, narrative._decision(st["next_decision"] or "")])
        d.table(s, rows, 0.6, 1.8, 7.4, [0.5, 0.9, 1.4, 2.4, 2.2], size=12)
        d.card(s, 8.3, 1.8, 4.4, 4.7, ACCENT)
        d.text(s, "发生了什么", 8.55, 1.95, 4, 0.4, size=15, bold=True, color=ACCENT)
        hyp = [st["hypothesis"] for st in first["steps"] if st["hypothesis"]]
        d.text(s, (f"结论：{first['outcome']['summary']}\n\n"
                   f"Qwen 的两次尝试一次变慢、一次表头格式错误，按规则升级到 GPT；GPT 读到具体失败反馈后修正。\n\n"
                   f"模型假设（未验证）：{(hyp[-1] or '')[:90]}…\n\n"
                   f"费用 ${first['usage']['total']['cost_usd'] or 0:.3f} · {first['iterations']['model_requests']} 次请求"),
               8.55, 2.4, 4, 4, size=12.5, color=INK2)

    # 7 experience
    s = d.slide("经验是什么：程序从已验证的执行事实中提取", "经验")
    succ = [e for e in snap["experiences"] if e["outcome"] == "success"][:1]
    fail = ([e for e in snap["experiences"] if e["outcome"] == "failure"] or [e for e in snap["experiences"] if e["outcome"] != "success"])[:1]
    for i, e in enumerate(succ + fail):
        x = 0.6 + i * 6.2
        d.card(s, x, 1.8, 5.9, 4.0, GOOD if e["outcome"] == "success" else BAD)
        label = {"success": "✓ 成功", "no_gain": "– 无收益", "failure": "✕ 失败"}[e["outcome"]]
        d.text(s, f"{label} · {e['conditions']['task_id']}", x + 0.3, 1.95, 5.4, 0.4, size=16, bold=True)
        b = e["conditions"]["buckets"]
        res = e["result"]
        claim = (f"条件：{b['rows']} 行 · key {b['distinct_keys']} · {b['order']} · 偏斜 {b['skew']}\n"
                 f"改动特征：{', '.join(e['action']['code_features'].get('calls', [])[:7])}\n"
                 f"实测：{res['status']}" + (f"，{res['speedup']:.2f}×" if res["speedup"] else "")
                 + (f"（{', '.join(res['failure_kinds'] or [])}）" if res.get("failure_kinds") else "")
                 + f"\n来源：{e['source']['run_id']} 第 {e['source']['step_seq']} 步 {e['source']['candidate_id']}\n\n"
                 f"模型解释（未验证）：{(e['hypothesis'] or '—')[:80]}")
        d.text(s, claim, x + 0.3, 2.45, 5.4, 3.3, size=12.5, color=INK2)
    counts = snap["counts"]
    d.text(s, f"{final_snap} 共 {len(snap['experiences'])} 条：成功 {counts.get('success', 0)} · 无收益 {counts.get('no_gain', 0)} · 失败 {counts.get('failure', 0)}。"
              "检索：5 个分桶特征至少匹配 3 个，最多注入 3 成功 + 2 失败 + 1 无收益，并标出不同的特征与样本数。",
           0.6, 6.05, 12.1, 0.8, size=13, color=INK2)

    # 8 learning
    if learn:
        s = d.slide(f"学习阶段：A 批 6 个任务串行，v0 → {final_snap}", "学习")
        rows = [["任务", "读取", "结果", "请求", "模型路径", "费用", "读到经验", "发布"]]
        for r in learn:
            roles = "".join("G" if "large" in k else "Q" for k, v in r["usage"]["by_model"].items() for _ in range(v["requests"]))
            res = (f"达标 {r['outcome']['final_speedup']:.2f}×" if r["outcome"]["goal_met"]
                   else f"未达标（{narrative.STOP_ZH.get(r['stop_reason'], r['stop_reason'])}）")
            rows.append([r["task"]["task_id"], r["snapshot_id"], res, str(r["iterations"]["model_requests"]),
                         roles or "—", f"${r['usage']['total']['cost_usd'] or 0:.3f}", str(len(r["experience"]["read"])),
                         r["experience"]["published_snapshot_id"] or "—"])
        d.table(s, rows, 0.6, 1.8, 12.1, [0.9, 0.8, 4.2, 0.8, 1.6, 1.2, 1.2, 1.4], size=12)
        total = sum((r["usage"]["total"]["cost_usd"] or 0) for r in learn)
        d.text(s, f"学习阶段总费用 ${total:.3f}（GPT 按官方价表估算；本地 Qwen 无 API 费用，机器成本未核算）。"
                  "这是学习过程中的观察，不是对照证据——效果结论见下两页的留出对照。", 0.6, 5.0, 12.1, 0.9, size=14, color=INK2)

    # 9/10 comparisons
    for c, name in ((cmp_b, "B 批开发对照"), (cmp_c, "C 批最终留出")):
        s = d.slide(f"{name}：v0 vs {c['snapshot_b'] if c else final_snap}", "对照结果")
        if not c or c["finished_runs"] == 0:
            d.text(s, "对照尚未完成。", 0.6, 2.0, 10, 1, size=20, color=INK3)
            continue
        img = dots_chart(c, charts / f"{name[:1]}-dots.png", f"每个任务 × 每个快照 × {c['repeats']} 次的最终加速比（实心 = 达标）")
        d.image(s, img, 0.5, 1.65, 7.3)
        d.table(s, side_rows(c), 8.0, 1.75, 4.8, [1.9, 1.45, 1.45], size=11)
        lc = c["learning_cost"]
        first_run = next(r["run_id"] for t in c["tasks"] for r in c["per_task"][t][c["snapshot_a"]]["runs"])
        rule = json.loads(db.one("SELECT config_json FROM runs WHERE run_id = ?", (first_run,))["config_json"])["upgrade_rule"]["id"]
        foot = (f"{c['finished_runs']}/{c['planned_runs']} 次运行 · 配置一致性{'通过' if c['fair'] else '未通过'} · {rule} · "
                + (f"学习成本另计 ${lc['cost_usd']:.3f} / {lc['wall_clock_s']:.0f}s" if lc.get("in_lineage") and lc.get("cost_usd") is not None else ""))
        d.text(s, foot, 8.0, 5.3, 4.8, 0.8, size=11, color=INK3)

    # what the headline medians hide: fewer upgrades also means stopping at a smaller speedup
    if cmp_c and cmp_c["finished_runs"]:
        a, b = cmp_c["snapshot_a"], cmp_c["snapshot_b"]
        s = d.slide("代价：少升级，也就更早停在较小的加速比", "C 批解读")
        rows = [["任务", f"{a} 加速比", f"{b} 加速比", f"{a} 请求", f"{b} 请求"]]
        for t in cmp_c["tasks"]:
            cells = []
            for snapname in (a, b):
                runs = cmp_c["per_task"][t][snapname]["runs"]
                cells.append(" ".join(("—" if r["final_speedup"] is None else f"{r['final_speedup']:.2f}") + ("" if r["goal_met"] else "✕") for r in runs))
            rows.append([t, *cells, *(" ".join(str(r["model_requests"]) for r in cmp_c["per_task"][t][sn]["runs"]) for sn in (a, b))])
        d.table(s, rows, 0.6, 1.8, 7.4, [0.9, 2.0, 2.0, 1.25, 1.25], size=12)
        split = {k: gpt_split(c) for k, c in (("B", cmp_b), ("C", cmp_c)) if c and c["finished_runs"]}
        med = lambda v: f"{statistics.median(v):.2f}×" if v else "—"  # noqa: E731
        d.card(s, 8.3, 1.8, 4.4, 4.7, ACCENT)
        d.text(s, "为什么", 8.55, 1.95, 4, 0.4, size=15, bold=True, color=ACCENT)
        d.text(s, ("达标线是 1.10×，智能体达标即停止。\n\n达标运行的最终加速比中位数（两版合计）：\n"
                   + "\n".join(f"  {k}：用过 GPT {med(v['gpt'])}（{len(v['gpt'])} 次）· 只用 Qwen {med(v['qwen'])}（{len(v['qwen'])} 次）" for k, v in split.items())
                   + f"\n\n{a} 更常升级到 GPT，在 C-01、C-02 上停在更快的程序；{b} 用学到的做法一次达标就停。"
                   "学到的是更省的达标路径，不是更高的上限；要追求上限需要改终止条件。"),
               8.55, 2.4, 4, 4, size=12.5, color=INK2)
        d.text(s, "✕ = 未达标；— = 没有计时结果。开发数据上达标、最终测试有样本不快于基线的运行同样记为 ✕。", 0.6, 6.3, 7.4, 0.5, size=11, color=INK3)

    # behaviour pair: same held-out task, same repeat, two snapshots
    if cmp_b and cmp_b["finished_runs"]:
        pt = cmp_b["per_task"]
        a, b = cmp_b["snapshot_a"], cmp_b["snapshot_b"]
        # the task where the old snapshot needed the most requests in repeat 1 shows the change most plainly
        task = max(cmp_b["tasks"], key=lambda t: (pt[t][a]["runs"][0]["model_requests"] - pt[t][b]["runs"][0]["model_requests"]))
        ra, rb = report.build(pt[task][a]["runs"][0]["run_id"]), report.build(pt[task][b]["runs"][0]["run_id"])
        s = d.slide(f"行为对照：{task} 第 1 轮，同一任务两版经验各做了什么", "RX-05")
        for i, (rep, snapname, col) in enumerate(((ra, a, OLD), (rb, b, NEW))):
            x = 0.6 + i * 6.2
            d.card(s, x, 1.75, 5.9, 4.9, col)
            up = rep["iterations"]["upgrade_at_step"]
            lines = [f"{snapname}（{'旧' if i == 0 else '新'}经验）· 读到经验 {len(rep['experience']['read'])} 条",
                     f"{rep['outcome']['summary']}",
                     f"请求 {rep['iterations']['model_requests']} · 升级 {rep['iterations']['upgrades']} · 费用 ${rep['usage']['total']['cost_usd'] or 0:.3f} · {rep['timing']['wall_clock_total_s']:.0f}s", ""]
            for st in rep["steps"]:
                who = "程序" if st["actor"] == "program" else ("GPT" if up and st["seq"] > up else "Qwen")
                sp = st["result"].get("speedup")
                lines.append(f"{st['seq']:>2}  {who:<4} {narrative.ACTION_ZH.get(st['action'], st['action'])} "
                             f"{st['candidate_id'] or ''} {narrative.STATUS_ZH.get(st['status'], st['status'])}"
                             + (f" {sp:.2f}×" if isinstance(sp, (int, float)) else ""))
            first = next((st["purpose"] for st in rep["steps"] if st["actor"] == "model" and st["purpose"]), "")
            lines += ["", f"第一步的目的：{first[:110]}"]
            d.text(s, "\n".join(lines), x + 0.3, 1.9, 5.4, 4.7, size=11.5, color=INK)

    # where experience did not help
    if cmp_b and cmp_b["finished_runs"]:
        s = d.slide("经验不适用的地方：如实报告，并据此修改规则", "反例")
        worst = min(cmp_b["tasks"], key=lambda t: cmp_b["per_task"][t][cmp_b["snapshot_b"]]["goal_met"] - cmp_b["per_task"][t][cmp_b["snapshot_a"]]["goal_met"])
        rows = [["运行", cmp_b["snapshot_a"] + " 结果", "请求 / 模型", cmp_b["snapshot_b"] + " 结果", "请求 / 模型"]]
        for k in range(cmp_b["repeats"]):
            cells = []
            for snapname in (cmp_b["snapshot_a"], cmp_b["snapshot_b"]):
                r = cmp_b["per_task"][worst][snapname]["runs"][k]
                rep = report.build(r["run_id"])
                path = "".join("G" if "large" in key else "Q" for key, v in rep["usage"]["by_model"].items() for _ in range(v["requests"]))
                cells += [("达标 " if r["goal_met"] else "未达标 ") + (f"{r['final_speedup']:.2f}×" if r["final_speedup"] else ""),
                          f"{r['model_requests']} / {path}"]
            rows.append([f"第 {k + 1} 轮", *cells])
        d.table(s, rows, 0.6, 1.8, 7.2, [1.0, 1.7, 1.5, 1.7, 1.3], size=12)
        d.card(s, 8.1, 1.8, 4.6, 4.6, ACCENT)
        d.text(s, f"{worst}：成簇、高基数", 8.35, 1.95, 4.2, 0.4, size=15, bold=True, color=ACCENT)
        d.text(s, ("学到的经验对这类数据全是“无收益”。小模型据此把请求花在分析和取证上，迟迟不提出第二个失败候选，"
                   "升级规则（只看连续失败候选）来不及触发，预算耗尽。\n\n"
                   "这是 B（开发对照）的结论。C 之前把升级规则改为 v2：再加一条“小模型 3 次请求仍无达标候选就升级”，"
                   "对旧、新经验同样生效；同时修正记录，规则满足但没有请求额度时如实写明。\n\n"
                   "C 是未参与任何调整的最终留出验收"
                   + (f"；其中同类的高基数任务 C-05：{cmp_c['snapshot_a']} {cmp_c['per_task']['C-05'][cmp_c['snapshot_a']]['goal_met']}/{cmp_c['repeats']}、"
                      f"{cmp_c['snapshot_b']} {cmp_c['per_task']['C-05'][cmp_c['snapshot_b']]['goal_met']}/{cmp_c['repeats']}。"
                      if cmp_c and "C-05" in cmp_c["tasks"] else "。")), 8.35, 2.45, 4.2, 3.9, size=12.5, color=INK2)

    # cost ledger
    target_cost = cmp_c if cmp_c and cmp_c["finished_runs"] else cmp_b
    if target_cost:
        s = d.slide("成本账：学习花了多少，使用经验省了多少", "效率")
        rows = [["批次", "旧经验 费用", "新经验 费用", "差额", "旧经验 耗时", "新经验 耗时", "请求中位数"]]
        for c, name in ((cmp_b, "B 开发对照"), (cmp_c, "C 最终留出")):
            if not c or not c["finished_runs"]:
                continue
            A, B = c["sides"][c["snapshot_a"]], c["sides"][c["snapshot_b"]]
            rows.append([name, f"${A['cost_usd_total'] or 0:.3f}", f"${B['cost_usd_total'] or 0:.3f}",
                         f"${(A['cost_usd_total'] or 0) - (B['cost_usd_total'] or 0):+.3f}",
                         f"{A['wall_clock_s_total']:.0f}s", f"{B['wall_clock_s_total']:.0f}s",
                         f"{g(A['model_requests_median'])} → {g(B['model_requests_median'])}"])
        d.table(s, rows, 0.6, 1.8, 12.1, [2.0, 1.7, 1.7, 1.5, 1.7, 1.7, 1.8], size=13)
        lc = target_cost["learning_cost"]
        if lc.get("in_lineage"):
            d.text(s, (f"学习阶段（A 批 {len(lc['learn_runs'])} 次学习运行）另计 ${lc['cost_usd']:.3f}、{lc['wall_clock_s']:.0f}s，"
                       "不摊进任何一侧。费用是 GPT 按官方价表的估算；本地 Qwen 没有 API 费用，机器成本未核算；"
                       "一次 GPT 请求被循环剩余时间截断、服务方未返回用量，记为“未知”。"),
                   0.6, 3.6, 12.1, 1.2, size=14, color=INK2)
            saved = [((c["sides"][c["snapshot_a"]]["cost_usd_total"] or 0) - (c["sides"][c["snapshot_b"]]["cost_usd_total"] or 0)) / c["sides"][c["snapshot_b"]]["runs"]
                     for c in (cmp_b, cmp_c) if c and c["finished_runs"]]
            if lc.get("cost_usd") and saved and min(saved) > 0:
                d.text(s, (f"每次运行少花 {' / '.join(f'${v:.4f}' for v in saved)}（B / C），按此学习成本约在 "
                           f"{' / '.join(f'{lc['cost_usd'] / v:.0f}' for v in saved)} 次运行后收回。"
                           "加入经验后提示词更长，输入 Token 反而增加；节省来自更少的请求、升级与输出 Token。"),
                       0.6, 4.9, 12.1, 1.0, size=14, color=INK2)

    # RX-01/02: one real two-round session, end to end
    ses = db.one("SELECT * FROM sessions WHERE status = 'completed' AND comparison_id IS NOT NULL ORDER BY created_at DESC LIMIT 1")
    if ses:
        sc = compare.summarize(ses["comparison_id"])
        lr = report.build(ses["learn_run_id"])
        a, b = sc["snapshot_a"], sc["snapshot_b"]
        s = d.slide("两轮现场演示：学习 → 自动发布 → 在没见过的任务上对照", "日新 · RX-01/02")
        phases = [("第一轮 学习", f"{ses['learn_task']} 读取 {ses['base_snapshot_id']}\n{'达标' if lr['outcome']['goal_met'] else '未达标'} {lr['outcome']['final_speedup'] or 0:.2f}×\n"
                                f"{lr['iterations']['model_requests']} 次请求 · {lr['timing']['wall_clock_total_s']:.0f}s"),
                  ("自动发布", f"{ses['new_snapshot_id']}（父版本 {ses['base_snapshot_id']}）\n"
                              f"{lr['experience']['published_experiences']} 条经验，程序核对来源后原子发布"),
                  ("第二轮 对照", f"{ses['eval_task']}：{a} 与 {b} 各 1 次\n配置一致性{'通过' if sc['fair'] else '未通过'}"),
                  ("三行说明", "由对照数据自动填写\n可回退到任一版本")]
        for i, (k, v) in enumerate(phases):
            x = 0.6 + i * 3.1
            d.card(s, x, 1.8, 2.8, 1.9, ACCENT if i == 1 else None)
            d.text(s, f"✓ {k}", x + 0.2, 1.95, 2.5, 0.45, size=15, bold=True, font=HEAD_FONT)
            d.text(s, v, x + 0.2, 2.45, 2.5, 1.2, size=11.5, color=INK2)
        rows = [["", f"{a}（旧经验）", f"{b}（新经验）"]]
        A, B = sc["sides"][a], sc["sides"][b]
        rows += [["结果", f"{'达标' if A['goal_met'] else '未达标'} {A['final_speedup_median'] or 0:.2f}×", f"{'达标' if B['goal_met'] else '未达标'} {B['final_speedup_median'] or 0:.2f}×"],
                 ["模型请求 / 升级", f"{g(A['model_requests_median'])} / {A['upgrades_total']}", f"{g(B['model_requests_median'])} / {B['upgrades_total']}"],
                 ["费用 / 耗时", f"${A['cost_usd_total'] or 0:.3f} / {A['wall_clock_s_total']:.0f}s", f"${B['cost_usd_total'] or 0:.3f} / {B['wall_clock_s_total']:.0f}s"]]
        d.table(s, rows, 0.6, 4.1, 7.4, [2.0, 2.7, 2.7], size=13)
        t0 = datetime.fromisoformat(ses["created_at"]); t1 = datetime.fromisoformat(ses["ended_at"])
        d.text(s, (f"实测一次（{ses['session_id']}），全程 {(t1 - t0).total_seconds() / 60:.1f} 分钟，中间无人工操作；"
                   "模型、提示词、预算、评测器不变，只换快照。\n\n单次结果只验证流程是否走通，不作为效果证据——效果见 B/C 对照。"
                   "演示结束后把生效版本切回正式快照。"), 8.3, 4.1, 4.4, 2.6, size=12.5, color=INK2)

    # 11 three lines
    target = cmp_c or cmp_b
    if target and target["finished_runs"]:
        note = narrative.evolution_note(target["comparison_id"])
        s = d.slide("三行进化说明（由对照数据自动填写）", "日新")
        for i, line in enumerate(note["lines"]):
            d.card(s, 0.6, 1.8 + i * 1.65, 12.1, 1.45, ACCENT)
            d.text(s, line, 0.9, 1.9 + i * 1.65, 11.6, 1.3, size=13.5, color=INK)

    # 12 limits
    s = d.slide("诚实声明与下一步", "边界")
    d.bullets(s, ["单一任务族：结论只适用于同族任务之间的经验迁移",
                  "计时在一台 Mac（OrbStack 虚拟化）上；交替测量与“全部样本更快”规则压低噪声，小输入任务固定开销仍占约一半",
                  "模型不支持固定种子：每个配置重复 3 次，报告全部结果；3 次重复衡量运行波动，不等于学习过程被重复验证",
                  "Qwen 自部署机器成本未核算；GPT 费用按 2026-11-13 官方价表估算",
                  "下一步：更多任务族；用同一批任务对照专用决策模型是否降低总成本；经验的去重与合并"], 0.6, 1.75, 12.1, 5, size=16)

    # 13 reproduce
    s = d.slide("复现与界面", "交付")
    d.bullets(s, ["cd backend && uv sync && cp .env.example .env",
                  "scripts/experiment.sh   # 重建任务包 → A 学习 → B 对照 → C 对照",
                  "uv run routeevo serve   # 界面：任务运行 · 经验查看 · 对照结果 · 版本管理",
                  "uv run routeevo export-run <run_id>   # 单次运行的研究记录",
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
