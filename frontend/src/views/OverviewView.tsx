import { api } from '../api'
import type { Comparison, SideSummary, Stream } from '../api'
import { SessionCard } from '../components/SessionCard'
import { Chip, Empty } from '../components/ui'
import { usePoll } from '../hooks'
import { ROUTE, STOP, fmt } from '../labels'

/* The first screen for judges: what was learned, what the held-out comparisons show, and where the evidence is. */
export function OverviewView({ onOpenRun, onOpenComparison }: { onOpenRun: (id: string) => void; onOpenComparison: (id: string) => void }) {
  const runs = usePoll(() => api.runs(), [], 5000)
  const list = usePoll(api.comparisons, [], 5000)
  const snaps = usePoll(api.snapshots, [], 5000)
  const pick = (p: string) => list.data?.find((c) => (c.label ?? '').startsWith(p))?.comparison_id ?? null
  const bId = pick('B'), cId = pick('C'), dId = pick('D')
  const running = (id: string | null) => list.data?.find((x) => x.comparison_id === id)?.status === 'running'
  const sId = list.data?.find((c) => c.kind === 'stream' && (c.label ?? '').startsWith('S online'))?.comparison_id ?? null
  const st = usePoll(() => (sId ? api.stream(sId) : Promise.resolve(null)), [sId], 8000, running(sId))
  const sNote = usePoll(() => (sId ? api.note(sId) : Promise.resolve(null)), [sId, st.data?.finished_runs], 10000, false)
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
        <StreamStrip s={st.data} onOpen={onOpenComparison} />
        <div className="card" style={{ borderTop: '3px solid var(--accent)' }}>
          <div className="eyebrow">记忆带来的变化 · 由任务流数据自动填写</div>
          {sNote.data ? (
            <ol style={{ margin: '6px 0 0', paddingLeft: 22, fontSize: 15, lineHeight: 1.65 }}>
              {sNote.data.lines.map((l) => <li key={l} style={{ marginBottom: 8 }}>{l}</li>)}
            </ol>
          ) : <Empty title="任务流完成后自动生成" />}
        </div>
      </div>
      <RouterCard />
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

function StreamStrip({ s, onOpen }: { s: Stream | null; onOpen: (id: string) => void }) {
  const title = 'S 任务流 · 分流器 + 记忆 · 3 个任务族（封存，配置冻结后运行）'
  if (!s) return <div className="card"><div className="eyebrow">{title}</div><Empty title="尚未运行" /></div>
  const F = s.sides.fresh, M = s.sides.memory
  const tiles: [string, string, string][] = F && M && M.runs ? [
    ['达标', `${F.goal_met}/${F.runs}`, `${M.goal_met}/${M.runs}`],
    ['大模型请求', String(F.large_model_requests_total ?? 0), String(M.large_model_requests_total ?? 0)],
    ['模型费用', fmt.usd(F.cost_usd_total), fmt.usd(M.cost_usd_total)],
    ['未调用模型的运行', `${F.runs_without_model_request ?? 0}`, `${M.runs_without_model_request ?? 0}`],
    ['总耗时', fmt.s(F.wall_clock_s_total), fmt.s(M.wall_clock_s_total)],
    ['最终加速比中位数', fmt.x(F.final_speedup_median), fmt.x(M.final_speedup_median)],
  ] : []
  return (
    <div className="card">
      <div className="spread">
        <div>
          <div className="eyebrow">{title}</div>
          <h3 style={{ margin: 0 }}>从 {s.start_snapshot} 出发 · {s.tasks.length} 任务 × {s.repeats} 次重放 · 已完成 {s.finished_runs}/{s.planned_runs}</h3>
        </div>
        <div className="row">
          <Chip tone={s.fair ? 'good' : 'bad'} icon={s.fair ? '✓' : '✕'}>{s.fair ? '配置一致' : '配置不一致'}</Chip>
          {s.status === 'running' && <Chip tone="accent" icon="●">运行中</Chip>}
          <button className="link" onClick={() => onOpen(s.comparison_id)}>逐任务详情</button>
        </div>
      </div>
      {tiles.length > 0 && (
        <div className="stats" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', marginTop: 16 }}>
          {tiles.map(([k, a, b]) => (
            <div key={k} className="stat">
              <div className="k">{k}</div>
              <div className="v" style={{ fontSize: 26 }}>{b}</div>
              <div className="s"><span style={{ color: 'var(--series-old)' }}>●</span> 不带记忆 {a} → <span style={{ color: 'var(--series-new)' }}>●</span> 带记忆 {b}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* The routing rule as a boundary table: every run takes exactly one of these paths, decided by the program. */
function RouterCard() {
  const rows: [string, string, string, string][] = [
    ['reuse', '经验里有同族已验证程序，在本任务上复验达标', '不调用模型，直接交付', '复验结果写入经验（程序在新条件下仍成立）'],
    ['familiar', '复验未达标，但有同族成功经验与本任务 ≥ 3/5 项条件相同', '先用本地小模型，连续未达标按规则升级到大模型', '验证过的候选写入经验'],
    ['new_family', '经验里没有这个任务族的任何记录', '直接交给大模型', '首次结果写入经验，下次同类任务先复用'],
    ['new_conditions', '有同族记录，但没有条件相近的成功经验', '直接交给大模型', '同上'],
  ]
  return (
    <div className="card">
      <div className="spread">
        <div>
          <div className="eyebrow">分流器 · 每次运行只走其中一条路线，由程序按经验覆盖情况决定，不由模型自评</div>
          <h3 style={{ margin: 0 }}>熟悉的复用，相近的交给本地小模型，全新的直接交给大模型，做完都记下来</h3>
        </div>
      </div>
      <table className="tbl" style={{ marginTop: 12 }}>
        <thead><tr><th>路线</th><th>条件</th><th>做法</th><th>留下什么</th></tr></thead>
        <tbody>{rows.map(([k, when, act, keep]) => (
          <tr key={k}><td><Chip tone={ROUTE[k][1]}>{ROUTE[k][0]}</Chip></td><td className="small">{when}</td><td className="small">{act}</td><td className="small">{keep}</td></tr>
        ))}</tbody>
      </table>
      <p className="small muted" style={{ marginBottom: 0 }}>
        评测模式只读经验、不写入；在线模式交付后写入；学习模式在已知最佳之上继续超越。留出任务不能写经验，读过的经验与任务来源分开校验。
      </p>
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
