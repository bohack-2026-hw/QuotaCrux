import { useState } from 'react'
import { AxisSwitch, BatchBadges, CostTotal, ModeLegend, ProgressChart, Scoreboard } from '../components/research'
import type { Axis } from '../components/research'
import { Empty } from '../components/ui'
import { fmt, rmode } from '../labels'
import type { RBatch, RTask } from '../research'
import { familyName, sumText, taskVerdict } from '../researchFormat'
import { useResearchBatch, useResearchList } from '../researchData'

/* The roadshow screen: one claim, the latest batch's numbers per task, and how they got there. Everything else is one
   click away on the research page. */
export function HomeView({ onOpenResearch }: { onOpenResearch: (id: string) => void }) {
  const { entries } = useResearchList()
  const entry = entries[0] ?? null
  const { batch: b } = useResearchBatch(entry)
  const [axis, setAxis] = useState<Axis>('time')

  return (
    <div>
      <section className="hero">
        <span className="kicker"><span className={`pulse ${b?.running ? '' : 'idle'}`} />单任务长程研究 · {b ? `${b.tasks.length} 个任务 · ${b.runs.length} 轮` : '载入中'}</span>
        <h1>固定预算下，<span className="dim">Agent 能不能把</span>一个任务越做越好？</h1>
        <p className="lede">模型、提示、预算和评测器全部固定，只改变 Agent 能看到什么：每一轮的评测反馈、只看初始程序，或看不到任何结果。</p>
        {b && (
          <div className="row">
            <BatchBadges b={b} />
            <button className="btn primary" onClick={() => onOpenResearch(b.id)} style={{ marginLeft: 'auto' }}>逐题对照 →</button>
          </div>
        )}
      </section>

      {!b ? <div className="card"><Empty title="还没有研究批次" /></div> : (
        <>
          <div className="spread wrap" style={{ margin: '28px 0 12px' }}>
            <div className="row" style={{ gap: 14 }}>
              <ModeLegend modes={b.modes} repeats={[]} />
            </div>
            <AxisSwitch axis={axis} setAxis={setAxis} costOk={b.runs.some((r) => r.progress.some((p) => p.cost != null))} />
          </div>
          <div className="board">
            {b.tasks.map((t) => <TaskCard key={t.id} t={t} b={b} axis={axis} />)}
          </div>
          <BatchLine b={b} />
        </>
      )}
    </div>
  )
}

function TaskCard({ t, b, axis }: { t: RTask; b: RBatch; axis: Axis }) {
  const v = taskVerdict(t, (m) => `${rmode(m).label}组`)
  return (
    <div className="card task-card">
      <div className="head">
        <h2>{t.title}</h2>
        <span className="mono small muted">{familyName(t.family)} · {t.metric === 'score' ? '原始得分 ↑' : '加速比 ↑'}</span>
      </div>
      <p className="verdict">{v.text}</p>
      <Scoreboard task={t} lead={v.lead} planned={b.modes} />
      <ProgressChart task={t} axis={axis} currency={b.pricing?.currency ?? null} height={190} />
    </div>
  )
}

function BatchLine({ b }: { b: RBatch }) {
  const L = b.limits
  return (
    <div className="metaline" style={{ marginTop: 20 }}>
      <span>模型 <b>{b.model?.name ?? '未记录'}</b></span>
      {L && <span>每轮上限 <b>{L.wall_clock_s}s · {L.max_model_requests} 次请求 · {L.max_candidates} 个候选</b></span>}
      <span>实耗 <b>{sumText(b.runs.map((r) => r.requests), String)} 次请求 · {sumText(b.runs.map((r) => r.wallS), (x) => fmt.s(x))}</b></span>
      <span>费用 <b><CostTotal costs={b.runs.map((r) => r.cost)} /></b>{b.pricing ? '（标价估算）' : ''}</span>
      {b.codeCommit && <span>代码 <b>{b.codeCommit.slice(0, 7)}</b></span>}
    </div>
  )
}
