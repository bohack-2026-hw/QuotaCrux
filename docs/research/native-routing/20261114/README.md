# 2026-11-14 路由批次准备

执行基线为 `912b20a4cfeb51af9c36d0679b23f0990abe862f`。当前已准备中央 24 项逻辑计划、
desktop ahc026 的 12 项计划、模型与价格快照；独立执行环境核验已通过，启动清单见 [ale-freeze.json](ale-freeze.json)。
Mac 的主机及旧任务材料已由 #4 回传；GC v2 的新任务、镜像及校准待补齐，旧 v1 绑定只作历史记录。

公开配置来自实际执行环境：small 为 AIPing Qwen3.8-27B，禁用 thinking、输出上限 8192；
large 为官方 Responses API 的 gpt-6.1-sol，xhigh、输出上限 32000；Decisions 为官方端点的
gpt-6-luna，显式缓存且不设置写入断点。所有组均为 feedback/adaptive、eval/v0，初始 small，
不固定生成角色，关闭初始经验分流。每轮共用 900 秒、20 次全部 HTTP 请求、10 个候选的上限。

价格见 [prices.json](prices.json)。Qwen 沿用当天采集的 AIPing 快照；
[Sol 官方模型页](https://developers.openai.com/api/docs/models/gpt-6.1-sol)确认标准短上下文每百万
输入/输出 Token 为 USD 2/10；[Decisions 官方说明](https://developers.openai.com/api/docs/guides/decisions#pricing-and-availability)
确认输入为 USD 0.10/百万、输出不计费。这里按未缓存标准价估算，缓存读写、折扣和额度不参与计算。

desktop 复用已冻结的 ahc026 任务包、候选/裁判镜像及 CPU 4 测量参数；另建 checkout 和 VAR_DIR。
同题 12 轮串行，安排在原 15 轮 ALE 批次完成后。原始校准证据见
[ALE 环境记录](../../native-formal-20261114/ale/README.md)。

[estimate.json](estimate.json)记录全部来源和假设：同题已有 48 次 Qwen 调用、同配置 Sol 的
6 次历史调用（含 1 次未知用量超时），以及 25 次 Decisions 完整历史回放。没有新增付费 pilot。
以下是填满请求预算的两个规划场景，每 12 轮假设 small/large/Decisions 分别调用 18/153/69 次。

| desktop 12 轮场景 | CNY | USD | 串行墙钟 |
|---|---:|---:|---:|
| 每次 Sol 输出 2k Token、等待 40 秒 | 1.242 | 7.7535 | 约 126 分钟 |
| 每次 Sol 输出 6k Token、等待 75 秒 | 1.242 | 13.8735 | 约 164 分钟 |

场景采用每次 15k 输入 Token、Qwen 2k 输出和 25 秒等待、Decisions 1.5 秒等待；
每轮另计开发/初始化 60 秒及 final/设置 12 秒，研究循环按 900 秒封顶。
费用按完整请求分配计算，提前 finish 或墙钟限制会减少实际请求；这些数值不是费用硬上限。
旧 Sol/Decisions 记录来自其他工作负载，所以场景不构成原生路由的实测预测。
Mac 的 GC v2 校准尚未回传，其费用和墙钟不直接套用本表。

[preparation.json](preparation.json)保留中央24项计划；desktop 的12项已独立冻结，Mac仍等待GC v2校准。
[启动核验](ale-preflight/ale-preflight.json)记录干净源码、空账本、模型/任务/镜像/提示及价格一致性；
[环境证据](ale-preflight/deployment.json)保存实际Python、CPU、依赖与公开配置。执行助手置于checkout外，按SHA256冻结；其`--execute`只允许新空账本启动一次。
原反馈消融中 ALE 15 轮已在 `990f598` 完成，Mac 15 轮改用上述已合入的 GC v2 源码；原反馈消融与新路由批次分别汇总。

启动命令（desktop）：

```sh
cd /home/hycx233/routeevo-routing-formal-20261114/repo/backend
.venv/bin/python /home/hycx233/routeevo-routing-formal-20261114/run_ale_routing.py \
  --freeze /home/hycx233/routeevo-routing-formal-20261114/ale-freeze.json --execute
```

后台启动信息与实际comparison ID在后续执行记录中登记；启动前不会将12项准备清单记为已运行。
