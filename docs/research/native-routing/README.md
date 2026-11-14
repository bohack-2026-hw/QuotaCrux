# Native 路由研究

本研究对应 issue #6，比较 baseline、仅动作 Decisions、仅模型 Decisions、两者均启用四组。它与原 30 项固定 Qwen F/I/N 消融分别登记、执行和汇总。

## 已保存的批次

| 批次 | 实际范围与状态 | 入口 |
| --- | --- | --- |
| laptop / desktop 模型策略补充 | 固定小、固定大、规则自适应、动作 Decisions，每台各 1 次；7 completed、1 API failed，8 份交付候选均通过 final，另列 1 次中断 | [报告与局部接入结论](../onehour-20261114/README.md) · [时间—质量曲线](../onehour-20261114/quality-time.png) · [协议](../onehour-20261114/protocol.md) |
| desktop ahc026 短批 | 四组各 1 次，每轮 360 秒；4/4 completed、4/4 final 通过 | [批次说明](20261114/README.md) · [结果摘要](20261114/RESULTS.md) · [原始证据与曲线](20261114/short-results/README.md) |
| desktop 原长批 | 原 900 秒批次按范围调整停止；1 completed、1 user_stopped、10 not_run，单独保留 | [停止批次记录](20261114/long-batch-stopped/README.md) |
| Mac AlgoTune | 原路由 12 轮计划本轮取消启动；独立 dev-only 探索另行归档 | [Mac 交接](../native-formal-20261114/mac-handoff.md) |

短批每组运行一次，用于观察效果和成本；长批另行汇总。双机补充使用不同的四策略矩阵，增加固定大小模型参照，没有重跑双 Decisions，不能作为旧四路由矩阵的完整重复。

## 协议与实现入口

- [动作/模型路由设计与读取约定](../../design/action-model-routing.md)。
- [原 24 轮计划与完整交接说明（归档）](../../archive/routing-study-plan-v1.md)。
- [冻结模板](freeze-template.json)只作为原计划模板，实际执行使用批次内的冻结清单。
- [早期 Decisions 接口探索（归档）](../../archive/decisions-experiments/README.md)。

[返回实验批次索引](../README.md)。
