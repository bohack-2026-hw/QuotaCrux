import { BatchBadges, ProgressChart, Scoreboard } from '../components/research'
import { Empty } from '../components/ui'
import { rmode } from '../labels'
import type { RBatch, RTask } from '../research'
import { bestOf, gainOf, taskVerdict } from '../researchFormat'
import { useResearchBatch, useResearchList } from '../researchData'

/* Overview: numbers only. The best gain per task up top, then a scoreboard and a curve per task. */
export function HomeView({ onOpenResearch }: { onOpenResearch: (id: string) => void }) {
  const { entries } = useResearchList()
  const { batch: b } = useResearchBatch(entries[0] ?? null)
  if (!b) return <div className="card"><Empty title="还没有研究批次" /></div>

  return (
    <div>
      <section className="hero">
        <Highlights b={b} />
        <div className="spread wrap" style={{ marginTop: 26 }}>
          <BatchBadges b={b} />
          <button className="btn primary" onClick={() => onOpenResearch(b.id)}>研究对照 →</button>
        </div>
      </section>
      <div className="board">
        {b.tasks.map((t) => <TaskCard key={t.id} t={t} b={b} />)}
      </div>
    </div>
  )
}

/** The best gain of each task, large. */
function Highlights({ b }: { b: RBatch }) {
  const items = b.tasks.map((t) => ({ t, best: bestOf(t) }))
  return (
    <div className="highlights">
      {items.map(({ t, best }) => {
        const g = best ? gainOf(t, best.value) : null
        return (
          <div key={t.id} className="highlight">
            <div className="label mono">{t.title}</div>
            <div className={`big ${g ? 'gain-text' : 'muted'}`}>{g ? <>{g.big}<small>{g.unit}</small></> : '—'}</div>
            <div className="cap">{t.metric === 'score' ? '得分' : '提速'}{best ? <> · <span style={{ color: rmode(best.mode).color }}>●</span> {rmode(best.mode).label}</> : ''}</div>
          </div>
        )
      })}
    </div>
  )
}

function TaskCard({ t, b }: { t: RTask; b: RBatch }) {
  const v = taskVerdict(t, (m) => `${rmode(m).label}组`)
  return (
    <div className="card task-card">
      <div className="head">
        <h2>{t.title}</h2>
        <span className="metric-pill">{t.metric === 'score' ? '原始得分 ↑' : '加速比 ↑'}</span>
      </div>
      <Scoreboard task={t} lead={v.lead} planned={b.modes} />
      <ProgressChart task={t} axis="time" currency={b.pricing?.currency ?? null} height={170} />
    </div>
  )
}
