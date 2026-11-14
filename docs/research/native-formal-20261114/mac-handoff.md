# Mac AlgoTune：v2 计时协议交接

> 历史交接档案：本交接对应的 Mac 固定 Qwen 15 项与路由 12 项正式批次最终未启动（0/15、0/12）。后续在同一硬件上完成的非正式 dev-only 探索归档于 [Mac 探索结果包](../mac-exploratory-20261114/README.md)。

2026-11-14，关联 [issue #2](https://github.com/bohack-2026-hw/QuotaCrux/issues/2) 与 [issue #4](https://github.com/bohack-2026-hw/QuotaCrux/issues/4)。该交接版本记录了正式批次启动前的配置、计时修正与检查清单（当时正式评测处于 `0/15`、路由实验处于 `0/12` 待启动状态）。

## 机器、计时方法和代码版本

- [bdd78b8](https://github.com/bohack-2026-hw/QuotaCrux/commit/bdd78b85e448f591dab13babdc279ec7cd6cefe5) 已交付 M4 Max（12P+4E）/128 GiB、macOS 26.6.2、OrbStack 2.2.5 / Docker 29.8.2、原生 arm64 VM（16 vCPU、约15.66 GiB）及两题5 dev/15 final材料。候选固定使用 **Docker VM vCPU 2**，实际运行在哪个 Apple 核心由虚拟机调度。
- [64c64b0 的交替 GC 对照](https://github.com/bohack-2026-hw/QuotaCrux/blob/64c64b0/docs/research/native-formal-20261114/algotune/evidence/pagerank-gc-probe.json) 保留原始与 gc-disabled 各3次自比：PageRank第3样本/其余样本中位数从1.84418降至0.99752，组内极差/中位数从84.52%降至3.17%，均无误入选。该诊断已完成。
- 已在[验收评论](https://github.com/bohack-2026-hw/QuotaCrux/issues/4#issuecomment-6874329133)确认合入 [e28ce9d](https://github.com/bohack-2026-hw/QuotaCrux/commit/e28ce9dbadec01bc855345c40a2a9014a87ac022)：`isolated-function-timing-v2`，`gc_policy=automatic_gc_disabled_during_solve`。仅在solve计时内关闭自动循环GC，finally恢复；正常和异常恢复路径已有检查。基线/候选、预热/正式计时使用同一方法，候选选择标准不变。
- **Mac 执行 SHA：`912b20a4cfeb51af9c36d0679b23f0990abe862f`**，已由[PR #11](https://github.com/bohack-2026-hw/QuotaCrux/pull/11)合入main并核对远端ref。以此公共 checkout 内的原生导入器、计时器和 Mac 便携校准脚本准备；执行目录保持干净，正式期间不再更新。
- ALE 已实际使用 `990f598b87f7c93bd27b6ceef5751bbc2d39dd79`。两端的实际执行 SHA 分别记录，仍按同题、同机、同源码/镜像口径比较各模式；Mac 旧 v1 预检保留为历史修复证据。

## 评测设置与待填信息

[原30项逻辑计划](central-plan.json)、[研究协议](protocol.md)和[价格快照](price-snapshot.json)继续适用：convolve_1d 的F/N/I各3次，pagerank的F/I各3次；5 dev/15 final，`size=1000`、`seed=1729`。托管Qwen3.8-27B，`eval/v0`、固定small、thinking=false、max_output_tokens=8192、response_format=json_object；每轮900秒/20请求/10候选，请求超时120秒，允许主动finish。输入¥3/百万Token、输出¥12/百万Token，缓存按普通输入价估算，未知用量为null。本地MLX模型不进入该主批次。

本节prepared清单只含原固定Qwen的15项；追加Decisions的12项见下节，独立计划、VAR_DIR、baseline和费用，按各自已冻结次序串行执行。

Mac保持 **concurrency=1、VM vCPU 2、3次预热/5次函数计时**。重新导入必须生成新的candidate/judge image ID和任务ID，旧 `82a6fac682` / `b2ad8ba1c8` 任务包不直接用于正式批次。新输入仍使用原生成参数；对照记录dev/final文件hash，final只核验文件，不执行评测。

[mac-binding-prepared.json](mac-binding-prepared.json) 已保留原提案 hash、模型/预算、15 项顺序与中央映射，状态为 `prepared_not_executable`。重校准后需补齐以下条目：

| 待填项 | 要求 |
| --- | --- |
| 两题task_id / canonical manifest SHA256 | 与任务文件和SQLite注册一致；全部包文件hash核验通过 |
| candidate / 两题judge image ID | 原生arm64；实际环境协议为v2，逐sample记录gc_policy |
| 每题F/I或F/N/I system prompt hash | 从最终checkout与新任务构造，提示版本仍为`agent-prompt-v7` |
| 两题校准产物及SHA256 | 原3轮自比、正/反控制，3 warmups/5 timings；自比零误入选、控制符合预期；保留失败记录 |
| 主机/VM测量快照 | 实际CPU/内存、容器affinity及安静窗口负载；记录资源变化 |
| 正式账本初始状态 | 独立绝对VAR_DIR，runs/model_calls/final evaluations均为0，run.lock/compare.lock保留 |

旧任务和证据保留。新任务、镜像和机器登记完成前，prepared文件中的对应值保持null。

## 准备与一次最小启动核对

在最终执行SHA的干净checkout中，从`backend/`执行，使用新的绝对VAR_DIR和证据目录，保留旧预检账本：

```bash
uv sync --frozen --python 3.12.11
MAC_VAR="$PWD/var-algotune-formal-v2-20261114"
MAC_EVIDENCE="$MAC_VAR/evidence"
mkdir -p "$MAC_EVIDENCE"
export QUOTACRUX_NO_DOTENV=1
export QUOTACRUX_VAR_DIR="$MAC_VAR"
for problem in convolve_1d pagerank; do
  .venv/bin/quotacrux tasks import-algotune "$problem" \
    --split formal-v2-20261114 --dev-cases 5 --final-cases 15 --size 1000 --seed 1729
done
# 将变量设为本次 importer 实际返回的新 task_id。
.venv/bin/python scripts/calibrate_native.py --task-id "$CONVOLVE_TASK_ID" \
  --cpuset-cpus 2 --rounds 3 --repeats 5 --warmups 3 --control-delay-ms 3 \
  --output "$MAC_EVIDENCE/calibration-convolve_1d-v2.json"
.venv/bin/python scripts/calibrate_native.py --task-id "$PAGERANK_TASK_ID" \
  --cpuset-cpus 2 --rounds 3 --repeats 5 --warmups 3 --control-delay-ms 20 \
  --output "$MAC_EVIDENCE/calibration-pagerank-v2.json"
```

控制强度沿用已登记的3ms/20ms，不删除慢点或临时调统计门槛。只需要本次镜像/任务重建和这轮校准；正常/异常GC恢复检查与全量pytest不重复。

证据补齐并汇总后，将 prepared 文件补全并另存为 `mac-freeze.json`。首次付费请求前执行最小核对：实际 HEAD 与干净状态、冻结模型公开配置、两题包/SQLite/hash、镜像及 v2 环境字段、校准状态、模式提示 hash 和 15 项映射一致后启动。凭据由环境提供，取消准备阶段的 `QUOTACRUX_NO_DOTENV` 或显式加载所需模型环境，凭据不写入冻结文件。按同一 checkout/VAR_DIR 串行运行：

```bash
.venv/bin/quotacrux research-compare \
  --plan "$MAC_EVIDENCE/mac-freeze.json" --plan-id native-formal-20261114-mac-v2 \
  --pricing "$MAC_EVIDENCE/price-snapshot.json" --fixed-model small \
  --wall-clock 900 --max-requests 20 --max-candidates 10 --request-timeout 120 \
  --cpuset-cpus 2 --function-warmups 3
```

计划与价格材料来自准备文档提交`540adf6`，不要求执行SHA同时包含这些文档；把已核验的材料放在独立证据目录。若批次中断，保留原比较与未执行slot，先登记原因，再仅续接未启动项；不替换已有失败/中断轮次。研究结束先冻结dev最优候选，再做final；c0最终正确时记归一基线1×且未重新测速，失败、未完成及零改善继续进入分母。

## 随后直接执行的12轮Decisions路由批次

范围为新v2卷积任务：`baseline=llm/rule`、`action_decisions=decisions/rule`、`model_decisions=llm/decisions`、`both_decisions=decisions/decisions`各3次。四组均使用`feedback + adaptive + eval/v0`，`fixed_model=None`，关闭初始经验分流，初始small且允许单向升级至large。所有生成和Decisions HTTP尝试共用每轮900秒/20请求/10候选，错误与超时同样计数。

公开配置及三角色价格已在[routing preparation](https://github.com/bohack-2026-hw/QuotaCrux/blob/eea66f1484bc1f2909010c2b31b52ac858bba26e/docs/research/native-routing/20261114/preparation.json)和[prices.json](https://github.com/bohack-2026-hw/QuotaCrux/blob/eea66f1484bc1f2909010c2b31b52ac858bba26e/docs/research/native-routing/20261114/prices.json)备齐：small为Qwen3.8-27B，large为`gpt-6.1-sol / xhigh / 32000`，Decisions为`gpt-6-luna`。当前准备文件仍含旧执行SHA和旧Mac任务，尚非最终freeze；用本交接的最终SHA和已接受的新卷积绑定替换，保持其已登记的variant/repeat顺序及中央seq，冻结后另存Mac专属12项计划。价格分别保留CNY/USD，不跨币种直接相加。

路由批次使用新的绝对VAR_DIR和输出目录；同一冻结卷积包须在该目录完成文件及SQLite登记。原固定Qwen的feedback结果不能复用为路由baseline。`mac-routing-plan.json`保存准备文件`plan`中Mac卷积的12项JSON数组，保留原seq并替换新task_id；不要直接把整个preparation对象传给`--plan`。补齐路由问题、动作schema、模式提示及三角色公开配置/价格hash，确认与执行环境一致后，直接运行已授权的真实批次：

```bash
MAC_ROUTING_VAR="$PWD/var-algotune-routing-v2-20261114"
MAC_ROUTING_EVIDENCE="$MAC_ROUTING_VAR/evidence"
# 先在此新VAR_DIR登记已冻结的卷积包，并放入上述计划及三角色价格文件。
QUOTACRUX_VAR_DIR="$MAC_ROUTING_VAR" .venv/bin/quotacrux ablate-routing "$CONVOLVE_TASK_ID" \
  --snapshot v0 --repeats 3 --research-mode feedback --research-model-policy adaptive \
  --plan "$MAC_ROUTING_EVIDENCE/mac-routing-plan.json" --plan-id routing-native-20261114-mac-v2 \
  --pricing "$MAC_ROUTING_EVIDENCE/prices.json" \
  --wall-clock 900 --max-requests 20 --max-candidates 10 --request-timeout 120 \
  --cpuset-cpus 2 --function-warmups 3
```

两批都遵守先冻结dev最优再final、保留失败/c0/无收益与真实请求账本的规则；路由结果使用`study=routing`和`variant`，不写进原30项F/I/N表。当前只补各批启动所需核对，不重复已完成的诊断或全量测试。

## Mac执行序号与中央身份

沿用 `bdd78b8` 事前确定的交错顺序。`seq` 为 Mac 执行顺序，`central_slot` 仅按 `task_key + repeat + mode` 映射[总运行计划](central-plan.json)（保持原顺而不按 `central_slot` 重排）。新任务 ID 替换占位符时，模式、repeat 与顺序不变。

| seq | central_slot | 任务 | repeat | mode |
| ---: | ---: | --- | ---: | --- |
| 1 | 16 | convolve_1d | 1 | feedback |
| 2 | 26 | pagerank | 1 | independent |
| 3 | 17 | convolve_1d | 1 | no_feedback |
| 4 | 25 | pagerank | 1 | feedback |
| 5 | 18 | convolve_1d | 1 | independent |
| 6 | 28 | pagerank | 2 | feedback |
| 7 | 19 | convolve_1d | 2 | no_feedback |
| 8 | 27 | pagerank | 2 | independent |
| 9 | 20 | convolve_1d | 2 | independent |
| 10 | 30 | pagerank | 3 | independent |
| 11 | 21 | convolve_1d | 2 | feedback |
| 12 | 29 | pagerank | 3 | feedback |
| 13 | 22 | convolve_1d | 3 | independent |
| 14 | 23 | convolve_1d | 3 | feedback |
| 15 | 24 | convolve_1d | 3 | no_feedback |

交接依据：[issue #4 执行说明](https://github.com/bohack-2026-hw/QuotaCrux/issues/4#issuecomment-6874435562)。
