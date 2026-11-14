export const initialState = () => ({
  version: 1, enabled: false, status: 'idle', headline: '等待研究任务',
  local: 0, remote: 0, remote_limit: 1, validations: 0, reused: 0,
  calls: [], remote_calls: [], timeline: [], project_stats: null, core_roots: [],
});

export function reducePacket(previous, packet) {
  const state = { ...previous };
  const add = (title, kind = 'program') => {
    state.headline = title;
    state.timeline = [...state.timeline, { title, kind, at: new Date().toISOString() }].slice(-40);
  };
  if (packet.kind === 'project_history') state.project_stats = packet.stats;
  if (packet.kind === 'engine_event') {
    const { type, payload: p, run_id: runId } = packet.event;
    state.run_id = runId;
    if (type === 'run_created') { state.status = 'running'; state.snapshot_read = p.snapshot_id; add('自有引擎已启动；读取本项目经验快照'); }
    if (type === 'model_routed') add('优先本机模型；远程保留为按需求助');
    if (type === 'remote_requested') { state.remote_reason = p.reason; add(`远程求助条件成立：${p.reason}`, 'remote'); }
    if (type === 'returned_to_local') add('远程工作结束，执行权交回本地');
    if (type === 'model_started') {
      const remote = p.role === 'large';
      state[remote ? 'remote' : 'local'] += 1;
      const call = { id: p.call_id, role: p.role, model: p.model, status: 'running',
        started_at: packet.event.ts, reason: remote ? state.remote_reason || '引擎按反馈求助' : '本机处理研究动作' };
      state.calls = [...state.calls, call];
      state.remote_calls = state.calls.filter(item => item.role === 'large');
      add(remote ? `正在调用远程 ${p.model}；第 ${state.remote}/${state.remote_limit} 次` : `本机 ${p.model} 正在处理`, remote ? 'remote' : 'local');
    }
    if (type === 'model_finished') {
      state.calls = state.calls.map(call => call.id === p.call_id ? { ...call, status: p.ok ? 'completed' : 'error',
        input_tokens: p.input_tokens, output_tokens: p.output_tokens, latency_s: p.latency_s,
        cost_usd: p.cost_usd, cost_status: p.cost_status, error: p.error_kind || null } : call);
      state.remote_calls = state.calls.filter(item => item.role === 'large');
    }
    if (type === 'evaluation_started') add(`程序正在验证候选 ${p.candidate_id}，不消耗远程模型请求`);
    if (type === 'evaluation_finished') { state.validations += 1; add(`候选 ${p.candidate_id}：${p.status}，开发加速比 ${p.speedup ?? '未知'}`); }
    if (type === 'candidate_created' && p.origin === 'experience') { state.reused += 1; add(`复用项目经验中的程序 ${p.candidate_id}，重新验证后再交付`); }
    if (type === 'final_eval_started') add('候选已冻结，程序执行独立最终验收');
    if (type === 'remote_limit_reached') add('远程额度已用完；继续本地处理');
  }
  if (packet.kind === 'work_recorded') {
    state.calls = state.calls.map(call => call.id === packet.call_id ? { ...call,
      action: packet.action, purpose: packet.purpose || '模型未提供有效工作说明',
      analysis: packet.analysis || packet.evidence?.analysis || null,
      candidate_id: packet.candidate_id, action_status: packet.status,
    } : call);
    state.remote_calls = state.calls.filter(item => item.role === 'large');
  }
  if (packet.kind === 'model_failure') {
    state.calls = state.calls.map(call => call.id === packet.call_id ? { ...call, error_message: packet.error } : call);
    state.remote_calls = state.calls.filter(item => item.role === 'large');
    add(`${packet.role === 'large' ? '远程' : '本机'}请求失败：${packet.error}`);
  }
  if (packet.kind === 'result') {
    const report = packet.report;
    state.status = report.status;
    state.outcome = report.outcome;
    state.report_path = packet.report_path;
    state.best_path = packet.best_path;
    state.snapshot_published = report.experience?.published_snapshot_id || null;
    state.project_stats = packet.project_stats;
    state.usage = report.usage.total;
    state.timing = report.timing;
    state.ended_at = report.ended_at;
    state.stop_reason = report.stop_reason;
    state.stop_detail = report.stop_detail;
    if (report.status === 'failed') state.error = report.stop_detail || report.outcome.final_error || '研究执行失败';
    state.calls = state.calls.map(call => {
      const candidate = report.candidates.find(item => item.candidate_id === call.candidate_id);
      return { ...call, candidate_path: candidate?.code_path || null,
        validation: candidate?.dev_evaluations?.at(-1) || null };
    });
    state.remote_calls = state.calls.filter(item => item.role === 'large');
    add(report.status === 'failed' ? `研究未完成：${state.error}` : report.outcome.summary || '研究结束');
  }
  if (packet.kind === 'fatal') { state.status = 'failed'; state.error = packet.error; add(`运行未完成：${packet.error}`); }
  return state;
}

const jsonStateSchema = {
  parse(value) {
    if (!value || value.version !== 1 || !Number.isSafeInteger(value.local) || !Number.isSafeInteger(value.remote)
        || value.local < 0 || value.remote < 0 || !Array.isArray(value.remote_calls) || !Array.isArray(value.timeline)) {
      throw new Error('Invalid QuotaCrux session projection');
    }
    return value;
  },
};

