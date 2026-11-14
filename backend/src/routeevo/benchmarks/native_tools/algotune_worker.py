"""Execute only pinned upstream task methods, in a checker-only container."""
import ast
import json
from pathlib import Path
import sys

import numpy as np
from wire import decode, encode, finite

request = json.load(sys.stdin)
source = Path("/opt/algotune/task.py").read_text()
tree = ast.parse(source)
body = []
for node in tree.body:
    if isinstance(node, ast.ImportFrom) and node.module == "AlgoTuneTasks.base":
        continue
    if isinstance(node, ast.ClassDef):
        node.bases = [ast.Name(id="object", ctx=ast.Load())]
        node.decorator_list = []
        class_name = node.name
    body.append(node)
# These two task classes only use Task for registration and its no-argument initializer.
# Dataset orchestration is handled by RouteEvo; all generator/solver/checker methods stay unchanged.
tree.body = body
namespace = {"__name__": "upstream_task"}
exec(compile(ast.fix_missing_locations(tree), "upstream_task.py", "exec"), namespace)
task = namespace[class_name]()
if request["operation"] == "generate":
    problems = [task.generate_problem(request["size"], random_seed=seed) for seed in request["seeds"]]
    for problem in problems:
        reference = task.solve(problem)
        if not finite(reference) or not task.is_solution(problem, reference):
            raise RuntimeError("upstream reference failed its own checker")
    print(json.dumps({"problems": [encode(p) for p in problems]}, allow_nan=False))
elif request["operation"] == "judge":
    results = []
    for case in request["cases"]:
        problem = decode(case["problem"])
        expected = task.solve(problem)
        passed = []
        for raw in case["solutions"]:
            try:
                solution = decode(raw)
                shape_ok = not isinstance(expected, np.ndarray) or (isinstance(solution, np.ndarray) and solution.shape == expected.shape)
                passed.append(bool(shape_ok and finite(solution) and task.is_solution(problem, solution)))
            except (ValueError, TypeError, KeyError, IndexError, OverflowError):
                passed.append(False)
        results.append({"correct": all(passed), "measurements_passed": sum(passed), "measurements": len(passed)})
    print(json.dumps({"cases": results}))
else:
    raise ValueError("unknown operation")
