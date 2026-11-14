// Builds the archived research batch the dashboard shows until the read-only research API (#2) is wired in.
// Input: the committed second native pilot under docs/research/native-r2-20261114 (real runs, dev-only).
// Output: src/samples/research-native-r2.json in the draft contract shape (src/research.ts).
// Only fields already in the archive are copied; nothing is estimated here except what the archive states.
//   node scripts/research-sample.mjs
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const dir = 'docs/research/native-r2-20261114'
const src = join(here, '..', '..', dir)
const out = join(here, '..', 'src', 'samples', 'research-native-r2.json')
const read = (p) => JSON.parse(readFileSync(join(src, p), 'utf8'))

const cmp = read('comparison.json')
const summary = read('summary.json')
const manifest = read('manifest.json')
const reports = Object.fromEntries(cmp.runs.map((r) => [r.run_id, read(`${r.run_id}/report.json`)]))

const role = cmp.fixed_model
const m = manifest.models[role]
const host = new URL(m.base_url).hostname
const hosted = !['localhost', '127.0.0.1', '::1'].includes(host)

const tasks = []
for (const r of cmp.runs) {
  if (tasks.some((t) => t.task_id === r.task_id)) continue
  const t = reports[r.run_id].task
  const s = summary.runs.find((x) => x.run_id === r.run_id)
  tasks.push({
    task_id: t.task_id,
    family: t.family,
    title: t.presentation?.title ?? t.task_id,
    objective: {
      metric: t.objective.metric,
      direction: t.objective.direction,
      baseline: t.objective.metric === 'score' ? r.best_dev?.objective?.baseline ?? null : 1,
      min_speedup: t.objective.min_speedup ?? null,
    },
    dev_cases: s?.dev_case_count ?? null,
    final_cases: null,
  })
}

const trimUsage = (u) => ({
  requests: u.requests, ok: u.ok, errors: u.errors,
  input_tokens: u.input_tokens, cached_input_tokens: u.cached_input_tokens, output_tokens: u.output_tokens,
  reasoning_tokens: u.reasoning_tokens, cost_usd: u.cost_usd, cost_status: u.cost_status,
})

const runs = cmp.runs.map((r) => {
  const rep = reports[r.run_id]
  const s = summary.runs.find((x) => x.run_id === r.run_id)
  const { cases: _cases, ...objective } = r.best_dev?.objective ?? {}
  return {
    seq: r.seq, task_id: r.task_id, repeat: r.repeat, mode: r.mode, run_id: r.run_id,
    status: r.status, stop_reason: r.stop_reason, started_at: rep.started_at, ended_at: rep.ended_at,
    outcome: r.outcome,
    // Proposed for #2: final state as its own field so "not enabled" never reads as "failed".
    final: { enabled: cmp.final_evaluation, state: cmp.final_evaluation ? (r.outcome.final_evaluated ? 'completed' : 'missing') : 'disabled',
      correct: r.outcome.final_correct, value: r.outcome.final_objective?.value ?? r.outcome.final_speedup ?? null },
    best_candidate_id: r.best_candidate_id,
    best_dev: r.best_dev ? { ...r.best_dev, objective: r.best_dev.objective ? objective : null } : null,
    candidates: { proposed: s.candidates_proposed, passed: s.candidates_passed, unique_ast: s.unique_ast_candidates },
    iterations: r.iterations,
    timing: r.timing,
    usage: trimUsage(r.usage),
    estimated_cost: r.estimated_cny == null ? null
      : { amount: r.estimated_cny, currency: summary.pricing.currency, basis: 'list_price', note: r.cost_note },
    progress: r.progress.map((p) => ({
      elapsed_s: p.elapsed_s, model_requests: p.model_requests, tokens: p.tokens,
      input_tokens: p.usage.input_tokens, cached_input_tokens: p.usage.cached_input_tokens, output_tokens: p.usage.output_tokens,
      metric: p.metric, value: p.value, best_candidate_id: p.best_candidate_id,
    })),
    record: `${dir}/${r.run_id}/research.md`,
  }
})

const sample = {
  contract: 'research-comparison/v0-draft',
  comparison_id: cmp.comparison_id,
  status: cmp.status,
  label: cmp.label,
  protocol: cmp.protocol,
  scope: summary.scope,
  fair: cmp.fair,
  created_at: manifest.started_at,
  ended_at: runs.map((r) => r.ended_at).sort().at(-1),
  code_commit: manifest.git_commit,
  prompt_version: reports[cmp.runs[0].run_id].config.prompt.version,
  fixed_model: role,
  model: { role, name: m.model, provider: m.provider, host, hosted },
  final_evaluation: cmp.final_evaluation,
  modes: [...new Set(cmp.runs.map((r) => r.mode))],
  repeats: Math.max(...cmp.runs.map((r) => r.repeat)),
  limits: cmp.limits,
  measure: cmp.measure,
  pricing: { ...summary.pricing, cached_input: summary.pricing.input, fetched_at: null },
  tasks,
  runs,
  source: { kind: 'archive', path: dir },
}

mkdirSync(dirname(out), { recursive: true })
writeFileSync(out, JSON.stringify(sample, null, 2) + '\n')
console.log(`wrote ${out}: ${runs.length} runs, ${tasks.length} tasks`)
