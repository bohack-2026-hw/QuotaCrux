"""Verify and summarize the retained, dev-only ALE calibration evidence."""
from pathlib import Path
import hashlib
import json
import re
import statistics

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"


def read(name):
    return json.loads((EVIDENCE / name).read_text())


def main():
    ledger = read("ledger-audit.json")
    host = read("host.json")
    assert hashlib.sha256((HERE / "preflight.py").read_bytes()).hexdigest() == host["preflight_sha256"]
    records = [json.loads(p.read_text()) for p in sorted((EVIDENCE / "calibration").glob("*.json"))]
    assert len(records) == 24
    actual = {(r["worker"], r["phase"], r["repeat"], r["program"]) for r in records}
    assert actual == {(w, p, n, c) for w in ("a", "b") for p in ("serial", "parallel")
                      for n in (1, 2, 3) for c in ("c0", "cpu_control")}
    groups = []
    for name in ("a", "b"):
        worker = read(f"worker-{name}.json")
        audit = ledger["workers"][name]
        assert worker["manifest_sha256"] == audit["manifest_sha256"]
        assert audit["counts"] == {"tasks": 1, "runs": 0, "model_calls": 0,
                                   "evaluations": 18, "final_evaluations": 0}
        assert audit["locks_released"] == {"run.lock": True, "compare.lock": True}
        for program in ("c0", "cpu_control"):
            source = (EVIDENCE / worker["programs"][program]["file"]).read_bytes()
            digest = hashlib.sha256(source).hexdigest()
            assert digest == worker["programs"][program]["sha256"]
            rows = [r for r in records if r["worker"] == name and r["program"] == program]
            medians = {}
            for phase in ("serial", "parallel"):
                selected = sorted([r for r in rows if r["phase"] == phase], key=lambda r: r["repeat"])
                medians[phase] = []
                for row in selected:
                    ev = row["evaluation"]
                    assert row["candidate_sha256"] == ev["detail"]["candidate_sha256"] == digest
                    assert row["task_id"] == ev["task_id"] == worker["task_id"]
                    assert ev["dataset"] == "dev" and ev["status"] == "passed"
                    assert ev["detail"]["dataset_sha256"] == worker["manifest"]["files"]["dev_input"]["sha256"]
                    assert ev["detail"]["case_count"] == ev["detail"]["passed_cases"] == 5
                    assert len(ev["detail"]["samples"]) == 5
                    assert all(s["status"] == "ok" for s in ev["detail"]["samples"])
                    medians[phase].append(statistics.median(s["elapsed_s"] for s in ev["detail"]["samples"]))
            groups.append({"worker": name, "program": program, "per_repeat_sample_median_s": medians,
                           "paired_parallel_over_serial": [p/s for p, s in zip(medians["parallel"], medians["serial"])]})
        per_case = [r["evaluation"]["detail"]["objective"]["cases"] for r in records if r["worker"] == name]
        assert all(cases == per_case[0] for cases in per_case)
    samples = read("cpu-samples.json")
    utilization = {}
    for cpu in samples[0]["cpu"]:
        delta = [b-a for a,b in zip(samples[0]["cpu"][cpu], samples[-1]["cpu"][cpu])]
        utilization[cpu] = 100 * (sum(delta) - delta[3] - delta[4]) / sum(delta)
    batches = []
    for line in (EVIDENCE / "calibration.log").read_text().splitlines():
        match = re.fullmatch(r"(serial|parallel) r(\d) (c0|cpu_control): ([\d.]+)s", line)
        assert match, line
        phase, repeat, program, seconds = match.groups()
        batches.append({"phase": phase, "repeat": int(repeat), "program": program, "wall_clock_s": float(seconds)})
    assert len(batches) == 12
    serial = sum(b["wall_clock_s"] for b in batches if b["phase"] == "serial")
    parallel = sum(b["wall_clock_s"] for b in batches if b["phase"] == "parallel")
    result = {"status": "passed", "top_level_calibration_evaluations": len(records),
              "persisted_evaluations": sum(w["counts"]["evaluations"] for w in ledger["workers"].values()),
              "additional_c0_reference_evaluations": 12, "model_calls": 0, "final_evaluations": 0,
              "candidate_affinity_verified": True, "candidate_core_exclusive": False,
              "judge_affinity_configured": False, "groups": groups,
              "observed_cpu_busy_percent": utilization, "batches": batches,
              "serial_batch_wall_clock_s": serial, "parallel_batch_wall_clock_s": parallel,
              "batch_wall_clock_ratio_parallel_over_serial": parallel / serial,
              "notes": ["Raw candidate_cpu_isolation means candidate affinity only; CPU exclusivity was not configured.",
                        "Raw evaluations=24 counts top-level calls; cpu_control also evaluates c0, yielding 36 DB rows.",
                        "Control programs retain c0 output; scores do not test time-limited search quality."]}
    (EVIDENCE / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("groups", "batches", "notes")}, indent=2))


if __name__ == "__main__":
    main()
