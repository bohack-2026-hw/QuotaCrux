// Within-task research comparisons: the read-only contract from #2 and the one place its states are decided.
// Primary shape: research-comparison-v1 (GET /api/research-comparisons[/{id}], backend research_views.py): the
// comparison JSON plus api_contract, dev_only, price_snapshot and per-run task / final_status / dev_status / cost.
// Older comparison.json files (no v1 fields) still render: every v1 field has a fallback from what they record.
// No runtime imports: scripts/check-research.ts runs this file directly under Node.

export type ResearchMode = 'feedback' | 'independent' | 'no_feedback'
export const MODES: ResearchMode[] = ['feedback', 'independent', 'no_feedback']

/* ---------- raw contract (research-comparison-v1, with fallbacks for older JSON) ---------- */

export interface RawObjective { metric?: string; direction?: string; value?: number | null; baseline?: number | null; min_speedup?: number | null }
export interface RawUsage {
  requests?: number; input_tokens?: number | null; cached_input_tokens?: number | null; output_tokens?: number | null
  cost_usd?: number | null; cost_status?: string
}
export interface RawPoint {
  elapsed_s: number; model_requests?: number; tokens?: number | null; metric?: string; value: number | null; best_candidate_id?: string | null
  input_tokens?: number | null; cached_input_tokens?: number | null; output_tokens?: number | null
  usage?: RawUsage; estimated_cost?: number | null
}
export interface RawPricing {
  currency: string; unit?: string; input: number; output: number; cached_input?: number | null
  source?: string; method?: string; fetched_at?: string | null
}
export interface RawPriceSnapshot {
  model?: string; currency: string; unit?: string; input_per_1m: number; output_per_1m: number; source?: string; retrieved_at?: string
}
export interface RawCost { amount: number | null; currency: string | null; status?: string; source?: string | null; note?: string }
export interface RawRun {
  seq: number; task_id: string; repeat: number; mode: string; run_id?: string | null
  task?: RawTask | null
  final_status?: string | null; dev_status?: string | null
  final_evaluation?: { status?: string; correct?: boolean | null; speedup?: number | null; objective?: RawObjective | null; normalized?: boolean; measured?: boolean } | null
  cost?: RawCost | null
  status?: string | null; stop_reason?: string | null; started_at?: string | null; ended_at?: string | null
  outcome?: {
    dev_improved?: boolean; best_is_initial?: boolean; final_evaluated?: boolean; final_correct?: boolean | null
    final_speedup?: number | null; final_objective?: RawObjective | null; goal_met?: boolean
    final_status?: string | null; final_error?: string | null
  } | null
  final?: { enabled?: boolean | null; state?: string | null; correct?: boolean | null; value?: number | null; error?: string | null } | null
  best_candidate_id?: string | null
  best_dev?: { status?: string; correct?: number | boolean | null; speedup?: number | null; improved?: number | boolean | null; objective?: RawObjective | null } | null
  candidates?: { proposed?: number; passed?: number; unique_ast?: number } | null
  iterations?: Record<string, number | null> | null
  timing?: Record<string, number | null> | null
  usage?: RawUsage | null
  estimated_cost?: { amount: number | null; currency: string; basis?: string; note?: string } | null
  estimated_cny?: number | null
  progress?: RawPoint[] | null
  record?: string | null
  error?: string | null
}
export interface RawTask {
  task_id: string; family?: string | null; title?: string; workload?: string; objective?: RawObjective; dev_cases?: number | null; final_cases?: number | null
}
export interface RawBatch {
  contract?: string; api_contract?: string; dev_only?: boolean; price_snapshot?: RawPriceSnapshot | null; comparison_id: string; status: string; label?: string | null; protocol?: string | null; scope?: string | null
  fair?: boolean | null; created_at?: string | null; ended_at?: string | null; code_commit?: string | null; prompt_version?: string | null
  fixed_model?: string | null; model?: { role?: string; name?: string; provider?: string; host?: string; hosted?: boolean | null } | null
  final_evaluation?: boolean | null; modes?: string[]; repeats?: number
  limits?: { max_model_requests?: number; max_candidates?: number; wall_clock_s?: number } | null
  measure?: { repeats?: number; function_warmups?: number; cpuset_cpus?: string | null } | null
  pricing?: RawPricing | null
  tasks?: RawTask[]
  runs: RawRun[]
  error?: string | null
  source?: { kind: string; path?: string }
}
export interface RawBatchRow {
  comparison_id: string; status: string; label?: string | null; protocol?: string | null; created_at?: string | null
  fair?: boolean | null; final_evaluation?: boolean | null; dev_only?: boolean; task_ids?: string[]; modes?: string[]
  runs_total?: number; runs_finished?: number; final_status_counts?: Record<string, number>; cost?: RawCost | null
}

