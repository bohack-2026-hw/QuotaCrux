# Desktop ahc026 Decisions 路由结果

执行源码 `912b20a4cfeb51af9c36d0679b23f0990abe862f`；计划 `routing-native-short-20261114-ale-v1`。
计划四组各1次，feedback/adaptive、eval/v0；每轮360秒、20个全部HTTP请求、10候选。5 dev / 15 final，dev选优冻结后执行final。探索性小样本，报告实际效应与成本。

运行状态 `{'completed': 4}`；审计 `passed=True`，fair=`True`。
导出 28 份候选、61 份调用JSON；失败和未跑项保留。

| 组 | final分数 | small / large请求 | 路由请求 | 升级轮数 | 候选通过/提出 |
|---|---|---:|---:|---:|---:|
| baseline | [139736] | 3 / 6 | 0 | 1 / 1 | 5 / 5 |
| action_decisions | [139972] | 2 / 5 | 7 | 1 / 1 | 7 / 7 |
| model_decisions | [139559] | 7 / 4 | 8 | 1 / 1 | 6 / 6 |
| both_decisions | [132540] | 6 / 0 | 13 | 0 / 1 | 6 / 6 |

费用按币种分别记录；unknown/partial不补零。

```json
{
  "CNY": {
    "amount": 0.441477,
    "known_amount": 0.441477,
    "status": "estimated"
  },
  "USD": {
    "amount": null,
    "known_amount": 0.8042834999999999,
    "status": "partial"
  }
}
```

逐轮状态、final、配对差异、交互项、动作频率与routing/generation用量见 [comparison.json](comparison.json)。
过程图使用dev保留分数，不含final；CNY与USD分别为各币种累计成本，不进行换汇相加。预算中路由请求会占用生成机会，未观察到升级的轮次原样保留。

![ahc026 elapsed_s](ahc026-elapsed_s.svg)

![ahc026 tokens](ahc026-tokens.svg)

![ahc026 CNY](ahc026-CNY.svg)

![ahc026 USD](ahc026-USD.svg)
