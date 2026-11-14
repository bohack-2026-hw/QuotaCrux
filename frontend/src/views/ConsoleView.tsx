import type { ReactNode } from 'react'
import { BatchFacts, CostText, CostTotal, FinalChip, ModeTag, RunLink, RunStateChip } from '../components/research'
import { Empty } from '../components/ui'
import { STUDY, fmt } from '../labels'
import type { RBatch, RRun, RTask } from '../research'
import { MODES } from '../research'
import { deltaText, metricText, stopText, sumText } from '../researchFormat'
import { useResearchBatch, useResearchList } from '../researchData'
import type { ApiState, BatchEntry } from '../researchData'

/* 后台: every recorded detail of a research batch in one place, as key-value blocks and one run ledger.
   The overview and the research page show only results; this page is where a reviewer checks them. */
export function ConsoleView({ selected, onSelect, onOpenRun }: { selected: string | null; onSelect: (id: string) => void; onOpenRun: (id: string) => void }) {
  const { entries, apiState, apiError } = useResearchList()
  const entry = entries.find((e) => e.id === selected) ?? entries[0] ?? null
  const { batch: b, error } = useResearchBatch(entry)
  if (!entry) return <div className="card"><Empty title="还没有研究批次" /></div>

  return (
    <div className="stack">
      {error && <div className="error small">{error}</div>}
      <div className="console-grid">
        <Block title="批次">
          {entries.length > 1 && (
            <select value={entry.id} onChange={(e) => onSelect(e.target.value)} style={{ marginBottom: 10 }}>
              {entries.map((e) => <option key={e.id} value={e.id}>{e.label ?? e.id}</option>)}
            </select>
          )}
          <KV rows={[
            ['研究', b ? `${STUDY[b.study]}${b.fixture ? ' · FIXTURE' : ''}` : '—'],
            ['名称', b?.label ?? '—'],
            ['ID', <span key="id" className="mono id-wrap">{entry.id}</span>],
            ['状态', b?.status ?? entry.status],
            ['一致性', b?.fair === true ? 'fair = true' : b?.fair === false ? 'fair = false' : 'fair = null'],
            ['开始', b?.createdAt?.replace('T', ' ').slice(0, 19) ?? '—'],
            ['结束', b?.endedAt?.replace('T', ' ').slice(0, 19) ?? '—'],
            ['进度', b ? `${b.finished} / ${b.planned}` : '—'],
          ]} />
        </Block>
        <Block title="数据来源"><Source state={apiState} error={apiError} entry={entry} /></Block>
        {b && <Block title="配置"><BatchFacts b={b} /></Block>}
        {b?.priceSnapshots && <Block title="价格快照">
          <KV rows={Object.entries(b.priceSnapshots).map(([role, p]) => [role, `${p.model ?? '?'} · ${p.currency} · 入 ${p.input_per_1m} / 出 ${p.output_per_1m} 每百万`])} />
        </Block>}
        {b?.fairness && <Block title="一致性">
          <KV rows={Object.entries(b.fairness).map(([k, v]) => [FAIRNESS[k] ?? k, <span key={k} className="mono">{Array.isArray(v) ? (v.length ? v.join(', ') : '无') : v === true ? '✓ 是' : v === false ? '✕ 否' : v == null ? '—' : String(v)}</span>])} />
        </Block>}
        {b && <Block title="用量">
          <KV rows={usageRows(b)} />
        </Block>}
      </div>

      {b && <Ledger b={b} archive={entry.source === 'archive'} onOpenRun={onOpenRun} />}
      {b && b.study === 'routing' && b.interactions.length > 0 && (
        <Block title="交互项 · both − action − model + baseline">
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>任务</th><th>重复</th><th>状态</th><th>值</th></tr></thead>
            <tbody>{b.interactions.map((x) => (
              <tr key={`${x.task_id}-${x.repeat}`}><td className="mono">{b.tasks.find((t) => t.id === x.task_id)?.title ?? x.task_id}</td><td className="mono">r{x.repeat}</td>
                <td>{x.status === 'completed' ? '完成' : '缺失或失败'}</td><td className="mono">{x.both_minus_action_minus_model_plus_baseline ?? '—'}</td></tr>
            ))}</tbody>
          </table></div>
        </Block>
      )}

      <Block title="口径">
        <ul className="rules">
          <li><b>final</b> disabled = 本批未启用；pending = 未到；passed / failed = 验收结果；error = 裁判异常；missing = 运行已结束但无结果。未测不计失败。</li>
          <li><b>fair</b> 三态：true / false / null（未确认，不当作通过）。</li>
          <li><b>开发最佳</b> 选择器保留的候选在开发集上的结果；加速比要求全部计时样本快于基线。</li>
          <li><b>score / speedup</b> 分开报告，不跨题、不跨硬件比较。</li>
          <li><b>费用</b> 调用前价格快照 × Token 的标价估算；缺失为未知，不按 0 计，不换算币种。</li>
          <li><b>重复</b> 每组次数少于 3 时只描述单次结果，不推断稳定性。</li>
          <li><b>study</b> feedback 与 routing 各自成批，组、基线与费用不合并；routing 的 fair 只表示协议可比，完成率与 final 另列。</li>
          <li><b>≥</b> 部分用量无法计价时只显示已知部分，作为下界，不当总额。</li>
        </ul>
      </Block>
    </div>
  )
}

