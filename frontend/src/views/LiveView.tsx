import { api } from '../api'
import type { LiveCell, LiveData } from '../api'
import { Chip, Empty } from '../components/ui'
import { usePoll } from '../hooks'
import { ACTION, FAMILY, MODE, ROUTE, STOP, decision, fmt } from '../labels'

const MARK: Record<string, string> = { reuse: '↺', familiar: '○', new_family: '★', new_conditions: '◆', router_off: '·' }
const STEP_ICON: Record<string, [string, string]> = {
  done: ['✓', 'var(--good-ink)'], running: ['●', 'var(--accent)'], pending: ['○', 'var(--ink-3)'],
  skipped: ['–', 'var(--ink-3)'], failed: ['✕', 'var(--critical)'],
}

/* What is happening right now: the operator's work plan and log, the running experiment, the running run, the machine. */
export function LiveView({ onOpenRun, onOpenComparison }: { onOpenRun: (id: string) => void; onOpenComparison: (id: string) => void }) {
  const live = usePoll(api.live, [], 2000)
  const d = live.data
  if (!d) return <div className="card"><Empty title={live.error ? `后端未连接：${live.error}` : '加载中'} /></div>
  const p = d.progress
  const current = p.steps.find((s) => s.status === 'running')
  const doneN = p.steps.filter((s) => s.status === 'done').length
  return (
    <div className="stack">
      <div className="grid cols-2">
        <div className="card" style={{ borderTop: '3px solid var(--accent)' }}>
          <div className="spread">
            <div className="eyebrow">正在做 · {p.title ?? '—'}</div>
            <span className="small muted">{doneN}/{p.steps.length} 步完成 · 每 2 秒刷新</span>
          </div>
          <h2 style={{ margin: '4px 0 6px' }}>{current ? current.title : '没有进行中的步骤'}</h2>
          {current?.note && <p className="small" style={{ marginTop: 0 }}>{current.note}</p>}
          <div className="bar" style={{ margin: '10px 0 14px' }}><i style={{ width: `${(doneN / Math.max(1, p.steps.length)) * 100}%` }} /></div>
          <ol className="checklist">
            {p.steps.map((s) => {
              const [icon, color] = STEP_ICON[s.status] ?? ['?', 'var(--ink-3)']
              return (
                <li key={s.id} className={s.status}>
                  <span className="ic" style={{ color }}>{icon}</span>
                  <span className="t">{s.title}</span>
                  <span className="when small muted">{s.ended_at ? fmt.time(s.ended_at) : s.started_at ? `开始于 ${fmt.time(s.started_at)}` : ''}</span>
                </li>
              )
            })}
          </ol>
        </div>
        <div className="card">
          <div className="eyebrow">工作日志 · 最新在上</div>
          <ul className="log">
            {[...p.log].reverse().slice(0, 14).map((l, i) => (
              <li key={`${l.ts}-${i}`}><span className="mono small muted">{fmt.time(l.ts)}</span><span>{l.text}</span></li>
            ))}
            {p.log.length === 0 && <li className="muted small">暂无</li>}
          </ul>
        </div>
      </div>

      {d.comparison && <ExperimentCard c={d.comparison} onOpenRun={onOpenRun} onOpenComparison={onOpenComparison} />}

      <div className="grid cols-2">
        <RunCard r={d.run} onOpenRun={onOpenRun} />
        <MachineCard d={d} />
      </div>
    </div>
  )
}

