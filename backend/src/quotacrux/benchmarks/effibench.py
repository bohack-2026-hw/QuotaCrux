"""Pinned EffiBench-X Python tasks, adapted to QuotaCrux's runtime optimization protocol."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

from .. import config
from ..agent.actions import check_code
from ..sandbox import executor
from ..taskpkg import TARGET_MIN_SPEEDUP, _write, register_package, sha256_file
from . import Case

HERE = Path(__file__).resolve().parent
CATALOG = json.loads((HERE / "effibench_catalog.json").read_text())
REVISION = CATALOG["revision"]
ADAPTER_VERSION = "effibench-x-python-v1"
MIN_MATCHES = 1


def _stdlib_only(code: str) -> None:
    check_code(code, config.RunLimits().max_code_bytes)
    names = {n.id for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Name)}
    if names & {"SortedList", "SortedDict", "SortedSet", "sortedcontainers"}:
        raise ValueError("this task requires sortedcontainers; QuotaCrux supports the Python standard library only")


def import_problem(problem: str, *, split: str, dev_cases: int = 20, case_limit: int | None = None,
                   parquet: Path | None = None, task_id: str | None = None):
    """Read only the requested shard, verifying the pinned upstream SHA before parsing."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        raise RuntimeError("EffiBench import needs pyarrow: run `uv sync --extra benchmark`") from None
    item = next((p for p in CATALOG["problems"] if p["key"] == problem), None)
    if item is None:
        raise ValueError(f"unknown EffiBench-X problem {problem!r}; see benchmarks/effibench_catalog.json")
    shard = CATALOG["shards"][item["shard"]]
    if parquet is None:
        parquet = config.VAR_DIR / "benchmarks" / "effibench-x" / REVISION / Path(shard["file"]).name
        if not parquet.exists():
            parquet.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://huggingface.co/datasets/{CATALOG['dataset']}/resolve/{REVISION}/{shard['file']}"
            with tempfile.NamedTemporaryFile(dir=parquet.parent, delete=False) as tmp:
                tmp_path = Path(tmp.name)
                try:
                    with urllib.request.urlopen(url, timeout=60) as response:
                        shutil.copyfileobj(response, tmp, length=1 << 20)
                    tmp.close()
                    _verify_shard(tmp_path, shard)
                    tmp_path.replace(parquet)
                finally:
                    tmp_path.unlink(missing_ok=True)
    _verify_shard(parquet, shard)
    columns = ["id", "source", "title", "description_md", "type", "solutions.python3.code",
               "test_runners.python3", "generated_tests", "evaluator", "time_limit_nanos", "memory_limit_bytes"]
    rows = pq.ParquetFile(parquet).read(columns=columns).to_pylist()
    record = next(r for r in rows if f"{r['source']}/{r['id']}" == problem)
    config.TASK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return build_record(record, split=split, dev_cases=dev_cases, case_limit=case_limit, task_id=task_id,
                        provenance={"dataset": CATALOG["dataset"], "revision": REVISION,
                                    "shard": shard["file"], "shard_sha256": shard["sha256"]})


def _verify_shard(path: Path, shard: dict) -> None:
    if path.stat().st_size != shard["bytes"] or sha256_file(path) != shard["sha256"]:
        raise ValueError(f"{path}: does not match pinned EffiBench-X shard {shard['file']}")


