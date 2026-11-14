"""Access-log statistics task family: per hour and endpoint, request count, server errors, latency sum and maximum.

Everything here runs on the host as part of the evaluator; none of it is mounted into candidate containers.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .csvcheck import check_keyed_csv

FAMILY = "logstats"
GENERATOR_VERSION = "logstats-gen-1"
CHECKER_VERSION = "logstats-check-1"
INITIAL_CODE_PATH = Path(__file__).with_name("logstats_initial.py")

OUTPUT_HEADER = "hour,method,path,count,errors,sum_ms,max_ms"
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
METHOD_WEIGHTS = (60, 20, 8, 6, 6)
SEGMENTS = ("api", "v1", "v2", "users", "orders", "items", "cart", "search", "auth", "login", "health", "static", "img",
            "assets", "admin", "report", "export", "billing", "invoice", "profile", "settings", "feed", "media", "upload")
OK_STATUSES = (200, 200, 200, 200, 200, 200, 201, 204, 301, 304, 400, 401, 403, 404, 404, 429)
ERROR_STATUSES = (500, 502, 503, 504)

CONTRACT = """\
Program contract (logstats v1)
- Read an access log from standard input: zero or more lines, each terminated by `\\n`, of the form
  `<timestamp> <method> <path> <status> <latency_ms>` with exactly one space between fields.
- `timestamp` is a valid UTC time written `YYYY-MM-DDTHH:MM:SSZ`. Lines are not guaranteed to be in time order.
- `method` is one of DELETE, GET, PATCH, POST, PUT. `path` starts with `/` and is 1-48 characters from [a-z0-9/_-].
- `status` is an integer from 100 to 599. `latency_ms` is a non-negative integer without leading zeros, at most 9999999.
- Group the lines by (hour, method, path), where hour is the timestamp truncated to the hour and written `YYYY-MM-DDTHH`.
- Write to standard output the header `hour,method,path,count,errors,sum_ms,max_ms`, then one line per group: the
  number of lines, the number of lines with status >= 500, the sum of latency_ms and the maximum latency_ms, each line
  terminated by `\\n`.
