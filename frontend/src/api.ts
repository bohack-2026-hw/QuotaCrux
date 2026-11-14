// Thin typed client for the FastAPI backend. Reports are large nested objects; only fields the UI reads are typed.

import type { RawBatch, RawBatchRow } from './research'

export type Json = Record<string, unknown>
export interface Objective { metric: string; direction: string; value?: number; baseline?: number | null }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { 'content-type': 'application/json' }, ...init })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* keep status text */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body?: unknown) => call<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
const put = <T>(path: string, body: unknown) => call<T>(path, { method: 'PUT', body: JSON.stringify(body) })

export interface TaskSummary {
  task_id: string
  split: string
  family: string
  family_title: string
  workload: string
  notes: string
  target: { min_speedup: number | null; metric?: string }
  presentation?: { title: string; workload: string }
  dev_params: Json
}

export interface Route {
  route: 'small' | 'large'
  reason: 'familiar' | 'new_family' | 'new_conditions' | 'router_off'
  family: string
  family_records: number
  similar_successes: number
  min_matches: number
  model: string
}

export interface RunRow {
  run_id: string
  task_id: string
  mode: string
  snapshot_id: string
  status: string
  stop_reason: string | null
  best_candidate_id: string | null
  started_at: string
  final_goal_met: number | null
  final_speedup: number | null
  final_score: number | null
  // From #2 (research-comparison-v1 run list); absent on older APIs, where a missing final row means "final not run".
  research_mode?: string | null
  dev_only?: boolean | null
}

export interface Step {
  seq: number
  actor: string
  action: string
  status: string
  purpose: string | null
  expected_result: string | null
  verification: string | null
  hypothesis: string | null
  params: Json
  result: Json
  next_decision: string | null
  candidate_id: string | null
  model_call_id: string | null
  model_role: string | null
  started_at: string
}

export interface Ledger {
  requests: number
  input_tokens: number | null
  output_tokens: number | null
  reasoning_tokens: number | null
  input_tokens_unknown_calls: number
  cost_usd: number | null
  cost_status: string
  latency_s: number
}

export interface Candidate {
  candidate_id: string
  origin: string
  parent_candidate_id: string | null
  code_path: string
  dev_evaluations: { status: string; speedup: number | null; improved: number | null; goal_met: number | null; objective?: Objective | null }[]
}

export interface Experiment {
  candidate_id: string
  step: number
  hypothesis: string | null
  purpose: string | null
  expected: string | null
  verification: string | null
  result: { status: string | null; speedup: number | null; improved: number | boolean | null; failure: string | null; contract_case: string | null; objective?: Objective | null }
  verdict: 'supported' | 'partial' | 'refuted' | 'untestable' | 'untested'
  then: string | null
  kind?: 'reuse' | 'model'
  target?: number
}

export interface Research {
  definition: {
    question: string; goal: string; workload: string; scope: string; verification: string; final_test: string
    baseline: { program: string; dev_median_s: number | null; final_median_s: number | null }
    tools: { action: string; label: string }[]
    budget: { model_requests: number; candidates: number; loop_s: number; request_timeout_s: number; measurement_timeout_s: number }
  }
  experiments: Experiment[]
  verdicts: Record<string, number>
  verdict_labels: Record<string, string>
}

export interface Report {
  run_id: string
  research: Research
  task: { task_id: string; split: string; family?: string; workload?: string; target_min_speedup: number | null; dev_params: Json; objective: Objective }
  route?: Route | null
  mode: string
  snapshot_id: string
  label: string | null
  scripted_model: string[]
  status: string
  stop_reason: string | null
  stop_detail: string | null
  config_fingerprint: string
  outcome: {
    run_completed: boolean
    candidate_ran: boolean
    dev_validation_passed: boolean
    dev_improved: boolean
    best_is_initial: boolean
    best_from_reuse?: boolean
    final_evaluated: boolean
    final_correct: boolean | null
    final_speedup: number | null
    final_objective?: Objective | null
    goal_met: boolean
    summary: string
  }
  experience: {
    snapshot_read: string
    retrieval: { feature_count?: number; matched_by_outcome: Record<string, number>; current_buckets: Record<string, string>; snapshot_size: number } | null
    read: { experience_id: string; rank: number; matching_features: number; outcome: string; task_id: string; source_run_id: string }[]
    published_snapshot_id: string | null
    published_experiences: string[]
  }
  best_candidate: Candidate | null
  final_evaluation: { status: string; correct: boolean | null; speedup: number | null; candidate_median_s: number | null; baseline_median_s: number | null } | null
  candidates: Candidate[]
  iterations: Record<string, number | null>
  usage: { total: Ledger; by_model: Record<string, Ledger>; by_purpose?: { routing: Ledger; generation: Ledger } }
  timing: Record<string, number | null>
  steps: Step[]
  config: {
    limits: { max_model_requests: number; max_candidates: number; wall_clock_s: number }
    models: Record<string, { model: string; reasoning_effort: string | null }>
    research_protocol?: { mode: string; fixed_model: 'small' | 'large' | null; final_evaluation: boolean }
    routing?: { action: 'llm' | 'decisions'; model: 'rule' | 'decisions' }
  }
  reproduce: Record<string, string | null>
}

