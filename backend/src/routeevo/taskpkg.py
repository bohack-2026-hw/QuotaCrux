"""Frozen task packages.

A spec file in backend/tasks/ lists task instances by generator parameters. `build` regenerates the data
deterministically under var/tasks/<task_id>/, writes a manifest with hashes and registers it. Once a task id
is registered (or pinned in tasks/lock.json) a different manifest is rejected, so a task cannot drift.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import config, db
from . import families

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

    # Evaluator-only.
    def dataset(self, name: str) -> tuple[Path, Path]:
        if name not in ("dev", "final"):
            raise ValueError(name)
        return self.dir / f"{name}_input.csv", self.dir / f"{name}_expected.csv"

    @property
    def target_min_speedup(self) -> float:
        return float(self.manifest["target"]["min_speedup"])

    @property
    def family(self) -> str:
        return self.manifest["family"]

    @property
    def fam(self):
        return families.get(self.manifest["family"])


def _write(path: Path, data: bytes) -> dict:
    path.write_bytes(data)
    return {"file": path.name, "sha256": sha256_bytes(data), "bytes": len(data)}


SPLITS = ("A", "B", "C", "D", "S", "T", "smoke")


def build_task(family: str, entry: dict, out_root: Path = config.TASK_DATA_DIR) -> Task:
    fam = families.get(entry.get("family", family))
    task_id, split = entry["task_id"], entry["split"]
    if split not in SPLITS:
        raise ValueError(f"{task_id}: split must be one of {SPLITS}")
    params = dict(entry["params"])
    dev_p = fam.GenParams(**params, seed=entry["dev_seed"])
    final_p = fam.GenParams(**{**params, **entry.get("final_overrides", {})}, seed=entry["final_seed"])

    tmp = out_root / f".{task_id}.building"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    files = {}
    for name, p in (("dev", dev_p), ("final", final_p)):
        data = fam.generate(p)
        files[f"{name}_input"] = _write(tmp / f"{name}_input.csv", data)
        files[f"{name}_expected"] = _write(tmp / f"{name}_expected.csv", fam.reference_output(data))
        if name == "dev":
            dev_profile = fam.profile(data)
    files["dev_profile"] = _write(tmp / "dev_profile.json", json.dumps(dev_profile, indent=2).encode())
    files["examples"] = _write(tmp / "examples.json", json.dumps(fam.examples(entry.get("examples_seed", 7), params), indent=2).encode())
    files["contract"] = _write(tmp / "contract.txt", fam.CONTRACT.encode())
    files["initial"] = _write(tmp / "initial.py", fam.INITIAL_CODE_PATH.read_bytes())

    manifest = {
        "task_id": task_id,
        "family": fam.FAMILY,
        "split": split,
        "notes": entry.get("notes", ""),
        "generator_version": fam.GENERATOR_VERSION,
        "checker_version": fam.CHECKER_VERSION,
        "generator_python": platform.python_version(),
        "dev_params": dev_p.to_dict(),
        "final_params": final_p.to_dict(),
        "examples_seed": entry.get("examples_seed", 7),
        "target": {"metric": "speedup", "definition": "baseline_median_s / candidate_median_s", "min_speedup": TARGET_MIN_SPEEDUP},
        "files": files,
        # Only these files may be shown to the model; the rest are evaluator-only.
        "agent_visible": ["contract", "initial", "examples", "dev_profile"],
    }
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
            "task_id": task_id, "family": fam.FAMILY, "split": split,
            "manifest_json": db.dumps(manifest), "manifest_sha256": manifest_sha, "registered_at": db.now(),
        })
    return Task(task_id, split, final_dir, manifest)


def build_spec(spec_path: Path) -> list[Task]:
    """A spec names a default family; an entry may name its own (mixed-family batches)."""
    spec = json.loads(spec_path.read_text())
    return [build_task(spec.get("family", ""), entry) for entry in spec["tasks"]]


def spec_paths() -> list[Path]:
    return sorted(config.TASK_SPEC_DIR.glob("spec*.json"))


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
