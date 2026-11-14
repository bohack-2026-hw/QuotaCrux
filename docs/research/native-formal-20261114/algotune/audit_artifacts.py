#!/usr/bin/env python3
"""Verify the committed AlgoTune Mac preflight without reading sealed task inputs."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPECTED_TASKS = {
    "convolve_1d": ("algotune-convolve_1d-formal-20261114-82a6fac682",
                    "bc00cd13960442ea34b0bb08a152eb9a0b95ab1f23faa97b4f24252944febfd9"),
    "pagerank": ("algotune-pagerank-formal-20261114-b2ad8ba1c8",
                 "61ab8297dfa51ccce5c79a77bc7dafe074bb6fa41936f7065b4ccbbe024994f4"),
}


def load(path: str) -> dict:
    return json.loads((HERE / path).read_text())


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_checksums() -> int:
    listed = set()
    for line in (HERE / "SHA256SUMS").read_text().splitlines():
        expected, relative = line.split("  ", 1)
        path = HERE / relative
        check(path.is_file(), f"missing checksum target: {relative}")
        check(digest(path) == expected, f"checksum mismatch: {relative}")
        listed.add(relative)
    actual = {str(path.relative_to(HERE)) for path in HERE.rglob("*")
              if path.is_file() and path.name != "SHA256SUMS"}
    check(listed == actual, f"checksum file set mismatch: missing={actual - listed}, extra={listed - actual}")
    return len(listed)


def main() -> None:
    checksum_count = verify_checksums()
    host = load("evidence/host.json")
    ledger = load("evidence/ledger-audit.json")
    audit = load("evidence/audit.json")
    timing = load("evidence/timing-observation.json")
    gc_probe = load("evidence/pagerank-gc-probe.json")
    plan = load("proposed-run-plan.json")

    check(host["docker"]["native_architecture"] is True, "Docker server is not native arm64")
    check(host["docker"]["server_architecture"] == "aarch64", "unexpected Docker architecture")
    check(host["affinity_scope"]["physical_apple_core_mapping"] is None,
          "evidence must not claim a Docker-vCPU-to-Apple-core mapping")
    check(host["affinity_scope"]["physical_core_exclusive"] is False,
          "evidence must not claim physical core exclusivity")
    check(host["formal_model"]["model_requests"] == 0 and host["local_qwen"]["model_requests"] == 0,
          "preflight must not contain model calls")

    check(ledger["integrity_check"] == "ok" and ledger["foreign_key_violations"] == 0,
          "SQLite audit failed")
    check(ledger["counts"]["tasks"] == 2 and ledger["counts"]["runs"] == 0,
          "unexpected task or run count")
    check(ledger["model_requests"] == 0 and ledger["final_evaluations"] == 0,
          "model or final work occurred during preflight")
    check(ledger["dev_evaluations"] == 24, "expected 24 retained dev calibration evaluations")
    check(ledger["evaluation_counts"] == [{"count": 24, "dataset": "dev", "status": "passed"}],
          "calibration ledger is incomplete")
    check(not any(ledger["locks"].values()) and not ledger["routeevo_containers"],
          "lock or RouteEvo container remained after calibration")

    for problem, (task_id, manifest_sha) in EXPECTED_TASKS.items():
        worker = load(f"evidence/worker-{problem}.json")
        calibration = load(f"evidence/calibration-{problem}.json")
        check(worker["task_id"] == task_id and worker["manifest_canonical_sha256"] == manifest_sha,
              f"task identity mismatch: {problem}")
        check(worker["sqlite_manifest_matches_disk"] and worker["package_files_verified"],
              f"task package verification failed: {problem}")
        check(all(meta["sha256"] == meta["observed_sha256"]
                  for meta in worker["package_files"].values()), f"package hash mismatch: {problem}")
        check(worker["manifest"]["selection"] == {"dev_cases": 5, "final_cases": 15},
              f"case counts changed: {problem}")
        check(len(worker["workload_profiles"]["dev"]["cases"]) == 5 and
              worker["workload_profiles"]["final"] == {
                  "case_count": 15,
                  "details_published": False,
                  "input_sha256": worker["manifest"]["files"]["final_input"]["sha256"],
                  "source": "sealed_final_input",
              },
              f"workload profile is incomplete: {problem}")
        check(worker["candidate_image"]["architecture"] == "arm64" and
              worker["judge_image"]["architecture"] == "arm64", f"emulated image: {problem}")
        check(calibration["status"] == "completed" and calibration["dataset"] == "dev",
              f"calibration did not complete: {problem}")
        check(calibration["task_id"] == task_id and
              calibration["task_manifest_canonical_sha256"] == manifest_sha,
              f"calibration task mismatch: {problem}")
        check(calibration["model_requests"] == 0 and len(calibration["results"]) == 8,
              f"calibration matrix mismatch: {problem}")
        check(calibration["measures"]["pinned"]["repeats"] == 5 and
              calibration["measures"]["pinned"]["function_warmups"] == 3,
              f"measurement protocol mismatch: {problem}")
        check(all(row["evaluation"]["status"] == "passed" and row["expected_outcome_observed"]
                  for row in calibration["results"]), f"unexpected calibration outcome: {problem}")
        check(sum(row["evaluation"]["improved"] is True for row in calibration["results"]
                  if row["kind"] == "self") == 0, f"self comparison was falsely selected: {problem}")
        controls = {row["kind"]: row for row in calibration["results"] if row["kind"] != "self"}
        check(controls["positive_control"]["evaluation"]["improved"] is True and
              controls["negative_control"]["evaluation"]["improved"] is False,
              f"controls did not separate: {problem}")
        check(calibration["affinity_probe"]["requested_affinity"] == [2] and
              all(value == [2] for value in calibration["affinity_probe"]["observed_affinities"]),
              f"Docker VM affinity mismatch: {problem}")

    failed_path = HERE / "evidence/calibration-convolve_1d-attempt1-failed.json"
    insufficient = load("evidence/calibration-pagerank-attempt1-insufficient-control.json")
    check(load(str(failed_path.relative_to(HERE)))["status"] == "failed",
          "failed path attempt was not retained")
    check(insufficient["status"] == "completed" and
          insufficient["summary"]["controls"][0]["expected_outcome_observed"] is False,
          "insufficient PageRank control attempt is not represented accurately")

    runs = plan["runs"]
    check(plan["status"] == "proposal-awaiting-issue-2-freeze-and-timing-recalibration" and len(runs) == 15,
          "run plan must remain a 15-run proposal")
    check([row["sequence"] for row in runs] == list(range(1, 16)), "run sequences are not contiguous")
    actual = Counter((row["problem"], row["mode"]) for row in runs)
    expected = Counter({("convolve_1d", "feedback"): 3,
                        ("convolve_1d", "independent"): 3,
                        ("convolve_1d", "no_feedback"): 3,
                        ("pagerank", "feedback"): 3,
                        ("pagerank", "independent"): 3})
    check(actual == expected, f"run matrix mismatch: {actual}")
    check(plan["experiment_sha"] is None and plan["prompt_hashes"] is None and
          plan["price_snapshot"] is None, "proposal incorrectly claims public freeze data")
    check(plan["execution"]["concurrency"] == 1, "timing-sensitive plan must stay serial")

    check(audit["formal_progress"] == {"completed": 0, "total": 15}, "formal progress is incorrect")
    check(audit["status"] == "environment-ready-calibration-provisional" and
          audit["recommendation"]["accepted_for_freeze"] is False and
          audit["recommendation"]["recalibration_required"] is True,
          "audit must keep the noisy calibration provisional")
    check(audit["final_inputs_executed"] is False and audit["model_requests"] == 0,
          "audit incorrectly claims formal execution")
    check(all(row["all_expected_outcomes_observed"] for row in audit["calibrations"].values()),
          "accepted calibration summary contains a failed expectation")
    check(timing["accepted_for_freeze"] is False and timing["recalibration_required"] is True,
          "timing observation must block freeze")
    check(timing["tasks"]["pagerank"]["repeat_3_vs_other_median"] > 1.5,
          "systematic PageRank timing observation disappeared")
    check(gc_probe["model_requests"] == 0 and gc_probe["final_evaluations"] == 0,
          "GC probe must remain dev-only and model-free")
    check(gc_probe["summary"]["original"]["evaluations"] == 3 and
          gc_probe["summary"]["gc_disabled"]["evaluations"] == 3,
          "GC probe matrix is incomplete")
    check(gc_probe["summary"]["original"]["repeat_3_vs_other_median"] > 1.5 and
          gc_probe["summary"]["gc_disabled"]["repeat_3_vs_other_median"] < 1.1,
          "GC probe did not isolate the repeat-position effect")
    check(gc_probe["summary"]["gc_disabled"]["median_range_over_median"] < 0.1 and
          gc_probe["summary"]["gc_disabled"]["strict_false_improvements"] == 0,
          "GC-disabled probe remains too noisy or selected a false improvement")
    print(json.dumps({"status": "ok", "checksummed_files": checksum_count,
                      "tasks": list(EXPECTED_TASKS), "formal_progress": audit["formal_progress"]}, indent=2))


if __name__ == "__main__":
    main()
