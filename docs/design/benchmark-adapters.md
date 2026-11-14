# Benchmark 解耦与 EffiBench-X 接入

实现分支：`feat/effibench-x-adapter`；基线：`f8fbb3e`。本次把任务语义从研究执行循环中拆出，并加入 EffiBench-X 的 Python 导入入口。

## 1. 当前架构与边界

```mermaid
flowchart LR
    G[groupagg 生成器] --> A[任务适配器]
    E[固定版本 EffiBench-X Parquet] --> A
    A --> T[冻结任务包与 manifest]
    T --> R[Runner：预算、模型路由、候选与步骤]
    R --> V[通用运行时间评测器]
    V --> C[候选 Docker 沙箱]
    V --> J[适配器正确性校验]
    J --> D[EffiBench 独立校验沙箱]
    R --> M[按任务语义检索经验]
    R --> O[报告与研究记录]
```

| 边界 | 实现 | 负责内容 |
| --- | --- | --- |
| 任务包 | `taskpkg.py` | 文件哈希、不可变注册、加载与复现入口 |
| 题目适配器 | `benchmarks/groupagg.py`、`benchmarks/effibench.py` | 用例、正确性、公开规则、输入特征、经验兼容性、展示说明 |
| 通用评测 | `evaluator.py` | 每用例独立执行、预热、交替计时、结果状态与持久化 |
| 研究循环 | `agent/runner.py` | 预算、模型升级、提出/验证候选、冻结最佳产物、经验发布 |
| 任务上下文 | `agent/prompt.py` | 公共动作规则；题目特有约束来自适配器 |
| 报告和页面 | `report.py`、`research.py`、任务选择器 | 使用适配器的题名、输入规模和特点、基线与验证说明 |

两个任务族都是 CPU Python 程序优化，共用加速比、候选选择和停止规则。其他类型任务需提供自己的运行环境、指标和选择规则。

原有 groupagg 生成代码与 manifest 内容保留，A/B/C/D 的任务锁不变。七个公开规则用例和五维检索特征移入其适配器。评测器、提示词、检索与经验提取版本已更新，旧版本与新版本运行的配置指纹不同。

## 2. 数据集规模与固定来源

