# EffiBench-X 试接入验证

日期：2026-11-14。实现提交：`c79dad6`；原始基线：`f8fbb3e`。数据与评测边界见 [适配方案](../design/benchmark-adapters.md)。

后续真实模型评测见 [四题子集结果](../research/effibench-x-20261114/README.md)：60/60 final 用例通过，2/4 题达标，含 token、费用和耗时。下文保留首次适配验证记录。

## 真实数据检查

使用固定 revision `49babbec95f0897d5f06276aaf274f9f1dcd036b` 的第 9 号分片（从 0 编号），7,321,349 bytes，SHA256：

```text
958c052cd9b3f61c70acd476bb3c75bf1e62f574dae5b43ba1e7fcde2aebacdc
```

实际通过下载入口获取并核对文件，随后导入两道题的全部用例。数据集原始参考程序在 RouteEvo Docker 沙箱执行，输出由原始 evaluator 在另一个隔离沙箱判定。

| 题目 | 接口 | 原始用例 | 去重后 | dev / final | 正确性结果 |
| --- | --- | ---: | ---: | --- | --- |
| Codeforces 2104A · Three Decks | io | 100 | 100 | 20 / 80 | 全部通过 |
| LeetCode 3188 · Find Champion I | functional | 100 | 92 | 20 / 72 | 全部通过 |

共检查 **192 个唯一输入**。LeetCode 题的 8 个重复输入没有跨 dev/final 分配。此次全用例检查只验证正确性，不计为优化成绩。

| task ID | dataset | evaluation ID | 用例数 | 评测总耗时 |
| --- | --- | --- | ---: | ---: |
| `ebx-codeforces-2104A-smoke-20-100` | dev | `3e0c5f12e795` | 20 | 8.899 s |
| 同上 | final | `1ab2edc43c21` | 80 | 27.567 s |
| `ebx-leetcode-3188-smoke-20-92` | dev | `6b28dd7befa9` | 20 | 6.513 s |
| 同上 | final | `04ae761eeb05` | 72 | 20.160 s |

耗时包含容器启动和校验，只用于估计批量检查成本。

## 研究循环检查

每题另外导入 6 个用例的 smoke 包（3 dev / 3 final）。脚本模型依次请求 cProfile、提交原始参考代码、结束运行；其余流程使用真实 Runner、Docker 评测器、持久化和报告构建。候选计时沿用默认 5 轮，未用伪造计时替代程序执行。

| task ID | run ID | 取证 / 候选 / 脚本请求 | 最终正确性 | 总耗时 |
| --- | --- | --- | --- | ---: |
| `ebx-codeforces-2104A-smoke-3-6` | `run-20261114T030141-2541` | 1 / 1 / 3 | 通过 | 12.859 s |
| `ebx-leetcode-3188-smoke-3-6` | `run-20261114T030154-24f4` | 1 / 1 / 3 | 通过 | 16.413 s |

两次都以 `agent_finished` 结束。使用空快照 `v0`、评测模式；没有真实模型请求或学习发布。提交与基线相同的程序是链路检查，不能据此声称模型带来性能提升。

## 回归与检查

- **18 个新增测试通过**：io/functional、Parquet 嵌套列真实读写、固定文件校验、不可变任务包、重复输入冲突、dev/final 隔离、跨题/跨 dev 划分经验隔离、逐例计时汇总、累计输出限制、checker 调用顺序与归一化、checker 异常和超时、错误停止与不发布经验、完整脚本循环及报告导出。
- **26 个原有测试分批通过**。其中复用测试初次和一次复测在不同计时断言上失败：一次中位加速比为 1.2735，但候选最慢样本 0.1825 s 超过基线最快 0.1784 s；另一次出现 0.3090 s 的候选样本，因此按既有规则不计改善。原基线 `f8fbb3e` 和当前分支随后分别隔离复测通过。测试断言与性能门槛均保留。这类实测断言对共享机器上的计时波动敏感。
- `smoke-01` 使用 Python 3.12.11 重新生成，manifest SHA256 与仓库锁一致：`a3495b448ad9184a530564da0a2f2440a022da1fc0f2173ec158d811c10db32f`。
- 前端 TypeScript/Vite 构建、oxlint、Python 编译、Git whitespace 检查通过。前端使用与原工作区相同的依赖副本；未改前端依赖版本。
- 可选 `pyarrow` 锁定为 26.0.1；原有依赖版本与镜像地址保留，锁文件检查通过。

共覆盖 44 个 pytest 测试，按受影响范围分批运行。未对 623 题做全量执行，也未运行真实 Qwen/GPT 的优化成绩评测。

## 本地产物与复现

以下产物留在当前分支工作区的忽略目录：

- `backend/var/effibench-pilot-results.json`：上述原始结果摘要。
- `backend/var/runs/<run_id>/report.json`：两次脚本研究运行的完整报告、步骤与计时。
- `backend/var/tasks/<task_id>/`：冻结输入、期望输出、checker、初始程序与 manifest。
- `backend/var/benchmarks/effibench-x/<revision>/`：经哈希验证的原始分片。

重新导入、运行和离线导入命令见 [使用方式](../design/benchmark-adapters.md#4-使用方式)。首次真实模型评测应固定题目级 A/B/C/D 划分、模型/路由配置和机器资源，再记录完成率、加速比、token、云端成本与墙钟时间；本次没有选择或承诺一个全量得分。
