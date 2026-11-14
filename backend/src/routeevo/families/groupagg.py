"""Group-by aggregation task family: contract, data generator, reference output, profile, output check.

Everything here runs on the host as part of the evaluator; none of it is mounted into candidate containers.
"""

from __future__ import annotations

import random
import string
from dataclasses import asdict, dataclass
from pathlib import Path

FAMILY = "groupagg"
GENERATOR_VERSION = "groupagg-gen-1"
CHECKER_VERSION = "groupagg-check-2"
INITIAL_CODE_PATH = Path(__file__).with_name("groupagg_initial.py")

KEY_ALPHABET = string.ascii_letters + string.digits + "_"
INPUT_HEADER = "key,value"
OUTPUT_HEADER = "key,count,sum"

CONTRACT = """\
Program contract (groupagg v1)
- Read UTF-8 CSV from standard input. The first line is always the header `key,value`.
  Every following line is `<key>,<value>` terminated by `\\n`. There may be zero data lines.
- `key` is 1-32 characters from [A-Za-z0-9_]. No quoting, no spaces, no empty fields.
- `value` is a signed base-10 integer without leading `+` or leading zeros (e.g. `-17`, `0`, `42`).
- Write to standard output the header `key,count,sum`, then one line per distinct key:
  `<key>,<number of rows with that key>,<integer sum of their values>`, each terminated by `\\n`.
- Output lines are sorted by key in ascending Python string order (byte order for these characters).
- With zero data lines the output is the header line only.
- The program must be correct for every input that satisfies this contract, not only for the data it was tuned on.
"""


@dataclass(frozen=True)
class GenParams:
    rows: int
    keys: int
    seed: int
    key_len_min: int = 4
    key_len_max: int = 12
    skew: float = 0.0  # Zipf exponent over the key pool; 0 = uniform
    order: str = "random"  # random | sorted | nearly_sorted | clustered
    disorder: float = 0.0  # nearly_sorted: fraction of rows swapped out of place
    value_min: int = -1_000_000
    value_max: int = 1_000_000

    def to_dict(self) -> dict:
        return asdict(self)


def _key_pool(rng: random.Random, n: int, lo: int, hi: int) -> list[str]:
    pool: set[str] = set()
    while len(pool) < n:
        length = rng.randint(lo, hi)
        pool.add("".join(rng.choices(KEY_ALPHABET, k=length)))
    # Sort first so the pool (and the Zipf ranking) does not depend on set iteration order.
    keys = sorted(pool)
    rng.shuffle(keys)
    return keys


def generate(p: GenParams) -> bytes:
    if p.order not in {"random", "sorted", "nearly_sorted", "clustered"}:
        raise ValueError(f"unknown order {p.order!r}")
    if not (1 <= p.key_len_min <= p.key_len_max <= 32):
        raise ValueError("key length must be within 1..32")
    rng = random.Random(p.seed)
    pool = _key_pool(rng, max(p.keys, 1), p.key_len_min, p.key_len_max) if p.rows else []
    if p.rows == 0:
        return (INPUT_HEADER + "\n").encode()

    if p.skew > 0:
        cum, total = [], 0.0
        for rank in range(len(pool)):
            total += 1.0 / (rank + 1) ** p.skew
            cum.append(total)
        keys = rng.choices(pool, cum_weights=cum, k=p.rows)
    else:
        keys = rng.choices(pool, k=p.rows)
    span = p.value_max - p.value_min + 1
    values = [p.value_min + rng.randrange(span) for _ in range(p.rows)]
    rows = list(zip(keys, values))

    if p.order == "sorted":
        rows.sort(key=lambda r: r[0])
    elif p.order == "nearly_sorted":
        rows.sort(key=lambda r: r[0])
        for _ in range(int(p.rows * p.disorder / 2)):
            i, j = rng.randrange(p.rows), rng.randrange(p.rows)
            rows[i], rows[j] = rows[j], rows[i]
    elif p.order == "clustered":
        groups: dict[str, list[tuple[str, int]]] = {}
        for r in rows:
            groups.setdefault(r[0], []).append(r)
        group_keys = sorted(groups)
        rng.shuffle(group_keys)
        rows = [r for k in group_keys for r in groups[k]]

    out = [INPUT_HEADER]
    out.extend(f"{k},{v}" for k, v in rows)
    return ("\n".join(out) + "\n").encode()