数据集：[EffiBench/effibench-x](https://huggingface.co/datasets/EffiBench/effibench-x)。固定 revision：`49babbec95f0897d5f06276aaf274f9f1dcd036b`。

| 项目 | 核实结果 |
| --- | --- |
| 题目数 | 623，全部带 Python 参考解 |
| 接口类型 | 285 个 `io`，338 个 `functional`；全部 functional 题带 Python runner |
| 来源 | Aizu 33、AtCoder 149、CodeChef 93、Codeforces 10、LeetCode 338 |
| 上游 split | 只有 `test`；RouteEvo 的 A/B/C/D 是本地实验划分 |
| 分片 | 20 个 Parquet，合计 **2,341,977,516 bytes**，约 **2.34 GB / 2.18 GiB** |
| 用例数 | 官方说明每题 100 个；导入时记录实际条数并去除重复输入 |

题目目录、分片大小和 SHA256 在 `backend/src/routeevo/benchmarks/effibench_catalog.json`。规模与 Python 覆盖通过读取全部 20 个分片的元数据和选定列核实；没有把 2.34 GB 数据放进 Git。部分题目的测试字符串很大，解压时所需内存可能明显高于压缩文件大小。

上游运行逻辑参考 [EffiBench-X `21b6668a`](https://github.com/EffiBench/EffiBench-X/tree/21b6668a49a342c843e679cc5ed16081064a5768)，相关许可证及修改说明见 [第三方说明](../../THIRD_PARTY_NOTICES.md)。

## 3. 接入协议

- **优化对象**：从数据集已有 Python 参考解开始。`io` 直接作为程序；`functional` 把参考解嵌入该题 Python runner，补入上游标准库导入项，成为完整 stdin/stdout 程序。候选继续提交完整程序。
- **支持范围**：Python 3.12 标准库、当前 20,000 字节代码上限和既有 Docker 资源限制。需要 `sortedcontainers` 等第三方库的题目明确拒绝，623 题的执行验证仍待完成。
- **数据划分**：同一输入重复出现时去重；若期望输出冲突则拒绝。按输入 SHA256 排序，默认前 20 个为 dev，其余为 final。`--case-limit` 可指定试接入子集，子集数量和原始用例 ID 写入 manifest。该划分是固定、可复现的工程选择，未按难度分层。
- **模型可见数据**：题目、初始程序、dev 概况和最多两个小型 dev 例子。候选容器只接收单个测试输入；final 数据和 checker 不进入模型上下文。
- **正确性**：使用数据集的 `evaluate`，调用顺序和文本归一化遵循上述上游版本实际代码，即 `evaluate(actual, expected)`，不根据函数形参名称猜测。checker 在单独的无网络、只读 Docker 沙箱执行；异常、超时或非法返回明确记作 `checker_error`，不写成候选失败经验。
- **性能**：每个 case 使用全新容器；一轮计时为该 suite 各用例运行时间之和，校验器执行时间不计入候选耗时。单轮累计 stdout 也受现有输出预算限制，避免多用例放大输出内存占用。基线和候选各预热一轮，交替运行 5 轮，用两组总时间的中位数之比作为 speedup；每个计时轮仍检查输出。全部候选轮快于全部基线轮且 speedup ≥ 1.10 才达标。
- **证据工具**：cProfile 使用第一个 dev case，反馈注明 case ID 和 dev 总数。
- **经验隔离**：EffiBench 的 problem、数据 revision、checker、runner、适配版本和 dev 输入划分共同组成兼容键。只检索/复验同一兼容键的经验，避免跨题误用完整解法，也避免改变 dev 划分后将已见输入带入新的 final。groupagg 保留原有跨输入规模和特点复用。

本实验优化已有参考程序，报告加速比。同题内可复用程序；跨题效果待测。

## 4. 使用方式

在仓库 `backend/` 下运行。保留 groupagg 任务锁时使用 Python **3.12.11**。

```bash
uv sync --extra benchmark --python 3.12.11

# 每题只下载所在分片，缓存到当前 ROUTEEVO_VAR_DIR/benchmarks/。
# 下列两题在同一个 7,321,349-byte 分片中，第二次导入可复用缓存。
uv run --extra benchmark routeevo tasks import-effibench codeforces/2104A \
  --split smoke --dev-cases 3 --case-limit 6
uv run --extra benchmark routeevo tasks import-effibench leetcode/3188 \
  --split smoke --dev-cases 3 --case-limit 6

uv run routeevo tasks list
uv run routeevo run ebx-codeforces-2104A-smoke-3-6 --mode eval --snapshot v0
uv run routeevo run ebx-leetcode-3188-smoke-3-6 --mode eval --snapshot v0
```

离线导入加 `--parquet /path/to/test-00009-of-00020.parquet`，仍然验证固定 SHA256。去掉 `--case-limit` 即导入该题全部去重后用例；`--split` 必须明确指定，只有 A/smoke 可发布学习经验。不要把用于正式留出的题目先放入学习 split；pilot 与正式评测应使用独立 `ROUTEEVO_VAR_DIR`。

一题有 100 个独立用例时，完整计时的容器启动次数较多：一个含 N 个用例的 suite，计时评测执行 12×N 次候选/基线程序，另有 12 次独立校验。预算检查仍在现有 Runner 的步骤边界进行；先用小子集测量每次实验成本，再决定正式批次和实际耗时预算。

首次运行先验证参考程序；参考程序或校验器出错时停止。

## 5. 验证记录

见 [EffiBench-X 试接入结果](../archive/effibench-pilot.md)，列出实际运行的题目、用例覆盖和检查结果。测试中的脚本模型只用于验证研究循环和报告链路。

研究评测按[正式研究协议 v2](../research/native-formal-20261114/protocol.md)推进，主线验证同一轮研究 利用反馈的效果。现有适配器和四题结果保留。ALE-Bench、AlgoTune、KernelBench 的首批子集已通过原生适配接口接入，分别提供原始分数、函数计时和 GPU worker；当前范围与命令见[研究任务 benchmark 接入](research-benchmarks.md)。`evaluator.evaluate` 按任务族选择原生执行器，Runner 继续复用预算、动作和记录链路。
