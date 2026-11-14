"""Generate bilingual README data visualizations for QuotaCrux.

Each figure targets ~9.6 in width with 10.5–14 pt typography and generous vertical
aspect ratios (1.3:1 to 2.2:1) so charts remain crisp and legible inside GitHub
README columns on desktop and mobile.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch
import numpy as np


FONT_REG_CANDIDATES = [
    Path("/usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-Regular.otf"),
    Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
]
FONT_BOLD_CANDIDATES = [
    Path("/usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-Bold.otf"),
    Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"),
]

BG = "#FAFBFD"
CARD_BG = "#FFFFFF"
BORDER = "#CBD5E1"
NAVY = "#1E293B"
SLATE = "#475569"
MUTED = "#64748B"
GRAY_BAR = "#94A3B8"
TEAL = "#0F766E"
INDIGO = "#3B5BDB"
AMBER = "#D97706"
CRIMSON = "#B91C1C"
GRID_COLOR = "#CBD5E1"


def configure_fonts() -> tuple[font_manager.FontProperties, font_manager.FontProperties]:
    reg_path = next((p for p in FONT_REG_CANDIDATES if p.exists()), None)
    bold_path = next((p for p in FONT_BOLD_CANDIDATES if p.exists()), reg_path)
    if reg_path:
        font_manager.fontManager.addfont(str(reg_path))
        if bold_path and bold_path != reg_path:
            font_manager.fontManager.addfont(str(bold_path))
        family = font_manager.FontProperties(fname=str(reg_path)).get_name()
        plt.rcParams["font.family"] = family
        reg_fp = font_manager.FontProperties(fname=str(reg_path))
        bold_fp = font_manager.FontProperties(fname=str(bold_path))
    else:
        reg_fp = font_manager.FontProperties()
        bold_fp = font_manager.FontProperties(weight="bold")

    plt.rcParams.update({
        "font.size": 11.2,
        "text.parse_math": False,
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": BORDER,
        "axes.linewidth": 1.0,
        "text.color": NAVY,
        "xtick.color": SLATE,
        "ytick.color": SLATE,
    })
    return reg_fp, bold_fp


def style_ax(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.set_facecolor(CARD_BG)
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=GRID_COLOR, linestyle="-", linewidth=0.75, alpha=0.55)
    ax.tick_params(length=4.0, color="#94A3B8")


def save_fig(fig: plt.Figure, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)


def plot_evolution_abatch(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    """1A: A-Batch two-round progression across A-01..A-06."""
    zh = lang == "zh"
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    fig.patch.set_facecolor(BG)

    tasks = ["A-01", "A-02", "A-03", "A-04", "A-05", "A-06"]
    r1 = np.array([1.19, 1.41, 1.09, 1.40, 1.24, 1.77])
    r2 = np.array([1.45, 2.03, 1.24, 1.58, 1.69, 1.96])

    x = np.arange(len(tasks))
    w = 0.36
    style_ax(ax, "y")
    b1 = ax.bar(
        x - w / 2, r1, width=w, color="#748CAB",
        label="第 1 轮学习（5/6 达标）" if zh else "Round 1 Learn (5/6 met)"
    )
    b2 = ax.bar(
        x + w / 2, r2, width=w, color=TEAL,
        label="第 2 轮进化（→ v19 · 6/6 全达标）" if zh else "Round 2 Evolve (→ v19 · 6/6 met)"
    )
    ax.axhline(1.10, color=AMBER, linestyle="--", linewidth=1.6, zorder=2)
    ax.text(
        5.55, 1.135, "目标线 1.10×" if zh else "Target 1.10×",
        ha="right", va="bottom", color=AMBER, fontsize=10.5, fontproperties=bold_fp,
        bbox={"boxstyle": "round,pad=0.2", "facecolor": BG, "edgecolor": "none", "alpha": 0.92},
        zorder=4,
    )

    for rect, val in zip(b1, r1):
        ax.text(
            rect.get_x() + rect.get_width() / 2, val + 0.035, f"{val:.2f}×",
            ha="center", va="bottom", fontsize=10.2, color=SLATE
        )
    for rect, val in zip(b2, r2):
        ax.text(
            rect.get_x() + rect.get_width() / 2, val + 0.035, f"{val:.2f}×",
            ha="center", va="bottom", fontsize=11.0, color=TEAL, fontproperties=bold_fp
        )

    ax.set_xticks(x, tasks, fontsize=11.8, fontproperties=bold_fp)
    ax.set_xlim(-0.56, 5.62)
    ax.set_ylim(0, 2.38)
    ax.set_ylabel("最终加速比（相对初始 c0）" if zh else "Final Speedup vs. c0", fontsize=11.5, fontproperties=bold_fp)
    ax.legend(
        loc="upper left", bbox_to_anchor=(0.0, 1.02), ncol=2,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=10.5
    )

    fig.suptitle(
        "Built for Better · A 批两轮自我学习：全任务持续刷新最佳"
        if zh else
        "Built for Better · A-Batch Two-Round Self-Evolution Across Every Task",
        x=0.015, y=0.99, ha="left", fontsize=13.8, fontproperties=bold_fp
    )
    fig.text(
        0.015, -0.01,
        "累计两轮学习开销 $0.455；沉淀不可变快照 v19（59 条三态记录：42 成功 / 13 无收益 / 4 失败），支持 CLI 与控制台一键回退。"
        if zh else
        "Cumulative 2-round learning cost: $0.455; captured immutable v19 (59 tri-state records: 42 success / 13 no-gain / 4 failure), rollback-safe.",
        fontsize=9.8, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.94])
    save_fig(fig, out_dir / f"evolution-abatch-{lang}.png")


def plot_evolution_zero_llm(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    """1B: From learning to zero-LLM direct verification delivery."""
    zh = lang == "zh"
    fig, ax = plt.subplots(figsize=(9.6, 4.3))
    fig.patch.set_facecolor(BG)

    style_ax(ax, "x")
    y_labels = [
        "D 批 · 封存留出验收\n（v0 空快照 → v19 复验）" if zh else "D-Batch · Sealed Held-out\n(v0 Empty → v19 Snapshot)",
        "S 任务流 · 新族后续任务\n（无记忆 → 在线自进化）" if zh else "S-Stream · Follow-up Tasks\n(Fresh → Online Memory)",
    ]
    y = np.arange(len(y_labels))
    h = 0.30
    before_zero = np.array([0.0, 30.0])
    after_zero = np.array([100.0, 100.0])

    ax.barh(
        y + h / 2 + 0.025, before_zero, height=h, color=GRAY_BAR,
        label="进化前（v0 / 无记忆）" if zh else "Before (v0 / Fresh)"
    )
    ax.barh(
        y - h / 2 - 0.025, after_zero, height=h, color=TEAL,
        label="进化后（v19 / 在线进化）" if zh else "After (v19 / Online)"
    )

    ax.text(3.0, 0 + h / 2 + 0.025, "0.0%  (0/18)", va="center", fontsize=10.8, color=SLATE)
    ax.text(
        103.0, 0 - h / 2 - 0.025,
        "100% (18/18)  ·  留出费用 $0.376 → $0.000*  ·  总耗时 −62.5%"
        if zh else
        "100% (18/18)  ·  Held-out USD $0.376 → $0.000*  ·  Time −62.5%",
        va="center", fontsize=10.6, color=TEAL, fontproperties=bold_fp
    )

    ax.text(33.0, 1 + h / 2 + 0.025, "30.0%  (9/30)", va="center", fontsize=10.8, color=SLATE)
    ax.text(
        103.0, 1 - h / 2 - 0.025,
        "100% (30/30)  ·  全流 GPT 请求 −78% (27→6)  ·  费用 $0.086"
        if zh else
        "100% (30/30)  ·  Stream GPT −78% (27→6)  ·  Spend $0.086",
        va="center", fontsize=10.6, color=TEAL, fontproperties=bold_fp
    )

    ax.set_yticks(y, y_labels, fontsize=11.0, fontproperties=bold_fp)
    ax.set_ylim(-0.55, 1.55)
    ax.set_xlim(0, 218)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("零模型调用直接复验交付率（%）" if zh else "Zero-LLM Re-validation Delivery Rate (%)", fontsize=11.5, fontproperties=bold_fp)
    ax.legend(
        loc="lower right", bbox_to_anchor=(1.0, 1.03), ncol=2,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=10.2
    )

    fig.suptitle(
        "从“单次学会”到“零模型直接交付”（封存留出集与在线流式检验）"
        if zh else
        "From Learning to Zero-LLM Delivery (Sealed Held-out & Live Stream)",
        x=0.015, y=0.99, ha="left", fontsize=13.5, fontproperties=bold_fp
    )
    fig.text(
        0.015, -0.01,
        "* D 批留出端 18 次运行全部通过模型前沙箱复验交付（学习期两轮费用 $0.455 单列）；S 任务流仅首次遇到未知新族时升级强模型。"
        if zh else
        "* D-Batch held-out delivered all 18 runs via pre-LLM sandbox validation (prior A-batch learning cost $0.455 tracked separately); S-Stream escalated once per unseen family.",
        fontsize=9.6, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.90])
    save_fig(fig, out_dir / f"evolution-zero-llm-{lang}.png")


def plot_routing_tradeoff(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    """2A: ahc026 time-quality Pareto & final score gain."""
    zh = lang == "zh"
    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    fig.patch.set_facecolor(BG)
    style_ax(ax, "both")
    ax.grid(axis="both", color=GRID_COLOR, linestyle="-", linewidth=0.75, alpha=0.55)

    times = [112.9, 389.9, 392.0, 389.4]
    gains = [0.51, 5.84, 5.97, 6.15]
    scores = [132540, 139559, 139736, 139972]
    colors = [AMBER, INDIGO, NAVY, TEAL]

    ax.axhline(0.0, color="#94A3B8", linestyle=":", linewidth=1.3, zorder=1)
    ax.text(
        408.0, 0.14, "初始程序 c0 = 131,864（+0.00%）" if zh else "Initial c0 = 131,864 (+0.00%)",
        ha="right", va="bottom", fontsize=9.8, color=MUTED, fontproperties=bold_fp
    )

    labels = (
        [
            "Decisions / Decisions（双决策）\n112.9s · 132,540 (+0.51%)\n耗时 −71.2% · 全程轻量模型早停",
            "LLM / Decisions（模型决策）\n389.9s · 139,559 (+5.84%)",
            "LLM / rule（默认基线）\n392.0s · 139,736 (+5.97%)",
            "Decisions / rule（动作决策 · 最优）\n389.4s · 139,972 (+6.15% · +236 vs 基线)\n箱搬运代价 18,136 → 10,028 (−44.7%)",
        ]
        if zh
        else [
            "Decisions / Decisions (Dual)\n112.9s · 132,540 (+0.51%)\n−71.2% wall time · Small tier early finish",
            "LLM / Decisions (Model)\n389.9s · 139,559 (+5.84%)",
            "LLM / rule (Baseline)\n392.0s · 139,736 (+5.97%)",
            "Decisions / rule (Action · Best)\n389.4s · 139,972 (+6.15% · +236 vs Base)\nBox energy 18,136 → 10,028 (−44.7%)",
        ]
    )
    text_positions = [
        (132.0, 1.35),   # Dual: clean upper right of bottom-left dot
        (235.0, 4.35),   # Model Decisions: clean lower left
        (225.0, 5.45),   # Baseline: clean mid left
        (205.0, 6.72),   # Action Decisions (Best): top left
    ]
    va_aligns = ["bottom", "center", "center", "center"]

    for i in range(4):
        size = 190 if i in (0, 3) else 125
        ax.scatter(
            times[i], gains[i], s=size, color=colors[i], edgecolor="white",
            linewidth=1.8, zorder=5
        )
        ax.annotate(
            labels[i],
            xy=(times[i], gains[i]),
            xytext=text_positions[i],
            textcoords="data",
            ha="left",
            va=va_aligns[i],
            fontsize=10.3 if i in (0, 3) else 10.0,
            color=colors[i],
            fontproperties=bold_fp if i in (0, 3) else reg_fp,
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": CARD_BG,
                "edgecolor": colors[i] if i in (0, 3) else BORDER,
                "linewidth": 1.3 if i in (0, 3) else 0.9,
                "alpha": 0.96,
            },
            arrowprops={
                "arrowstyle": "->",
                "color": colors[i],
                "lw": 1.3,
                "connectionstyle": "arc3,rad=0.06",
            },
            zorder=4,
        )

    ax.set_xlim(90, 415)
    ax.set_ylim(-0.45, 7.65)
    ax.set_xlabel("单轮总耗时（含 15 例隐藏 final，秒）" if zh else "Total Wall Time incl. 15 Hidden Final Cases (s)", fontsize=11.5, fontproperties=bold_fp)
    ax.set_ylabel("相对初始程序 c0 的得分提升（%）" if zh else "Final Score Gain vs. c0 (%)", fontsize=11.5, fontproperties=bold_fp)

    fig.suptitle(
        "ALE-Bench ahc026 路由消融：时间、质量与早停权衡"
        if zh else
        "ALE-Bench ahc026 Routing Ablation: Speed vs. Final Quality Trade-off",
        x=0.015, y=0.99, ha="left", fontsize=13.8, fontproperties=bold_fp
    )
    fig.text(
        0.015, -0.01,
        "统一预算：360s 轮内上限 / 20 总请求 / 10 候选（基于 v0 每组 1 次）；另有固定 Qwen 15 轮正式消融：60/96 (62.5%) 过 dev，15/15 过 final。"
        if zh else
        "Unified budget: 360s cap / 20 HTTP req / 10 candidates (1 run/arm from v0). Separately, 15 fixed-Qwen ALE runs: 60/96 (62.5%) passed dev, 15/15 passed final.",
        fontsize=9.6, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.94])
    save_fig(fig, out_dir / f"routing-ahc026-tradeoff-{lang}.png")


def plot_routing_requests(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    """2B: ahc026 HTTP request breakdown, candidate pass rate & decision cost."""
    zh = lang == "zh"
    fig, ax = plt.subplots(figsize=(9.6, 4.5))
    fig.patch.set_facecolor(BG)
    style_ax(ax, "x")

    variants = [
        ("Decisions / Decisions\n（双决策）" if zh else "Decisions / Decisions\n(Dual)"),
        ("LLM / Decisions\n（模型决策）" if zh else "LLM / Decisions\n(Model)"),
        ("LLM / rule\n（默认基线）" if zh else "LLM / rule\n(Baseline)"),
        ("Decisions / rule\n（动作决策 · 最优）" if zh else "Decisions / rule\n(Action · Best)"),
    ]
    small_r = np.array([6, 7, 3, 2])
    large_r = np.array([0, 4, 6, 5])
    dec_r = np.array([13, 8, 0, 7])
    totals = small_r + large_r + dec_r
    y = np.arange(len(variants))

    ax.barh(y, small_r, height=0.56, color="#64748B", label="轻量模型 Qwen" if zh else "Small (Qwen)")
    ax.barh(y, large_r, left=small_r, height=0.56, color=INDIGO, label="强模型 gpt-6.1-sol" if zh else "Large (gpt-6.1-sol)")
    ax.barh(y, dec_r, left=small_r + large_r, height=0.56, color=AMBER, label="Decisions (gpt-6-luna)" if zh else "Decisions (gpt-6-luna)")

    ax.axvline(20, color=CRIMSON, linestyle="--", linewidth=1.5, alpha=0.8, zorder=2)
    ax.text(
        20.25, 3.55, "20 次请求上限" if zh else "20 req cap",
        ha="left", va="bottom", fontsize=10.2, color=CRIMSON, fontproperties=bold_fp,
        bbox={"boxstyle": "round,pad=0.16", "facecolor": BG, "edgecolor": "none", "alpha": 0.95},
        zorder=4,
    )

    right_notes = (
        [
            "共 19 次 · 通过 6/6（全程 0 次强模型）",
            "共 19 次 · 通过 6/6（7 小 / 4 大 / 8 决策）",
            "共 9 次 · 通过 5/5（3 小 / 6 大 / 0 决策）",
            "共 14 次 · 通过 7/7 · Decisions 路由仅占已知美元费用 2.26% ($0.0068)",
        ]
        if zh
        else [
            "19 req · 6/6 pass (0 large-tier calls)",
            "19 req · 6/6 pass (7 small / 4 large / 8 Dec)",
            "9 req · 5/5 pass (3 small / 6 large / 0 Dec)",
            "14 req · 7/7 pass · Routing = 2.26% of USD spend ($0.0068)",
        ]
    )

    for i in range(4):
        if small_r[i] > 0:
            ax.text(small_r[i] / 2, i, str(small_r[i]), ha="center", va="center", color="white", fontsize=10.6, fontproperties=bold_fp)
        if large_r[i] > 0:
            ax.text(small_r[i] + large_r[i] / 2, i, str(large_r[i]), ha="center", va="center", color="white", fontsize=10.6, fontproperties=bold_fp)
        if dec_r[i] > 0:
            ax.text(small_r[i] + large_r[i] + dec_r[i] / 2, i, str(dec_r[i]), ha="center", va="center", color="white", fontsize=10.6, fontproperties=bold_fp)

        anchor_x = max(totals[i], 20.0) + 0.55 if totals[i] >= 19 else totals[i] + 0.55
        if i == 3:
            anchor_x = 14.55
        ax.text(
            anchor_x, i, right_notes[i], va="center",
            fontsize=10.0,
            color=TEAL if i == 3 else NAVY,
            fontproperties=bold_fp if i == 3 else reg_fp,
            bbox={"boxstyle": "round,pad=0.14", "facecolor": CARD_BG, "edgecolor": "none", "alpha": 0.90},
            zorder=4,
        )

    ax.set_yticks(y, variants, fontsize=10.6, fontproperties=bold_fp)
    ax.set_ylim(-0.55, 3.88)
    ax.set_xlim(0, 41.5)
    ax.set_xlabel("单轮 HTTP 请求次数（含动作/模型决策调用）" if zh else "HTTP Request Breakdown (incl. Routing Decisions)", fontsize=11.5, fontproperties=bold_fp)
    ax.legend(
        loc="lower left", bbox_to_anchor=(0.0, 1.02), ncol=3,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=9.8
    )

    fig.suptitle(
        "ALE-Bench ahc026 请求预算分配、候选通过率与决策开销"
        if zh else
        "ALE-Bench ahc026 Request Mix, Pass Rate & Decision Overhead",
        x=0.015, y=0.99, ha="left", fontsize=13.5, fontproperties=bold_fp
    )
    fig.text(
        0.015, -0.01,
        "Decisions / rule 组 strong-tier Token 占 46.6% (68,207 / 146,253)，Decisions 路由仅 $0.0068 / $0.3006（另有 2 次 Qwen 请求）。"
        if zh else
        "In Decisions / rule, gpt-6.1-sol used 46.6% of total tokens (68,207 / 146,253), while Decisions routing cost $0.0068 of $0.3006 USD subtotal (+2 Qwen calls).",
        fontsize=9.5, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.90])
    save_fig(fig, out_dir / f"routing-ahc026-requests-{lang}.png")


def plot_algotune(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    """3: Vertical 2-row stack for full-width legibility (Dumbbell latency + Speedup)."""
    zh = lang == "zh"
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9.6, 7.0), gridspec_kw={"height_ratios": [1.0, 1.08]}
    )
    fig.patch.set_facecolor(BG)

    rows = [
        ("一维卷积 · feedback" if zh else "1D Conv · feedback"),
        ("一维卷积 · independent" if zh else "1D Conv · independent"),
        ("PageRank · independent"),
        ("PageRank · feedback"),
    ]
    base_ms = np.array([0.963, 1.117, 10.909, 11.148])
    best_ms = np.array([0.742, 0.419, 0.473, 0.445])
    speedup = np.array([1.30, 2.67, 23.05, 25.04])
    changes = (
        [
            "实数 FFT 批处理调度与缓冲区复用",
            "误差容限内切换 float32 实数 FFT",
            "由邻接表直建稀疏矩阵执行乘法迭代",
            "绕过 NetworkX 构图，直转 SciPy 稀疏幂迭代",
        ]
        if zh
        else [
            "Batched rFFT scheduling & buffer reuse",
            "Switch to float32 rFFT within L2 tolerance",
            "Build sparse matrix directly from adjacency list",
            "Bypass NetworkX; SciPy sparse power iteration",
        ]
    )
    colors = ["#64748B", INDIGO, "#0D9488", TEAL]
    y = np.arange(len(rows))

    # Top row: Log-scale dumbbell latency drop
    style_ax(ax1, "x")
    ax1.set_xscale("log")
    for i in range(4):
        ax1.annotate(
            "", xy=(best_ms[i], i), xytext=(base_ms[i], i),
            arrowprops={"arrowstyle": "->", "color": colors[i], "lw": 2.8}
        )
        ax1.scatter(base_ms[i], i, s=110, facecolor=CARD_BG, edgecolor=SLATE, linewidth=2.2, zorder=4)
        ax1.scatter(best_ms[i], i, s=125, color=colors[i], edgecolor="white", linewidth=1.4, zorder=5)
        ax1.text(base_ms[i] * 1.12, i, f"{base_ms[i]:.2f} ms", va="center", ha="left", fontsize=10.2, color=SLATE)
        ax1.text(best_ms[i] * 0.88, i, f"{best_ms[i]:.2f} ms", va="center", ha="right", fontsize=10.5, color=colors[i], fontproperties=bold_fp)

    ax1.set_yticks(y, rows, fontsize=10.8, fontproperties=bold_fp)
    ax1.set_xlim(0.20, 24.0)
    ax1.set_xticks([0.3, 0.5, 1.0, 3.0, 10.0], ["0.3", "0.5", "1.0", "3.0", "10.0"])
    ax1.set_xlabel("两例 dev 总执行中位耗时（毫秒，对数坐标）" if zh else "Median Solve Time (2 dev cases, ms, log scale)", fontsize=11.0, fontproperties=bold_fp)
    ax1.set_title("① 基线实现（空心）→ 最佳候选（实心）毫秒耗时压缩" if zh else "(1) Baseline (hollow) → Best Candidate (solid) Latency", loc="left", fontsize=12.2, pad=10, fontproperties=bold_fp)

    # Bottom row: Speedup bars + algorithmic innovation
    style_ax(ax2, "x")
    bars = ax2.barh(y, speedup, height=0.56, color=colors)
    for i, (rect, sp, ch) in enumerate(zip(bars, speedup, changes)):
        ax2.text(
            sp + 0.65, rect.get_y() + rect.get_height() / 2,
            f"{sp:.2f}×   |   {ch}",
            va="center", fontsize=10.4,
            color=colors[i] if i >= 2 else NAVY,
            fontproperties=bold_fp if i >= 2 else reg_fp
        )
    ax2.set_yticks(y, rows, fontsize=10.8, fontproperties=bold_fp)
    ax2.set_xlim(0, 62.0)
    ax2.set_xlabel("相对配对参考实现的执行加速比（×）" if zh else "Speedup vs. Paired Reference (×)", fontsize=11.0, fontproperties=bold_fp)
    ax2.set_title("② 函数级加速倍数与核心算法突破" if zh else "(2) Speedup Multiplier & Key Algorithmic Rewrite", loc="left", fontsize=12.2, pad=10, fontproperties=bold_fp)

    fig.suptitle(
        "AlgoTune 函数级优化探索（gpt-6.1-sol · Mac 2-case Dev）"
        if zh else
        "Exploratory AlgoTune Optimization (gpt-6.1-sol · Mac 2-Case Dev)",
        x=0.015, y=0.99, ha="left", fontsize=13.8, fontproperties=bold_fp
    )
    fig.text(
        0.015, -0.01,
        "口径：每项上限 180s / 5 请求 / 3 候选，2 个 dev 输入 × 5 次交替计时取中位数（关闭 final 评测；审计批费用 USD 0.336）。"
        if zh else
        "Scope: 180s / 5 req / 3 candidates per run, 2 dev inputs × 5 repeats (final disabled; audited batch OpenAI subtotal USD 0.336).",
        fontsize=9.6, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.95], h_pad=2.0)
    save_fig(fig, out_dir / f"algotune-speedups-{lang}.png")


def plot_experience_quality(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    """4A: Speedup & target attainment (Text-only C-Batch regression vs D-Batch & S-Stream)."""
    zh = lang == "zh"
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    fig.patch.set_facecolor(BG)
    style_ax(ax, "y")

    batches = [
        ("C 批 · 纯文字经验\n(v0 → v6)" if zh else "C-Batch · Text-Only\n(v0 → v6)"),
        ("D 批 · 可执行程序复用\n(v0 → v19)" if zh else "D-Batch · Program Reuse\n(v0 → v19)"),
        ("S 任务流 · 在线分流进化\n(无记忆 → 在线)" if zh else "S-Stream · Online Triage\n(Fresh → Online)"),
    ]
    x = np.arange(3)
    w = 0.32
    sp_before = [1.41, 1.20, 1.86]
    sp_after = [1.29, 1.73, 1.86]

    ax.bar(x - w / 2, sp_before, width=w, color=GRAY_BAR)
    ax.bar(x + w / 2, sp_after, width=w, color=[CRIMSON, TEAL, TEAL])

    pass_notes = ["达标 16/18 → 16/18", "达标 15/18 → 18/18", "达标 36/36 → 36/36"] if zh else ["Met 16/18 → 16/18", "Met 15/18 → 18/18", "Met 36/36 → 36/36"]
    delta_notes = ["−8.5% 加速比退步" if zh else "−8.5% regression", "+44.2% 显著提速" if zh else "+44.2% speedup gain", "零模型前提下稳住高加速" if zh else "Sustained w/ 30/30 zero-LLM"]

    for i in range(3):
        ax.text(x[i] - w / 2, sp_before[i] + 0.04, f"{sp_before[i]:.2f}×", ha="center", va="bottom", fontsize=10.6, color=SLATE)
        c = CRIMSON if i == 0 else TEAL
        ax.text(x[i] + w / 2, sp_after[i] + 0.04, f"{sp_after[i]:.2f}×", ha="center", va="bottom", fontsize=11.0, color=c, fontproperties=bold_fp)
        ax.text(
            x[i], max(sp_before[i], sp_after[i]) + 0.21,
            f"{delta_notes[i]}\n{pass_notes[i]}",
            ha="center", va="bottom", fontsize=10.0,
            color=c if i == 0 else (TEAL if i == 1 else NAVY),
            fontproperties=bold_fp
        )

    ax.set_xticks(x, batches, fontsize=11.0, fontproperties=bold_fp)
    ax.set_ylim(0, 2.52)
    ax.set_ylabel("留出/流式最终加速比中位数（×）" if zh else "Median Final Speedup (×)", fontsize=11.5, fontproperties=bold_fp)
    ax.legend(
        handles=[
            Patch(facecolor=GRAY_BAR, label="对照前（v0 / 无记忆）" if zh else "Before (v0 / Fresh)"),
            Patch(facecolor=TEAL, label="可执行经验正收益 / 保持" if zh else "Executable Experience Win"),
            Patch(facecolor=CRIMSON, label="纯文字经验退步" if zh else "Text-Only Regression"),
        ],
        loc="lower left", bbox_to_anchor=(0.0, 1.02), ncol=3,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=9.8
    )

    fig.suptitle(
        "经验形态受控对照：纯文字建议退步 (−8.5%) vs. 可执行程序复用 (+44.2%)"
        if zh else
        "Experience Form Ablation: Text-Only Regression (−8.5%) vs. Executable Reuse (+44.2%)",
        x=0.015, y=0.99, ha="left", fontsize=13.3, fontproperties=bold_fp
    )
    fig.text(
        0.015, -0.01,
        "实验锁死相同模型权重、提示词与沙箱裁判，仅更换经验快照；C 批纯文字退步直接促使系统演进出 v2 程序复用与 v3 覆盖分流。"
        if zh else
        "Identical model weights, prompts, and sandbox judge across all runs—varying only the experience snapshot; C-Batch regression drove v2 executable reuse & v3 triage.",
        fontsize=9.6, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.90])
    save_fig(fig, out_dir / f"experience-quality-ablation-{lang}.png")


def plot_experience_cost_runtime(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    """4B: Vertical 2-row horizontal bar chart for USD spend, GPT requests & wall time."""
    zh = lang == "zh"
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9.6, 7.4), gridspec_kw={"height_ratios": [1.0, 1.0]}
    )
    fig.patch.set_facecolor(BG)

    batches = [
        ("C 批 · 纯文字 (v0 → v6)" if zh else "C-Batch · Text (v0 → v6)"),
        ("D 批 · 程序复用 (v0 → v19)" if zh else "D-Batch · Reuse (v0 → v19)"),
        ("S 任务流 · 在线 (无记忆 → 在线)" if zh else "S-Stream · Online (Fresh → On)"),
    ]
    y = np.arange(3)
    h = 0.30

    # Row 1: Cloud USD Spend & GPT Requests
    style_ax(ax1, "x")
    usd_before = np.array([0.372, 0.376, 0.402])
    usd_after = np.array([0.292, 0.000, 0.086])
    ax1.barh(y + h / 2 + 0.025, usd_before, height=h, color=GRAY_BAR, label="对照前费用" if zh else "Before Spend")
    ax1.barh(y - h / 2 - 0.025, usd_after, height=h, color=TEAL, label="加入经验后费用" if zh else "With Experience")

    usd_after_notes = (
        [
            "$0.292  (GPT 升级 11 → 5)",
            "$0.000*  (GPT 7 → 0 · 总请求 52 → 0)",
            "$0.086  (GPT 请求 −78%：27 → 6)",
        ]
        if zh
        else [
            "$0.292  (GPT escalations 11 → 5)",
            "$0.000*  (GPT 7 → 0 · Total req 52 → 0)",
            "$0.086  (GPT requests −78%: 27 → 6)",
        ]
    )
    for i in range(3):
        ax1.text(usd_before[i] + 0.012, y[i] + h / 2 + 0.025, f"${usd_before[i]:.3f}", va="center", fontsize=10.4, color=SLATE)
        ax1.text(usd_after[i] + 0.012, y[i] - h / 2 - 0.025, usd_after_notes[i], va="center", fontsize=10.5, color=TEAL, fontproperties=bold_fp)

    ax1.set_yticks(y, batches, fontsize=10.6, fontproperties=bold_fp)
    ax1.set_ylim(-0.55, 2.55)
    ax1.set_xlim(0, 0.72)
    ax1.set_xlabel("模型估算费用（USD）与强模型请求变化" if zh else "Estimated Cloud USD Spend & GPT Call Reduction", fontsize=11.0, fontproperties=bold_fp)
    ax1.set_title("① 云端大模型支出与请求数量" if zh else "(1) Cloud Model Spend & Request Collapse", loc="left", fontsize=12.0, pad=12, fontproperties=bold_fp)
    ax1.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), ncol=2, frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=9.6)

    # Row 2: Total Batch Wall Time & Median Loop Time
    style_ax(ax2, "x")
    tot_before = np.array([2000, 1782, 1486])
    tot_after = np.array([1886, 669, 1064])
    ax2.barh(y + h / 2 + 0.025, tot_before, height=h, color=GRAY_BAR, label="对照前总耗时" if zh else "Before Wall Time")
    ax2.barh(y - h / 2 - 0.025, tot_after, height=h, color=TEAL, label="加入经验后总耗时" if zh else "With Experience")

    time_after_notes = (
        [
            "1886s  (单轮中位 84s → 50s)",
            "669s  (−62.5% · 单轮中位 53s → 27s)",
            "1064s  (−28.4% · 单轮中位 31.2s → 14.3s)",
        ]
        if zh
        else [
            "1886s  (Median loop 84s → 50s)",
            "669s  (−62.5% · Median loop 53s → 27s)",
            "1064s  (−28.4% · Median loop 31.2s → 14.3s)",
        ]
    )
    for i in range(3):
        ax2.text(tot_before[i] + 38, y[i] + h / 2 + 0.025, f"{tot_before[i]}s", va="center", fontsize=10.4, color=SLATE)
        ax2.text(tot_after[i] + 38, y[i] - h / 2 - 0.025, time_after_notes[i], va="center", fontsize=10.5, color=TEAL, fontproperties=bold_fp)

    ax2.set_yticks(y, batches, fontsize=10.6, fontproperties=bold_fp)
    ax2.set_ylim(-0.55, 2.55)
    ax2.set_xlim(0, 2950)
    ax2.set_xlabel("整批端到端总耗时与单轮循环中位时长（秒）" if zh else "Total Batch Runtime & Median Loop Duration (s)", fontsize=11.0, fontproperties=bold_fp)
    ax2.set_title("② 端到端耗时与循环延迟收敛" if zh else "(2) Batch Wall Time & Median Loop Convergence", loc="left", fontsize=12.0, pad=12, fontproperties=bold_fp)
    ax2.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), ncol=2, frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=9.6)

    fig.suptitle(
        "跨任务经验复用：云端支出归零与端到端耗时收敛"
        if zh else
        "Cross-Task Experience Reuse: Frontier Cost & Wall-Time Reduction",
        x=0.015, y=0.99, ha="left", fontsize=13.6, fontproperties=bold_fp
    )
    fig.text(
        0.015, -0.01,
        "* D 批留出端实现 18/18 零模型交付，前置两轮学习费用 $0.455 单列；S 任务流（v19 起点，12 任务 × 3 重放）所有同族后续 30/30 均零模型交付。"
        if zh else
        "* D-Batch held-out achieved 18/18 zero-LLM delivery while prior two-round learning ($0.455) is tracked separately; S-Stream resolved all 30/30 follow-up runs without LLMs.",
        fontsize=9.5, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.94], h_pad=2.6)
    save_fig(fig, out_dir / f"experience-cost-runtime-{lang}.png")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "docs/assets/readme",
    )
    args = p.parse_args()
    reg_fp, bold_fp = configure_fonts()
    for lang in ("zh", "en"):
        plot_evolution_abatch(lang, args.out_dir, reg_fp, bold_fp)
        plot_evolution_zero_llm(lang, args.out_dir, reg_fp, bold_fp)
        plot_routing_tradeoff(lang, args.out_dir, reg_fp, bold_fp)
        plot_routing_requests(lang, args.out_dir, reg_fp, bold_fp)
        plot_algotune(lang, args.out_dir, reg_fp, bold_fp)
        plot_experience_quality(lang, args.out_dir, reg_fp, bold_fp)
        plot_experience_cost_runtime(lang, args.out_dir, reg_fp, bold_fp)
    print(f"Generated 14 responsive README charts in {args.out_dir}")


if __name__ == "__main__":
    main()
