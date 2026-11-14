# RouteEvo 文档导航

按阅读目的选择入口。需求与设计说明系统约定；每个实验批次自己的协议、冻结清单和结果记录说明实际执行情况。历史文档中的“当前”指其撰写时的版本，不覆盖后续批次。

## 从这里开始

| 想了解什么 | 阅读入口 |
| --- | --- |
| 项目做什么、如何演示 | [项目说明](presentation/project-description.md) · [演示脚本](presentation/demo.md) |
| 需求、赛题与验收 | [Research Agent PRD](requirements/research-agent-track-prd.md) · [赛题补充说明](requirements/research-agent-clarifications.md) · [验收对照](requirements/research-agent-acceptance.md) |
| 如何运行与开发 | [仓库首页](../README.md) · [后端说明](../backend/README.md) · [工程设计与接入](design/README.md) |
| 正式评测协议与交接 | [正式协议 v2](research/native-formal-20261114/protocol.md) · [中央 30 项计划](research/native-formal-20261114/central-plan.json) · [Mac 交接](research/native-formal-20261114/mac-handoff.md) |
| 实验结果与证据 | [实验批次索引](research/README.md) · [评测方法与历史结果](evaluation/README.md) |
| 提交材料与幻灯片 | [展示材料索引](presentation/README.md) |
| 早期方案与决策依据 | [历史归档](archive/README.md) |

## 目录职责

| 目录 | 内容与维护方式 |
| --- | --- |
| [requirements/](requirements/README.md) | 赛题原文、产品需求、核心 PRD 和验收对照 |
| [design/](design/README.md) | Benchmark 接入和动作/模型路由设计 |
| [evaluation/](evaluation/README.md) | 评测方法、旧经验对照汇总；具体运行以批次记录为准 |
| [research/](research/README.md) | 预实验、正式批次、冻结清单、候选、请求、报告和复现脚本 |
| [presentation/](presentation/README.md) | 项目说明、演示脚本、PPT/PDF 和幻灯片图表素材 |
| [archive/](archive/README.md) | 选题比较、首版决策、边界说明、接入预检与集成历史 |
| [decision-model/](decision-model/README.md) | Decisions API 的独立接口探索与冒烟证据 |
| [poster/](poster/) | 海报 PDF、预览和图像素材 |
| [licenses/](licenses/) | 第三方许可文本；总说明见 [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md) |

## 更新约定

- 新说明放入相应分类；新实验按批次单独建目录，并在实验索引登记协议、结果入口与状态。
- 实验报告保留其执行 SHA、模型、主机、计时和费用口径。开发集预实验、正式留出评测、固定模型与路由实验分别报告。
- 已冻结批次的原始数据、候选、请求、校验清单和目录位置保留；导航调整不重写实验结果。
- 同名 Markdown 是可编辑源文件，PDF/PPTX 是导出材料。更新源文档不表示已有导出文件已同步重建。
- 修改文件路径时，同时更新相对链接和生成脚本；提交前检查本地引用是否仍可解析。
