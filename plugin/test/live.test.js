import assert from 'node:assert/strict';
import { test } from 'node:test';
import { initialState, reducePacket, foldConversation, renderLive } from '../live-state.js';
import { apply } from '../engine.js';
import { completeModel } from '../transport.js';
import { openAIMessages, tokenUsage, localStream, LOCAL_PROVIDER } from '../local-adapter.js';

test('all inputs keep the normal agent loop, with local Gemma selected', async () => {
  const hooks = {}, selections = [];
  apply({ effect() {}, on(name, handler) { hooks[name] = handler; } });
  const agent = { model: { select(value) { selections.push(value); }, current() { return selections.at(-1); } } };
  hooks['agent/created']({ agent });
  assert.deepEqual(selections[0], { provider: LOCAL_PROVIDER, model: 'gemma4u-26b' });
  for (const input of ['你好', '写一段营销文案', '解释归并排序', '帮我修改这个项目']) {
    const decision = { kind: 'enter', messages: [{ content: input }] };
    assert.equal(await hooks['agent/pre-step']({ agent, turn: 1, step: 1 }, () => decision), decision);
  }
});

test('messages retain ordinary text and actual tool call/result pairs', () => {
  const messages = openAIMessages({ messages: [
    { role: 'user', content: [{ type: 'text', text: '你好' }] },
    { role: 'assistant', content: [{ type: 'tool-call', id: 'a1', name: 'remote_llm', arguments: '{"task":"check"}' }] },
    { role: 'tool', toolCallId: 'a1', content: [{ type: 'text', text: 'expert result' }] },
  ] });
  assert.equal(messages[0].content, '你好');
  assert.equal(messages[1].tool_calls[0].function.name, 'remote_llm');
  assert.equal(messages[2].tool_call_id, 'a1');
});

test('local SSE text is yielded as text, not synthetic tool calls', async t => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  let request;
  globalThis.fetch = async (_url, options) => {
    request = JSON.parse(options.body);
    return new Response('data: {"choices":[{"delta":{"content":"你好"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":2}}\n\ndata: [DONE]\n\n');
  };
  const chunks = [];
  for await (const chunk of localStream({ model: 'gemma4u-26b', messages: [{ role: 'user', content: [{ type: 'text', text: '你好' }] }] }, { smallBaseURL: 'http://localhost:1234/v1' })) chunks.push(chunk);
  assert.equal(request.stream, true);
  assert.equal(chunks.filter(chunk => chunk.type === 'text-delta').map(chunk => chunk.text).join(''), '你好');
  assert(!chunks.some(chunk => chunk.type === 'tool-call-delta'));
  assert.equal(chunks.at(-1).reason.kind, 'stop');
});

test('normal local replies and remote calls have separate counters', () => {
  let state = { ...initialState(), enabled: true };
  state = foldConversation(state, { type: 'assistant/message', data: { message: { source: { provider: LOCAL_PROVIDER } } } });
  assert.equal(state.local, 1); assert.equal(state.remote, 0);
  state = foldConversation(state, { type: 'tool/call', data: { name: 'remote_llm', callId: 'r1', arguments: '{"reason":"复杂诊断","task":"核对边界"}' } });
  assert.equal(state.remote, 1); assert.equal(state.remote_calls[0].reason, '复杂诊断');
  state = foldConversation(state, { type: 'tool/result', data: { message: { toolCallId: 'r1' }, meta: { quotacrux_remote: { answer: '需要处理空输入', model: 'expert' } } } });
  assert.equal(state.remote_calls[0].answer, '需要处理空输入');
});

test('remote child snapshots cannot double count core work before its root result', () => {
  let state = { ...initialState(), enabled: true, local: 1 };
  state = foldConversation(state, { type: 'tool/call', data: { name: 'research_optimize', callId: 'root' } });
  state = foldConversation(state, { type: 'tool/call', data: { name: 'remote_model_call', callId: 'child', arguments: '{"reason":"需要诊断"}' } });
  const core = { ...initialState(), local: 2, remote: 1, validations: 3, reused: 1, headline: '研究结束' };
  const result = callId => ({ type: 'tool/result', data: { message: { toolCallId: callId }, meta: { quotacrux_live: core } } });
  state = foldConversation(state, result('child'));
  assert.equal(state.local, 1); assert.equal(state.validations, 0);
  state = foldConversation(state, result('root'));
  assert.equal(state.local, 3); assert.equal(state.remote, 1); assert.equal(state.validations, 3); assert.equal(state.reused, 1);
  assert.equal(foldConversation(state, result('root')), state);
});

test('remote usage preserves disjoint cached input accounting', async () => {
  assert.deepEqual(tokenUsage({ prompt_tokens: 100, completion_tokens: 20, prompt_tokens_details: { cached_tokens: 90 } }), { inputTokens: 10, outputTokens: 20, cacheReadTokens: 90 });
  const ctx = { llm: { async resolveModelInfo() { return {}; }, async *stream() {
    yield { type: 'text-delta', text: '{"action":"analyze"}' };
    yield { type: 'usage', usage: { inputTokens: 10, cacheReadTokens: 90, outputTokens: 20 } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  } } };
  const output = await completeModel(ctx, {}, { signal: new AbortController().signal, agent: { session: { id: 's' } } },
    { provider: 'usa0', model: 'large' }, { role: 'large', timeout_s: 1, system: 's', user: 'u', schema: {}, max_output_tokens: 30 });
  assert.equal(output.usage.input_tokens, 100); assert.equal(output.usage.cached_input_tokens, 90);
});

test('failed reuse attempts are never described as verified zero-model delivery', () => {
  const state = { ...initialState(), reused: 1, local: 1, status: 'failed', outcome: { best_from_reuse: false, final_correct: false, goal_met: false } };
  assert(!renderLive(state).includes('零模型调用交付'));
  const verified = { ...state, local: 0, status: 'completed', outcome: { best_from_reuse: true, final_correct: true, goal_met: true } };
  assert(renderLive(verified).includes('零模型调用交付'));
});

test('real research audit counts failed remote attempts', () => {
  let state = initialState();
  for (const [type, payload] of [['remote_requested', { reason: '本地验证失败' }], ['model_started', { call_id: 'm1', role: 'large', model: 'expert' }], ['model_finished', { call_id: 'm1', ok: false, error_kind: 'timeout', input_tokens: null, output_tokens: null }]]) {
    state = reducePacket(state, { kind: 'engine_event', event: { type, payload, run_id: 'run1' } });
  }
  assert.equal(state.remote, 1); assert.equal(state.remote_calls[0].status, 'error');
});
