// State checks for src/research.ts against the archived real batch and the states it must also handle.
//   node --experimental-strip-types scripts/check-research.ts
import { readFileSync } from 'node:fs'
import { strict as assert } from 'node:assert'
import { VARIANTS, costTotals, fairLabel, finalState, normalize, runState } from '../src/research.ts'
import { bestOf, modeSummary, resultOf } from '../src/researchFormat.ts'
import type { RawBatch, RawRun } from '../src/research.ts'

const sample: RawBatch = JSON.parse(readFileSync(new URL('../src/samples/research-native-r2.json', import.meta.url), 'utf8'))
const clone = (): RawBatch => JSON.parse(JSON.stringify(sample))
let n = 0
const check = (name: string, fn: () => void) => { fn(); n += 1; console.log(`ok ${n} - ${name}`) }

check('archived batch: dev-only finals are "disabled", never failed', () => {
  const b = normalize(sample)
  assert.equal(b.finalEnabled, false)
  assert.ok(b.runs.every((r) => r.final.state === 'disabled'))
  assert.equal(b.fair, true)
  assert.equal(b.finished, 4)
})

check('archived batch: convolve feedback keeps 1.8343x on dev, ALE uses raw score', () => {
  const b = normalize(sample)
  const conv = b.runs.find((r) => r.taskId.startsWith('algotune') && r.mode === 'feedback')!
  assert.equal(conv.metric, 'speedup')
  assert.equal(conv.dev.value!.toFixed(4), '1.8343')
  assert.equal(conv.dev.improved, true)
  const aleF = b.runs.find((r) => r.taskId.startsWith('ale') && r.mode === 'feedback')!
  const aleI = b.runs.find((r) => r.taskId.startsWith('ale') && r.mode === 'independent')!
  assert.equal(aleF.metric, 'score')
  assert.deepEqual([aleF.dev.value, aleF.dev.initial, aleF.dev.improved], [17753, true, false])
  assert.deepEqual([aleI.dev.value, aleI.dev.improved], [18230, true])
  assert.equal(b.tasks.find((t) => t.metric === 'score')!.baseline, 17753)
})

check('archived batch: costs stay CNY estimates and sum to the report total', () => {
  const b = normalize(sample)
  const t = costTotals(b.runs.map((r) => r.cost))
  assert.deepEqual(Object.keys(t.byCurrency), ['CNY'])
  assert.equal(t.byCurrency.CNY.toFixed(4), '1.1951')
  assert.equal(t.unknown, 0)
  // every progress point gets a cost from the batch price snapshot and its own token counts
  const run = b.runs[0]
  assert.ok(run.progress.every((p) => p.cost != null && p.tokens != null))
  assert.equal(b.model?.name, 'Qwen3.8-27B')
  assert.equal(b.contract, 'research-comparison-v1')
})

check('running batch: fair null is "pending", planned and running runs have no final verdict', () => {
  const raw = clone()
  raw.status = 'running'
  raw.fair = null
  raw.final_evaluation = true
  raw.dev_only = false
  const running: RawRun = { ...raw.runs[1], status: 'running', final_status: 'pending', outcome: null, best_dev: null, progress: [], usage: null, cost: { amount: null, currency: 'CNY', status: 'unknown' }, timing: null }
  const planned: RawRun = { seq: 5, task_id: raw.runs[0].task_id, repeat: 2, mode: 'no_feedback', status: 'not_run', final_status: 'not_run' }
  raw.runs = [raw.runs[0], running, planned].map((r, i) => (i === 0 ? { ...r, final_status: 'not_run' } : r))
  const b = normalize(raw)
  assert.deepEqual(b.runs.map((r) => r.state), ['completed', 'running', 'planned'])
  assert.deepEqual(b.runs.map((r) => r.final.state), ['missing', 'pending', 'pending'])
  assert.equal(b.runs[2].cost.kind, 'not_run')
  assert.equal(b.runs[2].cost.amount, null)
  assert.equal(fairLabel(b.fair, b.running).tone, 'warn')
  assert.equal(fairLabel(false, false).tone, 'bad')
  assert.equal(b.finished, 1)
})

