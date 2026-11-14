import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Experience } from '../api'
import { Chip, DiffView, Empty } from '../components/ui'
import { usePoll } from '../hooks'
import { OUTCOME, fmt, roleName, status } from '../labels'

export function ExperienceView({ snapshotId, setSnapshotId, focus, onOpenRun }: {
  snapshotId: string
  setSnapshotId: (s: string) => void
  focus: string | null
  onOpenRun: (runId: string) => void
}) {
  const snaps = usePoll(api.snapshots, [], 5000)
  const snap = usePoll(() => api.snapshot(snapshotId), [snapshotId], 5000)
  const [filter, setFilter] = useState<'all' | 'success' | 'no_gain' | 'failure'>('all')
  const added = new Set((snap.data?.diff.added ?? []).map((a) => a.experience_id))

  useEffect(() => {
    if (focus) document.getElementById(`exp-${focus}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [focus, snap.data])

  const list = (snap.data?.experiences ?? []).filter((e) => filter === 'all' || e.outcome === filter)
  return (
    <div className="stack">
      <div className="card">
        <div className="spread">
          <div className="row">
            <span className="eyebrow" style={{ margin: 0 }}>快照</span>
            <div className="seg">
              {snaps.data?.snapshots.map((s) => (
                <button key={s.snapshot_id} className={s.snapshot_id === snapshotId ? 'on' : ''} onClick={() => setSnapshotId(s.snapshot_id)}>
                  {s.snapshot_id}{s.snapshot_id === snaps.data?.active_snapshot_id ? ' ●' : ''}
                </button>
              ))}
            </div>
          </div>
          <div className="seg">
            {(['all', 'success', 'no_gain', 'failure'] as const).map((k) => (
              <button key={k} className={filter === k ? 'on' : ''} onClick={() => setFilter(k)}>
                {k === 'all' ? '全部' : OUTCOME[k][0]} {k === 'all' ? snap.data?.experiences.length ?? 0 : snap.data?.counts[k] ?? 0}
              </button>
            ))}
          </div>
        </div>
        {snap.data && (
          <p className="small muted" style={{ marginBottom: 0 }}>
            {snap.data.snapshot_id} 共 {snap.data.experiences.length} 条经验
            {snap.data.parent_snapshot_id && <>，父版本 {snap.data.parent_snapshot_id}，本版新增 {added.size} 条（标记 <span className="tag diff">新增</span>）</>}
            {snap.data.source_run_id && <>，来自学习运行 <button className="link mono" onClick={() => onOpenRun(snap.data!.source_run_id!)}>{snap.data.source_run_id}</button></>}
            。经验由程序从已验证的执行记录中提取；模型的解释单独标为未验证。
          </p>
        )}
      </div>
      {list.length === 0 ? <div className="card"><Empty title={snapshotId === 'v0' ? 'v0 是空的初始快照' : '没有符合筛选的经验'}>学习模式运行结束后，合格记录会自动发布为新版本。</Empty></div> : (
        <div className="exp-grid">
          {list.map((e) => <ExperienceCard key={e.experience_id} e={e} isNew={added.has(e.experience_id)} focused={focus === e.experience_id} onOpenRun={onOpenRun} />)}
        </div>
      )}
    </div>
  )
}

function ExperienceCard({ e, isNew, focused, onOpenRun }: { e: Experience; isNew: boolean; focused: boolean; onOpenRun: (id: string) => void }) {
  const [open, setOpen] = useState(false)
  const [label, tone, icon] = OUTCOME[e.outcome]
  const [st] = status(e.result.status)
  const ex = e.result.failure_example as Record<string, unknown> | string | null
  return (
    <div id={`exp-${e.experience_id}`} className={`card exp ${e.outcome}`} style={focused ? { outline: '3px solid var(--accent)' } : undefined}>
      <div className="spread">
        <div className="row"><Chip tone={tone} icon={icon}>{label}</Chip>{isNew && <span className="tag diff">新增</span>}<b>{e.conditions.task_id}</b></div>
        <span className="id">{e.experience_id}</span>
      </div>
      <div className="claim">
        在 <b>{e.conditions.workload}</b> 的数据上，
        {e.result.speedup != null
          ? <>实测加速比 <b>{fmt.x(e.result.speedup)}</b>{e.result.improved ? '，全部样本快于基线' : '，与基线重叠，不计改善'}。</>
          : <>验证结果为 <b>{st}</b>{e.result.failure_kinds ? `（${e.result.failure_kinds.join('、')}）` : ''}。</>}
      </div>
      {ex && <p className="small" style={{ color: '#8e2424', margin: '4px 0' }}>反例：{typeof ex === 'string' ? ex.slice(0, 160) : `期望 ${String(ex.expected)}，得到 ${String(ex.got)}`}</p>}
      {e.hypothesis && <p className="why">{e.hypothesis}</p>}
      <dl className="kv">
        <dt>改动特征</dt><dd>{(e.action.code_features.calls ?? []).slice(0, 10).map((c) => <span key={c} className="tag mono" style={{ marginRight: 4 }}>{c}</span>)}</dd>
        <dt>资源</dt><dd className="small">{roleName(e.resources.model_role ?? undefined)} · 输出 {fmt.n(e.resources.output_tokens)} token · {fmt.s(e.resources.latency_s)}{e.resources.cost_usd ? ` · ${fmt.usd(e.resources.cost_usd)}` : ''}</dd>
        <dt>来源</dt><dd className="small"><button className="link mono" onClick={() => onOpenRun(e.source.run_id)}>{e.source.run_id}</button> · 第 {e.source.step_seq} 步 · {e.source.candidate_id} · 评测 {e.source.evaluation_id}</dd>
      </dl>
      <div style={{ marginTop: 10 }}>
        <button className="link" onClick={() => setOpen(!open)}>{open ? '收起改动' : '查看相对初始程序的改动'}</button>
        {open && <div style={{ marginTop: 8 }}><DiffView diff={e.action.diff_vs_initial} /></div>}
      </div>
    </div>
  )
}
