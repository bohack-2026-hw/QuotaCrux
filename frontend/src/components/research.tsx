import { useState } from 'react'
import type { ReactNode } from 'react'
import { useWidth } from '../hooks'
import { FINAL, RUN_STATE, fmt, money, rmode } from '../labels'
import type { Cost, RBatch, RRun, RTask } from '../research'
import { costTotals, fairLabel } from '../research'
import { bigNumber, deltaText, metricName, metricText, modeSummary } from '../researchFormat'
import { REPO_BLOB } from '../researchData'
import { Chip } from './ui'

/* ---------- small parts shared by the overview and the research view ---------- */

export function ModeMark({ mode, size = 10 }: { mode: string; size?: number }) {
  const m = rmode(mode)
  return <svg width={size} height={size} viewBox="0 0 10 10" aria-hidden style={{ flex: '0 0 auto' }}><Shape shape={m.shape} x={5} y={5} r={4.2} fill={m.color} /></svg>
}

export function ModeTag({ mode, repeat }: { mode: string; repeat?: number }) {
  const m = rmode(mode)
  return (
    <span className="mode-tag" title={m.desc}>
      <ModeMark mode={mode} />{m.label}<span className="mono muted">{mode}</span>{repeat != null && <span className="mono muted">r{repeat}</span>}
    </span>
  )
}

function Shape({ shape, x, y, r, fill, stroke }: { shape: string; x: number; y: number; r: number; fill: string; stroke?: string }) {
  const common = { fill, stroke: stroke ?? 'var(--card)', strokeWidth: stroke ? 2 : 1.5 }
  if (shape === 'square') return <rect x={x - r * 0.9} y={y - r * 0.9} width={r * 1.8} height={r * 1.8} rx={1.5} {...common} />
  if (shape === 'triangle') return <path d={`M${x},${y - r * 1.1} L${x + r},${y + r * 0.8} L${x - r},${y + r * 0.8} Z`} {...common} />
  return <circle cx={x} cy={y} r={r} {...common} />
}

export function FinalChip({ run }: { run: RRun }) {
  const [label, tone, icon] = FINAL[run.final.state] ?? [run.final.state, 'neutral', '']
  return <Chip tone={tone} icon={icon}>{label}</Chip>
}

export function RunStateChip({ run }: { run: RRun }) {
  const [label, tone] = RUN_STATE[run.state] ?? [run.state, 'neutral']
  return <Chip tone={tone} icon={run.state === 'running' ? '●' : undefined}>{label}</Chip>
}

export function FairChip({ b }: { b: RBatch }) {
  const f = fairLabel(b.fair, b.running)
  return <Chip tone={f.tone} icon={f.icon}>{f.text}</Chip>
}

export function CostText({ c }: { c: Cost }) {
  if (c.kind === 'none') return <span className="muted">无 API 费用</span>
  if (c.amount == null) return <span className="muted">未知</span>
  return <span title={c.note ?? undefined}>{money(c.amount, c.currency)}{c.kind === 'estimate' && <span className="muted small"> 估</span>}</span>
}

export function CostTotal({ costs }: { costs: Cost[] }) {
  const t = costTotals(costs)
  const parts = Object.entries(t.byCurrency).map(([cur, v]) => money(v, cur))
  if (!parts.length) return <>未知</>
  return <>{parts.join(' + ')}{t.kinds.has('estimate') ? ' 估' : ''}{t.unknown ? `（另 ${t.unknown} 轮未知）` : ''}</>
}

export function RunLink({ run, onOpenRun, archive }: { run: RRun; onOpenRun?: (id: string) => void; archive: boolean }) {
  if (!run.runId) return <span className="muted">—</span>
  if (archive) return run.record ? <a className="link" href={REPO_BLOB + run.record} target="_blank" rel="noreferrer">研究记录</a> : <span className="mono small">{run.runId}</span>
  return <button className="link" onClick={() => onOpenRun?.(run.runId!)}>查看运行</button>
}