check('v1 final_status: completed/failed/not_run/disabled, final_error stays an error', () => {
  const base: RawRun = { seq: 1, task_id: 't', repeat: 1, mode: 'feedback', run_id: 'r', status: 'completed' }
  assert.equal(finalState({ ...base, final_status: 'completed', final_evaluation: { status: 'passed', correct: true } }, true, 'completed'), 'passed')
  assert.equal(finalState({ ...base, final_status: 'failed' }, true, 'completed'), 'failed')
  assert.equal(finalState({ ...base, final_status: 'failed', outcome: { final_error: 'judge crashed' } }, true, 'completed'), 'error')
  assert.equal(finalState({ ...base, final_status: 'not_run' }, true, 'completed'), 'missing')
  assert.equal(finalState({ ...base, status: 'not_run', final_status: 'not_run' }, true, 'planned'), 'pending')
  assert.equal(finalState({ ...base, final_status: 'disabled' }, false, 'completed'), 'disabled')
  assert.equal(runState({ ...base, status: 'not_run' }), 'planned')
})

check('final states: passed, failed, error and an exception inside a completed batch', () => {
  const base: RawRun = { seq: 1, task_id: 't', repeat: 1, mode: 'feedback', run_id: 'r', status: 'completed' }
  assert.equal(finalState({ ...base, outcome: { final_evaluated: true, final_correct: true } }, true, 'completed'), 'passed')
  assert.equal(finalState({ ...base, outcome: { final_evaluated: true, final_correct: false } }, true, 'completed'), 'failed')
  assert.equal(finalState({ ...base, final: { state: 'error', error: 'judge crashed' } }, true, 'completed'), 'error')
  assert.equal(finalState({ ...base, final: { state: 'completed', correct: null } }, true, 'completed'), 'error')
  assert.equal(finalState({ ...base }, true, 'completed'), 'missing')
  assert.equal(finalState({ ...base }, false, 'completed'), 'disabled')
})

check('run states: interrupted, stopped and failed runs are not "completed"', () => {
  const base: RawRun = { seq: 1, task_id: 't', repeat: 1, mode: 'feedback', run_id: 'r' }
  assert.equal(runState({ ...base, status: 'interrupted' }), 'interrupted')
  assert.equal(runState({ ...base, status: 'stopped' }), 'stopped')
  assert.equal(runState({ ...base, status: 'failed' }), 'failed')
  assert.equal(runState({ seq: 1, task_id: 't', repeat: 1, mode: 'feedback' }), 'planned')
})

check('current JSON without proposed fields: estimated_cny, no tasks, no pricing', () => {
  const raw = clone()
  delete raw.price_snapshot; delete raw.model; delete raw.dev_only; delete raw.api_contract
  raw.runs = raw.runs.map((r) => ({ ...r, task: undefined, final_status: undefined, dev_status: undefined, cost: undefined, estimated_cny: r.cost?.amount ?? null }))
  const b = normalize(raw)
  assert.ok(b.runs.every((r) => r.final.state === 'disabled'))
  assert.ok(b.runs.every((r) => r.cost.kind === 'estimate' && r.cost.currency === 'CNY'))
  assert.ok(b.runs.every((r) => r.progress.every((p) => p.cost == null)))
  assert.equal(b.tasks.find((t) => t.metric === 'score')!.baseline, 17753)
  assert.equal(b.tasks.find((t) => t.metric === 'speedup')!.baseline, 1)
  assert.equal(b.model?.name, null)
  assert.equal(b.tasks[0].title, 'ALE-Bench · ahc026')
})

check('unknown usage cost is never zero and currencies are never merged', () => {
  const raw = clone()
  delete raw.price_snapshot
  raw.runs = raw.runs.map((r, i) => ({ ...r, cost: i === 0 ? { amount: 0.02, currency: 'USD', status: 'estimated' } : { amount: null, currency: 'CNY', status: 'unknown' }, usage: { ...r.usage, cost_usd: null, cost_status: 'unknown' } }))
  raw.runs[1] = { ...raw.runs[1], cost: { amount: 0.3, currency: 'CNY', status: 'estimated' } }
  const t = costTotals(normalize(raw).runs.map((r) => r.cost))
  assert.deepEqual(t.byCurrency, { USD: 0.02, CNY: 0.3 })
  assert.equal(t.unknown, 2)
})

