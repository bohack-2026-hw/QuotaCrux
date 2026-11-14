# Native 路由研究

本研究对应 issue #6，比较 baseline、仅动作 Decisions、仅模型 Decisions、两者均启用四组。它与原 30 项固定 Qwen F/I/N 消融分别登记、执行和汇总。

## 已落盘的批次

| 批次 | 实际范围与状态 | 入口 |
| --- | --- | --- |
| desktop ahc026 短批 | 四组各 1 次，每轮 360 秒；4/4 completed、4/4 final 通过 | [批次说明](20261114/README.md) · [结果摘要](20261114/RESULTS.md) · [原始证据与曲线](20261114/short-results/README.md) |
| desktop 原长批 | 原 900 秒批次按范围调整停止；1 completed、1 user_stopped、10 not_run，单独保留 | [停止批次记录](20261114/long-batch-stopped/README.md) |
| Mac AlgoTune | 卷积额外 12 轮的交接要求；本索引不将准备材料视为已执行结果 | [Mac 交接](../native-formal-20261114/mac-handoff.md) |

每组仅一次的短批是探索性结果；不与原长批混合计算，也不据此宣称统计显著。

## 协议与实现入口

- [动作/模型路由设计与读取约定](../../design/routing-adapters.md)。
- [原 24 轮计划与完整交接说明（归档）](../../archive/native-routing-plan.md)。
- [冻结模板](freeze-template.json)只作为原计划模板，实际执行使用批次内的冻结清单。
- [早期 Decisions 接口探索（归档）](../../archive/decision-model/README.md)。

[返回实验批次索引](../README.md)。
