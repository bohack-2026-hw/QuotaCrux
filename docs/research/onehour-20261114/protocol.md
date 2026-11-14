# 一小时双机补充实验

本批为约一小时窗口内的双机并行补充对照，在 laptop 与 desktop 上对比 `ahc026` 的四种模型使用策略，每台主机各完整执行四组一次（共八轮）。

## 冻结条件

- 执行源码：`912b20a4cfeb51af9c36d0679b23f0990abe862f`（该版本 Python 包名仍为 `routeevo`），不包含产品分支界面的近期改动。
- 四组：`fixed_small`、`fixed_large`、`adaptive_rule`、`action_decisions`。全部使用 feedback、eval、空 v0，禁用初始经验路由，每轮新建 run，不写回经验。
- small：托管 Qwen3.8-27B，thinking=false，max_output_tokens=8192；large：gpt-6.1-sol，xhigh，max_output_tokens=32000；动作路由：Decisions gpt-6-luna。端点与公开参数继承当天短批冻结配置。
- 每轮上限：研究循环 360 秒、全部模型 HTTP 请求 20 次、候选 10 个；允许系统主动结束。启动与 final 单列。总计划最多 160 个模型请求；每台串行、双机最多两个在途请求。
- 数据：继承原 `ahc026` 的同一 5 dev / 15 final 包。每轮按 dev 选定候选，再执行独立 final。因该任务包此前已用于相关实验，本批主要作为既有任务上的同口径策略对照。
- 初始程序 dev 得分必须为 44120。两台分别校验通过后才启动付费请求。final 不用于环境校准或选择策略。
- laptop 顺序：动作 Decisions → 自适应 → 固定大 → 固定小；desktop 为反序，用于分散执行顺序带来的影响。
- 独立工作目录、SQLite 与 run.lock；两台均固定候选到逻辑 CPU4，1 CPU / 1 GiB。鉴于两台硬件不同，质量、时间与成本比较均按主机分层报告，作为双机配对观察而非多次重复显著性检验。

## 环境与可追溯性

`preflight.json` 保存逐文件源码哈希、任务文件哈希、模型配置、提示/动作 schema 哈希、裁判与候选镜像、主机 CPU、Python、价格快照及顺序。执行前再次核验这些字段，使用独占创建的 `execution-freeze.json` 防止重复启动。

laptop 从 desktop 导入原 judge 镜像后本地镜像 ID 存在差异，已作为独立 task ID 登记，而任务数据、合约与初始代码文件保持逐字节一致。各主机的实际镜像 ID 均独立记录。

`images.json` 核对结果：judge 的 10 层 RootFS、Config、OS/架构相同；candidate 的 Config 相同，7 层中的最后 3 层摘要不同。两台 candidate 内均为 Python 3.12.16，执行 harness 均为 1414 bytes，SHA256 `1a94f4538d6aa82d55d979b3763a86e0e960370f586b704f34598989f8f3d444`，与执行源码一致。上述镜像摘要差异已在记录中保留。

## 停止与汇总

每台最多四轮，不启用自动重试或额外抽样；若某轮研究或 final 未完成，则保留既有状态及候选并中止该主机后续轮次。每台执行超过 40 分钟后停止开启新轮，以保证一小时总体窗口内收尾。

汇总字段涵盖全部八个计划格、final 原始分数与相对 c0 提升、研究/总耗时、dev 合法候选数、各模型请求与 token，以及 CNY/USD 分列估算与未知项。价格沿用当天原批次冻结快照估算，与既往短批各自独立归档。

核心观察指标为两项：自适应策略相对固定大模型的质量与成本关系，以及动作 Decisions 相对规则自适应的增益；两台主机结果分别完整展示。

## 执行修订：laptop 会话中断

23:22 巡检发现 laptop 前台会话以退出码 143（SIGTERM）终止。此时首轮动作 Decisions 已完整交付，第二轮自适应仅记录 1 次分析、零个模型候选及 1 条未闭合的 `model_started` 记录。

23:25 通过 `continuation-freeze.json` 固定续跑方案：保留中断轮次及其原始账本，沿用相同的代码、任务、镜像、预算与模型配置由持久进程 `continue_laptop.py` 重新执行该未完成格子，随后推进尚未启动的固定大、小模型两格；并设定在 15:48 UTC 后停止开启新轮。

质量对照保持八格计划结构，上述中断尝试单列计入实际执行次数与已知调用开销（未闭合 `model_started` 记录的用量与费用保留未知）。

23:35 登记第二次执行修订：替代执行的自适应轮次因两次模型 API 超时以 `failed/model_api_error` 结束，其冻结候选完成 final 评测得 139020 分。通过 `finish-controls-freeze.json` 确认保留该轮原始结果，并按原定参数继续完成余下的固定大、小模型两格对照。
