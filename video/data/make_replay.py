"""Generate one ahc026 case the way the statement does, run the research run's real c0 and c7 on it, and write the
operation sequences with a simulated energy ledger for the 3D replay."""
import json, random, subprocess, sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[2] / "docs/research/native-routing/20261114/short-results/run-20261114T085616-894b"
N, M, SEED = 200, 10, 20261114
rng = random.Random(SEED)
boxes = list(range(1, N + 1)); rng.shuffle(boxes)
stacks = [boxes[i * N // M:(i + 1) * N // M] for i in range(M)]
inp = f"{N} {M}\n" + "\n".join(" ".join(map(str, s)) for s in stacks) + "\n"

def simulate(ops):
    st = [list(s) for s in stacks]; where = {b: i for i, s in enumerate(st) for b in s}
    energy, nxt, steps = 0, 1, []
    for v, i in ops:
        src = where[v]
        if i == 0:
            assert v == nxt and st[src][-1] == v, ("illegal carry", v)
            st[src].pop(); nxt += 1; steps.append({"op": "out", "v": v, "from": src, "energy": energy})
        else:
            j = st[src].index(v); moved = st[src][j:]; st[src] = st[src][:j]; st[i - 1] += moved
            for b in moved: where[b] = i - 1
            energy += len(moved) + 1
            steps.append({"op": "move", "v": v, "from": src, "to": i - 1, "k": len(moved), "energy": energy})
    assert nxt == N + 1, "not all boxes carried out"
    return steps, energy

out = {"seed": SEED, "stacks": stacks}
for cid in ("c0", "c7"):
    r = subprocess.run([sys.executable, str(RUN / "candidates" / f"{cid}.py")], input=inp, capture_output=True, text=True, timeout=60)
    ops = [tuple(map(int, l.split())) for l in r.stdout.split("\n") if l.strip()]
    steps, energy = simulate(ops)
    out[cid] = {"steps": steps, "energy": energy, "score": max(1, 10000 - energy), "moves": sum(s["op"] == "move" for s in steps)}
    print(cid, "ops", len(ops), "moves", out[cid]["moves"], "energy", energy)
Path(__file__).with_name("replay.json").write_text(json.dumps(out))
