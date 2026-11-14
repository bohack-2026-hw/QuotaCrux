# EffiBench-X 四题真实模型评测

2026-11-14，在 `feat/effibench-x-adapter` 的 `6297c0b87b7d6eb4b3247d1880e7a97b05ff3d7d` 上运行。**4/4 题最终正确，60/60 个 final 用例通过；2/4 题达到加速目标；包含保留初始程序的两题，几何平均加速比为 1.5585×。** 这轮从已有正确参考程序开始做优化，正确率不是从零解题的 pass@1。

四次研究运行合计 **507.532 秒（8 分 27.532 秒）**。Qwen 额度消耗 **¥0.0980028**；OpenAI 已知用量估算 **$0.123553**，另有一次连接超时没有返回用量，保留为未知。

## 结果

每题固定 5 个 dev、15 个 final 用例，只执行一轮真实研究运行。最终数据不回流给模型。

| 题目（数据集 ID） | 最终正确 | 交付 / 加速比 | 总耗时 | Qwen / GPT 请求数 | Qwen 额度消耗 CNY | GPT 已知估算 USD |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Three Decks (`codeforces/2104A`) | 15/15 | c0 · 1.0000× | 194.992 s | 2 / 3 | 0.0265830 | 0.080546 |
| Permutation Warm-Up (`codeforces/2108A`) | 15/15 | c0 · 1.0000× | 142.715 s | 3 / 3 | 0.0323208 | 0.043007 + 1 次未知 |
| Find Champion I (`leetcode/3188`) | 15/15 | c1 · **2.5159×** | 73.741 s | 1 / 0 | 0.0154620 | 0 |
| Maximum Strong Pair XOR I (`leetcode/3193`) | 15/15 | c1 · **2.3452×** | 96.084 s | 1 / 0 | 0.0236370 | 0 |

`c0` 表示保留初始程序；1× 是相对于自身的定义值，最终只复核正确性，没有把重复计时噪声当成收益。两个 c1 的最终计时均满足“候选最慢轮仍快于基线最快轮”且中位加速比 ≥ 1.10。

| 最终性能测量（每轮为 15 个用例之和） | 基线中位 | 候选中位 | 基线范围 | 候选范围 |
| --- | ---: | ---: | --- | --- |
| `leetcode/3188` | 1.752463 s | 0.696546 s | 1.710704–1.948214 s | 0.667868–1.013895 s |
| `leetcode/3193` | 1.856788 s | 0.791733 s | 1.737934–2.066745 s | 0.703162–1.215407 s |

9 个模型候选全部通过 dev 正确性验证。第一题用完 4 个候选预算，第二题用完 6 次请求预算；两题都没有稳定改善。后两题均由 Qwen 的第一次提交达标，没有升级到 GPT。共 13 次模型请求：12 次成功、1 次连接超时；没有格式不可用回复或非法动作。

## 固定配置与选样