const FAIRNESS: Record<string, string> = {
  tasks_with_mixed_configurations: '配置不一致的题', plan_matches: '计划一致', complete_variant_matrix: '变体矩阵完整',
  all_planned_runs_recorded: '全部已记录', all_planned_runs_completed: '全部完成', all_final_evaluations_completed: 'final 全部完成',
}

/** Totals over the runs that actually ran; a slot that never ran is not an unknown amount. */
function usageRows(b: RBatch): [string, ReactNode][] {
  const ran = b.runs.filter((r) => r.state !== 'planned')
  return [
    ['请求', sumText(ran.map((r) => r.requests), String)],
    ['输入 Token', sumText(ran.map((r) => r.inputTokens), fmt.n)],
    ['输出 Token', sumText(ran.map((r) => r.outputTokens), fmt.n)],
    ['墙钟', sumText(ran.map((r) => r.wallS), (v) => fmt.s(v))],
    ['模型等待', sumText(ran.map((r) => r.modelWaitS), (v) => fmt.s(v))],
    ['开发评测', sumText(ran.map((r) => r.devEvalS), (v) => fmt.s(v))],
    ['费用', <CostTotal key="cost" costs={ran.map((r) => r.cost)} />],
    ['未运行', `${b.runs.length - ran.length} 轮`],
  ]
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return <section className="card block"><div className="block-title">{title}</div>{children}</section>
}

function KV({ rows }: { rows: [string, ReactNode][] }) {
  return <dl className="facts">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
}

function Source({ state, error, entry }: { state: ApiState; error: string | null; entry: BatchEntry }) {
  return (
    <KV rows={[
      ['来源', entry.source === 'archive' ? '仓库存档' : '研究接口'],
      ['路径', entry.source === 'archive' ? <span key="p" className="mono id-wrap">{entry.archivePath}</span> : <span key="p" className="mono">/api/research-comparisons/{entry.id}</span>],
      ['接口', state === 'ok' ? '可用' : state === 'missing' ? '未提供' : state === 'loading' ? '连接中' : `不可用${error ? `（${error}）` : ''}`],
      ['写入', '只读'],
    ]} />
  )
}

function Ledger({ b, archive, onOpenRun }: { b: RBatch; archive: boolean; onOpenRun: (id: string) => void }) {
  const routing = b.study === 'routing'
  const rows = b.tasks.flatMap((t) => [...t.runs]
    .sort((x, y) => x.repeat - y.repeat || MODES.indexOf(x.mode as never) - MODES.indexOf(y.mode as never))
    .map((r) => ({ t, r })))
  return (
    <section className="card block">
      <div className="block-title">逐轮明细 · {rows.length}</div>
      <div className="tbl-wrap">
        <table className="tbl pair-table">
          <thead><tr>
            <th>任务</th><th>组</th><th>状态</th><th>结束</th><th>开发最佳</th><th>相对基线</th><th>final</th><th>候选</th><th>请求</th>
            {routing && <><th>路由</th><th>small / large</th><th>路由请求</th><th>升级</th></>}
            <th>Token 入 / 出</th><th>墙钟</th><th>等待</th><th>费用</th><th />
          </tr></thead>
          <tbody>{rows.map(({ t, r }, i) => (
            <tr key={`${t.id}-${r.seq}`} className={i > 0 && rows[i - 1].t.id !== t.id ? 'group-start' : ''}>
              <td className="nowrap"><b>{t.title}</b></td>
              <td className="nowrap"><ModeTag mode={r.mode} repeat={r.repeat} /></td>
              <td className="nowrap"><RunStateChip run={r} /></td>
              <td className="nowrap small">{stopText(r)}</td>
              <td className="nowrap mono"><Dev t={t} r={r} /></td>
              <td className="nowrap mono">{r.dev.value == null ? '—' : r.dev.initial ? '0' : t.metric === 'score' ? deltaText(t, r.dev.value) ?? '—' : `${r.dev.value.toFixed(4)}×`}</td>
              <td className="nowrap"><FinalChip run={r} />{r.final.value != null && <span className="mono small"> {metricText(t.metric, r.final.value)}{r.final.normalized ? ' (c0 归一化)' : ''}</span>}</td>
              <td className="nowrap mono">{r.passed ?? '?'}/{r.proposed ?? '?'}</td>
              <td className="nowrap mono">{r.requests ?? '?'}/{b.limits?.max_model_requests ?? '?'}</td>
              {routing && <>
                <td className="nowrap mono small">{r.routing ? `${r.routing.action ?? '?'} / ${r.routing.model ?? '?'}` : '—'}</td>
                <td className="nowrap mono">{r.calls.small ?? '—'} / {r.calls.large ?? '—'}</td>
                <td className="nowrap mono">{r.calls.routing ?? '—'}</td>
                <td className="nowrap mono">{r.calls.upgrades ?? '—'}</td>
              </>}
              <td className="nowrap mono">{fmt.n(r.inputTokens)} / {fmt.n(r.outputTokens)}</td>
              <td className="nowrap mono">{fmt.s(r.wallS)}</td>
              <td className="nowrap mono">{fmt.s(r.modelWaitS)}</td>
              <td className="nowrap mono"><CostText c={r.cost} /></td>
              <td className="nowrap"><RunLink run={r} archive={archive} onOpenRun={onOpenRun} /></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  )
}

function Dev({ t, r }: { t: RTask; r: RRun }) {
  if (r.state === 'planned') return <span className="muted">—</span>
  if (r.dev.value == null) return <span className="muted">无</span>
  return <>{metricText(t.metric, r.dev.value)} <span className="muted">{r.dev.candidate}</span></>
}
