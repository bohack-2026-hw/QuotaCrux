import { api } from '../api'
import type { Report } from '../api'
import { usePoll } from '../hooks'
import { ACTION, fmt } from '../labels'
import { StatusChip } from './ui'

/* Same held-out task, same repeat index, two snapshots: what the agent actually did under each. */
export function BehaviorPair({ task, a, b, runA, runB, onOpenRun }: {
  task: string; a: string; b: string; runA?: string; runB?: string; onOpenRun: (id: string) => void
}) {
  const ra = usePoll(() => (runA ? api.run(runA) : Promise.resolve(null)), [runA], 0, false)
  const rb = usePoll(() => (runB ? api.run(runB) : Promise.resolve(null)), [runB], 0, false)
  return (
    <div className="grid cols-2" style={{ marginTop: 14 }}>
      <Column title={`${task} · ${a}（旧经验）`} color="var(--series-old)" rep={ra.data} onOpenRun={onOpenRun} />
      <Column title={`${task} · ${b}（新经验）`} color="var(--series-new)" rep={rb.data} onOpenRun={onOpenRun} />
    </div>
  )
}

function Column({ title, color, rep, onOpenRun }: { title: string; color: string; rep: Report | null; onOpenRun: (id: string) => void }) {
  if (!rep) return <div className="card"><div className="eyebrow">{title}</div><p className="muted">加载中…</p></div>
  const up = rep.iterations.upgrade_at_step
  return (
    <div className="card" style={{ borderTop: `3px solid ${color}` }}>
      <div className="spread">
        <div className="eyebrow" style={{ margin: 0 }}>{title}</div>
        <button className="link mono" onClick={() => onOpenRun(rep.run_id)}>{rep.run_id.slice(-9)}</button>
      </div>
      <p style={{ margin: '6px 0 10px', fontWeight: 600 }}>{rep.outcome.summary}</p>
      <p className="small muted" style={{ marginTop: 0 }}>
        读取经验 {rep.experience.read.length} 条 · 请求 {rep.iterations.model_requests} · 候选 {rep.iterations.candidates_proposed}
        · 升级 {rep.iterations.upgrades} · 费用 {fmt.usd(rep.usage.total.cost_usd)} · {fmt.s(rep.timing.wall_clock_total_s)}
      </p>
      <table className="tbl">
        <tbody>
          {rep.steps.map((s) => {
            const r = s.result as Record<string, unknown>
            const who = s.actor === 'program' ? '程序' : up != null && s.seq > up ? 'GPT' : 'Qwen'
            return (
              <tr key={s.seq}>
                <td className="mono" style={{ width: 28 }}>{s.seq}</td>
                <td style={{ width: 52 }}>{who}</td>
                <td>{ACTION[s.action] ?? s.action}{s.candidate_id ? ` ${s.candidate_id}` : ''}</td>
                <td><StatusChip value={s.status} /></td>
                <td>{typeof r.speedup === 'number' ? fmt.x(r.speedup) : ''}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {rep.steps.find((s) => s.actor === 'model' && s.purpose) && (
        <p className="small" style={{ marginBottom: 0 }}>
          第一步的目的：{rep.steps.find((s) => s.actor === 'model' && s.purpose)!.purpose!.slice(0, 160)}
        </p>
      )}
    </div>
  )
}
