import { useState } from 'react'
import { AxisSwitch, BatchFacts, CostText, CostTotal, FairChip, FinalChip, ModeLegend, ModeTag, ProgressChart, RunLink, RunStateChip } from '../components/research'
import { deltaText, familyName, metricName, metricText, stopText, sumText } from '../researchFormat'
import type { Axis } from '../components/research'
import { Chip, Empty, StatusChip } from '../components/ui'
import { FINAL, fmt, rmode } from '../labels'
import type { RBatch, RRun, RTask } from '../research'
import { MODES, median } from '../research'
import { useResearchBatch, useResearchList } from '../researchData'
import type { ApiState, BatchEntry } from '../researchData'

/* Within-task research: per task and repeat, the feedback / independent / no_feedback runs side by side, with the best
   development result over time, tokens and estimated cost, and the final state kept apart from development results. */
export function ResearchView({ selected, onSelect, onOpenRun }: { selected: string | null; onSelect: (id: string) => void; onOpenRun: (id: string) => void }) {
  const { entries, apiState, apiError } = useResearchList()
  const entry = entries.find((e) => e.id === selected) ?? entries[0] ?? null
  const { batch, error } = useResearchBatch(entry)

  return (
    <div className="stack">
      <SourceNote state={apiState} error={apiError} entry={entry} />
      {entries.length > 1 && (
        <div className="card">
          <label className="field" style={{ marginBottom: 0 }}><span>研究批次</span>
            <select value={entry?.id ?? ''} onChange={(e) => onSelect(e.target.value)}>
              {entries.map((e) => <option key={e.id} value={e.id}>{e.label ?? e.id} · {e.status}{e.source === 'archive' ? ' · 存档' : ''}</option>)}
            </select>
          </label>
        </div>
      )}
      {error && <div className="error small">读取批次失败：{error}</div>}
      {batch && entry ? <BatchDetail b={batch} entry={entry} onOpenRun={onOpenRun} />
        : <div className="card"><Empty title="还没有研究批次">研究对照批次完成第一轮后会出现在这里。</Empty></div>}
    </div>
  )
}

export function SourceNote({ state, error, entry }: { state: ApiState; error: string | null; entry: BatchEntry | null }) {
  if (entry?.source !== 'archive') return null
  const why = state === 'missing' ? '后端尚未提供研究对照接口（#2 进行中）' : state === 'error' ? `后端未连接（${error}）` : state === 'loading' ? '正在连接后端' : '后端暂无此批次'
  return (
    <div className="note small">
      当前显示仓库存档的真实记录 <code>{entry.archivePath}</code>：{why}。接口上线后，新批次会自动排在前面；存档只读，页面不会发起任何实验。
    </div>
  )
}