/* ---------- view model ---------- */

export type RunState = 'planned' | 'running' | 'completed' | 'stopped' | 'failed' | 'interrupted'
/** disabled = dev-only batch; pending/running = not reached yet; missing = enabled but no result after the run ended. */
export type FinalState = 'disabled' | 'pending' | 'running' | 'passed' | 'failed' | 'error' | 'missing'
export type Metric = 'score' | 'speedup'
export interface Cost { kind: 'estimate' | 'billed' | 'unknown' | 'none'; amount: number | null; currency: string | null; note: string | null }
export interface Point { t: number; tokens: number | null; cost: number | null; value: number | null; candidate: string | null }

export interface RRun {
  seq: number; taskId: string; repeat: number; mode: string; runId: string | null; state: RunState; stopReason: string | null
  metric: Metric
  dev: { value: number | null; improved: boolean | null; candidate: string | null; initial: boolean; status: string | null }
  final: { state: FinalState; correct: boolean | null; value: number | null; error: string | null; normalized: boolean }
  requests: number | null; inputTokens: number | null; outputTokens: number | null; tokens: number | null
  wallS: number | null; modelWaitS: number | null; devEvalS: number | null
  proposed: number | null; passed: number | null
  cost: Cost
  progress: Point[]
  record: string | null; error: string | null
}
export interface RTask {
  id: string; family: string; title: string; metric: Metric; direction: string; baseline: number | null; minSpeedup: number | null
  devCases: number | null; finalCases: number | null; modes: string[]; repeats: number[]; runs: RRun[]
}
export interface RBatch {
  id: string; label: string | null; status: string; running: boolean; protocol: string | null; scope: string | null
  fair: boolean | null; finalEnabled: boolean | null; contract: string | null
  model: { role: string | null; name: string | null; hosted: boolean | null; provider: string | null } | null
  modes: string[]; limits: RawBatch['limits']; measure: RawBatch['measure']; pricing: RawPricing | null
  codeCommit: string | null; promptVersion: string | null; createdAt: string | null; endedAt: string | null
  tasks: RTask[]; runs: RRun[]; planned: number; finished: number; error: string | null
}

const RUNNING_RUN = new Set(['running'])
const ENDED_BAD = new Set(['failed', 'stopped', 'interrupted'])

export function runState(r: RawRun): RunState {
  if (!r.run_id && !r.status) return 'planned'
  if (r.status === 'not_run' || r.status === 'pending' || r.status === 'planned') return 'planned'
  const s = r.status ?? 'running'
  if (RUNNING_RUN.has(s)) return 'running'
  if (ENDED_BAD.has(s)) return s as RunState
  if (s === 'completed') return 'completed'
  return r.run_id ? 'running' : 'planned'
}

