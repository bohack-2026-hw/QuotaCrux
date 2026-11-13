"""Run one candidate sample in a fresh, locked-down container and time it from outside.

Timing starts when the in-container harness reports ready (container and interpreter already up) and the host
begins sending input; it stops when the host has received the complete stdout. Container startup is reported
separately as ready latency.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .. import config

SANDBOX_DIR = Path(__file__).resolve().parent
READY = b"ROUTEEVO_READY\n"
COMPILE_ERROR_EXIT = 97
_image_lock = threading.Lock()
_image_cache: dict[str, str] = {}


@dataclass
class SampleResult:
    status: str  # ok | compile_error | runtime_error | timeout | output_limit | memory_limit | sandbox_error
    elapsed_s: float | None
    ready_latency_s: float | None
    exit_code: int | None
    stdout: bytes
    stderr_tail: str

    def summary(self) -> dict:
        d = asdict(self)
        d.pop("stdout")
        d["stdout_bytes"] = len(self.stdout)
        return d


def image_tag() -> str:
    h = hashlib.sha256()
    for name in ("Dockerfile", "harness.py"):
        h.update((SANDBOX_DIR / name).read_bytes())
    return f"routeevo-sandbox:{h.hexdigest()[:12]}"


def ensure_image() -> dict:
    """Build the sandbox image if needed; return identifiers to record in run configs."""
    tag = image_tag()
    with _image_lock:
        if tag not in _image_cache:
            probe = subprocess.run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"], capture_output=True, text=True)
            if probe.returncode != 0:
                build = subprocess.run(["docker", "build", "-q", "-t", tag, str(SANDBOX_DIR)], capture_output=True, text=True)
                if build.returncode != 0:
                    raise RuntimeError(f"docker build failed: {build.stderr.strip()[-2000:]}")
                probe = subprocess.run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"], capture_output=True, text=True, check=True)
            _image_cache[tag] = probe.stdout.strip()
    return {"image_tag": tag, "image_id": _image_cache[tag]}


def environment_info(measure: config.MeasureConfig) -> dict:
    info = ensure_image()
    ver = subprocess.run(["docker", "version", "--format", "{{.Server.Version}} {{.Server.Os}}/{{.Server.Arch}}"], capture_output=True, text=True)
    info.update({
        "docker_server": ver.stdout.strip() or None,
        "container_python": "3.12-slim (pinned digest in Dockerfile)",
        "limits": {"cpus": measure.cpus, "memory": measure.memory, "pids_limit": measure.pids_limit,
                   "network": "none", "read_only_rootfs": True, "user": "65534:65534"},
    })
    return info


def run_sample(code: bytes, input_bytes: bytes, timeout_s: float, measure: config.MeasureConfig, profile: bool = False) -> SampleResult:
    image = ensure_image()["image_tag"]
    work = config.VAR_DIR / "sandbox" / uuid.uuid4().hex
    work.mkdir(parents=True)
    code_file = work / "candidate.py"
    code_file.write_bytes(code)
    code_file.chmod(0o444)
    work.chmod(0o555)
    name = f"routeevo-{work.name[:16]}"
    cmd = [
        "docker", "run", "--rm", "-i", "--name", name,
        "--network", "none", "--read-only",
        "--cpus", str(measure.cpus), "--memory", measure.memory, "--memory-swap", measure.memory,
        "--pids-limit", str(measure.pids_limit),
        "--user", "65534:65534", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "-e", "PYTHONHASHSEED=0", "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{work}:/work:ro", "-w", "/work",
        image, "python", "-B", "-s", "/opt/routeevo/harness.py", "/work/candidate.py",
    ]
    if profile:
        cmd.append("--profile")

    spawn = time.perf_counter()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    ready = threading.Event()
    eof = threading.Event()
    state = {"ready_at": None, "eof_at": None, "overflow": False}
    out_chunks: list[bytes] = []
    err_buf = bytearray()

    def read_stdout() -> None:
        pending = b""
        size = 0
        while True:
            chunk = proc.stdout.read(1 << 16)
            if not chunk:
                state["eof_at"] = time.perf_counter()
                if not ready.is_set():
                    out_chunks.append(pending)
                eof.set()
                return
            if not ready.is_set():
                pending += chunk
                idx = pending.find(READY)
                if idx < 0:
                    continue
                state["ready_at"] = time.perf_counter()
                ready.set()
                chunk = pending[idx + len(READY):]
            size += len(chunk)
            if size > measure.max_output_bytes:
                state["overflow"] = True
                _kill(name)
                continue
            out_chunks.append(chunk)

    def read_stderr() -> None:
        while True:
            chunk = proc.stderr.read(1 << 14)
            if not chunk:
                return
            err_buf.extend(chunk)
            if len(err_buf) > 256 * 1024:
                del err_buf[: len(err_buf) - 256 * 1024]

    t_out = threading.Thread(target=read_stdout, daemon=True)
    t_err = threading.Thread(target=read_stderr, daemon=True)
    t_out.start()
    t_err.start()

    def finish(status: str, elapsed: float | None, ready_latency: float | None) -> SampleResult:
        try:
            exit_code = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            _kill(name)
            exit_code = proc.wait(timeout=30)
        t_out.join(timeout=5)
        t_err.join(timeout=5)
        _make_writable(work)
        shutil.rmtree(work, ignore_errors=True)
        stderr_text = err_buf.decode("utf-8", errors="replace")
        if status == "ok":
            if state["overflow"]:
                status = "output_limit"
            elif exit_code == 137:
                status = "memory_limit"
            elif exit_code != 0:
                status = "runtime_error"
        return SampleResult(status, elapsed, ready_latency, exit_code, b"".join(out_chunks), stderr_text[-8000:])

    # Wait until the harness is ready, or the process dies before that.
    deadline = spawn + measure.ready_timeout_s
    while not ready.wait(timeout=0.05):
        if eof.is_set() or proc.poll() is not None:
            proc.wait()
            t_err.join(timeout=5)
            text = err_buf.decode("utf-8", errors="replace")
            status = "compile_error" if proc.returncode == COMPILE_ERROR_EXIT and "ROUTEEVO_COMPILE_ERROR" in text else "sandbox_error"
            return finish(status, None, None)
        if time.perf_counter() > deadline:
            _kill(name)
            err_buf.extend(b"\nROUTEEVO: harness did not become ready in time\n")
            return finish("sandbox_error", None, None)
    ready_latency = state["ready_at"] - spawn

    def write_input() -> None:
        try:
            proc.stdin.write(input_bytes)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    t0 = time.perf_counter()
    t_in = threading.Thread(target=write_input, daemon=True)
    t_in.start()
    if not eof.wait(timeout=timeout_s):
        _kill(name)
        eof.wait(timeout=30)
        t_in.join(timeout=5)
        return finish("timeout", time.perf_counter() - t0, ready_latency)
    t_in.join(timeout=5)
    return finish("ok", state["eof_at"] - t0, ready_latency)


def _kill(name: str) -> None:
    subprocess.run(["docker", "kill", name], capture_output=True)


def _make_writable(path: Path) -> None:
    try:
        path.chmod(0o755)
        for p in path.iterdir():
            p.chmod(0o644)
    except OSError:
        pass
