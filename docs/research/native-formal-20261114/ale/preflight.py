"""No-model ALE preparation and dev-only serial/two-worker calibration."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

SOURCE_SHA = "a67850f3db224a9243f59703d25397ede3d54aa7"
WORKERS = {"a": {"problem": "ahc024", "cpu": "2", "sibling": "8"},
           "b": {"problem": "ahc026", "cpu": "4", "sibling": "10"}}
# Fixed operation count makes additional CPU contention visible in elapsed time.
CONTROL = "_work = 0\nfor _i in range(12000000):\n    _work = (_work + _i) & 65535\n"


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def capture(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def locks(var: Path):
    handles = []
    for name in ("compare.lock", "run.lock"):
        f = (var / name).open("a")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        handles.append(f)
    return handles


def prepare(args) -> None:
    from quotacrux import config, db, taskpkg
    from quotacrux.sandbox import executor

    selected = WORKERS[args.worker]
    source_root = args.root / "var-prepare" / "tasks"
    paths = [p for p in source_root.iterdir() if p.is_dir() and
             json.loads((p / "manifest.json").read_text())["problem"]["key"] == selected["problem"]]
    if len(paths) != 1:
        raise RuntimeError(f"expected one prepared task for {selected['problem']}, got {paths}")
    source = paths[0]
    manifest = json.loads((source / "manifest.json").read_text())
    config.TASK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".register-", dir=config.TASK_DATA_DIR))
    shutil.copytree(source, tmp, dirs_exist_ok=True)
    task = taskpkg.register_package(tmp, manifest, config.TASK_DATA_DIR)
    taskpkg.load(task.task_id, verify=True)
    measure = config.MeasureConfig(cpuset_cpus=selected["cpu"])
    affinity = executor.run_sample(b"import os; print(sorted(os.sched_getaffinity(0)))\n", b"", 2, measure)
    if affinity.status != "ok" or json.loads(affinity.stdout) != [int(selected["cpu"])]:
        raise RuntimeError(f"candidate affinity failed: {affinity}")
    row = db.one("SELECT manifest_sha256 FROM tasks WHERE task_id=?", (task.task_id,))
    programs = {}
    for name, prefix in (("c0", ""), ("cpu_control", CONTROL)):
        code = (prefix + task.initial_code).encode()
        path = args.root / "evidence" / "programs" / f"{selected['problem']}-{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(code)
        programs[name] = {"file": str(path.relative_to(args.root / "evidence")),
                          "sha256": hashlib.sha256(code).hexdigest()}
    result = {"source_sha": SOURCE_SHA, "worker": args.worker, **selected,
              "task_id": task.task_id, "manifest_sha256": row["manifest_sha256"],
              "manifest": manifest, "measure": measure.to_dict(),
              "environment": task.adapter.environment_info(task, measure),
              "affinity_probe": {**affinity.summary(), "stdout": affinity.stdout.decode()},
              "var_dir": str(config.VAR_DIR), "programs": programs,
              "final_evaluations": db.one("SELECT COUNT(*) AS n FROM evaluations WHERE dataset='final'")["n"],
              "model_calls": db.one("SELECT COUNT(*) AS n FROM model_calls")["n"],
              "python": sys.version, "uv": capture(str(args.root / "bin/uv"), "--version")}
    dump(args.root / "evidence" / f"worker-{args.worker}.json", result)
    print(json.dumps({k: result[k] for k in ("worker", "task_id", "manifest_sha256")}))


def worker(args) -> None:
    from quotacrux import config, db, evaluator, taskpkg

    record = json.loads((args.root / "evidence" / f"worker-{args.worker}.json").read_text())
    task = taskpkg.load(record["task_id"])
    held = locks(config.VAR_DIR)
    try:
        if db.one("SELECT COUNT(*) AS n FROM evaluations WHERE dataset='final'")["n"]:
            raise RuntimeError("calibration VAR_DIR contains final evaluations")
        code = ((CONTROL if args.program == "cpu_control" else "") + task.initial_code).encode()
        measure = config.MeasureConfig(**record["measure"])
        ev = evaluator.evaluate(task, code, "dev", measure, config.RunLimits())
        result = {"phase": args.phase, "repeat": args.repeat, "worker": args.worker,
                  "task_id": task.task_id, "cpu": record["cpu"], "program": args.program,
                  "candidate_sha256": hashlib.sha256(code).hexdigest(), "evaluation": asdict(ev)}
        dump(args.out, result)
        # Keep failed calibration evidence, then stop instead of replacing it.
        if ev.status != "passed":
            raise RuntimeError(f"calibration failed: {args.out}: {ev.status}")
    finally:
        for f in held:
            f.close()


def cpu_sample() -> dict:
    rows = {}
    for line in Path("/proc/stat").read_text().splitlines():
        parts = line.split()
        if parts and parts[0].startswith("cpu"):
            rows[parts[0]] = [int(x) for x in parts[1:9]]
    return rows


def calibrate(args) -> None:
    evidence = args.root / "evidence"
    out = evidence / "calibration"
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("*.json")):
        raise RuntimeError("use a fresh calibration directory; retained results are not overwritten")
    script = Path(__file__).resolve()
    samples = []
    done = threading.Event()

    def monitor():
        while not done.is_set():
            samples.append({"monotonic": time.monotonic(), "cpu": cpu_sample()})
            done.wait(0.5)

    def run(phase, repeat, program, name):
        path = out / f"{phase}-{repeat}-{program}-{name}.json"
        env = {**os.environ, "ROUTEEVO_NO_DOTENV": "1",
               "ROUTEEVO_VAR_DIR": str(args.root / f"var-worker-{name}")}
        subprocess.run([sys.executable, str(script), "worker", "--root", str(args.root),
                        "--worker", name, "--phase", phase, "--repeat", str(repeat),
                        "--program", program, "--out", str(path)], env=env, check=True)
        return json.loads(path.read_text())

    started = time.monotonic()
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    records = []
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for repeat in (1, 2, 3):
                phases = ("serial", "parallel") if repeat % 2 else ("parallel", "serial")
                for phase in phases:
                    for program in ("c0", "cpu_control"):
                        batch_start = time.monotonic()
                        if phase == "serial":
                            batch = [run(phase, repeat, program, name) for name in ("a", "b")]
                        else:
                            jobs = [pool.submit(run, phase, repeat, program, name) for name in ("a", "b")]
                            batch = [job.result() for job in jobs]
                        elapsed = time.monotonic() - batch_start
                        records.extend(batch)
                        print(f"{phase} r{repeat} {program}: {elapsed:.3f}s", flush=True)
    finally:
        done.set()
        thread.join()
        dump(evidence / "cpu-samples.json", samples)
    groups = []
    for name in WORKERS:
        for program in ("c0", "cpu_control"):
            group = {"worker": name, "program": program}
            for phase in ("serial", "parallel"):
                rows = [x["evaluation"] for x in records if x["worker"] == name and
                        x["program"] == program and x["phase"] == phase]
                timings = [s["elapsed_s"] for r in rows for s in r["detail"]["samples"]]
                group[phase] = {"scores": [r["detail"]["objective"]["value"] for r in rows],
                                "sample_median_s": statistics.median(timings), "sample_max_s": max(timings),
                                "evaluation_median_s": statistics.median(r["detail"]["duration_s"] for r in rows),
                                "timeouts": sum(s["status"] == "timeout" for r in rows for s in r["detail"]["samples"])}
            group["sample_median_ratio_parallel_over_serial"] = group["parallel"]["sample_median_s"] / group["serial"]["sample_median_s"]
            groups.append(group)
    dump(evidence / "calibration-summary.json", {"source_sha": SOURCE_SHA, "groups": groups,
         "wall_clock_s": time.monotonic() - started, "evaluations": len(records),
         "model_calls": 0, "final_evaluations": 0,
         "candidate_cpu_isolation": True, "judge_cpu_isolation": False,
         "control_prefix": CONTROL, "repeats_per_condition": 3})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "worker", "calibrate"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--worker", choices=WORKERS)
    parser.add_argument("--phase", choices=("serial", "parallel"))
    parser.add_argument("--program", choices=("c0", "cpu_control"))
    parser.add_argument("--repeat", type=int)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    {"prepare": prepare, "worker": worker, "calibrate": calibrate}[args.command](args)
