# 正式研究协议 v2

日期：2026-11-14。公共代码固定 `990f598b87f7c93bd27b6ceef5751bbc2d39dd79`，提示版本 `agent-prompt-v7`。本文与机器清单在首次正式模型请求前发布；新增 Decisions 路由消融 #6 使用另一个批次和 SHA。

## 预登记范围

[central-plan.json](central-plan.json) 固定全部 30 项逻辑矩阵：ahc024 F/I 各3次；ahc026 F/N/I 各3次；convolve_1d F/N/I 各3次；pagerank F/I 各3次。F/N/I 为 feedback/no_feedback/independent，三组按 F-N-I / N-I-F / I-F-N 轮换，两组交替。每题5 dev/15 final。

公共代码、模型、数据生成参数和30项矩阵统一固定，主机材料按执行分片绑定。ALE 的实际 task/image/prompt/hash/core/15项次序见 [ale-freeze.json](ale-freeze.json)，已可执行。Mac 的 task/image/hardware/calibration 仍由 #4 提交；绑定前其15项保持未运行，不以别的机器的数据冒充 Mac 结果。这项分片冻结安排替代“等待两机所有物理材料齐备才运行任一分片”的排期，实验矩阵与比较条件不变。

- 托管 Qwen3.8-27B，eval/v0，固定 small，关闭初始经验分流与模型升级。thinking=false、max_output_tokens=8192、response_format=json_object；完整公开配置进入冻结清单。
- 每轮上限900秒、20模型请求、10候选、单模型请求120秒。允许主动finish，不因开发达标提前停止。真实墙钟含模型与评测时间；预算外完成的候选保留记录但不入选。
- 每题各模式共用外部裁判、最优选择规则和 final 流程。先记录 loop_ended/best，再执行 final；final 不返回模型、不重选。
- ALE按原始score，5个dev用例各运行一次；AlgoTune以3预热/5计时为预登记起点，须由Mac校准确认。其3次研究重复与5次函数计时分别记录。

## 模型可见性

F 保留当前任务全部候选、模型分析/假设/意图和真实评测反馈。I 每次只看到公共任务、冻结初始程序/基线与预算，仅允许 propose_candidate/finish。N 保留全部已提交代码、提交顺序、父关系、模型自己的分析/假设/意图，隐藏后续外部评测结果、验证步骤、错误、计时、分数、排名、真实best和按验证状态筛选的候选列表。

三组共有首次 c0 的公开基线；N 后续重测 c0 也不更新这一公共快照。N/I 的真实 best 显示 withheld/null，不伪装成 c0。研究模式省略 parent 时统一使用 c0，显式 parent 可用于F/N迭代。N 的静态失败候选仍保留并可请求验证，真实失败照常落盘。

模型格式/动作参数错误可以返回；候选的语法、导入、编译、执行和裁判失败属于隐藏评测结果。native 的F/N均无cProfile工具。N保持真实请求数、候选数和总墙钟预算，因此仍存在总时间这一间接信号，不宣称消除所有时间侧信道。

## ALE 两路与失败处理

接受 [desktop无模型校准](ale/README.md) 记录的执行条件：A/ahc024候选CPU2，B/ahc026候选CPU4；judge维持未绑核；不改变governor/EPP，不宣称核心独占。各worker独立VAR_DIR、SQLite、run.lock和compare.lock。

前六个wave双路，双方结束后进入下一wave；后面三个wave为B单路。A每种模式各与B三种模式搭配一次；B每种模式均为两项双路、一项单路。wave等待在episode预算外，实际重叠及batch墙钟另记。desktop每worker最多一个在途模型请求，合计最多两个；公共调用原有限流/错误规则保留，不增加隐藏重试。

final状态分 disabled/pending/completed/failed/not_run；completed须验收通过。final错误输出、超时、裁判异常保留为failed。c0性能final正确时报告1.0且normalized=true/measured=false；ALE使用实际score。失败、缺失、c0、零改善保留在分母和配对表，c0分数为零不计算百分比。

环境、内部、模型API致命错误或人工停止会中断后续wave，已执行和未执行项全部留档；不自动重跑替换。单个候选final不通过照实计为失败，继续已登记的其他项。配置公平性独立于结果成败：相同配置且记录完整为true，变化为false，材料不足为null。

## 费用、接口和验证

[price-snapshot.json](price-snapshot.json) 冻结AIPing公开标价：输入¥3/百万Token、输出¥12/百万Token，缓存按普通输入价估算，不扣优惠和赠金；原始模型条目见 [provider-price.json](provider-price.json)。API实时账单与机器成本不等同于此估算，未知用量保留null。

新增只读 `/api/research-comparisons` 与 `/{comparison_id}`，直接读取既有比较JSON，可脱离原worker数据库展示。字段包括task/objective/mode/repeat/fair/dev/final/progress/usage/timing/cost。运行列表补research_mode/dev_only/final_status。[合成API示例](api-example.json) 明确标记fixture，不计入实验。

新增隔离、比较、报告/API的40项针对性检查全部通过，包括实际模型输入的反事实一致性、静态失败重验证、c0重测、final异常、失败样本、公平性、价格和未知费用。已通过的相关回归保留；按用户要求停止耗时全量测试，未将其记为全量通过。生产改动与样例以GPG签名发布。

## 执行

在desktop的固定源码checkout内，使用已登记的两worker任务包，先运行不带`--execute`的冻结一致性检查，再执行同一命令加`--execute`。脚本核对源码SHA、干净checkout、模型、任务manifest、镜像、schema和各模式提示哈希，拒绝覆盖已有批次目录。

```bash
cd /home/hycx233/routeevo-ale-formal-20261114/repo/backend
.venv/bin/python ../../run_ale.py \
  --root /home/hycx233/routeevo-ale-formal-20261114 \
  --manifest /home/hycx233/routeevo-ale-formal-20261114/freeze.json \
  --out /home/hycx233/routeevo-ale-formal-20261114/formal-v2 --execute
```

脚本按本次任务复用 `research_compare.execute(plan=...)`，不是新的队列服务。每wave记录墙钟，中央结果按预登记seq/task_id/repeat/mode匹配；完整真实请求、候选、评测和SQLite仍保留在各worker目录。