- 数据：`EffiBench/effibench-x`，revision `49babbec95f0897d5f06276aaf274f9f1dcd036b`；上游 runner/checker 版本及接入边界见[适配方案](../../benchmark-adapters.md)。
- 选样在模型调用前写入 [issue #1](https://github.com/bohack-2026-hw/RouteEvo/issues/1#issuecomment-6870725713)：从已缓存的同一分片选两道 io、两道 functional 题，覆盖不同程序结构；没有根据运行成绩更换题目。这是小规模方便样本，没有做难度分层。
- 原始分片 `data/test-00009-of-00020.parquet`，7,321,349 bytes，SHA256 `958c052cd9b3f61c70acd476bb3c75bf1e62f574dae5b43ba1e7fcde2aebacdc`。
- 每题输入先去重，再按输入 SHA256 排序，前 5 个作 dev、后 15 个作 final；完整用例 ID、文件哈希和来源在 [plan.json](plan.json)。`leetcode/3188` 的 100 个原始用例有 92 个唯一输入，其余三题均为 100 个。
- RouteEvo split 为 `B`，`eval` 模式，空经验快照 `v0`。B 是本地实验标记，上游只有 test split；本轮不发布学习经验。
- 小模型：AIPing `Qwen3.8-27B`，`enable_thinking=false`，`json_object`，最多 8192 output tokens；大模型：OpenAI `gpt-6.1-sol`，`reasoning_effort=xhigh`，最多 32000 output tokens。
- 使用 `upgrade-rule-v2`：从小模型开始，连续两个候选未达目标或小模型连续三次请求未达目标后升级。提示词为 `agent-prompt-v3`；完整配置与哈希在 [results.json](results.json)。没有接入同时迭代中的 Decisions 或 `feat/shared-core` 新首选模型规则。
- 每题最多 6 次模型请求、4 个候选、300 秒研究循环；单次请求上限 120 秒（连接超时 10 秒）、单次程序测量上限 10 秒。最终评测位于研究循环之后，包含在上表总耗时中。四题都没有超过循环预算。
- Python 3.12.11；Docker 29.9.3 linux/amd64；CPU 为 Intel Core Ultra X7 358H，16 个逻辑 CPU，未绑核。每个沙箱限制 1 CPU、1 GiB、64 PIDs，无网络、只读根文件系统。镜像 ID 为 `sha256:4b9d5900ff655d52acfeb025b28622f610463c4d6cf32e6bc0ae87f9af903d33`。

本地 agent 已协调串行 Docker 运行，并在余额对账窗口暂停同一个 Qwen key 的调用。结束后立即释放窗口。远端协作通过 issue #1 同步；运行时冻结代码，不在批次中途合并另一分支。

## 正确性、时间与费用口径

在任何模型调用前，四题参考解的 20 个入选用例全部通过预检，共 **80/80**，耗时 **19.202 秒**。这部分不计入模型优化成绩和上表研究耗时。

正确性由数据集原始 checker 在独立沙箱判定。性能先预热基线与候选，再交替计时 5 轮，取 suite 总时间中位数之比；程序计时从沙箱 ready 后发送输入到收到完整输出，容器准备与 checker 不计入该加速比。研究墙钟时间包含这些开销。

批次从 `2026-11-14T03:13:13.840Z` 到 `03:21:44.422Z`，共 510.582 秒，其中各 run 合计 507.532 秒，其余是配置、容器环境查询与余额查询间隔。模型等待共 280.231 秒。原始 5 轮计时、每个候选的 dev 结果与运行 ID 均保存在 [results.json](results.json)。

| 模型 | 请求 | 已返回 input tokens | 已返回 output tokens | 模型等待 |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.8-27B | 7 | 22,486 | 3,211 | 82.808 s |
| gpt-6.1-sol | 6（含 1 次超时） | 18,668 | 7,689 | 197.423 s |

Qwen 的 [models API 快照](qwen-price.json) 给出的未折扣输入/输出标准价为 ¥3/¥12 每百万 tokens；按全部输入原价估算为 ¥0.105990。本轮第二题返回了 3,328 个缓存命中输入 tokens，[缓存计费规则](https://aiping.cn/docs/Features/cached-prompt-discount) 允许这些输入单独按折扣价计费。实际采用每题前后 [余额 API](https://aiping.cn/docs/API/balance-query) 的差值，共 ¥0.0980028，四题间的余额变化均为 0。本轮扣减均来自赠送额度，充值余额没有变化。账户余额差不是逐请求账单；绝对余额仅保存在本地私有文件。

OpenAI 按[官方标准价](https://developers.openai.com/api/docs/models/gpt-6.1-sol)估算：输入 $2、缓存输入 $0.10、缓存写入 $2.50、输出 $10，每百万 tokens。计算使用实际返回的缓存写入数量，推理 tokens 已包含在 output 中。第二题一次请求发生 `ConnectTimeout`，实际等待 10.013 秒，没有 request ID 或 usage；它占用一个请求预算，其费用保留未知，没有按零计费。表中的 $0.123553 是其余调用的已知估算小计。人民币和美元分别列账；本地机器费用未折算。

## 这轮能够说明什么

当前链路已经能真实运行两种题目接口，执行小模型到大模型的升级、隐藏 final 验收和费用记录。四题交付正确，但只有两题取得有效优化；整体几何平均包含两个 1×，避免只汇总成功题。

两道 Codeforces 初始程序本身很短，候选主要修改解析和输出，没有形成稳定优势。两道 functional 题的优化都精简了输入处理、函数调用或循环，也移除了通用 prelude 导入；**加速比相对于导入后的完整参考程序，包含 runner/prelude 成本**。这轮没有单独分离算法与包装开销的贡献。原始候选代码保存在 [best/](best/)，没有为展示而再编辑。

这是 RouteEvo 的参考程序优化子集结果，不是 EffiBench-X 官方代码生成和综合效率排名。4 题、每题一次运行、15 个 final 用例足以检查接入与量级，不能推断 623 题的总体成绩。下一批适合预先按来源、接口和参考程序运行量级分层，加入运行更重的题目，并对相同冻结子集比较路由版本。

## 文件与复现

- [results.json](results.json)：冻结配置、数据来源、预检摘要、逐调用 token/费用状态、原始计时、候选结果和汇总；无凭据或绝对余额。
- [plan.json](plan.json)：固定题目、用例 ID 和文件 SHA256。
- [best/](best/)：四份最终交付代码（包括两份 c0）；其 SHA256 与报告一致。参考代码来源和许可见[第三方说明](../../../THIRD_PARTY_NOTICES.md)。
- [run_subset.py](run_subset.py)：本次实际使用的批次驱动；preflight 无模型调用，run 阶段调用真实模型，已有 runs 的目录会拒绝重复付费执行。
- [reproduce.sh](reproduce.sh)：导入相同冻结任务并复核四份交付程序，不调用模型。先协调 Docker 计时窗口，再从仓库中运行 `bash docs/research/effibench-x-20261114/reproduce.sh`。

重跑真实模型批次时，在上述代码版本及 Python 3.12.11 下，先配置 `backend/.env` 为本报告的模型参数，再执行：

```bash
cd backend
uv sync --extra benchmark --python 3.12.11
export ROUTEEVO_VAR_DIR="$PWD/var/effibench-x-real-repeat"
report_dir="../docs/research/effibench-x-20261114"
for problem in codeforces/2104A codeforces/2108A leetcode/3188 leetcode/3193; do
  uv run --extra benchmark routeevo tasks import-effibench "$problem" --split B --dev-cases 5 --case-limit 20
done
cp "$report_dir/plan.json" "$ROUTEEVO_VAR_DIR/plan.json"
uv run python "$report_dir/run_subset.py" preflight --env-file .env --pricing-snapshot "$report_dir/qwen-price.json"
uv run python "$report_dir/run_subset.py" run --env-file .env --pricing-snapshot "$report_dir/qwen-price.json"
```

该驱动按当前 `.env` 读取真实服务；Qwen 余额接口针对本次的 AIPing。`qwen-price.json` 是本次历史价表，未来重跑需重新查询价格，模型回复和实测时间也会变化。本次原始调用、完整 run 报告、SQLite、冻结任务和私有余额记录另外保留在本地忽略目录 `backend/var/effibench-real-20261114/`。

## 本次验证

8 项 actions/pricing 测试通过；80 个参考样例预检通过；4 次真实运行完成，9 个模型候选通过 dev，60 个 final 样例通过。公开文件中的 token/cost 汇总已与原始账本核对，OpenAI 已知费用按返回缓存字段逐次复算；最终代码 SHA256 已与运行记录核对。报告与复现脚本通过 JSON、Python/Bash 语法和 Git whitespace 检查；`best/` 中的模型代码按原始字节保存，保留生成时的行尾空格以保证哈希一致。前一轮的适配器与原有回归验证见[试接入记录](../../effibench-pilot.md)。
