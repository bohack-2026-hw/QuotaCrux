// Chinese labels and tones for backend enums. Tone drives chip color; text always carries the meaning.

export type Tone = 'good' | 'bad' | 'warn' | 'neutral' | 'accent'

export const ACTION: Record<string, string> = {
  analyze: '分析', get_evidence: '取证', propose_candidate: '提出候选', run_validation: '验证',
  finish: '结束', upgrade_model: '升级模型', model_request: '模型请求', invalid: '无效回复',
  reuse_candidate: '复用已验证程序', set_target: '提高本次目标', route_model: '分流',
}

export const MODE: Record<string, string> = { eval: '评测', learn: '学习', online: '在线' }

export const FAMILY: Record<string, string> = { groupagg: '分组聚合', logstats: '访问日志统计', intervals: '区间合并' }

/** How a run got its model: re-use delivered before any request, or the router's reason for the starting model. */
export const ROUTE: Record<string, [string, Tone]> = {
  reuse: ['复用直接交付', 'good'],
  familiar: ['相近经验 → 本地小模型', 'neutral'],
  new_family: ['全新任务族 → 大模型', 'accent'],
  new_conditions: ['新条件 → 大模型', 'warn'],
  router_off: ['分流关闭 → 小模型', 'neutral'],
  no_model_request: ['未请求模型', 'neutral'],
}

const STATUS: Record<string, [string, Tone]> = {
  passed: ['通过', 'good'], done: ['完成', 'neutral'], submitted: ['已提交', 'neutral'], requested: ['已请求', 'neutral'],
  wrong_output: ['输出错误', 'bad'], format_error: ['格式错误', 'bad'], contract_violation: ['违反契约', 'bad'],
  runtime_error: ['运行错误', 'bad'], timeout: ['超时', 'bad'], memory_limit: ['内存超限', 'bad'], output_limit: ['输出超限', 'bad'],
  compile_error: ['编译错误', 'bad'], static_check_failed: ['静态检查失败', 'bad'], unstable: ['结果不稳定', 'bad'],
  sandbox_error: ['环境错误', 'warn'], checker_error: ['校验器错误', 'warn'], baseline_failed: ['基线失败', 'warn'], invalid_action: ['无效动作', 'warn'],
  api_error: ['接口错误', 'warn'], unusable_reply: ['回复不可用', 'warn'], tool_failed: ['工具失败', 'warn'],
  running: ['运行中', 'accent'], completed: ['已完成', 'neutral'], stopped: ['已停止', 'warn'], failed: ['失败', 'bad'],
  interrupted: ['已中断', 'warn'],
}

export const status = (s: string | null | undefined): [string, Tone] => (s ? STATUS[s] ?? [s, 'neutral'] : ['—', 'neutral'])

export const STOP: Record<string, string> = {
  goal_reached: '开发数据达标', budget_exhausted: '预算耗尽', agent_finished: 'Agent 主动结束', user_stopped: '用户停止',
  model_api_error: '模型接口错误', environment_error: '环境错误', internal_error: '内部错误', process_interrupted: '进程中断',
}

export const OUTCOME: Record<string, [string, Tone, string]> = {
  success: ['成功', 'good', '✓'],
  no_gain: ['无收益', 'neutral', '–'],
  failure: ['失败', 'bad', '✕'],
}

export const BUCKET: Record<string, string> = {
  rows: '行数', distinct_keys: 'key 数', rows_per_key: '每 key 行数', order: '顺序', skew: '偏斜',
  groups: '分组数', rows_per_group: '每组行数', errors: '错误率',
  intervals_per_merged: '每段合并数', magnitude: '数值大小', sign: '符号',
}

export const ORDER: Record<string, string> = {
  random: '随机', unsorted: '乱序', sorted: '有序', nearly_sorted: '几乎有序', clustered: '成簇', none: '无',
  time_sorted: '按时间有序', has_negative: '含负数', non_negative: '非负', empty: '空',
}

export const BUCKET_VALUE: Record<string, string> = { low: '低', high: '高', none: '无', ...ORDER }

const DECISION: [RegExp, string][] = [
  [/^continue$/, '继续'], [/^validate candidate$/, '验证候选'], [/^re-measure candidate$/, '重新测量'],
  [/^continue with feedback$/, '带着反馈继续'], [/^continue with large model$/, '改用大模型继续'],
  [/^upgrade to large model, continue$/, '升级到大模型并继续'], [/^retry with a new request if budget allows$/, '预算允许则重发请求'],
  [/^upgrade rule met but no model requests left$/, '满足升级条件，但模型请求已用完'],
  [/^validate re-used program$/, '复验'], [/^validate next re-used program$/, '复验下一个'], [/^re-use finished$/, '复用复验结束'],
  [/^continue with the model to beat the best known program$/, '交给模型，尝试超越已知最佳'],
  [/^start model requests on the small model$/, '先用本地小模型'], [/^start model requests on the large model$/, '直接用大模型'],
  [/^stop: (\w+)$/, '停止：$1'], [/^stop$/, '停止'],
]
export function decision(d: string): string {
  for (const [re, zh] of DECISION) {
    if (re.test(d)) return d.replace(re, zh).replace(/停止：(\w+)/, (_, k: string) => `停止：${STOP[k] ?? k}`)
  }
  return d
}

export const SPLIT: Record<string, string> = {
  A: 'A · 学习', B: 'B · 开发对照', C: 'C · 最终留出', D: 'D · 封存留出', S: 'S · 封存任务流', T: 'T · 新任务族调优', smoke: '冒烟',
}

export const fmt = {
  x: (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(2)}×`),
  n: (v: number | null | undefined) => (v == null ? '未知' : v.toLocaleString('en-US')),
  usd: (v: number | null | undefined) => (v == null ? '未知' : `$${v < 0.01 && v > 0 ? v.toFixed(4) : v.toFixed(3)}`),
  s: (v: number | null | undefined) => (v == null ? '—' : v >= 100 ? `${Math.round(v)}s` : `${v.toFixed(1)}s`),
  pct: (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)}%`),
  time: (iso: string) => new Date(iso).toLocaleTimeString('zh-CN', { hour12: false }),
  rows: (v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${Math.round(v / 1e3)}k` : String(v)),
}

export const roleName = (role: string | undefined, model?: string) =>
  role === 'large' ? `GPT${model ? ` · ${model}` : ''}` : role === 'small' ? `Qwen${model ? ` · ${model}` : ''}` : role ?? ''

/** Program stop details are short English facts; render the common shapes in Chinese, keep anything else verbatim. */
export function stopDetail(d: string): string {
  const line = d.split('\n')[0]
  let m = line.match(/^(c\d+) dev speedup ([\d.]+) >= ([\d.]+)$/)
  if (m) return `${m[1]} 开发数据加速比 ${m[2]}× ≥ 目标 ${m[3]}×`
  m = line.match(/^re-used (c\d+) dev speedup ([\d.]+) >= ([\d.]+); no model request needed$/)
  if (m) return `复用的 ${m[1]} 开发数据加速比 ${m[2]}× ≥ 目标 ${m[3]}×，无需调用模型`
  m = line.match(/^(candidates|model_requests|tokens): used (\d+)\/(\d+)$/)
  if (m) return `${({ candidates: '候选', model_requests: '模型请求', tokens: 'Token' } as Record<string, string>)[m[1]]}已用完（${m[2]}/${m[3]}）`
  m = line.match(/^wall_clock: ([\d.]+)s left/)
  if (m) return `循环时长只剩 ${m[1]} 秒，不足以发起新请求`
  return line
}
