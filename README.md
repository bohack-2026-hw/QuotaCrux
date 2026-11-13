# RouteEvo

一个根据实验反馈推进研究、积累执行经验的 Research Agent 系统。

团队已于 2026-11-14 确认选择倍漾量化 Research Agent 赛道。系统在给定数据、工具和资源限制下，自主完成“规划—收集证据—提出假设—实验—验证—修正”，交付可复现的成果，并将执行经验用于后续研究。

- [Research Agent 主线 PRD](docs/research-agent-track-prd.md)
- [赛题补充说明与团队确认](docs/research-agent-clarifications.md)
- [首版开工决策与 agent 问题答复](docs/implementation-decisions.md)
- [执行、经验与评测核心 PRD](docs/shared-core-prd.md)

首版评估任务是 Python 分组聚合程序的性能优化：初始程序正确，正确性为硬约束，程序处理耗时为主指标，同时统计 Agent 的总耗时、Token 和费用。使用自部署 Qwen + GPT-6.1 Sol（xhigh）、Python 3.12 + SQLite + FastAPI，在固定机器的 Docker 环境中运行。

实现顺序：先完成可验证的研究闭环，再完成经验版本、A/B/C 对照和展示。企业方补充说明原文、开发 agent 的 14 个问题与答复，以及模型、预算、运行环境的确认均已入库。

按现有赛事说明，项目材料于 11 月 15 日 08:00 前提交，当日上午现场展示，时区为 Asia/Shanghai。当前 main 分支交付内容为需求与开工决策文档。

历史参考：[两个方向的差异](docs/track-differences.md)、[日新方向 PRD](docs/rixin-track-prd.md)。这两份文档保留选题过程，不属于当前开发范围。
