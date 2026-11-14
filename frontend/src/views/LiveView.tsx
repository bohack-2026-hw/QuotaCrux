import { api } from '../api'
import type { Report, Step } from '../api'
import { BatchBadges, CostText, FinalChip, ModeMark, ProgressChart } from '../components/research'
import { Empty, Meter } from '../components/ui'
import { usePoll } from '../hooks'
import { ACTION, STUDY, fmt, rmode, status as statusLabel } from '../labels'
import type { RawBatch, RawRun, RBatch, RRun, RTask } from '../research'
import { normalize } from '../research'
import { metricText, resultOf } from '../researchFormat'
import { useResearchBatch, useResearchList } from '../researchData'
import type { BatchEntry } from '../researchData'

/* Live: the research batch that is running (or the latest one), as a task × repeat × group matrix, and the run that
   is executing right now with its budget, best-so-far curve and latest steps. Reads only; starts nothing. */
export function LiveView({ onOpenRun, onOpenResearch }: { onOpenRun: (id: string) => void; onOpenResearch: (id: string) => void }) {
  const { entries } = useResearchList()
  const live = usePoll(api.live, [], 2000)
  const running = entries.filter((e) => e.status === 'running')
  const shown = running.length ? running : entries.slice(0, 1)
  const runId = live.data?.run?.run_id ?? null

  return (
    <div className="stack">
      <CurrentRun runId={runId} elapsed={live.data?.run?.elapsed_s ?? null} offline={!!live.error} onOpenRun={onOpenRun} />
      {shown.map((e) => <BatchLive key={e.id} entry={e} runId={runId} onOpenRun={onOpenRun} onOpenResearch={onOpenResearch} />)}
      {!shown.length && <div className="card"><Empty title="没有研究批次" /></div>}
    </div>
  )
}

/* ---------- the run executing now ---------- */

function CurrentRun({ runId, elapsed, offline, onOpenRun }: { runId: string | null; elapsed: number | null; offline: boolean; onOpenRun: (id: string) => void }) {
  const rep = usePoll(() => (runId ? api.run(runId) : Promise.resolve(null)), [runId], 2000, !!runId)
  if (!runId) {
    return (
      <div className="live-idle">
        <span className={`pulse ${offline ? 'off' : 'idle'}`} />
        <b>{offline ? '后端未连接' : '空闲'}</b>
        <span className="muted mono small">{offline ? '无法读取正在执行的运行' : '当前没有运行在执行'}</span>
      </div>
    )
  }
  const r = rep.data
  if (!r) return <div className="card"><Empty title="读取运行中…" /></div>
  const L = r.config.limits
  const it = r.iterations
  const loop = r.timing.agent_loop_elapsed_s ?? elapsed ?? 0
  const task = taskFromReport(r)
  const mode = r.config.research_protocol?.mode ?? r.mode
  const best = task.runs[0]?.dev
  return (
    <section className="card live-run">
      <div className="head-row">
        <span className="pulse" />
        <span className="mono small muted">正在执行</span>
        <h2 style={{ margin: 0 }}>{task.title}</h2>
        {mode && <span className="mode-tag"><ModeMark mode={mode} />{rmode(mode).label}</span>}
        <button className="link mono" style={{ marginLeft: 'auto' }} onClick={() => onOpenRun(r.run_id)}>{r.run_id}</button>
      </div>
      <div className="live-run-grid">
        <div>
          <div className="live-best">
            <div className="k">开发集当前最佳</div>
            <div className={`v ${best?.improved ? 'gain-text' : ''}`}>{metricText(task.metric, best?.value ?? null)}</div>
            <div className="mono small muted">{best?.candidate ?? '—'}{best?.initial ? ' · 初始程序' : ''}</div>
          </div>
          <div className="meters live-meters">
            <Meter label="模型请求" value={it.model_requests ?? 0} max={L.max_model_requests} />
            <Meter label="候选" value={it.candidates_proposed ?? 0} max={L.max_candidates} />
            <Meter label="循环时长" value={Math.round(loop)} max={L.wall_clock_s} unit="s" hot={loop > L.wall_clock_s * 0.8} />
          </div>
        </div>
        <div style={{ minWidth: 0 }}>
          {task.runs[0]?.progress.length ? <ProgressChart task={task} axis="time" currency={null} height={180} />
            : <Empty title="等待首个有效候选" />}
        </div>
      </div>
      <Ticker steps={r.steps.slice(-6)} metric={task.metric} />
    </section>
  )
}

/** A running report as a one-run task, so the best-so-far curve and metric units match the research page. */
function taskFromReport(r: Report): RTask {
  // While a run is going, best_candidate is written only when its loop ends; the progress log already names the
  // candidate the selector keeps, so read the current best from there.
  const kept = r.best_candidate?.candidate_id ?? (r.progress ?? []).at(-1)?.best_candidate_id ?? null
  const bestCand = r.best_candidate ?? r.candidates.find((c) => c.candidate_id === kept) ?? null
  const best = bestCand?.dev_evaluations.at(-1) ?? null
  const raw: RawBatch = {
    comparison_id: r.run_id, status: 'running',
    runs: [{
      seq: 1, task_id: r.task.task_id, repeat: 1, mode: r.config.research_protocol?.mode ?? r.mode, run_id: r.run_id, status: r.status,
      task: { task_id: r.task.task_id, family: r.task.family ?? null, objective: r.task.objective },
      best_candidate_id: bestCand?.candidate_id ?? null,
      // Extend the best-so-far step line to now while the run is going, so a single kept candidate still shows.
      timing: { agent_loop_s: r.timing.agent_loop_s ?? r.timing.agent_loop_elapsed_s ?? null },
      best_dev: best ? { status: best.status, speedup: best.speedup, improved: best.improved, objective: best.objective ?? null } : null,
      progress: r.progress ?? [],
    } as RawRun],
  }
  const t = normalize(raw).tasks[0]
  const title = (r.task as { presentation?: { title?: string } }).presentation?.title
  return title ? { ...t, title } : t
}

