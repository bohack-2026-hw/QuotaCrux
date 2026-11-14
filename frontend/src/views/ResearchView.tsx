import { useState } from 'react'
import { AxisSwitch, BatchBadges, BatchFacts, CostText, CostTotal, FinalChip, ModeLegend, ModeTag, ProgressChart, RunLink, RunStateChip,
  Scoreboard } from '../components/research'
import type { Axis } from '../components/research'
import { Empty } from '../components/ui'
import { fmt, rmode } from '../labels'
import type { RBatch, RRun, RTask } from '../research'
import { MODES } from '../research'
import { deltaText, familyName, metricName, metricText, stopText, sumText, taskVerdict } from '../researchFormat'
import { useResearchBatch, useResearchList } from '../researchData'
import type { ApiState, BatchEntry } from '../researchData'

/* Within-task research, per task: the scoreboard, the curve, and the per-run ledger folded underneath. */
export function ResearchView({ selected, onSelect, onOpenRun }: { selected: string | null; onSelect: (id: string) => void; onOpenRun: (id: string) => void }) {
  const { entries, apiState, apiError } = useResearchList()
  const entry = entries.find((e) => e.id === selected) ?? entries[0] ?? null
  const { batch, error } = useResearchBatch(entry)
  const [axis, setAxis] = useState<Axis>('time')

  return (
    <div className="stack">
      {error && <div className="error small">读取批次失败：{error}</div>}
      {!batch || !entry ? <div className="card"><Empty title="还没有研究批次">第一轮研究对照结束后出现在这里。</Empty></div> : (
        <>
          <div className="card">
            <div className="spread wrap">
              <div style={{ minWidth: 0 }}>
                <div className="eyebrow">批次 · {batch.id}</div>
                <h2 style={{ marginBottom: 10 }}>{batch.label ?? batch.id}</h2>
                <BatchBadges b={batch} />
              </div>
              {entries.length > 1 && (
                <select value={entry.id} onChange={(e) => onSelect(e.target.value)} style={{ width: 'auto', maxWidth: '100%' }}>
                  {entries.map((e) => <option key={e.id} value={e.id}>{e.label ?? e.id}{e.source === 'archive' ? '（存档）' : ''}</option>)}
                </select>
              )}
            </div>
            {batch.error && <div className="error small" style={{ marginTop: 12 }}>批次异常：{batch.error}</div>}
            <div className="metaline" style={{ marginTop: 16 }}>
              <span>模型 <b>{batch.model?.name ?? '未记录'}</b></span>
              <span>请求 <b>{sumText(batch.runs.map((r) => r.requests), String)}</b></span>
              <span>Token <b>{sumText(batch.runs.map((r) => r.tokens), fmt.n)}</b></span>
              <span>墙钟 <b>{sumText(batch.runs.map((r) => r.wallS), (v) => fmt.s(v))}</b></span>
              <span>费用 <b><CostTotal costs={batch.runs.map((r) => r.cost)} /></b></span>
            </div>
            <details className="fold">
              <summary>实验配置与数据来源</summary>
              <BatchFacts b={batch} />
              <SourceNote state={apiState} error={apiError} entry={entry} />
            </details>
          </div>

          {batch.tasks.map((t) => <TaskCard key={t.id} t={t} b={batch} axis={axis} setAxis={setAxis} archive={entry.source === 'archive'} onOpenRun={onOpenRun} />)}

          <p className="footnote">
            {batch.finalEnabled === false && '本批只有开发集结果，未测最终集不算失败。'}
            {batch.tasks.some((t) => t.repeats.length < 2) && '每组只跑了 1 次，只能说明这一次，不能说明稳定性。'}
            得分与加速比分开报告，不跨题比较。费用为调用前价格快照下的标价估算，缺失记为“未知”，不换算币种。
          </p>
        </>
      )}
    </div>
  )
}

function SourceNote({ state, error, entry }: { state: ApiState; error: string | null; entry: BatchEntry }) {
  if (entry.source !== 'archive') return <p className="small muted">来源：后端研究接口。</p>
  const why = state === 'missing' ? '后端尚未提供研究接口' : state === 'error' ? `后端未连接（${error}）` : state === 'loading' ? '正在连接后端' : '后端暂无此批次'
  return <p className="small muted">来源：仓库存档 <code>{entry.archivePath}</code>（{why}）。存档只读，页面不会发起实验。</p>
}

