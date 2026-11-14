import { randomUUID } from 'node:crypto';

export function programReply(session, turn, step, text) {
  session.append('assistant/message', { turn, step, stream: [],
    message: { id: randomUUID(), role: 'assistant',
      source: { kind: 'model', provider: 'quotacrux-program', model: 'controller-no-llm' },
      content: [{ type: 'text', text }] },
  }, { surfaceOp: 'append' });
}

export function startTool(session, turn, step, name, args, callId = randomUUID()) {
  const argumentsText = JSON.stringify(args);
  // DSH's durable format requires an advertised lifecycle before tool/call.
  // This is a program controller record, with no model request or token stream.
  session.append('assistant/message', { turn, step, stream: [],
    message: { id: randomUUID(), role: 'assistant',
      source: { kind: 'model', provider: 'quotacrux-program', model: 'controller-no-llm' },
      content: [{ type: 'tool-call', id: callId, name, arguments: argumentsText }] },
  }, { surfaceOp: 'append' });
  session.append('tool/call', { turn, step, callId, name, arguments: argumentsText });
  return callId;
}

export function recordTool(session, turn, step, name, args, state, text, { callId = randomUUID(), start = true, failed = false } = {}) {
  if (start) startTool(session, turn, step, name, args, callId);
  session.append('tool/result', { turn, step,
    message: { id: randomUUID(), role: 'tool', toolCallId: callId, content: [{ type: 'text', text }],
      isError: failed, source: { kind: 'tool', callId } },
    meta: { quotacrux_live: state },
  }, { surfaceOp: 'append' });
  return callId;
}

export function describeModelCall(call) {
  const lines = [call.role === 'large' ? '远程大模型调用' : '本地模型调用',
    `调用编号：${call.id}；模型：${call.model}`, `开始时间：${call.started_at}`,
    `触发原因：${call.reason}`, `具体工作：${call.purpose || '未取得有效研究动作'}`,
    `动作：${call.action || '未返回'}；执行状态：${call.action_status || call.status}`];
  if (call.candidate_id) lines.push(`生成／处理的候选：${call.candidate_id}；候选正确性与性能由程序独立验证。`);
  if (call.analysis) lines.push(`返回的分析／复核意见：\n${call.analysis}`);
  if (call.error_message) lines.push(`错误：${call.error_message}`);
  if (call.validation) lines.push(`程序验证：${call.validation.status}；加速比 ${call.validation.speedup ?? '未知'}`);
  lines.push(`输入 Token：${call.input_tokens ?? '未知'}；输出 Token：${call.output_tokens ?? '未知'}；模型耗时：${call.latency_s ?? '未知'} 秒`,
    `费用：${call.cost_usd == null ? '未知' : `$${call.cost_usd}`}（${call.cost_status || 'unknown'}）；验证耗时另计。`);
  return lines.join('\n');
}

export class NativeResearchLog {
  constructor(session, turn, step, remoteOnly = false) {
    Object.assign(this, { session, turn, step });
    this.remoteOnly = remoteOnly;
    this.models = new Map();
  }

  progress(state, title, packet) {
    if (this.remoteOnly && !((packet?.kind === 'engine_event' && packet.event.type === 'model_started' && packet.event.payload.role === 'large')
        || (['work_recorded', 'model_failure'].includes(packet?.kind) && packet.role === 'large'))) return;
    if (packet?.kind === 'engine_event' && packet.event.type === 'model_started') {
      const call = state.calls.find(item => item.id === packet.event.payload.call_id);
      const callId = randomUUID();
      this.models.set(call.id, callId);
      startTool(this.session, this.turn, this.step, call.role === 'large' ? 'remote_model_call' : 'local_model_call',
        { model: call.model, reason: call.reason, request: call.id }, callId);
      if (this.remoteOnly) return;
    }
    if (packet?.kind === 'work_recorded' || packet?.kind === 'model_failure') {
      const call = state.calls.find(item => item.id === packet.call_id);
      const callId = this.models.get(packet.call_id);
      if (call && callId) {
        recordTool(this.session, this.turn, this.step, call.role === 'large' ? 'remote_model_call' : 'local_model_call', {},
          state, describeModelCall(call), { callId, start: false, failed: call.status === 'error' || ['invalid_action', 'error'].includes(call.action_status) });
        this.models.delete(packet.call_id);
        return;
      }
    }
    recordTool(this.session, this.turn, this.step, 'engine_progress', { stage: title }, state, title);
  }

  closePending(state) {
    for (const [id, callId] of this.models) {
      const call = state.calls.find(item => item.id === id);
      if (call) recordTool(this.session, this.turn, this.step, call.role === 'large' ? 'remote_model_call' : 'local_model_call', {}, state,
        describeModelCall(call), { callId, start: false, failed: call.status !== 'completed' });
    }
    this.models.clear();
  }
}
