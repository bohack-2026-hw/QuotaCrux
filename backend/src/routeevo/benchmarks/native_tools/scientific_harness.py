"""Time solve(problem) calls; the candidate image contains no reference or checker."""
import json
from pathlib import Path
import sys
from time import perf_counter

from wire import decode, encode

source = compile(Path(sys.argv[1]).read_text(), "candidate.py", "exec")
print("ROUTEEVO_READY", flush=True)
request = json.load(sys.stdin)
if not 1 <= request["repeats"] <= 100:
    raise ValueError("invalid repeat count")
warmups = request.get("warmups", 1)
if type(warmups) is not int or not 1 <= warmups <= 20:
    raise ValueError("invalid warm-up count")
results, times, initialization = [], [], []
for i in range(request["repeats"] + warmups):
    # Fresh candidate globals and input object for each measurement; imports are outside the timer.
    namespace = {"__name__": "candidate"}
    start = perf_counter()
    exec(source, namespace)
    solve = namespace["solve"]
    problem = decode(request["problem"])
    initialization.append(perf_counter() - start)
    start = perf_counter()
    answer = solve(problem)
    elapsed = perf_counter() - start
    results.append(encode(answer))
    if i >= warmups:
        times.append(elapsed)
print(json.dumps({"solutions": results, "times_s": times, "initialization_s": initialization,
                  "warmup_count": warmups}, allow_nan=False))
