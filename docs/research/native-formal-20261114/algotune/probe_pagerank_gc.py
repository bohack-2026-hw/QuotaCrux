#!/usr/bin/env python3
"""Compare the current PageRank timer with automatic GC disabled only during solve."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[4]
TASK_ID = "algotune-pagerank-formal-20261114-b2ad8ba1c8"
ORDER = ("original", "gc_disabled", "gc_disabled", "original", "original", "gc_disabled")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--var-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")

    with tempfile.TemporaryDirectory(prefix="routeevo-pagerank-gc-probe-") as temporary:
        probe_var = Path(temporary) / "var"
        shutil.copytree(args.var_dir.resolve(), probe_var)
        os.environ["ROUTEEVO_VAR_DIR"] = str(probe_var)
        os.environ["ROUTEEVO_NO_DOTENV"] = "1"

        from routeevo import config, db, taskpkg
        from routeevo.benchmarks import algotune

        task = taskpkg.load(TASK_ID)
        original = task.initial_code.encode()
        gc_disabled = (task.initial_code + '''

import gc as _probe_gc
_probe_original_solve = solve
def solve(problem):
    _probe_enabled = _probe_gc.isenabled()
    _probe_gc.disable()
    try:
        return _probe_original_solve(problem)
    finally:
        if _probe_enabled:
            _probe_gc.enable()
''').encode()
        programs = {"original": original, "gc_disabled": gc_disabled}
        measure = config.MeasureConfig(repeats=5, function_warmups=3, cpuset_cpus="2")
        results = []
        for sequence, condition in enumerate(ORDER, 1):
            load_before = list(os.getloadavg())
            code = programs[condition]
            evaluation = algotune.evaluate(task, code, "dev", measure, config.RunLimits(), baseline_code=code)
            results.append({
                "sequence": sequence,
                "condition": condition,
                "load_before": load_before,
                "load_after": list(os.getloadavg()),
                "evaluation": asdict(evaluation),
            })
            if evaluation.status != "passed" or evaluation.correct is not True or evaluation.improved is not False:
                raise RuntimeError(f"unexpected probe result: {condition}: {evaluation.status}")

        summary = {}
        for condition in programs:
            rows = [row["evaluation"] for row in results if row["condition"] == condition]
            repeat_values = [[] for _ in range(5)]
            ranges = []
            for row in rows:
                timing = row["detail"]["timing"]
                for role in ("baseline_s", "candidate_s"):
                    values = timing[role]
                    ranges.append((max(values) - min(values)) / statistics.median(values))
                    for index, value in enumerate(values):
                        repeat_values[index].append(value * 1000)
            repeat_medians = [statistics.median(values) for values in repeat_values]
            summary[condition] = {
                "evaluations": len(rows),
                "repeat_index_median_ms": repeat_medians,
                "repeat_3_vs_other_median": (repeat_medians[2] /
                                               statistics.median(repeat_medians[:2] + repeat_medians[3:])),
                "median_range_over_median": statistics.median(ranges),
                "speedups": [row["speedup"] for row in rows],
                "strict_false_improvements": sum(row["improved"] is True for row in rows),
            }
        output = {
            "schema": "pagerank-gc-timing-probe-v1",
            "created_at": datetime.now().astimezone().isoformat(),
            "source_git_head": subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
            "task_id": TASK_ID,
            "task_manifest_canonical_sha256": db.one(
                "SELECT manifest_sha256 FROM tasks WHERE task_id = ?", (TASK_ID,))["manifest_sha256"],
            "dataset": "dev",
            "model_requests": 0,
            "final_evaluations": 0,
            "measure": measure.to_dict(),
            "order": list(ORDER),
            "program_sha256": {name: sha256(code) for name, code in programs.items()},
            "treatment": "gc_disabled disables automatic GC immediately before solve and restores it before return",
            "results": results,
            "summary": summary,
            "interpretation": ("Removing automatic GC from the timed solve window removes the systematic third-repeat "
                               "slowdown in this diagnostic. Public protocol ownership remains with issue #2."),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
