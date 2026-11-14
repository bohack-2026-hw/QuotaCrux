import subprocess
import sys

from quotacrux.families import groupagg
from quotacrux.families.groupagg import GenParams


def run_initial(data: bytes) -> bytes:
    return subprocess.run([sys.executable, str(groupagg.INITIAL_CODE_PATH)], input=data, capture_output=True, check=True).stdout


def test_generator_is_deterministic():
    p = GenParams(rows=2000, keys=50, seed=3, skew=1.0)
    assert groupagg.generate(p) == groupagg.generate(p)
    assert groupagg.generate(p) != groupagg.generate(GenParams(rows=2000, keys=50, seed=4, skew=1.0))


def test_initial_program_matches_reference_for_all_orders():
    for order in ("random", "sorted", "nearly_sorted", "clustered"):
        data = groupagg.generate(GenParams(rows=3000, keys=40, seed=11, order=order, disorder=0.05))
        assert run_initial(data) == groupagg.reference_output(data), order


def test_empty_input_outputs_header_only():
    data = groupagg.generate(GenParams(rows=0, keys=1, seed=1))
    assert data == b"key,value\n"
    assert groupagg.reference_output(data) == b"key,count,sum\n"
    assert run_initial(data) == b"key,count,sum\n"


def test_profile_reflects_order():
    sorted_p = groupagg.profile(groupagg.generate(GenParams(rows=5000, keys=100, seed=5, order="sorted")))
    random_p = groupagg.profile(groupagg.generate(GenParams(rows=5000, keys=100, seed=5, order="random")))
    clustered = groupagg.profile(groupagg.generate(GenParams(rows=5000, keys=100, seed=5, order="clustered")))
    assert sorted_p["sortedness"] == 1.0
    assert random_p["sortedness"] < 0.6
    assert clustered["key_runs_per_key"] == 1.0
    assert sorted_p["distinct_keys"] == 100


def test_check_output_categories():
    data = groupagg.generate(GenParams(rows=500, keys=20, seed=8))
    expected = groupagg.reference_output(data)
    assert groupagg.check_output(expected, expected)["correct"]
    assert groupagg.check_output(expected.replace(b"\n", b"\r\n"), expected)["correct"]
    assert groupagg.check_output(b"oops\n", expected)["failure"]["category"] == "format_error"
    lines = expected.decode().splitlines()
    missing = ("\n".join(lines[:-1]) + "\n").encode()
    r = groupagg.check_output(missing, expected)
    assert r["format_ok"] and not r["correct"] and r["failure"]["kinds"] == ["missing_keys"]
    swapped = ("\n".join([lines[0], lines[2], lines[1], *lines[3:]]) + "\n").encode()
    assert groupagg.check_output(swapped, expected)["failure"]["kinds"] == ["wrong_order"]
