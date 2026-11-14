"""Interval-merge task family: union of closed integer intervals, sorted by start.

Everything here runs on the host as part of the evaluator; none of it is mounted into candidate containers.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path

from .csvcheck import check_keyed_csv

FAMILY = "intervals"
GENERATOR_VERSION = "intervals-gen-1"
CHECKER_VERSION = "intervals-check-1"
INITIAL_CODE_PATH = Path(__file__).with_name("intervals_initial.py")

INPUT_HEADER = "start,end"
OUTPUT_HEADER = "start,end"
LIMIT = 10**12

CONTRACT = """\
Program contract (intervals v1)
- Read UTF-8 CSV from standard input. The first line is always the header `start,end`. Every following line is
  `<start>,<end>` terminated by `\\n`: signed base-10 integers without leading `+` or leading zeros, with
  -1000000000000 <= start <= end <= 1000000000000. Each line is the closed interval [start, end].
  There may be zero data lines. Lines are in no guaranteed order and may repeat.
- Merge intervals that overlap or share an endpoint: [a, b] and [c, d] with a <= c belong to the same merged interval
  when c <= b ([1,3] and [3,5] merge into [1,5]; [1,3] and [4,5] stay apart). Merging is transitive.
- Write to standard output the header `start,end`, then one line `<start>,<end>` per merged interval, sorted by start
  ascending, each terminated by `\\n`.
