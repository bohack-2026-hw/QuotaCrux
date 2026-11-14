# 路由研究初版计划（24轮）

> 这是最初的24轮计划。后续范围和结果见[路由研究入口](../research/native-routing/README.md)。

对应 [issue #6](https://github.com/bohack-2026-hw/QuotaCrux/issues/6)。本目录交付实现说明与
[freeze-template.json](../research/native-routing/freeze-template.json)，当前不包含真实路由实验结果。
ALE ahc026 / AlgoTune convolve_1d 各四组 × 三次，新增 24 轮（与既有 30 轮固定 Qwen 反馈对照独立）；因本批允许模型升级，基线单独执行而不复用固定 Qwen 结果。

## 已接入的执行链

两层适配器沿用现有 `agent/routing.py`。ActionRouter 选择动作，ModelRouter 选择生成角色；
代码和分析仍由 small/large 生成。四组固定为 baseline=`llm/rule`、action_decisions=`decisions/rule`、
model_decisions=`llm/decisions`、both_decisions=`decisions/decisions`。

研究入口显式使用 `feedback + adaptive + eval/v0`；`fixed_model=None`，初始经验分流关闭。
初始角色为 small，ModelRouter 可以在第一次生成前升级；升到 large 后保持 large。
默认 fixed、independent、no_feedback 的入口保持原有行为。所有路由/生成 HTTP 尝试共用请求、
Token、实际耗时预算，包含错误和超时；固定 20 次总请求会让 Decisions 组有更少生成机会。

RoutingState 携带任务 objective、可用工具、可复验候选和研究模式。native 不提供 cProfile；
ALE 原始 score 使用目标方向，AlgoTune 使用 speedup。动作选择、生成内容、dev 判断均不读取 final。
达到目标后继续研究，保留主动 finish；冻结 dev 最优且预算内有效的候选，再执行 final。
已有 c0 归一化、final 失败与未执行状态由公共报告保留。

**规则组实际语义**：research feedback 中，每次计入 attempt 的候选复验都会使 `misses` 加一（包括已达 milestone 的候选），累计两次触发升级；另有 small 请求数达到三次的升级条件。该语义与“仅在连续两次质量失败后升级”不同。本次保留该规则算法并将 `comparison_config.config.upgrade_rule` 与代码 SHA 一同冻结；Decisions 根据可见状态独立决策。

## 运行与导出

计划由 desktop 节点执行 ALE 12 轮，Mac 节点执行 AlgoTune 12 轮。同一 task 的全部组和重复使用同一主机、任务包、裁判镜像、MeasureConfig 与校准并发条件。新建 routing 批次目录与 VAR_DIR，使用独立冻结 checkout，与运行中的其他批次环境隔离。

正式启动前将模板中的两个占位 task_id 替换为注册任务 ID，填入各自 manifest/文件 hash，
确认 5 dev / 15 final。按 task 分出两份 12 项 JSON plan，保留中央 seq、repeat 和 variant。
模板中的顺序轮换规则来自 `routing_ablation.plan([ale_id, algotune_id], 3)`。

下面是冻结完成后的命令形式；`task_id`、文件路径及测量参数应替换为该 worker 的冻结值。
`--pricing` 文件内容是三个角色的价格快照映射，而不是整个 freeze 文档。

```sh
uv run quotacrux ablate-routing TASK_ID --snapshot v0 --repeats 3 \
  --research-mode feedback --research-model-policy adaptive \
  --plan worker-plan.json --plan-id routing-native-v1 --pricing prices.json \
  --wall-clock 900 --max-requests 20 --max-candidates 10 --request-timeout 120 \
  --cpuset-cpus FROZEN_CPU --function-warmups FROZEN_WARMUPS
```

Python 入口同时支持完整 `RunLimits` / `MeasureConfig`、`final_evaluation`、`plan_id`、`label`。
默认仍保留 legacy CLI 兼容性，native 调用必须明确给 `research_mode="feedback"`。
省略 final 开关即启用 final，`--dev-only` 只用于功能检查。单次报告的 reproduce 命令保留 adaptive 与两个路由开关。

产物位于 `VAR_DIR/comparisons/research-routing-*.json`，单次证据仍位于 `VAR_DIR/runs/<run_id>/`。
共享比较锁保证每个 VAR_DIR 串行执行；中途失败停止该 worker 批次，后续 slot 保持 not_run，以保留完整的批内执行记录；如需补测则另建批次并注明原始 slot。

## 汇总导出与接口读取契约

- 顶层 `study="routing"`、`protocol="within-task-routing-v2"`、`variants`；每行 `mode="feedback"`
  与 `variant` 分开。读取 API 沿用 `/api/research-comparisons` 及其详情入口。
- `plan`、`plan_sha256`、`plan_id` 保留执行前顺序；`runs` 包含全部 planned slot。
  `execution` 保存实际 task/snapshot/routing；`comparison_config` 仅移除 treatment 的 action/model 开关，
  保留提示 hash、模型、预算、selector 配置和完整环境。同一 task 内逐项相等，不跨 task 强求环境相等。
- `fair` 为 false 表示配置或计划不一致；null 表示记录或四组矩阵未齐；true 表示协议一致。
  `fairness.all_planned_runs_completed`、`all_final_evaluations_completed` 单独展示完成程度。
  failed / interrupted / stopped / not_run、final failed / not_run / disabled 均保留。
- `iterations` 给出 small/large、routing/generation 请求和升级次数；`routing_steps` 保留选择、概率和 call id；
  `action_counts` 按决策动作分类，生成请求、无效动作和错误另保留原始账本。
- `usage_by_model` 的键为 `role:provider:model`，`usage_by_purpose` 区分 routing/generation。
  `price_snapshots={small,large,decisions}` 各自使用既有 `research_views.validate_pricing` 格式。
  `cost.by_model` 保留 purpose、usage、币种、快照、amount、known_amount、status；
  `cost.by_currency` 逐币种汇总。缺少用量时 amount=null，已知部分只写 known_amount；没有价格保持 unknown。
  费用是标准 Token 价格估算，缓存按冻结 input 单价，折扣和额度不在估算内；不进行汇率换算。
- `summary.tasks[].variants[]` 包含 final 正确数/值/中位数、c0、候选有效率、升级率、生成角色、动作频率、
  用途账本与模型/裁判/总耗时。升级率分母是有用量记录的已执行轮；未跑项另计数。
  `pairs` 提供同题同 repeat 的六种配对差值，缺失或失败保留 null；
  `interactions` 为 both − action − model + baseline。ALE 分数与 AlgoTune speedup 分别解释，不跨题平均。

`routing_ablation.summarize(data)` 仅依赖导出的 JSON，不访问原始数据库。
跨 worker 合并时保留完整中央 24 项 plan/hash，将两份 runs 按中央 seq 排序并保留原 worker 产物路径后重建汇总；每题公平性依据行内完整配置判定，各环境字段原样保留。

## 正式启动前需要填写的冻结信息

模板标记为 `template`，空值表示尚未冻结，需在正式调用前逐项确定：

1. 最终执行 SHA、uv.lock、提示/动作 schema/路由问题 hash；两端一致的 small/large/Decisions 公开配置。
   small 预期为 AIPing Qwen3.8-27B，Decisions 为现有 gpt-6-luna；large 的准确模型、推理强度、输出上限从执行环境读取。
2. 三种角色的价格来源、含时区的采集时间、币种和每百万输入/输出 Token 单价；不得复用不同模型价格。
3. 两题的任务包、种子封存与 hash、完整主机/镜像/CPU/测量/并发证据、API 在途限制、24 项中央计划。
4. 路由调用、生成调用、dev/final 裁判分项耗时和 Token 估计。只读配置不足以给出可信实际费用；
   先填同模型同端点路由 pilot 或经负责人确认的估算假设，标明来源，再发布正式启动估算。

当前可确定的预算上限为 **24 × 20 = 480 次总请求配额**、**24 × 900 = 21,600 秒累计研究循环预算**。
每台机器各 12 轮、累计循环预算三小时；两机并行时实际墙钟历时还需计入 final、初始化、排队与超时余量（上述数字为预算配额上限，不作为实际完成时刻）。费用按各角色预计调用数 × 预计输入/输出 Token × 冻结单价分别估算 CNY / USD；输入长度增长、角色切换及失败缺失用量保留为不确定项。
原 Qwen-only pilot 仅作流程参考，不直接用于本批 GPT/Decisions 的成本或耗时外推。

## 本次验证与后续交接

已通过 19 项路由检查、7 项执行器/portable 费用与公平性检查、6 项新增 native 集成检查，
以及 28 项 fixed / independent / no_feedback 交叉回归。native 集成使用 fake providers 和 fake judges，
覆盖 ALE score、AlgoTune speedup 四组的实际调用角色、升级、预算、工具菜单、dev 选择和 final 隔离。
这些检查覆盖调用流程和记录格式，实际效果待正式实验数据验证。

后续沿公共 Runner/CLI/API、两台执行机独立推进及前端按 `study + variant` 展示协同衔接，具体进度同步于 [issue #6](https://github.com/bohack-2026-hw/QuotaCrux/issues/6)。
