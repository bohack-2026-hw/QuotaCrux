import { useState } from 'react'
import { useWidth } from '../hooks'
import type { Candidate, TaskRun } from '../api'
import { fmt, status } from '../labels'

/* Speedup per candidate against the target line. Failed candidates have no bar; their status is written instead. */
export function SpeedupBars({ candidates, target, bestId, onPick }: {
  candidates: Candidate[]; target: number | null; bestId: string | null; onPick?: (cid: string) => void
}) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const [box, W] = useWidth<HTMLDivElement>()
  const score = target == null
  const format = score ? fmt.n : fmt.x
  const rows = candidates.map((c) => {
    const ev = c.dev_evaluations[c.dev_evaluations.length - 1]
    const speed = score ? (ev?.status === 'passed' ? ev.objective?.value ?? null : null)
      : c.candidate_id === 'c0' ? 1 : ev?.status === 'passed' ? ev.speedup : null
    return { id: c.candidate_id, speed, ev, initial: c.candidate_id === 'c0', reused: c.origin === 'experience' }
  })
  const maxX = score ? Math.max(1, ...rows.map((r) => (r.speed ?? 0) * 1.1))
    : Math.max(1.6, (target ?? 1.1) + 0.2, ...rows.map((r) => (r.speed ?? 0) + 0.1))
  const left = 64, right = 70, rowH = 34, top = 22
  const H = top + rows.length * rowH + 26
  const x = (v: number) => left + (v / maxX) * (W - left - right)
  const ticks = score ? [0, 1, 2, 3, 4].map((n) => Math.round(n * maxX / 4))
    : [0, 0.5, 1, 1.5, 2, 2.5, 3].filter((t) => t <= maxX)

  return (
    <div className="chart" ref={box} onMouseLeave={() => setTip(null)}>
      <svg width={W} height={H} role="img" aria-label={`各候选在开发数据上的${score ? '原始得分' : '加速比'}`}>
        <g className="grid">{ticks.map((t) => <line key={t} x1={x(t)} x2={x(t)} y1={top - 6} y2={H - 22} />)}</g>
        <g className="axis">{ticks.map((t, i) => <text key={i} x={x(t)} y={H - 6} textAnchor="middle">{t}{score ? '' : '×'}</text>)}</g>
        {target != null && <g className="target">
          <line x1={x(target)} x2={x(target)} y1={top - 14} y2={H - 22} />
          <text x={x(target) + 4} y={top - 6}>目标 {target}×</text>
        </g>}
        {rows.map((r, i) => {
          const y = top + i * rowH
          const best = r.id === bestId
          const [label] = status(r.ev?.status)
          const tipText = score ? `${r.id}：${r.speed == null ? label : `原始得分 ${format(r.speed)}`}` : r.initial ? 'c0 初始程序：加速比定义为 1.00×'
            : r.speed != null ? `${r.id}${r.reused ? '（复用经验中的程序）' : ''}：${fmt.x(r.speed)}${r.ev?.improved ? '，全部样本快于基线' : '，与基线重叠，不计改善'}`
            : r.ev ? `${r.id}：${label}` : `${r.id}：验证中`
          return (
            <g key={r.id} style={{ cursor: onPick ? 'pointer' : undefined }} onClick={() => onPick?.(r.id)}
              onMouseMove={(e) => {
                const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                setTip({ x: e.clientX - box.left, y: e.clientY - box.top, text: tipText })
              }}>
              <rect x={0} y={y} width={W} height={rowH} fill="transparent" />
              <text x={left - 12} y={y + rowH / 2 + 4} textAnchor="end" className={best ? 'lbl-strong' : 'lbl'}>
                {r.id}{r.reused ? ' ↺' : ''}{best ? ' ★' : ''}
              </text>
              {r.speed != null ? (
                <>
                  <rect x={left} y={y + 9} height={rowH - 18} rx={4}
                    width={Math.max(2, x(r.speed) - left)}
                    fill={r.initial ? 'var(--rule-strong)' : r.ev?.goal_met ? 'var(--good)' : r.ev?.improved ? 'var(--ink-2)' : 'var(--ink-3)'} />
                  <text x={x(r.speed) + 6} y={y + rowH / 2 + 4} className="lbl-strong">{format(r.speed)}</text>
                </>
              ) : r.ev ? (
                <text x={left + 4} y={y + rowH / 2 + 4} className="lbl" style={{ fill: 'var(--critical)' }}>✕ {label}</text>
              ) : (
                <text x={left + 4} y={y + rowH / 2 + 4} className="lbl">验证中…</text>
              )}
            </g>
          )
        })}
      </svg>
      {tip && <div className="tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
    </div>
  )
}

