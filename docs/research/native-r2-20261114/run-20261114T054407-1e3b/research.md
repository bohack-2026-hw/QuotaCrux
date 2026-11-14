# 研究记录 run-20261114T054407-1e3b

- 任务：algotune-convolve_1d-smoke-eeb3cd9d83；模式：feedback；模型：Qwen3.8-27B。
- 提示版本：agent-prompt-v5；经验快照：v0。
- 范围：开发集预实验；最终数据未评测。
- 停止原因：agent_finished。

## 保留结果

- 保留候选：[c3](candidates/c3.py)；开发用例通过 2/2；speedup = 1.8342501948017726；改善判定：True。
- 全部候选的最高原始 speedup：1.8342501948017726；候选：c3；改善判定：True。
- 原始 speedup 峰值与保留指标分别记录；保留方案须通过正确性及选择规则。

## 研究过程

| 步骤 | 执行者 | 动作 | 状态 | 目的或结果 |
|---|---|---|---|---|
| 1 | program | run_validation | passed | c0: 2/2 cases; metric=None; improved=None |
| 2 | model | analyze | done | 分析初始程序的性能瓶颈和优化方向，确定下一步实验策略 |
| 3 | model | propose_candidate | submitted | 用scipy.signal.fftconvolve替代signal.convolve，减少内部算法选择开销，直接走FFT路径 |
| 4 | program | run_validation | passed | c1: 2/2 cases; metric=1.1551488961638963; improved=False |
| 5 | model | analyze | done | 分析c1的结果，理解为什么median speedup为1.155但improved为false，并确定下一步优化方向 |
| 6 | model | propose_candidate | submitted | 用纯numpy FFT实现卷积，避免scipy.signal.fftconvolve的内部开销（参数验证、FFT大小选择逻辑等），直接控制FFT路径以进一步降低延迟 |
| 7 | program | run_validation | passed | c2: 2/2 cases; metric=0.8172208941506133; improved=False |
| 8 | model | analyze | done | 分析c2为什么比c1慢，确定下一步优化方向 |
| 9 | model | propose_candidate | submitted | 使用scipy.fftpack.next_fast_len选择最优FFT大小，然后用numpy.fft.rfft/irfft执行卷积，结合scipy的FFT大小优化和numpy的直接调用优势，避免scipy.signal.fftconvolve的额外开销 |
| 10 | program | run_validation | passed | c3: 2/2 cases; metric=1.8342501948017726; improved=True |
| 11 | model | analyze | done | 分析c3的成功原因和timing_spread，判断是否还有进一步优化空间 |
| 12 | model | propose_candidate | submitted | 尝试用scipy.fftpack.rfft/irfft替代numpy.fft.rfft/irfft，减少Python包装层开销，进一步降低FFT调用延迟 |
| 13 | program | run_validation | wrong_output | c4: 0/2 cases; metric=None; improved=None |
| 14 | model | analyze | done | 分析c4失败原因，确定下一步优化策略 |
| 15 | model | propose_candidate | submitted | 在c3基础上尝试in-place乘法（fa *= fb）避免创建中间数组fc，减少一次内存分配和拷贝开销 |
| 16 | program | run_validation | passed | c5: 2/2 cases; metric=1.432923570639249; improved=True |
| 17 | model | analyze | done | 分析c5结果与c3的对比，判断in-place操作为何反而更慢，并评估是否值得继续优化 |
| 18 | model | invalid | invalid_action | missing_field: field 'expected_result' is required |
| 19 | model | analyze | done | 分析当前状态，c3已是best_candidate且improved=true，评估是否值得继续优化或结束 |
| 20 | model | finish | done | c3已达成目标且improved=true，继续优化风险大于收益 |

## 假设与实验

假设为模型在候选提交前的解释，判定来自随后实际评测。

| 候选 | 假设或目的 | 预期 | 实测状态 | 判定 |
|---|---|---|---|---|
| c1 | scipy.signal.convolve内部会先判断是否使用FFT（比较n*m和FFT成本），对于大数组这个判断本身有微小开销；fftconvolve直接走FFT路径，可能略快 | 正确性通过，速度比c0有小幅提升（避免scipy.signal.convolve内部的参数检查和算法选择逻辑） | passed | refuted |
| c2 | scipy.signal.fftconvolve内部有额外的函数调用层和参数检查开销；直接用numpy.fft.rfft/irfft并手动选择合适FFT大小可以减少这些开销，使总时间更短且更稳定 | 候选时间应低于c1的median 0.00164s，理想情况下所有候选样本都低于baseline最小值0.00177s，从而满足improved条件 | passed | refuted |
| c3 | scipy.fftpack.next_fast_len(37999)会返回一个比65536小但能整除或接近的数（如49152=2^4*3^4），使FFT计算量显著降低；同时直接调用numpy.fft.rfft/irfft避免了scipy.signal.fftconvolve内部的参数检查和函数调用层开销 | 预期比c1（scipy.signal.fftconvolve）更快，因为next_fast_len可能选择比65536更小的FFT大小（如49152），减少计算量；同时直接调用numpy FFT避免了scipy.signal层的函数调用开销。目标median时间低于0.0014s，且所有候选样本都快于所有基线样本。 | passed | supported |
| c4 | numpy.fft.rfft内部会做额外的参数检查和数组处理，而scipy.fftpack.rfft更接近底层C实现，可能有更少的Python开销；但两者最终都调用相同的FFTW库，差异可能很小 | 如果scipy.fftpack直接调用比numpy.fft更快（减少一层Python函数调用），则candidate median可能从0.001024s降至约0.00095s或更低，speedup可能提升至约1.9-2.0 | wrong_output | untestable |
| c5 | fc = fa * fb会创建一个新数组并分配内存，而fa *= fb是原地操作，避免了额外的内存分配和可能的数据拷贝，对于大数组可能有微小的性能提升 | 如果成功，median时间可能从0.001024s进一步降低到约0.00095-0.0010s，speedup可能提升到1.9以上；如果数值精度出现问题则回退到c3 | passed | supported |

## 候选

| 候选 | 来源 | 父候选 | 开发验证 | 指标 | 改善 |
|---|---|---|---|---|---|
| [c0](candidates/c0.py) | initial | — | passed | — | False |
| [c1](candidates/c1.py) | model | c0 | passed | 1.1551488961638963 | False |
| [c2](candidates/c2.py) | model | c1 | passed | 0.8172208941506133 | False |
| [c3](candidates/c3.py) | model | c1 | passed | 1.8342501948017726 | True |
| [c4](candidates/c4.py) | model | c3 | wrong_output | — | False |
| [c5](candidates/c5.py) | model | c3 | passed | 1.432923570639249 | True |

## 资源

- 请求 14 次；候选 5 个，通过 4 个；AST 去重后 5 个。
- 时间：总计 141.833s；模型等待 121.457s；开发验证 20.234s。
- Token：输入 75331（含缓存 31232），输出 5692。
- 按冻结单价估算 ¥0.294297；输入 ¥3/百万 token、输出 ¥12/百万 token，缓存按普通输入价估算。

## 复现

```sh
uv run routeevo run algotune-convolve_1d-smoke-eeb3cd9d83 --mode eval --snapshot v0 --research-mode feedback --fixed-model small --dev-only --cpuset-cpus 2 --function-warmups 3 --wall-clock 900 --max-requests 20 --max-candidates 10 --request-timeout 120.0
```
