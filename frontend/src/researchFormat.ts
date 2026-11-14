// Plain-text formatting for research results, shared by the research components (kept out of component files).
import { FAMILY_TITLE, RUN_STATE, STOP, fmt } from './labels'
import type { RRun, RTask } from './research'
import { median, total } from './research'

/** Score and speedup keep their own units; a speedup carries four decimals as the reports do. */
export function metricText(metric: string, v: number | null | undefined): string {
  if (v == null) return '—'
  return metric === 'score' ? `${fmt.n(v)} 分` : `${v.toFixed(4)}×`
}

export function metricName(metric: string) {
  return metric === 'score' ? '原始得分' : '加速比'
}

export function deltaText(task: RTask, v: number | null): string | null {
  if (v == null || task.baseline == null) return null
  if (task.metric === 'score') {
    const d = v - task.baseline
    const pct = task.baseline ? (d / Math.abs(task.baseline)) * 100 : null
    return `${d >= 0 ? '+' : ''}${fmt.n(d)}${pct != null ? `（${d >= 0 ? '+' : ''}${pct.toFixed(2)}%）` : ''}`
  }
  return null
}

export function sumText(vs: (number | null)[], f: (v: number) => string) {
  const t = total(vs)
  return t.value == null ? '未知' : `${f(t.value)}${t.partial ? '（部分未知）' : ''}`
}

export function familyName(f: string) {
  return FAMILY_TITLE[f] ?? f
}

export function stopText(r: RRun): string {
  if (r.state === 'planned') return '尚未开始'
  if (r.state === 'running') return '研究中'
  return STOP[r.stopReason ?? ''] ?? r.stopReason ?? RUN_STATE[r.state]?.[0] ?? r.state
}

export interface ModeSummary { mode: string; value: number | null; runs: number; ended: number; improved: number; pending: boolean }

/** One mode on one task: median development result across repeats and how many repeats beat the baseline. */
export function modeSummary(task: RTask, mode: string): ModeSummary {
  const runs = task.runs.filter((r) => r.mode === mode)
  const vals = runs.map((r) => r.dev.value).filter((v): v is number => v != null)
  const ended = runs.filter((r) => r.state !== 'planned' && r.state !== 'running').length
  return {
    mode, value: median(vals), runs: runs.length, ended,
    improved: runs.filter((r) => r.dev.improved && !r.dev.initial).length,
    pending: runs.length > 0 && ended === 0 && vals.length === 0,
  }
}

/** Short big-number form: "1.8343" + "×", or "18,230" + "分". */
export function bigNumber(metric: string, v: number | null): [string, string] {
  if (v == null) return ['—', '']
  return metric === 'score' ? [fmt.n(v), '分'] : [v.toFixed(4), '×']
}

/** One sentence per task in plain words; never claims a lead the numbers do not show. */
export function taskVerdict(task: RTask, label: (m: string) => string): { text: string; lead: string | null } {
  const s = task.modes.map((m) => modeSummary(task, m)).filter((x) => x.value != null)
  if (!s.length) return { text: '还没有可比较的结果', lead: null }
  const better = (a: number, b: number) => (task.direction === 'minimize' ? a < b : a > b)
  const sorted = [...s].sort((a, b) => (better(a.value!, b.value!) ? -1 : better(b.value!, a.value!) ? 1 : 0))
  const top = sorted[0]
  const improvedAny = s.some((x) => x.improved > 0)
  if (!improvedAny) return { text: '各组都没有超过基线', lead: null }
  if (sorted.length > 1 && sorted[1].value === top.value) return { text: '各组结果持平', lead: null }
  const others = sorted.slice(1).map((x) => `${label(x.mode)} ${metricText(task.metric, x.value)}`).join('，')
  const d = deltaText(task, top.value)
  return { text: `${label(top.mode)}领先：${metricText(task.metric, top.value)}${d ? `，比基线 ${d}` : ''}${others ? `；${others}` : ''}`, lead: top.mode }
}

/** The improvement a room should see, in the task's own unit; null when nothing beat the baseline. */
export function gainOf(task: RTask, v: number | null): { big: string; unit: string; detail: string } | null {
  if (v == null || task.baseline == null) return null
  if (task.metric === 'score') {
    const d = v - task.baseline
    if (d <= 0) return null
    const pct = task.baseline ? (d / Math.abs(task.baseline)) * 100 : null
    return { big: pct != null ? `+${pct.toFixed(2)}` : `+${fmt.n(d)}`, unit: pct != null ? '%' : '分', detail: `+${fmt.n(d)} 分` }
  }
  if (v <= 1) return null
  return { big: v.toFixed(2), unit: '×', detail: `提速 ${v.toFixed(2)}×` }
}

/** The single best result of a task across modes, with its mode. */
export function bestOf(task: RTask): { mode: string; value: number } | null {
  let best: { mode: string; value: number } | null = null
  for (const m of task.modes) {
    const s = modeSummary(task, m)
    if (s.value == null || s.improved === 0) continue
    if (!best || (task.direction === 'minimize' ? s.value < best.value : s.value > best.value)) best = { mode: m, value: s.value }
  }
  return best
}