# Small public inputs every candidate must pass before it is timed. They catch programs that are correct on the
# task's data distribution but violate the contract (e.g. assuming sorted input without checking).
CONTRACT_CASES = {
    "empty": "key,value\n",
    "single_row": "key,value\nz,5\n",
    "interleaved_repeats": "key,value\nb,1\na,2\nb,3\nc,-4\na,5\n",
    "ascii_order": "key,value\nb,1\nB,2\n_,3\n9,4\nZ,5\nb0,6\na,7\nb,8\n",
    "big_and_negative": "key,value\nk,99999999999999999999\nk,-1\nm,0\nn,-123456789012345678901\n",
    "nearly_sorted_trap": "key,value\na,1\nb,1\nc,1\na,1\nd,1\nd,2\n",
    "long_keys": "key,value\n" + "x" * 32 + ",1\n" + "x" * 31 + ",2\n" + "x" * 32 + ",3\n",
}
CONTRACT_CASES_NOTE = ("empty input, a single row, interleaved repeated keys, ASCII ordering of digits/upper/underscore/lower "
                       "case, very large and negative integers, an almost-sorted input and 32-character keys")


def reference_output(data: bytes) -> bytes:
    """Trusted evaluator-side implementation, deliberately independent from the initial program."""
    lines = data.decode("ascii").split("\n")
    if lines[0] != INPUT_HEADER:
        raise ValueError("input header mismatch")
    acc: dict[str, list[int]] = {}
    for line in lines[1:]:
        if not line:
            continue
        key, value = line.split(",")
        slot = acc.get(key)
        if slot is None:
            acc[key] = [1, int(value)]
        else:
            slot[0] += 1
            slot[1] += int(value)
    out = [OUTPUT_HEADER]
    out.extend(f"{k},{c},{s}" for k, (c, s) in sorted(acc.items()))
    return ("\n".join(out) + "\n").encode()


def profile(data: bytes) -> dict:
    """Workload features the agent may see and that experience retrieval filters on."""
    lines = data.decode("ascii").split("\n")[1:]
    keys = [line.split(",", 1)[0] for line in lines if line]
    n = len(keys)
    if n == 0:
        return {"rows": 0, "bytes": len(data), "distinct_keys": 0}
    counts: dict[str, int] = {}
    for k in keys:
        counts[k] = counts.get(k, 0) + 1
    distinct = len(counts)
    top = sorted(counts.values(), reverse=True)
    pairs = max(n - 1, 1)
    non_decreasing = sum(1 for a, b in zip(keys, keys[1:]) if a <= b)
    adjacent_equal = sum(1 for a, b in zip(keys, keys[1:]) if a == b)
    # A key "run" is a maximal block of equal adjacent keys; clustered input has runs == distinct keys.
    runs = n - adjacent_equal
    return {
        "rows": n,
        "bytes": len(data),
        "distinct_keys": distinct,
        "avg_rows_per_key": round(n / distinct, 3),
        "duplicate_rate": round(1 - distinct / n, 6),
        "top_key_share": round(top[0] / n, 6),
        "top10_key_share": round(sum(top[:10]) / n, 6),
        "sortedness": round(non_decreasing / pairs, 6),
        "adjacent_equal_rate": round(adjacent_equal / pairs, 6),
        "key_runs_per_key": round(runs / distinct, 3),
        "avg_key_len": round(sum(map(len, keys)) / n, 3),
    }


