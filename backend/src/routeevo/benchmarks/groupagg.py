"""The original group aggregation benchmark; generated manifests remain unchanged."""
import json
import platform
import tempfile
from pathlib import Path

from ..families import groupagg
from ..taskpkg import TARGET_MIN_SPEEDUP, _write, register_package
from . import Case

MIN_MATCHES = 3


def _examples(seed: int, order: str) -> list[dict]:
    """Small visible input/output pairs, generated from seeds unrelated to dev/final data."""
    cases = [
        groupagg.GenParams(rows=0, keys=1, seed=seed),
        groupagg.GenParams(rows=10, keys=4, seed=seed + 1, key_len_min=1, key_len_max=3, order=order, value_min=-20, value_max=20),
        groupagg.GenParams(rows=8, keys=8, seed=seed + 2, key_len_min=1, key_len_max=4, value_min=-5, value_max=5),
    ]
    out = []
    for p in cases:
        data = groupagg.generate(p)
        out.append({"input": data.decode(), "output": groupagg.reference_output(data).decode()})
    return out


def build(entry: dict, out_root: Path):
    family = groupagg.FAMILY
    task_id, split = entry["task_id"], entry["split"]
    if split not in ("A", "B", "C", "D", "smoke"):
        raise ValueError(f"{task_id}: split must be A, B, C, D or smoke")
    params = dict(entry["params"])
    dev_p = groupagg.GenParams(**params, seed=entry["dev_seed"])
    final_p = groupagg.GenParams(**{**params, **entry.get("final_overrides", {})}, seed=entry["final_seed"])

    tmp = Path(tempfile.mkdtemp(prefix=f".{task_id}-", dir=out_root))
    files = {}
    for name, p in (("dev", dev_p), ("final", final_p)):
        data = groupagg.generate(p)
        files[f"{name}_input"] = _write(tmp / f"{name}_input.csv", data)
        files[f"{name}_expected"] = _write(tmp / f"{name}_expected.csv", groupagg.reference_output(data))
        if name == "dev":
            dev_profile = groupagg.profile(data)
    files["dev_profile"] = _write(tmp / "dev_profile.json", json.dumps(dev_profile, indent=2).encode())
    files["examples"] = _write(tmp / "examples.json", json.dumps(_examples(entry.get("examples_seed", 7), params.get("order", "random")), indent=2).encode())
    files["contract"] = _write(tmp / "contract.txt", groupagg.CONTRACT.encode())
    files["initial"] = _write(tmp / "initial.py", groupagg.INITIAL_CODE_PATH.read_bytes())

    manifest = {
        "task_id": task_id,
        "family": family,
        "split": split,
        "notes": entry.get("notes", ""),
        "generator_version": groupagg.GENERATOR_VERSION,
        "checker_version": groupagg.CHECKER_VERSION,
        "generator_python": platform.python_version(),
        "dev_params": dev_p.to_dict(),
        "final_params": final_p.to_dict(),
        "examples_seed": entry.get("examples_seed", 7),
        "target": {"metric": "speedup", "definition": "baseline_median_s / candidate_median_s", "min_speedup": TARGET_MIN_SPEEDUP},
        "files": files,
        # Only these files may be shown to the model; the rest are evaluator-only.
        "agent_visible": ["contract", "initial", "examples", "dev_profile"],
    }
    return register_package(tmp, manifest, out_root)


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


def cases(task, dataset: str) -> list[Case]:
    source, expected = task.dataset(dataset)
    return [Case(dataset, source.read_bytes(), expected.read_bytes())]


def public_cases(task) -> list[Case]:
    return [Case(name, text.encode(), groupagg.reference_output(text.encode()))
            for name, text in groupagg.CONTRACT_CASES.items()]


def check_outputs(task, cases, outputs, measure, limits) -> dict:
    for case, output in zip(cases, outputs, strict=True):
        check = groupagg.check_output(output, case.expected)
        if not check["correct"]:
            return {**check, "failure": {**check["failure"], "case": case.name}}
    return {"format_ok": True, "correct": True}


def presentation(manifest: dict) -> dict:
    p = manifest["dev_params"]
    return {
        "title": "分组聚合",
        "workload": f"{p['rows']:,} 行 · {p['keys']:,} 个 key · {p['order']} · 偏斜 {p['skew']}",
        "baseline": "c0：csv + 两个 dict + sorted（初始程序）",
        "validation": "开发数据正确性 + 7 个公开契约用例",
        "agent_notes": "Public contract cases cover empty input, single rows, interleaved repeated keys, ASCII ordering, "
                       "large and negative integers, nearly sorted input and 32-character keys.",
    }


def compatible(current: dict, theirs: dict) -> bool:
    return True
