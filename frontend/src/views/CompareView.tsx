import { useState } from 'react'
import { api } from '../api'
import type { Comparison, SideSummary } from '../api'
import { BehaviorPair } from '../components/BehaviorPair'
import { PairedDots } from '../components/charts'
import { Chip, Empty, StatusChip } from '../components/ui'
import { usePoll } from '../hooks'
import { STOP, fmt } from '../labels'

/* `selected` comes from the URL (#cmp/<id>) so a comparison can be linked directly; otherwise the newest is shown. */
export function CompareView({ selected, onSelect, onOpenRun }: { selected: string | null; onSelect: (id: string) => void; onOpenRun: (id: string) => void }) {
  const list = usePoll(api.comparisons, [], 4000)
  const snaps = usePoll(api.snapshots, [], 5000)
  const current = selected ?? list.data?.[0]?.comparison_id ?? null
  const live = list.data?.find((c) => c.comparison_id === current)?.status === 'running'
  const cmp = usePoll(() => (current ? api.comparison(current) : Promise.resolve(null)), [current], 4000, live)

  const latest = snaps.data?.active_snapshot_id ?? 'v0'
  const [split, setSplit] = useState<'B' | 'C'>('B')
  const [repeats, setRepeats] = useState(3)
  const [err, setErr] = useState<string | null>(null)
  const start = async () => {
    setErr(null)
    try {
      const tasks = [1, 2, 3, 4, 5, 6].map((i) => `${split}-0${i}`)
      const r = await api.startComparison({ task_ids: tasks, snapshot_a: 'v0', snapshot_b: latest, repeats, label: `${split} dashboard` })
      onSelect(r.comparison_id)
      list.refresh()
    } catch (e) { setErr((e as Error).message) }
  }

  return (
    <div className="grid cols-run">
      <div className="stack">
        <div className="card">
          <h2>发起对照</h2>
          <p className="small muted" style={{ marginTop: -6 }}>同一批留出任务、同一配置，只换经验快照；串行交替运行，不写入经验库。</p>
          <div className="field"><span>留出批次</span>
            <div className="seg">
              <button className={split === 'B' ? 'on' : ''} onClick={() => setSplit('B')}>B · 开发对照</button>
              <button className={split === 'C' ? 'on' : ''} onClick={() => setSplit('C')}>C · 最终留出</button>
            </div>
          </div>
          <label className="field"><span>重复次数（每任务每版本）</span>
            <input type="number" min={1} max={5} value={repeats} onChange={(e) => setRepeats(Number(e.target.value))} />
          </label>
          <p className="small">v0（无经验） 对比 <b>{latest}</b>，共 {6 * 2 * repeats} 次运行</p>
          <button className="btn primary block" onClick={start}>开始对照</button>
          {err && <div className="error small" style={{ marginTop: 12 }}>{err}</div>}
        </div>
        <div className="card">
          <h3>对照记录</h3>
          <div className="runlist">
            {(list.data ?? []).map((c) => (
              <button key={c.comparison_id} className={c.comparison_id === current ? 'on' : ''} onClick={() => onSelect(c.comparison_id)}>
                <div className="spread"><b>{c.label ?? c.tasks.join(' ')}</b><span>{c.status === 'running' ? '运行中' : c.status === 'completed' ? '完成' : c.status}</span></div>
                <div className="rid">{c.snapshot_a} vs {c.snapshot_b} · ×{c.repeats} · {c.comparison_id}</div>
              </button>
            ))}
            {list.data?.length === 0 && <p className="muted small">还没有对照。</p>}
          </div>
        </div>
      </div>
      <div className="stack" style={{ minWidth: 0 }}>
        {cmp.data ? <ComparisonDetail c={cmp.data} onOpenRun={onOpenRun} /> : <div className="card"><Empty title="选择或发起一次对照" /></div>}
      </div>
    </div>
  )
}

