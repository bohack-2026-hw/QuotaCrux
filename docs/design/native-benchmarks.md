# ALE、AlgoTune 与 KernelBench 接入

分支：`feat/research-benchmarks`，基于 `feat/effibench-x-adapter@19ce8db`。
正式评测按[研究协议 v2](../research/native-formal-20261114/protocol.md)执行；早期双组设计见[归档方案](../archive/feedback-comparison-plan-v1.md)。

首轮 ALE-Bench / AlgoTune 真实开发预实验已完成，见[结果与完整轨迹](../research/native-20261114/README.md)。本批使用 v4 提示；之后补齐筛选规则与动作 JSON 示例的 v5 提示单独记录，未混入旧结果。

第二轮补齐实际任务概况、保留任务内分析，并完成 CPU 计时校准后，已执行固定 Qwen 的真实对照。AlgoTune feedback / independent 的保留开发加速分别为 1.8343× / 1.2101×；ALE independent 得分从 17,753 提高到 18,230，feedback 保持基线。完整指标、成本、过程曲线和冻结配置见[第二轮报告](../research/native-r2-20261114/README.md)。两轮均未评测最终集。

## 已接入范围

| Benchmark | 当前支持题目 | 原生评价 | 执行环境 |
| --- | --- | --- | --- |
| ALE-Bench | `ahc026`、`ahc024`，均为 batch 题 | 上游 Rust `vis` 校验可行性并计算原始分数；按用例求和，越高越好 | 本机 CPU；候选 Python，裁判独立容器 |
| AlgoTune | `convolve_1d`、`pagerank` | 上游 `is_solution` 数值校验；初始 `solve` / 候选 `solve` 的函数加速比 | 本机 CPU，NumPy / SciPy / NetworkX |
| KernelBench | Level 1 `1_Square_matrix_multiplication_` | 参考张量对照、CUDA events 计时 | 独立 GPU worker；面向 desktop 的 RTX 2080 Ti |

目前接入上表中的题目。ALE 报告原始得分；AlgoTune 和 KernelBench 按下述方法计时。下载数据和运行产物保存在 `backend/var/`（或 `QUOTACRUX_VAR_DIR`）。

固定来源：