/* Per task: each run of the old and the new snapshot as a dot on one speedup axis. Runs without a timed final result
   sit in a separate "未计时" column so failures stay visible instead of disappearing. */
export function PairedDots({ tasks, perTask, a, b, target }: {
  tasks: string[]; perTask: Record<string, Record<string, { runs: TaskRun[] }>>; a: string; b: string; target: number
}) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const [box, W] = useWidth<HTMLDivElement>(760)
  const all = tasks.flatMap((t) => [a, b].flatMap((s) => perTask[t]?.[s]?.runs ?? []))
  const speeds = all.map((r) => r.final_speedup).filter((v): v is number => v != null)
  const lo = Math.min(0.6, ...speeds.map((v) => v - 0.05)), hi = Math.max(1.8, target + 0.2, ...speeds.map((v) => v + 0.05))
  const left = 70, failCol = 70, right = 24, rowH = 46, top = 26
  const H = top + tasks.length * rowH + 28
  const x0 = left + failCol
  const x = (v: number) => x0 + ((v - lo) / (hi - lo)) * (W - x0 - right)
  const ticks: number[] = []
  for (let t = Math.ceil(lo * 4) / 4; t <= hi; t += 0.25) ticks.push(Math.round(t * 100) / 100)

  const show = (e: React.MouseEvent<SVGGElement>, text: string) => {
    const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
    setTip({ x: e.clientX - box.left, y: e.clientY - box.top, text })
  }

  return (
    <div className="chart" ref={box} onMouseLeave={() => setTip(null)}>
      <div className="legend">
        <span><i style={{ background: 'var(--series-old)' }} />{a}（{a === 'v0' ? '无经验' : '旧经验'}）</span>
        <span><i style={{ background: 'var(--series-new)' }} />{b}（新经验）</span>
        <span><i style={{ background: 'transparent', border: '2px solid var(--ink-3)' }} />空心 = 未达标或无计时结果</span>
      </div>
      <svg width={W} height={H} role="img" aria-label={`每个任务上 ${a} 与 ${b} 的最终加速比`}>
        <g className="grid">{ticks.map((t) => <line key={t} x1={x(t)} x2={x(t)} y1={top - 8} y2={H - 24} />)}</g>
        <g className="axis">
          {ticks.filter((_, i) => i % 2 === 0).map((t) => <text key={t} x={x(t)} y={H - 8} textAnchor="middle">{t}×</text>)}
          <text x={left + failCol / 2} y={H - 8} textAnchor="middle">未计时</text>
        </g>
        <line x1={x0 - 6} x2={x0 - 6} y1={top - 8} y2={H - 24} stroke="var(--rule-strong)" />
        <g className="target">
          <line x1={x(target)} x2={x(target)} y1={top - 16} y2={H - 24} />
          <text x={x(target) + 4} y={top - 8}>目标 {target}×</text>
        </g>
        {tasks.map((t, i) => {
          const y = top + i * rowH
          return (
            <g key={t}>
              <text x={left - 10} y={y + rowH / 2 + 4} textAnchor="end" className="lbl-strong">{t}</text>
              {[a, b].map((s, si) => {
                const runs = perTask[t]?.[s]?.runs ?? []
                const cy = y + rowH / 2 + (si === 0 ? -8 : 8)
                const color = si === 0 ? 'var(--series-old)' : 'var(--series-new)'
                return runs.map((r, ri) => {
                  const cx = r.final_speedup != null ? x(r.final_speedup) : left + 16 + ri * 16
                  const text = `${t} · ${s} 第${ri + 1}次：${r.final_speedup != null ? fmt.x(r.final_speedup) : '无计时结果'}，`
                    + `${r.goal_met ? '达标' : '未达标'}，${r.model_requests} 次请求，${fmt.s(r.wall_clock_s)}`
                  return (
                    <g key={`${s}-${r.run_id}`} onMouseMove={(e) => show(e, text)}>
                      <circle cx={cx} cy={cy} r={12} fill="transparent" />
                      <circle cx={cx} cy={cy} r={5.5} fill={r.goal_met ? color : 'var(--card)'} stroke={r.goal_met ? 'var(--card)' : color}
                        strokeWidth={2} />
                    </g>
                  )
                })
              })}
            </g>
          )
        })}
      </svg>
      {tip && <div className="tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
    </div>
  )
}