function ComparisonDetail({ c, onOpenRun }: { c: Comparison; onOpenRun: (id: string) => void }) {
  const [table, setTable] = useState(false)
  const [pair, setPair] = useState<{ task: string; repeat: number }>({ task: c.tasks[0], repeat: 0 })
  const note = usePoll(() => api.note(c.comparison_id), [c.comparison_id, c.finished_runs], 0, false)
  const A = c.sides[c.snapshot_a], B = c.sides[c.snapshot_b]
  const target = 1.1
  return (
    <>
      <div className="card">
        <div className="spread">
          <div className="eyebrow">{c.label} · {c.comparison_id}</div>
          <div className="row">
            {c.scripted_model && <Chip tone="warn" icon="!">脚本模型：仅功能检查</Chip>}
            <Chip tone={c.fair ? 'good' : 'bad'} icon={c.fair ? '✓' : '✕'}>{c.fair ? '配置指纹一致' : '配置不一致，不能比较'}</Chip>
            <StatusChip value={c.status} />
          </div>
        </div>
        <div className="headline">{c.snapshot_a} → {c.snapshot_b}：{c.tasks.length} 个留出任务 × {c.repeats} 次，已完成 {c.finished_runs}/{c.planned_runs}</div>
        {A && B && <SideTable a={c.snapshot_a} b={c.snapshot_b} A={A} B={B} />}
      </div>

      {note.data && c.finished_runs > 0 && (
        <div className="card" style={{ borderTop: '3px solid var(--accent)' }}>
          <div className="eyebrow">经验带来的变化 · 由对照数据自动填写</div>
          <ol style={{ margin: 0, paddingLeft: 22, fontSize: 16, lineHeight: 1.7 }}>
            {note.data.lines.map((l) => <li key={l} style={{ marginBottom: 6 }}>{l}</li>)}
          </ol>
        </div>
      )}

      <div className="card">
        <div className="spread">
          <h2>逐任务最终加速比</h2>
          <div className="seg"><button className={!table ? 'on' : ''} onClick={() => setTable(false)}>图</button><button className={table ? 'on' : ''} onClick={() => setTable(true)}>表</button></div>
        </div>
        {table ? <RunTable c={c} onOpenRun={onOpenRun} /> : <PairedDots tasks={c.tasks} perTask={c.per_task} a={c.snapshot_a} b={c.snapshot_b} target={target} />}
      </div>

      <div className="card">
        <div className="spread">
          <h2>行为对照：同一任务、同一轮，旧经验与新经验分别做了什么</h2>
          <div className="row">
            <select value={pair.task} onChange={(e) => setPair({ ...pair, task: e.target.value })} style={{ width: 110 }}>
              {c.tasks.map((t) => <option key={t}>{t}</option>)}
            </select>
            <div className="seg">
              {Array.from({ length: c.repeats }, (_, i) => (
                <button key={i} className={pair.repeat === i ? 'on' : ''} onClick={() => setPair({ ...pair, repeat: i })}>第 {i + 1} 轮</button>
              ))}
            </div>
          </div>
        </div>
        <BehaviorPair task={pair.task} a={c.snapshot_a} b={c.snapshot_b}
          runA={c.per_task[pair.task]?.[c.snapshot_a]?.runs[pair.repeat]?.run_id}
          runB={c.per_task[pair.task]?.[c.snapshot_b]?.runs[pair.repeat]?.run_id} onOpenRun={onOpenRun} />
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>学习成本（{c.snapshot_a} → {c.snapshot_b}）</h3>
          {c.learning_cost.in_lineage ? (
            <div className="stats" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
              <div className="stat"><div className="k">学习运行</div><div className="v">{c.learning_cost.learn_runs?.length}</div></div>
              <div className="stat"><div className="k">费用</div><div className="v">{fmt.usd(c.learning_cost.cost_usd)}</div></div>
              <div className="stat"><div className="k">耗时</div><div className="v">{fmt.s(c.learning_cost.wall_clock_s)}</div></div>
            </div>
          ) : <p className="muted">{c.learning_cost.note}</p>}
          <p className="small muted">学习阶段成本单独列出；使用经验后的成本见上表。不能只凭第二轮更便宜就说整个流程省钱。</p>
        </div>
        <div className="card">
          <h3>口径说明</h3>
          <ul className="small" style={{ paddingLeft: 18, margin: 0 }}>{c.notes.map((n) => <li key={n}>{n}</li>)}</ul>
          {c.errors.length > 0 && <div className="error small" style={{ marginTop: 10 }}>{c.errors.length} 次计划运行出错：{c.errors[0].error}</div>}
        </div>
      </div>
    </>
  )
}

