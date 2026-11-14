import { api } from '../api'
import { usePoll } from '../hooks'
import { fmt } from '../labels'

/* System design in numbers: how much of the work the local small model did, and which key node brought the cloud
   large model in. Counts every finished real run in the store, control arms included. */
export function SystemPanel() {
  const s = usePoll(api.systemSummary, [], 0, false).data
  if (!s || !s.runs) return null
  const { split, calls, upgrades, routes } = s
  const small = calls.small?.requests ?? 0, large = calls.large?.requests ?? 0
  const reqTotal = small + large
  const parts: [string, number, string][] = [
    ['不调用模型（复用已验证程序）', split.no_model, 'var(--good)'],
    ['只用本地小模型', split.small_only, 'var(--series-1)'],
    ['用到云端大模型', split.large_used, 'var(--series-2)'],
  ]
  const nodes: [string, number][] = [
    ['小模型连续 2 个候选未达标 → 升级', upgrades.upgrade_two_misses],
    ['小模型 3 次请求仍无达标候选 → 升级', upgrades.upgrade_small_cap],
    ['全新任务族，没有任何同族经验 → 直接交给大模型', routes.new_family ?? 0],
    ['有同族记录但没有相近的成功 → 直接交给大模型', routes.new_conditions ?? 0],
    ...(upgrades.upgrade_decision_model ? [['决策模型判断需要升级', upgrades.upgrade_decision_model] as [string, number]] : []),
  ]
  const pct = (n: number, d: number) => (d ? `${Math.round((n / d) * 100)}%` : '—')
  return (
    <section className="card sys">
      <div className="spread wrap">
        <div>
          <div className="eyebrow">系统设计 · 全部 {s.runs} 次真实运行</div>
          <h2 style={{ margin: '4px 0 0' }}>本地小模型干主力，只在关键节点调用云端大模型</h2>
        </div>
        <span className="small muted">{s.runs - split.large_used}/{s.runs} 次运行（{pct(s.runs - split.large_used, s.runs)}）没有用到云端大模型</span>
      </div>
      <div className="sys-grid">
        <div>
          <div className="k">每次运行用了哪些模型</div>
          <div className="stack-bar" role="img" aria-label="运行按所用模型分组">
            {parts.map(([k, n, c]) => n > 0 && <i key={k} style={{ flexGrow: n, background: c }} title={`${k}：${n} 次`} />)}
          </div>
          <ul className="sys-legend">
            {parts.map(([k, n, c]) => <li key={k}><span style={{ background: c }} />{k}<b className="mono">{n}</b><span className="muted mono">{pct(n, s.runs)}</span></li>)}
          </ul>
        </div>
        <div>
          <div className="k">模型请求由谁完成</div>
          <div className="sys-big"><b className="mono">{pct(small, reqTotal)}</b><span>本地 Qwen · {small} 次 · 无 API 费用</span></div>
          <div className="sys-big"><b className="mono" style={{ color: 'var(--series-2)' }}>{pct(large, reqTotal)}</b><span>云端 GPT · {large} 次 · {fmt.usd(calls.large?.cost_usd ?? 0)} 估{calls.large?.unknown_cost ? `（另有 ${calls.large.unknown_cost} 次费用未知）` : ''}</span></div>
        </div>
        <div>
          <div className="k">什么时候叫大模型（程序规则，不由模型自评）</div>
          <ul className="sys-nodes">
            {nodes.map(([k, n]) => <li key={k}><span>{k}</span><b className="mono">{n}</b></li>)}
          </ul>
        </div>
      </div>
      <p className="small muted" style={{ margin: '12px 0 0' }}>统计范围包括对照组：无经验 v0、任务流里“不带记忆”一侧、分流器关闭的对照；这些组按设计更常用到大模型。研究对照批次（ALE 等）另见下方。</p>
    </section>
  )
}
