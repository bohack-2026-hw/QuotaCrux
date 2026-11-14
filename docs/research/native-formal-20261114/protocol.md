# 正式研究协议 v2

日期：2026-11-14。提示版本为 `agent-prompt-v7`。ALE 使用代码版本 `990f598b87f7c93bd27b6ceef5751bbc2d39dd79`；Mac 新计时方法和 Decisions 路由使用 `912b20a4cfeb51af9c36d0679b23f0990abe862f`。下文的“冻结”指评测前固定代码、数据和参数，运行期间不再修改。

## 运行安排

[central-plan.json](central-plan.json) 列出 30 次运行：ahc024 的 F/I 各3次，ahc026 的 F/N/I 各3次，convolve_1d 的 F/N/I 各3次，pagerank 的 F/I 各3次。F/N/I 分别为 feedback/no_feedback/independent。三组按 F-N-I / N-I-F / I-F-N 轮换，两组交替。每题使用5个开发用例（dev）和15个最终测试用例（final）。

ALE 的任务、镜像、提示词、CPU 和15项顺序见 [ale-freeze.json](ale-freeze.json)。15项已执行：14项正常完成，1项因 API 错误失败；15个选定候选均通过最终测试。见 [ALE 结果](ale/results/README.md)。

Mac 已采用 GC v2 计时方法，待 #4 回传任务、镜像和校准记录后启动原15项，见 [Mac交接](mac-handoff.md)。各模式使用同题、同机、同代码和镜像，旧v1计时结果单独保留。Mac卷积另有12轮 Decisions 路由实验，使用独立计划和结果。各批校准及配置检查通过后即可启动。

以下设置用于原30项固定模型批次：

- 托管 Qwen3.8-27B，eval/v0，固定 small，关闭初始经验分流与模型升级。thinking=false、max_output_tokens=8192、response_format=json_object；完整公开配置进入冻结清单。
- 每轮上限900秒、20模型请求、10候选、单模型请求120秒。允许主动finish，不因开发达标提前停止。实际耗时含模型与评测时间；预算外完成的候选保留记录但不入选。
- 每题各模式共用外部裁判、最优选择规则和 final 流程。先记录 loop_ended/best，再执行 final；final 不返回模型、不重选。
- ALE按原始score，5个dev用例各运行一次；AlgoTune以3预热/5计时为预先确定起点，须由Mac校准确认。其3次研究重复与5次函数计时分别记录。

## 模型可见性

F 保留当前任务全部候选、模型分析/假设/意图和真实评测反馈。I 每次只看到公共任务、冻结初始程序/基线与预算，仅允许 propose_candidate/finish。N 保留全部已提交代码、提交顺序、父关系、模型自己的分析/假设/意图，隐藏后续外部评测结果、验证步骤、错误、计时、分数、排名、真实best和按验证状态筛选的候选列表。

三组都能看到初始程序 c0 的首次测试结果；N 组之后重测 c0 时仍显示首次结果。N/I 的最佳候选字段为 withheld/null。省略 parent 时统一使用 c0，F/N 可显式指定父候选。N 组中语法检查失败的代码也保留在列表中，允许再次请求验证。

模型回复格式或动作参数错误会返回提示；N 组看不到代码的语法、导入、编译、执行和裁判错误。F/N 的原生评测任务都不提供 cProfile。N 组仍能看到已用请求数、候选数和总耗时，因此耗时可能间接透露评测情况。

## ALE 两路与失败处理

按 [desktop校准](ale/README.md) 设置：ahc024 的候选程序固定使用 CPU2，ahc026 固定使用 CPU4；这些核心仍可能被其他进程使用。裁判未固定核心，governor/EPP 保持原值。每个执行进程（worker）有独立 VAR_DIR、SQLite、run.lock 和 compare.lock。

前六批同时运行 A/B 两路，两路都结束后再开始下一批；后三批只运行 B。A 的每种模式分别与 B 的三种模式搭配一次，B 的每种模式有两次双路、一次单路。批间等待不占单轮研究预算；重叠时间和整批耗时另记。每路最多一个模型请求，全机最多两个；沿用原有限流和错误处理规则，不额外重试。

final状态分 disabled/pending/completed/failed/not_run；completed须验收通过。final错误输出、超时、裁判异常保留为failed。c0性能final正确时报告1.0且normalized=true/measured=false；ALE使用实际score。失败、缺失、c0、零改善保留在分母和配对表，c0分数为零不计算百分比。

环境、内部、模型API致命错误或人工停止会中断后续wave，已执行和未执行项全部留档；不自动重跑替换。单个候选final不通过照实计为失败，继续已登记的其他项。配置公平性独立于结果成败：相同配置且记录完整为true，变化为false，材料不足为null。

## 费用、接口和验证

[price-snapshot.json](price-snapshot.json) 记录 AIPing 标价：输入¥3/百万Token，输出¥12/百万Token。缓存按普通输入价估算，不扣优惠和赠金；原始价格见 [provider-price.json](provider-price.json)。未知用量记null，实际账单和机器成本另计。

新增只读 `/api/research-comparisons` 与 `/{comparison_id}`，直接读取既有比较JSON，可脱离原worker数据库展示。字段包括task/objective/mode/repeat/fair/dev/final/progress/usage/timing/cost。运行列表补research_mode/dev_only/final_status。[合成API示例](api-example.json) 明确标记fixture，不计入实验。

40项输入隔离、对照、报告/API检查通过，覆盖：修改隐藏评测结果后模型输入不变、语法检查失败后重测、c0重测、final异常、失败样本、配置一致性及费用。全量测试未跑完。代码与样例已用GPG签名发布。

## 执行

以下保留已完成 ALE 批次的启动命令：在desktop的固定源码checkout内，使用已登记的两worker任务包，先运行不带`--execute`的冻结一致性检查，再执行同一命令加`--execute`。脚本核对源码SHA、干净checkout、模型、任务manifest、镜像、schema和各模式提示哈希，拒绝覆盖已有批次目录。当前待执行的 Mac 原15轮及新增路由12轮按 [Mac交接](mac-handoff.md)完成v2任务、镜像和机器登记后启动。

```bash
cd /home/hycx233/routeevo-ale-formal-20261114/repo/backend
.venv/bin/python ../../run_ale.py \
  --root /home/hycx233/routeevo-ale-formal-20261114 \
  --manifest /home/hycx233/routeevo-ale-formal-20261114/freeze.json \
  --out /home/hycx233/routeevo-ale-formal-20261114/formal-v2 --execute
```

脚本复用 `research_compare.execute(plan=...)`，逐批记录耗时。结果按计划中的seq/task_id/repeat/mode匹配，请求、候选、评测和SQLite保存在各worker目录。