function SideTable({ a, b, A, B }: { a: string; b: string; A: SideSummary; B: SideSummary }) {
  const rows: [string, string, string, string?][] = [
    ['达标次数 / 运行次数', `${A.goal_met} / ${A.runs}`, `${B.goal_met} / ${B.runs}`],
    ['成功率', fmt.pct(A.success_rate), fmt.pct(B.success_rate)],
    ['最终加速比中位数', fmt.x(A.final_speedup_median), fmt.x(B.final_speedup_median)],
    ['无改进运行', String(A.no_improvement_runs), String(B.no_improvement_runs)],
    ['模型请求中位数', String(A.model_requests_median ?? '—'), String(B.model_requests_median ?? '—')],
    ...(B.goal_met_from_reuse ? [['复用经验程序直接达标', `${A.goal_met_from_reuse ?? 0} 次`, `${B.goal_met_from_reuse} 次`] as [string, string, string]] : []),
    ...(B.runs_without_model_request != null ? [['未调用模型的运行', `${A.runs_without_model_request ?? 0} 次`, `${B.runs_without_model_request} 次`] as [string, string, string]] : []),
    ['升级到 GPT 次数', String(A.upgrades_total), String(B.upgrades_total)],
    ['失败候选', String(A.candidates_failed_total), String(B.candidates_failed_total)],
    ['输出 Token 合计', fmt.n(A.output_tokens.total), fmt.n(B.output_tokens.total)],
    ['模型费用合计', fmt.usd(A.cost_usd_total), fmt.usd(B.cost_usd_total)],
    ['总耗时', fmt.s(A.wall_clock_s_total), fmt.s(B.wall_clock_s_total)],
    ['循环时长中位数', fmt.s(A.agent_loop_s_median), fmt.s(B.agent_loop_s_median)],
  ]
  const stops = (s: SideSummary) => Object.entries(s.stop_reasons).map(([k, v]) => `${STOP[k] ?? k} ${v}`).join('，')
  return (
    <table className="tbl">
      <thead><tr><th>指标</th><th><span style={{ color: 'var(--series-old)' }}>●</span> {a}（旧经验）</th><th><span style={{ color: 'var(--series-new)' }}>●</span> {b}（新经验）</th></tr></thead>
      <tbody>
        {rows.map(([k, x, y]) => <tr key={k}><td>{k}</td><td>{x}</td><td><b>{y}</b></td></tr>)}
        <tr><td>终止原因</td><td className="small">{stops(A)}</td><td className="small">{stops(B)}</td></tr>
      </tbody>
    </table>
  )
}

function RunTable({ c, onOpenRun }: { c: Comparison; onOpenRun: (id: string) => void }) {
  return (
    <table className="tbl">
      <thead><tr><th>任务</th><th>快照</th><th>达标</th><th>最终加速比</th><th>请求</th><th>输出 Token</th><th>费用</th><th>耗时</th><th>终止</th><th>运行</th></tr></thead>
      <tbody>
        {c.tasks.flatMap((t) => [c.snapshot_a, c.snapshot_b].flatMap((s) => (c.per_task[t]?.[s]?.runs ?? []).map((r) => (
          <tr key={r.run_id}>
            <td>{t}</td><td>{s}</td><td>{r.goal_met ? '✓' : '✕'}</td><td>{fmt.x(r.final_speedup)}</td><td>{r.model_requests}</td>
            <td>{fmt.n(r.output_tokens)}</td><td>{fmt.usd(r.cost_usd)}</td><td>{fmt.s(r.wall_clock_s)}</td><td>{STOP[r.stop_reason] ?? r.stop_reason}</td>
            <td><button className="link mono" onClick={() => onOpenRun(r.run_id)}>{r.run_id.slice(-9)}</button></td>
          </tr>
        ))))}
      </tbody>
    </table>
  )
}
