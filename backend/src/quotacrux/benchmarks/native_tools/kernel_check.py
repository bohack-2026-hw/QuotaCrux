"""Check saved GPU outputs after both candidate containers have exited."""
import json
import sys
import numpy as np

request = json.load(sys.stdin)
passed = []
for i in range(request["repeats"] + 1):
    reference = np.load(f"/reference/result_{i}.npy", allow_pickle=False)
    candidate = np.load(f"/candidate/result_{i}.npy", allow_pickle=False)
    passed.append(bool(candidate.shape == reference.shape and candidate.dtype == reference.dtype and
                       np.isfinite(candidate).all() and np.allclose(candidate, reference, atol=1e-4, rtol=1e-4)))
print(json.dumps({"correct": all(passed), "measurements_passed": sum(passed), "measurements": len(passed)}))
