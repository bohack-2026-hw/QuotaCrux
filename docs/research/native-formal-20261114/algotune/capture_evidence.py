#!/usr/bin/env python3
"""Capture the public, non-secret evidence for the Mac AlgoTune preflight."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
DEFAULT_TASKS = {
    "convolve_1d": "algotune-convolve_1d-formal-20261114-82a6fac682",
    "pagerank": "algotune-pagerank-formal-20261114-b2ad8ba1c8",
}
CALIBRATIONS = {
    "convolve_1d": "calibration-convolve_1d.json",
    "pagerank": "calibration-pagerank.json",
}


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True, timeout=30).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def write_checksums() -> int:
    files = sorted(path for path in HERE.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    lines = [f"{sha256(path)}  {path.relative_to(HERE)}" for path in files]
    (HERE / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return len(lines)


def scalar(value: str) -> object:
    value = value.strip()
    if value in ("true", "false"):
        return value == "true"
    try:
        return int(value)
    except ValueError:
        return value


def orb_config() -> dict:
    allowed = {"cpu", "memory_mib", "machine.docker.cpu", "machine.docker.memory_mib",
               "machine.docker.isolated", "rosetta", "k8s.enable"}
    return {key: scalar(value) for line in command("orb", "config", "show").splitlines()
            for key, value in [line.split(":", 1)] if key in allowed}


def docker_image(image_id: str) -> dict:
    raw = json.loads(command("docker", "image", "inspect", image_id))[0]
    return {
        "image_id": raw["Id"],
        "repo_tags": raw.get("RepoTags") or [],
        "repo_digests": raw.get("RepoDigests") or [],
        "architecture": raw["Architecture"],
        "os": raw["Os"],
        "size_bytes": raw["Size"],
        "created": raw["Created"],
        "digest_note": ("Local BuildKit image has no registry RepoDigest; image_id is the immutable local identity."
                        if not raw.get("RepoDigests") else None),
    }


def local_model(model: str) -> dict:
    shown = command("ollama", "show", model)
    fields = {}
    for name in ("architecture", "parameters", "context length", "embedding length", "quantization", "requires"):
        match = re.search(rf"^\s*{re.escape(name)}\s+(.+?)\s*$", shown, re.MULTILINE)
        fields[name.replace(" ", "_")] = match.group(1) if match else None
    listing = next(line for line in command("ollama", "list").splitlines()[1:]
                   if line.split()[0] == model)
    columns = listing.split()
    return {
        "purpose": "feasibility record only; not the hosted formal batch",
        "runtime": command("ollama", "--version"),
        "model": columns[0],
        "model_id": columns[1],
        "stored_size": " ".join(columns[2:4]),
        **fields,
        "capabilities": [name for name in ("completion", "vision", "tools", "thinking")
                         if re.search(rf"^\s*{name}\s*$", shown, re.MULTILINE)],
        "loaded_during_capture": model in command("ollama", "ps"),
        "api_fee": 0,
        "machine_running_cost": "not measured",
        "formal_batch_compatibility": "separate model/quantization; do not combine with hosted Qwen3.8-27B",
        "model_requests": 0,
    }


def elapsed_seconds(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--var-dir", type=Path, required=True)
    parser.add_argument("--convolve-task-id", default=DEFAULT_TASKS["convolve_1d"])
    parser.add_argument("--pagerank-task-id", default=DEFAULT_TASKS["pagerank"])
    parser.add_argument("--local-model", default="qwen3.8:27b-mlx")
    args = parser.parse_args()
    var_dir = args.var_dir.resolve()
    try:
        var_dir_label = str(var_dir.relative_to(ROOT))
    except ValueError:
        var_dir_label = "external-var-dir"
    tasks = {"convolve_1d": args.convolve_task_id, "pagerank": args.pagerank_task_id}
    os.environ["ROUTEEVO_VAR_DIR"] = str(var_dir)
    os.environ["ROUTEEVO_NO_DOTENV"] = "1"

    from routeevo import db, taskpkg
    from routeevo.benchmarks import algotune

    docker_version = json.loads(command("docker", "version", "--format", "{{json .}}"))
    docker_info = json.loads(command("docker", "info", "--format", "{{json .}}"))
    stat = os.statvfs(ROOT)
    host = {
        "captured_at": datetime.now().astimezone().isoformat(),
        "source_git_head": command("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        "source_branch": command("git", "-C", str(ROOT), "branch", "--show-current"),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "chip": command("sysctl", "-n", "machdep.cpu.brand_string"),
            "logical_cpus": int(command("sysctl", "-n", "hw.ncpu")),
            "performance_cores": int(command("sysctl", "-n", "hw.perflevel0.physicalcpu")),
            "efficiency_cores": int(command("sysctl", "-n", "hw.perflevel1.physicalcpu")),
            "memory_bytes": int(command("sysctl", "-n", "hw.memsize")),
            "macos_version": command("sw_vers", "-productVersion"),
            "macos_build": command("sw_vers", "-buildVersion"),
            "filesystem_available_bytes": stat.f_bavail * stat.f_frsize,
        },
        "toolchain": {
            "python": platform.python_version(),
            "uv": command("uv", "--version"),
            "uv_lock_sha256": sha256(ROOT / "backend/uv.lock"),
        },
        "orbstack": {"version": command("orb", "version"), "config": orb_config()},
        "docker": {
            "client_version": docker_version["Client"]["Version"],
            "server_version": docker_version["Server"]["Version"],
            "server_os": docker_info["OSType"],
            "server_architecture": docker_info["Architecture"],
            "server_cpus": docker_info["NCPU"],
            "server_memory_bytes": docker_info["MemTotal"],
            "driver": docker_info["Driver"],
            "name": docker_info["Name"],
            "native_architecture": docker_info["Architecture"] == "aarch64",
        },
        "local_qwen": local_model(args.local_model),
        "formal_model": {
            "status": "awaiting issue #2 freeze",
            "preferred_provider": "hosted",
            "model": "Qwen3.8-27B",
            "credentials_recorded": False,
            "price_snapshot": None,
            "model_requests": 0,
        },
        "affinity_scope": {
            "requested": "Docker VM vCPU 2",
            "observed": [2],
            "physical_apple_core_mapping": None,
            "physical_core_exclusive": False,
        },
    }
    write_json(EVIDENCE / "host.json", host)

    task_records = {}
    images = {}
    for problem, task_id in tasks.items():
        task = taskpkg.load(task_id, verify=True)
        row = db.one("SELECT manifest_sha256, manifest_json FROM tasks WHERE task_id = ?", (task_id,))
        disk_manifest = json.loads((task.dir / "manifest.json").read_text())
        calibration = json.loads((EVIDENCE / CALIBRATIONS[problem]).read_text())
        profiles = {}
        for dataset in ("dev",):
            meta = task.manifest["files"]["dev_input"]
            records = json.loads((task.dir / meta["file"]).read_text())
            profile = algotune.input_profile(problem, records, task.manifest["native"]["size"])
            profile["source"] = "frozen_dev_input_statistics_only"
            profile["input_sha256"] = meta["sha256"]
            profiles[dataset] = profile
        final_meta = task.manifest["files"]["final_input"]
        profiles["final"] = {
            "source": "sealed_final_input",
            "case_count": task.manifest["final_params"]["cases"],
            "input_sha256": final_meta["sha256"],
            "details_published": False,
        }
        candidate = docker_image(task.manifest["native"]["candidate_image"]["image_id"])
        judge = docker_image(task.manifest["native"]["judge_image"]["image_id"])
        images[candidate["image_id"]] = candidate
        images[judge["image_id"]] = judge
        record = {
            "task_id": task_id,
            "problem": problem,
            "var_dir": var_dir_label,
            "manifest_canonical_sha256": row["manifest_sha256"],
            "manifest_file_sha256": sha256(task.dir / "manifest.json"),
            "sqlite_manifest_matches_disk": json.loads(row["manifest_json"]) == disk_manifest,
            "package_files_verified": True,
            "package_files": {key: {**meta, "observed_sha256": sha256(task.dir / meta["file"])}
                              for key, meta in task.manifest["files"].items()},
            "manifest": task.manifest,
            "workload_profiles": profiles,
            "checker_contract": algotune.PROBLEM_CONTRACTS[problem],
            "candidate_image": candidate,
            "judge_image": judge,
            "measure": calibration["measures"]["pinned"],
            "affinity_probe": calibration["affinity_probe"],
            "calibration_program_sha256": calibration["program_sha256"],
            "calibration_file": f"evidence/{CALIBRATIONS[problem]}",
            "model_requests": 0,
            "final_evaluations": 0,
        }
        task_records[problem] = record
        write_json(EVIDENCE / f"worker-{problem}.json", record)

    tables = {name: db.one(f"SELECT COUNT(*) AS n FROM {name}")["n"]
              for name in ("tasks", "runs", "model_calls", "evaluations")}
    evaluations = [dict(row) for row in db.all_rows(
        "SELECT dataset, status, COUNT(*) AS count FROM evaluations GROUP BY dataset, status ORDER BY dataset, status")]
    routeevo_containers = []
    for line in command("docker", "ps", "--format", "{{json .}}").splitlines():
        container = json.loads(line)
        if container["Image"].startswith("routeevo-"):
            routeevo_containers.append({key: container[key] for key in ("Image", "Names", "State", "Status")})
    ledger = {
        "captured_at": datetime.now().astimezone().isoformat(),
        "var_dir": var_dir_label,
        "sqlite_path": f"{var_dir_label}/routeevo.sqlite3",
        "integrity_check": db.one("PRAGMA integrity_check")[0],
        "foreign_key_violations": len(db.all_rows("PRAGMA foreign_key_check")),
        "counts": tables,
        "evaluation_counts": evaluations,
        "dev_evaluations": sum(row["count"] for row in evaluations if row["dataset"] == "dev"),
        "final_evaluations": sum(row["count"] for row in evaluations if row["dataset"] == "final"),
        "formal_runs": 0,
        "model_requests": tables["model_calls"],
        "api_cost": 0,
        "task_manifests": {problem: record["manifest_canonical_sha256"]
                           for problem, record in task_records.items()},
        "task_packages_verified": all(record["package_files_verified"] for record in task_records.values()),
        "locks": {name: (var_dir / name).exists() for name in ("run.lock", "compare.lock")},
        "routeevo_containers": routeevo_containers,
    }
    write_json(EVIDENCE / "ledger-audit.json", ledger)

    calibration_rows = {}
    timing_observation = {"accepted_for_freeze": False, "recalibration_required": True, "tasks": {}}
    for problem, filename in CALIBRATIONS.items():
        value = json.loads((EVIDENCE / filename).read_text())
        calibration_rows[problem] = {
            "file": f"evidence/{filename}",
            "status": value["status"],
            "task_id": value["task_id"],
            "duration_s": elapsed_seconds(value["results"][0]["started_at"], value["ended_at"]),
            "control_delay_ms": value["control_delay_ms"],
            "default": value["summary"]["default"],
            "pinned": value["summary"]["pinned"],
            "controls": value["summary"]["controls"],
            "all_results_passed": all(row["evaluation"]["status"] == "passed" for row in value["results"]),
            "all_expected_outcomes_observed": all(row["expected_outcome_observed"] for row in value["results"]),
        }
        self_results = [row for row in value["results"] if row["kind"] == "self"]
        by_repeat = [[] for _ in range(value["measures"]["pinned"]["repeats"])]
        for result in self_results:
            for sample in result["raw_samples"]:
                for index, elapsed in enumerate(sample["times_s"]):
                    by_repeat[index].append(elapsed * 1000)
        repeat_medians = [statistics.median(values) for values in by_repeat]
        loads = [load for result in self_results
                 for environment in (result["environment_before"], result["environment_after"])
                 for load in environment["load_average"][:1]]
        timing_observation["tasks"][problem] = {
            "repeat_index_median_ms": repeat_medians,
            "repeat_3_vs_other_median": (repeat_medians[2] /
                                           statistics.median(repeat_medians[:2] + repeat_medians[3:])),
            "host_load_1m_min_max": [min(loads), max(loads)],
            "self_range_over_median": {
                "default": value["summary"]["default"]["median_range_over_median"],
                "pinned": value["summary"]["pinned"]["median_range_over_median"],
            },
        }
    timing_observation.update({
        "finding": "PageRank repeat index 3 is systematically slower and the host load was high.",
        "interpretation": "The pattern is consistent with a periodic runtime effect, but the cause is not yet proven.",
        "required_decision": "Issue #2 must freeze the timing-harness treatment before tasks are rebuilt and recalibrated in a quiet window.",
    })
    write_json(EVIDENCE / "timing-observation.json", timing_observation)
    audit = {
        "schema": "algotune-mac-preflight-v1",
        "status": "environment-ready-calibration-provisional",
        "source_git_head": host["source_git_head"],
        "formal_progress": {"completed": 0, "total": 15},
        "calibrations": calibration_rows,
        "attempts_retained": [
            {"file": "evidence/calibration-convolve_1d-attempt1-failed.json",
             "accepted": False, "reason": "relative VAR_DIR was rejected before the affinity probe"},
            {"file": "evidence/calibration-pagerank-attempt1-insufficient-control.json",
             "accepted": False, "reason": "3 ms positive-control timing intervals overlapped"},
        ],
        "selection_rule": "correct and max(candidate_samples) < min(baseline_samples)",
        "recommendation": {
            "formal_episode_concurrency": 1,
            "reason": "AlgoTune function timing is noise-sensitive; keep measurement windows serial",
            "docker_vm_cpuset_cpu": "2",
            "function_warmups": 3,
            "timing_repeats": 5,
            "physical_core_exclusive": False,
            "accepted_for_freeze": False,
            "recalibration_required": True,
        },
        "native_architecture": host["docker"]["native_architecture"],
        "all_image_architectures": sorted({image["architecture"] for image in images.values()}),
        "task_manifest_hashes": ledger["task_manifests"],
        "final_inputs_generated_and_hashed": True,
        "final_inputs_executed": False,
        "model_requests": 0,
        "api_cost": 0,
        "blocking_dependencies": [
            "issue #2 must freeze the timing-harness treatment and publish the experiment SHA",
            "accepted calibration must be rerun in a quiet measurement window",
            "issue #2 must publish prompts, pricing and the full run plan"
        ],
    }
    write_json(EVIDENCE / "audit.json", audit)
    checksum_count = write_checksums()
    print(json.dumps({"host": str((EVIDENCE / "host.json").relative_to(ROOT)), "tasks": list(tasks.values()),
                      "ledger": ledger["counts"], "formal_progress": audit["formal_progress"],
                      "checksummed_files": checksum_count}, indent=2))


if __name__ == "__main__":
    main()
