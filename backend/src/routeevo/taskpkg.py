"""Frozen task packages.

A spec file in backend/tasks/ lists task instances by generator parameters. `build` regenerates the data
deterministically under var/tasks/<task_id>/, writes a manifest with hashes and registers it. Once a task id
is registered (or pinned in tasks/lock.json) a different manifest is rejected, so a task cannot drift.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import config, db

TARGET_MIN_SPEEDUP = 1.10
LOCK_PATH = config.TASK_SPEC_DIR / "lock.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class Task:
    task_id: str
    split: str
    dir: Path
    manifest: dict

    # Files the agent may see. Everything else in the package is evaluator-only.
    @property
    def contract(self) -> str:
        return (self.dir / "contract.txt").read_text()

    @property
    def initial_code(self) -> str:
        return (self.dir / "initial.py").read_text()

    @property
    def examples(self) -> list[dict]:
        return json.loads((self.dir / "examples.json").read_text())

    @property
    def dev_profile(self) -> dict:
        return json.loads((self.dir / "dev_profile.json").read_text())

    @property
    def adapter(self):
        from .benchmarks import get
        return get(self.manifest["family"])

    @property
    def presentation(self) -> dict:
        return self.adapter.presentation(self.manifest)

    # Evaluator-only.
    def dataset(self, name: str) -> tuple[Path, Path]:
        if name not in ("dev", "final"):
            raise ValueError(name)
        return tuple(self.dir / self.manifest["files"][f"{name}_{kind}"]["file"] for kind in ("input", "expected"))

    @property
    def target_min_speedup(self) -> float | None:
        value = self.manifest["target"]["min_speedup"]
        return None if value is None else float(value)

    @property
    def is_native(self) -> bool:
        return "native" in self.manifest

    @property
    def objective(self) -> dict:
        return {"metric": "speedup", "direction": "maximize", **self.manifest["target"]}


def _write(path: Path, data: bytes) -> dict:
    path.write_bytes(data)
    return {"file": path.name, "sha256": sha256_bytes(data), "bytes": len(data)}


def build_task(family: str, entry: dict, out_root: Path = config.TASK_DATA_DIR) -> Task:
    from .benchmarks import get

    out_root.mkdir(parents=True, exist_ok=True)
    adapter = get(family)
    if not hasattr(adapter, "build"):
        raise ValueError(f"{family} uses `routeevo tasks import-effibench`, not a generator spec")
    return adapter.build(entry, out_root)


def register_package(tmp: Path, manifest: dict, out_root: Path) -> Task:
    """Register an immutable package produced by a benchmark adapter."""
    task_id, family, split = (manifest[k] for k in ("task_id", "family", "split"))
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    manifest_sha = sha256_bytes(json.dumps(manifest, sort_keys=True).encode())

    lock = json.loads(LOCK_PATH.read_text()) if LOCK_PATH.exists() else {}
    if task_id in lock and lock[task_id] != manifest_sha:
        shutil.rmtree(tmp)
        raise RuntimeError(f"{task_id}: regenerated manifest {manifest_sha[:12]} differs from tasks/lock.json {lock[task_id][:12]}")
    row = db.one("SELECT manifest_sha256 FROM tasks WHERE task_id = ?", (task_id,))
    if row and row["manifest_sha256"] != manifest_sha:
        shutil.rmtree(tmp)
        raise RuntimeError(f"{task_id}: already registered with manifest {row['manifest_sha256'][:12]}; task ids are immutable")

    final_dir = out_root / task_id
    shutil.rmtree(final_dir, ignore_errors=True)
    tmp.rename(final_dir)
    if not row:
        db.insert("tasks", {
            "task_id": task_id, "family": family, "split": split,
            "manifest_json": db.dumps(manifest), "manifest_sha256": manifest_sha, "registered_at": db.now(),
        })
    return Task(task_id, split, final_dir, manifest)


def build_spec(spec_path: Path) -> list[Task]:
    spec = json.loads(spec_path.read_text())
    return [build_task(spec["family"], entry) for entry in spec["tasks"]]


def load(task_id: str, verify: bool = True) -> Task:
    row = db.one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    if not row:
        raise KeyError(f"task {task_id} is not registered; run `routeevo tasks build` first")
    manifest = json.loads(row["manifest_json"])
    task = Task(task_id, row["split"], config.TASK_DATA_DIR / task_id, manifest)
    if verify:
        for key, meta in manifest["files"].items():
            path = task.dir / meta["file"]
            if not path.exists() or sha256_file(path) != meta["sha256"]:
                raise RuntimeError(f"{task_id}: {meta['file']} is missing or modified; rebuild the task package")
    return task


def write_lock(task_ids: list[str] | None = None) -> dict:
    """Pin registered manifests so later rebuilds must reproduce identical data."""
    lock = json.loads(LOCK_PATH.read_text()) if LOCK_PATH.exists() else {}
    rows = db.all_rows("SELECT task_id, manifest_sha256 FROM tasks")
    for r in rows:
        if task_ids is None or r["task_id"] in task_ids:
            lock[r["task_id"]] = r["manifest_sha256"]
    LOCK_PATH.write_text(json.dumps(dict(sorted(lock.items())), indent=2) + "\n")
    return lock


def rebuild_command(task_id: str) -> str:
    import shlex
    task = load(task_id)
    if task.manifest["family"] == "groupagg":
        return "uv run routeevo tasks build >/dev/null  # verify frozen groupagg packages"
    m = task.manifest
    if task.is_native:
        args = ["uv", "run", "routeevo", "tasks", "import-" + m["family"], m["problem"]["key"],
                "--split", task.split, "--task-id", task_id, "--dev-cases", str(m["dev_params"]["cases"]),
                "--final-cases", str(m["final_params"]["cases"])]
        if m["family"] == "algotune":
            args += ["--size", str(m["native"]["size"]), "--seed", str(m["native"]["seed"])]
        if m["family"] == "kernelbench":
            args += ["--worker-command", json.dumps(m["native"]["worker_command"]), "--image", m["native"]["image_id"]]
        return shlex.join(args)
    return shlex.join(["uv", "run", "--extra", "benchmark", "routeevo", "tasks", "import-effibench", m["problem"]["key"],
                       "--split", task.split, "--task-id", task_id, "--dev-cases", str(m["dev_params"]["cases"]),
                       "--case-limit", str(m["selection"]["selected_cases"])])
