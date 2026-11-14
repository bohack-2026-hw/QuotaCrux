import { BatchBadges, CostTotal, ProgressChart, Scoreboard } from '../components/research'
import { Empty } from '../components/ui'
import { fmt, rmode } from '../labels'
import type { RBatch, RTask } from '../research'
import { bestOf, gainOf, sumText, taskVerdict } from '../researchFormat'
import { useResearchBatch, useResearchList } from '../researchData'

/* The roadshow screen: one question, the best gains up front, then one scoreboard and one curve per task.
   Configuration, data source and per-run ledgers live on the research page. */
export function HomeView({ onOpenResearch }: { onOpenResearch: (id: string) => void }) {
  const { entries } = useResearchList()
  const { batch: b } = useResearchBatch(entries[0] ?? null)

  return (
    <div>
      <section className="hero">
        <div className="hero-grid">
          <div>
            <span className="kicker"><span className={`pulse ${b?.running ? '' : 'idle'}`} />单任务长程研究</span>
            <h1>固定预算下，<span className="dim">Agent 能不能把</span>一个任务越做越好？</h1>
            <p className="lede">模型、预算和评测器全部固定，只改变 Agent 能看到什么：每一轮的评测反馈、只看初始程序，或看不到任何结果。</p>
            {b && (
              <div className="row">
                <BatchBadges b={b} />
                <button className="btn primary" onClick={() => onOpenResearch(b.id)}>逐题对照 →</button>
              </div>
            )}
          </div>
          {b && <Highlights b={b} />}
        </div>
      </section>

      {!b ? <div className="card"><Empty title="还没有研究批次" /></div> : (
        <>
          <div className="board">
            {b.tasks.map((t) => <TaskCard key={t.id} t={t} b={b} />)}
          </div>
          <div className="metaline" style={{ marginTop: 18 }}>
            <span>模型 <b>{b.model?.name ?? '未记录'}</b></span>
            <span>实耗 <b>{sumText(b.runs.map((r) => r.requests), String)} 次请求 · {sumText(b.runs.map((r) => r.wallS), (x) => fmt.s(x))}</b></span>
            <span>费用 <b><CostTotal costs={b.runs.map((r) => r.cost)} /></b></span>
          </div>
        </>
      )}
    </div>
  )
}

/** The best gain of each task, large: what the research loop actually bought. */
function Highlights({ b }: { b: RBatch }) {
  const items = b.tasks.map((t) => ({ t, best: bestOf(t) })).filter((x) => x.best)
  if (!items.length) return null
  return (
    <div className="highlights">
      {items.map(({ t, best }) => {
        const g = gainOf(t, best!.value)!
        return (
          <div key={t.id} className="highlight">
            <div className="big gain-text">{g.big}<small>{g.unit}</small></div>
            <div className="cap"><b>{t.title.split(' · ').pop()}</b> · {t.metric === 'score' ? '得分提升' : '提速'} · {rmode(best!.mode).label}组</div>
          </div>
        )
      })}
      <div className="cap muted">{b.finalEnabled === false ? '开发集最佳结果' : '研究结束时保留的结果'}</div>
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
