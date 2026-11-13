"""Experience records, immutable snapshots, deterministic retrieval and the active-snapshot pointer.

Experiences are extracted by the program from stored run records (no LLM summarisation). Each one says: under
these observed workload conditions, this change was tried, and the evaluator measured this. Model explanations
are kept but labelled as unverified hypotheses.
"""

from __future__ import annotations

import ast
import difflib
import json
from pathlib import Path

from . import config, db

RETRIEVAL = {
    "version": "retrieval-v1",
    "features": ["rows", "distinct_keys", "rows_per_key", "order", "skew"],
    "min_matches": 3,
    "max_per_outcome": {"success": 3, "failure": 2, "no_gain": 1},
    "rank": "matching features desc, then newest first",
}
LEARNABLE_SPLITS = {"A", "smoke"}
EXTRACTOR_VERSION = "extractor-v1"
NON_EVIDENCE_STATUSES = {"sandbox_error", "baseline_failed"}
_NOTABLE_CALLS = {
    "reader", "writer", "DictReader", "read", "readline", "readlines", "splitlines", "split", "rsplit", "partition",
    "rpartition", "find", "index", "groupby", "Counter", "defaultdict", "sorted", "sort", "map", "zip", "join",
    "write", "writelines", "decode", "encode", "int", "get", "setdefault", "update", "accumulate", "compile",
}


class PointerLocked(RuntimeError):
    pass


# ---------- conditions ----------

def buckets(profile: dict) -> dict:
    rows, dk = profile.get("rows", 0), profile.get("distinct_keys", 0)
    if rows == 0:
        return {"rows": "empty", "distinct_keys": "none", "rows_per_key": "none", "order": "none", "skew": "none"}
    rpk = profile.get("avg_rows_per_key", 0)
    sortedness = profile.get("sortedness", 0)
    if sortedness >= 0.999:
        order = "sorted"
    elif profile.get("key_runs_per_key", 99) <= 1.01:
        order = "clustered"
    elif sortedness >= 0.9:
        order = "nearly_sorted"
    else:
        order = "unsorted"
    return {
        "rows": "<100k" if rows < 100_000 else ("<1M" if rows < 1_000_000 else ">=1M"),
        "distinct_keys": "<1k" if dk < 1_000 else ("<100k" if dk < 100_000 else ">=100k"),
        "rows_per_key": "<=2" if rpk <= 2 else ("<=20" if rpk <= 20 else ">20"),
        "order": order,
        "skew": "high" if profile.get("top10_key_share", 0) >= 0.3 else "low",
    }


def _conditions(task_row, profile: dict) -> dict:
    keep = ("rows", "distinct_keys", "avg_rows_per_key", "duplicate_rate", "top10_key_share", "sortedness", "key_runs_per_key")
    return {"family": task_row["family"], "task_id": task_row["task_id"], "split": task_row["split"],
            "buckets": buckets(profile), "profile": {k: profile.get(k) for k in keep}}


# ---------- extraction ----------

def code_features(code: str) -> dict:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"parse_error": True}
    imports, calls = set(), set()
    loops = {"for": 0, "while": 0, "comprehension": 0}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if name in _NOTABLE_CALLS:
                calls.add(name)
        elif isinstance(node, ast.For):
            loops["for"] += 1
        elif isinstance(node, ast.While):
            loops["while"] += 1
        elif isinstance(node, ast.comprehension):
            loops["comprehension"] += 1
    uses_bytes_stdin = "buffer" in code and "stdin" in code
    return {"imports": sorted(imports), "calls": sorted(calls), "loops": loops, "binary_stdin": uses_bytes_stdin}


def _diff(a: str, b: str, max_lines: int = 80) -> str:
    lines = list(difflib.unified_diff(a.splitlines(), b.splitlines(), "initial.py", "candidate.py", n=1, lineterm=""))
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} more diff lines)"]
    return "\n".join(lines)


def _outcome(ev) -> str:
    if ev["status"] == "passed":
        return "success" if ev["improved"] else "no_gain"
    return "failure"