/** The final verdict never borrows from the batch status: a completed batch can hold a final that errored. */
export function finalState(r: RawRun, batchFinal: boolean | null | undefined, state: RunState): FinalState {
  const f = r.final
  const enabled = f?.enabled ?? batchFinal ?? null
  const evaluated = r.outcome?.final_evaluated ?? null
  const correct = f?.correct ?? r.final_evaluation?.correct ?? r.outcome?.final_correct ?? null
  // v1: final_status is decided by the backend; a recorded final_error stays an error, not a plain failure.
  if (r.final_status && !f?.state) {
    if (r.outcome?.final_error) return 'error'
    switch (r.final_status) {
      case 'disabled': return 'disabled'
      case 'pending': return 'pending'
      case 'completed': return correct === false ? 'failed' : 'passed'
      case 'failed': return 'failed'
      case 'not_run': return state === 'planned' || state === 'running' ? 'pending' : 'missing'
    }
  }
  if (f?.state) {
    switch (f.state) {
      case 'disabled': return 'disabled'
      case 'pending': case 'planned': return 'pending'
      case 'running': return 'running'
      case 'failed': return 'failed'
      case 'error': case 'exception': return 'error'
      case 'missing': case 'incomplete': return state === 'planned' || state === 'running' ? 'pending' : 'missing'
      case 'completed': return correct == null ? 'error' : correct ? 'passed' : 'failed'
    }
  }
  if (enabled === false) return 'disabled'
  if (evaluated) return correct == null ? 'error' : correct ? 'passed' : 'failed'
  if (state === 'planned' || state === 'running') return 'pending'
  // enabled (or not recorded) and the run is over without a final result: never shown as a pass or a plain failure.
  return 'missing'
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const sumKnown = (...vs: (number | null | undefined)[]) => (vs.every((v) => v == null) ? null : vs.reduce<number>((a, v) => a + (v ?? 0), 0))

function metricOf(r: RawRun, task?: RawTask): Metric {
  const m = task?.objective?.metric ?? r.task?.objective?.metric ?? r.best_dev?.objective?.metric ?? r.progress?.find((p) => p.metric)?.metric
  return m === 'score' ? 'score' : 'speedup'
}

function devOf(r: RawRun, metric: Metric) {
  const b = r.best_dev
  const initial = (r.best_candidate_id ?? null) === 'c0' || !!r.outcome?.best_is_initial
  let value: number | null = null
  if (b) value = metric === 'score' ? num(b.objective?.value) : num(b.speedup) ?? (initial && b.status === 'passed' ? 1 : null)
  const improved = b?.improved == null ? r.outcome?.dev_improved ?? null : !!b.improved
  return { value, improved: value == null && improved == null ? null : improved, candidate: r.best_candidate_id ?? null, initial, status: b?.status ?? null }
}

export function priceOf(p: RawPricing | null | undefined, input: number | null | undefined, cached: number | null | undefined, output: number | null | undefined): number | null {
  if (!p || input == null || output == null) return null
  const c = Math.min(cached ?? 0, input)
  const cachedRate = p.cached_input ?? p.input
  return ((input - c) * p.input + c * cachedRate + output * p.output) / 1e6
}

export function costOf(r: RawRun, pricing: RawPricing | null | undefined): Cost {
  const c = r.cost
  if (c) {
    if (c.status === 'no_model_calls') return { kind: 'none', amount: c.amount ?? 0, currency: c.currency, note: null }
    if (c.amount != null && c.currency) return { kind: c.status === 'billed' ? 'billed' : 'estimate', amount: c.amount, currency: c.currency, note: c.note ?? null }
    return { kind: 'unknown', amount: null, currency: c.currency, note: c.note ?? null }
  }
  const e = r.estimated_cost
  if (e && e.amount != null) return { kind: 'estimate', amount: e.amount, currency: e.currency, note: e.note ?? null }
  if (r.estimated_cny != null) return { kind: 'estimate', amount: r.estimated_cny, currency: 'CNY', note: null }
  const u = r.usage
  if (u?.cost_usd != null && u.cost_status === 'estimated') return { kind: 'estimate', amount: u.cost_usd, currency: 'USD', note: '按官方价表估算' }
  if (u?.cost_usd != null) return { kind: 'billed', amount: u.cost_usd, currency: 'USD', note: null }
  if (u?.cost_status === 'no_model_calls' || u?.cost_status === 'local_no_api_fee') return { kind: 'none', amount: null, currency: null, note: u.cost_status }
  // Tokens are known but no price was recorded for this run: an estimate needs the batch's price snapshot.
  const est = priceOf(pricing, u?.input_tokens, u?.cached_input_tokens, u?.output_tokens)
  if (est != null && pricing) return { kind: 'estimate', amount: est, currency: pricing.currency, note: '按批次价格快照由 Token 推算' }
  return { kind: 'unknown', amount: null, currency: null, note: null }
}

function progressOf(r: RawRun, pricing: RawPricing | null | undefined): Point[] {
  return (r.progress ?? []).map((p) => {
    const input = p.input_tokens ?? p.usage?.input_tokens ?? null
    const cached = p.cached_input_tokens ?? p.usage?.cached_input_tokens ?? null
    const output = p.output_tokens ?? p.usage?.output_tokens ?? null
    return {
      t: p.elapsed_s, value: num(p.value), candidate: p.best_candidate_id ?? null,
      tokens: num(p.tokens) ?? sumKnown(input, output),
      cost: num(p.estimated_cost) ?? priceOf(pricing, input, cached, output),
    }
  })
}

/** v1 carries the frozen price snapshot; older JSON may carry the draft `pricing` object. */
export function pricingOf(raw: RawBatch): RawPricing | null {
  if (raw.pricing) return raw.pricing
  const p = raw.price_snapshot
  if (!p) return null
  return { currency: p.currency, unit: p.unit, input: p.input_per_1m, output: p.output_per_1m, cached_input: p.input_per_1m,
    source: p.source, fetched_at: p.retrieved_at ?? null, method: 'list price; cached input at the input rate' }
}

const FAMILY_TITLE: Record<string, string> = { 'ale-bench': 'ALE-Bench', algotune: 'AlgoTune', kernelbench: 'KernelBench', effibench: 'EffiBench-X' }

/** "algotune-convolve_1d-smoke-eeb3cd9d83" -> "AlgoTune · convolve_1d" when no title is recorded. */
export function titleOf(taskId: string, family: string): string {
  if (!taskId.startsWith(`${family}-`)) return taskId
  const name = taskId.slice(family.length + 1).split('-')[0]
  return name ? `${FAMILY_TITLE[family] ?? family} · ${name}` : taskId
}

export function normalize(raw: RawBatch): RBatch {
  const pricing = pricingOf(raw)
  const taskMeta = new Map<string, RawTask>((raw.tasks ?? []).map((t) => [t.task_id, t]))
  for (const r of raw.runs) if (r.task && !taskMeta.has(r.task_id)) taskMeta.set(r.task_id, r.task)
  const finalEnabled = raw.dev_only != null ? !raw.dev_only : raw.final_evaluation ?? null
  const runs: RRun[] = raw.runs.map((r) => {
    const meta = taskMeta.get(r.task_id)
    const metric = metricOf(r, meta)
    const state = runState(r)
    const u = r.usage ?? {}
    const t = r.timing ?? {}
    const it = r.iterations ?? {}
    return {
      seq: r.seq, taskId: r.task_id, repeat: r.repeat, mode: r.mode, runId: r.run_id ?? null, state, stopReason: r.stop_reason ?? null,
      metric, dev: devOf(r, metric),
      final: {
        state: finalState(r, finalEnabled, state),
        correct: r.final?.correct ?? r.final_evaluation?.correct ?? r.outcome?.final_correct ?? null,
        value: r.final?.value ?? num(r.final_evaluation?.objective?.value) ?? num(r.final_evaluation?.speedup)
          ?? num(r.outcome?.final_objective?.value) ?? num(r.outcome?.final_speedup),
        error: r.final?.error ?? r.outcome?.final_error ?? null,
        normalized: !!r.final_evaluation?.normalized,
      },
      requests: num(u.requests) ?? num(it.model_requests),
      inputTokens: num(u.input_tokens), outputTokens: num(u.output_tokens),
      tokens: u.input_tokens == null && u.output_tokens == null ? null : (u.input_tokens ?? 0) + (u.output_tokens ?? 0),
      wallS: num(t.wall_clock_total_s) ?? num(t.agent_loop_s), modelWaitS: num(t.model_wait_s), devEvalS: num(t.dev_evaluation_s),
      proposed: r.candidates?.proposed ?? num(it.candidates_proposed), passed: r.candidates?.passed ?? num(it.candidates_passed),
      cost: costOf(r, pricing),
      progress: progressOf(r, pricing),
      record: r.record ?? null, error: r.error ?? null,
    }
  })
  const order: string[] = []
  for (const r of raw.runs) if (!order.includes(r.task_id)) order.push(r.task_id)
  const tasks: RTask[] = order.map((id) => {
    const meta = taskMeta.get(id)
    const own = runs.filter((r) => r.taskId === id)
    const metric = own[0]?.metric ?? 'speedup'
    const scoreBaseline = raw.runs.find((r) => r.task_id === id && r.best_dev?.objective?.baseline != null)?.best_dev?.objective?.baseline ?? null
    const family = meta?.family ?? familyOf(id)
    return {
      id, family, title: meta?.title ?? titleOf(id, family), metric,
      direction: meta?.objective?.direction ?? 'maximize',
      baseline: meta?.objective?.baseline ?? (metric === 'speedup' ? 1 : scoreBaseline),
      minSpeedup: meta?.objective?.min_speedup ?? null,
      devCases: meta?.dev_cases ?? null, finalCases: meta?.final_cases ?? null,
      modes: (MODES as string[]).filter((m) => own.some((r) => r.mode === m)).concat([...new Set(own.map((r) => r.mode))].filter((m) => !(MODES as string[]).includes(m))),
      repeats: [...new Set(own.map((r) => r.repeat))].sort((a, b) => a - b),
      runs: own,
    }
  })
  const modes = raw.modes?.length ? raw.modes : MODES.filter((m) => runs.some((r) => r.mode === m))
  return {
    id: raw.comparison_id, label: raw.label ?? null, status: raw.status, running: raw.status === 'running', protocol: raw.protocol ?? null,
    scope: raw.scope ?? null, fair: raw.fair ?? null, finalEnabled, contract: raw.api_contract ?? raw.contract ?? null,
    model: raw.model ? { role: raw.model.role ?? raw.fixed_model ?? null, name: raw.model.name ?? null, hosted: raw.model.hosted ?? null, provider: raw.model.provider ?? null }
      : raw.fixed_model || raw.price_snapshot?.model ? { role: raw.fixed_model ?? null, name: raw.price_snapshot?.model ?? null, hosted: null, provider: null } : null,
    modes, limits: raw.limits ?? null, measure: raw.measure ?? null, pricing,
    codeCommit: raw.code_commit ?? null, promptVersion: raw.prompt_version ?? null, createdAt: raw.created_at ?? null, endedAt: raw.ended_at ?? null,
    tasks, runs, planned: runs.length, finished: runs.filter((r) => r.state !== 'planned' && r.state !== 'running').length, error: raw.error ?? null,
  }
}

export function familyOf(taskId: string): string {
  for (const f of ['ale-bench', 'algotune', 'kernelbench', 'effibench']) if (taskId.startsWith(f)) return f
  return taskId.split('-')[0]
}

/** fair is three-state: true (checked and equal), false (checked and different), null (not checked yet, or never). */
export function fairLabel(fair: boolean | null, running: boolean): { text: string; tone: 'good' | 'bad' | 'warn'; icon: string } {
  if (fair === true) return { text: '配置一致', tone: 'good', icon: '✓' }
  if (fair === false) return { text: '配置不一致', tone: 'bad', icon: '✕' }
  return { text: running ? '一致性待确认（批次未完成）' : '一致性未确认', tone: 'warn', icon: '?' }
}

/** Sums that stay honest: a total is "partial" as soon as one run's value is unknown. */
export function total(vs: (number | null)[]): { value: number | null; partial: boolean } {
  const known = vs.filter((v): v is number => v != null)
  return { value: known.length ? known.reduce((a, b) => a + b, 0) : null, partial: known.length < vs.length }
}

/** Cost totals per currency; amounts in different currencies are never added or converted. */
export function costTotals(costs: Cost[]): { byCurrency: Record<string, number>; unknown: number; kinds: Set<Cost['kind']> } {
  const byCurrency: Record<string, number> = {}
  let unknown = 0
  const kinds = new Set<Cost['kind']>()
  for (const c of costs) {
    kinds.add(c.kind)
    if (c.amount != null && c.currency) byCurrency[c.currency] = (byCurrency[c.currency] ?? 0) + c.amount
    else if (c.kind === 'unknown') unknown += 1
  }
  return { byCurrency, unknown, kinds }
}

export function median(vs: number[]): number | null {
  if (!vs.length) return null
  const s = [...vs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}
