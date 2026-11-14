# 实验批次与结果

先从[评测规则](../evaluation/README.md)选择实验类型，再按下表查看批次的设置和结果。每份批次报告链接到计划、候选、请求及原始数据。完成范围见[2026-11-14 实验数据汇总](20261114-summary.md)，随后追加的模型策略对照见[双机补充报告](onehour-20261114/README.md)。

| 批次 | 范围与状态 | 入口 |
| --- | --- | --- |
| 双机模型策略补充（2026-11-14） | ahc026 每台四策略各 1 次，7 completed、1 API failed；8 份交付候选均通过 final，另保留 1 次基础设施中断。按主机比较质量、时间和请求，讨论局部 Decisions 的开销与取舍 | [报告](onehour-20261114/README.md) · [协议](onehour-20261114/protocol.md) · [时间—质量曲线](onehour-20261114/quality-time.png) · [数据](onehour-20261114/summary.json) |
| 原生正式评测 v2（2026-11-14） | 中央计划 30 项。ALE 15 项已执行：14 completed、1 API 错误 failed，15 项冻结候选均通过 final；Mac 原正式计划本轮取消启动，探索结果与正式批次分开记录 | [协议](native-formal-20261114/protocol.md) · [中央计划](native-formal-20261114/central-plan.json) · [ALE 结果](native-formal-20261114/ale/results/README.md) · [Mac 交接](native-formal-20261114/mac-handoff.md) · [Mac 校准与探索说明](native-formal-20261114/algotune/README.md) |
| Native Decisions 路由（2026-11-14） | ahc026 四组各 1 次，360 秒探索实验：4/4 completed、4/4 final 通过；单独保留中止的 900 秒长批 | [结果摘要](native-routing/20261114/RESULTS.md) · [完整短批证据](native-routing/20261114/short-results/README.md) · [中止长批](native-routing/20261114/long-batch-stopped/README.md) · [系列入口](native-routing/README.md) |
| Mac dev-only 探索（2026-11-14） | 固定 Sol 的四项 2-case dev 探索，远端 LM Studio 失败/截断与人工语义重建单列；final disabled、高负载，不并入取消的正式 15+12 计划 | [结果包与离线审计](mac-exploratory-20261114/README.md) |
| 原生 CPU 第二轮（2026-11-14） | 校准后的 ALE / AlgoTune F/I 开发对照，dev-only，未评测 final | [报告](native-r2-20261114/README.md) · [协议](native-r2-20261114/protocol.md) · [审计](native-r2-20261114/protocol-audit.json) |
| 原生 CPU 第一轮（2026-11-14） | ALE / AlgoTune 首轮开发预实验，dev-only，未评测 final | [报告](native-20261114/README.md) · [清单](native-20261114/manifest.json) |
| EffiBench-X 四题（2026-11-14） | 60/60 final 用例通过，2/4 题达到加速目标，按币种记录费用 | [报告](effibench-x-20261114/README.md) · [计划](effibench-x-20261114/plan.json) · [结果](effibench-x-20261114/results.json) |
| 经验学习第一至三版 | groupagg、D 留出及 S 任务流，属于早期跨任务经验实验 | [历史汇总](../archive/memory-learning-results.md) · [代表性研究交付样例](case-studies.md) |

## 如何阅读一份实验

先读批次 `README.md` 或协议，再看 manifest / plan 和汇总，最后按 run ID 查看 `report.json`、候选、原始请求与复现脚本。分别查看研究运行、最终测试和配置检查的结果。

`run-*` 目录保存研究样例，日期目录保存各批次材料。`SHA256SUMS` 用于检查文件是否被改动。

`backend/scripts/export_research.py` 生成 [examples.md](case-studies.md) 并更新选中的样例目录；本索引手工维护。单次导出可使用 `uv run quotacrux export-run <run_id> --bundle <目录>`。

[返回文档导航](../README.md)。
