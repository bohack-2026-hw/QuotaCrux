# 历史文档

按“选题 → 首版实现 → 早期评测”保存开发过程。后续执行情况见[实验批次](../research/README.md)。

| 阶段 | 文档 | 为什么保留 |
| --- | --- | --- |
| 赛道选择 | [两个赛道比较](track-comparison.md)、[日新需求](rixin-requirements.md) | 记录选择 Research Agent 的依据与未采用方案 |
| 首版实现 | [实现决定与问答](initial-implementation-decisions.md)、[运行规则](legacy-runtime-rules.md) · [PDF](legacy-runtime-rules.pdf) | 说明早期模型、预算、经验和版本规则 |
| 接入选型 | [评测集调研](benchmark-survey.md)、[EffiBench-X 预检](effibench-preflight.md) | 保存选型和首次接入结果 |
| 主分支整合 | [2026-11-14集成记录](integration-20261114.md) | 记录并行开发线合并的提交与检查 |
| 反馈对照 | [初版双组方案](feedback-comparison-plan-v1.md) | 保存正式 v2 三模式协议之前的设计 |
| 经验学习 | [第一至三版结果](memory-learning-results.md) · [PDF](memory-learning-results.pdf) | 保存 groupagg、D 留出和 S 任务流的完整汇总 |
| 演示文稿第一版 | [项目与技术文稿](presentation-v1/)（PPTX · PDF，`backend/scripts/build_deck.py` 生成） | 2026-11 被 `docs/presentation/slides/` 的新版技术演示取代 |
| Decisions 探索 | [接口探索与回放](decisions-experiments/README.md)、[原24轮计划](routing-study-plan-v1.md) | 保存初次接口验证和范围调整前的计划 |

历史结果生成脚本 `backend/scripts/write_results.py` 输出到 `memory-learning-results.md`。后续路由实验见[当前入口](../research/native-routing/README.md)。

[返回文档导航](../README.md)。
