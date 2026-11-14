# 2026-11-14 路由批次准备

执行基线为 `e0d23719b97928db0ab7b87de9469a6bf6c3a101`。当前已准备中央 24 项逻辑计划、
desktop ahc026 的 12 项计划、模型与价格快照；等待独立执行环境核验。尚未开始本批付费调用。
Mac 的 convolve_1d 任务和主机参数由 #4 补齐，不能将占位项当成已冻结或已执行记录。

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
Mac 的负载和测量参数尚未回传，其费用和墙钟不直接套用本表。

[preparation.json](preparation.json)仍标记为准备状态；正式启动前还需登记实际独立环境并冻结最终清单。
原 30 轮反馈消融继续使用 `990f598`，两批结果分别汇总。