function ExperimentCard({ c, onOpenRun, onOpenComparison }: { c: NonNullable<LiveData['comparison']>; onOpenRun: (id: string) => void; onOpenComparison: (id: string) => void }) {
  const stream = c.kind === 'stream'
  const arms = stream ? ['memory', 'fresh'] : [c.snapshot_a ?? 'a', c.snapshot_b ?? 'b']
  const armName = (a: string) => (a === 'memory' ? '带记忆' : a === 'fresh' ? '不带记忆' : a)
  const byTask = c.tasks.map((t) => ({ t, cells: c.cells.filter((x) => x.task_id === t) }))
  const pct = (c.done / Math.max(1, c.planned)) * 100
  return (
    <div className="card">
      <div className="spread">
        <div>
          <div className="eyebrow">正在运行的实验 · {c.comparison_id}</div>
          <h3 style={{ margin: 0 }}>{c.label}{stream ? ` · 从 ${c.start_snapshot} 出发，${c.tasks.length} 任务 × ${c.repeats} 次重放 × 带 / 不带记忆` : ''}</h3>
        </div>
        <div className="row">
          <Chip tone={c.status === 'running' ? 'accent' : c.status === 'completed' ? 'good' : 'warn'} icon={c.status === 'running' ? '●' : undefined}>
            {c.status === 'running' ? '运行中' : c.status === 'completed' ? '已完成' : c.status === 'stopped' ? '已停止' : c.status}
          </Chip>
          <button className="link" onClick={() => onOpenComparison(c.comparison_id)}>完整结果</button>
        </div>
      </div>
      <div className="spread" style={{ marginTop: 12 }}>
        <b style={{ fontSize: 22 }}>{c.done} / {c.planned} 次运行</b>
        <span className="small muted">{c.avg_run_s ? `平均每次 ${fmt.s(c.avg_run_s)}` : ''}{c.eta_s != null ? ` · 预计还需 ${Math.ceil(c.eta_s / 60)} 分钟` : ''}</span>
      </div>
      <div className="bar" style={{ margin: '8px 0 16px' }}><i style={{ width: `${pct}%` }} /></div>
      <div className="stats" style={{ gridTemplateColumns: `repeat(${arms.length}, minmax(0, 1fr))` }}>
        {arms.map((a) => {
          const t = c.totals[a]
          return (
            <div key={a} className="stat">
              <div className="k"><span style={{ color: a === 'memory' || a === c.snapshot_b ? 'var(--series-new)' : 'var(--series-old)' }}>●</span> {armName(a)} · 已完成 {t?.runs ?? 0} 次</div>
              <div className="v" style={{ fontSize: 22 }}>大模型 {t?.large_requests ?? 0} 次 · {fmt.usd(t?.cost_usd ?? 0)}</div>
              <div className="s">达标 {t?.goal_met ?? 0}/{t?.runs ?? 0} · 没调用模型 {t?.no_model ?? 0} 次 · 累计 {fmt.s(t?.seconds ?? 0)}</div>
            </div>
          )
        })}
      </div>
      <div style={{ overflowX: 'auto', marginTop: 16 }}>
        <table className="tbl live-grid">
          <thead>
            <tr><th>任务</th>{Array.from({ length: c.repeats }, (_, i) => <th key={i} colSpan={arms.length}>第 {i + 1} 次{stream ? '重放' : ''}</th>)}</tr>
            <tr><th />{Array.from({ length: c.repeats }, (_, i) => arms.map((a) => <th key={`${i}-${a}`} className="small">{armName(a)}</th>))}</tr>
          </thead>
          <tbody>
            {byTask.map(({ t, cells }) => (
              <tr key={t}>
                <td className="mono">{t}</td>
                {Array.from({ length: c.repeats }, (_, i) => arms.map((a) => {
                  const cell = cells.find((x) => x.repeat === i + 1 && x.arm === a)
                  return <td key={`${i}-${a}`}><Cell cell={cell} onOpenRun={onOpenRun} /></td>
                }))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted" style={{ marginBottom: 0 }}>↺ 复用直接交付 · ★ 全新任务族 → 大模型 · ◆ 新条件 → 大模型 · ○ 相近经验 → 小模型；绿色 = 达标，红色 = 未达标，闪烁 = 正在运行。点格子打开那次运行。</p>
    </div>
  )
}

function Cell({ cell, onOpenRun }: { cell?: LiveCell; onOpenRun: (id: string) => void }) {
  if (!cell || cell.state === 'planned') return <span className="cell planned">·</span>
  if (cell.state === 'running') return <button className="cell running" onClick={() => cell.run_id && onOpenRun(cell.run_id)}>{MARK[cell.route ?? ''] ?? '…'}</button>
  const ok = cell.goal_met
  const title = `${ROUTE[cell.route ?? '']?.[0] ?? cell.route ?? ''} · ${cell.requests} 次请求 · ${fmt.usd(cell.cost_usd ?? 0)} · ${fmt.x(cell.final_speedup)}${ok ? '' : ` · ${STOP[cell.stop_reason ?? ''] ?? cell.stop_reason ?? '未达标'}`}`
  return (
    <button className={`cell ${ok ? 'ok' : 'miss'}`} title={title} onClick={() => cell.run_id && onOpenRun(cell.run_id)}>
      <span className="m">{MARK[cell.route ?? ''] ?? '–'}</span><span className="x">{cell.final_speedup != null ? cell.final_speedup.toFixed(1) : '✕'}</span>
    </button>
  )
}

function RunCard({ r, onOpenRun }: { r: LiveData['run']; onOpenRun: (id: string) => void }) {
  if (!r) return <div className="card"><div className="eyebrow">正在执行的运行</div><Empty title="空闲：没有运行在执行" /></div>
  const route = r.route?.reason
  return (
    <div className="card">
      <div className="spread">
        <div className="eyebrow">正在执行的运行 · {fmt.s(r.elapsed_s)}</div>
        <button className="link mono" onClick={() => onOpenRun(r.run_id)}>{r.run_id}</button>
      </div>
      <h3 style={{ margin: '2px 0 8px' }}>{r.task_id} · {MODE[r.mode] ?? r.mode} · 读 {r.snapshot_id}</h3>
      <div className="row" style={{ marginBottom: 10 }}>
        {route && <Chip tone={ROUTE[route]?.[1] ?? 'neutral'} icon="⇢">{ROUTE[route]?.[0] ?? route}</Chip>}
        <span className="tag">模型请求 {r.requests}</span><span className="tag">{fmt.usd(r.cost_usd ?? 0)}</span>
        {r.label && <span className="small muted">{r.label.replace(/^str-\S+ /, '')}</span>}
      </div>
      <ol className="mini-steps">
        {r.steps.map((s) => (
          <li key={s.seq}>
            <span className="mono small muted">{s.seq}</span>
            <b>{s.actor === 'model' ? '模型' : '程序'} · {ACTION[s.action] ?? s.action}</b>
            {s.candidate_id && <span className="tag mono">{s.candidate_id}</span>}
            {typeof s.speedup === 'number' && <span className="tag">{fmt.x(s.speedup)}</span>}
            {s.next_decision && <span className="small muted">→ {decision(s.next_decision)}</span>}
          </li>
        ))}
      </ol>
      {r.last_event && <p className="small muted" style={{ marginBottom: 0 }}>最新事件：{r.last_event.type} · {fmt.time(r.last_event.ts)}</p>}
    </div>
  )
}

function MachineCard({ d }: { d: LiveData }) {
  const pts = d.machine.load
  const W = 520, H = 90
  const max = Math.max(16, ...pts.map((p) => p.load1))
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${(i / Math.max(1, pts.length - 1)) * W},${H - (p.load1 / max) * H}`).join(' ')
  const ic = d.machine.icloud_sync
  return (
    <div className="card">
      <div className="eyebrow">机器与费用</div>
      <div className="row" style={{ margin: '6px 0 10px', flexWrap: 'wrap' }}>
        <Chip tone={ic === 'paused' ? 'good' : ic === 'running' ? 'warn' : 'neutral'}>iCloud 同步：{ic === 'paused' ? '已暂停' : ic === 'running' ? '运行中' : ic === 'not_running' ? '未运行' : '未知'}</Chip>
        <span className="tag">生效经验版本 {d.active_snapshot}</span>
        <span className="tag">今天 GPT {d.gpt_today.calls} 次 · {fmt.usd(d.gpt_today.cost_usd)}</span>
      </div>
      {pts.length > 1 ? (
        <>
          <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ height: 90, display: 'block' }} role="img" aria-label="系统 1 分钟负载">
            <line x1={0} x2={W} y1={H - (16 / max) * H} y2={H - (16 / max) * H} stroke="var(--rule-strong)" strokeDasharray="4 4" />
            <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
          </svg>
          <p className="small muted" style={{ margin: '6px 0 0' }}>
            系统 1 分钟负载（每 30 秒采样，虚线 = 16 核）：最新 {pts[pts.length - 1].load1.toFixed(0)}，本次实验中位数 {[...pts].sort((a, b) => a.load1 - b.load1)[Math.floor(pts.length / 2)].load1.toFixed(0)}
          </p>
        </>
      ) : <p className="muted small">实验开始后采样负载。</p>}
      <p className="small muted" style={{ marginBottom: 0 }}>任务族：{Object.values(FAMILY).join(' · ')}</p>
    </div>
  )
}
