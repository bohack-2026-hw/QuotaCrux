# RouteEvo

一个根据实验反馈推进研究、积累执行经验的 Research Agent 系统。

团队已于 2026-11-14 确认选择倍漾量化 Research Agent 赛道。系统在给定数据、工具和资源限制下，自主完成“规划—收集证据—提出假设—实验—验证—修正”，交付可复现的成果，并将执行经验用于后续研究。

- 提交材料：[项目说明](docs/project-description.md)（[PDF](docs/project-description.pdf)） · [实验结果](docs/results.md)（[PDF](docs/results.pdf)） · [演示文稿](docs/RouteEvo.pptx)（[PDF](docs/RouteEvo.pdf)）
- [RA 验收对照](docs/research-agent-acceptance.md)：RA-AC-01—08 逐条对应的实现与证据 · [研究成果样例](docs/research/) · [演示脚本](docs/demo.md)
- [Research Agent 主线 PRD](docs/research-agent-track-prd.md) · [赛题补充说明与团队确认](docs/research-agent-clarifications.md)
- [首版开工决策与 agent 问题答复](docs/implementation-decisions.md) · [执行、经验与评测核心 PRD](docs/shared-core-prd.md)

首版评估任务是 Python 分组聚合程序的性能优化：初始程序正确，正确性为硬约束，程序处理耗时为主指标，同时统计 Agent 的总耗时、Token 和费用。使用自部署 Qwen + GPT-6.1 Sol（xhigh）、Python 3.12 + SQLite + FastAPI，在固定机器的 Docker 环境中运行。

当前状态：研究闭环、独立评测、资源账本、经验版本与回退、对照评测和展示界面均已实现并完成正式运行。第二版把经验从文字记录升级为“已验证的程序 + 它成立的条件”：新任务先由程序复验最接近的已验证程序，学习运行在已知最佳上继续超越。在实现前封存的 D 批留出任务上（6 任务 × 3 次，v0 vs v19）：达标 15/18 → 18/18，最终加速比中位数 1.20× → 1.73×，模型请求中位数 2.5 → 0，GPT 费用 $0.376 → $0，单次研究循环时长中位数 53 s → 27 s；学习两轮另计 $0.455。第一版（只有文字经验）更省但最终加速比从 1.41× 降到 1.29×，这一发现是第二版修改的依据。完整数据与解读见实验结果和项目说明。

按现有赛事说明，项目材料于 11 月 15 日 08:00 前提交，当日上午现场展示，时区为 Asia/Shanghai。

## 快速开始

```sh
cd backend && uv sync && cp .env.example .env   # 填 OPENAI_API_KEY；本地 Qwen 走 Ollama
uv run routeevo tasks build                     # 按 tasks/lock.json 重建冻结的任务包
(cd ../frontend && pnpm install && pnpm build)
uv run routeevo serve                           # 打开 http://127.0.0.1:8000
```

- [后端说明](backend/README.md)：研究循环、Docker 沙箱与外部评测器、经验快照、对照评测、命令与接口。
- `frontend/`：展示界面——总览、研究运行、经验查看、对照结果、版本管理。

历史参考：[两个方向的差异](docs/track-differences.md)、[日新方向 PRD](docs/rixin-track-prd.md)。这两份文档保留选题过程，不属于当前开发范围。
