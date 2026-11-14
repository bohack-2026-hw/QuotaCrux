// State checks for src/research.ts against the archived real batch and the states it must also handle.
//   node --experimental-strip-types scripts/check-research.ts
import { readFileSync } from 'node:fs'
import { strict as assert } from 'node:assert'
import { costTotals, fairLabel, finalState, normalize, runState } from '../src/research.ts'
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
})

check('running batch: fair null is "pending", planned and running runs have no final verdict', () => {
  const raw = clone()
  raw.status = 'running'
  raw.fair = null
  raw.final_evaluation = true
  const running: RawRun = { ...raw.runs[1], status: 'running', outcome: null, final: null, best_dev: null, progress: [], usage: null, estimated_cost: null, timing: null }
  const planned: RawRun = { seq: 5, task_id: raw.runs[0].task_id, repeat: 2, mode: 'no_feedback' }
  raw.runs = [raw.runs[0], running, planned].map((r, i) => (i === 0 ? { ...r, final: null } : r))
  const b = normalize(raw)
  assert.deepEqual(b.runs.map((r) => r.state), ['completed', 'running', 'planned'])
  assert.deepEqual(b.runs.map((r) => r.final.state), ['missing', 'pending', 'pending'])
  assert.equal(b.runs[2].cost.kind, 'unknown')
  assert.equal(b.runs[2].cost.amount, null)
  assert.equal(fairLabel(b.fair, b.running).tone, 'warn')
  assert.equal(fairLabel(false, false).tone, 'bad')
  assert.equal(b.finished, 1)
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
  delete raw.tasks; delete raw.pricing; delete raw.model
  raw.runs = raw.runs.map((r) => ({ ...r, final: undefined, estimated_cost: undefined, estimated_cny: r.estimated_cost?.amount ?? null }))
  const b = normalize(raw)
  assert.ok(b.runs.every((r) => r.final.state === 'disabled'))
  assert.ok(b.runs.every((r) => r.cost.kind === 'estimate' && r.cost.currency === 'CNY'))
  assert.ok(b.runs.every((r) => r.progress.every((p) => p.cost == null)))
  assert.equal(b.tasks.find((t) => t.metric === 'score')!.baseline, 17753)
  assert.equal(b.tasks.find((t) => t.metric === 'speedup')!.baseline, 1)
  assert.equal(b.model?.name, null)
})

check('unknown usage cost is never zero and currencies are never merged', () => {
  const raw = clone()
  delete raw.pricing
  raw.runs = raw.runs.map((r, i) => ({ ...r, estimated_cost: i === 0 ? { amount: 0.02, currency: 'USD' } : null, usage: { ...r.usage, cost_usd: null, cost_status: 'unknown' } }))
  raw.runs[1] = { ...raw.runs[1], estimated_cost: { amount: 0.3, currency: 'CNY' } }
  const t = costTotals(normalize(raw).runs.map((r) => r.cost))
  assert.deepEqual(t.byCurrency, { USD: 0.02, CNY: 0.3 })
  assert.equal(t.unknown, 2)
})

console.log(`${n} checks passed`)