export const projectionDefinition = {
  key: 'quotacruxLive', stateVersion: 3, stateSchema: jsonStateSchema,
  init: header => ({ ...initialState(), enabled: header?.agentPreset === 'quotacrux-live' }),
  apply: foldConversation,
  wire: { viewSchema: jsonStateSchema, view: state => state, summary: false },
};

export function foldConversation(state, event) {
  if (event.type === 'agent-preset/selected' && event.data.agentPreset === 'quotacrux-live') return { ...state, enabled: true };
  if (event.type === 'assistant/message' && event.data.message?.source?.provider === 'quotacrux-local') {
    return { ...state, enabled: true, local: state.local + 1, headline: '本地 Gemma 已返回，继续正常处理请求' };
  }
  if (!state.enabled) return state;
  if (event.type === 'turn/start') return { ...initialState(), enabled: true, status: 'running', headline: '本地 Gemma 正在处理请求' };
  if (event.type === 'tool/call' && ['research_optimize', 'quotacrux_engine'].includes(event.data.name)) {
    return { ...state, core_roots: [...(state.core_roots || []), event.data.callId] };
  }
  if (event.type === 'tool/call' && ['remote_llm', 'remote_model_call'].includes(event.data.name)) {
    let args = {};
    try { args = JSON.parse(event.data.arguments); } catch {}
    const call = { id: event.data.callId, role: 'large', status: 'running', reason: args.reason || '引擎按需求助', task: args.task || null };
    return { ...state, remote: state.remote + 1, remote_calls: [...state.remote_calls, call], headline: `远程求助：${call.reason}` };
  }
  if (event.type === 'tool/result') {
    const remote = event.data.meta?.quotacrux_remote;
    if (remote) return { ...state, remote_calls: state.remote_calls.map(call => call.id === event.data.message.toolCallId
      ? { ...call, ...remote, status: 'completed' } : call), headline: '远程子任务已返回，由本地继续完成' };
    const core = event.data.meta?.quotacrux_live;
    if (core && state.core_roots?.includes(event.data.message.toolCallId) && state.last_core_call !== event.data.message.toolCallId) return { ...state,
      local: state.local + core.local, remote: Math.max(state.remote, core.remote),
      validations: state.validations + core.validations, reused: state.reused + core.reused,
      last_core_call: event.data.message.toolCallId, headline: core.headline };
  }
  if (event.type === 'turn/end') return { ...state, status: event.data.reason.kind === 'error' ? 'failed' : event.data.reason.kind === 'aborted' ? 'stopped' : 'completed',
    headline: event.data.reason.kind === 'error' ? event.data.reason.error?.message || '请求失败' : event.data.reason.kind === 'aborted' ? '已停止' : '已完成' };
  return state;
}

export const FAMILY_TITLES = { groupagg: '分组聚合', logstats: '日志统计', intervals: '区间合并' };

export function renderLive(state) {
  const total = state.local + state.remote;
  const lines = [`枢决真实研究引擎｜${state.family ? FAMILY_TITLES[state.family] : '研究入口'}`,
    state.read_saved ? '正在查看上次真实运行，没有重新启动研究。' : '执行已由 QuotaCrux 接管；DSH 外层对话模型请求为 0。',
    `本次研究：本机模型 ${state.local} 次；远程大模型 ${state.remote}/${state.remote_limit} 次；程序验证 ${state.validations} 次；复用程序 ${state.reused} 个。`,
    `远程请求占比：${total ? `${(100 * state.remote / total).toFixed(1)}%（${state.remote}/${total}）` : '未调用模型'}`, state.headline,
  ];
  for (const call of state.remote_calls) {
    lines.push(`远程调用 ${call.id}｜${call.model}\n触发：${call.reason}\n实际工作：${call.purpose || '等待返回'}\n动作：${call.action || '尚未返回'}；状态：${call.action_status || call.status}${call.candidate_id ? `；候选 ${call.candidate_id}` : ''}`);
    if (call.analysis) lines.push(`远程复核原文：${call.analysis}`);
    if (call.validation) lines.push(`程序验证：${call.validation.status}；加速比 ${call.validation.speedup ?? '未知'}`);
    lines.push(`Token：输入 ${call.input_tokens ?? '未知'}，输出 ${call.output_tokens ?? '未知'}；耗时 ${call.latency_s ?? '未知'} 秒；费用 ${call.cost_usd == null ? '未知' : `$${call.cost_usd}`}`);
  }
  if (!state.remote) lines.push(state.status === 'completed' && state.outcome?.best_from_reuse && state.outcome?.final_correct && state.outcome?.goal_met && !state.local
    ? '项目经验程序已通过独立最终验收，零模型调用交付。' : '本次没有远程调用；复用尝试不等于验证成功，以上是实际统计。');
  if (state.project_stats) lines.push(`本项目累计：本机 ${state.project_stats.local} 次、远程 ${state.project_stats.remote} 次、研究 ${state.project_stats.runs} 轮。`);
  if (state.report_path) lines.push(`真实研究报告：${state.report_path}`);
  if (state.best_path) lines.push(`最佳程序：${state.best_path}`);
  if (state.error) lines.push(`错误：${state.error}`);
  if (state.help) lines.push(...state.help);
  return lines.filter(Boolean).join('\n\n');
}
