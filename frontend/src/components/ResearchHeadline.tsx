import type { ReactNode } from 'react'
import { FINAL, fmt, rmode } from '../labels'
import type { RBatch } from '../research'
import { costTotals, median } from '../research'
import { useResearchBatch, useResearchList } from '../researchData'
import { SourceNote } from '../views/ResearchView'
import { deltaText, metricText } from '../researchFormat'
import { CostTotal, FairChip, ModeMark } from './research'
import { Chip, Empty, StatusChip } from './ui'

/* The first screen answers four questions about the latest research batch: what is being researched, whether it
   improved on development data, whether the final set verified it, and whether the groups and budgets match. */
export function ResearchHeadline({ onOpenResearch }: { onOpenResearch: (id: string) => void }) {
  const { entries, apiState, apiError } = useResearchList()
  const entry = entries[0] ?? null
  const { batch: b } = useResearchBatch(entry)
  if (!entry || !b) return <div className="card"><div className="eyebrow">最近研究批次</div><Empty title="还没有研究批次" /></div>
  return (
    <div className="card headline-card">
      <div className="spread wrap">
        <div style={{ minWidth: 0 }}>
          <div className="eyebrow">最近研究批次 · 单个长任务内持续研究与优化</div>
          <h2 style={{ marginBottom: 2 }}>{b.label ?? b.id}</h2>
          <div className="small muted">已结束 {b.finished} / {b.planned} 轮{b.endedAt ? ` · ${b.endedAt.slice(0, 16).replace('T', ' ')} UTC` : ''}</div>
        </div>
        <div className="row">
          <StatusChip value={b.status} />
          <FairChip b={b} />
          <button className="btn" onClick={() => onOpenResearch(b.id)}>逐题对照 →</button>
        </div>
      </div>
      <div className="answers">
        <Answer q="研究哪个任务">
          <ul>{b.tasks.map((t) => <li key={t.id}><b>{t.title}</b><span className="muted"> · {t.metric === 'score' ? '原始得分' : '加速比'}</span></li>)}</ul>
          <p className="small muted">{b.modes.map((m) => rmode(m).label).join(' / ')} 各 {Math.max(...b.tasks.map((t) => t.repeats.length))} 次 · {b.model?.name ? `固定 ${b.model.name}` : '固定模型'}</p>
        </Answer>
        <Answer q="开发集是否改善">
          <ul>{b.tasks.map((t) => (
            <li key={t.id}>
              <b>{t.title}</b>
              {t.modes.map((m) => {
                const runs = t.runs.filter((r) => r.mode === m)
                const v = median(runs.map((r) => r.dev.value).filter((x): x is number => x != null))
                const up = runs.some((r) => r.dev.improved && !r.dev.initial)
                const pending = runs.every((r) => r.state === 'planned' || r.state === 'running')
                const d = deltaText(t, v)
                return (
                  <div key={m} className="small mline">
                    <ModeMark mode={m} />{rmode(m).label} <b>{metricText(t.metric, v)}</b>{' '}
                    {pending ? <span className="muted">进行中</span> : up ? <span className="nowrap" style={{ color: 'var(--good-ink)' }}>✓ 改善{d ? ` ${d}` : ''}</span> : <span className="muted nowrap">未改善（保留基线）</span>}
                  </div>
                )
              })}
            </li>
          ))}</ul>
        </Answer>
        <Answer q="最终集是否验证"><FinalAnswer b={b} /></Answer>
        <Answer q="对照组与预算是否一致">
          <div className="row" style={{ marginBottom: 6 }}><FairChip b={b} /></div>
          <p className="small" style={{ margin: '0 0 6px' }}>
            各组同一模型、同一上限：{b.limits ? `${b.limits.wall_clock_s} 秒 / ${b.limits.max_model_requests} 次请求 / ${b.limits.max_candidates} 个候选` : '未记录'}
          </p>
          <ul className="small">{b.modes.map((m) => {
            const runs = b.runs.filter((r) => r.mode === m)
            const req = runs.reduce((a, r) => a + (r.requests ?? 0), 0)
            const wall = runs.reduce((a, r) => a + (r.wallS ?? 0), 0)
            return <li key={m} className="mline"><ModeMark mode={m} />{rmode(m).label} 实耗 {req} 次请求 · {fmt.s(wall)} · <CostTotal costs={runs.map((r) => r.cost)} /></li>
          })}</ul>
          {costTotals(b.runs.map((r) => r.cost)).kinds.has('estimate') && b.pricing && <p className="small muted" style={{ margin: 0 }}>费用为 {b.pricing.currency} 标价估算</p>}
        </Answer>
      </div>
      <SourceNote state={apiState} error={apiError} entry={entry} />
    </div>
  )
}

function Answer({ q, children }: { q: string; children: ReactNode }) {
  return <div className="answer"><div className="q">{q}</div><div className="a">{children}</div></div>
}

function FinalAnswer({ b }: { b: RBatch }) {
  const counts = b.runs.reduce<Record<string, number>>((a, r) => ({ ...a, [r.final.state]: (a[r.final.state] ?? 0) + 1 }), {})
  if (b.finalEnabled === false || (counts.disabled ?? 0) === b.runs.length) {
    return (
      <>
        <Chip tone="warn" icon="!">未验证</Chip>
        <p className="small" style={{ margin: '8px 0 0' }}>本批是开发预实验，final 未启用。上面的改善只来自开发集，不能当作最终验收，也不算失败。</p>
      </>
    )
  }
  const order = ['passed', 'failed', 'error', 'missing', 'running', 'pending', 'disabled']
  return (
    <div className="row">
      {order.filter((s) => counts[s]).map((s) => {
        const [label, tone, icon] = FINAL[s]
        return <Chip key={s} tone={tone} icon={icon}>{label} {counts[s]}</Chip>
      })}
    </div>
  )
}
