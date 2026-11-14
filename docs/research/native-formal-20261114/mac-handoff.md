# Mac AlgoTune：v2 计时协议交接

2026-11-14。负责人 SnowballXueQiu，公共协调 #2。**固定Qwen正式评测0/15，路由实验0/12；等待新版本的任务、镜像和校准记录。** 用户已授权：校准和配置检查通过后直接运行。

## 机器、计时方法和代码版本

- [bdd78b8](https://github.com/bohack-2026-hw/RouteEvo/commit/bdd78b85e448f591dab13babdc279ec7cd6cefe5) 已交付 M4 Max（12P+4E）/128 GiB、macOS 26.6.2、OrbStack 2.2.5 / Docker 29.8.2、原生 arm64 VM（16 vCPU、约15.66 GiB）及两题5 dev/15 final材料。候选固定使用 **Docker VM vCPU 2**，实际运行在哪个 Apple 核心由虚拟机调度。
- [64c64b0 的交替 GC 对照](https://github.com/bohack-2026-hw/RouteEvo/blob/64c64b0/docs/research/native-formal-20261114/algotune/evidence/pagerank-gc-probe.json) 保留原始与 gc-disabled 各3次自比：PageRank第3样本/其余样本中位数从1.84418降至0.99752，组内极差/中位数从84.52%降至3.17%，均无误入选。该诊断已完成，无需重复。
- #2 已在[接受记录](https://github.com/bohack-2026-hw/RouteEvo/issues/4#issuecomment-6874329133)接受 [e28ce9d](https://github.com/bohack-2026-hw/RouteEvo/commit/e28ce9dbadec01bc855345c40a2a9014a87ac022)：`isolated-function-timing-v2`，`gc_policy=automatic_gc_disabled_during_solve`。仅在solve计时内关闭自动循环GC，finally恢复；正常和异常恢复路径已有检查。基线/候选、预热/正式计时使用同一方法，候选选择标准不变。
- **Mac 执行 SHA：`912b20a4cfeb51af9c36d0679b23f0990abe862f`**，已由[PR #11](https://github.com/bohack-2026-hw/RouteEvo/pull/11)合入main并核对远端ref。以此公共 checkout 内的原生导入器、计时器和 Mac 便携校准脚本准备；执行目录保持干净，正式期间不再更新。
- ALE 已实际使用 `990f598b87f7c93bd27b6ceef5751bbc2d39dd79`，不改写其来源。原“统一执行 SHA”在本次计时修订后改为分别记录 ALE 与 Mac 的实际 SHA；仍按题、同机、同源码/镜像比较各模式。Mac旧v1预检只作为修复证据，不进入v2正式计时汇总。

## 评测设置与待填信息

[原30项逻辑计划](central-plan.json)、[研究协议](protocol.md)和[价格快照](price-snapshot.json)继续适用：convolve_1d 的F/N/I各3次，pagerank的F/I各3次；5 dev/15 final，`size=1000`、`seed=1729`。托管Qwen3.8-27B，`eval/v0`、固定small、thinking=false、max_output_tokens=8192、response_format=json_object；每轮900秒/20请求/10候选，请求超时120秒，允许主动finish。输入¥3/百万Token、输出¥12/百万Token，缓存按普通输入价估算，未知用量为null。本地MLX模型不进入该主批次。

本节prepared清单只含原固定Qwen的15项；追加Decisions的12项见下节，独立计划、VAR_DIR、baseline和费用，按各自已冻结次序串行执行。

Mac保持 **concurrency=1、VM vCPU 2、3次预热/5次函数计时**。重新导入必须生成新的candidate/judge image ID和任务ID，旧 `82a6fac682` / `b2ad8ba1c8` 任务包不直接用于正式批次。新输入仍使用原生成参数；对照记录dev/final文件hash，final只核验文件，不执行评测。

[mac-binding-prepared.json](mac-binding-prepared.json) 已保留原提案hash、模型/预算、15项顺序与中央映射，状态为`prepared_not_executable`。#4重校准后补齐：

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
export ROUTEEVO_NO_DOTENV=1
export ROUTEEVO_VAR_DIR="$MAC_VAR"
for problem in convolve_1d pagerank; do
  .venv/bin/routeevo tasks import-algotune "$problem" \
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

新证据回传 #4/#2 后，将prepared文件补全并另存为`mac-freeze.json`。首次付费请求前做一次最小核对：实际HEAD与清洁状态、冻结模型公开配置、两题包/SQLite/hash、镜像及v2环境字段、校准状态、模式提示hash和15项映射均一致即启动，无需等待再次确认。凭据由环境提供，取消准备阶段的`ROUTEEVO_NO_DOTENV`或显式加载所需模型环境，不将密钥写入冻结文件。按同一checkout/VAR_DIR串行运行：

```bash
.venv/bin/routeevo research-compare \
  --plan "$MAC_EVIDENCE/mac-freeze.json" --plan-id native-formal-20261114-mac-v2 \
  --pricing "$MAC_EVIDENCE/price-snapshot.json" --fixed-model small \
  --wall-clock 900 --max-requests 20 --max-candidates 10 --request-timeout 120 \
  --cpuset-cpus 2 --function-warmups 3
```

计划与价格材料来自准备文档提交`540adf6`，不要求执行SHA同时包含这些文档；把已核验的材料放在独立证据目录。若批次中断，保留原比较与未执行slot，先登记原因，再仅续接未启动项；不替换已有失败/中断轮次。研究结束先冻结dev最优候选，再做final；c0最终正确时记归一基线1×且未重新测速，失败、未完成及零改善继续进入分母。

## 随后直接执行的12轮Decisions路由批次

范围为新v2卷积任务：`baseline=llm/rule`、`action_decisions=decisions/rule`、`model_decisions=llm/decisions`、`both_decisions=decisions/decisions`各3次。四组均使用`feedback + adaptive + eval/v0`，`fixed_model=None`，关闭初始经验分流，初始small且允许单向升级至large。所有生成和Decisions HTTP尝试共用每轮900秒/20请求/10候选，错误与超时同样计数。

公开配置及三角色价格已在[routing preparation](https://github.com/bohack-2026-hw/RouteEvo/blob/eea66f1484bc1f2909010c2b31b52ac858bba26e/docs/research/native-routing/20261114/preparation.json)和[prices.json](https://github.com/bohack-2026-hw/RouteEvo/blob/eea66f1484bc1f2909010c2b31b52ac858bba26e/docs/research/native-routing/20261114/prices.json)备齐：small为Qwen3.8-27B，large为`gpt-6.1-sol / xhigh / 32000`，Decisions为`gpt-6-luna`。当前准备文件仍含旧执行SHA和旧Mac任务，尚非最终freeze；用本交接的最终SHA和已接受的新卷积绑定替换，保持其已登记的variant/repeat顺序及中央seq，冻结后另存Mac专属12项计划。价格分别保留CNY/USD，不跨币种直接相加。

路由批次使用新的绝对VAR_DIR和输出目录；同一冻结卷积包须在该目录完成文件及SQLite登记。原固定Qwen的feedback结果不能复用为路由baseline。`mac-routing-plan.json`保存准备文件`plan`中Mac卷积的12项JSON数组，保留原seq并替换新task_id；不要直接把整个preparation对象传给`--plan`。补齐路由问题、动作schema、模式提示及三角色公开配置/价格hash，确认与执行环境一致后，直接运行已授权的真实批次：

```bash
MAC_ROUTING_VAR="$PWD/var-algotune-routing-v2-20261114"
MAC_ROUTING_EVIDENCE="$MAC_ROUTING_VAR/evidence"
# 先在此新VAR_DIR登记已冻结的卷积包，并放入上述计划及三角色价格文件。
ROUTEEVO_VAR_DIR="$MAC_ROUTING_VAR" .venv/bin/routeevo ablate-routing "$CONVOLVE_TASK_ID" \
  --snapshot v0 --repeats 3 --research-mode feedback --research-model-policy adaptive \
  --plan "$MAC_ROUTING_EVIDENCE/mac-routing-plan.json" --plan-id routing-native-20261114-mac-v2 \
  --pricing "$MAC_ROUTING_EVIDENCE/prices.json" \
  --wall-clock 900 --max-requests 20 --max-candidates 10 --request-timeout 120 \
  --cpuset-cpus 2 --function-warmups 3
```

两批都遵守先冻结dev最优再final、保留失败/c0/无收益与真实请求账本的规则；路由结果使用`study=routing`和`variant`，不写进原30项F/I/N表。当前只补各批启动所需核对，不重复已完成的诊断或全量测试。

## Mac执行序号与中央身份

沿用 #4 在`bdd78b8`事前发布的交错顺序。`seq`是Mac执行顺序，`central_slot`仅按`task_key + repeat + mode`映射[总运行计划](central-plan.json)，**不按central_slot重新排序**。新任务ID替换占位时，模式、repeat和顺序保持不变。

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

交接依据：[#4最终代码版本与27轮启动授权](https://github.com/bohack-2026-hw/RouteEvo/issues/4#issuecomment-6874435562)。
