"""Finish only the two unstarted controls; retain the adaptive API failure."""
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path("/tmp/quotacrux-onehour-20261114/laptop")
REPO = Path("/tmp/quotacrux-onehour-20261114/source")
os.environ["ROUTEEVO_VAR_DIR"] = str(ROOT / "var")
sys.path.insert(0, str(REPO / "backend/src"))
from routeevo import config, db, taskpkg
from routeevo.agent.runner import Runner, RunOptions
from routeevo.agent import routing
from routeevo.routing_ablation import costs
from run_batch import save

config.load_dotenv(Path("/home/hycx233/Projects/bohack/RouteEvo/backend/.env"))
os.environ["ROUTEEVO_NO_DOTENV"] = "1"
frozen = json.loads((ROOT / "execution-freeze.json").read_text())
for path, expected in frozen["source_files"].items():
    assert hashlib.sha256((REPO / "backend" / path).read_bytes()).hexdigest() == expected
small, large = frozen["models"]["small"], frozen["models"]["large"]
os.environ.update({"QWEN_BASE_URL": small["base_url"], "QWEN_MODEL": small["model"],
    "QWEN_RESPONSE_FORMAT": small["response_format"], "QWEN_ENABLE_THINKING": "false",
    "QWEN_MAX_OUTPUT_TOKENS": str(small["max_output_tokens"]), "QWEN_REASONING_EFFORT": "",
    "OPENAI_BASE_URL": large["base_url"], "OPENAI_MODEL": large["model"],
    "OPENAI_REASONING_EFFORT": large["reasoning_effort"], "OPENAI_MAX_OUTPUT_TOKENS": str(large["max_output_tokens"])})
os.environ.pop("QWEN_TEMPERATURE", None)
models = {k: v.public_dict() for k, v in config.default_model_configs().items()}
models["decisions"] = routing.decision_config("router_action").public_dict()
assert models == frozen["models"]
task = taskpkg.load(frozen["task_id"])
limits, measure = config.RunLimits(**frozen["limits"]), config.MeasureConfig(**frozen["measure"])
assert task.adapter.environment_info(task, measure) == frozen["environment"]
batch = json.loads((ROOT / "batch.json").read_text())
assert [r["status"] for r in batch["runs"]] == ["completed", "failed", "not_run", "not_run"]
assert batch["runs"][1]["final_status"] == "completed"
with (ROOT / "finish-controls-freeze.json").open("x") as out:
    json.dump({"created_at": db.now(), "plan": ["fixed_large", "fixed_small"],
        "reason": "retain adaptive API-failed run and its valid final; execute only unstarted controls",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "inherited_freeze_sha256": hashlib.sha256((ROOT / "execution-freeze.json").read_bytes()).hexdigest()}, out, indent=2)
batch["status"] = "running"
save(ROOT / "batch.json", batch)
try:
    for step in batch["runs"][2:]:
        if datetime.now(timezone.utc) >= datetime(2026, 11, 14, 15, 48, tzinfo=timezone.utc):
            batch["status"] = "time_limit"
            break
        fixed = step["variant"].removeprefix("fixed_")
        runner = Runner(RunOptions(task_id=task.task_id, mode="eval", snapshot_id="v0", research_mode="feedback",
            fixed_model=fixed, router=False, final_evaluation=True, limits=limits, measure=measure,
            label=f"onehour-20261114 laptop {step['variant']} remaining control"))
        step.update(run_id=runner.create(), status="running", started_at=db.now())
        save(ROOT / "batch.json", batch)
        print(json.dumps(step), flush=True)
        rep = runner.execute()
        step.update(status=rep["status"], final_status=rep["outcome"]["final_status"], stop_reason=rep["stop_reason"],
            report_path=str(runner.dir / "report.json"), timing=rep["timing"], cost=costs(rep["usage"]["by_model"], frozen["price_snapshots"]))
        save(ROOT / "batch.json", batch)
        print(json.dumps({k: step[k] for k in ("variant", "run_id", "status", "final_status")}), flush=True)
    else:
        batch["status"] = "completed_with_failures" if any(r["status"] != "completed" for r in batch["runs"]) else "completed"
except BaseException as exc:
    batch.update(status="interrupted", error=f"{type(exc).__name__}: {exc}")
    raise
finally:
    batch["ended_at"] = db.now()
    batch["elapsed_s"] = (datetime.fromisoformat(batch["ended_at"]) - datetime.fromisoformat(batch["created_at"])).total_seconds()
    save(ROOT / "batch.json", batch)
