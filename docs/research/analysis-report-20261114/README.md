# QuotaCrux / 枢决：研究优化实验报告

**[阅读 PDF（19 页，v1.2）](output/pdf/quotacrux-research-report.pdf)**

报告围绕系统机制、实验结果和过程分析展开，作为后续 PPT、海报与演示的数据来源。正文使用思源宋体，标题使用思源黑体 Medium；七张图统一中文标注，并保存独立矢量 PDF。

## 阅读与源码

| 页码 | 内容 | 源码 |
| --- | --- | --- |
| 1–2 | 摘要、目录与结果索引 | [report.tex](report.tex) |
| 3–4 | 系统状态、模块、动作与模型决策、F/I/N 信息条件 | [系统设计](sections/01-system.tex) |
| 5–6 | 任务定义、GC v2、环境、实验矩阵与指标 | [实验方法](sections/02-protocol.tex) |
| 7–8 | 固定 Qwen 结果、候选质量、重复代码与地图失败链 | [策略分析](sections/03-feedback.tex) |
| 9–10 | 路由结果、搬运能耗换算、升级和停止 | [路由分析](sections/04-routing.tex) |
| 11–12 | 搬箱算法逐次变化、候选退步与保留最佳 | [研究案例](sections/05-case.tex) |
| 13–14 | 请求、等待、决策开销与按角色费用 | [资源分析](sections/06-resources.tex) |
| 15–16 | 卷积与 PageRank 算法路径、逐候选结果、计时范围 | [Mac 探索](sections/07-mac.tex) |
| 17 | 综合结论与具体改进方向 | [结论](sections/08-conclusions.tex) |
| 18–19 | 全部重复、费用、版本与数据复核状态 | [附录](sections/09-appendix.tex) |

## 可复用数据与图表

- [analysis.json](generated/analysis.json)：desktop 逐轮结果、开发轨迹、调用和费用，439 个分析输入文件的 SHA256。
- [deep-analysis.json](generated/deep-analysis.json)：候选失败类型、重复哈希、刷新最佳、路由动作与延迟、箱子搬运能耗。
- [mac-analysis.json](generated/mac-analysis.json)：Mac 运行账本、逐候选计时、输入参数、来源哈希与导出代码复核状态。
- [metrics.tex](generated/metrics.tex)：可直接引用的数值宏；同目录另有生成的表格行。

| 图表 | 内容 |
| --- | --- |
| [策略最终结果](figures/feedback_ablation.pdf) | 全部重复、中位数与 c0 交付 |
| [候选结果分类](figures/candidate_outcomes.pdf) | 正确且优于初始、正确但无初始提升、失败 |
| [路由质量与耗时](figures/routing_tradeoff.pdf) | 最终提升与实际单轮总耗时 |
| [开发过程轨迹](figures/routing_trajectory.pdf) | 验证结束时的保留最佳 |
| [搬箱候选案例](figures/action_case.pdf) | 每个候选的实际得分与保留最佳 |
| [资源账本](figures/routing_resources.pdf) | 请求角色、时间阶段与分币种费用 |
| [Mac 函数计时](figures/mac_timings.pdf) | 最佳候选及参考实现的中位数和 min–max 范围 |

图表同时提供同名 PNG。分析区分“相对初始程序的改进”和“刷新本轮最佳”；搬运能耗是 ahc026 任务定义的操作代价。

## 重建报告

依赖：Python 3.11+、uv、Matplotlib 3.10.8、XeLaTeX / TeX Live（ctex、fontspec、TikZ、tcolorbox 等）、思源宋体、思源黑体、Liberation Serif/Sans、DejaVu Sans Mono。绘图脚本使用 /usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-Regular.otf，将所需字形转换为临时 TrueType 子集以嵌入矢量 PDF。

在本目录运行：

    bash build.sh

构建流程核验 desktop 三批 524 个清单条目，从原始 JSON 重算 desktop 数据和六张图，随后校验 Mac 归档并重算其分析 JSON 与计时图，最后编译 LaTeX。该脚本仅读取本地归档，不触发模型或基准评测；首次执行可能需拉取绘图依赖。

只更新正文时，执行两遍：

    xelatex -interaction=nonstopmode -halt-on-error -output-directory=output/pdf -jobname=quotacrux-research-report report.tex

Mac 归档（提交 `5962203`）可单独重新分析：

    uv run --with matplotlib==3.10.8 python scripts/analyze_mac.py --source ../mac-exploratory-20261114 --source-commit 5962203315dc1c229cd6ef3255d06e2dc5745436

脚本只读取本地目录，输出分析 JSON、代码一致性检查和图表。`--plot-only` 仅使用已保存的分析 JSON 重建图形。

## 数据版本与复核

- desktop 数据快照：cd9cc4fcc7af46451acd2398042c9e9b8b255d67。
- 固定 Qwen 执行源码：990f598b87f7c93bd27b6ceef5751bbc2d39dd79。
- 路由及 Mac 最终执行源码：912b20a4cfeb51af9c36d0679b23f0990abe862f。
- [固定 Qwen 结果](../native-formal-20261114/ale/results/README.md)、[路由短批](../native-routing/20261114/short-results/README.md)、[停止长批](../native-routing/20261114/long-batch-stopped/README.md)。
- [Mac 探索归档](https://github.com/bohack-2026-hw/QuotaCrux/tree/5962203315dc1c229cd6ef3255d06e2dc5745436/docs/research/mac-exploratory-20261114)及[导出一致性核验记录](https://github.com/bohack-2026-hw/QuotaCrux/pull/20#issuecomment-6875817264)。

Mac 归档已完成导出恢复与校验（189 项清单、24 份候选、12 份最优程序与 16 份任务源码哈希一致，53 份归档程序通过语法检查；分析状态为 `verified_archive`，恢复记录见 [recovery.json](../mac-exploratory-20261114/recovery.json)）。

构建检验覆盖归档 SHA256、原始数据重算、LaTeX 无警告编译与字体嵌入。源码仓库为 QuotaCrux（归档 JSON 中保留历史标识 RouteEvo）。