def build_record(record: dict, *, split: str, dev_cases: int, provenance: dict,
                 case_limit: int | None = None, task_id: str | None = None,
                 out_root: Path = config.TASK_DATA_DIR):
    if split not in ("A", "B", "C", "D", "smoke"):
        raise ValueError("split must be A, B, C, D or smoke")
    if record["type"] not in ("io", "functional"):
        raise ValueError(f"unsupported EffiBench interface {record['type']!r}")
    key = f"{record['source']}/{record['id']}"
    raw = json.loads(record["generated_tests"])
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{key}: generated_tests must be a nonempty list")
    # Identical inputs must never straddle the dev/final boundary.
    unique, seen = [], {}
    for index, case in enumerate(raw):
        if not isinstance(case, dict) or not all(isinstance(case.get(k), str) for k in ("input", "output")):
            raise ValueError(f"{key}: case {index} must contain string input/output")
        digest = hashlib.sha256(case["input"].encode()).hexdigest()
        if digest in seen:
            if seen[digest] != case["output"]:
                raise ValueError(f"{key}: identical input has conflicting expected outputs")
            continue
        seen[digest] = case["output"]
        unique.append({"id": index, "input": case["input"], "output": case["output"], "sha256": digest})
    # Split on content hashes, not upstream order (which often starts with hand-picked examples).
    unique.sort(key=lambda c: c["sha256"])
    count = len(unique) if case_limit is None else case_limit
    if not 1 <= dev_cases < count <= len(unique):
        raise ValueError(f"need 1 <= dev_cases < case_limit <= {len(unique)} unique cases")
    selected = unique[:count]
    reference = record["solutions"]["python3"]["code"]
    runner = (record.get("test_runners") or {}).get("python3")
    checker = record["evaluator"]
    if not isinstance(reference, str) or not reference.strip() or not isinstance(checker, str) or not checker.strip():
        raise ValueError(f"{key}: Python reference and evaluator are required")
    if record["type"] == "functional":
        if not isinstance(runner, str) or runner.count("==Code Submission==") != 1:
            raise ValueError(f"{key}: expected one Python runner submission placeholder")
        # Preserve imports in the submission; runner and reference become one visible stdin/stdout program.
        template = "\n".join("==Code Submission==" if "==Code Submission==" in line else line for line in runner.splitlines())
        initial = (HERE / "effibench_imports.py").read_text() + "\n" + template.replace("==Code Submission==", reference)
    else:
        initial = reference
    _stdlib_only(initial)
    _stdlib_only(checker)
    if not any(isinstance(n, ast.FunctionDef) and n.name == "evaluate" for n in ast.parse(checker).body):
        raise ValueError(f"{key}: evaluator must define evaluate(output, expected)")
    memory_key = hashlib.sha256(json.dumps({"problem": key, "revision": provenance["revision"],
                                           "checker": checker, "runner": runner, "adapter": ADAPTER_VERSION,
                                           "dev_inputs": [c["sha256"] for c in selected[:dev_cases]]}, sort_keys=True).encode()).hexdigest()
    task_id = task_id or f"ebx-{record['source']}-{record['id']}-{split}-{dev_cases}-{count}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", task_id):
        raise ValueError("task_id must contain only letters, digits, dots, underscores and hyphens (max 120 characters)")
    out_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{task_id}-", dir=out_root))
    try:
        files = {}
        for name, cases_ in (("dev", selected[:dev_cases]), ("final", selected[dev_cases:])):
            for kind, field in (("input", "input"), ("expected", "output")):
                values = [{"id": c["id"], "text": c[field]} for c in cases_]
                files[f"{name}_{kind}"] = _write(tmp / f"{name}_{kind}.json", json.dumps(values).encode())
        profile = {"problem": key, "memory_key": memory_key, "interface": record["type"], "cases": dev_cases,
                   "input_bytes": sum(len(c["input"].encode()) for c in selected[:dev_cases])}
        contract = (f"EffiBench-X: {record['title']} ({key})\n\n{record['description_md']}\n\n"
                    "QuotaCrux interface: submit a complete Python 3.12 standard-library program reading stdin and writing stdout. "
                    "For functional tasks, initial.py includes the upstream serializer and runner. Preserve its I/O contract. "
                    "Each test case runs in a fresh process. Optimize the provided reference program.\n")
        # Public examples are dev-only and bounded; final inputs/outputs never enter model context.
        examples = [{"input": c["input"], "output": c["output"]} for c in selected[:dev_cases]
                    if len(c["input"].encode()) + len(c["output"].encode()) <= 4000][:2]
        for name, filename, value in (("dev_profile", "dev_profile.json", json.dumps(profile).encode()),
                                      ("examples", "examples.json", json.dumps(examples).encode()),
                                      ("contract", "contract.txt", contract.encode()),
                                      ("initial", "initial.py", initial.encode()),
                                      ("checker", "checker.py", checker.encode())):
            files[name] = _write(tmp / filename, value)
        manifest = {
            "task_id": task_id, "family": "effibench-x", "split": split, "notes": record["title"],
            "adapter_version": ADAPTER_VERSION, "checker_version": ADAPTER_VERSION,
            "problem": {"key": key, "title": record["title"], "interface": record["type"]},
            "source": provenance, "memory_key": memory_key,
            "upstream_limits": {"time_limit_nanos": record.get("time_limit_nanos"), "memory_limit_bytes": record.get("memory_limit_bytes")},
            "selection": {"raw_cases": len(raw), "unique_cases": len(unique), "selected_cases": count,
                          "order": "sha256(input) ascending", "dev_ids": [c["id"] for c in selected[:dev_cases]],
                          "final_ids": [c["id"] for c in selected[dev_cases:]], "protocol": "routeevo-runtime-optimization-v1"},
            "dev_params": {"cases": dev_cases}, "final_params": {"cases": count - dev_cases},
            "target": {"metric": "speedup", "definition": "baseline_median_suite_s / candidate_median_suite_s", "min_speedup": TARGET_MIN_SPEEDUP},
            "files": files, "agent_visible": ["contract", "initial", "examples", "dev_profile"],
        }
        return register_package(tmp, manifest, out_root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cases(task, dataset: str) -> list[Case]:
    source, expected = task.dataset(dataset)
    inputs, outputs = json.loads(source.read_text()), json.loads(expected.read_text())
    return [Case(str(i["id"]), i["text"].encode(), o["text"].encode()) for i, o in zip(inputs, outputs, strict=True)]


def public_cases(task) -> list[Case]:
    return []  # Visible examples already belong to the frozen dev suite.


def check_outputs(task, cases, outputs, measure, limits) -> dict:
    payload = {"checker": (task.dir / "checker.py").read_text(),
               "pairs": [[output.decode("utf-8", errors="replace"), case.expected.decode()]
                         for case, output in zip(cases, outputs, strict=True)]}
    code = (HERE / "effibench_imports.py").read_bytes() + b"\n" + (HERE / "effibench_judge.py").read_bytes()
    result = executor.run_sample(code, json.dumps(payload).encode(), limits.measurement_timeout_s, measure)
    if result.status != "ok":
        return {"format_ok": None, "correct": None, "failure": {"category": "checker_error", "checker_status": result.status}}
    try:
        verdicts = json.loads(result.stdout)
        if not isinstance(verdicts, list) or len(verdicts) != len(cases) or not all(type(v) is bool for v in verdicts):
            raise ValueError("invalid checker response")
    except (ValueError, UnicodeDecodeError):
        return {"format_ok": None, "correct": None, "failure": {"category": "checker_error", "message": "invalid checker response"}}
    for case, passed in zip(cases, verdicts, strict=True):
        if not passed:
            return {"format_ok": True, "correct": False, "failure": {"category": "wrong_output", "case": case.name}}
    return {"format_ok": True, "correct": True}


def buckets(profile: dict) -> dict:
    return {"problem": profile["memory_key"]}


def presentation(manifest: dict) -> dict:
    return {
        "title": f"EffiBench-X · {manifest['problem']['title']}",
        "workload": f"{manifest['problem']['key']} · {manifest['problem']['interface']} · {manifest['dev_params']['cases']} 个开发用例",
        "baseline": "c0：数据集 Python 参考解（functional 题含原始 runner）",
        "validation": "冻结用例逐例执行 + 数据集 evaluator 在独立沙箱中校验",
        "agent_notes": "The evaluator checks every case in the selected suite with the dataset's checker. "
                       "One timing sample is the sum of fresh-process runtimes over the entire suite; "
                       "cProfile evidence uses the first dev case only. This is the QuotaCrux optimization protocol.",
    }


def compatible(current: dict, theirs: dict) -> bool:
    return current == theirs
