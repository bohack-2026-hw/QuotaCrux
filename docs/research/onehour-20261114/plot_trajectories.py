"""Plot retained development quality against elapsed research time from exported reports."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager
import matplotlib.pyplot as plt

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("summary", type=Path)
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
s = json.loads(a.summary.read_text())
font = "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"
font_manager.fontManager.addfont(font)
plt.rcParams.update({"font.family": font_manager.FontProperties(fname=font).get_name(),
    "font.size": 11, "axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False})
styles = {"fixed_small": ("固定小模型", "#6b7f99"), "fixed_large": ("固定大模型", "#5362b8"),
          "adaptive_rule": ("规则自适应", "#168c80"), "action_decisions": ("Decisions 动作路由", "#cf8231")}
fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.6), sharey=True)
records = []
for ax, host in zip(axes, ["desktop", "laptop"]):
    for variant, (label, color) in styles.items():
        row = next(r for r in s["runs"] if r["host"] == host and r["variant"] == variant)
        rep = json.loads(Path(row["report_path"]).read_text())
        initial = next(c for c in rep["candidates"] if c["candidate_id"] == "c0")
        baseline = initial["dev_evaluations"][0]["objective"]["value"]
        points = [{"elapsed_s": 0, "value": baseline}] + [
            {"elapsed_s": x["elapsed_s"], "value": x["value"]} for x in rep["progress"]]
        points.append({"elapsed_s": row["loop_s"], "value": points[-1]["value"]})
        ax.step([x["elapsed_s"] for x in points], [x["value"] for x in points],
                where="post", color=color, label=label, linewidth=2)
        ax.scatter(points[-1]["elapsed_s"], points[-1]["value"], color=color,
                   marker="x" if row["status"] != "completed" else "o", s=42, zorder=4)
        records.append({"host": host, "variant": variant, "run_id": row["run_id"],
                        "status": row["status"], "development_baseline": baseline, "points": points})
    ax.set(title=host, xlabel="研究循环已用时间（秒）", xlim=(0, 375), ylim=(43950, 47120))
    ax.grid(alpha=.2)
    ax.set_xticks([0, 60, 120, 180, 240, 300, 360])
axes[0].set_ylabel("当前保留的最佳 dev 分数（5 个用例）")
fig.suptitle("同一时间内，当前最好方案有多好？", fontsize=19, fontweight="bold", y=.98)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.5, .085), ncol=4, frameon=False)
fig.text(.07, .025, "只展示 dev 过程；独立 final 结果另见主表。曲线截至实际研究结束，× 标记 API 失败终止。每台每策略仅一次。", fontsize=9, color="#586475")
fig.subplots_adjust(left=.08, right=.98, top=.86, bottom=.25, wspace=.1)
a.out.mkdir(parents=True, exist_ok=True)
for ext in ["png", "svg"]:
    fig.savefig(a.out / ("quality-time." + ext), dpi=180)
(a.out / "development-trajectories.json").write_text(json.dumps({"scope": "retained development quality; no final scores or inferred future trajectory", "runs": records}, ensure_ascii=False, indent=2) + "\n")
