"""Public native profiles describe dev inputs and remain part of frozen task identity."""
import base64
import copy
import json

import pytest

from routeevo import config, taskpkg
from routeevo.benchmarks import algotune, native


def array(length):
    return {"__array__": True, "dtype": "<f8", "shape": [length],
            "data": base64.b64encode(b"\0" * (8 * length)).decode()}


@pytest.fixture
def import_generated(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "VAR_DIR", tmp_path)
    monkeypatch.setattr(config, "TASK_DATA_DIR", tmp_path / "tasks")

    def fetch(url, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class Task:\n    def solve(self, problem):\n        return problem\n"
                        if path.name == "task.py" else "fixture license")
        return path

    monkeypatch.setattr(native, "fetch", fetch)
    image = {"image_id": "sha256:profile-fixture", "image_tag": "profile-fixture"}
    monkeypatch.setattr(algotune, "scientific_image", lambda: image)
    monkeypatch.setattr(native, "build_image", lambda *args: image)

    def run(problem, dev):
        # The final record deliberately has no usable dev schema.
        generated = dev + [{"private_marker": "FINAL_INPUT_MUST_STAY_PRIVATE"}]
        monkeypatch.setattr(native, "worker", lambda *args, **kwargs: {"problems": generated})
        return algotune.import_problem(problem, split="smoke", size=1000,
                                       dev_cases=len(dev), final_cases=1)

    return run


def test_convolution_profile_uses_encoded_input_shapes_and_only_dev(import_generated):
    inputs = {"__tuple__": [array(30000), array(8000)]}
    task = import_generated("convolve_1d", [inputs])
    profile = task.dev_profile["input_profile"]
    case = profile["cases"][0]
    assert profile["generator_scale"] == 1000
    assert case["a"]["shape"] == [30000] and case["b"]["shape"] == [8000]
    assert case["a"]["dtype"] == case["b"]["dtype"] == "float64"
    assert case["a"]["nbytes"] == 240000 and case["b"]["nbytes"] == 64000
    assert case["output_shape"] == [37999]
    public = json.dumps(task.dev_profile) + task.contract + task.initial_code
    assert "FINAL_INPUT_MUST_STAY_PRIVATE" not in public
    assert inputs["__tuple__"][0]["data"] not in public
    assert "norm(solution - reference, 2) / (norm(reference, 2) + 1e-12) <= 1e-6" in task.contract
    assert "Return a NumPy array" in task.contract and "mode='full'" in task.contract
    assert "generator scale=1000" in task.presentation["workload"]
    assert taskpkg.load(task.task_id).dev_profile == task.dev_profile


def test_profile_is_observed_instead_of_reconstructed_from_generator_scale():
    profile = algotune.input_profile("convolve_1d",
        [{"id": "dev", "problem": {"__tuple__": [array(9), array(4)]}}], size=1000)
    assert profile["cases"][0]["a"]["shape"] == [9]
    assert profile["cases"][0]["b"]["shape"] == [4]
    assert profile["cases"][0]["output_shape"] == [12]


def test_pagerank_profile_measures_edges_and_exposes_checker_contract(import_generated):
    task = import_generated("pagerank", [{"adjacency_list": [[1, 2], [], [1]]}])
    case = task.dev_profile["input_profile"]["cases"][0]
    assert case["nodes"] == 3 and case["directed_edges"] == 3
    assert case["dangling_nodes"] == 1
    assert case["out_degree"] == {"min": 0, "max": 2, "mean": 1}
    assert case["output_scores"] == 3
    assert "adjacency_list" not in json.dumps(task.dev_profile)
    assert "FINAL_INPUT_MUST_STAY_PRIVATE" not in json.dumps(task.dev_profile)
    assert "numpy.allclose(rtol=1e-5, atol=1e-8)" in task.contract
    assert "math.isclose(rel_tol=1e-5, abs_tol=1e-8)" in task.contract
    assert "max_iter=100, tol=1e-6" in task.contract
    assert "list[float | int]" in task.contract


@pytest.mark.parametrize("change", [{"shape": [1000]}, {"shape": [2, 2]}, {"dtype": "<f4"}])
def test_convolution_rejects_inaccurate_array_metadata(change):
    invalid = {**array(4), **change}
    with pytest.raises(ValueError, match="convolve_1d"):
        algotune.input_profile("convolve_1d",
            [{"id": "dev", "problem": {"__tuple__": [invalid, array(2)]}}], size=1)


def test_pagerank_rejects_edges_outside_observed_graph():
    with pytest.raises(ValueError, match="in-range integer node IDs"):
        algotune.input_profile("pagerank",
            [{"id": "dev", "problem": {"adjacency_list": [[3], []]}}], size=1000)


def test_profile_changes_task_identity_without_rewriting_old_packages(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TASK_DATA_DIR", tmp_path)

    def build(**kwargs):
        return native.package("algotune", "profile-fixture", "smoke", {"revision": "fixture"},
            "contract", "initial", [{"id": "dev"}], [{"id": "final"}],
            objective={"metric": "speedup", "direction": "maximize"}, settings={}, **kwargs)

    old = build()
    old_manifest = (old.dir / "manifest.json").read_bytes()
    old_profile = (old.dir / "dev_profile.json").read_bytes()
    first = build(input_profile={"shape": [30]})
    changed = build(input_profile={"shape": [30000]})
    assert len({old.task_id, first.task_id, changed.task_id}) == 3
    assert first.manifest["files"]["dev_profile"]["sha256"] != changed.manifest["files"]["dev_profile"]["sha256"]
    first_manifest = copy.deepcopy(first.manifest)
    with pytest.raises(RuntimeError, match="task ids are immutable"):
        build(task_id=first.task_id, input_profile={"shape": [30000]})
    assert taskpkg.load(first.task_id).manifest == first_manifest
    assert (old.dir / "manifest.json").read_bytes() == old_manifest
    assert (old.dir / "dev_profile.json").read_bytes() == old_profile
