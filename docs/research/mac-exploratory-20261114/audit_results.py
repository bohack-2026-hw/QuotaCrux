#!/usr/bin/env python3
"""Offline audit for the committed Mac exploratory result package."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TOOL_FILES = {Path("audit_results.py"), Path("export_results.py")}
CHECKSUM_EXCLUSIONS = {Path("SHA256SUMS"), Path("audit.json")}
PRIVACY_EXCLUSIONS = TOOL_FILES | {Path("SHA256SUMS")}


def relative_files() -> list[Path]:
    return sorted(path.relative_to(ROOT) for path in ROOT.rglob("*") if path.is_file())


def strict_json(path: Path) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            assert key not in value, f"duplicate JSON key {key!r}: {path.relative_to(ROOT)}"
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise AssertionError(f"non-finite JSON value {value}: {path.relative_to(ROOT)}")

    return json.loads(path.read_text(), object_pairs_hook=unique_object, parse_constant=reject_constant)


def load(path: str) -> dict[str, Any]:
    value = strict_json(ROOT / path)
    assert isinstance(value, dict), f"expected JSON object: {path}"
    return value


def audit_forbidden_files() -> int:
    forbidden = []
    for relative in relative_files():
        name = relative.name.lower()
        if (
            name.endswith((".sqlite", ".sqlite3", ".db", ".wal", ".shm", ".lock"))
            or name in {"compare.lock", "run.lock"}
        ):
            forbidden.append(relative.as_posix())
    assert not forbidden, f"forbidden runtime files committed: {forbidden}"
    return len(relative_files())


def audit_json_files() -> int:
    paths = [
        ROOT / relative
        for relative in relative_files()
        if relative.suffix == ".json" and relative != Path("audit.json")
    ]
    for path in paths:
        strict_json(path)
    return len(paths)


def audit_checksums() -> int:
    checksum_path = ROOT / "SHA256SUMS"
    lines = checksum_path.read_text().splitlines()
    assert lines, "SHA256SUMS is empty"
    listed: set[Path] = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        assert match is not None, f"malformed SHA256SUMS line: {line!r}"
        expected, raw_relative = match.groups()
        relative = Path(raw_relative)
        assert not relative.is_absolute() and ".." not in relative.parts, f"unsafe checksum path: {raw_relative}"
        assert relative not in listed, f"duplicate checksum path: {raw_relative}"
        path = ROOT / relative
        assert path.is_file(), f"checksum target missing: {raw_relative}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, f"checksum mismatch: {raw_relative}"
        listed.add(relative)

    required = set(relative_files()) - CHECKSUM_EXCLUSIONS
    assert listed == required, (
        f"SHA256SUMS coverage differs; missing={sorted(map(str, required - listed))}, "
        f"extra={sorted(map(str, listed - required))}"
    )
    return len(listed)


def audit_privacy() -> int:
    forbidden = (
        ("macOS home path", re.compile(rb"/Users/")),
        ("Linux home path", re.compile(rb"/home/[^/\s]+/")),
        ("link-local peer", re.compile(rb"169\.254\.")),
        ("local proxy endpoint", re.compile(rb"127\.0\.0\.1:615[23]")),
        ("private endpoint port", re.compile(rb'(?i)(?:https?|local)://[^\s"\']+:(?:1234|615[23])')),
        ("authorization bearer value", re.compile(rb'(?i)authorization["\s:]+bearer\s+[a-z0-9._-]{12,}')),
        ("API key value", re.compile(rb'(?i)(?:openai|qwen|lm_studio)_api_key\s*[:=]\s*["\']?[a-z0-9._-]{8,}')),
        ("OpenAI-style secret", re.compile(rb"sk-[a-zA-Z0-9_-]{16,}")),
        ("password value", re.compile(rb'(?i)password\s*[:=]\s*["\']?[^"\'\s]{8,}')),
    )
    checked = 0
    for relative in relative_files():
        if relative in PRIVACY_EXCLUSIONS:
            continue
        data = (ROOT / relative).read_bytes()
        for label, pattern in forbidden:
            assert not pattern.search(data), f"{label} in {relative}"
        checked += 1
    return checked


def table(ledger: dict[str, Any], name: str) -> list[dict[str, Any]]:
    rows = ledger["tables"][name]
    assert isinstance(rows, list), f"ledger table {name} is not a list"
    return rows


def audit_export_manifest() -> dict[str, Any]:
    manifest = load("export-manifest.json")
    assert manifest["format"] == "routeevo-mac-exploratory-export-v1"
    assert manifest["execution_code_sha"] == "912b20a4cfeb51af9c36d0679b23f0990abe862f"
    assert manifest["formal_results_eligible"] is False
    batches = manifest["batches"]
    assert [row["batch"] for row in batches] == [
        "openai",
        "remote-preload",
        "remote-loaded",
        "remote-bounded",
        "remote-direct",
    ]
    for row in batches:
        assert row["excluded"]["sqlite_wal_shm"]
        assert row["excluded"]["raw_dev_and_final_inputs"]
        assert row["excluded"]["locks"]
    return {"format": manifest["format"], "batches": len(batches)}


def audit_ledger(ledger: dict[str, Any]) -> None:
    assert ledger["format"] == "routeevo-sqlite-json-v1"
    assert ledger["source_binary_committed"] is False
    assert isinstance(ledger["schemas"], dict) and isinstance(ledger["tables"], dict)
    assert set(ledger["schemas"]) == set(ledger["tables"])


def audit_programs() -> dict[str, int]:
    candidates = best_files = task_programs = 0
    for report_path in sorted(ROOT.glob("**/runs/*/report.json")):
        report = strict_json(report_path)
        batch = report_path.parents[2]
        ledger = strict_json(batch / "ledger.json")
        recorded = {
            row["candidate_id"]: row["code_sha256"]
            for row in table(ledger, "candidates") if row["run_id"] == report["run_id"]
        }
        rows = report["candidates"]
        assert set(recorded) == {row["candidate_id"] for row in rows}
        for row in rows:
            path = report_path.parent / "candidates" / f'{row["candidate_id"]}.py'
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == row["code_sha256"] == recorded[row["candidate_id"]], (
                f"candidate differs from execution identity: {path.relative_to(ROOT)}"
            )
            candidates += 1
        best = report["best_candidate"]
        if best:
            candidate = report_path.parent / "candidates" / f'{best["candidate_id"]}.py'
            assert (report_path.parent / "best.py").read_bytes() == candidate.read_bytes()
            best_files += 1
    for identity_path in sorted(ROOT.glob("**/tasks/*/task-identity.json")):
        identity = strict_json(identity_path)
        for name, metadata in identity["files"].items():
            path = identity_path.parent / name
            if path.suffix == ".py" and metadata["content_committed"]:
                data = path.read_bytes()
                assert hashlib.sha256(data).hexdigest() == metadata["sha256"], (
                    f"task program differs from source identity: {path.relative_to(ROOT)}"
                )
                assert len(data) == metadata["bytes"]
                task_programs += 1
    programs = [ROOT / relative for relative in relative_files()
                if relative.suffix == ".py" and relative not in TOOL_FILES]
    for path in programs:
        ast.parse(path.read_bytes(), filename=path.relative_to(ROOT).as_posix())
    return {"candidates": candidates, "best_files": best_files,
            "task_programs": task_programs, "syntax_checked": len(programs)}


def audit_openai() -> dict[str, Any]:
    comparison = load("openai/comparison.json")
    metadata = load("openai/evidence/run-metadata.json")
    ledger = load("openai/ledger.json")
    audit_ledger(ledger)
    assert metadata["formal_results_eligible"] is False and metadata["final_evaluation"] is False
    assert comparison["status"] == "completed" and comparison["fair"] is True
    assert comparison["final_evaluation"] is False and len(comparison["runs"]) == 4
    assert all(row["status"] == "completed" and row["final_status"] == "disabled" for row in comparison["runs"])
    expected = {
        ("algotune-convolve_1d-exploratory-short-20261114", "feedback"): 1.2985780320905493,
        ("algotune-pagerank-exploratory-short-20261114", "independent"): 23.051414599425694,
        ("algotune-convolve_1d-exploratory-short-20261114", "independent"): 2.669287533650096,
        ("algotune-pagerank-exploratory-short-20261114", "feedback"): 25.041934744449737,
    }
    actual = {(row["task_id"], row["mode"]): row["best_dev"]["speedup"] for row in comparison["runs"]}
    assert actual == expected
    calls = table(ledger, "model_calls")
    evaluations = table(ledger, "evaluations")
    assert len(calls) == 12 and all(row["status"] == "ok" for row in calls)
    assert len(evaluations) == 16 and {row["dataset"] for row in evaluations} == {"dev"}
    assert all(row["final_evaluation_id"] is None for row in table(ledger, "runs"))
    return {
        "runs": 4,
        "calls": 12,
        "evaluations": 16,
        "best_dev_speedups": [
            {"task_id": task_id, "mode": mode, "speedup": speedup}
            for (task_id, mode), speedup in sorted(actual.items())
        ],
    }


def audit_remote_attempt(path: str, runs: int, calls: int) -> None:
    comparison = load(f"{path}/comparison.json")
    metadata = load(f"{path}/evidence/run-metadata.json")
    ledger = load(f"{path}/ledger.json")
    audit_ledger(ledger)
    assert metadata["formal_results_eligible"] is False and metadata["final_evaluation"] is False
    assert comparison["status"] == "completed" and comparison["final_evaluation"] is False
    assert len(comparison["runs"]) == runs
    assert all(
        row["status"] == "completed"
        and row["final_status"] == "disabled"
        and row["best_candidate_id"] == "c0"
        for row in comparison["runs"]
    )
    ledger_runs = table(ledger, "runs")
    model_calls = table(ledger, "model_calls")
    candidates = table(ledger, "candidates")
    evaluations = table(ledger, "evaluations")
    assert len(ledger_runs) == runs and all(row["final_evaluation_id"] is None for row in ledger_runs)
    assert len(model_calls) == calls
    assert all(row["status"] == "error" and row["error_kind"] == "bad_response" for row in model_calls)
    assert all("HTTP 503" in row["error_message"] for row in model_calls)
    assert len(candidates) == runs and {row["candidate_id"] for row in candidates} == {"c0"}
    assert len(evaluations) == runs and {row["dataset"] for row in evaluations} == {"dev"}

    call_files = sorted((ROOT / path / "runs").glob("*/calls/*.json"))
    assert len(call_files) == calls
    for call_file in call_files:
        record = strict_json(call_file)
        assert isinstance(record, dict)
        assert isinstance(record["response"], str) and "<title>Connection Closed</title>" in record["response"]


def audit_remote() -> dict[str, Any]:
    audit_remote_attempt("remote/01-preload-proxy", 4, 12)
    audit_remote_attempt("remote/02-loaded-proxy", 2, 6)
    audit_remote_attempt("remote/03-bounded-proxy", 1, 1)

    comparison = load("remote/04-direct/comparison.json")
    run_metadata = load("remote/04-direct/evidence/run-metadata.json")
    direct_ledger = load("remote/04-direct/ledger.json")
    audit_ledger(direct_ledger)
    assert comparison["status"] == "completed" and comparison["final_evaluation"] is False
    assert len(comparison["runs"]) == 1
    assert comparison["runs"][0]["best_candidate_id"] == "c0"
    assert comparison["runs"][0]["final_status"] == "disabled"
    direct_calls = table(direct_ledger, "model_calls")
    assert len(direct_calls) == 1
    call = direct_calls[0]
    assert call["status"] == "error" and call["error_kind"] == "incomplete"
    assert (call["input_tokens"], call["output_tokens"], call["reasoning_tokens"]) == (2327, 2047, 1707)
    candidates = table(direct_ledger, "candidates")
    assert len(candidates) == 1 and candidates[0]["candidate_id"] == "c0"
    assert all(row["final_evaluation_id"] is None for row in table(direct_ledger, "runs"))

    raw_call = load("remote/04-direct/runs/run-20261114T091800-a13b/calls/m1.json")
    choice = raw_call["response"]["choices"][0]
    usage = raw_call["response"]["usage"]
    assert choice["finish_reason"] == "length" and choice["message"]["content"]
    assert (usage["prompt_tokens"], usage["completion_tokens"]) == (2327, 2047)
    assert usage["completion_tokens_details"]["reasoning_tokens"] == 1707

    evaluation = load("remote/04-direct/evidence/manual-completion-evaluation.json")
    metadata = load("remote/04-direct/evidence/manual-completion-metadata.json")
    candidate_path = ROOT / "remote/04-direct/evidence/remote-proposal-manually-completed.py"
    candidate_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    assert candidate_sha == evaluation["detail"]["candidate_sha256"]
    assert metadata["source_run_id"] == call["run_id"]
    assert metadata["source_call_id"] == call["call_id"]
    assert metadata["source_finish_reason"] == "length"
    assert evaluation["correct"] is True and evaluation["passed_cases"] == evaluation["case_count"] == 2
    assert evaluation["speedup"] == 1.225486477902775 and evaluation["goal_met"] is True
    assert evaluation["timing_spread"]["candidate_min_max_s"][1] < evaluation["timing_spread"]["baseline_min_max_s"][0]
    assert metadata["eligible_as_model_generated_candidate"] is False
    assert metadata["formal_results_eligible"] is False
    assert run_metadata["formal_results_eligible"] is False
    assert run_metadata["model_call"]["status"] == "incomplete"
    assert run_metadata["model_call"]["protocol_candidates"] == 0
    assert run_metadata["assisted_reconstruction"]["eligible_as_model_generated_candidate"] is False

    manual_rows = [
        row for row in table(direct_ledger, "evaluations") if row["evaluation_id"] == evaluation["evaluation_id"]
    ]
    assert len(manual_rows) == 1
    assert manual_rows[0]["run_id"] is None and manual_rows[0]["candidate_id"] is None
    assert manual_rows[0]["dataset"] == "dev"
    return {"proxy_503_calls": 19, "direct_incomplete_calls": 1, "assisted_speedup": evaluation["speedup"]}


def main() -> None:
    forbidden_scan_files = audit_forbidden_files()
    json_files = audit_json_files()
    checksum_files = audit_checksums()
    privacy_files = audit_privacy()
    result = {
        "status": "passed",
        "forbidden_scan_files": forbidden_scan_files,
        "json_files": json_files,
        "checksum_files": checksum_files,
        "privacy_files": privacy_files,
        "export": audit_export_manifest(),
        "program_integrity": audit_programs(),
        "openai": audit_openai(),
        "remote": audit_remote(),
        "formal_results_eligible": False,
        "final_evaluations": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
