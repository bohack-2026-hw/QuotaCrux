# RouteEvo 实验分析报告

本报告是本轮数据分析与结论的统一入口，后续 PPT、海报和演示可从此处取图、取数。报告使用 LaTeX 编写，主结果来自已归档的 desktop 实验；Mac 新探索结果保留 issue 级来源标记。

- **[阅读 PDF](output/pdf/routeevo-research-report.pdf)**：10 页，中文，包含方法、结果、轨迹、资源账本、结论与证据索引。
- [LaTeX 源码](report.tex)
- [可重算数据](generated/analysis.json)：逐轮结果、dev 轨迹、分角色调用与费用、批次汇总和 439 个输入文件哈希。
- [数值宏](generated/metrics.tex)：报告中的核心数据可直接引用。
- [矢量图与 PNG](figures/)：可单独用于后续排版。

## 阅读顺序

| PDF 页码 | 内容 |
| --- | --- |
| 1 | 执行摘要与关键观察 |
| 2–3 | 研究流程、模型分工、实验设计、统计口径 |
| 4 | 固定 Qwen：研究策略对照与反馈消融 |
| 5 | 四种路由组合的质量与实际耗时 |
| 6 | 真实开发轨迹：升级、改进、回退与保留最佳 |
| 7 | 请求、模型等待、分币种费用 |
| 8 | Mac 开发集探索及人工介入说明 |
| 9 | 三条结论、解释边界与展示建议 |
| 10 | 完整重复、费用小计、版本与证据索引 |

## 数据范围与结论

报告分析固定 Qwen 的 15 轮研究策略对照，以及 ahc026 四种路由组合各一次的短批；停止的 900 秒长批仅作为范围与费用附录。历史自建任务的跨任务经验复用作为能力背景，不混入本轮样本。

1. 研究闭环能够交付独立 final 验证后的改进方案；正确交付、c0 保留和模型候选通过率分别统计。
2. 路由短批观察到质量、时间与费用的取舍。动作 Decisions 相对 c0 提高 6.149%，相对路由 baseline 提高 0.169%；各组仅一次。
3. 固定 Qwen 下，当前反馈驱动策略未表现出稳定优势。F/I 同时改变历史与候选可见性，不能把二者差异只解释为反馈效应。

本轮 desktop 使用托管 Qwen3.8-27B；Decisions 是离散调度层，代码由 Qwen / Sol 生成。Mac 的约 25× 是两个 dev 用例上的作者报告值，原始文件待交付，没有 final；人工语义重建候选不计为模型自主交付。

## 图表使用

| 文件 | 内容与必要口径 |
| --- | --- |
| [feedback_ablation.pdf](figures/feedback_ablation.pdf) | 全部重复 + 中位数；空心点为 c0 交付，X 为 API 失败但保留正确候选的轮次；两面板刻度不同 |
| [routing_tradeoff.pdf](figures/routing_tradeoff.pdf) | final 质量与含最终测试的单轮总耗时；n=1；c0 与路由 baseline 不同 |
| [routing_trajectory.pdf](figures/routing_trajectory.pdf) | 5 例 dev 的 best-so-far，按真实验证结束时间作图；不混入 final |
| [routing_resources.pdf](figures/routing_resources.pdf) | 请求分工、时间分解、CNY/USD；baseline USD 为已知小计，timeout 用量未知 |

图内缩写：Baseline = LLM / rule，Action D = Decisions / rule，Model D = LLM / Decisions，Both D = Decisions / Decisions。

## 重建

依赖：Python 3.11+、`uv`、Matplotlib 3.10.8、XeLaTeX（TeX Live 的 ctex、fontspec、TikZ、tcolorbox 等包）、Noto Serif/Sans CJK SC、Liberation Serif/Sans、DejaVu Sans Mono。`pdftoppm`、`pdftotext` 和 `pdfinfo` 用于渲染核验。

在本目录运行：

```sh
bash build.sh
```

脚本先核验三个归档的 524 个 SHA256 条目，再从原始 JSON 重算图表并编译两遍 LaTeX。没有模型调用或 benchmark 执行；`uv` 首次运行可能下载绘图依赖。只重新编译排版时可运行：

```sh
xelatex -interaction=nonstopmode -halt-on-error -output-directory=output/pdf -jobname=routeevo-research-report report.tex
xelatex -interaction=nonstopmode -halt-on-error -output-directory=output/pdf -jobname=routeevo-research-report report.tex
```

`scripts/analyze.py` 校验候选哈希和调用数量，并按冻结价格重新计费。输出的分析依赖哈希与三批归档清单是不同范围：前者为实际读取的 439 个文件，后者为归档的 524 个条目。缺失用量以 `null` 总额和已知小计同时保留。

生成后的 PDF 应再次渲染检查。数值和图形可从归档重建；PDF 元数据包含编译时间，因此不保证 PDF 文件逐字节相同。

## 证据与验证

- 报告基于仓库快照 `cd9cc4fcc7af46451acd2398042c9e9b8b255d67`。
- 固定模型执行源码：`990f598b87f7c93bd27b6ceef5751bbc2d39dd79`。
- 路由与 Mac 最终执行源码：`912b20a4cfeb51af9c36d0679b23f0990abe862f`。
- [固定 Qwen 原始结果](../native-formal-20261114/ale/results/README.md)、[路由短批](../native-routing/20261114/short-results/README.md)、[停止长批](../native-routing/20261114/long-batch-stopped/README.md)。
- [Mac 作者汇报快照](sources/mac-openai-issue.json)、[人工介入更正快照](sources/mac-correction-issue.json)：保存来源 URL、作者、时间和文本，不代替运行原始文件。

已完成：归档哈希核验、原始数据重算、独立内容复核、LaTeX 编译与全部 10 页视觉检查。本次未重新运行裁判或模型；部分 benchmark 输入与 expected 文件不在当前归档中，复现实验需要对应上游环境和数据。
