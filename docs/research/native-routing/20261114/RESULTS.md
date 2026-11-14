# ahc026 路由探索性小样本：结果摘要

2026-11-14，北京时间16:49:44至17:11:08，整批耗时21分24秒。四组各1次，研究循环统一上限360秒、20个全部HTTP请求、10候选，5 dev / 15 final。4/4 completed，4/4 final通过；真实调用账本与候选/冻结/final时序审计通过。

| 组 | final分数 | 相对c0提升 | 实际总耗时 | small / large请求 | Decisions请求 |
|---|---:|---:|---:|---:|---:|
| 基线 LLM / rule | 139736 | 5.970% | 392.0秒 | 3 / 6 | 0 |
| 仅动作 Decisions | 139972 | 6.149% | 389.4秒 | 2 / 5 | 7 |
| 仅模型 Decisions | 139559 | 5.836% | 389.9秒 | 7 / 4 | 8 |
| 双 Decisions | 132540 | 0.513% | 112.9秒 | 6 / 0 | 13 |

共同 final `c0` 分数为 131864。仅动作 Decisions 本次取得最高分 139972（较基线高 236 分），仅模型 Decisions 为 139559；双 Decisions 保持在 small 模型未升级 GPT，112.9 秒结束并取得 132540 分，表现为更短耗时与较小涨幅。四组各仅运行一次，以上为本批单次探索观察。

实际共61次HTTP请求：18 small、15 large（含1次timeout）、28 Decisions。24个模型候选全部通过dev，另保留4个c0文件；最终交付候选全部通过15个final用例。

短批冻结标价估算：CNY 0.441477；USD已知部分0.8042835。基线组1次GPT timeout用量未知，USD总额保持null。不同币种分别记录，所有失败尝试计入请求预算。

完整[比较、配对与交互项](short-results/comparison.json)、[逐轮报告/候选/请求和曲线](short-results/README.md)、[审计结果](short-results/audit.json)、[SHA256清单](short-results/SHA256SUMS)均已导出。

原 900 秒长批在中途终止后已作为[独立补充记录](long-batch-stopped/README.md)单列：1 completed、1 user_stopped、10 not_run。其 `baseline` final 为 139950，已知费用为 CNY 0.128631 与 USD 0.7716757（另有 1 次超时用量未知），与上述 360 秒短批分别统计。

Mac 端本轮因凭据与负载条件未具备，正式批次未启动；本目录仅包含 desktop 端短批 4 项及上述中止长批（ALE 反馈 15 项另见 `native-formal-20261114`）。
