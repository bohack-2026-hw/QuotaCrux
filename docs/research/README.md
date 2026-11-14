# 实验批次与研究成果

每批的模型、源码、任务、预算、硬件及 final 状态，以该批协议和原始记录为准。下表区分正式评测、开发预实验和独立路由实验。

| 批次 | 范围与状态 | 入口 |
| --- | --- | --- |
| 原生正式评测 v2（2026-11-14） | 中央计划 30 项。ALE 15 项已执行：14 completed、1 API 错误 failed，15 项冻结候选均通过 final；Mac 原 15 项按交接记录仍待物理绑定与启动 | [协议](native-formal-20261114/protocol.md) · [中央计划](native-formal-20261114/central-plan.json) · [ALE 结果](native-formal-20261114/ale/results/README.md) · [Mac 交接](native-formal-20261114/mac-handoff.md) |
| Native Decisions 路由（2026-11-14） | ahc026 四组各 1 次，360 秒探索实验：4/4 completed、4/4 final 通过；单独保留中止的 900 秒长批 | [结果摘要](native-routing/20261114/RESULTS.md) · [完整短批证据](native-routing/20261114/short-results/README.md) · [中止长批](native-routing/20261114/long-batch-stopped/README.md) · [系列入口](../archive/native-routing-plan.md) |
| 原生 CPU 第二轮（2026-11-14） | 校准后的 ALE / AlgoTune F/I 开发对照，dev-only，未评测 final | [报告](native-r2-20261114/README.md) · [协议](native-r2-20261114/protocol.md) · [审计](native-r2-20261114/protocol-audit.json) |
| 原生 CPU 第一轮（2026-11-14） | ALE / AlgoTune 首轮开发预实验，dev-only，未评测 final | [报告](native-20261114/README.md) · [清单](native-20261114/manifest.json) |
| EffiBench-X 四题（2026-11-14） | 60/60 final 用例通过，2/4 题达到加速目标，按币种记录费用 | [报告](effibench-x-20261114/README.md) · [计划](effibench-x-20261114/plan.json) · [结果](effibench-x-20261114/results.json) |
| 经验学习第一至三版 | groupagg、D 留出及 S 任务流，属于早期跨任务经验实验 | [历史汇总](../archive/results.md) · [代表性研究交付样例](examples.md) |

## 如何阅读一份实验

先读批次 `README.md` 或协议，再看 manifest / plan 和汇总，最后按 run ID 查看 `report.json`、候选、原始请求与复现脚本。区分 episode 状态、final 状态与公平性：运行失败可能已有 final；final 通过也不等于研究循环正常完成。

`run-*` 目录是保留的交付样例；日期批次目录保存其运行版本、证据、曲线和脚本。带 `SHA256SUMS` 的目录按原字节核验，整理导航时保留路径和内容。

`backend/scripts/export_research.py` 生成 [examples.md](examples.md) 并更新选中的样例目录；它不删除整个研究归档，也不重写本索引。单次导出可使用 `uv run routeevo export-run <run_id> --bundle <目录>`。

[返回文档导航](../README.md)。
