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

The ALE-Bench adapter downloads unmodified task archives from
[SakanaAI/ALE-Bench](https://huggingface.co/datasets/SakanaAI/ALE-Bench/tree/0f426173b4e4e73b09b2b3631ae0490f66b75f99)
under the dataset's CC-BY-ND-4.0 license. Original statements, generators and score calculators remain in ignored
local storage; they are not redistributed in this repository. The initial feasible Python programs are RouteEvo's.

AlgoTune task sources are downloaded from
[oripress/AlgoTune](https://github.com/oripress/AlgoTune/tree/dff9914c10800c7a031c9e8c3d4d1c8cd1b38906)
under the [MIT license](docs/licenses/AlgoTune-MIT.txt), copyright 2025 Ori Press and the AlgoTune contributors.
The adapter removes framework registration and the Task base class, retaining the two supported tasks' original
generator, solve and checker methods. The candidate's initial module extracts the initializer and solve method;
the checker and reference stay in separate containers. Downloaded task packages and exported bundles retain the license.

KernelBench reference sources are downloaded from
[ScalingIntelligence/KernelBench](https://github.com/ScalingIntelligence/KernelBench/tree/129232ea3c4cfa05c2dd5473bdb935d6246dc84b)
under the [MIT license](docs/licenses/KernelBench-MIT.txt), copyright 2023 Anne Ouyang, Simon Guo and Azalia Mirhoseini,
Scaling Intelligence Lab, Stanford University. The initial module renames Model to ModelNew; its computation and input
generator are unchanged. Downloaded task packages and exported bundles retain the license.
