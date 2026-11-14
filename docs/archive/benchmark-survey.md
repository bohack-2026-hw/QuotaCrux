# 研究任务评测集调研

核查日期：2026-11-14。目标是展示单个研究任务内的“实验—反馈—修正—继续改进”；评测方法见[单任务评测方案](feedback-comparison-plan-v1.md)。本次读取上游文档、代码、数据目录和两个题目包的元数据，未运行这些 benchmark。

## 1. 选择结论

**研究主线优先 ALE-Bench，性能优化备选 AlgoTune；有 RTX 2080 Ti 后，KernelBench 也值得做小规模预检。** 这是基于任务结构、当前架构与可用资源的接入判断，尚无 RouteEvo 在这些 benchmark 上的效果结果。

| Benchmark | 核实规模 | 一项任务的研究内容与时长计算方式 | 资源与本项目适配 |
| --- | --- | --- | --- |
| [ALE-Bench](https://github.com/SakanaAI/ALE-Bench) | 当前发布数据 40 题，Lite 10 题；40 个压缩题目包合计约 99.3 MB | 在同一启发式优化问题上持续提高分数；源比赛为数小时至数周，研究预算可自行设定 | CPU + Docker + 原生裁判；最贴合持续优化，需把 speedup 单指标扩展到质量分数 |
| [AlgoTune](https://github.com/oripress/AlgoTune) | 当前固定代码版本 154 个任务目录 | 数学/科学计算函数保持数值正确并加速；配套 AlgoTuner 反复编辑、评测；当前配置以费用额度控制，非统一小时制 | 科学计算 Python 环境，选定任务可用 CPU；运行时间目标接近现有实现，但需改函数计时与依赖 |
| [KernelBench](https://github.com/ScalingIntelligence/KernelBench) | Level 1/2/3 共 250 题（100/100/50）；当前仓库另有 Level 4 | 对 PyTorch 程序编写更快的 GPU kernel，可用固定预算反复编译、验证、优化 | 需要实际 GPU 与兼容编译栈；2080 Ti 可作为小题预检目标，先确认软件与显存适配 |
| [MLE-bench](https://github.com/openai/mle-bench) | 75 个 Kaggle 竞赛；Lite 22 个；上游标注全量 3.3 TB、Lite 158 GB | 数据探索、特征、训练、验证、生成提交；推荐标准预算每项 24 小时 | 标准配置 36 vCPU、440 GB RAM、24 GB A10；单个小数据任务可缩减，但当前需新增完整训练工作区与产物管理 |
| [RE-Bench](https://github.com/METR/RE-Bench) | 7 个研究工程环境 | ML 调参与训练优化、GPU kernel、scaling law 等，评测研究能力随时间预算变化 | 多项涉及 GPU/训练环境；当前仓库已归档、README 标记 DEPRECATED，优先借鉴方法，降低新接入优先级 |

“长时”指整轮研究的时间。例如，每次测试限时 2 秒，算法改进过程仍可持续数小时。

## 2. ALE-Bench：优先接入的优化研究任务

作者的[研究介绍](https://sakana.ai/ale-bench/)明确将任务定位为长时、目标驱动的算法工程。任务来自 AtCoder Heuristic Contest，解可以都合法，但质量不同；有持续改进空间。

### 固定来源与数据规模

- 代码核查提交：[`8ba16e6baf743aa8736516c45d1c52afdbd4de99`](https://github.com/SakanaAI/ALE-Bench/tree/8ba16e6baf743aa8736516c45d1c52afdbd4de99)。
- 数据核查 revision：[`0f426173b4e4e73b09b2b3631ae0490f66b75f99`](https://huggingface.co/datasets/SakanaAI/ALE-Bench/tree/0f426173b4e4e73b09b2b3631ae0490f66b75f99)。按 [`problem_ids.txt`](https://huggingface.co/datasets/SakanaAI/ALE-Bench/blob/0f426173b4e4e73b09b2b3631ae0490f66b75f99/problem_ids.txt) 计数为 40 题；[`problem_ids_lite.txt`](https://huggingface.co/datasets/SakanaAI/ALE-Bench/blob/0f426173b4e4e73b09b2b3631ae0490f66b75f99/problem_ids_lite.txt) 为 10 题。
- 40 个 `.zip` 的文件元数据之和为 **99,332,896 bytes，99.3 MB / 94.7 MiB**。这是题目包压缩体积，不含 Docker 镜像、编译缓存和运行生成的测试输入。库支持按题下载。
- Lite 列表：`ahc008`、`ahc011`、`ahc015`、`ahc016`、`ahc024`、`ahc025`、`ahc026`、`ahc027`、`ahc039`、`ahc046`。
- 代码 Apache-2.0，数据 CC BY-ND 4.0，见上游 [README](https://github.com/SakanaAI/ALE-Bench/blob/8ba16e6baf743aa8736516c45d1c52afdbd4de99/README.md)。本次未把上游题目数据加入 Git。

### 建议的两个 CPU 任务

| 任务 | 为什么适合观察研究行为 | 本次核查信息 |
| --- | --- | --- |
| [`ahc026` Stack of Boxes](https://atcoder.jp/contests/ahc026/tasks/ahc026_a) | 在按序取出箱子的约束下减少搬运代价，可比较不同移动策略与局部搜索 | 非交互，得分越高越好；原比赛 4 小时，单例 2 秒 / 1024 MiB；包 113,228 bytes |
| [`ahc024` Topological Map](https://atcoder.jp/contests/ahc024/tasks/ahc024_a) | 保持区域连通与邻接关系同时压缩地图，可观察约束失败后的修正 | 非交互，得分越高越好；原比赛 4 小时，单例 2 秒 / 1024 MiB；包 131,248 bytes |

两个包的元数据均为 public 50 / public_lite 5 / private 150 / private_lite 150。**Lite 不保证最终评价用例更少**；按 150 个私有用例、每例接近 2 秒估算，单个最终候选的纯程序执行可能约 5 分钟，另有裁判开销。题目包虽小，仍要计入最终评价时间。

首个 pilot 可选 `ahc026`，仅使用 public 评价，保留 private 供正式对照。正式试验前冻结题目、公开/私有用例与语言；若 pilot 使用其全部私有结果指导配置，正式评测需另选留出，不能继续把同一私有集合称为完全未见。首轮优先 Python 语言，明确这是固定语言的本地实验；需要 C++ 时作为另一份冻结配置重新比较，不让两个实验组使用不同语言预算。

### 复用与改动

[上游评测代码](https://github.com/SakanaAI/ALE-Bench/blob/8ba16e6baf743aa8736516c45d1c52afdbd4de99/docs/evaluation.md)已有 repeated sampling 与 self-refinement，并提供 public/private evaluation；这与我们要验证的“利用反馈是否优于独立尝试”直接对应。上游按采样次数组织的对照，仍需改为 RouteEvo 统一预算后才能回答我们的成本问题。

RouteEvo 可复用任务冻结、候选记录、资源用量记录和结果导出。必须新增原生裁判调用、可行性/分数/优化方向、最佳候选规则和预算内持续优化；不能把得分装入 `speedup` 字段。最终种子、参考结果、排名映射与私有裁判状态留在可信评测侧，不把完整 session 对象暴露给候选或模型。

CPU 串行小规模运行即可预检；上游建议统一机器来比较性能。本地试验应报告实际机器与裁判版本，不直接套用另一台硬件的时间或排名结论。

## 3. AlgoTune：更接近现有的运行时间优化

核查提交：[`dff9914c10800c7a031c9e8c3d4d1c8cd1b38906`](https://github.com/oripress/AlgoTune/tree/dff9914c10800c7a031c9e8c3d4d1c8cd1b38906)。该版本 `AlgoTuneTasks/` 实际包含 **154 个任务目录**，README 同样写 154；不同论文版本的数量不混用。

[项目网站](https://algotune.io/)提供完整迭代轨迹和隐藏输入上的函数加速评价；[当前配置](https://github.com/oripress/AlgoTune/blob/dff9914c10800c7a031c9e8c3d4d1c8cd1b38906/AlgoTuner/config/config.yaml)为 `spend_limit: 1.0` 美元、train/test 各 100、开发计时 2 次、正式计时 10 次。1 美元是该版本的默认预算。

首批 CPU 候选：

- [`convolve_1d`](https://github.com/oripress/AlgoTune/blob/dff9914c10800c7a031c9e8c3d4d1c8cd1b38906/AlgoTuneTasks/convolve_1d/convolve_1d.py)：NumPy/SciPy 一维卷积，有数值误差约束，适合比较不同实现和规模下的算法选择。
- [`pagerank`](https://github.com/oripress/AlgoTune/blob/dff9914c10800c7a031c9e8c3d4d1c8cd1b38906/AlgoTuneTasks/pagerank/pagerank.py)：NetworkX/NumPy 图计算，验证分数归一性及参考容差，适合观察数据结构与计算路径改进。

它们没有 GPU 必需条件，但当前 RouteEvo 的标准库、1 GB 沙箱不适合直接照搬。上游配置给验证 worker 的内存上限为 14 GB；这不是每题最低需求，需按选定题目预检实际峰值。数据可按任务生成或加载，本次未核实全任务数据总大小，因此不报估算总量。

接入时保留上游的输入生成、数值验证和函数计时语义，固定 BLAS/线程配置；将安装、导入、编译与目标函数耗时分别记录。当前 EffiBench 的完整进程计时不可直接当作 AlgoTune 分数。上游汇总使用加速比调和平均，本地子集应同时列逐题结果并明确协议差异。

## 4. GPU 与完整 ML 研究备选

### KernelBench 与 RTX 2080 Ti

用户提供 `ssh desktop`。本次只读查询确认：RTX 2080 Ti，**11,264 MiB** 显存，驱动 `615.78.08`；查询时占用 211 MiB、GPU 利用率 1%，这是瞬时状态。默认 SSH 被本机系统配置文件权限阻断，使用 `ssh -F /home/hycx233/.ssh/config desktop` 可连接，未修改 SSH 配置。

远端为 Linux，GPU compute capability 为 7.5，存在 Docker 命令；默认 Python 为 3.14.9，未装 PyTorch，PATH 中未发现 `nvcc`。本次没有查遍其他虚拟环境，也未验证 Docker GPU 透传；需要单独准备兼容环境后才能执行 kernel 预检。

[KernelBench README](https://github.com/ScalingIntelligence/KernelBench)要求在实际目标 GPU 上运行和测量，提供 Level 1 单算子、Level 2 融合、Level 3 完整模型，另有 Level 4 扩展。当前 [pyproject](https://github.com/ScalingIntelligence/KernelBench/blob/main/pyproject.toml)指定 Python 3.10、PyTorch ≥ 2.9，GPU 依赖另含 Triton/CuPy 等；不能仅凭显卡可见就认定上游环境已兼容。

[当前 Triton 支持范围](https://github.com/triton-lang/triton#compatibility)要求 NVIDIA compute capability 8.0+，而这块 2080 Ti 是 7.5。因此首选预检 KernelBench 的 CUDA C++ 后端，不能默认采用当前 Triton 后端；兼容的 PyTorch/CUDA 构建仍需实际验证。

建议先选择一个显存可容纳的 Level 1 算子，检查目标架构的 PyTorch/CUDA 构建、编译器和校验器；随后才选少量 Level 2 融合任务。禁止把新一代 GPU 上的参考时间当作 2080 Ti 的基线；正确性、同步、预热与 CUDA 计时均由裁判完成。其长时研究协议需我们自己设定，不是上游已有的统一小时制。

### MLE-bench 与 RE-Bench

[MLE-bench README](https://github.com/openai/mle-bench#benchmarking)给出 75 题、24 小时和上述 A10 配置，Lite 为 22 题、158 GB。它与补充说明中的“围绕数据集反复改进分类方案”很贴近；小型任务例如 detecting-insults-in-social-commentary，上游数据表约 0.002 GB，可单独考虑。完整接入涉及训练目录、数据划分、模型文件和最终提交，不只是替换正确性 checker。2080 Ti 的存在不等于达到标准 24 GB A10 配置；缩减预算应单独报告。

[RE-Bench README](https://github.com/METR/RE-Bench)列出 7 项研究工程任务，并明确标为 DEPRECATED；GitHub 仓库 `archived=true`。其[研究报告介绍](https://metr.org/blog/2024-11-22-evaluating-r-d-capabilities-of-llms/)强调专家与 Agent 的时间预算比较，可借鉴预算曲线和成果评分。多次独立运行后取最好成绩的总算力，不能当成一轮研究 内持续学习的证据。

## 5. 本次完成范围

本调研阶段完成任务结构、规模、官方接口与主要资源要求的核实，以及评测协议调整。后续用户已授权接入前三项，`feat/research-benchmarks` 提供 ALE-Bench、AlgoTune、KernelBench 首批适配器；CPU 原生裁判已预检，GPU worker 实机测试后置。当前接入范围、运行命令与环境检查见[接入文档](../design/native-benchmarks.md)，主线实施状态见[评测方案](feedback-comparison-plan-v1.md#6-实现与验收状态)。
