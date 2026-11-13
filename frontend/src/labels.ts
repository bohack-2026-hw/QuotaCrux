// Chinese labels and tones for backend enums. Tone drives chip color; text always carries the meaning.

export type Tone = 'good' | 'bad' | 'warn' | 'neutral' | 'accent'

export const ACTION: Record<string, string> = {
  analyze: '分析', get_evidence: '取证', propose_candidate: '提出候选', run_validation: '验证',
  finish: '结束', upgrade_model: '升级模型', model_request: '模型请求', invalid: '无效回复',
}

const STATUS: Record<string, [string, Tone]> = {
  passed: ['通过', 'good'], done: ['完成', 'neutral'], submitted: ['已提交', 'neutral'], requested: ['已请求', 'neutral'],
  wrong_output: ['输出错误', 'bad'], format_error: ['格式错误', 'bad'], contract_violation: ['违反契约', 'bad'],
  runtime_error: ['运行错误', 'bad'], timeout: ['超时', 'bad'], memory_limit: ['内存超限', 'bad'], output_limit: ['输出超限', 'bad'],
  compile_error: ['编译错误', 'bad'], static_check_failed: ['静态检查失败', 'bad'], unstable: ['结果不稳定', 'bad'],
  sandbox_error: ['环境错误', 'warn'], baseline_failed: ['基线失败', 'warn'], invalid_action: ['无效动作', 'warn'],
  api_error: ['接口错误', 'warn'], unusable_reply: ['回复不可用', 'warn'], tool_failed: ['工具失败', 'warn'],
  running: ['运行中', 'accent'], completed: ['已完成', 'neutral'], stopped: ['已停止', 'warn'], failed: ['失败', 'bad'],
  interrupted: ['已中断', 'warn'],
}

export const status = (s: string | null | undefined): [string, Tone] => (s ? STATUS[s] ?? [s, 'neutral'] : ['—', 'neutral'])

export const STOP: Record<string, string> = {
  goal_reached: '目标达成', budget_exhausted: '预算耗尽', agent_finished: 'Agent 主动结束', user_stopped: '用户停止',
  model_api_error: '模型接口错误', environment_error: '环境错误', internal_error: '内部错误', process_interrupted: '进程中断',
}

export const OUTCOME: Record<string, [string, Tone, string]> = {
  success: ['成功', 'good', '✓'],
  no_gain: ['无收益', 'neutral', '–'],
  failure: ['失败', 'bad', '✕'],
}

export const BUCKET: Record<string, string> = {
  rows: '行数', distinct_keys: 'key 数', rows_per_key: '每 key 行数', order: '顺序', skew: '偏斜',
}

export const ORDER: Record<string, string> = {
  random: '随机', unsorted: '乱序', sorted: '有序', nearly_sorted: '几乎有序', clustered: '成簇', none: '无',
}

export const BUCKET_VALUE: Record<string, string> = { low: '低', high: '高', none: '无', ...ORDER }

const DECISION: [RegExp, string][] = [
  [/^continue$/, '继续'], [/^validate candidate$/, '验证候选'], [/^re-measure candidate$/, '重新测量'],
  [/^continue with feedback$/, '带着反馈继续'], [/^continue with large model$/, '改用大模型继续'],
  [/^upgrade to large model, continue$/, '升级到大模型并继续'], [/^retry with a new request if budget allows$/, '预算允许则重发请求'],
  [/^stop: (\w+)$/, '停止：$1'], [/^stop$/, '停止'],
]
export function decision(d: string): string {
  for (const [re, zh] of DECISION) {
    if (re.test(d)) return d.replace(re, zh).replace(/停止：(\w+)/, (_, k: string) => `停止：${STOP[k] ?? k}`)
  }
  return d
}

export const SPLIT: Record<string, string> = { A: 'A · 学习', B: 'B · 开发对照', C: 'C · 最终留出', smoke: '冒烟' }

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
