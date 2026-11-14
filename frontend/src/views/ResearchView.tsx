import { useState } from 'react'
import { AxisSwitch, BatchBadges, ModeLegend, ProgressChart, RoutingTable, Scoreboard } from '../components/research'
import type { Axis } from '../components/research'
import { Empty } from '../components/ui'
import { STUDY, fmt, rmode } from '../labels'
import type { RBatch, RTask } from '../research'
import { metricName, taskVerdict } from '../researchFormat'
import { useResearchBatch, useResearchList } from '../researchData'

/* Results only: per task the scoreboard and the best-so-far curve. Configuration and the run ledger are on 后台. */
export function ResearchView({ selected, onSelect, onOpenConsole }: { selected: string | null; onSelect: (id: string) => void; onOpenConsole: (id: string) => void }) {
  const { entries } = useResearchList()
  const entry = entries.find((e) => e.id === selected) ?? entries[0] ?? null
  const { batch, error } = useResearchBatch(entry)
  const [axis, setAxis] = useState<Axis>('time')

  if (error) return <div className="error small">{error}</div>
  if (!batch || !entry) return <div className="card"><Empty title="还没有研究批次" /></div>
  return (
    <div className="stack">
      <div className="spread wrap">
        <div className="row">
          <span className="metric-pill">{STUDY[batch.study]}</span>
          <BatchBadges b={batch} />
          {entries.length > 1 && (
            <select value={entry.id} onChange={(e) => onSelect(e.target.value)} style={{ width: 'auto' }}>
              {entries.map((e) => <option key={e.id} value={e.id}>{STUDY[e.study] ?? e.study} · {e.label ?? e.id}</option>)}
            </select>
          )}
        </div>
        <div className="row">
          <AxisSwitch axis={axis} setAxis={setAxis} costOk={batch.runs.some((r) => r.progress.some((p) => p.cost != null))} />
          <button className="btn" onClick={() => onOpenConsole(batch.id)}>明细 →</button>
        </div>
      </div>
      {batch.tasks.map((t) => <TaskCard key={t.id} t={t} b={batch} axis={axis} />)}
    </div>
  )
}

function TaskCard({ t, b, axis }: { t: RTask; b: RBatch; axis: Axis }) {
  const v = taskVerdict(t, (m) => `${rmode(m).label}组`)
  return (
    <div className="card">
      <div className="head-row">
        <h2 style={{ margin: 0 }}>{t.title}</h2>
        <span className="metric-pill">{metricName(t.metric)} ↑ · {t.source === 'final' ? '最终集' : '开发集'}</span>
        <span className="mono small muted" style={{ marginLeft: 'auto' }}>基线 {t.metric === 'score' ? fmt.n(t.source === 'final' ? t.finalBaseline : t.baseline) : '1×'}</span>
      </div>
      <Scoreboard task={t} lead={v.lead} planned={b.modes} />
      {t.repeats.length > 1 && <ModeLegend modes={t.modes} repeats={t.repeats} />}
      <ProgressChart task={t} axis={axis} currency={b.pricing?.currency ?? null} />
      {b.study === 'routing' && <div style={{ marginTop: 14 }}><RoutingTable task={t} /></div>}
    </div>
  )
}
