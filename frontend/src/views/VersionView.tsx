import { useState } from 'react'
import { api } from '../api'
import { Chip, Empty } from '../components/ui'
import { usePoll } from '../hooks'
import { OUTCOME, fmt } from '../labels'

export function VersionView({ onOpenSnapshot, onOpenRun, onChanged }: {
  onOpenSnapshot: (id: string) => void
  onOpenRun: (id: string) => void
  onChanged: () => void
}) {
  const snaps = usePoll(api.snapshots, [], 3000)
  const [sel, setSel] = useState<string | null>(null)
  const [base, setBase] = useState('v0')
  const [reason, setReason] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const active = snaps.data?.active_snapshot_id ?? 'v0'
  const selected = sel ?? active
  const diff = usePoll(() => api.diff(base, selected), [base, selected], 0, false)
  const rows = snaps.data?.snapshots ?? []
  const node = rows.find((r) => r.snapshot_id === selected)

  const activate = async () => {
    setMsg(null)
    try {
      const ver = (id: string) => rows.find((r) => r.snapshot_id === id)?.version ?? 0
      const r = await api.activate(selected, reason || (ver(selected) < ver(active) ? '回退' : '切换'))
      setMsg({ ok: true, text: `生效版本 ${r.from} → ${r.to}。之后的运行读取 ${r.to}；历史记录与正在运行的任务不受影响。` })
      setReason('')
      snaps.refresh()
      onChanged()
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }) }
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="spread"><h2>版本链</h2><span className="small muted">点击版本查看；朱红标记为当前生效版本</span></div>
        <div className="lineage">
          {rows.map((s, i) => (
            <div key={s.snapshot_id} style={{ display: 'flex', alignItems: 'center' }}>
              {i > 0 && <div className={`edge ${s.parent_snapshot_id !== rows[i - 1].snapshot_id ? 'branch' : ''}`} title={`父版本 ${s.parent_snapshot_id}`} />}
              <div className={`node ${s.snapshot_id === selected ? 'sel' : ''} ${s.snapshot_id === active ? 'active' : ''}`} onClick={() => setSel(s.snapshot_id)}>
                {s.snapshot_id === active && <span className="flagpin">生效</span>}
                <div className="disc">{s.snapshot_id}</div>
                <div className="cap">{s.experience_count} 条{s.parent_snapshot_id && s.parent_snapshot_id !== rows[i - 1]?.snapshot_id ? ` · 父 ${s.parent_snapshot_id}` : ''}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          {node ? (
            <>
              <div className="eyebrow">版本详情</div>
              <h2 style={{ fontFamily: 'var(--f-sans)', fontSize: 40, fontWeight: 700, margin: '0 0 6px' }}>{node.snapshot_id}</h2>
              <dl className="kv">
                <dt>父版本</dt><dd>{node.parent_snapshot_id ?? '—（初始空快照）'}</dd>
                <dt>来源运行</dt><dd>{node.source_run_id ? <button className="link mono" onClick={() => onOpenRun(node.source_run_id!)}>{node.source_run_id}</button> : '—'}</dd>
                <dt>创建时间</dt><dd>{new Date(node.created_at).toLocaleString('zh-CN', { hour12: false })}</dd>
                <dt>经验条数</dt><dd>{node.experience_count}</dd>
              </dl>
              {(node.diff.added ?? []).length > 0 && (
                <>
                  <hr className="rule" />
                  <div className="eyebrow">相对父版本新增</div>
                  <table className="tbl"><tbody>{node.diff.added!.map((a) => {
                    const [label, tone, icon] = OUTCOME[a.outcome] ?? [a.outcome, 'neutral', '']
                    return <tr key={a.experience_id}><td><Chip tone={tone} icon={icon}>{label}</Chip></td><td>{a.task_id}</td><td>{a.speedup != null ? fmt.x(a.speedup) : a.status}</td></tr>
                  })}</tbody></table>
                </>
              )}
              <div className="row" style={{ marginTop: 14 }}>
                <button className="btn" onClick={() => onOpenSnapshot(node.snapshot_id)}>查看全部经验</button>
              </div>
            </>
          ) : <Empty title="选择一个版本" />}
        </div>

        <div className="card">
          <h3>切换 / 回退生效版本</h3>
          <p className="small muted" style={{ marginTop: -6 }}>只改变之后的运行读取哪个快照。所有版本、经验和运行记录都保留；正在执行的任务不受影响；学习运行进行中时不能切换。</p>
          <div className="row" style={{ alignItems: 'stretch' }}>
            <div style={{ flex: 1 }}><input type="text" placeholder="原因（例如：新经验在 B 上退化，回退验证）" value={reason} onChange={(e) => setReason(e.target.value)} /></div>
            <button className="btn accent" disabled={selected === active} onClick={activate}>设 {selected} 为生效版本</button>
          </div>
          {msg && <div className={msg.ok ? 'note' : 'error'} style={{ marginTop: 12 }}>{msg.text}</div>}
          <hr className="rule" />
          <div className="spread">
            <h3 style={{ margin: 0 }}>版本差异</h3>
            <label className="row small">对比基准
              <select value={base} onChange={(e) => setBase(e.target.value)} style={{ width: 90 }}>
                {rows.map((r) => <option key={r.snapshot_id}>{r.snapshot_id}</option>)}
              </select> → {selected}
            </label>
          </div>
          {diff.data && (
            <p className="small">新增 <b>{diff.data.added.length}</b> 条 · 移除 <b>{diff.data.removed.length}</b> 条 · 共有 {diff.data.common} 条
              {diff.data.added.length > 0 && <span className="muted">：{diff.data.added.slice(0, 6).map((e) => e.slice(-6)).join('、')}{diff.data.added.length > 6 ? '…' : ''}</span>}
            </p>
          )}
          <hr className="rule" />
          <h3>指针历史</h3>
          <table className="tbl">
            <thead><tr><th>时间</th><th>变化</th><th>操作者</th><th>原因</th></tr></thead>
            <tbody>{(snaps.data?.pointer_history ?? []).slice(0, 8).map((h) => (
              <tr key={h.id}><td>{fmt.time(h.ts)}</td><td>{h.from_snapshot_id} → <b>{h.to_snapshot_id}</b></td><td>{({ learning: '学习发布', api: '界面', cli: '命令行', user: '用户' } as Record<string, string>)[h.actor] ?? h.actor}</td><td className="small">{h.reason}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
