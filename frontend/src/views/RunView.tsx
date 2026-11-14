import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Report, Research, RunRow, Step, TaskSummary } from '../api'
import { SpeedupBars } from '../components/charts'
import { Chip, Empty, Meter, Stat, StatusChip } from '../components/ui'
import { usePoll } from '../hooks'
import { ACTION, MODE, OUTCOME, ROUTE, SPLIT, STOP, decision, fmt, rmode, roleName, stopDetail } from '../labels'

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
  const [mode, setMode] = useState<'eval' | 'learn' | 'online'>('eval')
  const [snapshot, setSnapshot] = useState('')
  const [err, setErr] = useState<string | null>(null)

  const running = runs.data?.find((r) => r.status === 'running')
  const current = runId ?? runs.data?.[0]?.run_id ?? null
  const isLive = runs.data?.find((r) => r.run_id === current)?.status === 'running'
  const report = usePoll(() => (current ? api.run(current) : Promise.resolve(null)), [current], 1500, isLive)

  const task = tasks.data?.find((t) => t.task_id === taskId)
  const native = task ? ['ale-bench', 'algotune', 'kernelbench'].includes(task.family) : false
  const learnable = task ? !native && ['A', 'S', 'T', 'smoke'].includes(task.split) : false
  const effMode = learnable ? mode : 'eval'

  const start = async () => {
    setErr(null)
    try {
      const r = await api.startRun({ task_id: taskId, mode: effMode, snapshot_id: native ? 'v0' : snapshot || undefined, label: 'dashboard' })
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
                  {ts.map((t) => <option key={t.task_id} value={t.task_id}>{t.task_id} · {t.presentation?.workload ?? t.workload}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          {task && (
            <p className="small muted" style={{ margin: '-6px 0 14px' }}>
              {task.presentation?.workload ?? task.workload} · {task.target.metric === 'score' ? '目标：最大化原始得分' : `目标 ${task.target.min_speedup}×`}
            </p>
          )}
          <div className="field"><span>运行模式</span>
            <div className="seg">
              <button className={effMode === 'eval' ? 'on' : ''} onClick={() => setMode('eval')}>评测 · 冻结经验</button>
              <button className={effMode === 'online' ? 'on' : ''} disabled={!learnable} onClick={() => setMode('online')}
                title={learnable ? '交付后把验证过的结果写入经验' : '此任务使用评测模式'}>在线 · 交付并记住</button>
              <button className={effMode === 'learn' ? 'on' : ''} disabled={!learnable} onClick={() => setMode('learn')}
                title={learnable ? '在已知最佳之上继续超越' : '此任务使用评测模式'}>学习 · 超越已知</button>
            </div>
          </div>
          <label className="field"><span>读取的经验快照</span>
            <select value={native ? 'v0' : snapshot} disabled={native} onChange={(e) => setSnapshot(e.target.value)}>
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
  const order = ['S', 'T', 'A', 'B', 'C', 'D', 'smoke']
  return order.map((s) => [s, ts.filter((t) => t.split === s)] as [string, TaskSummary[]]).filter(([, v]) => v.length)
}

/** List outcome. No final evaluation row means the final test did not run (dev-only, or the run ended early): that is
    "final 未运行", never "未达标". */
function runOutcome(r: RunRow): { text: string; tone: 'good' | 'bad' | 'muted' | null } {
  if (r.status === 'running') return { text: '运行中', tone: null }
  const stop = STOP[r.stop_reason ?? ''] ?? r.stop_reason ?? r.status
  const finalRan = r.final_goal_met != null || r.final_speedup != null || r.final_score != null
  if (!finalRan) return { text: `${r.final_evaluation === false ? '仅开发' : 'final 未运行'} · ${stop}`, tone: 'muted' }
  if (r.final_score != null) return { text: `最终得分 ${fmt.n(r.final_score)}`, tone: null }
  if (r.final_goal_met) return { text: `达标 ${fmt.x(r.final_speedup)}`, tone: 'good' }
  return { text: `最终未达标${r.final_speedup != null ? ` ${fmt.x(r.final_speedup)}` : ''} · ${stop}`, tone: 'bad' }
}

function RunItem({ r, on, pick }: { r: RunRow; on: boolean; pick: () => void }) {
  const o = runOutcome(r)
  return (
    <button className={on ? 'on' : ''} onClick={pick}>
      <b className="id-wrap" style={{ display: 'block' }}>{r.task_id}</b>
      <div className="spread" style={{ flexWrap: 'wrap', gap: '2px 10px' }}>
        <span>{r.research_mode ? `研究 · ${rmode(r.research_mode).label}` : `${MODE[r.mode] ?? r.mode} · 读 ${r.snapshot_id}`}</span>
        <span style={o.tone === 'good' ? { color: on ? undefined : 'var(--good-ink)' } : o.tone === 'muted' ? { opacity: 0.75 } : undefined}>{o.text}</span>
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
  const routedLarge = rep.route?.route === 'large'
  const fixedRole = rep.config.research_protocol?.fixed_model
  const currentRole = fixedRole ?? (upgraded || routedLarge ? 'large' : 'small')
  const routeKey = rep.route?.reason ?? ((rep.iterations.model_requests ?? 0) === 0 && rep.outcome.best_from_reuse ? 'reuse' : null)
  const loopS = rep.timing.agent_loop_elapsed_s ?? 0
  const protocol = rep.config.research_protocol
  const score = rep.task.objective.metric === 'score'
  const devOnly = protocol?.final_evaluation === false
  const bestDev = rep.best_candidate?.dev_evaluations.at(-1) ?? null
  const bestDevValue = score ? bestDev?.objective?.value ?? null
    : bestDev?.speedup ?? (rep.best_candidate?.candidate_id === 'c0' && bestDev?.status === 'passed' ? 1 : null)

  useEffect(() => {
    if (!codeOf) return
    api.candidate(rep.run_id, codeOf).then((c) => setCode(c.code)).catch(() => setCode(null))
  }, [codeOf, rep.run_id])

  // The final flag is only yes/no once the final test ran; otherwise it says why it has no verdict.
  const finalFlag: [string, boolean | null, string | null] = live ? ['最终测试', null, '待定']
    : !o.final_evaluated ? ['最终测试', null, devOnly ? '未启用（仅开发）' : '未运行']
    : score ? ['最终测试正确', o.final_correct ?? null, null]
    : ['最终测试达到目标', o.goal_met, null]
  const flags: [string, boolean | null, string | null][] = [
    ['候选程序运行完成', o.candidate_ran, null],
    ['开发验证通过', o.dev_validation_passed, null],
    [score ? '开发得分高于基线' : '指标改善（全部样本快于基线）', o.dev_improved, null],
    finalFlag,
  ]

  return (
    <>
      <div className="card">
        <div className="spread">
          <div className="eyebrow">{rep.task.task_id} · {SPLIT[rep.task.split] ?? rep.task.split} 批 · {MODE[rep.mode] ?? rep.mode}模式 · 读取 {rep.snapshot_id}</div>
          <div className="row">
            {routeKey && <Chip tone={ROUTE[routeKey]?.[1] ?? 'neutral'} icon="⇢">{ROUTE[routeKey]?.[0] ?? routeKey}</Chip>}
            {protocol?.mode && <Chip tone="accent">研究 · {rmode(protocol.mode).label} {protocol.mode}</Chip>}
            {protocol?.fixed_model && <Chip>固定 {rep.config.models[protocol.fixed_model]?.model ?? protocol.fixed_model}</Chip>}
            {devOnly && <Chip tone="warn" icon="!">仅开发 · final 未启用</Chip>}
            {rep.scripted_model.length > 0 && <Chip tone="warn" icon="!">脚本模型：仅功能检查</Chip>}
            <StatusChip value={rep.status} />
            {rep.stop_reason && <Chip tone={rep.stop_reason === 'goal_reached' ? 'good' : 'neutral'}>{STOP[rep.stop_reason] ?? rep.stop_reason}</Chip>}
          </div>
        </div>
        <div className="headline">{live ? '运行中……' : o.summary}</div>
        <div className="flags">
          {flags.map(([k, v, na]) => (
            <div key={k} className={`flag ${v == null ? 'na' : v ? 'yes' : 'no'}`}>
              <div className="k">{k}</div>
              <div className="v">{v == null ? na ?? '待定' : v ? '✓ 是' : '✕ 否'}</div>
            </div>
          ))}
        </div>
        {rep.stop_detail && !live && <p className="small muted" style={{ marginBottom: 0 }}>终止依据：{stopDetail(rep.stop_detail)}</p>}
      </div>

      <TaskDefinition r={rep.research} />

      <div className="card">
        <div className="meters">
          <Meter label="模型请求" value={rep.iterations.model_requests ?? 0} max={limits.max_model_requests} />
          <Meter label="候选" value={rep.iterations.candidates_proposed ?? 0} max={limits.max_candidates} />
          <Meter label="循环时长" value={Math.round(loopS)} max={limits.wall_clock_s} unit="s" hot={loopS > limits.wall_clock_s * 0.8} />
        </div>
        <hr className="rule" />
        <div className="stats">
          <Stat k="当前生成模型" v={(rep.iterations.generation_requests ?? rep.iterations.model_requests ?? 0) === 0 && !live ? '未调用' : roleName(currentRole)}
            s={fixedRole ? `固定模型 · ${rep.config.models[fixedRole].model}` : routedLarge ? `分流：${ROUTE[rep.route!.reason]?.[0] ?? rep.route!.reason}` : upgraded ? `第 ${rep.iterations.upgrade_at_step} 步升级`
              : (rep.iterations.generation_requests ?? rep.iterations.model_requests ?? 0) === 0 && !live ? '本次未请求生成模型' : '小模型 · 未升级'} />
          <Stat k="Token 输入 / 输出" v={`${fmt.n(u.input_tokens)} / ${fmt.n(u.output_tokens)}`}
            s={u.reasoning_tokens != null ? `其中推理 ${fmt.n(u.reasoning_tokens)}` : u.input_tokens_unknown_calls ? `${u.input_tokens_unknown_calls} 次调用用量未知` : '推理 token 未单列'} />
          <Stat k="模型费用" v={fmt.usd(u.cost_usd)} s={costNote(u.cost_status)} />
          <Stat k={score ? '开发集最佳原始得分' : '开发集最佳加速比'}
            v={bestDevValue == null ? '—' : score ? fmt.n(bestDevValue) : `${bestDevValue.toFixed(4)}×`}
            s={rep.best_candidate ? `${rep.best_candidate.candidate_id}${rep.best_candidate.candidate_id === 'c0' ? ' · 初始程序' : ''}${score && rep.task.objective.baseline != null ? ` · 基线 ${fmt.n(rep.task.objective.baseline)}` : ''}` : '尚无有效候选'} />
          <Stat k={score ? '最终原始得分' : '最终加速比'}
            v={!o.final_evaluated ? (live ? '—' : '未运行') : score ? fmt.n(o.final_objective?.value) : fmt.x(o.final_speedup)}
            s={rep.final_evaluation ? `最终测试 ${rep.final_evaluation.correct ? '正确' : '未通过'}` : devOnly ? '本次为开发预实验，final 未启用' : '最终测试未运行'} />
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <div className="spread"><h3>候选与{rep.task.objective.metric === 'score' ? '原始得分' : '加速比'}（开发数据）</h3><span className="small muted">点击查看代码</span></div>
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
                    <td>{e.matching_features} / {rep.experience.retrieval?.feature_count ?? 5}</td>
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

      <Experiments r={rep.research} />

      <div className="card">
        <div className="spread"><h2>决策账本</h2><span className="small muted">每一步：目的 → 预期 → 实际反馈 → 下一步</span></div>
        <div className="ledger">{rep.steps.map((s) => <StepRow key={s.seq} s={s} rep={rep} />)}</div>
        {live && <p className="muted small">等待下一步……</p>}
        {!live && (
          <p className="small muted">
            复现：<code>{rep.reproduce.run_again}</code>
            <a className="link" style={{ marginLeft: 12 }} href={api.markdownUrl(rep.run_id)} target="_blank" rel="noreferrer">导出研究记录（Markdown）</a>
          </p>
        )}
      </div>
    </>
  )
}

/* RA-01: everything here was fixed when the run was created; the model could not change it. */
function TaskDefinition({ r }: { r: Research }) {
  const d = r.definition
  const b = d.budget
  const rows: [string, string][] = [
    ['工作负载', d.workload],
    ['基线', d.baseline.program + (d.baseline.dev_median_s != null ? `；开发数据中位耗时 ${d.baseline.dev_median_s.toFixed(3)}s` : '')],
    ['目标与约束', d.goal],
    ['允许修改', d.scope],
    ['工具', d.tools.map((t) => t.label.split('：')[0]).join(' · ')],
    ['验证方法', d.verification],
    ['预算', `模型请求 ${b.model_requests} 次 · 候选 ${b.candidates} 个 · 循环 ${b.loop_s}s · 单次请求 ${b.request_timeout_s}s · 单次测量 ${b.measurement_timeout_s}s`],
    ['独立验收', d.final_test],
  ]
  return (
    <details className="card research-def">
      <summary>
        <span className="eyebrow">研究任务 · 运行开始前固定</span>
        <span className="q">{d.question}</span>
      </summary>
      <dl>{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
    </details>
  )
}

const VERDICT_TONE: Record<string, ['good' | 'warn' | 'neutral' | 'bad', string]> = {
  supported: ['good', '✓'], partial: ['warn', '◐'], refuted: ['neutral', '✕'], untestable: ['bad', '!'], untested: ['neutral', '·'],
}

/* RA-03: hypothesis, prediction and check written before the experiment; the verdict comes from the evaluator. */
function Experiments({ r }: { r: Research }) {
  if (r.experiments.length === 0) return null
  return (
    <div className="card">
      <div className="spread">
        <h2>假设与实验</h2>
        <span className="small muted">
          {Object.entries(r.verdicts).filter(([, n]) => n > 0).map(([k, n]) => `${r.verdict_labels[k].split('（')[0]} ${n}`).join(' · ')}
        </span>
      </div>
      <p className="small muted" style={{ marginTop: 0 }}>假设、预期与验证方法在实验前写下（复用的程序由程序依据经验记录写明，模型候选由模型写）；判定由程序依据随后的评测给出，不由模型自评。</p>
      <table className="tbl exp-table">
        <thead><tr><th>候选</th><th>假设（事前）</th><th>预期</th><th>实测</th><th>判定</th><th>之后</th></tr></thead>
        <tbody>{r.experiments.map((e) => {
          const [tone, icon] = VERDICT_TONE[e.verdict]
          const res = e.result
          return (
            <tr key={e.candidate_id}>
              <td className="mono nowrap">{e.candidate_id}{e.kind === 'reuse' && <span className="tag" style={{ marginLeft: 6 }}>复用</span>}</td>
              <td>{e.hypothesis ?? e.purpose ?? '—'}</td>
              <td className="muted">{e.expected ?? '—'}</td>
              <td className="nowrap">{res.status ?? '—'}{res.objective ? ` · 得分 ${fmt.n(res.objective.value)}` : res.speedup != null ? ` · ${fmt.x(res.speedup)}` : ''}{res.contract_case ? ` · ${res.contract_case}` : ''}</td>
              <td><Chip tone={tone} icon={icon}>{r.verdict_labels[e.verdict].split('（')[0]}</Chip></td>
              <td className="small">{e.then ? decision(e.then) : '—'}</td>
            </tr>
          )
        })}</tbody>
      </table>
    </div>
  )
}

function costNote(s: string) {
  return ({ estimated: '按官方价表估算', local_no_api_fee: '本地 Qwen 无 API 费用', not_applicable: '脚本模型不计费', no_model_calls: '没有调用模型', partial: '部分调用费用未知', unknown: '费用未知' } as Record<string, string>)[s] ?? s
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
  if (s.model_role) return roleName(s.model_role)
  if (rep.config.research_protocol?.fixed_model) return roleName(rep.config.research_protocol.fixed_model)
  if (rep.route?.route === 'large') return roleName('large')
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