def extract(run_id: str) -> list[dict]:
    """Build experience records for every model candidate of a run that has a usable dev evaluation."""
    run = db.one("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    task_row = db.one("SELECT * FROM tasks WHERE task_id = ?", (run["task_id"],))
    manifest = json.loads(task_row["manifest_json"])
    profile = json.loads((config.TASK_DATA_DIR / run["task_id"] / "dev_profile.json").read_text())
    conditions = _conditions(task_row, profile)
    cands = {c["candidate_id"]: c for c in db.all_rows("SELECT * FROM candidates WHERE run_id = ?", (run_id,))}
    initial_code = Path(cands["c0"]["code_path"]).read_text()
    upgrades = db.one("SELECT COUNT(*) AS n FROM steps WHERE run_id = ? AND action = 'upgrade_model'", (run_id,))["n"]
    requests = db.one("SELECT COUNT(*) AS n FROM model_calls WHERE run_id = ?", (run_id,))["n"]
    cfg = json.loads(run["config_json"])

    out = []
    for cid, c in cands.items():
        if c["origin"] != "model":
            continue
        ev = db.one("SELECT * FROM evaluations WHERE run_id = ? AND candidate_id = ? AND dataset = 'dev'"
                    " ORDER BY ended_at DESC LIMIT 1", (run_id, cid))
        if ev is None or ev["status"] in NON_EVIDENCE_STATUSES:
            continue
        if ev["status"] == "passed" and ev["speedup"] is None:
            continue
        detail = json.loads(ev["detail_json"])
        failure = detail.get("failure") or {}
        step = db.one("SELECT * FROM steps WHERE run_id = ? AND candidate_id = ? AND action = 'propose_candidate'", (run_id, cid))
        call = db.one("SELECT * FROM model_calls WHERE call_id = ?", (step["model_call_id"],)) if step and step["model_call_id"] else None
        code = Path(c["code_path"]).read_text()
        timing = detail.get("timing") or {}
        out.append({
            "experience_id": f"e-{run_id.removeprefix('run-')}-{cid}",
            "outcome": _outcome(ev),
            "conditions": conditions,
            "action": {
                "kind": "propose_candidate",
                "parent_candidate_id": c["parent_candidate_id"],
                "code_sha256": c["code_sha256"],
                "code_features": code_features(code),
                "diff_vs_initial": _diff(initial_code, code),
                "model_stated_purpose": step["purpose"] if step else None,
            },
            "hypothesis": step["hypothesis"] if step else None,
            "result": {
                "status": ev["status"], "correct": None if ev["correct"] is None else bool(ev["correct"]),
                "speedup": ev["speedup"], "improved": None if ev["improved"] is None else bool(ev["improved"]),
                "goal_met": bool(ev["goal_met"]) if ev["goal_met"] is not None else None,
                "candidate_min_max_s": timing.get("candidate_min_max_s"),
                "baseline_min_max_s": timing.get("baseline_min_max_s"),
                "failure_category": failure.get("category"), "failure_kinds": failure.get("kinds"),
                "failure_example": (failure.get("examples") or [None])[0] or failure.get("message"),
                "target_min_speedup": manifest["target"]["min_speedup"],
            },
            "resources": {
                "model_role": call["role"] if call else None, "provider": call["provider"] if call else None,
                "model": call["model_returned"] or call["model_requested"] if call else None,
                "input_tokens": call["input_tokens"] if call else None, "output_tokens": call["output_tokens"] if call else None,
                "latency_s": call["latency_s"] if call else None, "cost_usd": call["cost_usd"] if call else None,
                "cost_status": call["cost_status"] if call else None,
                "run_model_requests": requests, "run_upgrades": upgrades,
            },
            "source": {
                "run_id": run_id, "step_seq": step["seq"] if step else None, "candidate_id": cid,
                "evaluation_id": ev["evaluation_id"], "evaluator_version": ev["evaluator_version"],
                "dataset": "dev", "dataset_sha256": ev["dataset_sha256"], "config_fingerprint": run["config_fingerprint"],
                "prompt_version": cfg["prompt"]["version"], "extractor_version": EXTRACTOR_VERSION, "evaluated_at": ev["ended_at"],
            },
        })
    return out


# ---------- snapshots ----------

def active_snapshot() -> str:
    return db.one("SELECT value FROM settings WHERE key = 'active_snapshot_id'")["value"]


def snapshot_experience_ids(snapshot_id: str) -> list[str]:
    return [r["experience_id"] for r in db.all_rows(
        "SELECT experience_id FROM snapshot_items WHERE snapshot_id = ? ORDER BY experience_id", (snapshot_id,))]


def publish(run_id: str) -> str | None:
    """Atomically publish parent snapshot + this run's experiences as a new version and make it active.

    Returns the new snapshot id, or None when the run produced no qualifying records (no empty versions).
    """
    run = db.one("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    if run["mode"] != "learn":
        raise ValueError("only learn-mode runs publish experience")
    records = extract(run_id)
    if not records:
        db.add_event(run_id, "learning_no_new_version", {"reason": "no qualifying experience records"})
        return None
    conn = db.get()
    conn.execute("BEGIN IMMEDIATE")
    try:
        parent = run["snapshot_id"]
        version = conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM snapshots").fetchone()[0]
        snap_id = f"v{version}"
        now = db.now()
        for r in records:
            conn.execute(
                "INSERT INTO experiences (experience_id, family, task_id, split, outcome, conditions_json, action_json,"
                " hypothesis, result_json, resources_json, source_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["experience_id"], r["conditions"]["family"], r["conditions"]["task_id"], r["conditions"]["split"],
                 r["outcome"], db.dumps(r["conditions"]), db.dumps(r["action"]), r["hypothesis"], db.dumps(r["result"]),
                 db.dumps(r["resources"]), db.dumps(r["source"]), now))
        inherited = snapshot_experience_ids(parent)
        added = [r["experience_id"] for r in records]
        diff = {"parent": parent, "added": [{"experience_id": r["experience_id"], "outcome": r["outcome"],
                                             "task_id": r["conditions"]["task_id"], "speedup": r["result"]["speedup"],
                                             "status": r["result"]["status"]} for r in records],
                "removed": [], "inherited_count": len(inherited)}
        conn.execute("INSERT INTO snapshots (snapshot_id, version, parent_snapshot_id, source_run_id, created_at, diff_json)"
                     " VALUES (?,?,?,?,?,?)", (snap_id, version, parent, run_id, now, db.dumps(diff)))
        conn.executemany("INSERT INTO snapshot_items (snapshot_id, experience_id) VALUES (?, ?)",
                         [(snap_id, e) for e in inherited + added])
        prev = conn.execute("SELECT value FROM settings WHERE key = 'active_snapshot_id'").fetchone()[0]
        conn.execute("UPDATE settings SET value = ? WHERE key = 'active_snapshot_id'", (snap_id,))
        conn.execute("INSERT INTO pointer_history (ts, from_snapshot_id, to_snapshot_id, reason, actor) VALUES (?,?,?,?,?)",
                     (now, prev, snap_id, f"学习运行 {run_id} 发布", "learning"))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    db.add_event(run_id, "snapshot_published", {"snapshot_id": snap_id, "parent": parent, "added": added})
    return snap_id


def activate(snapshot_id: str, reason: str, actor: str = "user") -> dict:
    """Switch the snapshot future runs read. History and running runs are untouched."""
    if not db.one("SELECT 1 FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)):
        raise KeyError(f"snapshot {snapshot_id} does not exist")
    learning = db.one("SELECT run_id FROM runs WHERE mode = 'learn' AND status = 'running'")
    if learning:
        raise PointerLocked(f"learn run {learning['run_id']} is in progress; switch after it publishes")
    prev = active_snapshot()
    db.update("settings", "key", "active_snapshot_id", {"value": snapshot_id})
    db.insert("pointer_history", {"ts": db.now(), "from_snapshot_id": prev, "to_snapshot_id": snapshot_id,
                                  "reason": reason, "actor": actor})
    return {"from": prev, "to": snapshot_id}


def experience(experience_id: str) -> dict:
    r = db.one("SELECT * FROM experiences WHERE experience_id = ?", (experience_id,))
    if not r:
        raise KeyError(experience_id)
    return {"experience_id": r["experience_id"], "outcome": r["outcome"], "conditions": json.loads(r["conditions_json"]),
            "action": json.loads(r["action_json"]), "hypothesis": r["hypothesis"], "result": json.loads(r["result_json"]),
            "resources": json.loads(r["resources_json"]), "source": json.loads(r["source_json"]), "created_at": r["created_at"]}


def snapshot(snapshot_id: str) -> dict:
    s = db.one("SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))
    if not s:
        raise KeyError(snapshot_id)
    exps = [experience(e) for e in snapshot_experience_ids(snapshot_id)]
    counts: dict[str, int] = {}
    for e in exps:
        counts[e["outcome"]] = counts.get(e["outcome"], 0) + 1
    return {"snapshot_id": s["snapshot_id"], "version": s["version"], "parent_snapshot_id": s["parent_snapshot_id"],
            "source_run_id": s["source_run_id"], "created_at": s["created_at"], "diff": json.loads(s["diff_json"]),
            "counts": counts, "experiences": exps, "active": active_snapshot() == snapshot_id}


def compare_snapshots(a: str, b: str) -> dict:
    ea, eb = set(snapshot_experience_ids(a)), set(snapshot_experience_ids(b))
    return {"from": a, "to": b, "added": sorted(eb - ea), "removed": sorted(ea - eb), "common": len(ea & eb)}


# ---------- retrieval ----------

def retrieve(snapshot_id: str, family: str, profile: dict) -> tuple[list[dict], dict]:
    """Deterministic selection of relevant experiences; returns (records for the prompt, selection summary)."""
    current = buckets(profile)
    scored = []
    for eid in snapshot_experience_ids(snapshot_id):
        e = experience(eid)
        if e["conditions"]["family"] != family:
            continue
        theirs = e["conditions"]["buckets"]
        matches = [f for f in RETRIEVAL["features"] if theirs.get(f) == current.get(f)]
        if len(matches) < RETRIEVAL["min_matches"]:
            continue
        differs = {f: {"experience": theirs.get(f), "current": current.get(f)} for f in RETRIEVAL["features"] if f not in matches}
        scored.append((len(matches), e["created_at"], e, differs))
    scored.sort(key=lambda t: t[1], reverse=True)  # newest first ...
    scored.sort(key=lambda t: t[0], reverse=True)  # ... within the same number of matching features (stable sort)
    by_outcome: dict[str, list] = {}
    for item in scored:
        by_outcome.setdefault(item[2]["outcome"], []).append(item)
    chosen = []
    for outcome, cap in RETRIEVAL["max_per_outcome"].items():
        chosen += by_outcome.get(outcome, [])[:cap]
    chosen.sort(key=lambda t: t[1], reverse=True)
    chosen.sort(key=lambda t: t[0], reverse=True)
    matched_counts = {k: len(v) for k, v in by_outcome.items()}
    records = []
    for score, _, e, differs in chosen:
        records.append({
            "experience_id": e["experience_id"],
            "outcome": e["outcome"],
            "match": {"matching_features": score, "of": len(RETRIEVAL["features"]), "differs": differs},
            "observed_conditions": {"task_id": e["conditions"]["task_id"], "buckets": e["conditions"]["buckets"],
                                    "profile": e["conditions"]["profile"]},
            "change": {"parent_candidate_id": e["action"]["parent_candidate_id"], "code_features": e["action"]["code_features"],
                       "diff_vs_initial_program": e["action"]["diff_vs_initial"]},
            "measured_result": {k: e["result"].get(k) for k in ("status", "correct", "speedup", "improved", "goal_met",
                                                                "failure_category", "failure_kinds", "failure_example")},
            "model_explanation_unverified": e["hypothesis"],
            "cost": {"model_role": e["resources"]["model_role"], "output_tokens": e["resources"]["output_tokens"],
                     "latency_s": e["resources"]["latency_s"]},
            "source": {"run_id": e["source"]["run_id"], "step_seq": e["source"]["step_seq"], "candidate_id": e["source"]["candidate_id"]},
        })
    summary = {"retrieval": RETRIEVAL["version"], "min_matches": RETRIEVAL["min_matches"], "current_buckets": current,
               "snapshot_size": len(snapshot_experience_ids(snapshot_id)),
               "matched_by_outcome": matched_counts, "selected": [r["experience_id"] for r in records],
               "scores": {r["experience_id"]: r["match"]["matching_features"] for r in records}}
    return records, summary
