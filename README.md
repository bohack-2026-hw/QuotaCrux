# RouteEvo

一个根据任务执行结果积累经验、改进后续决策的任务执行系统。

给定任务和预算，它自主执行、验证结果、保存经验，并比较不同经验版本的实际效果。共用核心与日新方向增量（两轮现场演示、自动发布、行为对照、三行进化说明）均已实现，建议报名**日新**，见赛道选择建议。

- 提交材料：[项目说明](docs/project-description.md)（[PDF](docs/project-description.pdf)） · [实验结果](docs/results.md)（[PDF](docs/results.pdf)） · [演示文稿](docs/RouteEvo.pptx)（[PDF](docs/RouteEvo.pdf)）
- [演示脚本](docs/demo.md) · [赛道选择建议](docs/track-decision.md)
- [共用核心 PRD](docs/shared-core-prd.md)
- [首版开工决策与 agent 问题答复](docs/implementation-decisions.md)
- [两个方向的差异与选择依据](docs/track-differences.md)
- [日新方向增量 PRD](docs/rixin-track-prd.md)
- [Research Agent 方向增量 PRD](docs/research-agent-track-prd.md)

当前状态：共用核心 M1—M3 与日新增量 RX-01—08 已实现；A 批学习（v0 → v6）、B 开发对照、C 最终留出对照均已完成，两批留出任务上达标率不变（16/18），模型请求中位数 3 → 1，升级到 GPT 8 → 1 / 11 → 5 次，费用 $0.327 → $0.108 / $0.372 → $0.292；代价是 C 的最终加速比中位数 1.41× → 1.29×。完整数据与解读见实验结果和项目说明第 5 节。

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
