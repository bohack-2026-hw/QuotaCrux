// Plain-text formatting for research results, shared by the research components (kept out of component files).
import { FAMILY_TITLE, RUN_STATE, STOP, fmt } from './labels.ts'
import type { RRun, RTask } from './research.ts'
import { median, total } from './research.ts'

/** Score and speedup keep their own units; a speedup carries four decimals as the reports do. */
export function metricText(metric: string, v: number | null | undefined): string {
  if (v == null) return '—'
  return metric === 'score' ? `${fmt.n(v)} 分` : `${v.toFixed(4)}×`
}

export function metricName(metric: string) {
  return metric === 'score' ? '原始得分' : '加速比'
}

/** The baseline the scoreboard compares against: the final-set c0 for final results, else the dev baseline. */
export function baseOf(task: RTask): number | null {
  return task.source === 'final' ? task.finalBaseline : task.baseline
}

/** One run's reported result: its final value when the task reports finals (failed or missing finals stay null). */
export function resultOf(task: RTask, r: RRun): { value: number | null; improved: boolean; initial: boolean } {
  if (task.source !== 'final') return { value: r.dev.value, improved: !!r.dev.improved && !r.dev.initial, initial: r.dev.initial }
  const value = r.final.state === 'passed' ? r.final.value : null
  const base = baseOf(task)
  const improved = value != null && base != null && (task.direction === 'minimize' ? value < base : value > base)
  return { value, improved, initial: r.dev.initial }
}

export function deltaText(task: RTask, v: number | null, base: number | null = task.baseline): string | null {
  if (v == null || base == null) return null
  if (task.metric === 'score') {
    const d = v - base
    const pct = base ? (d / Math.abs(base)) * 100 : null
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
  const results = runs.map((r) => resultOf(task, r))
  const vals = results.map((x) => x.value).filter((v): v is number => v != null)
  const ended = runs.filter((r) => r.state !== 'planned' && r.state !== 'running').length
  return {
    mode, value: median(vals), runs: runs.length, ended,
    improved: results.filter((x) => x.improved).length,
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
  const base = baseOf(task)
  const improvedAny = s.some((x) => x.value != null && base != null && (task.direction === 'minimize' ? x.value < base : x.value > base))
  if (!improvedAny) return { text: '各组都没有超过基线', lead: null }
  if (sorted.length > 1 && sorted[1].value === top.value) return { text: '各组结果持平', lead: null }
  const others = sorted.slice(1).map((x) => `${label(x.mode)} ${metricText(task.metric, x.value)}`).join('，')
  const d = deltaText(task, top.value, base)
  return { text: `${label(top.mode)}领先：${metricText(task.metric, top.value)}${d ? `，比基线 ${d}` : ''}${others ? `；${others}` : ''}`, lead: top.mode }
}

/** The improvement a room should see, in the task's own unit; null when nothing beat the baseline. */
export function gainOf(task: RTask, v: number | null): { big: string; unit: string; detail: string } | null {
  const base = baseOf(task)
  if (v == null || base == null) return null
  if (task.metric === 'score') {
    const d = v - base
    if (d <= 0) return null
    const pct = base ? (d / Math.abs(base)) * 100 : null
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
    const base = baseOf(task)
    if (s.value == null || base == null || !(task.direction === 'minimize' ? s.value < base : s.value > base)) continue
    if (!best || (task.direction === 'minimize' ? s.value < best.value : s.value > best.value)) best = { mode: m, value: s.value }
  }
  return best
}
