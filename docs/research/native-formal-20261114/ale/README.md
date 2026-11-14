# ALE 正式批次：环境与无模型校准

2026-11-14，负责人 hycx233，执行机 desktop。关联 [ALE #3](https://github.com/bohack-2026-hw/RouteEvo/issues/3)、[公共协议 #2](https://github.com/bohack-2026-hw/RouteEvo/issues/2)。

**状态：环境、任务包、参考程序和两路校准已完成；正式 15 轮为 0/15。** 本目录的分数全部来自 dev 校准。SQLite 核验正式研究 runs=0、模型调用=0、final 评测=0，因此本阶段 API 消耗为 0。尚待 #2 发布实现完整三组协议的唯一冻结 SHA、提示哈希、中央运行计划、并发口径与价格快照。

## 已准备的环境

- 校准源码固定 `a67850f3db224a9243f59703d25397ede3d54aa7`。独立分支 `bench/ale-formal-v1`，未修改公共 runner/prompt/research_compare/report/API。
- desktop 根目录 `/home/hycx233/routeevo-ale-formal-20261114`，代码位于 `repo/`，Git HEAD 已核验为上述 SHA。
- 隔离 CPython 3.12.11、uv 0.13.7，依赖按仓库 `uv.lock` 以 `uv sync --frozen --python 3.12.11` 安装。宿主 Python 不承担正式执行。
- i7-8700K，6 核 / 12 线程，约 47 GiB 内存；Docker 29.9.3，linux/amd64。镜像完成时可用磁盘约 23.24 GiB。
- Worker A：ahc024，候选 CPU 2，SMT 同胞 CPU 8；Worker B：ahc026，候选 CPU 4，同胞 CPU 10。容器内 affinity 探针分别返回 `[2]` / `[4]`。
- 保持既有 governor=`powersave`、EPP=`balance_performance`。候选使用 1 CPU、1 GiB、64 PIDs、无网络、只读根文件系统；每用例题目上限 2 秒。
- 两个 worker 各有独立 `var-worker-a` / `var-worker-b`、SQLite、`run.lock`、`compare.lock`。校准期间两个锁均持有，结束后确认释放；当前没有运行中的 QuotaCrux 容器。
- 现有 Qwen 配置通过 SSH 写入远端忽略的 `backend/.env`，权限 0600。公开配置为 Qwen3.8-27B / AIPing、thinking=false、max_output_tokens=8192、response_format=json_object。尚未以模型请求验证服务，也未领取正式价格快照；最终配置由 #2 冻结。

完整硬件、镜像和限制见 [host.json](evidence/host.json)、[worker A](evidence/worker-a.json)、[worker B](evidence/worker-b.json)。Docker 本地构建镜像没有 registry RepoDigest；下列值为实际不可变 image ID，不将 tag 当 digest。

| 镜像 | image ID |
| --- | --- |
| candidate | `sha256:adcc187ce2ca1745a7956ca4f2546e9ff984110733a4d03ee44233ef157436fb` |
| ahc024 judge | `sha256:ee44715bc32a6abd30a73f69c850912f10aa07ec8a476b62cb745a8ce708805a` |
| ahc026 judge | `sha256:6fa4bb666ea4b6fc05ec17820f09d9e14c7f1f1d1f9bef2bfddf7ac8d993da76` |

## 任务与封存

原生来源固定 `SakanaAI/ALE-Bench@0f426173b4e4e73b09b2b3631ae0490f66b75f99`，按现有 importer 取 `seeds.public` 前 5 个和 `seeds.private` 前 15 个，生成器检查两组不重叠。不是旧两用例 smoke 包，也不将该选取声称为 `public_lite` 集合。

| 题目 | task_id | manifest SHA256 |
| --- | --- | --- |
| ahc024 | `ale-bench-ahc024-formal-20261114-d052b16d54` | `1be26f2a809875d8fee65fc5ca8aa3a46955a467516c0946cc6d938802b8e6ef` |
| ahc026 | `ale-bench-ahc026-formal-20261114-66cd5cc2e0` | `a89676c4da2b451c55af5ef3db9a164d44f3db6edd3c1ea5dcfad2fcb44b3ba0` |

任务首先在 `var-prepare` 导入，再使用 `register_package()` 同时登记目标 worker 的文件和 SQLite manifest。结束时逐文件复核 SHA256、SQLite integrity/foreign-key 检查通过。任务文件保留在远端隔离目录，不在本目录发布输入正文。

生成并哈希 final 文件属于准备；本阶段没有执行 final 程序。之后必须先完成研究、冻结 dev 最优候选，再做 final，final 不参与重选。ALE 每候选对每个用例执行一次；`MeasureConfig.repeats=5` 不改变 ALE 的这一行为，不能把 5 个不同 dev 用例描述成五次计时重复。

## 校准结果

固定两类合法程序：c0；在 c0 前增加 1200 万次确定性整数运算的 CPU 控制程序。代码字节和 SHA 保存在 [programs](evidence/programs/)。每题、每程序、每执行条件各 3 次；条件次序为 S/P、P/S、S/P。同一次评测的五个样本是五个 dev 用例。

24 次顶层调用全部通过。CPU 控制程序与 c0 字节不同，现有 ALE evaluator 会额外执行 c0 reference，共产生 **36 条 SQLite dev 评测**，全部 passed；其中 12 条为额外参考评测。控制程序整套 `duration_s` 包含额外 c0 开销，候选 `samples` 不包含该参考开销。

| Worker / 程序 | 串行候选中位耗时 | 双路候选中位耗时 | 双路 / 串行 | 双路最慢用例 | 每次 5 dev 总分 | 超时 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A / c0 | 0.03463 s | 0.04237 s | 1.2236 | 0.04593 s | 5 | 0 |
| A / CPU 控制 | 1.26449 s | 1.27017 s | 1.0045 | 1.28390 s | 5 | 0 |
| B / c0 | 0.03504 s | 0.04275 s | 1.2201 | 0.04734 s | 44,120 | 0 |
| B / CPU 控制 | 1.26333 s | 1.26729 s | 1.0031 | 1.33798 s | 44,120 | 0 |

表中中位数汇总 3 次 × 5 个用例。按 repeat 配对，CPU 控制程序 A 的双路/串行比为 1.0099 / 1.0052 / 1.0031，B 为 1.0023 / 1.0240 / 1.0002。短小 c0 的相对开销约 22%，绝对增量约 7.7 ms；固定 CPU 工作量整体中位开销小于 0.5%，单次配对最高为 2.4%。

六个串行成对 batch 累计 60.832 秒，对应双路累计 29.570 秒，比例 48.61%。这是校准批次墙钟变化，不是算法加速比，也不是正式 15 轮的完成时间预测。逐 batch 时间保留于 [calibration.log](evidence/calibration.log)。

本次只证明候选 affinity 已设置，未配置核心排他使用。原生 judge 仍只有 `--cpus 1`，没有 cpuset；CPU 8 / 10 在整个校准窗口观测到约 4.29% / 4.41% busy，不能称为完全空闲。原始汇总的 `candidate_cpu_isolation=true` 在本批只表示候选绑核；以 [audit.json](evidence/audit.json) 的 `candidate_affinity_verified=true`、`candidate_core_exclusive=false`、`judge_affinity_configured=false` 为完整口径。

控制程序始终输出 c0 方案，分数一致说明合法性和执行链保持正常，并未测量限时搜索的迭代数或搜索质量。结合耗时、超时和资源结果，**建议向 #2 提议固定两路执行**；由公共负责人明确接受当前 judge 调度条件，或提供绑核修订后做相应校准，再统一冻结。

## 待冻结的 15 项计划

[proposed-run-plan.json](proposed-run-plan.json) 是提案，实验 SHA、提示哈希、价格快照保持未设置。每题全程固定同一个 worker/core，不删改公平性审计中的 affinity 字段。

| wave | A / ahc024 | B / ahc026 |
| --- | --- | --- |
| 1 | r1 feedback | r1 feedback |
| 2 | r1 independent | r1 no_feedback |
| 3 | r2 independent | r1 independent |
| 4 | r2 feedback | r2 no_feedback |
| 5 | r3 feedback | r2 independent |
| 6 | r3 independent | r2 feedback |
| 7 | — | r3 independent |
| 8 | — | r3 feedback |
| 9 | — | r3 no_feedback |

前六个 wave 各启动两个独立 worker，双方结束后进入下一 wave；后面三项串行。ahc024 的每组各与 ahc026 三种模式搭配一次；ahc026 每种模式各有两项处于双路 wave、一项处于串行 wave。wave 间等待在 episode 预算外，不修改单个研究循环的预算规则；实际模型/评测重叠时间照实记录。desktop 每 worker 最多一个在途请求、合计最多两个的提案也需要 #2 协调服务限流。

公共冻结仍需覆盖 no_feedback 的完整输入隔离、final 异常状态、执行入口/中央计划映射、统一模型/价格及提示/源码 SHA。本分片不以旧的两组实现先跑 F/I，再追加 N。

## 复现和审计

本地独立 checkout 的产物核验：

```bash
python docs/research/native-formal-20261114/ale/audit_artifacts.py
git diff --check
```

首次环境准备从冻结源码建立独立目录，先安装隔离 uv / Python；执行机需有可用 Docker。以下为本次实际参数，重做校准应选择新的根目录以保留旧账本：

```bash
ALE_ROOT=/home/hycx233/routeevo-ale-formal-20261114
cd "$ALE_ROOT/repo/backend"
UV_PYTHON_INSTALL_DIR="$ALE_ROOT/python" UV_CACHE_DIR="$ALE_ROOT/cache" \
  "$ALE_ROOT/bin/uv" sync --frozen --python 3.12.11

QUOTACRUX_NO_DOTENV=1 QUOTACRUX_VAR_DIR="$ALE_ROOT/var-prepare" \
  .venv/bin/python -c 'from quotacrux.sandbox.executor import ensure_image; print(ensure_image())'
for problem in ahc024 ahc026; do
  QUOTACRUX_NO_DOTENV=1 QUOTACRUX_VAR_DIR="$ALE_ROOT/var-prepare" \
    .venv/bin/quotacrux tasks import-ale-bench "$problem" \
    --split formal-20261114 --dev-cases 5 --final-cases 15
done
for worker in a b; do
  QUOTACRUX_NO_DOTENV=1 QUOTACRUX_VAR_DIR="$ALE_ROOT/var-worker-$worker" \
    .venv/bin/python "$ALE_ROOT/preflight.py" prepare --root "$ALE_ROOT" --worker "$worker"
done
QUOTACRUX_NO_DOTENV=1 .venv/bin/python -u "$ALE_ROOT/preflight.py" \
  calibrate --root "$ALE_ROOT" > "$ALE_ROOT/evidence/calibration.log" 2>&1
.venv/bin/python "$ALE_ROOT/ledger_audit.py" --root "$ALE_ROOT"
```

先将本目录的 `preflight.py` / `ledger_audit.py` / `host_evidence.py` 复制到 `ALE_ROOT`。`host_evidence.py --root "$ALE_ROOT"` 登记硬件、uv.lock 和镜像信息。构建涉及 apt/rust 工具链，重建时 image ID 可能变化；应登记新 ID 与新任务 manifest，不能沿用本次任务 hash。

[ledger-audit.json](evidence/ledger-audit.json) 提供 DB 实测计数、所有包文件哈希和锁释放检查；[audit_artifacts.py](audit_artifacts.py) 核对 24 个结果的完整矩阵、逐候选 SHA、dev hash、分数一致性和 36 条落盘记录的计数，再生成配对时间、CPU 和批次汇总。`SHA256SUMS` 覆盖本目录交付文件。未运行全仓测试；本次未修改生产执行代码。
