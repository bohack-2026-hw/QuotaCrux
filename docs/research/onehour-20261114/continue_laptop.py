"""Preserve the SIGTERM-interrupted attempt and finish the three original laptop cells."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path("/tmp/quotacrux-onehour-20261114/laptop")
REPO = Path("/tmp/quotacrux-onehour-20261114/source")


def save(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def main():
    os.environ["ROUTEEVO_VAR_DIR"] = str(ROOT / "var")
    os.environ.pop("ROUTEEVO_NO_DOTENV", None)
    sys.path.insert(0, str(REPO / "backend/src"))
    from routeevo import config, db, report, taskpkg
    from routeevo.agent import routing
    from routeevo.agent.runner import Runner, RunOptions
    from routeevo.routing_ablation import costs

    config.load_dotenv(Path("/home/hycx233/Projects/bohack/RouteEvo/backend/.env"))
    os.environ["ROUTEEVO_NO_DOTENV"] = "1"
    frozen = json.loads((ROOT / "execution-freeze.json").read_text())
    for path, expected in frozen["source_files"].items():
        assert hashlib.sha256((REPO / "backend" / path).read_bytes()).hexdigest() == expected, path
    small, large = frozen["models"]["small"], frozen["models"]["large"]
    os.environ.update({"QWEN_BASE_URL": small["base_url"], "QWEN_MODEL": small["model"],
        "QWEN_RESPONSE_FORMAT": small["response_format"], "QWEN_ENABLE_THINKING": "false",
        "QWEN_MAX_OUTPUT_TOKENS": str(small["max_output_tokens"]), "QWEN_REASONING_EFFORT": "",
        "OPENAI_BASE_URL": large["base_url"], "OPENAI_MODEL": large["model"],
        "OPENAI_REASONING_EFFORT": large["reasoning_effort"],
        "OPENAI_MAX_OUTPUT_TOKENS": str(large["max_output_tokens"])})
    os.environ.pop("QWEN_TEMPERATURE", None)
    models = {k: v.public_dict() for k, v in config.default_model_configs().items()}
    models["decisions"] = routing.decision_config("router_action").public_dict()
    assert models == frozen["models"]
    task = taskpkg.load(frozen["task_id"])
    limits, measure = config.RunLimits(**frozen["limits"]), config.MeasureConfig(**frozen["measure"])
    assert task.adapter.environment_info(task, measure) == frozen["environment"]
    batch = json.loads((ROOT / "batch.json").read_text())
    assert [r["status"] for r in batch["runs"]] == ["completed", "running", "not_run", "not_run"]
    interrupted = deepcopy(batch["runs"][1])
    old_id = interrupted["run_id"]
    assert db.one("SELECT COUNT(*) AS n FROM candidates WHERE run_id=? AND candidate_id!='c0'", (old_id,))["n"] == 0
    calls = [dict(x) for x in db.all_rows("SELECT call_id,role,status,latency_s FROM model_calls WHERE run_id=?", (old_id,))]
    starts = [dict(x) for x in db.all_rows("SELECT type,payload_json,ts FROM events WHERE run_id=? AND type='model_started'", (old_id,))]
    note = {"observed_at": db.now(), "exit_code": 143, "reason": "execution session ended with SIGTERM",
        "run_id": old_id, "model_calls_recorded": calls, "model_started_events": starts,
        "decision": "retain interrupted attempt; repeat its uncompleted cell, then finish the two unstarted cells",
        "selection_evidence": "zero generated candidates and no final evaluation before interruption",
        "unmatched_started_calls": len(starts) - len(calls),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "inherited_freeze_sha256": hashlib.sha256((ROOT / "execution-freeze.json").read_bytes()).hexdigest()}
    with (ROOT / "continuation-freeze.json").open("x") as out:
        json.dump(note, out, ensure_ascii=False, indent=2)
    (ROOT / "batch-before-interruption.json").write_bytes((ROOT / "batch.json").read_bytes())
    interrupted.update(status="interrupted", final_status="not_run", interruption=note)
    batch["interrupted_attempts"] = [interrupted]
    batch["runs"][1] = {"seq": 2, "variant": "adaptive_rule", "status": "not_run", "replaces_interrupted_attempt": old_id}
    batch["continuation_started_at"] = db.now()
    save(ROOT / "batch.json", batch)
    try:
        for step in batch["runs"][1:]:
            if datetime.now(timezone.utc) >= datetime(2026, 11, 14, 15, 48, tzinfo=timezone.utc):
                batch["status"] = "time_limit"
                break
            fixed = {"fixed_small": "small", "fixed_large": "large"}.get(step["variant"])
            runner = Runner(RunOptions(task_id=task.task_id, mode="eval", snapshot_id="v0", research_mode="feedback",
                research_model_policy="fixed" if fixed else "adaptive", fixed_model=fixed, router=False,
                final_evaluation=True, limits=limits, measure=measure,
                label=f"onehour-20261114 laptop {step['variant']} continuation"))
            step.update(run_id=runner.create(), status="running", started_at=db.now())
            if not (config.RUNS_DIR / old_id / "report.json").exists():
                save(config.RUNS_DIR / old_id / "report.json", report.build(old_id))
            save(ROOT / "batch.json", batch)
            print(json.dumps(step), flush=True)
            rep = runner.execute()
            step.update(status=rep["status"], final_status=rep["outcome"]["final_status"], stop_reason=rep["stop_reason"],
                report_path=str(runner.dir / "report.json"), timing=rep["timing"], cost=costs(rep["usage"]["by_model"], frozen["price_snapshots"]))
            save(ROOT / "batch.json", batch)
            print(json.dumps({k: step[k] for k in ("variant", "run_id", "status", "final_status")}), flush=True)
            if rep["status"] != "completed" or rep["outcome"]["final_status"] != "completed":
                batch["status"] = "interrupted"
                break
        else:
            batch["status"] = "completed"
    except BaseException as exc:
        batch.update(status="interrupted", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        batch["ended_at"] = db.now()
        batch["elapsed_s"] = (datetime.fromisoformat(batch["ended_at"]) - datetime.fromisoformat(batch["created_at"])).total_seconds()
        save(ROOT / "batch.json", batch)


if __name__ == "__main__":
    main()
