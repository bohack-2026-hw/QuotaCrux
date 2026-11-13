# RouteEvo

一个根据任务执行结果积累经验、改进后续决策的任务执行系统。

当前先实现日新赛道与 Research Agent 赛道共用的核心：给定任务和预算，自主执行、验证结果、保存经验，并比较不同经验版本的实际效果。具体参赛方向和研究场景在共用核心验证后确定。

- [共用核心 PRD](docs/shared-core-prd.md)
- [首版开工决策与 agent 问题答复](docs/implementation-decisions.md)
- [两个方向的差异与选择依据](docs/track-differences.md)
- [日新方向增量 PRD](docs/rixin-track-prd.md)
- [Research Agent 方向增量 PRD](docs/research-agent-track-prd.md)

先按共用核心推进，选定方向后实施对应增量。两份方向 PRD 是备选方案，不要求同时开发。赛道选择须在 11 月 14 日 10:00 锁定前完成，不以共用核心全部完成为前提。

当前状态：共用核心 M1—M3 已实现（后端 + 展示界面），A 批学习与 B/C 留出对照按 `backend/scripts/experiment.sh` 运行。

## 快速开始

```sh
cd backend && uv sync && cp .env.example .env   # 填 OPENAI_API_KEY；本地 Qwen 走 Ollama
uv run routeevo tasks build                     # 按 tasks/lock.json 重建冻结的任务包
(cd ../frontend && pnpm install && pnpm build)
uv run routeevo serve                           # 打开 http://127.0.0.1:8000
```

- [后端说明](backend/README.md)：执行循环、Docker 沙箱与外部评测器、经验快照、对照评测、命令与接口。
- `frontend/`：四个区域的展示界面——任务运行、经验查看、对照结果、版本管理。

首版已确定使用自部署 Qwen + GPT-6.1 Sol（xhigh）、Python 3.12 + SQLite + FastAPI，并在固定机器的 Docker 环境中验证程序优化。具体任务、A/B/C 数据划分、重复次数与开发分工见开工决策。