- With zero data lines the output is the header line only.
- The program must be correct for every input that satisfies this contract, not only for the data it was tuned on.
"""


@dataclass(frozen=True)
class GenParams:
    rows: int
    seed: int
    value_min: int = 0
    value_max: int = 10_000_000  # starts are drawn from [value_min, value_max]
    length_mean: int = 20  # mean interval length (exponential)
    order: str = "random"  # random | sorted | nearly_sorted
    disorder: float = 0.0
    duplicate_rate: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def generate(p: GenParams) -> bytes:
    if p.order not in {"random", "sorted", "nearly_sorted"}:
        raise ValueError(f"unknown order {p.order!r}")
    if not (-LIMIT <= p.value_min <= p.value_max <= LIMIT):
        raise ValueError("value range outside the contract")
    rng = random.Random(p.seed)
    pairs = []
    for _ in range(p.rows):
        if pairs and rng.random() < p.duplicate_rate:
            pairs.append(pairs[rng.randrange(len(pairs))])
            continue
        start = rng.randint(p.value_min, p.value_max)
        end = min(start + int(rng.expovariate(1 / p.length_mean)) if p.length_mean > 0 else start, LIMIT)
        pairs.append((start, end))
    if p.order == "sorted":
        pairs.sort()
    elif p.order == "nearly_sorted":
        pairs.sort()
        for _ in range(int(p.rows * p.disorder / 2)):
            i, j = rng.randrange(p.rows), rng.randrange(p.rows)
            pairs[i], pairs[j] = pairs[j], pairs[i]
    out = [INPUT_HEADER]
    out.extend(f"{a},{b}" for a, b in pairs)
    return ("\n".join(out) + "\n").encode()


CONTRACT_CASES = {
    "empty": "start,end\n",
    "single": "start,end\n5,9\n",
    "touching_and_gap": "start,end\n4,5\n1,3\n3,4\n7,8\n10,10\n9,9\n",
    "nested_and_transitive": "start,end\n2,3\n1,10\n4,5\n12,20\n11,12\n21,30\n",
    "duplicates_unsorted": "start,end\n6,7\n1,2\n6,7\n1,2\n1,2\n-3,-1\n",
    "equal_starts": "start,end\n1,9\n1,2\n1,5\n0,0\n",
    "extremes": "start,end\n999999999999,1000000000000\n-1000000000000,-1000000000000\n-5,5\n-1000000000000,-999999999999\n0,999999999999\n",
}
CONTRACT_CASES_NOTE = ("empty input, a single interval, touching intervals and gaps of one, nested and transitive merges, "
                       "duplicated unsorted lines, equal starts and values at -10^12 and 10^12")


def reference_output(data: bytes) -> bytes:
    """Trusted evaluator-side implementation, deliberately independent from the initial program."""
    lines = data.decode("ascii").split("\n")
    if lines[0] != INPUT_HEADER:
        raise ValueError("input header mismatch")
    pairs = sorted((int(a), int(b)) for a, b in (line.split(",") for line in lines[1:] if line))
    merged: list[list[int]] = []
    for a, b in pairs:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out = [OUTPUT_HEADER]
    out.extend(f"{a},{b}" for a, b in merged)
    return ("\n".join(out) + "\n").encode()


def profile(data: bytes) -> dict:
    """Workload features the agent may see and that experience retrieval filters on."""
    lines = data.decode("ascii").split("\n")[1:]
    pairs = [tuple(map(int, line.split(","))) for line in lines if line]
    n = len(pairs)
    if n == 0:
        return {"rows": 0, "bytes": len(data), "merged_intervals": 0}
    starts = [a for a, _ in pairs]
    merged, cur_end = 0, None
    for a, b in sorted(pairs):
        if cur_end is not None and a <= cur_end:
            cur_end = max(cur_end, b)
        else:
            merged += 1
            cur_end = b
    lo, hi = min(starts), max(b for _, b in pairs)
    pairs_n = max(n - 1, 1)
    return {
        "rows": n,
        "bytes": len(data),
        "merged_intervals": merged,
        "avg_intervals_per_merged": round(n / merged, 3),
        "start_sortedness": round(sum(1 for x, y in zip(starts, starts[1:]) if x <= y) / pairs_n, 6),
        "duplicate_rate": round(1 - len(set(pairs)) / n, 6),
        "min_value": lo,
        "max_value": hi,
        "max_abs_value": max(abs(lo), abs(hi)),
        "avg_length": round(sum(b - a for a, b in pairs) / n, 3),
    }


def check_output(stdout: bytes, expected: bytes, max_examples: int = 3) -> dict:
    return check_keyed_csv(stdout, expected, header=OUTPUT_HEADER, key_fields=1, int_fields=(0, 1), max_examples=max_examples)


TITLE_ZH = "区间合并"
BASELINE_ZH = "c0：csv 读入整数元组 + sorted + 逐个合并（初始程序，正确）"

# ---------- family hooks ----------

BUCKET_FEATURES = ["rows", "order", "intervals_per_merged", "magnitude", "sign"]
CONDITION_PROFILE_KEYS = ("rows", "merged_intervals", "avg_intervals_per_merged", "start_sortedness", "duplicate_rate",
                          "max_abs_value", "avg_length")
ORDER_ZH = {"random": "随机", "sorted": "有序", "nearly_sorted": "近似有序"}


def buckets(profile: dict) -> dict:
    rows = profile.get("rows", 0)
    if rows == 0:
        return {f: "none" for f in BUCKET_FEATURES} | {"rows": "empty"}
    ipm, srt = profile.get("avg_intervals_per_merged", 0), profile.get("start_sortedness", 0)
    return {
        "rows": "<200k" if rows < 200_000 else ("<1M" if rows < 1_000_000 else ">=1M"),
        "order": "sorted" if srt >= 0.999 else ("nearly_sorted" if srt >= 0.9 else "unsorted"),
        "intervals_per_merged": "<=2" if ipm <= 2 else ("<=20" if ipm <= 20 else ">20"),
        "magnitude": "<2^31" if profile.get("max_abs_value", 0) < 2**31 else ">=2^31",
        "sign": "has_negative" if profile.get("min_value", 0) < 0 else "non_negative",
    }


def examples(seed: int, params: dict) -> list[dict]:
    cases = [
        GenParams(rows=0, seed=seed),
        GenParams(rows=8, seed=seed + 1, value_min=0, value_max=40, length_mean=4, order=params.get("order", "random")),
        GenParams(rows=8, seed=seed + 2, value_min=-30, value_max=30, length_mean=6, duplicate_rate=0.2),
    ]
    out = []
    for p in cases:
        data = generate(p)
        out.append({"input": data.decode(), "output": reference_output(data).decode()})
    return out


def describe(params: dict) -> str:
    return (f"区间合并 · {ORDER_ZH.get(params['order'], params['order'])} · {params['rows']:,} 行 · "
            f"取值 [{params['value_min']:,}, {params['value_max']:,}] · 平均长度 {params['length_mean']}")
