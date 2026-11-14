# Third-party notices

`backend/src/routeevo/benchmarks/effibench_imports.py` adapts the Python import prelude from
[EffiBench-X](https://github.com/EffiBench/EffiBench-X/blob/21b6668a49a342c843e679cc5ed16081064a5768/effibench/utils.py).
The `sortedcontainers` imports are omitted for RouteEvo's standard-library environment.
`effibench_judge.py` follows the output normalization and positional evaluator invocation in
that revision's `effibench/run_tests.py`. Upstream is licensed under
[Apache License 2.0](docs/licenses/EffiBench-X-Apache-2.0.txt).

The pinned [EffiBench-X dataset](https://huggingface.co/datasets/EffiBench/effibench-x/tree/49babbec95f0897d5f06276aaf274f9f1dcd036b)
is downloaded on demand to ignored local storage; problems, solutions and generated tests are not vendored.
The catalog records upstream problem identities, shard sizes and SHA256 checksums.
