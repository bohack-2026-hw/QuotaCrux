# ahc026 路由探索性小样本：结果摘要

2026-11-14，北京时间16:49:44至17:11:08，整批耗时21分24秒。四组各1次，研究循环统一上限360秒、20个全部HTTP请求、10候选，5 dev / 15 final。4/4 completed，4/4 final通过；真实调用账本与候选/冻结/final时序审计通过。

| 组 | final分数 | 相对c0提升 | 实际总耗时 | small / large请求 | Decisions请求 |
|---|---:|---:|---:|---:|---:|
| 基线 LLM / rule | 139736 | 5.970% | 392.0秒 | 3 / 6 | 0 |
| 仅动作 Decisions | 139972 | 6.149% | 389.4秒 | 2 / 5 | 7 |
| 仅模型 Decisions | 139559 | 5.836% | 389.9秒 | 7 / 4 | 8 |
| 双 Decisions | 132540 | 0.513% | 112.9秒 | 6 / 0 | 13 |

共同final c0分数为131864。仅动作Decisions这次取得最高分139972，比基线高236；仅模型Decisions为139559。双Decisions保持small、未升级GPT，112.9秒结束，得分132540，表现为更短时间与较小分数提升。每组仅1次，这些是本次运行的探索性观察。

实际共61次HTTP请求：18 small、15 large（含1次timeout）、28 Decisions。24个模型候选全部通过dev，另保留4个c0文件；最终交付候选全部通过15个final用例。

短批冻结标价估算：CNY 0.441477；USD已知部分0.8042835。基线组1次GPT timeout用量未知，USD总额保持null。不同币种分别记录，所有失败尝试计入请求预算。

完整[比较、配对与交互项](short-results/comparison.json)、[逐轮报告/候选/请求和曲线](short-results/README.md)、[审计结果](short-results/audit.json)、[SHA256清单](short-results/SHA256SUMS)均已导出。

原900秒长批按用户缩减范围指令停止，作为[独立补充记录](long-batch-stopped/README.md)保留：1 completed、1 user_stopped、10 not_run。其baseline final=139950，已知费用CNY0.128631及USD0.7716757，另有1次timeout用量未知。该长预算数据不混入上述短预算对照。

Mac因凭据与负载条件未满足，本轮未执行；当前交付范围为已有ALE反馈15项加本次desktop路由4项。
