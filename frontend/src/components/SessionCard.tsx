import { useState } from 'react'
import { api } from '../api'
import { usePoll } from '../hooks'
import { Chip } from './ui'

/* 日新 two-round demo: learn on one task, auto-publish, compare an unseen task under base vs new snapshot. */
export function SessionCard({ onOpenRun, onOpenComparison }: { onOpenRun: (id: string) => void; onOpenComparison: () => void }) {
  const tasks = usePoll(api.tasks, [], 0, false)
  const sessions = usePoll(api.sessions, [], 2500)
  const snaps = usePoll(api.snapshots, [], 5000)
  const [learn, setLearn] = useState('A-01')
  const [evalTask, setEval] = useState('B-01')
  const [base, setBase] = useState('v0')
  const [err, setErr] = useState<string | null>(null)
  const s = sessions.data?.[0]
  const live = s?.status === 'running'

  const start = async () => {
    setErr(null)
    try { await api.startSession({ learn_task: learn, eval_task: evalTask, base_snapshot_id: base }); sessions.refresh() }
    catch (e) { setErr((e as Error).message) }
  }
  const phases: [string, string, boolean][] = s ? [
    ['round1_learning', `第一轮：${s.learn_task} 学习（读 ${s.base_snapshot_id}）`, !!s.learn_run_id],
    ['publishing', `自动发布 ${s.new_snapshot_id ?? '新版本'}`, !!s.new_snapshot_id],
    ['round2_comparison', `第二轮：${s.eval_task} 在 ${s.base_snapshot_id} 与 ${s.new_snapshot_id ?? '新版本'} 下各跑一次`, !!s.comparison_id],
    ['done', '进化说明与回退', s.phase === 'done'],
  ] : []
  const order = ['created', 'round1_learning', 'publishing', 'round2_comparison', 'done']

  return (
    <div className="card">
      <div className="spread">
        <div>
          <div className="eyebrow">两轮现场演示 · 中间不改代码、参数或提示词</div>
          <h3 style={{ margin: 0 }}>学习一个任务 → 自动发布 → 在没见过的任务上对照</h3>
        </div>
        {s && <Chip tone={s.status === 'completed' ? 'good' : s.status === 'failed' ? 'bad' : 'accent'}>{s.status === 'running' ? '进行中' : s.status === 'completed' ? '完成' : '失败'}</Chip>}
      </div>
      <div className="row" style={{ marginTop: 14 }}>
        <label className="row small">第一轮
          <select value={learn} onChange={(e) => setLearn(e.target.value)} style={{ width: 100 }}>
            {(tasks.data ?? []).filter((t) => t.split === 'A').map((t) => <option key={t.task_id}>{t.task_id}</option>)}
          </select>
        </label>
        <label className="row small">第二轮
          <select value={evalTask} onChange={(e) => setEval(e.target.value)} style={{ width: 100 }}>
            {(tasks.data ?? []).filter((t) => t.split === 'B' || t.split === 'C').map((t) => <option key={t.task_id}>{t.task_id}</option>)}
          </select>
        </label>
        <label className="row small">基础快照
          <select value={base} onChange={(e) => setBase(e.target.value)} style={{ width: 80 }}>
            {(snaps.data?.snapshots ?? []).map((x) => <option key={x.snapshot_id}>{x.snapshot_id}</option>)}
          </select>
        </label>
        <button className="btn primary" disabled={live} onClick={start}>开始两轮演示</button>
      </div>
      {err && <div className="error small" style={{ marginTop: 10 }}>{err}</div>}
      {s && (
        <ol style={{ margin: '14px 0 0', paddingLeft: 20, lineHeight: 1.9 }}>
          {phases.map(([id, label, done]) => {
            const current = live && s.phase === id
            return (
              <li key={id} style={{ color: done || current ? 'var(--ink)' : 'var(--ink-3)', fontWeight: current ? 700 : 400 }}>
                {done ? '✓ ' : current ? '● ' : ''}{label}
                {id === 'round1_learning' && s.learn_run_id && <button className="link" style={{ marginLeft: 8 }} onClick={() => onOpenRun(s.learn_run_id!)}>查看第一轮</button>}
                {id === 'round2_comparison' && s.comparison_id && <button className="link" style={{ marginLeft: 8 }} onClick={onOpenComparison}>查看对照</button>}
                {id === 'done' && order.indexOf(s.phase) >= 4 && <span className="small muted">（对照页显示三行说明；版本页可回退到 {s.base_snapshot_id}）</span>}
              </li>
            )
          })}
        </ol>
      )}
      {s?.detail && <p className="small muted">{s.detail.split('\n')[0]}</p>}
    </div>
  )
}
