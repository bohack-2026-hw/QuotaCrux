# OpenAI Decisions 在 RouteEvo 中的用途探索

> 历史探索：本文结论仅针对本轮回放样本。“暂不接入在线 runner”是当时的决定。后续适配实现见[路由设计](../../design/routing-adapters.md)，端到端实验见[路由研究](../../research/native-routing/README.md)。

2026-11-14；基线 `f8fbb3e`；分支 `explore/openai-decisions`。
协作入口：[issue #1](https://github.com/bohack-2026-hw/RouteEvo/issues/1)。

## 结论

当前证据不支持用 Decisions 替换 RouteEvo 的升级规则或候选验证。
接口已真实跑通，速度和费用适合轻量判断，但本次任务上的判断质量没有显示出足够收益。
保留独立实验入口，暂不接入在线 runner。

采用 OpenAI `gpt-6-luna`，调用 `POST https://api.openai.com/v1/decisions`。
这是输出概率、枚举选择或评分的接口；现有生成代码的大模型仍是 `gpt-6.1-sol`。
接口能力和当前支持模型见 [Decisions 指南](https://developers.openai.com/api/docs/guides/decisions)，
请求与回答结构见 [API reference](https://developers.openai.com/api/reference/resources/decisions/methods/create)。

## 实际实验

首轮共 25 次请求：11 个历史小模型请求前的路由点，以及 14 个候选提交后、验证前的判断。
每个候选同时询问正确性概率和正确且达到目标加速比的概率。首轮运行前固定阈值为 `0.5`。

随后做 14 次诊断对照：候选、问题和标签均保持相同，只提供任务契约、公开示例、开发负载、
初始程序和候选代码，去掉历史推理、已测候选及经验记录。此轮是在看到首轮结果后进行的输入消融，
不是独立测试集。AUC 为运行后补充的描述统计，没有据此调整阈值或重新选择样本。

| 指标 | 完整历史输入 | 精简候选输入 |
| --- | ---: | ---: |
| 真实 HTTP 请求 / 成功 | 25 / 25 | 14 / 14 |
| 输入 token | 145,167 | 21,806 |
| 请求延迟中位数 | 0.869 秒 | 0.643 秒 |
| 请求延迟合计 | 26.328 秒 | 9.080 秒 |
| 估算费用 | $0.0145167 | $0.0021806 |
| 实测达标候选中被保留 | 0 / 4 | 0 / 4 |
| 正确性判断与既有评测一致 | 11 / 14 | 10 / 14 |
| 被判为不正确的已通过候选 | 3 / 13 | 4 / 13 |
| 达标概率的 AUC | 0.5250 | 0.6625 |
| 达标概率的 Brier 分数（越低越好） | 0.24069 | 0.21175 |

共 39 次调用，166,973 个输入 token，估算 **$0.0166973**；响应均报告 0 个输出、缓存读取及缓存写入 token。
本实验显式关闭隐式缓存，使用官方标准短上下文输入价 $0.10 / 百万 token，输出不收费。
价格来源：[Decisions 定价](https://developers.openai.com/api/docs/guides/decisions#pricing-and-availability)、
[标准缓存费率](https://developers.openai.com/api/docs/pricing)。费用是响应 usage 对应的估算，不是账单核对。

### 模型升级

11 个路由点全部选择继续使用小模型。与当前 `upgrade-rule-v2` 有 1 处不同：
旧版 A-05 的第 4 次小模型请求前，当前规则会因已有 3 次小模型请求而升级，Decisions 仍选择小模型。

该回放只覆盖历史上仍处于 small 的预请求状态，不覆盖所有升级边界；旧记录来自不同版本。
没有实际执行另一条模型分支，因此不能把选择差异当作准确率、节省金额或最终成功率提升。
本次未观察到它在规则之前主动升级的价值，原规则仍应保留。

### 候选验证与排序

14 个候选中，既有开发评测有 13 个通过正确性、4 个达到当时生效的速度目标。
两轮的达标概率全部低于 0.5。直接据此跳过验证，会丢掉全部 4 个达标候选；
其分类结果与“全部拒绝”的常量策略相同。精简输入改善了概率排序，但跨样本概率最高的 4 项仍仅有 1 个实测达标项。
这只是描述排序，候选来自不同时间点，不能把它们当作当时同时可选的程序池来宣称调度收益。

几个具体反例：

| 候选 | 开发实测 | 完整输入达标概率 | 精简输入达标概率 |
| --- | --- | ---: | ---: |
| `run-20261113T161733-7c5a/c3` | 1.4547×，达标 | 0.16 | 0.27 |
| `run-20261113T212515-d6bd/c1` | 复用程序，1.2462×，达标 | 0.26 | 0.15 |
| `run-20261113T212515-d6bd/c6` | 1.7013×，超过提高后的 1.3085× 目标 | 0.06 | 0.13 |
| `run-20261114T023245-a91f/c2` | 在线 Qwen/GPT 联调产物，1.2818×，达标 | 0.12 | 0.14 |

最后一个候选的正确性概率也仅为 0.03 / 0.05，而它已通过开发数据与公开契约用例。
另一个输出表头错误的候选，两轮都给出正确性概率 0；这种错误现有评测器本就能直接检出。
正确性标签代表现有评测覆盖范围内的结果，并非对所有可能输入的形式化证明。

## 数据与时间边界

全部来自 A 学习批次的 4 次真实运行，仅涉及 A-01、A-05 两种工作负载：

| 来源运行 | 任务 | 路由点 | 候选数 |
| --- | --- | ---: | ---: |
| `run-20261113T161733-7c5a` | A-01 | 2 | 3 |
| `run-20261113T162613-8f0a` | A-05 | 4 | 3 |
| `run-20261113T212515-d6bd` | A-05 | 2 | 6，其中 3 个复用 |
| `run-20261114T023245-a91f` | A-01 | 3 | 2 |

前三组来自仓库 `docs/research`，第四组来自本机此前的在线 Qwen 联调导出。
这些样本是可获取的研究记录，非随机抽样；同一运行内的状态和候选相关。
此次没有 B 泛化实验、C/D 封存测试或新的端到端运行，不能据此断言模型在所有决策任务上无效。

输入由当时保存的模型请求恢复；新候选代码由当次提交提供。标签从随后第一次开发验证提取，
单独存放在 `reference`，HTTP 请求只发送 `evidence` 和 `questions`。
复用候选使用任务/负载、c0、旧经验和候选代码，不取首次模型请求中已经出现的复验结果。
隐藏 final 结果与数据没有进入模型输入；准备入口会拒绝 C/D 和 scripted 记录。

原始逐次请求、响应、request ID、usage 和耗时保存在本 worktree 的 `backend/var/decisions/`。
可携带的输入见 [cases.json](cases.json)，逐项回答及汇总见 [results.json](results.json)。
`results.json` 保存输入文件及每次请求的 SHA-256，凭证和 HTTP Authorization 头不在这些文件中。

## 实现与复现

新增文件均为独立实验用途，未修改 runner、memory、evaluator、任务协议、前端或现有运行数据库。
客户端沿用 `LLMResult` / `Usage` 错误通道；拒答、非法回答、限流、超时均显式失败，保留已发生请求的记录后停止。
未报告的用量与费用保持未知，不自动重试。

在本 worktree 的 `backend` 目录执行：

```sh
uv sync --frozen --python 3.12.11
.venv/bin/python -m pytest -q tests/test_decision_replay.py tests/test_actions_pricing.py

# 使用含 OPENAI_API_KEY 的本地环境文件，替换示例路径；会发生 25 次真实 API 调用。
.venv/bin/python scripts/decision_replay.py run \
  --cases ../docs/archive/decision-model/cases.json \
  --out var/decisions/replay-full \
  --env-file /path/to/private.env

# 产生精简视图；随后执行 14 次真实调用。
.venv/bin/python scripts/decision_replay.py compact \
  --cases ../docs/archive/decision-model/cases.json --out var/decisions/compact-cases.json
.venv/bin/python scripts/decision_replay.py run \
  --cases var/decisions/compact-cases.json \
  --out var/decisions/replay-compact \
  --env-file /path/to/private.env

# 只重算已有结果，不调用 API。
.venv/bin/python scripts/decision_replay.py summarize --results var/decisions/replay-full
```

运行目录必须是新路径，避免覆盖历史请求与费用记录。也可在 shell 中设置 `OPENAI_API_KEY` 后省略 `--env-file`。
已有研究 bundle 可通过 `prepare --bundle <目录> [--bundle <目录> ...] --out <文件>` 重新生成样本。

已验证：**21 项针对性测试通过**（其中 14 项覆盖新实验边界），Python 编译检查与 `git diff --check` 通过。
未重跑 Docker 性能回归；并行的 EffiBench-X agent 正在占用评测时段，本实验不执行候选程序。

## 后续适用点

当前先保留 `upgrade-rule-v2`、确定性经验检索和外部实测。若继续探索，优先在 EffiBench 多题型适配之后，
使用“给定任务契约与经验描述，哪条经验更相关”的有限候选排序问题，收集人工标签及真实复验收益。
这与预测未知运行时间相比更贴近文本判断能力，但本轮尚未验证，不能计入已有收益。
需在独立开发样本上校准阈值，并把额外延迟、费用、误弃有效候选及端到端成功率一起比较后，再决定是否接入。
