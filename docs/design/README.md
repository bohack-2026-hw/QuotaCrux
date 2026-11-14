# 实现设计

本节说明各模块的代码实现与接入设计。通用运行和经验规则见[核心需求](../requirements/core-requirements.md)，命令与 API 见[后端说明](../../backend/README.md)。

| 文档 | 负责范围 | 对应实验 |
| --- | --- | --- |
| [EffiBench-X 接入](effibench-integration.md) | 数据导入、任务适配、正确性校验与计时 | [四题结果](../research/effibench-x-20261114/README.md) |
| [ALE、AlgoTune 与 KernelBench 接入](native-benchmarks.md) | 各任务的输入输出、裁判、依赖及 CPU/GPU 环境 | [实验批次与结果](../research/README.md) |
| [动作与模型选择](action-model-routing.md) | ActionRouter / ModelRouter、OpenAI Decisions / Jev 配置、调用预算与四组对照 | [路由实验](../research/native-routing/README.md) |

各实验的冻结配置、运行顺序与结果记录保存在对应批次目录；早期 Decisions 接口探索见[Decisions 探索归档](../archive/decisions-experiments/README.md)。

[返回文档导航](../README.md)。