function BatchDetail({ b, entry, onOpenRun }: { b: RBatch; entry: BatchEntry; onOpenRun: (id: string) => void }) {
  const [axis, setAxis] = useState<Axis>('time')
  const archive = entry.source === 'archive'
  const runs = b.runs
  return (
    <>
      <div className="card">
        <div className="spread wrap">
          <div style={{ minWidth: 0 }}>
            <div className="eyebrow">研究批次 · {b.finalEnabled === false ? '开发预实验（final 未启用）' : b.finalEnabled ? '正式对照（含 final）' : '研究对照'}</div>
            <h2 style={{ marginBottom: 4 }}>{b.label ?? b.id}</h2>
            <div className="mono small muted id-wrap">{b.id}</div>
          </div>
          <div className="row">
            <StatusChip value={b.status} />
            <FairChip b={b} />
            <Chip tone={b.finalEnabled === false ? 'warn' : 'neutral'} icon={b.finalEnabled === false ? '!' : undefined}>
              {b.finalEnabled === false ? '仅开发集 · final 未启用' : b.finalEnabled ? 'final 启用' : 'final 设置未记录'}
            </Chip>
            {archive && <Chip>仓库存档</Chip>}
          </div>
        </div>
        {b.error && <div className="error small" style={{ marginTop: 12 }}>批次异常：{b.error}</div>}
        <div className="bar" style={{ margin: '16px 0 6px' }}><i style={{ width: `${b.planned ? (b.finished / b.planned) * 100 : 0}%` }} /></div>
        <div className="small muted">已结束 {b.finished} / {b.planned} 轮{runs.some((r) => r.state === 'running') ? ' · 1 轮进行中' : ''}</div>
        <div className="stats" style={{ marginTop: 16 }}>
          <Stat k="模型请求" v={sumText(runs.map((r) => r.requests), String)} />
          <Stat k="Token（输入 + 输出）" v={sumText(runs.map((r) => r.tokens), fmt.n)} />
          <Stat k="墙钟合计" v={sumText(runs.map((r) => r.wallS), (v) => fmt.s(v))} s={`其中模型等待 ${sumText(runs.map((r) => r.modelWaitS), (v) => fmt.s(v))}`} />
          <Stat k="估算费用" v={<CostTotal costs={runs.map((r) => r.cost)} />} s={b.pricing ? `${b.pricing.currency} 标价估算，非账单` : '无价格快照'} />
        </div>
        <hr className="rule" />
        <BatchFacts b={b} />
      </div>

      {b.tasks.map((t) => <TaskCard key={t.id} t={t} b={b} axis={axis} setAxis={setAxis} archive={archive} onOpenRun={onOpenRun} />)}

      <div className="card">
        <h3>读数须知</h3>
        <ul className="small" style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7 }}>
          {b.finalEnabled === false && <li>本批未启用最终集：所有数字都来自开发集，不能当作最终验收；未测 final 不计为失败。</li>}
          {b.tasks.some((t) => t.repeats.length < 2) && <li>每题每组只有 {Math.max(...b.tasks.map((t) => t.repeats.length))} 次研究重复，只能描述这一次的效果，不能比较稳定性或显著性。</li>}
          <li>原始得分与加速比分开报告，不跨题、不跨硬件比较原始耗时。加速比只在全部计时样本快于基线时计入保留结果。</li>
          <li>费用为调用前价格快照下的标价估算，不含折扣、账单与机器电力；记录缺失时显示“未知”，不按 0 计，也不换算币种。</li>
          {b.fair == null && <li>配置一致性尚未确认：在批次完成并通过检查前，组间差异只作参考。</li>}
        </ul>
      </div>
    </>
  )
}

function Stat({ k, v, s }: { k: string; v: React.ReactNode; s?: React.ReactNode }) {
  return <div className="stat"><div className="k">{k}</div><div className="v" style={{ fontSize: 22 }}>{v}</div>{s != null && <div className="s">{s}</div>}</div>
}

