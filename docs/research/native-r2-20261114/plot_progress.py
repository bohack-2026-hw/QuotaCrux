"""Render the stored pilot's best-so-far curves; no model or evaluator calls."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator


def main():
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path, help="contains manifest.json and comparison.json")
    args = p.parse_args()
    manifest = json.loads((args.directory / "manifest.json").read_text())
    comparison = json.loads((args.directory / "comparison.json").read_text())
    rates = manifest["pricing"]["price"]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
    colors = {"feedback": "#086e7d", "independent": "#be592b"}
    for run in comparison["runs"]:
        row = 0 if run["task_id"].startswith("ale-bench") else 1
        progress = run.get("progress", [])
        initial = (run.get("best_dev") or {}).get("objective")
        base = initial["baseline"] if row == 0 and initial else 1.0
        values = [base] + [x["value"] for x in progress]
        usage = [x["usage"] for x in progress]
        times = [0] + [x["elapsed_s"] for x in progress]
        tokens = [0] + [(u["input_tokens"] or 0) + (u["output_tokens"] or 0) for u in usage]
        costs = [0] + [((u["input_tokens"] or 0) * rates["input_price_range"][0]
                       + (u["output_tokens"] or 0) * rates["output_price_range"][0]) / 1e6 for u in usage]
        times += [run["timing"]["agent_loop_s"]]
        tokens += [(run["usage"]["input_tokens"] or 0) + (run["usage"]["output_tokens"] or 0)]
        costs += [run["estimated_cny"]]
        values += [values[-1]]
        for col, xs in enumerate((times, tokens, costs)):
            ax = axes[row, col]
            ax.step(xs, values, where="post", label=run["mode"], color=colors[run["mode"]], linewidth=2,
                    linestyle="-" if run["mode"] == "feedback" else "--", zorder=2 if run["mode"] == "feedback" else 3)
            ax.scatter([xs[-1]], [values[-1]], color=colors[run["mode"]], marker="x", zorder=3)
            ax.set_xlabel(("Research wall time (s)", "Cumulative input + output tokens", "Estimated token cost (CNY)")[col])
            ax.set_ylabel("ALE ahc026: raw dev score" if row == 0 else "AlgoTune convolve_1d: dev speedup")
            ax.grid(alpha=0.2)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.xaxis.set_major_locator(MaxNLocator(5))
            if col == 1:
                ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1000:g}k"))
            ax.legend()
    fig.suptitle("RouteEvo second native pilot: best accepted result within one episode\n2 dev cases; 1 repeat per arm; final evaluation disabled", fontsize=13)
    fig.savefig(args.directory / "progress.svg")
    svg = args.directory / "progress.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    fig.savefig(args.directory / "progress.png", dpi=160)


if __name__ == "__main__":
    main()
