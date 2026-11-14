"""One GPU candidate process. No expected outputs or correctness checker are mounted."""
import contextlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch

request = json.load(sys.stdin)
if request.get("operation") == "environment":
    print(json.dumps({"gpu": torch.cuda.get_device_name(), "capability": torch.cuda.get_device_capability(),
                      "torch": torch.__version__, "cuda": torch.version.cuda}))
    raise SystemExit(0)
torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False
torch.manual_seed(request["seed"])
torch.cuda.manual_seed_all(request["seed"])
factory = {"__name__": "input_factory"}
exec(compile(Path("/work/reference.py").read_text(), "reference.py", "exec"), factory)
inputs = factory["get_inputs"]()
init_inputs = factory["get_init_inputs"]()
inputs = [x.cuda() if isinstance(x, torch.Tensor) else x for x in inputs]
if any(isinstance(x, torch.Tensor) and x.dtype != torch.float32 for x in inputs):
    raise ValueError("initial KernelBench subset requires float32 tensor inputs")
start = time.monotonic()
namespace = {"__name__": "candidate"}
with contextlib.redirect_stdout(sys.stderr):
    exec(compile(Path("/work/candidate.py").read_text(), "candidate.py", "exec"), namespace)
    model = namespace["ModelNew"](*init_inputs).cuda().eval()
torch.cuda.synchronize()
initialization_s = time.monotonic() - start
times = []
with torch.inference_mode():
    for i in range(request["repeats"] + 1):
        args = [x.clone() if isinstance(x, torch.Tensor) else x for x in inputs]
        torch.cuda.synchronize()
        begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        begin.record()
        with contextlib.redirect_stdout(sys.stderr):
            output = model(*args)
        end.record()
        torch.cuda.synchronize()
        if not isinstance(output, torch.Tensor) or output.dtype != torch.float32:
            raise ValueError("initial KernelBench subset requires one float32 output tensor")
        np.save(f"/out/result_{i}.npy", output.detach().cpu().numpy(), allow_pickle=False)
        if i:
            times.append(begin.elapsed_time(end) / 1000)
        del output, args
print(json.dumps({"times_s": times, "initialization_s": initialization_s,
                  "gpu": torch.cuda.get_device_name(), "capability": torch.cuda.get_device_capability(),
                  "torch": torch.__version__, "cuda": torch.version.cuda}))
