import { useState } from 'react'
import { useWidth } from '../hooks'
import type { Candidate, TaskRun } from '../api'
import { fmt, status } from '../labels'

/* Speedup per candidate against the target line. Failed candidates have no bar; their status is written instead. */
export function SpeedupBars({ candidates, target, bestId, onPick }: {
  candidates: Candidate[]; target: number; bestId: string | null; onPick?: (cid: string) => void
}) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const [box, W] = useWidth<HTMLDivElement>()
  const rows = candidates.map((c) => {
    const ev = c.dev_evaluations[c.dev_evaluations.length - 1]
    const speed = c.candidate_id === 'c0' ? 1 : ev?.status === 'passed' ? ev.speedup : null
    return { id: c.candidate_id, speed, ev, initial: c.candidate_id === 'c0', reused: c.origin === 'experience' }
  })
  const maxX = Math.max(1.6, target + 0.2, ...rows.map((r) => (r.speed ?? 0) + 0.1))
  const left = 64, right = 70, rowH = 34, top = 22
  const H = top + rows.length * rowH + 26
  const x = (v: number) => left + (v / maxX) * (W - left - right)
  const ticks = maxX <= 3.2 ? [0, 0.5, 1, 1.5, 2, 2.5, 3].filter((t) => t <= maxX) : Array.from({ length: Math.floor(maxX) + 1 }, (_, i) => i)

  return (
    <div className="chart" ref={box} onMouseLeave={() => setTip(null)}>
      <svg width={W} height={H} role="img" aria-label="各候选在开发数据上的加速比">
        <g className="grid">{ticks.map((t) => <line key={t} x1={x(t)} x2={x(t)} y1={top - 6} y2={H - 22} />)}</g>
        <g className="axis">{ticks.map((t) => <text key={t} x={x(t)} y={H - 6} textAnchor="middle">{t}×</text>)}</g>
        <g className="target">
          <line x1={x(target)} x2={x(target)} y1={top - 14} y2={H - 22} />
          <text x={x(target) + 4} y={top - 6}>目标 {target}×</text>
        </g>
        {rows.map((r, i) => {
          const y = top + i * rowH
          const best = r.id === bestId
          const [label] = status(r.ev?.status)
          const tipText = r.initial ? 'c0 初始程序：加速比定义为 1.00×'
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
                  <text x={x(r.speed) + 6} y={y + rowH / 2 + 4} className="lbl-strong">{fmt.x(r.speed)}</text>
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
  const step = hi - lo > 4 ? 1 : 0.25
  for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) ticks.push(Math.round(t * 100) / 100)

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

/* Online stream: cumulative large-model (GPT) cost along the task sequence, one line per arm and repeat. Markers show
   where a run used the large model; a flat stretch means the tasks there were served without it. */
export function StreamLadder({ positions, series, repeats, metric }: {
  positions: { position: number; task_id: string; family: string; first_of_family: boolean }[]
  series: Record<'memory' | 'fresh', Record<string, { cost_usd: number[]; agent_loop_s: number[]; large_model_requests: number[] }>>
  repeats: number
  metric: 'cost_usd' | 'agent_loop_s' | 'large_model_requests'
}) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const [box, W] = useWidth<HTMLDivElement>(760)
  const arms = ['fresh', 'memory'] as const
  const vals = arms.flatMap((a) => Array.from({ length: repeats }, (_, r) => series[a]?.[String(r + 1)]?.[metric] ?? []).flat())
  const hi = Math.max(metric === 'cost_usd' ? 0.05 : 1, ...vals) * 1.08
  const left = 64, right = 20, top = 18, bottom = 64, H = 330
  const n = positions.length
  const x = (i: number) => left + (n <= 1 ? 0 : (i / (n - 1)) * (W - left - right))
  const y = (v: number) => top + (1 - v / hi) * (H - top - bottom)
  const fmtV = (v: number) => (metric === 'cost_usd' ? fmt.usd(v) : metric === 'agent_loop_s' ? fmt.s(v) : String(v))
  const ticks = Array.from({ length: 5 }, (_, i) => (hi / 1.08) * (i / 4))
  const color = { fresh: 'var(--series-old)', memory: 'var(--series-new)' }
  const name = { fresh: '不带记忆（每个任务都从起点出发）', memory: '带记忆（在线写入，下一个任务读取）' }
  const famMark: Record<string, string> = { groupagg: 'G', logstats: 'L', intervals: 'I' }
  return (
    <div className="chart" ref={box} onMouseLeave={() => setTip(null)}>
      <div className="legend">
        {arms.map((a) => <span key={a}><i style={{ background: color[a] }} />{name[a]}</span>)}
        <span><i style={{ background: 'transparent', border: '2px solid var(--ink-3)' }} />圆点 = 该任务用了大模型</span>
      </div>
      <svg width={W} height={H} role="img" aria-label="沿任务流累计的大模型成本">
        <g className="grid">{ticks.map((t) => <line key={t} x1={left} x2={W - right} y1={y(t)} y2={y(t)} />)}</g>
        <g className="axis">{ticks.map((t) => <text key={t} x={left - 8} y={y(t) + 4} textAnchor="end">{fmtV(t)}</text>)}</g>
        {positions.map((p, i) => (
          <g key={p.task_id} className="axis">
            <text x={x(i)} y={H - bottom + 18} textAnchor="middle" style={{ fontWeight: p.first_of_family ? 700 : 400 }}>{p.task_id.replace('S-', '')}</text>
            <text x={x(i)} y={H - bottom + 34} textAnchor="middle" style={{ fill: p.first_of_family ? 'var(--accent-ink)' : undefined }}>
              {famMark[p.family] ?? p.family}{p.first_of_family ? '*' : ''}
            </text>
          </g>
        ))}
        <text x={left} y={H - 8} className="axis" style={{ fontSize: 12 }}>G 分组聚合 · L 访问日志 · I 区间合并 · * 该任务族在任务流中首次出现</text>
        {arms.map((a) => Array.from({ length: repeats }, (_, r) => {
          const s = series[a]?.[String(r + 1)]
          const v = s?.[metric] ?? []
          if (!v.length) return null
          const pts = v.map((val, i) => `${x(i)},${y(val)}`).join(' ')
          return (
            <g key={`${a}-${r}`}>
              <polyline points={pts} fill="none" stroke={color[a]} strokeWidth={2} strokeOpacity={0.85} strokeLinejoin="round" />
              {v.map((val, i) => {
                const used = (s!.large_model_requests[i] ?? 0) > (i ? s!.large_model_requests[i - 1] : 0)
                const text = `第 ${r + 1} 次重放 · ${positions[i].task_id} · ${name[a].split('（')[0]}：累计 ${fmtV(val)}${used ? '；本任务用了大模型' : '；本任务没用大模型'}`
                return (
                  <g key={i} onMouseMove={(e) => {
                    const b = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                    setTip({ x: e.clientX - b.left, y: e.clientY - b.top, text })
                  }}>
                    <circle cx={x(i)} cy={y(val)} r={10} fill="transparent" />
                    {used && <circle cx={x(i)} cy={y(val)} r={4.5} fill={color[a]} stroke="var(--card)" strokeWidth={2} />}
                  </g>
                )
              })}
            </g>
          )
        }))}
      </svg>
      {tip && <div className="tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
    </div>
  )
}
