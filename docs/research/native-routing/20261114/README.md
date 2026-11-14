# 原生路由探索性小样本

用户于2026-11-14将当前交付缩为“半小时左右、最多1小时”的小子集。当前采用 ahc026 四种路由各1轮，每轮统一360秒、20个全部HTTP请求、10候选；5 dev / 15 final不变。评测上限合计24分钟，随后导出真实结果。样本用于展示行为、效应与成本，明确每组仅1次。

执行源码固定 `912b20a4cfeb51af9c36d0679b23f0990abe862f`。四组顺序仍为 baseline、action_decisions、model_decisions、both_decisions；均为feedback/adaptive、eval/v0、fixed_model=None，small起步且可单向升级。所有生成与Decisions请求共用预算。

[短批冻结清单](ale-short-freeze.json)与[四项计划](ale-short-plan.json)记录修改后的预算和范围。复用已核验的干净912 checkout、venv、ahc026任务包、候选/裁判镜像和CPU4；新建独立的绝对VAR_DIR/SQLite。模型保持Qwen3.8-27B（thinking=false、8192）、gpt-6.1-sol（xhigh、32000）、gpt-6-luna Decisions。价格见[prices.json](prices.json)，CNY/USD分别统计，未知用量保持unknown/partial。

原12项长批已按用户要求停止：保留已完成baseline、按user_stopped结束的action轮，以及全部超时/调用/候选/final记录。它们使用900秒预算，单独作为补充记录，不混入短批对照。原[ale-freeze.json](ale-freeze.json)、[24项准备清单](preparation.json)、[长预算估算](estimate.json)及其历史提交继续保留，均不是当前待执行范围。

启动命令：

```sh
cd /home/hycx233/routeevo-routing-formal-20261114/repo/backend
.venv/bin/python /home/hycx233/routeevo-routing-short-20261114/run_ale_routing.py \
  --freeze /home/hycx233/routeevo-routing-short-20261114/ale-short-freeze.json --execute
```

[长批环境证据](ale-preflight/deployment.json)中的模型、任务、镜像和源码内容沿用；短批另做空账本与新冻结文件核对，不重跑校准或全量测试。执行助手位于checkout外，以SHA256固定；首次启动使用排他冻结文件，防止重复执行。

原固定Qwen反馈消融ALE15项已独立完成并发布，不因本次路由预算变更改写。Mac尚未完成的物理校准和后续范围另行记录。
