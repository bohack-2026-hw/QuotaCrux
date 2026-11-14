import type { ReactNode } from 'react'
import { BatchBadges, CostTotal, ModeMark, ProgressChart, Scoreboard } from '../components/research'
import { Empty } from '../components/ui'
import { STUDY, fmt, rmode } from '../labels'
import type { RBatch, RTask } from '../research'
import { total } from '../research'
import { bestOf, gainOf, taskVerdict } from '../researchFormat'
import { useResearchBatch, useResearchList } from '../researchData'
import type { BatchEntry } from '../researchData'

/* Overview: numbers only, one section per study (feedback ablation first, then routing ablation when it exists).
   Studies are never merged: each keeps its own groups, baseline and budget. */
export function HomeView({ onOpenResearch }: { onOpenResearch: (id: string) => void }) {
  const { entries } = useResearchList()
  const feedback = entries.find((e) => e.study !== 'routing') ?? null
  const routing = entries.find((e) => e.study === 'routing') ?? null
  if (!feedback && !routing) return <div className="card"><Empty title="还没有研究批次" /></div>
  const both = !!feedback && !!routing
  return (
    <div>
      {feedback && <Study entry={feedback} titled={both} onOpen={onOpenResearch} />}
      {routing && <Study entry={routing} titled={both} onOpen={onOpenResearch} />}
    </div>
  )
}

function Study({ entry, titled, onOpen }: { entry: BatchEntry; titled: boolean; onOpen: (id: string) => void }) {
  const { batch: b } = useResearchBatch(entry)
  if (!b) return null
  return (
    <>
      {titled && <div className="study-head"><h2>{STUDY[b.study]}</h2><span className="mono small muted">{b.modes.length} 组 · {b.tasks.length} 题</span></div>}
      <section className="hero">
        <Highlights b={b} />
        <div className="spread wrap" style={{ marginTop: 26 }}>
          <BatchBadges b={b} />
          <button className="btn primary" onClick={() => onOpen(b.id)}>研究对照 →</button>
        </div>
      </section>
      <Kpis b={b} />
      <Groups b={b} />
      <div className="board">
        {b.tasks.map((t) => <TaskCard key={t.id} t={t} b={b} />)}
      </div>
    </>
  )
}

/** Batch totals as a strip of figures. */
function Kpis({ b }: { b: RBatch }) {
  const n = (vs: (number | null)[], f: (v: number) => string = String) => {
    const t = total(vs)
    return t.value == null ? '—' : f(t.value)
  }
  const tiles: [string, ReactNode][] = [
    ['任务', b.tasks.length],
    ['研究轮次', `${b.finished}/${b.planned}`],
    ['候选', `${n(b.runs.map((r) => r.passed))}/${n(b.runs.map((r) => r.proposed))}`],
    ['模型请求', n(b.runs.map((r) => r.requests))],
    ['Token', n(b.runs.map((r) => r.tokens), fmt.rows)],
    ['墙钟', n(b.runs.map((r) => r.wallS), (v) => fmt.s(v))],
    ['费用', <CostTotal key="cost" costs={b.runs.map((r) => r.cost)} />],
  ]
  return (
    <div className="kpis">
      {tiles.map(([k, v]) => <div key={k} className="kpi"><div className="k">{k}</div><div className="v">{v}</div></div>)}
    </div>
  )
}

/** The groups of this study: what each one changes, and how many runs it has in this batch. */
function Groups({ b }: { b: RBatch }) {
  const all = b.study === 'routing' ? b.modes : ['feedback', 'independent', 'no_feedback']
  return (
    <div className="modes">
      {all.map((m) => {
        const runs = b.runs.filter((r) => r.mode === m).length
        return (
          <div key={m} className={`mode-card ${runs ? '' : 'off'}`} style={{ ['--mode' as string]: rmode(m).color }}>
            <div className="row" style={{ gap: 8 }}><ModeMark mode={m} size={11} /><b>{rmode(m).label}</b><span className="mono muted small">{m}</span></div>
            <div className="seen"><span className="muted">{b.study === 'routing' ? '路由' : '可见'}</span> {rmode(m).seen}</div>
            <div className="mono small muted">{runs ? `${runs} 轮` : '本批未安排'}</div>
          </div>
        )
      })}
    </div>
  )
}

/** The best gain of each task, large. */
function Highlights({ b }: { b: RBatch }) {
  return (
    <div className="highlights">
      {b.tasks.map((t) => {
        const best = bestOf(t)
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
      <Scoreboard task={t} lead={v.lead} planned={b.modes} usage />
      <ProgressChart task={t} axis="time" currency={b.pricing?.currency ?? null} height={170} />
    </div>
  )
}
