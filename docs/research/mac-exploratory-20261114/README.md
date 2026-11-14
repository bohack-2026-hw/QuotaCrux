# Mac 探索结果包（2026-11-14）

本目录归档 Snowball 在 Mac 高主机负载环境下完成的 **dev-only 探索**。OpenAI 批次关闭了 final evaluation；远端 LM Studio 批次没有产生完整的协议内模型候选。所有结果均为非正式证据，不得并入或替代已取消启动的 formal fixed 15 + routing 12 计划，也不支持跨机器、跨模型或跨评测口径比较。

## 来源与边界

- 执行代码固定为 [`912b20a4cfeb51af9c36d0679b23f0990abe862f`](https://github.com/bohack-2026-hw/RouteEvo/commit/912b20a4cfeb51af9c36d0679b23f0990abe862f)。
- OpenAI 批次固定 `gpt-6.1-sol`，每个任务只有 2 个 dev 用例，final evaluation disabled；运行时宿主处于高负载。
- 远端批次使用 LM Studio 的 `qwen3.8-27b-uncensored-mlx`，与托管 Qwen 配置不是同一运行时或量化，不能合并统计。
- 包内的机器路径、私有端点和凭据已清理；脱敏后的捕获 `run.log` 会提交，原始 SQLite/WAL、锁及 sealed dev/final 输入不提交。任务身份、输入文件和公开工件由哈希与字节数标识。
- 顶层 [`export-manifest.json`](export-manifest.json) 将整个包标为 `formal_results_eligible=false`；[`SHA256SUMS`](SHA256SUMS) 与 [`audit_results.py`](audit_results.py) 用于离线完整性和口径复核。

## OpenAI-only dev 探索

[`openai/comparison.json`](openai/comparison.json) 记录 4 个探索 run。12 次模型调用全部成功，共执行 16 次 dev evaluation；final evaluations 为 0。累计 slot 耗时为 567.385 秒（各 slot 相加，不是整批墙钟）。

| 任务 | 模式 | 最佳正确候选 dev 加速比 |
| --- | --- | ---: |
| convolve_1d | feedback | 1.298578× |
| convolve_1d | independent | 2.669288× |
| PageRank | feedback | 25.041935× |
| PageRank | independent | 23.051415× |

上述数字只描述本次 2-case dev 探索。它们未经过 held-out final，不是正式质量或泛化结论。

### Token 与估算费用

文件审计得到 34,240 input tokens、26,717 output tokens，其中 18,884 reasoning tokens 已包含在 output 中，不重复计费。按批次冻结的每百万 input/output tokens `USD 2 / USD 10` 估算：

```text
34,240 * 2 / 1,000,000 + 26,717 * 10 / 1,000,000 = USD 0.335650
```

这是用量估算，不是供应商账单，也不包含主机运行成本。

## 远端 LM Studio 协议尝试

远端模型为 `qwen3.8-27b-uncensored-mlx`。前三本独立失败账本合计记录 19 次 HTTP 503 调用：

| 账本 | 结果 |
| --- | --- |
| [`remote/01-preload-proxy`](remote/01-preload-proxy/) | 12 次 HTTP 503 |
| [`remote/02-loaded-proxy`](remote/02-loaded-proxy/) | 6 次 HTTP 503 |
| [`remote/03-bounded-proxy`](remote/03-bounded-proxy/) | 1 次 HTTP 503 |

绕过系统代理后的 [`remote/04-direct`](remote/04-direct/) 记录 1 次直连调用：请求耗时 120.19 秒，2,327 input tokens、2,047 output tokens，其中 1,707 reasoning tokens；请求因长度上限以 `incomplete/length` 结束。三个失败账本和一次直连调用均产生 **0 个完整协议模型候选**。

## 人工辅助语义重建

直连响应的完整 reasoning 已描述 rfft/irfft/next_fast_len 方案，但可见代码在尾部截断。人工据此语义重建尾部，同时移除未使用 import 并重命名局部变量；这不是模型自主交付，也不是“只补两行”。

单独的 2-case dev 检查结果为 2/2 correct、1.225486×。严格计时区间中，candidate max 为 0.000856825 秒，baseline min 为 0.000881116 秒。证据分别见 [`manual-completion-evaluation.json`](remote/04-direct/evidence/manual-completion-evaluation.json) 与 [`manual-completion-metadata.json`](remote/04-direct/evidence/manual-completion-metadata.json)。元数据明确：

```text
eligible_as_model_generated_candidate=false
formal_results_eligible=false
```

因此该产物不计入模型候选成功率、OpenAI 四项结果或任何正式结果。

## 工件索引

| 路径 | 内容 |
| --- | --- |
| [`export-manifest.json`](export-manifest.json) | 导出格式、执行代码 SHA、批次与非正式资格 |
| [`audit.json`](audit.json) | 最终离线审计输出；自身不纳入校验和以避免循环依赖 |
| [`openai/inventory.json`](openai/inventory.json) | OpenAI 批次包含/排除项、run 与 task 列表 |
| [`openai/comparison.json`](openai/comparison.json) | 四项对照结果和最佳 dev 候选 |
| [`openai/ledger.json`](openai/ledger.json) | SQLite 全表的可移植 JSON 快照 |
| [`openai/runs`](openai/runs/) | 每轮报告、模型调用、候选和 best.py |
| [`openai/tasks`](openai/tasks/) | 公开任务材料、身份与 sealed 数据哈希 |
| [`remote`](remote/) | 三本 503 失败账本、一次直连截断及人工检查证据 |
| [`SHA256SUMS`](SHA256SUMS) | 除自身与 `audit.json` 外所有已提交工件的 SHA-256 清单 |

各远端子目录同样包含 `inventory.json`、`comparison.json`、`ledger.json`、`runs/` 和 `tasks/`。调用失败、截断响应与候选均保留，没有只挑选成功项。

## 审计与复现

在仓库根目录执行离线审计：

```bash
python3 docs/research/mac-exploratory-20261114/audit_results.py
```

审计会验证 SHA-256、隐私模式、4 个 OpenAI run、12 次成功调用、16 次 dev evaluation、0 次 final evaluation、19 次 HTTP 503、直连截断以及人工重建的非正式标记。

有本机原始账本和外部证据目录时，可将清理后的包重新导出到临时目录：

```bash
result_dir="$(mktemp -d)/mac-exploratory-20261114"
python3 docs/research/mac-exploratory-20261114/export_results.py \
  --runs-root "$ROUTEEVO_RUNS_ROOT" \
  --evidence-root "$ROUTEEVO_EVIDENCE_ROOT" \
  --diagnostics-root "$ROUTEEVO_DIAGNOSTICS_ROOT" \
  --output "$result_dir"
```

原始源目录不属于可移植结果包；重新导出只用于持有本机证据的维护者复核。

## 限制

- 每个 OpenAI 任务仅一次模式运行、2 个 dev 用例，且 final disabled。
- 主机处于高负载，绝对耗时和加速比不应外推到安静窗口或其他硬件。
- 远端 LM Studio 没有完整协议候选；人工语义重建必须始终单列。
- 原 formal fixed 15 + routing 12 计划取消启动；本目录不能被解释为其部分完成或替代结果。
