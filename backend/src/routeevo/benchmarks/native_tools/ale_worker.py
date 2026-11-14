"""Run the pinned AtCoder input generator or scorer, without candidate execution."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

request = json.load(sys.stdin)
tools = Path("/opt/ale")
with tempfile.TemporaryDirectory() as directory:
    os.chdir(directory)
    if request["operation"] == "generate":
        Path("seeds.txt").write_text("\n".join(map(str, request["seeds"])) + "\n")
        p = subprocess.run([str(tools / "gen"), "seeds.txt"], capture_output=True, text=True, timeout=60, check=True)
        print(json.dumps({"inputs": [p.read_text() for p in sorted(Path("in").glob("*.txt"))]}))
    elif request["operation"] == "judge":
        results = []
        for case in request["cases"]:
            Path("input.txt").write_text(case["input"])
            Path("output.txt").write_text(case["output"])
            p = subprocess.run([str(tools / "vis"), "input.txt", "output.txt"], capture_output=True, text=True, timeout=10)
            matches = re.findall(r"Score\s*=\s*(\d+)", p.stdout + "\n" + p.stderr)
            if p.returncode or not matches:
                raise RuntimeError(f"AtCoder scorer failed ({p.returncode}): {p.stderr[-1000:]} {p.stdout[-1000:]}")
            score = int(matches[-1])
            results.append({"correct": score > 0, "score": score})
        print(json.dumps({"cases": results}))
    else:
        raise ValueError("unknown operation")
