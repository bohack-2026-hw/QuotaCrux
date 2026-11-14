import subprocess
import sys

import pytest

from quotacrux import families
from quotacrux.families import intervals, logstats

NEW = {
    "logstats": [dict(rows=3000, endpoints=40, hours=5, order=o, disorder=0.05, error_rate=0.1) for o in ("time", "nearly_time", "shuffled")],
    "intervals": [dict(rows=3000, value_min=-500, value_max=5000, length_mean=5, order=o, disorder=0.05, duplicate_rate=0.1)
                  for o in ("random", "sorted", "nearly_sorted")],
}


def run_initial(fam, data: bytes) -> bytes:
    return subprocess.run([sys.executable, str(fam.INITIAL_CODE_PATH)], input=data, capture_output=True, check=True).stdout


def test_registry_has_every_family_and_hooks():
    assert set(families.REGISTRY) == {"groupagg", "logstats", "intervals"}
    for fam in families.REGISTRY.values():
        for hook in ("CONTRACT", "CONTRACT_CASES", "CONTRACT_CASES_NOTE", "BUCKET_FEATURES", "CONDITION_PROFILE_KEYS",
                     "generate", "reference_output", "profile", "check_output", "buckets", "examples", "describe"):
            assert hasattr(fam, hook), (fam.FAMILY, hook)
        assert len(fam.BUCKET_FEATURES) == 5
    with pytest.raises(ValueError):
        families.get("nope")


@pytest.mark.parametrize("name", sorted(NEW))
def test_initial_program_matches_reference(name):
    fam = families.get(name)
    for i, params in enumerate(NEW[name]):
        p = fam.GenParams(**params, seed=10 + i)
        data = fam.generate(p)
        assert data == fam.generate(p)  # deterministic
        assert run_initial(fam, data) == fam.reference_output(data), params
    for case, text in fam.CONTRACT_CASES.items():
        assert run_initial(fam, text.encode()) == fam.reference_output(text.encode()), case


def test_logstats_contract_details():
    out = logstats.reference_output(logstats.CONTRACT_CASES["hour_and_day_boundaries"].encode()).decode().splitlines()
    assert out == ["hour,method,path,count,errors,sum_ms,max_ms", "2026-12-31T23,GET,/a,2,1,4,3", "2027-01-01T00,GET,/a,2,0,6,4"]
    order = [line.split(",")[1:3] for line in logstats.reference_output(logstats.CONTRACT_CASES["method_and_path_order"].encode()).decode().splitlines()[1:]]
    assert order == [["DELETE", "/a"], ["GET", "/a"], ["GET", "/a-b"], ["GET", "/a/b"], ["GET", "/a0"], ["GET", "/a_b"],
                     ["PATCH", "/a"], ["POST", "/a"], ["PUT", "/a"]]
    assert logstats.reference_output(b"") == b"hour,method,path,count,errors,sum_ms,max_ms\n"


def test_intervals_contract_details():
    out = intervals.reference_output(intervals.CONTRACT_CASES["touching_and_gap"].encode()).decode().splitlines()
    assert out == ["start,end", "1,5", "7,8", "9,9", "10,10"]
    out = intervals.reference_output(intervals.CONTRACT_CASES["nested_and_transitive"].encode()).decode().splitlines()
    assert out == ["start,end", "1,10", "11,20", "21,30"]


def test_checkers_report_concrete_failures():
    ref = logstats.reference_output(logstats.generate(logstats.GenParams(rows=500, endpoints=10, hours=3, seed=1)))
    lines = ref.split(b"\n")
    lines[1], lines[2] = lines[2], lines[1]
    assert logstats.check_output(b"\n".join(lines), ref)["failure"]["kinds"] == ["wrong_order"]
    assert logstats.check_output(b"hour,method\n", ref)["failure"]["category"] == "format_error"
    got = intervals.check_output(b"start,end\n1,2\n", intervals.reference_output(b"start,end\n1,3\n"))
    assert got["failure"]["kinds"] == ["wrong_values"] and got["failure"]["examples"][0]["expected"] == "1,3"
    assert intervals.check_output(b"start,end\r\n1,3\r\n", b"start,end\n1,3\n")["correct"]


def test_buckets_separate_conditions():
    t = logstats.buckets(logstats.profile(logstats.generate(logstats.GenParams(rows=4000, endpoints=20, hours=2, seed=3))))
    s = logstats.buckets(logstats.profile(logstats.generate(logstats.GenParams(rows=4000, endpoints=2000, hours=30, seed=3, order="shuffled", error_rate=0.2))))
    assert t["order"] == "time_sorted" and s["order"] == "unsorted" and s["errors"] == "high" and t["rows_per_group"] != s["rows_per_group"]
    small = intervals.buckets(intervals.profile(intervals.generate(intervals.GenParams(rows=2000, seed=4))))
    big = intervals.buckets(intervals.profile(intervals.generate(intervals.GenParams(rows=2000, seed=4, value_min=-10**12, value_max=10**12, order="sorted"))))
    assert (small["magnitude"], small["sign"], small["order"]) == ("<2^31", "non_negative", "unsorted")
    assert (big["magnitude"], big["sign"], big["order"]) == (">=2^31", "has_negative", "sorted")
    assert logstats.buckets({"rows": 0})["rows"] == "empty"