export interface Experience {
  experience_id: string
  outcome: 'success' | 'no_gain' | 'failure'
  conditions: { family: string; task_id: string; split: string; workload: string; buckets: Record<string, string>; profile: Json }
  action: { parent_candidate_id: string | null; code_features: { calls?: string[]; imports?: string[] }; diff_vs_initial: string; model_stated_purpose: string | null }
  hypothesis: string | null
  result: { status: string; speedup: number | null; improved: boolean | null; failure_category: string | null; failure_kinds: string[] | null; failure_example: unknown }
  resources: { model_role: string | null; model: string | null; output_tokens: number | null; latency_s: number | null; cost_usd: number | null }
  source: { run_id: string; step_seq: number | null; candidate_id: string; evaluation_id: string }
  created_at: string
}

export interface SnapshotRow {
  snapshot_id: string
  version: number
  parent_snapshot_id: string | null
  source_run_id: string | null
  created_at: string
  experience_count: number
  diff: { added?: { experience_id: string; outcome: string; task_id: string; speedup: number | null; status: string }[] }
}

export interface Snapshot extends Omit<SnapshotRow, 'experience_count'> {
  counts: Record<string, number>
  experiences: Experience[]
  active: boolean
}

export interface SideSummary {
  runs: number
  goal_met: number
  success_rate: number | null
  final_speedups: number[]
  final_speedup_median: number | null
  no_improvement_runs: number
  output_tokens: { total: number | null }
  input_tokens: { total: number | null }
  cost_usd_total: number | null
  wall_clock_s_total: number
  agent_loop_s_median: number | null
  model_requests_median: number | null
  candidates_failed_total: number
  upgrades_total: number
  stop_reasons: Record<string, number>
  runs_without_model_request?: number
  goal_met_from_reuse?: number
  model_requests_total?: number
  large_model_requests_total?: number
  runs_using_large_model?: number
  routes?: Record<string, number>
}

export interface TaskRun { run_id: string; goal_met: boolean; final_speedup: number | null; stop_reason: string; model_requests: number; output_tokens: number | null; cost_usd: number | null; wall_clock_s: number | null; experiences_read: number; best_from_reuse?: boolean; programs_reused?: number; agent_loop_s?: number | null }

export interface Comparison {
  comparison_id: string
  status: string
  label: string | null
  tasks: string[]
  snapshot_a: string
  snapshot_b: string
  repeats: number
  scripted_model: boolean
  planned_runs: number
  finished_runs: number
  errors: { seq: number; task_id: string; snapshot_id: string; error: string }[]
  fair: boolean
  config_fingerprints: string[]
  sides: Record<string, SideSummary>
  per_task: Record<string, Record<string, { runs: TaskRun[]; goal_met: number; final_speedup_median: number | null }>>
  learning_cost: { in_lineage: boolean; cost_usd?: number | null; output_tokens?: number; input_tokens?: number; wall_clock_s?: number; learn_runs?: string[]; note?: string }
  notes: string[]
}

export interface StreamRun {
  run_id: string; repeat: number; snapshot_id: string; route: string; goal_met: boolean; final_speedup: number | null
  best_from_reuse: boolean; model_requests: number; large_model_requests: number; upgrades: number; cost_usd: number | null
  output_tokens: number | null; input_tokens: number | null; agent_loop_s: number | null; wall_clock_s: number | null
  published_snapshot_id: string | null; experiences_published: number; stop_reason: string
}

export interface StreamPosition {
  position: number; task_id: string; family: string; workload: string; first_of_family: boolean; notes: string
  arms: { memory: StreamRun[]; fresh: StreamRun[] }
}

export interface Stream {
  comparison_id: string; kind: 'stream'; status: string; label: string | null; tasks: string[]; start_snapshot: string
  repeats: number; router: boolean; scripted_model: boolean; planned_runs: number; finished_runs: number
  errors: { seq: number; task_id: string; arm: string; error: string }[]
  fair: boolean; config_fingerprints: string[]
  sides: { memory: SideSummary; fresh: SideSummary }
  first_of_family: { memory: SideSummary; fresh: SideSummary }
  repeats_of_family: { memory: SideSummary; fresh: SideSummary }
  by_family: Record<string, { memory: SideSummary; fresh: SideSummary }>
  positions: StreamPosition[]
  series: Record<'memory' | 'fresh', Record<string, { cost_usd: number[]; agent_loop_s: number[]; large_model_requests: number[] }>>
  growth: { repeat: number; start: string; end: string; published_versions: number; experiences_start: number; experiences_end: number }[]
  notes: string[]
}

