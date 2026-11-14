# 2026-11-14 主分支集成记录

本文记录 2026-11-14 多条并行开发线并入 `main` 的提交节点与回归验证结果。

| 开发线 | 纳入节点 | 内容 |
| --- | --- | --- |
| feat/shared-core | 2504bd8 | groupagg/logstats/intervals、初始经验路由、online 记忆、S 任务流、live UI 和第三版资料 |
| explore/openai-decisions | 49bea6b | 独立 ActionRouter / ModelRouter、Decisions provider、四组合开发功能检查与用途账本 |
| feat/research-calibration | f05fa96 | EffiBench-X、原生 ALE/AlgoTune/KernelBench、任务内反馈对照、两轮 CPU 实验、任务概况、分析状态和计时校准 |

`feat/effibench-x-adapter@19ce8db`、`feat/research-benchmarks@dbc88c4` 都是 research-calibration 的祖先，已随之完整纳入。集成期间远端 main 从 f8fbb3e 前进到 2504bd8，该节点也已包含在集成历史中。

## 关键合并处理

- 三个自建 family 接到统一 generated benchmark adapter；外部 benchmark 继续使用各自裁判和接口。groupagg 的旧任务构包内容保持一致。检索使用每个 adapter 的匹配阈值，保留语义兼容性及新任务族/新条件的区别。
- 保留 legacy eval/learn/online 与任务流；native 默认使用任务内 feedback，固定模型、空快照 v0。feedback/independent 研究模式只允许 eval/v0，独立组历史隔离、分析状态传递、截止时间和候选选择资格均保留。
- 固定模型绕过初始经验路由、模型选择请求及升级。显式使用 Decisions ModelRouter 时关闭初始经验规则，避免在第一次 Decisions 请求前直接进入 large。四组对照统一关闭初始规则，维持同一起点。
- native 与 feedback/independent 当前只接受默认 LLM ActionRouter + rule ModelRouter；不支持的组合在入口明确拒绝。legacy 保留两类路由的完整组合。详见[路由适配器](../design/action-model-routing.md)。
- 报告区分免费初始路由和付费 Decisions 选择，保留实际调用角色、用途和费用未知状态。CLI、报告与导出脚本保留研究、路由和计时复现参数。前端同时显示任务族、任务流、在线模式、速度或原始得分。
- 集成后的提示版本为 v6。已有实验按各自代码与提示版本保存；第二轮 native 实测均基于 `7408358/v5` 快照完成。

## 实际验证

后端全量运行覆盖 **131 项**：首次 129 通过，两个 EffiBench 脚本测试因新增初始路由直接选择 large 而未执行其 small 脚本；将这两个只验证适配器行为的测试明确设为 `router=False` 后，定向复测 **2/2 通过**。导出脚本随后补齐计时参数并新增断言，对应复测 **1/1 通过**。

上述检查涵盖真实 Docker 裁判/执行器、generated family、初始路由与 online/stream、Decisions 与研究协议隔离回归，以及 19 项组合约束检查；生成模型与 Decisions 请求均使用脚本或 mock 完成，集成回归阶段未触发付费模型调用。

前端 `tsc -b --force`、Vite build、oxlint 全部通过，依赖锁未改。Python 语法与 `git diff --check` 通过。原始第二轮报告、30 份候选代码的 SHA256 和最终集未评测状态均核对通过，过程图已渲染检查。

## 新的实测证据

[第二轮 native 报告](../research/native-r2-20261114/README.md)：固定 Qwen3.8-27B，4 个开发研究，47 次请求，约 738.6 秒，标价估算 ¥1.1951。AlgoTune feedback / independent 保留加速为 1.8343× / 1.2101×；ALE independent 得分 18,230（基线 17,753），feedback 保持基线。最终集未评测，KernelBench GPU 实机实验仍未执行。

协作动态同步于 [issue #1](https://github.com/bohack-2026-hw/QuotaCrux/issues/1)；后续开发以 `main` 为共同基线，原分支保留归档。