function TaskCard({ t, b, axis, setAxis, archive, onOpenRun }: { t: RTask; b: RBatch; axis: Axis; setAxis: (a: Axis) => void; archive: boolean; onOpenRun: (id: string) => void }) {
  const rows = [...t.runs].sort((x, y) => x.repeat - y.repeat || MODES.indexOf(x.mode as never) - MODES.indexOf(y.mode as never))
  const v = taskVerdict(t, (m) => `${rmode(m).label}组`)
  return (
    <div className="card">
      <div className="spread wrap">
        <div style={{ minWidth: 0 }}>
          <div className="eyebrow">{familyName(t.family)} · {metricName(t.metric)}{t.minSpeedup != null ? ` · 目标 ≥ ${t.minSpeedup}×` : ''}</div>
          <h2 style={{ margin: 0 }}>{t.title}</h2>
          <p className="small" style={{ margin: '4px 0 0', color: 'var(--fg-2)' }}>{v.text}</p>
        </div>
        <span className="mono small muted">基线 {t.metric === 'score' ? fmt.n(t.baseline) : '1×'}{t.devCases != null ? ` · 开发 ${t.devCases} 例` : ''}</span>
      </div>

      <Scoreboard task={t} lead={v.lead} planned={b.modes} />

      <div className="spread wrap" style={{ marginBottom: 4 }}>
        <ModeLegend modes={t.modes} repeats={t.repeats} />
        <AxisSwitch axis={axis} setAxis={setAxis} costOk={t.runs.some((r) => r.progress.some((p) => p.cost != null))} />
      </div>
      <ProgressChart task={t} axis={axis} currency={b.pricing?.currency ?? null} />

      <details className="fold">
        <summary>逐轮明细 · {rows.length} 轮</summary>
        <div className="tbl-wrap">
          <table className="tbl pair-table">
            <thead><tr><th>组 · 重复</th><th>状态</th><th>开发最佳</th><th>最终集</th><th>请求</th><th>Token 入 / 出</th><th>墙钟</th><th>费用</th><th /></tr></thead>
            <tbody>{rows.map((r, i) => (
              <tr key={r.seq} className={i > 0 && rows[i - 1].repeat !== r.repeat ? 'group-start' : ''}>
                <td className="nowrap"><ModeTag mode={r.mode} repeat={r.repeat} /></td>
                <td className="nowrap"><RunStateChip run={r} /><div className="small muted">{stopText(r)}</div></td>
                <td className="nowrap"><DevCell t={t} r={r} /></td>
                <td className="nowrap"><FinalChip run={r} />{r.final.value != null && <div className="small">{metricText(t.metric, r.final.value)}{r.final.normalized ? <span className="muted">（c0 归一化，未重测）</span> : null}</div>}</td>
                <td className="nowrap mono">{r.requests ?? '?'}<span className="muted">/{b.limits?.max_model_requests ?? '?'}</span></td>
                <td className="nowrap mono">{fmt.n(r.inputTokens)} / {fmt.n(r.outputTokens)}</td>
                <td className="nowrap mono">{fmt.s(r.wallS)}</td>
                <td className="nowrap mono"><CostText c={r.cost} /></td>
                <td className="nowrap"><RunLink run={r} archive={archive} onOpenRun={onOpenRun} /></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </details>
    </div>
  )
}

function DevCell({ t, r }: { t: RTask; r: RRun }) {
  if (r.state === 'planned') return <span className="muted">—</span>
  if (r.dev.value == null) return <span className="muted">{r.state === 'running' ? '等待首个有效候选' : '无有效候选'}</span>
  const d = deltaText(t, r.dev.value)
  return (
    <>
      <b className="mono">{metricText(t.metric, r.dev.value)}</b> <span className="mono small muted">{r.dev.candidate}</span>
      <div className="small">{r.dev.initial ? <span className="muted">保留初始程序</span>
        : r.dev.improved ? <span style={{ color: 'var(--good-ink)' }}>✓ 优于基线{d ? ` ${d}` : ''}</span>
        : <span className="muted">未优于基线</span>}</div>
    </>
  )
}
