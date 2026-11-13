# RouteEvo

一个根据任务执行结果积累经验、改进后续决策的任务执行系统。

当前先实现日新赛道与 Research Agent 赛道共用的核心：给定任务和预算，自主执行、验证结果、保存经验，并比较不同经验版本的实际效果。具体参赛方向和研究场景在共用核心验证后确定。

- [共用核心 PRD](docs/shared-core-prd.md)
- [首版开工决策与 agent 问题答复](docs/implementation-decisions.md)
- [两个方向的差异与选择依据](docs/track-differences.md)
- [日新方向增量 PRD](docs/rixin-track-prd.md)
- [Research Agent 方向增量 PRD](docs/research-agent-track-prd.md)

先按共用核心推进，选定方向后实施对应增量。两份方向 PRD 是备选方案，不要求同时开发。赛道选择须在 11 月 14 日 10:00 锁定前完成，不以共用核心全部完成为前提。

当前状态：产品需求草案，尚未开始业务实现。

首版已确定使用自部署 Qwen + GPT-6.1 Sol（xhigh）、Python 3.12 + SQLite + FastAPI，并在固定机器的 Docker 环境中验证程序优化。具体任务、A/B/C 数据划分、重复次数与开发分工见开工决策。
