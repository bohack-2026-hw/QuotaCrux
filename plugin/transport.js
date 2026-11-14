import { localBaseURL } from './models.js';

export async function completeModel(ctx, config, exec, selected, request) {
  const signal = AbortSignal.any([exec.signal, AbortSignal.timeout(Math.ceil(request.timeout_s * 1000))]);
  try {
    let text = '', usage = null, modelReturned = selected.model;
    let transportRequest;
    if (request.role === 'small') {
      const qwen = /qwen/i.test(selected.model);
      transportRequest = { model: selected.model,
        messages: [{ role: 'system', content: request.system + (qwen ? '\n/no_think' : '') }, { role: 'user', content: request.user }],
        max_tokens: request.max_output_tokens, temperature: 0.15,
        reasoning_effort: 'none', chat_template_kwargs: { enable_thinking: false },
        response_format: { type: 'json_schema', json_schema: { name: 'quotacrux_action', strict: true, schema: request.schema } } };
      const response = await fetch(`${localBaseURL(config.smallBaseURL)}/chat/completions`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
        body: JSON.stringify(transportRequest),
      });
      if (!response.ok) throw new Error(`LM Studio HTTP ${response.status}`);
      const data = await response.json();
      text = (data.choices?.[0]?.message?.content || '').replace(/<think>[\s\S]*?<\/think>/g, '').trim();
      const u = data.usage;
      usage = u ? { input_tokens: u.prompt_tokens ?? null, output_tokens: u.completion_tokens ?? null,
        cached_input_tokens: u.prompt_tokens_details?.cached_tokens ?? null, reasoning_tokens: u.completion_tokens_details?.reasoning_tokens ?? null } : {};
      modelReturned = data.model || selected.model;
      if (data.choices?.[0]?.finish_reason === 'length') return { ok: false, error_kind: 'incomplete', error_message: 'Local output hit its token limit', usage };
    } else {
      const info = await ctx.llm.resolveModelInfo(selected.provider, selected.model, signal);
      const reasoningEffort = info.reasoning?.efforts?.[0]?.id;
      let finish;
      transportRequest = {
        provider: selected.provider, model: selected.model,
        system: request.system + '\nReturn one JSON action matching this schema:\n' + JSON.stringify(request.schema),
        messages: [{ role: 'user', content: [{ type: 'text', text: request.user }] }],
        maxTokens: request.max_output_tokens, ...(reasoningEffort ? { reasoningEffort } : {}),
        sessionId: exec.agent.session.id,
      };
      for await (const chunk of ctx.llm.stream({ ...transportRequest, signal })) {
        if (chunk.type === 'text-delta') text += chunk.text;
        if (chunk.type === 'usage') {
          const u = chunk.usage;
          usage = { input_tokens: u.inputTokens == null ? null : u.inputTokens + (u.cacheReadTokens || 0) + (u.cacheWriteTokens || 0),
            output_tokens: u.outputTokens ?? null, cached_input_tokens: u.cacheReadTokens ?? null, reasoning_tokens: u.reasoningTokens ?? null };
        }
        if (chunk.type === 'finish') finish = chunk.reason;
        if (text.length > 1024 * 1024) throw new Error('Model response exceeds the bridge limit');
      }
      if (!finish || ['error', 'aborted', 'max-tokens'].includes(finish.kind)) {
        return { ok: false, error_kind: finish?.kind === 'max-tokens' ? 'incomplete' : 'network',
          error_message: finish?.failure?.message || `Remote stream ended: ${finish?.kind || 'missing finish'}`, usage: usage || {} };
      }
    }
    return { ok: !!text, text: text || null, usage: usage || {}, model_returned: modelReturned, request_body: transportRequest,
      ...(!text ? { error_kind: 'bad_response', error_message: 'Empty model response' } : {}) };
  } catch (error) {
    return { ok: false, text: null, canceled: exec.signal.aborted, usage: {},
      error_kind: signal.aborted ? 'timeout' : 'network', error_message: error.message.slice(0, 500) };
  }
}
