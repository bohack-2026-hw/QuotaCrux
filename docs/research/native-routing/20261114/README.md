# 原生路由探索性小样本

**已完成：4/4 运行结束，4/4 final 通过，实际耗时 21 分 24 秒。** 参见[结果摘要](RESULTS.md)与[完整证据/曲线](short-results/README.md)。

2026-11-14 调整范围后，本批聚焦在约一小时内可完成的 `ahc026` 探索性小子集：四组路由各执行 1 轮，每轮统一设为 360 秒、20 次全部 HTTP 请求与 10 候选上限（5 dev / 15 final 不变），研究循环总预算约 24 分钟（final、启动与导出另计），每组均为单次观察样本。

执行源码固定为 `912b20a4cfeb51af9c36d0679b23f0990abe862f`。四组顺序仍为 `baseline`、`action_decisions`、`model_decisions`、`both_decisions`；均启用 `feedback`、`adaptive`、`eval/v0`、`fixed_model=None`，由小模型起步并可单向升级，所有生成与 Decisions 请求共用同一预算。

[短批冻结清单](ale-short-freeze.json)与[四项计划](ale-short-plan.json)记录调整后的预算和范围，沿用经核验的 `912` checkout、venv、`ahc026` 任务包、候选/裁判镜像与逻辑 CPU4，并启用独立的 `VAR_DIR` 与 SQLite。模型固定为 Qwen3.8-27B（`thinking=false`、`8192`）、gpt-6.1-sol（`xhigh`、`32000`）与 gpt-6-luna（Decisions）。单价快照见 [prices.json](prices.json)，CNY/USD 分别统计，未知用量保留 `unknown/partial`。

此前启动的 12 项 900 秒长批已中途终止，已产生的 `baseline` 完成记录、`action_decisions` 的 `user_stopped` 记录及原始调用、候选与 final 数据归档在 [long-batch-stopped/](long-batch-stopped/README.md)，与短批对照分开列示；原 [ale-freeze.json](ale-freeze.json)、[24项准备清单](preparation.json) 与 [长预算估算](estimate.json) 作为早期规划文档保留。

启动命令示例：

```sh
cd "$HOME/routeevo-routing-formal-20261114/repo/backend"
.venv/bin/python "$HOME/routeevo-routing-short-20261114/run_ale_routing.py" \
  --freeze "$HOME/routeevo-routing-short-20261114/ale-short-freeze.json" --execute
```

[长批环境证据](ale-preflight/deployment.json)中的模型、任务、镜像和源码内容沿用；短批执行前另行核对空账本与新冻结清单。执行脚本位于 checkout 之外并以 SHA256 锁定，首次启动使用排他冻结文件。

此前独立完成的固定 Qwen 反馈对照 ALE 15 项保留各自独立记录；Mac 端的校准与探索结果见另行归档的目录。
