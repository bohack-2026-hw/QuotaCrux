import { useState } from 'react'
import { api } from '../api'
import type { SideSummary, Stream, StreamRun } from '../api'
import { StreamLadder } from '../components/charts'
import { Chip, StatusChip } from '../components/ui'
import { usePoll } from '../hooks'
import { FAMILY, ROUTE, fmt } from '../labels'

const ARM_NAME = { memory: '带记忆', fresh: '不带记忆' }
const ROUTE_MARK: Record<string, string> = { reuse: '↺', familiar: '○', new_family: '★', new_conditions: '◆', router_off: '·', no_model_request: '–' }

/* Online stream: the same task sequence with accumulating memory vs from a fixed start. */
export function StreamDetail({ c, onOpenRun }: { c: Stream; onOpenRun: (id: string) => void }) {
  const [metric, setMetric] = useState<'cost_usd' | 'agent_loop_s' | 'large_model_requests'>('cost_usd')
  const note = usePoll(() => api.note(c.comparison_id), [c.comparison_id, c.finished_runs], 0, false)
  const M = c.sides.memory, F = c.sides.fresh
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
        <div className="headline">任务流：从 {c.start_snapshot} 出发，{c.tasks.length} 个任务 × {c.repeats} 次重放，已完成 {c.finished_runs}/{c.planned_runs}</div>
        <p className="small muted" style={{ marginTop: -4 }}>
          同一串任务、同一配置。带记忆：在线模式，交付后把验证过的结果写入经验，下一个任务读取；不带记忆：每个任务都只读 {c.start_snapshot}。
          每次重放都从 {c.start_snapshot} 重新学起，所以重复的是学习过程本身。
        </p>
        {M && F && M.runs > 0 && <ArmTable F={F} M={M} />}
      </div>

      {note.data && c.finished_runs > 0 && (
        <div className="card" style={{ borderTop: '3px solid var(--accent)' }}>
          <div className="eyebrow">记忆带来的变化 · 由任务流数据自动填写</div>
          <ol style={{ margin: 0, paddingLeft: 22, fontSize: 16, lineHeight: 1.7 }}>
            {note.data.lines.map((l) => <li key={l} style={{ marginBottom: 6 }}>{l}</li>)}
          </ol>
        </div>
      )}

      <div className="card">
        <div className="spread">
          <h2>沿任务流累计</h2>
          <div className="seg">
            <button className={metric === 'cost_usd' ? 'on' : ''} onClick={() => setMetric('cost_usd')}>大模型费用</button>
            <button className={metric === 'large_model_requests' ? 'on' : ''} onClick={() => setMetric('large_model_requests')}>大模型请求</button>
            <button className={metric === 'agent_loop_s' ? 'on' : ''} onClick={() => setMetric('agent_loop_s')}>研究循环时长</button>
          </div>
        </div>
        <StreamLadder positions={c.positions} series={c.series} repeats={c.repeats} metric={metric} />
      </div>

      <div className="card">
        <div className="spread">
          <h2>逐任务：分流与结果</h2>
          <span className="small muted">↺ 复用直接交付 · ★ 全新任务族 → 大模型 · ◆ 新条件 → 大模型 · ○ 相近经验 → 小模型；每个符号是一次重放</span>
        </div>
        <table className="tbl">
          <thead><tr><th>#</th><th>任务</th><th>工作负载</th><th>{ARM_NAME.memory}</th><th>{ARM_NAME.fresh}</th></tr></thead>
          <tbody>
            {c.positions.map((p) => (
              <tr key={p.task_id}>
                <td>{p.position}</td>
                <td><b>{p.task_id}</b>{p.first_of_family && <div><span className="tag" style={{ color: 'var(--accent-ink)' }}>首次出现</span></div>}</td>
                <td className="small">{p.workload}</td>
                <td><ArmCell runs={p.arms.memory} onOpenRun={onOpenRun} /></td>
                <td><ArmCell runs={p.arms.fresh} onOpenRun={onOpenRun} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>各任务族</h3>
          <table className="tbl">
            <thead><tr><th>任务族</th><th>达标</th><th>大模型请求</th><th>费用</th><th>加速比中位数</th></tr></thead>
            <tbody>
              {Object.entries(c.by_family).map(([fam, s]) => (
                <tr key={fam}>
                  <td>{FAMILY[fam] ?? fam}</td>
                  <td>{s.fresh.goal_met}/{s.fresh.runs} → <b>{s.memory.goal_met}/{s.memory.runs}</b></td>
                  <td>{s.fresh.large_model_requests_total} → <b>{s.memory.large_model_requests_total}</b></td>
                  <td>{fmt.usd(s.fresh.cost_usd_total)} → <b>{fmt.usd(s.memory.cost_usd_total)}</b></td>
                  <td>{fmt.x(s.fresh.final_speedup_median)} → <b>{fmt.x(s.memory.final_speedup_median)}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small muted">左为不带记忆，右为带记忆。</p>
        </div>
        <div className="card">
          <h3>经验增长（带记忆一侧）</h3>
          <table className="tbl">
            <thead><tr><th>重放</th><th>版本</th><th>新发布</th><th>经验条数</th></tr></thead>
            <tbody>
              {c.growth.map((g) => (
                <tr key={g.repeat}><td>第 {g.repeat} 次</td><td className="mono">{g.start} → {g.end}</td><td>{g.published_versions} 个版本</td>
                  <td>{g.experiences_start} → <b>{g.experiences_end}</b></td></tr>
              ))}
            </tbody>
          </table>
          <ul className="small" style={{ paddingLeft: 18, margin: '10px 0 0' }}>{c.notes.map((n) => <li key={n}>{n}</li>)}</ul>
          {c.errors.length > 0 && <div className="error small" style={{ marginTop: 10 }}>{c.errors.length} 次计划运行出错：{c.errors[0].error}</div>}
        </div>
      </div>
    </>
  )
}

function ArmCell({ runs, onOpenRun }: { runs: StreamRun[]; onOpenRun: (id: string) => void }) {
  if (!runs.length) return <span className="muted small">待运行</span>
  const cost = runs.reduce((a, r) => a + (r.cost_usd ?? 0), 0)
  const speeds = runs.map((r) => r.final_speedup).filter((v): v is number => v != null).sort((a, b) => a - b)
  return (
    <div className="small">
      <div className="row" style={{ gap: 4 }}>
        {runs.map((r) => (
          <button key={r.run_id} className="link mono" title={`${ROUTE[r.route]?.[0] ?? r.route} · ${r.model_requests} 次请求 · ${fmt.usd(r.cost_usd)} · ${fmt.x(r.final_speedup)}${r.goal_met ? '' : ' · 未达标'}`}
            onClick={() => onOpenRun(r.run_id)} style={{ fontSize: 18, color: r.goal_met ? undefined : 'var(--critical)' }}>
            {ROUTE_MARK[r.route] ?? '?'}
          </button>
        ))}
      </div>
      <div className="muted">{speeds.length ? fmt.x(speeds[Math.floor(speeds.length / 2)]) : '—'} · 请求 {runs.reduce((a, r) => a + r.model_requests, 0)} · {fmt.usd(cost)}</div>
    </div>
  )
}

function ArmTable({ F, M }: { F: SideSummary; M: SideSummary }) {
  const routes = (s: SideSummary) => Object.entries(s.routes ?? {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${ROUTE[k]?.[0] ?? k} ${v}`).join('，')
  const rows: [string, string, string][] = [
    ['达标次数 / 运行次数', `${F.goal_met} / ${F.runs}`, `${M.goal_met} / ${M.runs}`],
    ['最终加速比中位数', fmt.x(F.final_speedup_median), fmt.x(M.final_speedup_median)],
    ['大模型请求合计', String(F.large_model_requests_total ?? 0), String(M.large_model_requests_total ?? 0)],
    ['用到大模型的运行', `${F.runs_using_large_model ?? 0} 次`, `${M.runs_using_large_model ?? 0} 次`],
    ['未调用模型的运行', `${F.runs_without_model_request ?? 0} 次`, `${M.runs_without_model_request ?? 0} 次`],
    ['模型费用合计', fmt.usd(F.cost_usd_total), fmt.usd(M.cost_usd_total)],
    ['总耗时', fmt.s(F.wall_clock_s_total), fmt.s(M.wall_clock_s_total)],
    ['循环时长中位数', fmt.s(F.agent_loop_s_median), fmt.s(M.agent_loop_s_median)],
  ]
  return (
    <table className="tbl">
      <thead><tr><th>指标</th><th><span style={{ color: 'var(--series-old)' }}>●</span> 不带记忆</th><th><span style={{ color: 'var(--series-new)' }}>●</span> 带记忆</th></tr></thead>
      <tbody>
        {rows.map(([k, x, y]) => <tr key={k}><td>{k}</td><td>{x}</td><td><b>{y}</b></td></tr>)}
        <tr><td>分流</td><td className="small">{routes(F)}</td><td className="small">{routes(M)}</td></tr>
      </tbody>
    </table>
  )
}