export interface LiveCell {
  seq: number; task_id: string; arm: string; repeat: number; position: number | null; run_id: string | null
  state: 'planned' | 'running' | 'done'; status: string | null; stop_reason: string | null; route: string | null
  requests: number; large: number; cost_usd: number | null; final_speedup: number | null; goal_met: boolean | null; error: string | null
}

export interface LiveData {
  now: string
  progress: {
    title: string | null
    steps: { id: string; title: string; status: string; note: string | null; started_at: string | null; ended_at: string | null }[]
    log: { ts: string; text: string }[]
  }
  comparison: {
    comparison_id: string; kind: string; label: string | null; status: string; tasks: string[]; repeats: number
    start_snapshot: string | null; snapshot_a: string | null; snapshot_b: string | null; planned: number; done: number
    avg_run_s: number | null; eta_s: number | null
    totals: Record<string, { runs: number; goal_met: number; large_requests: number; cost_usd: number; no_model: number; seconds: number }>
    cells: LiveCell[]
  } | null
  run: {
    run_id: string; task_id: string; mode: string; snapshot_id: string; label: string | null; started_at: string; elapsed_s: number
    route: Route | null; requests: number; cost_usd: number | null
    last_event: { type: string; ts: string; payload: Json } | null
    steps: { seq: number; actor: string; action: string; status: string; purpose: string | null; candidate_id: string | null; speedup: number | null; next_decision: string | null }[]
  } | null
  machine: { load: { ts: string; load1: number }[]; icloud_sync: string }
  active_snapshot: string
  gpt_today: { calls: number; cost_usd: number }
}

export interface Session {
  session_id: string
  learn_task: string
  eval_task: string
  base_snapshot_id: string
  phase: string
  status: string
  learn_run_id: string | null
  new_snapshot_id: string | null
  comparison_id: string | null
  detail: string | null
  created_at: string
}

export const api = {
  health: () => call<{ ok: boolean; running_run_id: string | null }>('/health'),
  live: () => call<LiveData>('/live'),
  tasks: () => call<TaskSummary[]>('/tasks'),
  runs: (taskId?: string) => call<RunRow[]>(`/runs?limit=300${taskId ? `&task_id=${taskId}` : ''}`),
  startRun: (body: { task_id: string; mode: string; snapshot_id?: string; label?: string;
    action_router?: 'llm' | 'decisions'; model_router?: 'rule' | 'decisions' }) => post<{ run_id: string }>('/runs', body),
  stopRun: (id: string) => post(`/runs/${id}/stop`),
  run: (id: string) => call<Report>(`/runs/${id}`),
  candidate: (runId: string, cid: string) => call<{ code: string }>(`/runs/${runId}/candidates/${cid}`),
  snapshots: () => call<{ active_snapshot_id: string; snapshots: SnapshotRow[]; pointer_history: { id: number; ts: string; from_snapshot_id: string; to_snapshot_id: string; reason: string; actor: string }[] }>('/snapshots'),
  snapshot: (id: string) => call<Snapshot>(`/snapshots/${id}`),
  diff: (a: string, b: string) => call<{ added: string[]; removed: string[]; common: number }>(`/snapshots/${a}/diff/${b}`),
  activate: (snapshot_id: string, reason: string) => put<{ from: string; to: string }>('/snapshots/active', { snapshot_id, reason }),
  experience: (id: string) => call<Experience>(`/experiences/${id}`),
  comparisons: () => call<{ comparison_id: string; kind: 'snapshots' | 'stream'; status: string; label: string | null; tasks: string[]; snapshot_a: string; snapshot_b: string; repeats: number; created_at: string }[]>('/comparisons'),
  comparison: (id: string) => call<Comparison>(`/comparisons/${id}`),
  stream: (id: string) => call<Stream>(`/comparisons/${id}`),
  startStream: (body: { task_ids: string[]; start_snapshot: string; repeats: number; label?: string }) => post<{ comparison_id: string }>('/streams', body),
  startComparison: (body: { task_ids: string[]; snapshot_a: string; snapshot_b: string; repeats: number; label?: string }) => post<{ comparison_id: string }>('/comparisons', body),
  stopComparison: (id: string) => post(`/comparisons/${id}/stop`),
  note: (id: string) => call<{ lines: string[]; fair: boolean; scripted_model: boolean }>(`/comparisons/${id}/note`),
  markdownUrl: (runId: string) => `/api/runs/${runId}/markdown`,
  sessions: () => call<Session[]>('/sessions'),
  // Read-only within-task research comparisons (research-comparison-v1 from #2, see src/research.ts).
  researchComparisons: () => call<RawBatchRow[]>('/research-comparisons'),
  researchComparison: (id: string) => call<RawBatch>(`/research-comparisons/${id}`),
  startSession: (body: { learn_task: string; eval_task: string; base_snapshot_id: string }) => post<{ session_id: string }>('/sessions', body),
}