- Output lines are sorted by (hour, method, path) ascending in Python string order.
- With no input lines the output is the header line only.
- The program must be correct for every input that satisfies this contract, not only for the data it was tuned on.
"""


@dataclass(frozen=True)
class GenParams:
    rows: int
    endpoints: int  # distinct (method, path) pairs
    hours: int  # hours spanned by the timestamps
    seed: int
    order: str = "time"  # time | nearly_time | shuffled
    disorder: float = 0.0  # nearly_time: fraction of lines swapped out of place
    skew: float = 0.0  # Zipf exponent over endpoints; 0 = uniform
    error_rate: float = 0.02
    latency_mean: int = 120
    start: str = "2026-11-01T00"

    def to_dict(self) -> dict:
        return asdict(self)


def _endpoints(rng: random.Random, n: int) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    while len(seen) < n:
        depth = rng.randint(1, 4)
        parts = []
        for _ in range(depth):
            parts.append(str(rng.randint(1, 99999)) if rng.random() < 0.25 else rng.choice(SEGMENTS))
        path = ("/" + "/".join(parts))[:48]
        seen.add((rng.choices(METHODS, weights=METHOD_WEIGHTS)[0], path))
    out = sorted(seen)
    rng.shuffle(out)
    return out


def generate(p: GenParams) -> bytes:
    if p.order not in {"time", "nearly_time", "shuffled"}:
        raise ValueError(f"unknown order {p.order!r}")
    if p.rows == 0:
        return b""
    rng = random.Random(p.seed)
    pool = _endpoints(rng, max(p.endpoints, 1))
    if p.skew > 0:
        cum, total = [], 0.0
        for rank in range(len(pool)):
            total += 1.0 / (rank + 1) ** p.skew
            cum.append(total)
        picks = rng.choices(pool, cum_weights=cum, k=p.rows)
    else:
        picks = rng.choices(pool, k=p.rows)
    seconds = sorted(rng.randrange(p.hours * 3600) for _ in range(p.rows))
    t0 = datetime.strptime(p.start, "%Y-%m-%dT%H")
    hour_names = [(t0 + timedelta(hours=h)).strftime("%Y-%m-%dT%H") for h in range(p.hours)]
    lines = []
    for sec, (method, path) in zip(seconds, picks):
        h, rest = divmod(sec, 3600)
        ts = f"{hour_names[h]}:{rest // 60:02d}:{rest % 60:02d}Z"
        status = rng.choice(ERROR_STATUSES) if rng.random() < p.error_rate else rng.choice(OK_STATUSES)
        latency = min(int(rng.expovariate(1 / p.latency_mean)), 9_999_999)
        lines.append(f"{ts} {method} {path} {status} {latency}")
    if p.order == "shuffled":
        rng.shuffle(lines)
    elif p.order == "nearly_time":
        for _ in range(int(p.rows * p.disorder / 2)):
            i, j = rng.randrange(p.rows), rng.randrange(p.rows)
            lines[i], lines[j] = lines[j], lines[i]
    return ("\n".join(lines) + "\n").encode()


CONTRACT_CASES = {
    "empty": "",
    "single_line": "2026-01-01T00:00:00Z GET / 200 5\n",
    "hour_and_day_boundaries": ("2026-12-31T23:59:59Z GET /a 200 1\n2027-01-01T00:00:00Z GET /a 200 2\n"
                                "2026-12-31T23:00:00Z GET /a 500 3\n2027-01-01T00:59:59Z GET /a 200 4\n"),
    "out_of_time_order": ("2026-03-01T10:15:00Z GET /x 200 7\n2026-03-01T09:59:59Z GET /x 200 1\n"
                          "2026-03-01T10:00:01Z GET /x 503 9\n2026-03-01T09:00:00Z POST /x 201 4\n"
                          "2026-02-28T10:30:00Z GET /x 200 2\n"),
    "status_edges": ("2026-05-05T05:05:05Z GET /s 499 1\n2026-05-05T05:05:06Z GET /s 500 1\n"
                     "2026-05-05T05:05:07Z GET /s 599 1\n2026-05-05T05:05:08Z GET /s 100 1\n"),
    "method_and_path_order": "".join(f"2026-07-07T07:00:00Z {m} {p} 200 3\n" for m, p in (
        ("PUT", "/a"), ("DELETE", "/a"), ("GET", "/a-b"), ("GET", "/a/b"), ("GET", "/a"), ("GET", "/a_b"),
        ("GET", "/a0"), ("PATCH", "/a"), ("POST", "/a"), ("GET", "/a"))),
    "latency_extremes": ("2026-08-08T08:08:08Z GET /big 200 9999999\n2026-08-08T08:09:09Z GET /big 200 0\n"
                         "2026-08-08T08:10:10Z GET /big 504 9999999\n"),
}
CONTRACT_CASES_NOTE = ("empty input, a single line, hour and day boundaries, lines out of time order, status 499/500/599/100, "
                       "method and path ordering (/a, /a-b, /a/b, /a0, /a_b) and latencies 0 and 9999999")


def reference_output(data: bytes) -> bytes:
    """Trusted evaluator-side implementation, deliberately independent from the initial program."""
    acc: dict[tuple[str, str, str], list[int]] = {}
    for line in data.decode("ascii").split("\n"):
        if not line:
            continue
        ts, method, path, status, latency = line.split(" ")
        key = (ts[:13], method, path)
        st, lat = int(status), int(latency)
        a = acc.get(key)
        if a is None:
            acc[key] = [1, int(st >= 500), lat, lat]
        else:
            a[0] += 1
            a[1] += st >= 500
            a[2] += lat
            if lat > a[3]:
                a[3] = lat
    out = [OUTPUT_HEADER]
    out.extend(f"{h},{m},{p},{c},{e},{s},{x}" for (h, m, p), (c, e, s, x) in sorted(acc.items()))
    return ("\n".join(out) + "\n").encode()


def profile(data: bytes) -> dict:
    """Workload features the agent may see and that experience retrieval filters on."""
    lines = [line for line in data.decode("ascii").split("\n") if line]
    n = len(lines)
    if n == 0:
        return {"rows": 0, "bytes": len(data), "groups": 0}
    groups: dict[tuple[str, str, str], int] = {}
    endpoints: dict[tuple[str, str], int] = {}
    hours: set[str] = set()
    stamps, errors = [], 0
    for line in lines:
        ts, method, path, status, _ = line.split(" ")
        stamps.append(ts)
        hours.add(ts[:13])
        groups[(ts[:13], method, path)] = groups.get((ts[:13], method, path), 0) + 1
        endpoints[(method, path)] = endpoints.get((method, path), 0) + 1
        errors += int(status) >= 500
    top = sorted(endpoints.values(), reverse=True)
    pairs = max(n - 1, 1)
    return {
        "rows": n,
        "bytes": len(data),
        "groups": len(groups),
        "endpoints": len(endpoints),
        "hours": len(hours),
        "avg_rows_per_group": round(n / len(groups), 3),
        "time_sortedness": round(sum(1 for a, b in zip(stamps, stamps[1:]) if a <= b) / pairs, 6),
        "error_rate": round(errors / n, 6),
        "top10_endpoint_share": round(sum(top[:10]) / n, 6),
        "avg_line_bytes": round(len(data) / n, 2),
    }


def check_output(stdout: bytes, expected: bytes, max_examples: int = 3) -> dict:
    return check_keyed_csv(stdout, expected, header=OUTPUT_HEADER, key_fields=3, int_fields=(3, 4, 5, 6),
                           max_examples=max_examples)


# ---------- family hooks ----------

BUCKET_FEATURES = ["rows", "groups", "rows_per_group", "order", "errors"]
CONDITION_PROFILE_KEYS = ("rows", "groups", "endpoints", "hours", "avg_rows_per_group", "time_sortedness", "error_rate",
                          "top10_endpoint_share")
ORDER_ZH = {"time": "按时间", "nearly_time": "近似按时间", "shuffled": "乱序"}


def buckets(profile: dict) -> dict:
    rows = profile.get("rows", 0)
    if rows == 0:
        return {f: "none" for f in BUCKET_FEATURES} | {"rows": "empty"}
    groups, rpg, srt = profile.get("groups", 0), profile.get("avg_rows_per_group", 0), profile.get("time_sortedness", 0)
    return {
        "rows": "<100k" if rows < 100_000 else ("<300k" if rows < 300_000 else ">=300k"),
        "groups": "<1k" if groups < 1_000 else ("<10k" if groups < 10_000 else ">=10k"),
        "rows_per_group": "<=5" if rpg <= 5 else ("<=50" if rpg <= 50 else ">50"),
        "order": "time_sorted" if srt >= 0.999 else ("nearly_sorted" if srt >= 0.9 else "unsorted"),
        "errors": "high" if profile.get("error_rate", 0) >= 0.05 else "low",
    }


def examples(seed: int, params: dict) -> list[dict]:
    cases = [
        GenParams(rows=0, endpoints=1, hours=1, seed=seed),
        GenParams(rows=10, endpoints=3, hours=2, seed=seed + 1, order=params.get("order", "time"), error_rate=0.3,
                  latency_mean=40),
        GenParams(rows=8, endpoints=4, hours=3, seed=seed + 2, order="shuffled", error_rate=0.2, latency_mean=20),
    ]
    out = []
    for p in cases:
        data = generate(p)
        out.append({"input": data.decode(), "output": reference_output(data).decode()})
    return out


def describe(params: dict) -> str:
    return (f"访问日志统计 · {ORDER_ZH.get(params['order'], params['order'])} · {params['rows']:,} 行 · "
            f"{params['endpoints']:,} 个接口 · {params['hours']} 小时 · 错误率 {params['error_rate']}")