- [ALE-Bench 数据](https://huggingface.co/datasets/SakanaAI/ALE-Bench/tree/0f426173b4e4e73b09b2b3631ae0490f66b75f99)：`0f426173b4e4e73b09b2b3631ae0490f66b75f99`。
- [AlgoTune](https://github.com/oripress/AlgoTune/tree/dff9914c10800c7a031c9e8c3d4d1c8cd1b38906)：`dff9914c10800c7a031c9e8c3d4d1c8cd1b38906`。
- [KernelBench](https://github.com/ScalingIntelligence/KernelBench/tree/129232ea3c4cfa05c2dd5473bdb935d6246dc84b)：`129232ea3c4cfa05c2dd5473bdb935d6246dc84b`；方阵乘参考文件另验 Git blob SHA1。

任务包固定来源哈希、开发/最终用例、初始代码、依赖镜像 ID、接口和目标。导入相同任务 ID 时仍走既有不可变注册检查。修改尺寸、种子、镜像或题目后生成新任务包。

## 先运行 CPU 子集

从 `backend/` 执行，依赖 Docker，首次导入需要下载源码、生成用例并构建镜像。准备阶段不计入研究预算。

```bash
uv sync --python 3.12.11

# 首轮小样本：2 个开发用例，3 个封存最终用例。
uv run quotacrux tasks import-ale-bench ahc026 --split smoke --dev-cases 2 --final-cases 3
uv run quotacrux tasks import-algotune convolve_1d --split smoke --dev-cases 2 --final-cases 3 --size 1000
uv run quotacrux tasks list

# 用导入输出的任务 ID 替换占位符。两题合计 4 个 episode，串行交替组别顺序。
uv run quotacrux research-compare ALE_TASK_ID ALGOTUNE_TASK_ID \
  --repeats 1 --wall-clock 900 --max-requests 20 --max-candidates 10 \
  --fixed-model small --dev-only

# 单个 episode 也可独立启动。
uv run quotacrux run TASK_ID --research-mode feedback --fixed-model small \
  --wall-clock 900 --max-requests 20 --max-candidates 10 --dev-only
```

另一题分别改为 `ahc024` / `pagerank`。ALE 默认取 5 个公开开发种子、150 个私有最终种子；AlgoTune 默认 5 / 15 个用例，`--size` 默认 1000，`--seed` 默认 1729。AlgoTune 各题的 `size` 语义由原始生成器决定。

`--dev-only` 保留最终集封存。正式实验去掉该参数，循环结束后只评测已冻结的最佳候选，不将最终结果传回模型。正式批次另建运行目录，先冻结选题、模型和预算，再做多次完整研究。

## 研究循环与报告

- `feedback`：从空快照 `v0` 开始，可以看到本次研究的候选、验证反馈和步骤；持续优化，不因达到 `1.10×` 而提前停止。
- `independent`：每次请求只看到任务、初始方案和剩余预算；仅提交以 `c0` 为父候选的新方案或结束，不展示其他尝试的代码、反馈或最佳得分。两组的原生 benchmark 都通过提交候选获取评价，没有 cProfile 工具。
- 两组固定同一生成模型，关闭自动升级，不发布跨任务经验。`research-compare` 只允许模式和相应提示词哈希不同，检查其余配置、任务哈希与环境一致，按题目及重复编号交替执行顺序。
- 请求、候选、实际耗时任一预算耗尽即停止；主动结束和错误仍如实保留。开发评价尽量按剩余时间限制超时，容器启动和清理可能有余量；预算之后完成的候选不进入产物选择。
- ALE 选择已通过开发验证且原始分数最高的候选；性能题保留现有严格噪声门槛（全部候选计时样本快于全部基线样本）。没有改善时交付初始方案。
- `report.json` 保存每次验证后的最佳结果、完成时间、累计请求、Token 与费用记录。`progress` 可按实际完成时间重建预算内的阶梯曲线，不将晚完成候选倒填到早期检查点。

```bash
uv run quotacrux report RUN_ID --json
uv run quotacrux export-run RUN_ID --bundle ../artifacts/RUN_ID
```

成对结果写入 `var/comparisons/research-*.json`，各轮研究 的完整报告、候选和请求仍按既有目录存储。控制台的比较结果给出文件路径。美元费用未知时维持 `null`；使用其他币种的服务需按该批冻结价目表单独报告估算，不记为零。

## 各裁判的边界

ALE 使用数据集内的原始 `gen` / `vis`，Cargo.lock 锁定 Rust 依赖。初始程序是 QuotaCrux 提供的简单可行方案：`ahc024` 输出原图，`ahc026` 按顺序移除箱子并把遮挡箱移到较短栈。得分与上述初始程序比较。候选沿用 1 CPU、1 GiB、无网络、只读容器；单用例时间上限取题目约束与运行配置较小者。裁判在独立镜像内运行，候选容器没有裁判文件、期望答案或最终套件。

AlgoTune 固定 NumPy 2.5.4、SciPy 1.18.1、NetworkX 3.7，单线程。仅移除上游 Task 注册器/基类和装饰器，保留这两题的生成、参考解和校验方法；初始程序提取 `solve` 及初始化代码。输入以 JSON + 数值数组 base64 传递，不使用 pickle。校验器额外拒绝 NaN/Inf 和错误数组形状。

每个用例分别运行初始/候选容器，交替先后顺序；一次预热、五次函数计时，每次重建候选 globals 和输入。计时只覆盖 `solve`，导入、输入编码、容器启动和独立校验计入 整轮研究耗时。预热和每个计时结果均由独立容器验证；五轮各自累加所有用例的函数耗时，再取中位数计算加速比。

## KernelBench GPU worker

本次提供接入代码与固定任务导入入口；GPU 实机评价安排在 CPU 两项之后。2080 Ti 的 compute capability 为 7.5，本入口支持 PyTorch / CUDA C++ `load_inline`。固定使用上游 4096×4096 float32 方阵，每个张量约 64 MiB。

2026-11-14 远端检查：2080 Ti，11264 MiB，驱动 615.78.08；Docker 仅登记 runc，GPU runtime 待配置。此机 SSH 需显式使用 `-F /home/hycx233/.ssh/config`，避开系统配置 include 的权限错误。以下示例的 ssh/scp 和 worker-command 在该环境中也需加上 `-F`。

部署到 `desktop` 的独立目录（下面以 `/home/USER/quotacrux-kernel-worker` 为例）：

```bash
# 从仓库根目录复制 worker、harness、checker 与 Dockerfile。
ssh desktop 'mkdir -p ~/quotacrux-kernel-worker'
scp backend/src/quotacrux/benchmarks/native_tools/kernel_*.py \
    backend/src/quotacrux/benchmarks/native_tools/Kernelbench.Dockerfile desktop:quotacrux-kernel-worker/
ssh desktop 'cd ~/quotacrux-kernel-worker && docker build -f Kernelbench.Dockerfile -t quotacrux-kernel:cu126 .'
ssh desktop 'docker image inspect quotacrux-kernel:cu126 --format "{{.Id}}"'

cd backend
uv run quotacrux tasks import-kernelbench 1_Square_matrix_multiplication_ --split smoke \
  --dev-cases 2 --final-cases 5 --image sha256:IMAGE_ID \
  --worker-command '["ssh","-o","BatchMode=yes","desktop","python3","/home/USER/quotacrux-kernel-worker/kernel_worker.py"]'
```

worker 需要 Docker GPU runtime；镜像固定 PyTorch 2.8.0 / CUDA 12.6 / NumPy 2.2.6，实际执行使用不可变镜像 ID。导入和运行时核对 GPU 型号、驱动和镜像环境。

每个种子的参考与候选在不同 GPU 容器运行，候选仅获得公共参考源码中的输入工厂与当前种子。所有结果保存为非 pickle 的 `.npy` 数组，再由无 GPU 的独立容器检查形状、有限数值和 `atol=rtol=1e-4`。输出文件须为普通文件，禁止借助符号链接访问参考结果。CUDA events 在同步后计时，禁用 TF32；编译、初始化、拷贝与校验计入研究耗时。当前只支持单个 float32 输出张量，未实现完整多级题库。

第三方许可与来源见[第三方说明](../../THIRD_PARTY_NOTICES.md)。
