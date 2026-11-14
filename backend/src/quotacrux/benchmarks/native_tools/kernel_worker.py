"""Trusted GPU host worker: JSON stdin/stdout, usable locally or through ssh.

Candidate, reference and checker run in separate containers. Only the public input
factory, current seed and candidate code reach the candidate container.
"""
import json
import hashlib
import math
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

active = set()


def cleanup(*_):
    for name in list(active):
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    if _:
        raise SystemExit(128 + _[0])


def container(image, script, payload, mounts, timeout, gpu):
    name = "quotacrux-kernel-" + uuid.uuid4().hex[:12]
    cmd = ["docker", "run", "--rm", "-i", "--name", name, "--network", "none", "--read-only",
           "--cpus", "2", "--memory", "4g", "--memory-swap", "4g", "--pids-limit", "256",
           "--user", "65534:65534", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--tmpfs", "/tmp:rw,nosuid,size=2g,mode=1777", "-e", "HOME=/tmp", "-e", "MAX_JOBS=1",
           "-e", "TORCH_EXTENSIONS_DIR=/tmp/extensions", "-e", "TORCH_CUDA_ARCH_LIST=7.5"]
    if gpu:
        cmd += ["--gpus", "device=0"]
    for host, target, mode in mounts:
        cmd += ["-v", f"{host}:{target}:{mode}"]
    cmd += [image, "python3", "-B", script]
    active.add(name)
    try:
        p = subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True, timeout=timeout)
        if p.returncode:
            return {"status": "runtime_error" if p.returncode != 125 else "sandbox_error", "stderr": p.stderr[-4000:]}
        result = json.loads(p.stdout)
        return {"status": "ok", **result}
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        return {"status": "timeout"}
    except (ValueError, TypeError) as exc:
        return {"status": "format_error", "message": str(exc)}
    finally:
        active.discard(name)


def evaluate(request):
    image = request["image"]
    if not image.startswith("sha256:") or len(image) != 71:
        raise ValueError("worker requires an immutable Docker image id")
    inspect = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], capture_output=True, text=True, check=True)
    if inspect.stdout.strip() != image:
        raise ValueError("image id mismatch")
    if request["operation"] == "environment":
        p = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], capture_output=True, text=True, check=True)
        probe = container(image, "/opt/quotacrux/kernel_harness.py", {"operation": "environment"}, [], 20, True)
        if probe["status"] != "ok":
            return probe
        return {"status": "ok", "image_id": image, "gpu": p.stdout.strip(), "protocol": "kernel-isolated-v1",
                "worker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "container": probe}
    if request["operation"] != "evaluate" or not 1 <= request["repeats"] <= 100:
        raise ValueError("invalid evaluation request")
    start = time.monotonic()
    cases = []
    with tempfile.TemporaryDirectory(prefix="quotacrux-kernel-") as root:
        root = Path(root)
        root.chmod(0o755)
        for seed in request["seeds"]:
            record = {"seed": seed}
            directories = {}
            for who, code in (("baseline", request["initial"]), ("candidate", request["code"])):
                directory = root / f"{seed}-{who}"
                directory.mkdir(mode=0o755)
                work, out = directory / "work", directory / "out"
                work.mkdir(mode=0o755)
                out.mkdir(mode=0o777)
                out.chmod(0o777)
                (work / "reference.py").write_text(request["reference"])
                (work / "candidate.py").write_text(code)
                directories[who] = out
                remaining = request["timeout_s"] - (time.monotonic() - start)
                if remaining <= 0:
                    return {"status": "budget_exhausted", "cases": cases}
                result = container(image, "/opt/quotacrux/kernel_harness.py", {"seed": seed, "repeats": request["repeats"]},
                    [(work, "/work", "ro"), (out, "/out", "rw")], remaining, True)
                if result["status"] != "ok":
                    status = "baseline_failed" if who == "baseline" and result["status"] != "sandbox_error" else result["status"]
                    return {"status": status, "failure": result, "cases": cases}
                times = result["times_s"]
                if len(times) != request["repeats"] or any(not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in times):
                    return {"status": "format_error", "cases": cases}
                for i in range(request["repeats"] + 1):
                    path = out / f"result_{i}.npy"
                    if not path.exists() or not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > 128 * 1024 * 1024:
                        return {"status": "format_error", "failure": {"message": "invalid output artifact"}, "cases": cases}
                record[who] = result
            check = container(image, "/opt/quotacrux/kernel_check.py", {"repeats": request["repeats"]},
                [(directories["baseline"], "/reference", "ro"), (directories["candidate"], "/candidate", "ro")], 60, False)
            if check["status"] != "ok":
                return {"status": "checker_error", "failure": check, "cases": cases}
            record["correct"] = check["correct"]
            cases.append(record)
            for out in directories.values():
                for p in out.iterdir():
                    if p.is_file() or p.is_symlink():
                        p.unlink()
    return {"status": "passed" if all(x["correct"] for x in cases) else "wrong_output", "cases": cases}


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    try:
        print(json.dumps(evaluate(json.load(sys.stdin)), allow_nan=False))
    finally:
        cleanup()
