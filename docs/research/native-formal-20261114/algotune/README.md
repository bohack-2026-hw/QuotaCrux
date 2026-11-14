# AlgoTune 正式批次：Mac 环境、任务包与无模型校准

2026-11-14，负责人 SnowballXueQiu，执行机为本机 Mac。关联 [AlgoTune #4](https://github.com/bohack-2026-hw/RouteEvo/issues/4) 与 [公共协议 #2](https://github.com/bohack-2026-hw/RouteEvo/issues/2)。

**状态：环境与两题 5 dev / 15 final 任务包已完成；当前校准为有保留的预检，尚未冻结；正式批次为 0/15。** 本目录没有正式模型回复或 final 评测。SQLite 记录 `runs=0`、`model_calls=0`、`final evaluations=0`，API 支出为 0。正式调用仍等待 #2 冻结计时处理、唯一实验 SHA、完整三模式提示与哈希、价格快照和中央 run plan，并须在安静窗口重新校准。

## 执行环境

- 校准任务和 evaluator 基于 `main@a67850f3db224a9243f59703d25397ede3d54aa7`，独立分支 `bench/algotune-formal-v1`、独立 VAR_DIR `backend/var-algotune-formal-20261114`。
- Apple M4 Max，12 个性能核 + 4 个能效核，128 GiB 内存；macOS 26.6.2（25G83）。
- OrbStack 2.2.5，Docker 29.8.2；Docker VM 暴露 16 vCPU、约 15.66 GiB 内存，server 为原生 `linux/aarch64`。candidate 与两个 judge 镜像均为 `arm64`，没有使用 Rosetta 或跨架构模拟。
- 使用 CPython 3.12.11、uv 0.8.19，并以 `uv sync --frozen --python 3.12.11` 安装锁定依赖。
- 候选容器使用 1 CPU、1 GiB、64 PIDs、无网络、只读根文件系统；函数预热 3 次、计时 5 次。
- affinity 探针在卷积与 PageRank 两批都连续返回 5 次 `[2]`。这是 **Docker VM vCPU 2**，不能映射成某个 M4 性能核，也没有物理核心排他性。

[host.json](evidence/host.json) 记录宿主、Docker VM、工具链和本地模型元数据。Docker 本地 BuildKit 镜像没有 registry RepoDigest；本批使用实际不可变 image ID，不把 tag 称为 digest。

| 镜像 | image ID |
| --- | --- |
| scientific candidate | `sha256:fed60f772eae5dfbe9b664b26450e6678ff541fe790a37968cde616859cfb5f9` |
| convolve_1d judge | `sha256:80e01b815874ca9173db16763ea48b0ff15d579fa98c77c9ed0397377ae9418e` |
| pagerank judge | `sha256:1d0ca27092f2616f71e7eecdaa1853ef9c920e248e41b7b22fe53387630da14b` |

校准结束后没有遗留 RouteEvo 容器。正式测量窗口仍应避免模型推理、构建和其他重负载。

## 模型准备

本机 Ollama 0.33.3 已有 `qwen3.8:27b-mlx`：model ID `5642e97495e1`、Qwen 3.5 架构、27.8B 参数、NVFP4、18 GB、context 262144，支持 completion/tools/thinking；采集证据时未加载，也没有发送请求。

它只证明本地可行性。其运行时、量化和准确模型标识与计划中的托管 `Qwen3.8-27B` 不同，不能合并为同一反馈消融批次。本地 API 费用为 0，但机器运行成本尚未测量，不能写成总成本为 0。正式主批仍以 #2 冻结的托管模型、endpoint、凭据和价格快照为准；凭据不进入产物。

## 冻结任务包

上游固定 `oripress/AlgoTune@dff9914c10800c7a031c9e8c3d4d1c8cd1b38906`，两题都使用 `size=1000`、种子 1729 到 1748；前 5 个为 dev，后 15 个为 final。任务包全部文件哈希与 SQLite canonical manifest 已交叉核对。生成和哈希 final 属于环境准备，本阶段没有运行 final。

| 题目 | task_id | canonical manifest SHA256 |
| --- | --- | --- |
| convolve_1d | `algotune-convolve_1d-formal-20261114-82a6fac682` | `bc00cd13960442ea34b0bb08a152eb9a0b95ab1f23faa97b4f24252944febfd9` |
| pagerank | `algotune-pagerank-formal-20261114-b2ad8ba1c8` | `61ab8297dfa51ccce5c79a77bc7dafe074bb6fa41936f7065b4ccbbe024994f4` |

卷积 dev 的真实输入均为 float64 一维数组，shape 分别为 `[30000]` 与 `[8000]`，输出 shape `[37999]`；相对 L2 误差要求不超过 `1e-6`。PageRank dev 均为 1000 节点，有向边数为 7878 到 8074；checker 使用 `rtol=1e-5, atol=1e-8`，并校验有限、非负、长度和归一化。逐 dev 用例的 shape、dtype、边数、悬空节点和出度统计见 [worker-convolve_1d.json](evidence/worker-convolve_1d.json) 与 [worker-pagerank.json](evidence/worker-pagerank.json)。final 只公开 case 数与输入哈希，不公开逐例统计或输入正文。

## 预校准结果与未决问题

每题使用上游初始程序自比 3 轮；每轮按 default/pinned 或 pinned/default 交替，共 6 次自比。正控制把延迟加入 baseline，负控制把同一延迟加入 candidate。所有输出，包括预热输出，都由独立 judge 检查；选优规则固定为正确且 `max(candidate samples) < min(baseline samples)`。

| 题目 / 配置 | 自比 speedup（3 轮） | 自比误入选 | 样本极差/中位数的中位数 |
| --- | --- | ---: | ---: |
| convolve / default | 1.0202 / 0.9993 / 1.0029 | 0 | 7.39% |
| convolve / VM vCPU 2 | 1.0501 / 1.0033 / 1.1161 | 0 | 8.86% |
| pagerank / default | 0.9898 / 1.0265 / 1.0126 | 0 | 85.79% |
| pagerank / VM vCPU 2 | 1.0306 / 0.9333 / 1.0129 | 0 | 86.52% |

卷积 3 ms 正控制严格入选（11.8920×），负控制未入选（0.0838×）。PageRank 首次 3 ms 正控制虽有 1.7440× 中位加速，但区间重叠，按规则未入选；这次结果保留为控制强度不足。改用 20 ms 延迟后，正控制严格入选（5.6388×），负控制未入选（0.1683×）。两题 12 次自比均零误入选，但这只说明严格规则没有误选，不能消除下述计时问题。

校准时宿主 1 分钟 load average 约为 30 到 49，高于 16 个逻辑 CPU。PageRank 的第 3 个计时样本在 baseline/candidate、default/pinned 和所有用例中都系统性变慢，跨样本中位数约为其他位置的 1.86 倍；该周期性运行时效应的原因尚未证明。固定 VM vCPU 没有消除它，样本极差/中位数约 86%，会让正式批次对真实小收益几乎失去检出力。[timing-observation.json](evidence/timing-observation.json) 将当前校准标为未接受。

因此必须由 #2 冻结 timing harness 对该周期效应的处理；若 harness 变化，candidate image 与任务 manifest 都要重建。随后在安静窗口重跑 3 预热 / 5 计时和正反控制。正式 15 个 episode 保持串行，measurement window 不重叠。用户允许的并行仅用于只读分析和环境准备。

完整逐例时间、初始化时间、顺序、镜像、程序 SHA 和环境快照见 [calibration-convolve_1d.json](evidence/calibration-convolve_1d.json) 与 [calibration-pagerank.json](evidence/calibration-pagerank.json)。首次相对 VAR_DIR 失败和 PageRank 弱控制结果均原样保留。SQLite 共记录 24 条通过的 dev calibration evaluations；[ledger-audit.json](evidence/ledger-audit.json) 记录数据库完整性、外键、锁和容器清理结果。

## 待冻结的 15 项计划

[proposed-run-plan.json](proposed-run-plan.json) 包含完整 15 项提案：convolve_1d 的 feedback / independent / no_feedback 各 3 次，pagerank 的 feedback / independent 各 3 次。卷积三组按 F-N-I、N-I-F、I-F-N 轮换，任务与两组顺序交错；每题固定同一任务包、VM vCPU 与测量参数。

该文件仍是提案，状态明确等待公共 freeze 与计时重校准，`experiment_sha`、`prompt_hashes` 和 `price_snapshot` 为 null。公共 freeze 后应将中央计划映射覆盖进本地执行清单，不能用旧 feedback/independent 结果补本批，也不能先看 F/I 再决定 N。

## 复现与审计

首次准备应使用新的绝对 VAR_DIR；Docker bind mount 不接受此处的相对路径。下列命令记录本次预检参数。importer 会打印实际 task ID；若重建镜像得到不同 image ID，必须使用新输出的 task ID 和 manifest，不能沿用本批 ID 或哈希。

```bash
cd backend
uv sync --frozen --python 3.12.11
export ROUTEEVO_NO_DOTENV=1
export ROUTEEVO_VAR_DIR="$PWD/var-algotune-formal-20261114"

.venv/bin/routeevo tasks import-algotune convolve_1d \
  --split formal-20261114 --dev-cases 5 --final-cases 15 --size 1000 --seed 1729
.venv/bin/routeevo tasks import-algotune pagerank \
  --split formal-20261114 --dev-cases 5 --final-cases 15 --size 1000 --seed 1729

# 将下面两项替换为 importer 实际打印的 task_id。本批实际值仅用于复核现有 VAR_DIR。
CONVOLVE_TASK_ID=algotune-convolve_1d-formal-20261114-82a6fac682
PAGERANK_TASK_ID=algotune-pagerank-formal-20261114-b2ad8ba1c8

.venv/bin/python scripts/calibrate_native.py \
  --task-id "$CONVOLVE_TASK_ID" \
  --cpuset-cpus 2 --rounds 3 --repeats 5 --warmups 3 --control-delay-ms 3 \
  --output ../docs/research/native-formal-20261114/algotune/evidence/calibration-convolve_1d.json
.venv/bin/python scripts/calibrate_native.py \
  --task-id "$PAGERANK_TASK_ID" \
  --cpuset-cpus 2 --rounds 3 --repeats 5 --warmups 3 --control-delay-ms 20 \
  --output ../docs/research/native-formal-20261114/algotune/evidence/calibration-pagerank.json

cd ..
backend/.venv/bin/python docs/research/native-formal-20261114/algotune/capture_evidence.py \
  --var-dir backend/var-algotune-formal-20261114 \
  --convolve-task-id "$CONVOLVE_TASK_ID" --pagerank-task-id "$PAGERANK_TASK_ID"
python3 docs/research/native-formal-20261114/algotune/audit_artifacts.py
```

`SHA256SUMS` 覆盖本目录的公开交付。`audit_artifacts.py` 无需读取 sealed 输入即可核对 15 项矩阵、任务身份、镜像架构、校准矩阵、控制结果、VM affinity、SQLite 摘要、formal 0/15 和 model calls 0。
