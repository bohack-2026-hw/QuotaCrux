"""Benchmark adapter for the generated stdin/stdout task families."""
import json
import platform
import tempfile
from pathlib import Path
from types import ModuleType

from ..taskpkg import SPLITS, TARGET_MIN_SPEEDUP, _write, register_package
from . import Case


class GeneratedBenchmark:
    MIN_MATCHES = 3

    def __init__(self, family: ModuleType):
        self.family = family

    def build(self, entry: dict, out_root: Path):
        fam = self.family
        task_id, split = entry["task_id"], entry["split"]
        if split not in SPLITS:
            raise ValueError(f"{task_id}: split must be one of {SPLITS}")
        params = dict(entry["params"])
        dev_p = fam.GenParams(**params, seed=entry["dev_seed"])
        final_p = fam.GenParams(**{**params, **entry.get("final_overrides", {})}, seed=entry["final_seed"])

        tmp = Path(tempfile.mkdtemp(prefix=f".{task_id}-", dir=out_root))
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
            "agent_visible": ["contract", "initial", "examples", "dev_profile"],
        }
        return register_package(tmp, manifest, out_root)

    def buckets(self, profile: dict) -> dict:
        return self.family.buckets(profile)

    def compatible(self, current: dict, theirs: dict) -> bool:
        return True

    def cases(self, task, dataset: str) -> list[Case]:
        source, expected = task.dataset(dataset)
        return [Case(dataset, source.read_bytes(), expected.read_bytes())]

    def public_cases(self, task) -> list[Case]:
        return [Case(name, text.encode(), self.family.reference_output(text.encode()))
                for name, text in self.family.CONTRACT_CASES.items()]

    def check_outputs(self, task, cases, outputs, measure, limits) -> dict:
        for case, output in zip(cases, outputs, strict=True):
            check = self.family.check_output(output, case.expected)
            if not check["correct"]:
                return {**check, "failure": {**check["failure"], "case": case.name}}
        return {"format_ok": True, "correct": True}

    def presentation(self, manifest: dict) -> dict:
        return {
            "title": self.family.TITLE_ZH,
            "workload": self.family.describe(manifest["dev_params"]),
            "baseline": self.family.BASELINE_ZH,
            "validation": f"开发数据正确性 + {len(self.family.CONTRACT_CASES)} 个公开契约用例",
            "agent_notes": f"Public contract cases cover {self.family.CONTRACT_CASES_NOTE}.",
        }
