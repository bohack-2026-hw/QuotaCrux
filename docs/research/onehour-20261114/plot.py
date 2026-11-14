"""Render host-stratified final quality and request accounting from summary.json."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("summary", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--font", type=Path, default=Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"))
    args = p.parse_args()
    data = json.loads(args.summary.read_text())
    font_manager.fontManager.addfont(str(args.font))
    plt.rcParams.update({"font.family": font_manager.FontProperties(fname=str(args.font)).get_name(),
        "font.size": 11, "axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False})
    variants = ["fixed_small", "fixed_large", "adaptive_rule", "action_decisions"]
    labels = ["固定小模型", "固定大模型", "自适应路由", "Decisions\n动作路由"]
    colors = ["#6b7f99", "#5362b8", "#168c80", "#cf8231"]
    hosts = [h for h in ("desktop", "laptop") if h in data["hosts"]]
    if len(hosts) != 2:
        raise ValueError("the overview requires both host blocks")
    observed = [r["gain_percent"] for r in data["runs"] if r.get("gain_percent") is not None]
    ymax = max(1, max(observed, default=1) * 1.22)
    ymin = min(0, min(observed, default=0) * 1.2)
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.3), gridspec_kw={"height_ratios": [1.1, 1]})
    fig.patch.set_facecolor("#fafbfD")
    x = np.arange(4)
    for col, host in enumerate(hosts):
        rows = {r["variant"]: r for r in data["runs"] if r["host"] == host}
        top, bottom = axes[0, col], axes[1, col]
        for ax in (top, bottom):
            ax.set_axisbelow(True)
            ax.grid(axis="y", alpha=.17)
            ax.set_xticks(x, labels)
            ax.set_xlim(-.6, 3.6)
            ax.tick_params(axis="x", length=0, labelsize=10)
            ax.spines["left"].set_alpha(.25)
            ax.spines["bottom"].set_alpha(.25)
        for i, variant in enumerate(variants):
            row = rows[variant]
            value = row.get("gain_percent")
            if value is None:
                top.text(i, ymax * .06, "未完成 final", ha="center", fontsize=9, color="#a23b36")
            else:
                failed = row["status"] != "completed"
                top.bar(i, value, color=colors[i], width=.62, hatch="//" if failed else None)
                top.text(i, value + ymax * .025, f"{value:+.2f}%", ha="center", fontsize=12, fontweight="bold")
                top.text(i, value + ymax * .095, f"{row['final_score']:,.0f}" + ("†" if failed else ""), ha="center", fontsize=9, color="#586475")
        top.set_ylim(ymin, ymax)
        top.set_title(host + " · final 质量", loc="left", fontsize=14, pad=16, fontweight="bold")
        top.set_ylabel("相对初始程序的分数提升（%）")
        lower = np.zeros(4)
        for role, label, color in [("small", "小模型", "#8b9cb2"), ("large", "大模型", "#5362b8"),
                                    ("router_action", "动作路由", "#cf8231")]:
            counts = [rows[v].get("usage_by_role", {}).get(role, {}).get("requests", 0) for v in variants]
            bottom.bar(x, counts, bottom=lower, width=.62, label=label, color=color)
            lower += np.array(counts)
        for i, variant in enumerate(variants):
            row = rows[variant]
            if row.get("requests") is not None:
                bottom.text(i, lower[i] + .45, str(row["requests"]), ha="center", fontsize=11)
        bottom.set_ylim(0, 22)
        bottom.set_yticks([0, 5, 10, 15, 20])
        bottom.axhline(20, color="#a7acb4", linestyle="--", linewidth=1)
        bottom.set_ylabel("模型请求数（含路由）")
        bottom.set_title("请求构成", loc="left", fontsize=13, pad=12)
    axes[1, 1].legend(loc="upper left", bbox_to_anchor=(.03, -.2), ncol=3, frameon=False, fontsize=10)
    fig.suptitle("模型选择的质量与请求开销", fontsize=22, fontweight="bold", x=.07, ha="left", y=.98)
    fig.text(.07, .928, "ahc026 · 每台每策略 1 轮 · 360 秒 / 20 请求 / 10 候选 · 5 dev + 15 final", color="#586475", fontsize=11)
    fig.text(.07, .025, "按主机分别比较；不合并运行时间。† 研究因 API 错误结束，冻结候选仍通过 final。\n另有 1 次会话中断尝试单列，未混入质量对照；完整请求与双币种成本见报告。", color="#586475", fontsize=9.5)
    fig.subplots_adjust(left=.07, right=.98, bottom=.16, top=.85, hspace=.5, wspace=.22)
    args.out.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(args.out / f"quality-requests.{ext}", dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    main()
