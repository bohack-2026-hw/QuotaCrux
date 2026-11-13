import { api } from '../api'
import type { Comparison, SideSummary } from '../api'
import { SessionCard } from '../components/SessionCard'
import { Chip, Empty } from '../components/ui'
import { usePoll } from '../hooks'
import { STOP, fmt } from '../labels'

/* The first screen for judges: what was learned, what the held-out comparisons show, and where the evidence is. */
export function OverviewView({ onOpenRun, onOpenComparison }: { onOpenRun: (id: string) => void; onOpenComparison: (id: string) => void }) {
  const runs = usePoll(() => api.runs(), [], 5000)
  const list = usePoll(api.comparisons, [], 5000)
  const snaps = usePoll(api.snapshots, [], 5000)
  const pick = (p: string) => list.data?.find((c) => (c.label ?? '').startsWith(p))?.comparison_id ?? null
  const bId = pick('B'), cId = pick('C'), dId = pick('D')
  const running = (id: string | null) => list.data?.find((x) => x.comparison_id === id)?.status === 'running'
  const b = usePoll(() => (bId ? api.comparison(bId) : Promise.resolve(null)), [bId], 8000, running(bId))
  const c = usePoll(() => (cId ? api.comparison(cId) : Promise.resolve(null)), [cId], 8000, running(cId))
  const d = usePoll(() => (dId ? api.comparison(dId) : Promise.resolve(null)), [dId], 8000, running(dId))
  // The note follows the current configuration: the sealed D comparison once it has runs, else its B comparison.
  const noteFor = dId && d.data?.finished_runs ? dId : bId
  const note = usePoll(() => (noteFor ? api.note(noteFor) : Promise.resolve(null)), [noteFor, d.data?.finished_runs], 10000, false)
  // The learned snapshot is the one the held-out comparison used; a live demo session may have published a newer branch.
  const learnedId = b.data?.snapshot_b ?? snaps.data?.active_snapshot_id
  const latest = snaps.data?.snapshots.find((x) => x.snapshot_id === learnedId)
  // The learning runs that built the learned snapshot: walk its parent chain back to v0.
  const chain: string[] = []
  for (let cur = learnedId; cur;) {
    const row = snaps.data?.snapshots.find((x) => x.snapshot_id === cur)
    if (!row) break
    if (row.source_run_id) chain.unshift(row.source_run_id)
    cur = row.parent_snapshot_id ?? undefined
  }
  const learn = chain.map((id) => runs.data?.find((r) => r.run_id === id)).filter((r): r is NonNullable<typeof r> => !!r)

  return (
    <div className="stack">
      <div className="grid cols-2">
        <div className="card">
          <div className="eyebrow">学习阶段 · A 批{learn.length > 6 ? ` · ${Math.ceil(learn.length / 6)} 轮` : ''}</div>
          <h2>v0 → {latest?.snapshot_id ?? '—'}：{latest?.experience_count ?? 0} 条已验证经验</h2>
          {learn.length === 0 ? <Empty title="还没有学习运行" /> : (
            <table className="tbl">
              <thead><tr><th>任务</th><th>读取</th><th>终止</th><th>发布</th><th /></tr></thead>
              <tbody>{learn.map((r) => (
                <tr key={r.run_id}>
                  <td><b>{r.task_id}</b></td><td>{r.snapshot_id}</td>
                  <td>{r.status === 'running' ? '运行中' : STOP[r.stop_reason ?? ''] ?? r.stop_reason}</td>
                  <td>{snaps.data?.snapshots.find((s) => s.source_run_id === r.run_id)?.snapshot_id ?? '—'}</td>
                  <td><button className="link" onClick={() => onOpenRun(r.run_id)}>查看决策</button></td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
        <div className="card" style={{ borderTop: '3px solid var(--accent)' }}>
          <div className="eyebrow">经验带来的变化 · 由对照数据自动填写</div>
          {note.data ? (
            <ol style={{ margin: '6px 0 0', paddingLeft: 22, fontSize: 16, lineHeight: 1.7 }}>
              {note.data.lines.map((l) => <li key={l} style={{ marginBottom: 8 }}>{l}</li>)}
            </ol>
          ) : <Empty title="对照完成后自动生成" />}
        </div>
      </div>
      {dId && <ComparisonStrip title="D 批 · 封存留出（复用已验证程序，配置冻结后一次性验收）" c={d.data} onOpen={onOpenComparison} />}
      <ComparisonStrip title={dId ? 'B 批 · 开发对照（复用已验证程序）' : 'B 批 · 开发对照'} c={b.data} onOpen={onOpenComparison} />
      <ComparisonStrip title={dId ? 'C 批 · 第一版（只有文字经验）的最终留出' : 'C 批 · 最终留出（配置冻结后一次性验收）'} c={c.data} onOpen={onOpenComparison} />
      <SessionCard onOpenRun={onOpenRun} onOpenComparison={onOpenComparison} />
    </div>
  )
}

function ComparisonStrip({ title, c, onOpen }: { title: string; c: Comparison | null; onOpen: (id: string) => void }) {
  if (!c) return <div className="card"><div className="eyebrow">{title}</div><Empty title="尚未运行" /></div>
  const A: SideSummary | undefined = c.sides[c.snapshot_a]
  const B: SideSummary | undefined = c.sides[c.snapshot_b]
  const tiles: [string, string, string][] = A && B ? [
    ['达标率', fmt.pct(A.success_rate), fmt.pct(B.success_rate)],
    ['最终加速比中位数', fmt.x(A.final_speedup_median), fmt.x(B.final_speedup_median)],
    ['模型请求中位数', String(A.model_requests_median ?? '—'), String(B.model_requests_median ?? '—')],
    ...(B.goal_met_from_reuse ? [['复用经验程序直接达标', `${A.goal_met_from_reuse ?? 0} 次`, `${B.goal_met_from_reuse} 次`] as [string, string, string]] : []),
    ['升级到 GPT', `${A.upgrades_total} 次`, `${B.upgrades_total} 次`],
    ['模型费用', fmt.usd(A.cost_usd_total), fmt.usd(B.cost_usd_total)],
    ['总耗时', fmt.s(A.wall_clock_s_total), fmt.s(B.wall_clock_s_total)],
  ] : []
  return (
    <div className="card">
      <div className="spread">
        <div>
          <div className="eyebrow">{title}</div>
          <h3 style={{ margin: 0 }}>{c.snapshot_a} → {c.snapshot_b} · {c.tasks.length} 任务 × {c.repeats} 次 · 已完成 {c.finished_runs}/{c.planned_runs}</h3>
        </div>
        <div className="row">
          <Chip tone={c.fair ? 'good' : 'bad'} icon={c.fair ? '✓' : '✕'}>{c.fair ? '配置一致' : '配置不一致'}</Chip>
          {c.status === 'running' && <Chip tone="accent" icon="●">运行中</Chip>}
          <button className="link" onClick={() => onOpen(c.comparison_id)}>逐任务详情</button>
        </div>
      </div>
      {tiles.length > 0 && (
        <div className="stats" style={{ gridTemplateColumns: 'repeat(6, minmax(0, 1fr))', marginTop: 16 }}>
          {tiles.map(([k, a, b]) => (
            <div key={k} className="stat">
              <div className="k">{k}</div>
              <div className="v" style={{ fontSize: 26 }}>{b}</div>
              <div className="s"><span style={{ color: 'var(--series-old)' }}>●</span> {c.snapshot_a} {a} → <span style={{ color: 'var(--series-new)' }}>●</span> {c.snapshot_b} {b}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