def _parse_output(text: str) -> tuple[list[str] | None, dict | None]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    if not lines or lines[0] != OUTPUT_HEADER:
        got = lines[0][:80] if lines else ""
        return None, {"category": "format_error", "message": f"first line must be {OUTPUT_HEADER!r}, got {got!r}"}
    for i, line in enumerate(lines[1:], start=2):
        parts = line.split(",")
        if len(parts) != 3:
            return None, {"category": "format_error", "message": f"line {i} must have 3 fields: {line[:80]!r}"}
        try:
            int(parts[1]), int(parts[2])
        except ValueError:
            return None, {"category": "format_error", "message": f"line {i} count/sum not integers: {line[:80]!r}"}
    return lines[1:], None


def check_output(stdout: bytes, expected: bytes, max_examples: int = 3) -> dict:
    """Return {format_ok, correct, failure}; failure carries a few concrete mismatches."""
    if stdout == expected:
        return {"format_ok": True, "correct": True, "failure": None}
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {"format_ok": False, "correct": False, "failure": {"category": "format_error", "message": f"output is not UTF-8: {exc}"}}
    got, err = _parse_output(text)
    if err:
        return {"format_ok": False, "correct": False, "failure": err}
    want, _ = _parse_output(expected.decode("ascii"))
    assert want is not None
    if got == want:
        # Same rows, only line-ending differences (e.g. CRLF or missing final newline).
        return {"format_ok": True, "correct": True, "failure": None}

    got_map = {line.split(",", 1)[0]: line for line in got}
    want_map = {line.split(",", 1)[0]: line for line in want}
    missing = [k for k in want_map if k not in got_map]
    extra = [k for k in got_map if k not in want_map]
    wrong = [k for k in want_map if k in got_map and got_map[k] != want_map[k]]
    duplicated = len(got) - len(got_map)
    categories = []
    if missing:
        categories.append("missing_keys")
    if extra:
        categories.append("extra_keys")
    if wrong:
        categories.append("wrong_values")
    if duplicated:
        categories.append("duplicate_keys")
    if not categories:
        categories.append("wrong_order")
    examples = [{"key": k, "expected": want_map[k], "got": got_map[k]} for k in wrong[:max_examples]]
    examples += [{"key": k, "expected": want_map[k], "got": None} for k in missing[: max(0, max_examples - len(examples))]]
    examples += [{"key": k, "expected": None, "got": got_map[k]} for k in extra[: max(0, max_examples - len(examples))]]
    return {
        "format_ok": True,
        "correct": False,
        "failure": {
            "category": "wrong_output",
            "kinds": categories,
            "expected_groups": len(want),
            "output_lines": len(got),
            "missing_keys": len(missing),
            "extra_keys": len(extra),
            "wrong_value_keys": len(wrong),
            "duplicated_lines": duplicated,
            "examples": examples,
        },
    }


# ---------- family hooks used by task packages, experience retrieval and the UI ----------

BUCKET_FEATURES = ["rows", "distinct_keys", "rows_per_key", "order", "skew"]
CONDITION_PROFILE_KEYS = ("rows", "distinct_keys", "avg_rows_per_key", "duplicate_rate", "top10_key_share", "sortedness",
                          "key_runs_per_key")
ORDER_ZH = {"random": "随机", "sorted": "有序", "nearly_sorted": "近似有序", "clustered": "成簇"}


def buckets(profile: dict) -> dict:
    """Coarse workload conditions an experience record is filed under (retrieval-v1 for this family)."""
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


def examples(seed: int, params: dict) -> list[dict]:
    """Small visible input/output pairs, generated from seeds unrelated to dev/final data."""
    order = params.get("order", "random")
    cases = [
        GenParams(rows=0, keys=1, seed=seed),
        GenParams(rows=10, keys=4, seed=seed + 1, key_len_min=1, key_len_max=3, order=order, value_min=-20, value_max=20),
        GenParams(rows=8, keys=8, seed=seed + 2, key_len_min=1, key_len_max=4, value_min=-5, value_max=5),
    ]
    out = []
    for p in cases:
        data = generate(p)
        out.append({"input": data.decode(), "output": reference_output(data).decode()})
    return out


def describe(params: dict) -> str:
    return (f"分组聚合 · {ORDER_ZH.get(params['order'], params['order'])} · {params['rows']:,} 行 · {params['keys']:,} 个 key"
            f" · 偏斜 {params['skew']}")