function TaskCard({ t, b, axis, setAxis, archive, onOpenRun }: { t: RTask; b: RBatch; axis: Axis; setAxis: (a: Axis) => void; archive: boolean; onOpenRun: (id: string) => void }) {
  const unplanned = b.modes.filter((m) => !t.modes.includes(m))
  const rows = [...t.runs].sort((x, y) => x.repeat - y.repeat || MODES.indexOf(x.mode as never) - MODES.indexOf(y.mode as never))
  const costOk = t.runs.some((r) => r.progress.some((p) => p.cost != null))
  return (
    <div className="card">
      <div className="spread wrap">
        <div style={{ minWidth: 0 }}>
          <div className="eyebrow">{familyName(t.family)} · {t.metric === 'score' ? '原始得分，越高越好' : `加速比${t.minSpeedup != null ? ` · 开发目标 ≥ ${t.minSpeedup}×` : ''}`}</div>
          <h2 style={{ marginBottom: 2 }}>{t.title}</h2>
          <div className="mono small muted id-wrap">{t.id}</div>
        </div>
        <div className="small muted" style={{ textAlign: 'right' }}>
          基线 {t.metric === 'score' ? metricText('score', t.baseline) : '1×（初始程序）'}
          {t.devCases != null && <> · 开发 {t.devCases} 例</>}{t.finalCases != null && <> · final {t.finalCases} 例</>}
        </div>
      </div>

      <div className="mode-tiles">
        {t.modes.map((m) => <ModeTile key={m} t={t} mode={m} />)}
        {unplanned.map((m) => (
          <div key={m} className="mode-tile off"><div className="row" style={{ gap: 6 }}><ModeTag mode={m} /></div><div className="small muted">此题未计划该组</div></div>
        ))}
      </div>

      <div className="spread wrap" style={{ margin: '18px 0 6px' }}>
        <h3 style={{ margin: 0 }}>开发集最佳{metricName(t.metric)}的变化</h3>
        <AxisSwitch axis={axis} setAxis={setAxis} costOk={costOk} />
      </div>
      <ModeLegend modes={t.modes} repeats={t.repeats} />
      <ProgressChart task={t} axis={axis} currency={b.pricing?.currency ?? null} />

      <h3 style={{ margin: '18px 0 8px' }}>按重复配对</h3>
      <div className="tbl-wrap">
        <table className="tbl pair-table">
          <thead><tr>
            <th>重复 · 组</th><th>状态</th><th>开发最佳</th><th>最终集</th><th>候选 通过/提出</th><th>请求</th><th>Token 输入 / 输出</th><th>墙钟（模型等待）</th><th>估算费用</th><th>记录</th>
          </tr></thead>
          <tbody>{rows.map((r, i) => (
            <tr key={r.seq} className={i > 0 && rows[i - 1].repeat !== r.repeat ? 'group-start' : ''}>
              <td className="nowrap"><ModeTag mode={r.mode} repeat={r.repeat} /></td>
              <td className="nowrap"><RunStateChip run={r} /><div className="small muted">{stopText(r)}</div></td>
              <td className="nowrap"><DevCell t={t} r={r} /></td>
              <td className="nowrap"><FinalChip run={r} />{r.final.value != null && <div className="small">{metricText(t.metric, r.final.value)}</div>}{r.final.error && <div className="small muted">{r.final.error}</div>}</td>
              <td className="nowrap">{r.passed ?? '?'} / {r.proposed ?? '?'}</td>
              <td className="nowrap">{r.requests ?? '未知'}{b.limits?.max_model_requests ? <span className="muted"> / {b.limits.max_model_requests}</span> : null}</td>
              <td className="nowrap">{fmt.n(r.inputTokens)} / {fmt.n(r.outputTokens)}</td>
              <td className="nowrap">{fmt.s(r.wallS)}{r.modelWaitS != null && <span className="muted">（{fmt.s(r.modelWaitS)}）</span>}</td>
              <td className="nowrap"><CostText c={r.cost} /></td>
              <td className="nowrap"><RunLink run={r} archive={archive} onOpenRun={onOpenRun} /></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}

function DevCell({ t, r }: { t: RTask; r: RRun }) {
  if (r.state === 'planned') return <span className="muted">—</span>
  if (r.dev.value == null) return <span className="muted">{r.state === 'running' ? '等待首个有效候选' : '无有效候选'}</span>
  const delta = deltaText(t, r.dev.value)
  return (
    <>
      <b>{metricText(t.metric, r.dev.value)}</b> <span className="mono small muted">{r.dev.candidate}</span>
      <div className="small">{r.dev.initial ? <span className="muted">保留初始程序，无改善</span>
        : r.dev.improved ? <span style={{ color: 'var(--good-ink)' }}>✓ 优于基线{delta ? ` ${delta}` : ''}</span>
        : <span className="muted">未优于基线{delta ? ` ${delta}` : ''}</span>}</div>
    </>
  )
}

/** One mode on one task: the development result across repeats and where its final stands. */
function ModeTile({ t, mode }: { t: RTask; mode: string }) {
  const runs = t.runs.filter((r) => r.mode === mode)
  const vals = runs.map((r) => r.dev.value).filter((v): v is number => v != null)
  const med = median(vals)
  const improved = runs.filter((r) => r.dev.improved && !r.dev.initial).length
  const ended = runs.filter((r) => r.state !== 'planned' && r.state !== 'running').length
  const finals = Object.entries(runs.reduce<Record<string, number>>((a, r) => ({ ...a, [r.final.state]: (a[r.final.state] ?? 0) + 1 }), {}))
  return (
    <div className="mode-tile" style={{ borderTopColor: rmode(mode).color }}>
      <ModeTag mode={mode} />
      <div className="v">{metricText(t.metric, med)}</div>
      <div className="small muted">
        {vals.length > 1 ? `${vals.length} 轮中位数 · 范围 ${metricText(t.metric, Math.min(...vals))} – ${metricText(t.metric, Math.max(...vals))}` : '开发集保留结果'}
      </div>
      <div className="small">{ended ? `${improved} / ${ended} 轮优于基线` : '尚未结束'} · {finals.map(([s, n]) => `${FINAL[s]?.[0] ?? s}${runs.length > 1 ? ` ×${n}` : ''}`).join('，')}</div>
    </div>
  )
}
