import { createRequire } from 'node:module';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { localBaseURL } from './models.js';

export const LOCAL_PROVIDER = 'quotacrux-local';

export function openAIMessages(options) {
  const messages = [];
  if (options.system) messages.push({ role: 'system', content: options.system });
  for (const message of options.messages) {
    const blocks = message.content || [];
    if (blocks.some(block => block.type === 'image')) throw new Error('当前本地适配器暂不处理图片附件，请先提供文字或使用文件工具。');
    const text = blocks.filter(block => block.type === 'text').map(block => block.text).join('\n');
    if (message.role === 'tool') {
      messages.push({ role: 'tool', tool_call_id: message.toolCallId, content: text });
    } else {
      const calls = blocks.filter(block => block.type === 'tool-call').map(block => ({
        id: block.id, type: 'function', function: { name: block.name, arguments: block.arguments },
      }));
      messages.push({ role: message.role === 'developer' ? 'user' : message.role, content: text || null,
        ...(calls.length ? { tool_calls: calls } : {}) });
    }
  }
  return messages;
}

export function tokenUsage(usage) {
  const cached = usage.prompt_tokens_details?.cached_tokens || 0;
  return { inputTokens: Math.max(0, (usage.prompt_tokens || 0) - cached), outputTokens: usage.completion_tokens || 0,
    cacheReadTokens: cached, ...(usage.total_tokens == null ? {} : { totalTokens: usage.total_tokens }),
    ...(usage.completion_tokens_details?.reasoning_tokens == null ? {} : { reasoningTokens: usage.completion_tokens_details.reasoning_tokens }) };
}

export async function* localStream(options, config, headers = {}) {
  const response = await fetch(`${localBaseURL(config.smallBaseURL)}/chat/completions`, {
    method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, signal: options.signal,
    body: JSON.stringify({ model: options.model, messages: openAIMessages(options),
      max_tokens: options.maxTokens || 2048, temperature: options.temperature ?? 0.2,
      reasoning_effort: 'none', chat_template_kwargs: { enable_thinking: false },
      stream: true, stream_options: { include_usage: true },
      ...(options.tools?.length ? { tools: options.tools.map(tool => ({ type: 'function', function: tool })), tool_choice: 'auto' } : {}),
    }),
  });
  if (!response.ok) throw new Error(`LM Studio HTTP ${response.status}: ${(await response.text()).slice(0, 700)}`);
  const decoder = new TextDecoder();
  let buffer = '', text = '', opened = false, usage = null, finish = null;
  const calls = new Map();
  for await (const bytes of response.body) {
    options.signal?.throwIfAborted();
    buffer += decoder.decode(bytes, { stream: true });
    let newline;
    while ((newline = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, newline).trim(); buffer = buffer.slice(newline + 1);
      if (!line.startsWith('data:')) continue;
      const raw = line.slice(5).trim();
      if (!raw || raw === '[DONE]') continue;
      const packet = JSON.parse(raw);
      if (packet.error) throw new Error(packet.error.message || 'LM Studio stream failed');
      if (packet.usage) usage = packet.usage;
      const choice = packet.choices?.[0];
      if (!choice) continue;
      const delta = choice.delta || {};
      if (delta.content) {
        if (!opened) { opened = true; yield { type: 'block-start', index: 0, blockType: 'text' }; }
        text += delta.content;
        yield { type: 'text-delta', index: 0, text: delta.content };
      }
      for (const item of delta.tool_calls || []) {
        const call = calls.get(item.index) || { id: '', name: '', arguments: '' };
        if (item.id) call.id += item.id;
        if (item.function?.name) call.name += item.function.name;
        if (item.function?.arguments) call.arguments += item.function.arguments;
        calls.set(item.index, call);
      }
      if (choice.finish_reason) finish = choice.finish_reason;
    }
  }
  if (opened) yield { type: 'block-end', index: 0, block: { type: 'text', text } };
  let index = opened ? 1 : 0;
  for (const call of calls.values()) {
    const id = call.id || randomUUID();
    yield { type: 'block-start', index, blockType: 'tool-call' };
    yield { type: 'tool-call-delta', index, id, name: call.name, argumentsDelta: call.arguments };
    yield { type: 'block-end', index, block: { type: 'tool-call', id, name: call.name, arguments: call.arguments } };
    index += 1;
  }
  if (usage) yield { type: 'usage', usage: tokenUsage(usage) };
  if (!finish) throw new Error('LM Studio closed the stream without a finish reason');
  yield { type: 'finish', reason: { kind: finish === 'length' ? 'max-tokens' : calls.size ? 'tool-calls' : 'stop' } };
}

export function installLocalAdapter(ctx, config) {
  const anchor = process.env.DSH_INSTALL_DIR || (process.resourcesPath && path.join(process.resourcesPath, 'app.asar/dsh'));
  if (!anchor) throw new Error('Cannot locate the running DSH installation');
  const runtime = createRequire(path.join(anchor, 'package.json'))('@deepseek-ai/dsh-llm');
  class LocalAdapter extends runtime.LlmAdapter {
    providerInfo() { return { id: LOCAL_PROVIDER, name: 'LM Studio · Gemma（本机）' }; }
    providerRetryPolicy() { return runtime.resolveRetryPolicy({ mode: 'normal', maxRetries: 0 }); }
    async listModels() { return [{ provider: LOCAL_PROVIDER, id: config.smallModel, name: 'Gemma · 本机', inputModalities: ['text'] }]; }
    async resolveModel(provider, model) {
      return { provider, id: model, name: 'Gemma · 本机', context: { contextWindow: 16384 }, defaultMaxTokens: 2048, inputModalities: ['text'] };
    }
    stream(options) { return localStream(options, config, runtime.attributionHeaders()); }
  }
  ctx.effect(() => ctx.llm.registerAdapter([LOCAL_PROVIDER], new LocalAdapter()));
}
