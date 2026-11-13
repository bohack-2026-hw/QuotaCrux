import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Report, RunRow, Step, TaskSummary } from '../api'
import { SpeedupBars } from '../components/charts'
import { Chip, Empty, Meter, Stat, StatusChip } from '../components/ui'
import { usePoll } from '../hooks'
import { ACTION, ORDER, OUTCOME, SPLIT, STOP, decision, fmt, roleName } from '../labels'

export function RunView({ runId, setRunId, activeSnapshot, onOpenExperience }: {
  runId: string | null
  setRunId: (id: string) => void
  activeSnapshot: string
  onOpenExperience: (snapshot: string, experienceId?: string) => void
}) {
  const tasks = usePoll(api.tasks, [], 0, false)
  const runs = usePoll(() => api.runs(), [], 3000)
  const snaps = usePoll(api.snapshots, [], 5000)
  const [taskId, setTaskId] = useState('B-01')
  const [mode, setMode] = useState<'eval' | 'learn'>('eval')
  const [snapshot, setSnapshot] = useState('')
  const [err, setErr] = useState<string | null>(null)

  const running = runs.data?.find((r) => r.status === 'running')
  const current = runId ?? runs.data?.[0]?.run_id ?? null
  const isLive = runs.data?.find((r) => r.run_id === current)?.status === 'running'
  const report = usePoll(() => (current ? api.run(current) : Promise.resolve(null)), [current], 1500, isLive)

  const task = tasks.data?.find((t) => t.task_id === taskId)
  const learnable = task ? ['A', 'smoke'].includes(task.split) : false
  const effMode = learnable ? mode : 'eval'

  const start = async () => {
    setErr(null)
    try {
      const r = await api.startRun({ task_id: taskId, mode: effMode, snapshot_id: snapshot || undefined, label: 'dashboard' })
      setRunId(r.run_id)
      runs.refresh()
    } catch (e) { setErr((e as Error).message) }
  }
  const stop = async () => {
    if (!running) return
    try { await api.stopRun(running.run_id) } catch (e) { setErr((e as Error).message) }
  }

  return (
    <div className="grid cols-run">
      <div className="stack">
        <div className="card">
          <h2>发起运行</h2>
          <label className="field"><span>任务</span>
            <select value={taskId} onChange={(e) => setTaskId(e.target.value)}>
              {groupTasks(tasks.data ?? []).map(([split, ts]) => (
                <optgroup key={split} label={SPLIT[split] ?? split}>
                  {ts.map((t) => <option key={t.task_id} value={t.task_id}>{t.task_id} · {ORDER[t.dev_params.order] ?? t.dev_params.order} · {fmt.rows(t.dev_params.rows)} 行 · {fmt.rows(t.dev_params.keys)} key</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          {task && (
            <p className="small muted" style={{ margin: '-6px 0 14px' }}>
              {task.notes} · 目标 {task.target.min_speedup}×
            </p>
          )}
          <div className="field"><span>运行模式</span>
            <div className="seg">
              <button className={effMode === 'eval' ? 'on' : ''} onClick={() => setMode('eval')}>评测 · 冻结经验</button>
              <button className={effMode === 'learn' ? 'on' : ''} disabled={!learnable} onClick={() => setMode('learn')}
                title={learnable ? '' : 'B/C 任务只能在评测模式运行'}>学习 · 发布新版本</button>
            </div>
          </div>
          <label className="field"><span>读取的经验快照</span>
            <select value={snapshot} onChange={(e) => setSnapshot(e.target.value)}>
              <option value="">当前生效版本（{activeSnapshot}）</option>
              {snaps.data?.snapshots.map((s) => <option key={s.snapshot_id} value={s.snapshot_id}>{s.snapshot_id} · {s.experience_count} 条经验</option>)}
            </select>
          </label>
          <div className="row">
            <button className="btn primary" disabled={!!running} onClick={start}>开始运行</button>
            <button className="btn" disabled={!running} onClick={stop}>停止</button>
          </div>
          {running && <p className="small muted">运行串行执行：{running.run_id} 进行中</p>}
          {err && <div className="error small" style={{ marginTop: 12 }}>{err}</div>}
        </div>
        <div className="card">
          <h3>运行记录</h3>
          <div className="runlist">
            {(runs.data ?? []).map((r) => <RunItem key={r.run_id} r={r} on={r.run_id === current} pick={() => setRunId(r.run_id)} />)}
            {runs.data?.length === 0 && <p className="muted small">还没有运行。</p>}
          </div>
        </div>
      </div>

      <div className="stack" style={{ minWidth: 0 }}>
        {report.data ? <RunDetail rep={report.data} onOpenExperience={onOpenExperience} />
          : <div className="card"><Empty title="选择或发起一次运行">左侧选择任务，点击开始运行；步骤会实时出现在这里。</Empty></div>}
      </div>
    </div>
  )
}

function groupTasks(ts: TaskSummary[]): [string, TaskSummary[]][] {
  const order = ['A', 'B', 'C', 'smoke']
  return order.map((s) => [s, ts.filter((t) => t.split === s)] as [string, TaskSummary[]]).filter(([, v]) => v.length)
}

function RunItem({ r, on, pick }: { r: RunRow; on: boolean; pick: () => void }) {
  return (
    <button className={on ? 'on' : ''} onClick={pick}>
      <div className="spread">
        <b>{r.task_id} · {r.mode === 'learn' ? '学习' : '评测'} · 读 {r.snapshot_id}</b>
        <span>{r.status === 'running' ? '运行中' : STOP[r.stop_reason ?? ''] ?? r.status}</span>
      </div>
      <div className="rid">{r.run_id}</div>
    </button>
  )
}

function RunDetail({ rep, onOpenExperience }: { rep: Report; onOpenExperience: (s: string, e?: string) => void }) {
  const [codeOf, setCodeOf] = useState<string | null>(null)
  const [code, setCode] = useState<string | null>(null)
  const limits = rep.config.limits
  const u = rep.usage.total
  const o = rep.outcome
  const live = rep.status === 'running'
  const upgraded = (rep.iterations.upgrades ?? 0) > 0
  const loopS = rep.timing.agent_loop_elapsed_s ?? 0

  useEffect(() => {
    if (!codeOf) return
    api.candidate(rep.run_id, codeOf).then((c) => setCode(c.code)).catch(() => setCode(null))
  }, [codeOf, rep.run_id])

  const flags: [string, boolean | null][] = [
    ['候选程序运行完成', o.candidate_ran],
    ['开发验证通过', o.dev_validation_passed],
    ['指标改善（全部样本快于基线）', o.dev_improved],
    ['最终测试达到目标', live ? null : o.goal_met],
  ]

  return (
    <>
      <div className="card">
        <div className="spread">
          <div className="eyebrow">{rep.task.task_id} · {SPLIT[rep.task.split] ?? rep.task.split} · {rep.mode === 'learn' ? '学习模式' : '评测模式'} · 读取 {rep.snapshot_id}</div>
          <div className="row">
            {rep.scripted_model.length > 0 && <Chip tone="warn" icon="!">脚本模型：仅功能检查</Chip>}
            <StatusChip value={rep.status} />
            {rep.stop_reason && <Chip tone={rep.stop_reason === 'goal_reached' ? 'good' : 'neutral'}>{STOP[rep.stop_reason] ?? rep.stop_reason}</Chip>}
          </div>
        </div>
        <div className="headline">{live ? '运行中……' : o.summary}</div>
        <div className="flags">
          {flags.map(([k, v]) => (
            <div key={k} className={`flag ${v == null ? 'na' : v ? 'yes' : 'no'}`}>
              <div className="k">{k}</div>
              <div className="v">{v == null ? '待定' : v ? '✓ 是' : '✕ 否'}</div>
            </div>
          ))}
        </div>
        {rep.stop_detail && !live && <p className="small muted" style={{ marginBottom: 0 }}>终止依据：{rep.stop_detail.split('\n')[0]}</p>}
      </div>

      <div className="card">
        <div className="meters">
          <Meter label="模型请求" value={rep.iterations.model_requests ?? 0} max={limits.max_model_requests} />
          <Meter label="候选" value={rep.iterations.candidates_proposed ?? 0} max={limits.max_candidates} />
          <Meter label="循环时长" value={Math.round(loopS)} max={limits.wall_clock_s} unit="s" hot={loopS > limits.wall_clock_s * 0.8} />
        </div>
        <hr className="rule" />
        <div className="stats">
          <Stat k="当前模型" v={upgraded ? 'GPT' : 'Qwen'} s={upgraded ? `第 ${rep.iterations.upgrade_at_step} 步按规则升级` : '本地 · 未升级'} />
          <Stat k="Token 输入 / 输出" v={`${fmt.n(u.input_tokens)} / ${fmt.n(u.output_tokens)}`}
            s={u.reasoning_tokens != null ? `其中推理 ${fmt.n(u.reasoning_tokens)}` : u.input_tokens_unknown_calls ? `${u.input_tokens_unknown_calls} 次调用用量未知` : '推理 token 未单列'} />
          <Stat k="模型费用" v={fmt.usd(u.cost_usd)} s={costNote(u.cost_status)} />
          <Stat k="最终加速比" v={fmt.x(o.final_speedup)} s={rep.final_evaluation ? `最终测试 ${rep.final_evaluation.correct ? '正确' : '未通过'}` : '最终测试未运行'} />
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <div className="spread"><h3>候选与加速比（开发数据）</h3><span className="small muted">点击查看代码</span></div>
          {rep.candidates.length > 0
            ? <SpeedupBars candidates={rep.candidates} target={rep.task.target_min_speedup} bestId={rep.best_candidate?.candidate_id ?? null} onPick={setCodeOf} />
            : <Empty title="等待初始程序验证" />}
          {codeOf && code != null && (
            <div style={{ marginTop: 12 }}>
              <div className="spread small"><b>{codeOf} 的代码</b><button className="link" onClick={() => setCodeOf(null)}>收起</button></div>
              <pre className="code" style={{ marginTop: 6 }}>{code}</pre>
            </div>
          )}
        </div>
        <div className="card">
          <h3>本次实际读取的经验（{rep.experience.snapshot_read}）</h3>
          {rep.experience.read.length === 0 ? <p className="muted small">{rep.experience.snapshot_read} 中没有与当前工作负载匹配的经验（或快照为空）。</p> : (
            <table className="tbl">
              <thead><tr><th>#</th><th>经验</th><th>结果</th><th>匹配特征</th><th>来源任务</th></tr></thead>
              <tbody>{rep.experience.read.map((e) => {
                const [label, tone, icon] = OUTCOME[e.outcome] ?? [e.outcome, 'neutral', '']
                return (
                  <tr key={e.experience_id}>
                    <td>{e.rank}</td>
                    <td><button className="link mono" onClick={() => onOpenExperience(rep.experience.snapshot_read, e.experience_id)}>{e.experience_id.slice(-10)}</button></td>
                    <td><Chip tone={tone} icon={icon}>{label}</Chip></td>
                    <td>{e.matching_features} / 5</td>
                    <td>{e.task_id}</td>
                  </tr>
                )
              })}</tbody>
            </table>
          )}
          {rep.experience.published_snapshot_id && (
            <div className="note" style={{ marginTop: 14 }}>
              本次学习发布了 <b>{rep.experience.published_snapshot_id}</b>，新增 {rep.experience.published_experiences.length} 条经验。
              <button className="link" style={{ marginLeft: 8 }} onClick={() => onOpenExperience(rep.experience.published_snapshot_id!)}>查看</button>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="spread"><h2>决策账本</h2><span className="small muted">每一步：目的 → 预期 → 实际反馈 → 下一步</span></div>
        <div className="ledger">{rep.steps.map((s) => <StepRow key={s.seq} s={s} rep={rep} />)}</div>
        {live && <p className="muted small">等待下一步……</p>}
        {!live && (
          <p className="small muted">复现：<code>{rep.reproduce.run_again}</code></p>
        )}
      </div>
    </>
  )
}

function costNote(s: string) {
  return ({ estimated: '按官方价表估算', local_no_api_fee: '本地 Qwen 无 API 费用', not_applicable: '脚本模型不计费', partial: '部分调用费用未知', unknown: '费用未知' } as Record<string, string>)[s] ?? s
}

function StepRow({ s, rep }: { s: Step; rep: Report }) {
  const r = s.result as Record<string, unknown>
  const model = s.model_call_id ? modelOf(rep, s) : null
  const isUpgrade = s.action === 'upgrade_model'
  return (
    <div className={`step ${s.actor} ${isUpgrade ? 'upgrade' : ''}`}>
      <div className="seq">{s.seq}</div>
      <div className="who">
        <b>{s.actor === 'model' ? (model ?? '模型') : '程序'}</b>
        <span className="muted">{ACTION[s.action] ?? s.action}</span>
      </div>
      <div className="body">
        <div className="row"><StatusChip value={s.status} />{s.candidate_id && <span className="tag mono">{s.candidate_id}</span>}
          {typeof r.speedup === 'number' && <span className="tag">{fmt.x(r.speedup)}{r.improved ? ' · 改善' : ''}</span>}
          {s.next_decision && <span className="small muted">→ {decision(s.next_decision)}</span>}
        </div>
        {s.purpose && <p>{s.purpose}</p>}
        {s.expected_result && s.actor === 'model' && <p className="small muted">预期：{s.expected_result}</p>}
        {s.hypothesis && <p className="hyp">{s.hypothesis}</p>}
        {feedback(r)}
      </div>
    </div>
  )
}

function modelOf(rep: Report, s: Step): string {
  const upgradeAt = rep.iterations.upgrade_at_step
  const role = upgradeAt != null && s.seq > upgradeAt ? 'large' : 'small'
  return roleName(role)
}

function feedback(r: Record<string, unknown>) {
  const f = r.failure as Record<string, unknown> | undefined
  if (f) {
    const ex = (f.examples as Record<string, unknown>[] | undefined)?.[0]
    return (
      <p className="small" style={{ color: '#8e2424' }}>
        反馈：{String(f.category ?? '')}{f.contract_case ? ` · 用例 ${String(f.contract_case)}` : ''}{f.message ? ` · ${String(f.message).slice(0, 120)}` : ''}
        {ex ? ` · 例：期望 ${String(ex.expected)}，得到 ${String(ex.got)}` : ''}
        {f.stderr_tail ? ` · ${String(f.stderr_tail).split('\n').slice(-1)[0]}` : ''}
      </p>
    )
  }
  if (r.analysis) return <p className="small muted">分析：{String(r.analysis).slice(0, 220)}</p>
  if (r.error_kind) return <p className="small" style={{ color: '#8e2424' }}>{String(r.error_kind)}：{String(r.message ?? '').slice(0, 160)}</p>
  if (r.finish_reason) return <p className="small muted">结束理由：{String(r.finish_reason)}</p>
  if (r.to) return <p className="small">切换到 {String(r.to)}（连续 {String(r.misses)} 次未达标）</p>
  return null
}