export function BatchFacts({ b }: { b: RBatch }) {
  const L = b.limits, M = b.measure, P = b.pricing
  const items: [string, ReactNode][] = [
    ['模型', b.model?.name ? `${b.model.name}${b.model.hosted == null ? '' : b.model.hosted ? ' · 托管' : ' · 本地'} · 固定，不升级` : b.model?.role ? `固定 ${b.model.role} 角色（模型名未记录）` : '未记录'],
    ['对照组', b.modes.map((m) => rmode(m).label).join(' / ')],
    ['预算上限（每轮）', L ? `${L.wall_clock_s ?? '?'} 秒 · ${L.max_model_requests ?? '?'} 次请求 · ${L.max_candidates ?? '?'} 个候选` : '未记录'],
    ['计时', M ? `${M.function_warmups ?? '?'} 次预热 · ${M.repeats ?? '?'} 次计时${M.cpuset_cpus ? ` · CPU ${M.cpuset_cpus}` : ''}` : '未记录'],
    ['最终集', b.finalEnabled === false ? '未启用：本批只有开发集结果' : b.finalEnabled ? '启用：研究结束、冻结候选后评测' : '未记录'],
    ['费用依据', P ? `${P.currency} 标价估算：输入 ${P.input} / 输出 ${P.output}${P.cached_input != null && P.cached_input !== P.input ? ` / 缓存 ${P.cached_input}` : '（缓存按普通输入计）'} ${P.unit ? `· ${P.unit.replace('per 1M tokens', '每百万 Token')}` : ''}；非账单` : '无价格快照：费用按记录显示，缺失即未知'],
    ['冻结版本', [b.codeCommit ? `代码 ${b.codeCommit.slice(0, 7)}` : null, b.promptVersion ? `提示 ${b.promptVersion}` : null, b.protocol ? `协议 ${b.protocol}` : null].filter(Boolean).join(' · ') || '未记录'],
  ]
  return <dl className="facts">{items.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
}

/* ---------- best-so-far curve ---------- */

export type Axis = 'time' | 'tokens' | 'cost'
const AXIS: Record<Axis, string> = { time: '墙钟', tokens: 'Token', cost: '估算费用' }

/** Best development result so far, one step line per run, against wall clock, tokens or estimated cost. The value only
    changes when the selector keeps a new candidate; the line ends where the run ended. */
export function ProgressChart({ task, axis, currency, height = 240 }: { task: RTask; axis: Axis; currency: string | null; height?: number }) {
  const [box, W] = useWidth<HTMLDivElement>(640)
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const xOf = (p: { t: number; tokens: number | null; cost: number | null }) => (axis === 'time' ? p.t : axis === 'tokens' ? p.tokens : p.cost)
  const endOf = (r: RRun) => (axis === 'time' ? r.wallS : axis === 'tokens' ? r.tokens : r.cost.amount)
  const series = task.runs.filter((r) => r.progress.length).map((r) => {
    const pts = r.progress.map((p) => ({ x: xOf(p), y: p.value, p })).filter((p): p is { x: number; y: number; p: typeof p.p } => p.x != null && p.y != null)
    const end = endOf(r)
    return { r, pts, end: end != null && pts.length && end > pts[pts.length - 1].x ? end : null }
  }).filter((s) => s.pts.length)
  if (!series.length) return <p className="small muted">{axis === 'cost' ? '缺少价格快照或 Token 记录，无法按费用作图。' : '还没有可作图的进度点。'}</p>

  const xs = series.flatMap((s) => [...s.pts.map((p) => p.x), s.end ?? 0])
  const ys = series.flatMap((s) => s.pts.map((p) => p.y)).concat(task.baseline != null ? [task.baseline] : [], task.minSpeedup != null ? [task.minSpeedup] : [])
  let lo = Math.min(...ys), hi = Math.max(...ys)
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.12
  lo -= pad; hi += pad
  const xMax = Math.max(...xs) * 1.02 || 1
  const left = task.metric === 'score' ? 62 : 50, right = 64, top = 14, bottom = 30
  const H = height
  const x = (v: number) => left + (v / xMax) * (W - left - right)
  const y = (v: number) => top + (1 - (v - lo) / (hi - lo)) * (H - top - bottom)
  const yTicks = niceTicks(lo, hi, 4)
  const xTicks = niceTicks(0, xMax, W < 420 ? 3 : 5).filter((t) => t >= 0 && t <= xMax)
  const xFmt = (v: number) => (axis === 'time' ? `${Math.round(v)}s` : axis === 'tokens' ? fmt.rows(v) : money(v, currency).replace(/(\.\d{2})\d+/, '$1'))
  const yFmt = (v: number) => (task.metric === 'score' ? fmt.n(v) : `${v.toFixed(2)}×`)

  // Direct labels at each line's end, nudged apart so they never overlap.
  const ends = series.map((s) => {
    const last = s.pts[s.pts.length - 1]
    return { key: `${s.r.mode}-${s.r.repeat}`, mode: s.r.mode, repeat: s.r.repeat, y: y(last.y), x: x(s.end ?? last.x) }
  }).sort((a, b) => a.y - b.y)
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14
  const multiRepeat = task.repeats.length > 1

  return (
    <div className="chart" ref={box} onMouseLeave={() => setTip(null)}>
      <svg width={W} height={H} role="img" aria-label={`${task.title} 开发集最佳${metricName(task.metric)}随${AXIS[axis]}的变化`}>
        <g className="grid">{yTicks.map((t) => <line key={t} x1={left} x2={W - right} y1={y(t)} y2={y(t)} />)}</g>
        <g className="axis">
          {yTicks.map((t) => <text key={t} x={left - 8} y={y(t) + 4} textAnchor="end">{yFmt(t)}</text>)}
          {xTicks.map((t) => <text key={t} x={x(t)} y={H - 8} textAnchor="middle">{xFmt(t)}</text>)}
        </g>
        {task.baseline != null && <g className="baseline">
          <line x1={left} x2={W - right} y1={y(task.baseline)} y2={y(task.baseline)} />
          <text x={left + 4} y={y(task.baseline) + 15}>基线 {task.metric === 'score' ? fmt.n(task.baseline) : '1×'}</text>
        </g>}
        {task.minSpeedup != null && <g className="target">
          <line x1={left} x2={W - right} y1={y(task.minSpeedup)} y2={y(task.minSpeedup)} strokeDasharray="4 4" />
          <text x={left + 4} y={y(task.minSpeedup) - 6}>开发目标 {task.minSpeedup}×</text>
        </g>}
        {series.map((s) => {
          const m = rmode(s.r.mode)
          let d = `M${x(s.pts[0].x)},${y(s.pts[0].y)}`
          for (let i = 1; i < s.pts.length; i++) d += ` H${x(s.pts[i].x)} V${y(s.pts[i].y)}`
          if (s.end != null) d += ` H${x(s.end)}`
          const changes = s.pts.filter((p, i) => i === 0 || p.y !== s.pts[i - 1].y)
          return (
            <g key={`${s.r.mode}-${s.r.repeat}`}>
              <path d={d} fill="none" stroke={m.color} strokeWidth={3} strokeLinejoin="round" strokeDasharray={multiRepeat && s.r.repeat > 1 ? (s.r.repeat === 2 ? '6 3' : '2 3') : undefined} />
              {s.end != null && <line x1={x(s.end)} x2={x(s.end)} y1={y(s.pts[s.pts.length - 1].y) - 5} y2={y(s.pts[s.pts.length - 1].y) + 5} stroke={m.color} strokeWidth={3} />}
              {changes.map((p, i) => (
                <g key={i} onMouseMove={(e) => {
                  const b = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                  setTip({ x: e.clientX - b.left, y: e.clientY - b.top,
                    text: `${m.label} r${s.r.repeat} · ${p.p.candidate ?? '—'} · ${metricText(task.metric, p.y)} · ${Math.round(p.p.t)}s · ${p.p.tokens != null ? fmt.n(p.p.tokens) : '?'} Token${p.p.cost != null ? ` · ${money(p.p.cost, currency)} 估` : ''}` })
                }}>
                  <circle cx={x(p.x)} cy={y(p.y)} r={12} fill="transparent" />
                  <Shape shape={m.shape} x={x(p.x)} y={y(p.y)} r={5.5} fill={m.color} stroke="var(--card)" />
                </g>
              ))}
            </g>
          )
        })}
        {ends.map((e) => (
          <text key={e.key} x={Math.min(e.x + 8, W - right + 8)} y={e.y + 4} className="lbl-strong">{rmode(e.mode).short}{multiRepeat ? `·r${e.repeat}` : ''}</text>
        ))}
      </svg>
      {tip && <div className="tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
    </div>
  )
}

function niceTicks(lo: number, hi: number, n: number): number[] {
  const span = hi - lo
  if (!(span > 0)) return [lo]
  const raw = span / n
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= raw) ?? raw
  const out: number[] = []
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(Math.round(t / step) * step)
  return out
}

export function AxisSwitch({ axis, setAxis, costOk }: { axis: Axis; setAxis: (a: Axis) => void; costOk: boolean }) {
  return (
    <div className="seg small-seg" role="group" aria-label="横轴">
      {(Object.keys(AXIS) as Axis[]).map((a) => (
        <button key={a} className={axis === a ? 'on' : ''} disabled={a === 'cost' && !costOk} onClick={() => setAxis(a)}
          title={a === 'cost' && !costOk ? '本批没有价格快照' : undefined}>{AXIS[a]}</button>
      ))}
    </div>
  )
}

export function ModeLegend({ modes, repeats }: { modes: string[]; repeats: number[] }) {
  return (
    <div className="legend">
      {modes.map((m) => <span key={m} className="row" style={{ gap: 6 }}><ModeMark mode={m} size={11} />{rmode(m).label}（{rmode(m).short}）</span>)}
      {repeats.length > 1 && <span className="muted">实线 r1 · 长虚线 r2 · 短虚线 r3</span>}
      <span className="muted">标记 = 保留结果更新；竖线 = 运行结束</span>
    </div>
  )
}

/* ---------- scoreboard: the numbers a room can read ---------- */

/** One tile per mode: the median development result, its change against the baseline, and nothing else. */
export function Scoreboard({ task, lead, planned }: { task: RTask; lead: string | null; planned: string[] }) {
  return (
    <div className="scores">
      {task.modes.map((m) => {
        const s = modeSummary(task, m)
        const [n, unit] = bigNumber(task.metric, s.value)
        const d = deltaText(task, s.value)
        const sub = s.pending ? '研究中' : s.value == null ? '无有效结果'
          : s.improved > 0 ? (task.metric === 'score' ? `比基线 ${d ?? ''}` : '快于初始程序')
          : '未超过基线'
        return (
          <div key={m} className={`score ${lead === m ? 'lead' : ''}`}>
            <div className="who"><ModeMark mode={m} size={10} />{rmode(m).label}{s.runs > 1 && <span className="mono muted">· {s.runs} 次中位</span>}</div>
            <div className="num">{n}{unit && <small>{unit}</small>}</div>
            <div className={`sub ${s.improved > 0 ? 'up' : ''}`}>{sub}</div>
          </div>
        )
      })}
      {planned.filter((m) => !task.modes.includes(m)).map((m) => (
        <div key={m} className="score off">
          <div className="who"><ModeMark mode={m} size={10} />{rmode(m).label}</div>
          <div className="num">—</div>
          <div className="sub">此题不设该组</div>
        </div>
      ))}
    </div>
  )
}

/** The whole batch state in four badges: which data, final, fairness, repeats. */
export function BatchBadges({ b }: { b: RBatch }) {
  const reps = Math.max(1, ...b.tasks.map((t) => t.repeats.length))
  const counts = b.runs.reduce<Record<string, number>>((a, r) => ({ ...a, [r.final.state]: (a[r.final.state] ?? 0) + 1 }), {})
  const finalChip = b.finalEnabled === false ? <Chip tone="warn" icon="!">最终集未验证</Chip>
    : counts.passed === b.runs.length ? <Chip tone="good" icon="✓">最终集全部通过</Chip>
    : (counts.failed || counts.error || counts.missing) ? <Chip tone="bad" icon="✕">最终集 {counts.passed ?? 0}/{b.runs.length} 通过</Chip>
    : <Chip icon="…">最终集 {counts.passed ?? 0}/{b.runs.length} 已通过</Chip>
  return (
    <div className="row">
      <Chip tone={b.running ? 'accent' : 'neutral'} icon={b.running ? '●' : undefined}>{b.running ? `进行中 ${b.finished}/${b.planned}` : b.finalEnabled === false ? '开发预实验' : '正式对照'}</Chip>
      {finalChip}
      <FairChip b={b} />
      <Chip>每组 {reps} 次</Chip>
      {b.limits && <Chip>每轮上限 {b.limits.wall_clock_s}s · {b.limits.max_model_requests} 次请求 · {b.limits.max_candidates} 个候选</Chip>}
    </div>
  )
}
