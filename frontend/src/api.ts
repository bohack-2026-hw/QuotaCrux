// Thin typed client for the FastAPI backend. Reports are large nested objects; only fields the UI reads are typed.

export type Json = Record<string, unknown>

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
  notes: string
  target: { min_speedup: number }
  dev_params: { rows: number; keys: number; order: string; skew: number }
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
  dev_evaluations: { status: string; speedup: number | null; improved: number | null; goal_met: number | null }[]
}

export interface Experiment {
  candidate_id: string
  step: number
  hypothesis: string | null
  purpose: string | null
  expected: string | null
  verification: string | null
  result: { status: string | null; speedup: number | null; improved: number | boolean | null; failure: string | null; contract_case: string | null }
  verdict: 'supported' | 'partial' | 'refuted' | 'untestable' | 'untested'
  then: string | null
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
  task: { task_id: string; split: string; target_min_speedup: number; dev_params: Json }
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
    final_evaluated: boolean
    final_correct: boolean | null
    final_speedup: number | null
    goal_met: boolean
    summary: string
  }
  experience: {
    snapshot_read: string
    retrieval: { matched_by_outcome: Record<string, number>; current_buckets: Record<string, string>; snapshot_size: number } | null
    read: { experience_id: string; rank: number; matching_features: number; outcome: string; task_id: string; source_run_id: string }[]
    published_snapshot_id: string | null
    published_experiences: string[]
  }
  best_candidate: Candidate | null
  final_evaluation: { status: string; correct: boolean | null; speedup: number | null; candidate_median_s: number | null; baseline_median_s: number | null } | null
  candidates: Candidate[]
  iterations: Record<string, number | null>
  usage: { total: Ledger; by_model: Record<string, Ledger> }
  timing: Record<string, number | null>
  steps: Step[]
  config: { limits: { max_model_requests: number; max_candidates: number; wall_clock_s: number }; models: Record<string, { model: string; reasoning_effort: string | null }> }
  reproduce: Record<string, string | null>
}

export interface Experience {
  experience_id: string
  outcome: 'success' | 'no_gain' | 'failure'
  conditions: { task_id: string; split: string; buckets: Record<string, string>; profile: Record<string, number> }
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
}

export interface TaskRun { run_id: string; goal_met: boolean; final_speedup: number | null; stop_reason: string; model_requests: number; output_tokens: number | null; cost_usd: number | null; wall_clock_s: number | null; experiences_read: number }

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
  tasks: () => call<TaskSummary[]>('/tasks'),
  runs: (taskId?: string) => call<RunRow[]>(`/runs?limit=300${taskId ? `&task_id=${taskId}` : ''}`),
  startRun: (body: { task_id: string; mode: string; snapshot_id?: string; label?: string }) => post<{ run_id: string }>('/runs', body),
  stopRun: (id: string) => post(`/runs/${id}/stop`),
  run: (id: string) => call<Report>(`/runs/${id}`),
  candidate: (runId: string, cid: string) => call<{ code: string }>(`/runs/${runId}/candidates/${cid}`),
  snapshots: () => call<{ active_snapshot_id: string; snapshots: SnapshotRow[]; pointer_history: { id: number; ts: string; from_snapshot_id: string; to_snapshot_id: string; reason: string; actor: string }[] }>('/snapshots'),
  snapshot: (id: string) => call<Snapshot>(`/snapshots/${id}`),
  diff: (a: string, b: string) => call<{ added: string[]; removed: string[]; common: number }>(`/snapshots/${a}/diff/${b}`),
  activate: (snapshot_id: string, reason: string) => put<{ from: string; to: string }>('/snapshots/active', { snapshot_id, reason }),
  experience: (id: string) => call<Experience>(`/experiences/${id}`),
  comparisons: () => call<{ comparison_id: string; status: string; label: string | null; tasks: string[]; snapshot_a: string; snapshot_b: string; repeats: number; created_at: string }[]>('/comparisons'),
  comparison: (id: string) => call<Comparison>(`/comparisons/${id}`),
  startComparison: (body: { task_ids: string[]; snapshot_a: string; snapshot_b: string; repeats: number; label?: string }) => post<{ comparison_id: string }>('/comparisons', body),
  stopComparison: (id: string) => post(`/comparisons/${id}/stop`),
  note: (id: string) => call<{ lines: string[]; fair: boolean; scripted_model: boolean }>(`/comparisons/${id}/note`),
  markdownUrl: (runId: string) => `/api/runs/${runId}/markdown`,
  sessions: () => call<Session[]>('/sessions'),
  startSession: (body: { learn_task: string; eval_task: string; base_snapshot_id: string }) => post<{ session_id: string }>('/sessions', body),
}