const routing: RawBatch = JSON.parse(readFileSync(new URL('./fixtures/routing-fixture.json', import.meta.url), 'utf8'))

check('routing study: runs group by variant, never into the feedback mode', () => {
  const b = normalize(routing)
  assert.equal(b.study, 'routing')
  assert.equal(b.fixture, true)
  assert.deepEqual(b.modes, VARIANTS)
  assert.ok(b.runs.every((r) => VARIANTS.includes(r.mode)))
  assert.ok(b.tasks.every((t) => t.modes.join() === VARIANTS.join()))
  assert.equal(fairLabel(b.fair, b.running).tone, 'warn')
})

check('routing study: final failed and not_run slots stay visible', () => {
  const b = normalize(routing)
  const ale = b.runs.find((r) => r.taskId.startsWith('ale') && r.mode === 'model_decisions')!
  assert.equal(ale.final.state, 'failed')
  const skipped = b.runs.find((r) => r.taskId.startsWith('algotune') && r.mode === 'both_decisions')!
  assert.deepEqual([skipped.state, skipped.final.state, skipped.cost.kind], ['planned', 'pending', 'not_run'])
  assert.equal(costTotals(b.runs.map((r) => r.cost)).unknown, 0)
  assert.equal(b.finished, 7)
})

check('routing study: CNY and USD stay apart; partial USD is a lower bound, not a total', () => {
  const b = normalize(routing)
  const t = costTotals(b.runs.map((r) => r.cost))
  assert.deepEqual(Object.keys(t.byCurrency).sort(), ['CNY', 'USD'])
  assert.ok(t.partial.has('USD') && !t.partial.has('CNY'))
  assert.equal(t.byCurrency.CNY.toFixed(3), (routing as unknown as { cost: { by_currency: Record<string, { known_amount: number }> } }).cost.by_currency.CNY.known_amount.toFixed(3))
  const action = b.runs.find((r) => r.mode === 'action_decisions')!
  assert.equal(action.cost.kind, 'partial')
  assert.ok(action.cost.purpose?.routing?.some((p) => p.amount == null))
})

check('routing study: small/large and routing/generation calls are read per run', () => {
  const b = normalize(routing)
  const both = b.runs.find((r) => r.taskId.startsWith('ale') && r.mode === 'both_decisions')!
  assert.deepEqual(both.calls, { small: 7, large: 3, routing: 7, generation: 10, upgrades: 1 })
  assert.deepEqual(both.routing, { action: 'decisions', model: 'decisions' })
  assert.equal(b.model?.name, 'Qwen3.8-27B → gpt-fixture-large')
})

const ale: RawBatch = JSON.parse(readFileSync(new URL('../src/samples/research-ale-formal.json', import.meta.url), 'utf8'))

check('ALE formal: scoreboards report final scores against the final-set c0', () => {
  const b = normalize(ale)
  assert.equal(b.runs.length, 15)
  assert.ok(b.runs.every((r) => r.final.state === 'passed'))
  const t026 = b.tasks.find((t) => t.id.includes('ahc026'))!
  assert.equal(t026.source, 'final')
  assert.equal(t026.finalBaseline, 131864)
  assert.deepEqual(['feedback', 'independent', 'no_feedback'].map((m) => modeSummary(t026, m).value), [132273, 133031, 132428])
  assert.deepEqual(bestOf(t026), { mode: 'independent', value: 133031 })
  const t024 = b.tasks.find((t) => t.id.includes('ahc024'))!
  assert.equal(bestOf(t024), null)
  assert.ok(t024.runs.every((r) => !resultOf(t024, r).improved))
})

check('ALE formal: an API-failed run keeps its passing final; the total is a lower bound of CNY 7.445133', () => {
  const b = normalize(ale)
  const r10 = b.runs.find((r) => r.seq === 10)!
  assert.deepEqual([r10.state, r10.final.state, r10.final.value, r10.cost.kind], ['failed', 'passed', 135088, 'partial'])
  const t = costTotals(b.runs.map((r) => r.cost))
  assert.equal(t.unknown, 0)
  assert.ok(t.partial.has('CNY'))
  assert.equal(t.byCurrency.CNY.toFixed(6), '7.445133')
})

console.log(`${n} checks passed`)
