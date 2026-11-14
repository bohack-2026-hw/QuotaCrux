"""Generate bilingual README data visualizations for QuotaCrux."""
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
BORDER = "#E2E8F0"
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
        "font.size": 10.5,
        "text.parse_math": False,
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#CBD5E1",
        "axes.linewidth": 0.9,
        "text.color": NAVY,
        "xtick.color": SLATE,
        "ytick.color": SLATE,
    })
    return reg_fp, bold_fp


def style_ax(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.set_facecolor(CARD_BG)
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=GRID_COLOR, linestyle="-", linewidth=0.7, alpha=0.55)
    ax.tick_params(length=3.5, color="#94A3B8")


def save_fig(fig: plt.Figure, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)


def plot_self_evolution(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    zh = lang == "zh"
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(15.0, 5.1), gridspec_kw={"width_ratios": [1.18, 1.05]}
    )
    fig.patch.set_facecolor(BG)

    # Panel A: A-Batch Round 1 vs Round 2 (v19)
    tasks = ["A-01", "A-02", "A-03", "A-04", "A-05", "A-06"]
    r1 = np.array([1.19, 1.41, 1.09, 1.40, 1.24, 1.77])
    r2 = np.array([1.45, 2.03, 1.24, 1.58, 1.69, 1.96])

    x = np.arange(len(tasks))
    w = 0.35
    style_ax(ax1, "y")
    b1 = ax1.bar(
        x - w / 2, r1, width=w, color="#748CAB",
        label="第 1 轮学习（达标 5/6）" if zh else "Round 1 Learn (5/6 met)"
    )
    b2 = ax1.bar(
        x + w / 2, r2, width=w, color=TEAL,
        label="第 2 轮进化（→ v19 · 6/6）" if zh else "Round 2 Evolve (→ v19 · 6/6)"
    )
    ax1.axhline(1.10, color=AMBER, linestyle="--", linewidth=1.35, zorder=2)
    ax1.text(
        5.55, 1.125, "目标线 1.10×" if zh else "Target 1.10×",
        ha="right", va="bottom", color=AMBER, fontsize=8.8, fontproperties=bold_fp,
        bbox={"boxstyle": "round,pad=0.18", "facecolor": BG, "edgecolor": "none", "alpha": 0.9},
        zorder=4,
    )
    for rect, val in zip(b1, r1):
        ax1.text(
            rect.get_x() + rect.get_width() / 2, val + 0.035, f"{val:.2f}×",
            ha="center", va="bottom", fontsize=8.5, color=SLATE
        )
    for rect, val in zip(b2, r2):
        ax1.text(
            rect.get_x() + rect.get_width() / 2, val + 0.035, f"{val:.2f}×",
            ha="center", va="bottom", fontsize=9.1, color=TEAL, fontproperties=bold_fp
        )
    ax1.set_xticks(x, tasks, fontsize=10.5, fontproperties=bold_fp)
    ax1.set_xlim(-0.58, 5.65)
    ax1.set_ylim(0, 2.38)
    ax1.set_ylabel("最终加速比（相对初始 c0）" if zh else "Final Speedup vs. c0", fontsize=10.2, fontproperties=bold_fp)
    ax1.set_title(
        "A 批两轮自我学习：全任务持续刷新最佳" if zh else "A-Batch Two-Round Evolution: Gains Across Every Task",
        loc="left", fontsize=12.2, pad=30, fontproperties=bold_fp
    )
    ax1.legend(
        loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=9.0
    )

    # Panel B: Zero-LLM Reuse Rate & Cost Shift on D-Batch (y=0) & S-Stream (y=1)
    style_ax(ax2, "x")
    y_labels = [
        "D 批 · 封存留出验收\n（v0 无经验 vs v19 快照）" if zh else "D-Batch · Sealed Held-out\n(v0 Empty vs. v19 Snapshot)",
        "S 任务流 · 同族后续任务\n（无记忆 vs 在线记忆）" if zh else "S-Stream · Follow-up Tasks\n(Fresh vs. Online Memory)",
    ]
    y = np.arange(len(y_labels))
    h = 0.28
    before_zero = np.array([0.0, 30.0])     # y=0: D-Batch 0/18 (0%), y=1: S-Stream follow-up 9/30 (30%)
    after_zero = np.array([100.0, 100.0])   # y=0: D-Batch 18/18 (100%), y=1: S-Stream follow-up 30/30 (100%)

    ax2.barh(
        y + h / 2 + 0.02, before_zero, height=h, color=GRAY_BAR,
        label="进化前（v0 / 无记忆）" if zh else "Before (v0 / Fresh)"
    )
    ax2.barh(
        y - h / 2 - 0.02, after_zero, height=h, color=TEAL,
        label="进化后（v19 / 在线记忆）" if zh else "After (v19 / Online)"
    )

    # Row 0 (D-Batch)
    ax2.text(3.0, 0 + h / 2 + 0.02, "0.0% (0/18)", va="center", fontsize=9.2, color=SLATE)
    ax2.text(
        103.0, 0 - h / 2 - 0.02,
        "100% (18/18)\n留出费用 $0.376 → $0.000*" if zh else "100% (18/18)\nHeld-out USD $0.376 → $0.000*",
        va="center", fontsize=9.1, color=TEAL, fontproperties=bold_fp
    )
    # Row 1 (S-Stream follow-up)
    ax2.text(33.0, 1 + h / 2 + 0.02, "30.0% (9/30)", va="center", fontsize=9.2, color=SLATE)
    ax2.text(
        103.0, 1 - h / 2 - 0.02,
        "100% (30/30)\n全流 GPT −78% (27→6) · $0.086" if zh else "100% (30/30)\nStream GPT −78% (27→6) · $0.086",
        va="center", fontsize=9.1, color=TEAL, fontproperties=bold_fp
    )

    ax2.set_yticks(y, y_labels, fontsize=9.6, fontproperties=bold_fp)
    ax2.set_ylim(-0.55, 1.55)
    ax2.set_xlim(0, 192)
    ax2.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax2.set_xlabel("零模型调用直接复验交付率（%）" if zh else "Zero-LLM Re-validation Delivery Rate (%)", fontsize=10.2, fontproperties=bold_fp)
    ax2.set_title(
        "从“学会”到“零模型直接交付”" if zh else "From Learning to Zero-LLM Delivery",
        loc="left", fontsize=12.2, pad=30, fontproperties=bold_fp
    )
    ax2.legend(
        loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=9.0
    )

    fig.suptitle(
        "Built for Better · 可核验、可回退的跨轮自我进化" if zh else "Built for Better · Quantified Cross-Round Self-Evolution",
        x=0.012, y=1.03, ha="left", fontsize=15, fontproperties=bold_fp
    )
    fig.text(
        0.012, -0.02,
        "* 注：v0 → v19 共沉淀 59 条三态经验（42 成功 / 13 无收益 / 4 失败），前置两轮学习阶段费用另计 $0.455；任意快照均支持 CLI / 控制台一键回退。"
        if zh else
        "* Note: v0 → v19 captures 59 tri-state records (42 success / 13 no-gain / 4 failure); prior 2-round learning cost $0.455 separately. Any snapshot rolls back atomically.",
        fontsize=8.8, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    save_fig(fig, out_dir / f"self-evolution-loop-{lang}.png")


def plot_routing_ablation(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    zh = lang == "zh"
    fig, (ax1, ax2, ax3) = plt.subplots(
        1, 3, figsize=(16.0, 5.2), gridspec_kw={"width_ratios": [1.02, 1.02, 1.26]}
    )
    fig.patch.set_facecolor(BG)

    variants = [
        ("Decisions / Decisions\n(双决策)" if zh else "Decisions / Decisions\n(Dual)"),
        ("LLM / Decisions\n(模型决策)" if zh else "LLM / Decisions\n(Model)"),
        ("LLM / rule\n(默认基线)" if zh else "LLM / rule\n(Baseline)"),
        ("Decisions / rule\n(动作决策)" if zh else "Decisions / rule\n(Action)"),
    ]
    colors = [AMBER, INDIGO, NAVY, TEAL]
    gains = [0.51, 5.84, 5.97, 6.15]
    scores = [132540, 139559, 139736, 139972]
    times = [112.9, 389.9, 392.0, 389.4]
    small_r = np.array([6, 7, 3, 2])
    large_r = np.array([0, 4, 6, 5])
    dec_r = np.array([13, 8, 0, 7])
    pass_lbl = ["6/6", "6/6", "5/5", "7/7"]
    y = np.arange(len(variants))

    # Panel A: Final Score Gain & Box-Movement Energy Reduction
    style_ax(ax1, "x")
    bars = ax1.barh(y, gains, height=0.55, color=colors)
    for i, (rect, g, s) in enumerate(zip(bars, gains, scores)):
        note = f"+{g:.2f}%  ({s:,})"
        if i == 3:
            note += "\n箱搬运代价 −44.7%" if zh else "\nBox cost −44.7%"
        ax1.text(
            g + 0.18, rect.get_y() + rect.get_height() / 2, note,
            va="center", fontsize=8.8,
            color=TEAL if i == 3 else NAVY,
            fontproperties=bold_fp if i == 3 else reg_fp
        )
    ax1.set_yticks(y, variants, fontsize=9.3, fontproperties=bold_fp)
    ax1.set_xlim(0, 11.2)
    ax1.set_xlabel("相对 c0 最终得分提升（%）" if zh else "Final Score Gain vs. c0 (%)", fontsize=10, fontproperties=bold_fp)
    ax1.set_title("最终质量（c0 = 131,864）" if zh else "Final Score (c0 = 131,864)", loc="left", fontsize=12, pad=30, fontproperties=bold_fp)

    # Panel B: Latency vs Score Gain Pareto
    style_ax(ax2, "both")
    ax2.grid(axis="both", color=GRID_COLOR, linestyle="-", linewidth=0.7, alpha=0.55)
    short_names = [
        ("双决策（早停 −71.2%）" if zh else "Dual Decisions (−71.2% time)"),
        ("模型决策" if zh else "Model Decisions"),
        ("默认基线" if zh else "Baseline (LLM/rule)"),
        ("动作决策" if zh else "Action Decisions"),
    ]
    offsets = [
        (20, 16),     # Dual -> clean upper right with single arrow
        (-28, -32),   # Model -> below left
        (-102, -3),   # Baseline -> left
        (-86, 22),    # Action -> upper left
    ]
    for i in range(4):
        ax2.scatter(times[i], gains[i], s=135 if i in (0, 3) else 95, color=colors[i], edgecolor="white", linewidth=1.4, zorder=4)
        ax2.annotate(
            f"{short_names[i]}\n{times[i]:.1f}s · +{gains[i]:.2f}%",
            xy=(times[i], gains[i]),
            xytext=offsets[i],
            textcoords="offset points",
            fontsize=8.6,
            color=colors[i],
            fontproperties=bold_fp if i in (0, 3) else reg_fp,
            arrowprops={"arrowstyle": "-", "color": colors[i], "lw": 0.9, "alpha": 0.75},
        )
    ax2.set_xlim(70, 445)
    ax2.set_ylim(-0.35, 7.6)
    ax2.set_xlabel("单轮总耗时（含 final，秒）" if zh else "Total Wall Time incl. Final (s)", fontsize=10, fontproperties=bold_fp)
    ax2.set_ylabel("得分提升（%）" if zh else "Score Gain (%)", fontsize=10, fontproperties=bold_fp)
    ax2.set_title("预算下时间–质量权衡" if zh else "Time vs. Quality Trade-off", loc="left", fontsize=12, pad=30, fontproperties=bold_fp)

    # Panel C: Stacked Request Mix against 20-request cap
    style_ax(ax3, "x")
    ax3.barh(y, small_r, height=0.55, color="#64748B", label="轻量 Qwen" if zh else "Small (Qwen)")
    ax3.barh(y, large_r, left=small_r, height=0.55, color=INDIGO, label="强模型 Sol" if zh else "Large (Sol)")
    ax3.barh(y, dec_r, left=small_r + large_r, height=0.55, color=AMBER, label="Decisions 决策" if zh else "Decisions")
    ax3.axvline(20, color=CRIMSON, linestyle="--", linewidth=1.2, alpha=0.75, zorder=2)
    ax3.text(
        20.0, 3.55, "20 次上限" if zh else "20 req cap",
        ha="center", va="bottom", fontsize=8.3, color=CRIMSON, fontproperties=bold_fp,
        bbox={"boxstyle": "round,pad=0.12", "facecolor": BG, "edgecolor": "none", "alpha": 0.95},
        zorder=4,
    )

    totals = small_r + large_r + dec_r
    for i in range(4):
        if small_r[i] > 0:
            ax3.text(small_r[i] / 2, i, str(small_r[i]), ha="center", va="center", color="white", fontsize=8.8, fontproperties=bold_fp)
        if large_r[i] > 0:
            ax3.text(small_r[i] + large_r[i] / 2, i, str(large_r[i]), ha="center", va="center", color="white", fontsize=8.8, fontproperties=bold_fp)
        if dec_r[i] > 0:
            ax3.text(small_r[i] + large_r[i] + dec_r[i] / 2, i, str(dec_r[i]), ha="center", va="center", color="white", fontsize=8.8, fontproperties=bold_fp)

        if i == 3:
            text_x = 20.6
            extra = f"14 req · 通过 7/7\n路由占 2.26% USD" if zh else "14 req · 7/7 pass\nRouting 2.26% USD"
        elif totals[i] == 19:
            text_x = 20.6
            extra = f"19 req · 通过 {pass_lbl[i]}" if zh else f"19 req · {pass_lbl[i]} pass"
            if i == 0:
                extra += " (0 Sol)"
        else:
            text_x = totals[i] + 0.55
            extra = f"9 req · 通过 {pass_lbl[i]}" if zh else f"9 req · {pass_lbl[i]} pass"

        ax3.text(
            text_x, i, extra, va="center", fontsize=8.5,
            color=TEAL if i == 3 else NAVY,
            fontproperties=bold_fp if i == 3 else reg_fp
        )

    ax3.set_yticks(y, [""] * 4)
    ax3.set_ylim(-0.58, 3.82)
    ax3.set_xlim(0, 31.8)
    ax3.set_xlabel("HTTP 请求次数构成（含决策请求）" if zh else "HTTP Request Breakdown", fontsize=10, fontproperties=bold_fp)
    ax3.set_title("请求分配与候选通过率" if zh else "Request Mix & Candidate Pass Rate", loc="left", fontsize=12, pad=30, fontproperties=bold_fp)
    ax3.legend(
        loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=3,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=8.4,
        columnspacing=1.0, handletextpad=0.5
    )

    fig.suptitle(
        "ALE-Bench ahc026 动作与模型四组路由消融（15 例隐藏最终集）" if zh else "ALE-Bench ahc026 Four-Way Action × Model Routing Ablation (15 Final Cases)",
        x=0.012, y=1.03, ha="left", fontsize=14.5, fontproperties=bold_fp
    )
    fig.text(
        0.012, -0.02,
        "统一预算：360s / 20 总请求 / 10 候选 · 每组从 v0 运行 1 次；另固定 Qwen 15 轮正式消融中 60/96 (62.5%) 过 dev，15/15 过 final。"
        if zh else
        "Unified cap: 360s / 20 HTTP req / 10 candidates (1 run/arm from v0). Separately, in 15 fixed-Qwen ALE runs, 60/96 (62.5%) passed dev and 15/15 passed final.",
        fontsize=8.8, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    save_fig(fig, out_dir / f"routing-ablation-ahc026-{lang}.png")


def plot_algotune(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    zh = lang == "zh"
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(15.2, 4.5), gridspec_kw={"width_ratios": [1.0, 1.38]}
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

    # Panel A: Log-axis dumbbell latency reduction
    style_ax(ax1, "x")
    ax1.set_xscale("log")
    for i in range(4):
        ax1.annotate(
            "", xy=(best_ms[i], i), xytext=(base_ms[i], i),
            arrowprops={"arrowstyle": "->", "color": colors[i], "lw": 2.4}
        )
        ax1.scatter(base_ms[i], i, s=85, facecolor=CARD_BG, edgecolor=SLATE, linewidth=2.0, zorder=4)
        ax1.scatter(best_ms[i], i, s=100, color=colors[i], edgecolor="white", linewidth=1.2, zorder=5)
        ax1.text(base_ms[i] * 1.13, i, f"{base_ms[i]:.2f} ms", va="center", ha="left", fontsize=8.7, color=SLATE)
        ax1.text(best_ms[i] * 0.87, i, f"{best_ms[i]:.2f} ms", va="center", ha="right", fontsize=8.9, color=colors[i], fontproperties=bold_fp)

    ax1.set_yticks(y, rows, fontsize=9.8, fontproperties=bold_fp)
    ax1.set_xlim(0.18, 28.0)
    ax1.set_xticks([0.3, 0.5, 1.0, 3.0, 10.0], ["0.3", "0.5", "1.0", "3.0", "10.0"])
    ax1.set_xlabel("两例 dev 总执行中位耗时（毫秒，对数轴）" if zh else "Median Solve Time (2 dev cases, ms, log scale)", fontsize=10, fontproperties=bold_fp)
    ax1.set_title("基线（空心）→ 最佳候选（实心）耗时" if zh else "Baseline (hollow) → Best (solid) Latency", loc="left", fontsize=12, pad=10, fontproperties=bold_fp)

    # Panel B: Speedup bars + Algorithmic change summary
    style_ax(ax2, "x")
    bars = ax2.barh(y, speedup, height=0.55, color=colors)
    for i, (rect, sp, ch) in enumerate(zip(bars, speedup, changes)):
        ax2.text(
            sp + 0.65, rect.get_y() + rect.get_height() / 2,
            f"{sp:.2f}×  |  {ch}",
            va="center", fontsize=9.0,
            color=colors[i] if i >= 2 else NAVY,
            fontproperties=bold_fp if i >= 2 else reg_fp
        )
    ax2.set_yticks(y, [""] * 4)
    ax2.set_xlim(0, 63.0)
    ax2.set_xlabel("相对参考实现的执行加速比（×）" if zh else "Speedup vs. Paired Reference (×)", fontsize=10, fontproperties=bold_fp)
    ax2.set_title("加速倍数与核心算法改写" if zh else "Speedup & Key Algorithmic Breakthrough", loc="left", fontsize=12, pad=10, fontproperties=bold_fp)

    fig.suptitle(
        "AlgoTune 函数级优化探索（gpt-6.1-sol · Mac 2-case Dev）" if zh else "Exploratory AlgoTune Optimization (gpt-6.1-sol · Mac 2-Case Dev)",
        x=0.012, y=1.02, ha="left", fontsize=14.5, fontproperties=bold_fp
    )
    fig.text(
        0.012, -0.02,
        "口径：每项上限 180s / 5 请求 / 3 候选，2 个 dev 输入 × 5 次交替计时取中位数（关闭 final 评测；本批估算费用 USD 0.336）。"
        if zh else
        "Scope: 180s / 5 req / 3 candidates per run, 2 dev inputs × 5 repeats (final disabled; audited Mac OpenAI subtotal USD 0.336).",
        fontsize=8.8, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    save_fig(fig, out_dir / f"algotune-speedups-{lang}.png")


def plot_experience_comparison(lang: str, out_dir: Path, reg_fp, bold_fp) -> None:
    zh = lang == "zh"
    fig, (ax1, ax2, ax3) = plt.subplots(
        1, 3, figsize=(16.0, 5.2), gridspec_kw={"width_ratios": [1.0, 1.0, 1.05]}
    )
    fig.patch.set_facecolor(BG)

    batches = [
        ("C 批 · 纯文字\nv0 → v6" if zh else "C-Batch · Text\nv0 → v6"),
        ("D 批 · 程序复用\nv0 → v19" if zh else "D-Batch · Reuse\nv0 → v19"),
        ("S 任务流 · 分流\n无记忆 → 在线" if zh else "S-Stream · Triage\nFresh → Online"),
    ]
    x = np.arange(3)
    w = 0.34

    # Panel A: Median Speedup Before vs After + Target attainment
    style_ax(ax1, "y")
    sp_before = [1.41, 1.20, 1.86]
    sp_after = [1.29, 1.73, 1.86]
    ax1.bar(x - w / 2, sp_before, width=w, color=GRAY_BAR)
    ax1.bar(x + w / 2, sp_after, width=w, color=[CRIMSON, TEAL, TEAL])
    pass_notes = ["16/18 → 16/18", "15/18 → 18/18", "36/36 → 36/36"]
    delta_notes = ["−8.5% 退步" if zh else "−8.5% drop", "+44.2%", "稳定保持" if zh else "Sustained"]

    for i in range(3):
        ax1.text(x[i] - w / 2, sp_before[i] + 0.04, f"{sp_before[i]:.2f}×", ha="center", va="bottom", fontsize=9.0, color=SLATE)
        c = CRIMSON if i == 0 else TEAL
        ax1.text(x[i] + w / 2, sp_after[i] + 0.04, f"{sp_after[i]:.2f}×", ha="center", va="bottom", fontsize=9.2, color=c, fontproperties=bold_fp)
        ax1.text(x[i], max(sp_before[i], sp_after[i]) + 0.21, f"{delta_notes[i]}\n({pass_notes[i]})", ha="center", va="bottom", fontsize=8.3, color=c if i != 2 else NAVY, fontproperties=bold_fp)

    ax1.set_xticks(x, batches, fontsize=9.2, fontproperties=bold_fp)
    ax1.set_ylim(0, 2.48)
    ax1.set_ylabel("最终加速比中位数（×）" if zh else "Median Final Speedup (×)", fontsize=10, fontproperties=bold_fp)
    ax1.set_title("优化质量与达标率" if zh else "Optimization Speedup & Attainment", loc="left", fontsize=12, pad=30, fontproperties=bold_fp)
    ax1.legend(
        handles=[
            Patch(facecolor=GRAY_BAR, label="对照前" if zh else "Before"),
            Patch(facecolor=TEAL, label="正收益" if zh else "Improved"),
            Patch(facecolor=CRIMSON, label="退步" if zh else "Drop"),
        ],
        loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=3,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=8.4,
        columnspacing=0.9, handletextpad=0.45
    )

    # Panel B: Cloud USD Spend & GPT Requests
    style_ax(ax2, "y")
    usd_before = [0.372, 0.376, 0.402]
    usd_after = [0.292, 0.000, 0.086]
    gpt_notes = ["GPT 升级 11→5", "GPT 7→0\n(总请求 52→0)", "GPT −78%\n(27→6)"] if zh else ["GPT 11→5", "GPT 7→0\n(52→0 total)", "GPT −78%\n(27→6)"]

    ax2.bar(x - w / 2, usd_before, width=w, color=GRAY_BAR)
    ax2.bar(x + w / 2, usd_after, width=w, color=TEAL)
    for i in range(3):
        ax2.text(x[i] - w / 2, usd_before[i] + 0.01, f"${usd_before[i]:.3f}", ha="center", va="bottom", fontsize=8.6, color=SLATE)
        lbl = f"${usd_after[i]:.3f}*" if i == 1 else f"${usd_after[i]:.3f}"
        ax2.text(x[i] + w / 2, usd_after[i] + 0.01, lbl, ha="center", va="bottom", fontsize=9.0, color=TEAL, fontproperties=bold_fp)
        ax2.text(x[i], max(usd_before[i], usd_after[i]) + 0.048, gpt_notes[i], ha="center", va="bottom", fontsize=8.4, color=NAVY, fontproperties=bold_fp)

    ax2.set_xticks(x, batches, fontsize=9.2, fontproperties=bold_fp)
    ax2.set_ylim(0, 0.54)
    ax2.set_ylabel("模型估算费用（USD）" if zh else "Estimated Model Cost (USD)", fontsize=10, fontproperties=bold_fp)
    ax2.set_title("云端大模型费用与请求锐减" if zh else "Frontier Spend & Request Collapse", loc="left", fontsize=12, pad=30, fontproperties=bold_fp)
    ax2.legend(
        handles=[
            Patch(facecolor=GRAY_BAR, label="对照前费用" if zh else "Before Spend"),
            Patch(facecolor=TEAL, label="加入经验后" if zh else "With Experience"),
        ],
        loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=8.4,
        columnspacing=1.0, handletextpad=0.5
    )

    # Panel C: Total Runtime & Median Loop Time
    style_ax(ax3, "y")
    tot_before = [2000, 1782, 1486]
    tot_after = [1886, 669, 1064]
    med_notes = ["中位 84s→50s", "−62.5%\n中位 53s→27s", "−28.4%\n中位 31.2→14.3s"] if zh else ["Med 84s→50s", "−62.5%\nMed 53s→27s", "−28.4%\nMed 31.2→14.3s"]

    ax3.bar(x - w / 2, tot_before, width=w, color=GRAY_BAR)
    ax3.bar(x + w / 2, tot_after, width=w, color=TEAL)
    for i in range(3):
        ax3.text(x[i] - w / 2, tot_before[i] + 35, f"{tot_before[i]}s", ha="center", va="bottom", fontsize=8.6, color=SLATE)
        ax3.text(x[i] + w / 2, tot_after[i] + 35, f"{tot_after[i]}s", ha="center", va="bottom", fontsize=9.0, color=TEAL, fontproperties=bold_fp)
        ax3.text(x[i], max(tot_before[i], tot_after[i]) + 175, med_notes[i], ha="center", va="bottom", fontsize=8.4, color=TEAL, fontproperties=bold_fp)

    ax3.set_xticks(x, batches, fontsize=9.2, fontproperties=bold_fp)
    ax3.set_ylim(0, 2500)
    ax3.set_ylabel("整批总耗时（秒）" if zh else "Total Batch Wall Time (s)", fontsize=10, fontproperties=bold_fp)
    ax3.set_title("总耗时与单轮循环时长收敛" if zh else "Batch & Median Loop Time Reduction", loc="left", fontsize=12, pad=30, fontproperties=bold_fp)
    ax3.legend(
        handles=[
            Patch(facecolor=GRAY_BAR, label="对照前耗时" if zh else "Before Total"),
            Patch(facecolor=TEAL, label="加入经验后" if zh else "With Experience"),
        ],
        loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2,
        frameon=True, facecolor=CARD_BG, edgecolor=BORDER, fontsize=8.4,
        columnspacing=1.0, handletextpad=0.5
    )

    fig.suptitle(
        "跨任务经验复用与在线分流受控对照（同权重 · 同提示词 · 同评测器 · 仅切换经验快照）"
        if zh else
        "Controlled Experience Memory Ablations (Identical Weights, Prompts & Judge — Snapshot Only)",
        x=0.012, y=1.03, ha="left", fontsize=14.3, fontproperties=bold_fp
    )
    fig.text(
        0.012, -0.02,
        "* D 批留出端实现 18/18 零模型交付，前置两轮学习费用 $0.455 单列；S 任务流（v19 起点，12 任务 × 3 重放）所有后续同族任务 30/30 零模型交付。"
        if zh else
        "* D-Batch held-out achieved 18/18 zero-LLM delivery while prior two-round learning ($0.455) is tracked separately; S-Stream resolved all 30/30 follow-up tasks without LLMs.",
        fontsize=8.8, color=MUTED
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    save_fig(fig, out_dir / f"experience-memory-comparison-{lang}.png")


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
        plot_self_evolution(lang, args.out_dir, reg_fp, bold_fp)
        plot_routing_ablation(lang, args.out_dir, reg_fp, bold_fp)
        plot_algotune(lang, args.out_dir, reg_fp, bold_fp)
        plot_experience_comparison(lang, args.out_dir, reg_fp, bold_fp)
    print(f"Generated 8 README charts in {args.out_dir}")


if __name__ == "__main__":
    main()