function Ticker({ steps, metric }: { steps: Step[]; metric: string }) {
  if (!steps.length) return null
  return (
    <ol className="ticker">
      {[...steps].reverse().map((s) => {
        const res = s.result as { speedup?: number; objective?: { value?: number } }
        const value = metric === 'score' ? res.objective?.value : res.speedup
        const [label, tone] = statusLabel(s.status)
        return (
          <li key={s.seq}>
            <span className="mono muted">{String(s.seq).padStart(2, '0')}</span>
            <span className="who">{s.actor === 'model' ? '模型' : '程序'}</span>
            <b>{ACTION[s.action] ?? s.action}</b>
            {s.candidate_id && <span className="tag">{s.candidate_id}</span>}
            <span className={`st ${tone}`}>{label}</span>
            {typeof value === 'number' && <span className="mono">{metricText(metric, value)}</span>}
          </li>
        )
      })}
    </ol>
  )
}

/* ---------- the batch: one cell per planned run ---------- */

function BatchLive({ entry, runId, onOpenRun, onOpenResearch }: { entry: BatchEntry; runId: string | null; onOpenRun: (id: string) => void; onOpenResearch: (id: string) => void }) {
  const { batch: b } = useResearchBatch(entry)
  if (!b) return null
  const done = b.runs.filter((r) => r.state !== 'planned' && r.state !== 'running')
  const walls = done.map((r) => r.wallS).filter((v): v is number => v != null)
  const avg = walls.length ? walls.reduce((a, v) => a + v, 0) / walls.length : null
  const remaining = b.runs.filter((r) => r.state === 'planned' || r.state === 'running').length
  return (
    <section className="card">
      <div className="spread wrap">
        <div className="head-row">
          <span className="metric-pill">{STUDY[b.study]}</span>
          <h2 style={{ margin: 0 }}>{b.label ?? b.id}</h2>
        </div>
        <button className="btn" onClick={() => onOpenResearch(b.id)}>研究对照 →</button>
      </div>
      <div className="live-progress">
        <div className="bar"><i style={{ width: `${b.planned ? (done.length / b.planned) * 100 : 0}%` }} /></div>
        <div className="metaline">
          <span>完成 <b>{done.length}/{b.planned}</b></span>
          {b.running && avg != null && <span>预计剩余 <b>{fmt.s(avg * remaining)}</b></span>}
          {avg != null && <span>单轮平均 <b>{fmt.s(avg)}</b></span>}
          <BatchBadges b={b} />
        </div>
      </div>
      {b.tasks.map((t) => <Matrix key={t.id} t={t} b={b} runId={runId} onOpenRun={onOpenRun} />)}
      <div className="legend" style={{ marginTop: 12 }}>
        <span><i className="dot planned" />计划</span><span><i className="dot running" />进行中</span>
        <span><i className="dot done" />完成</span><span><i className="dot bad" />失败 / 中断</span>
      </div>
    </section>
  )
}

function Matrix({ t, b, runId, onOpenRun }: { t: RTask; b: RBatch; runId: string | null; onOpenRun: (id: string) => void }) {
  const groups = b.modes.filter((m) => t.modes.includes(m))
  return (
    <div className="matrix">
      <div className="matrix-title"><b>{t.title}</b><span className="mono small muted">{t.metric === 'score' ? '原始得分' : '加速比'} · {t.source === 'final' ? '最终集' : '开发集'}</span></div>
      <div className="tbl-wrap">
        <table className="matrix-grid">
          <thead><tr><th />{groups.map((g) => <th key={g}><span className="mode-tag"><ModeMark mode={g} />{rmode(g).label}</span></th>)}</tr></thead>
          <tbody>{t.repeats.map((rep) => (
            <tr key={rep}>
              <th className="mono">r{rep}</th>
              {groups.map((g) => {
                const r = t.runs.find((x) => x.mode === g && x.repeat === rep)
                return <td key={g}>{r ? <Cell r={r} t={t} now={r.runId != null && r.runId === runId} onOpenRun={onOpenRun} /> : <span className="muted">—</span>}</td>
              })}
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}

function Cell({ r, t, now, onOpenRun }: { r: RRun; t: RTask; now: boolean; onOpenRun: (id: string) => void }) {
  const state = now || r.state === 'running' ? 'running' : r.state === 'planned' ? 'planned' : r.state === 'completed' ? 'done' : 'bad'
  const open = r.runId ? () => onOpenRun(r.runId!) : undefined
  // Same figure as the scoreboard: the final score once the task reports finals, else the dev best.
  const res = resultOf(t, r)
  return (
    <button className={`mcell ${state}`} onClick={open} disabled={!open} title={r.runId ?? '计划中'}>
      {state === 'planned' ? <span className="muted">计划</span>
        : state === 'running' ? <span className="mono">进行中</span>
        : <>
            <span className={`mono v ${res.improved ? 'up' : ''}`}>{metricText(t.metric, res.value)}</span>
            <span className="row" style={{ gap: 6 }}><FinalChip run={r} /><span className="mono small muted"><CostText c={r.cost} /></span></span>
          </>}
    </button>
  )
}
