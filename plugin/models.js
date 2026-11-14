export function localBaseURL(value) {
  const url = new URL(value);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) || url.username || url.password || url.search || url.hash) {
    throw new Error('LM Studio 必须使用不含凭据的本机 HTTP 地址。');
  }
  return url.href.replace(/\/$/, '');
}

export async function inspectModels(ctx, config, exec) {
  const signal = AbortSignal.any([exec.signal, AbortSignal.timeout(10000)]);
  const small = { role: 'small', transport: 'lm_studio', base_url: localBaseURL(config.smallBaseURL), model: config.smallModel, ready: false };
  try {
    const response = await fetch(`${small.base_url}/models`, { signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    small.available_models = (payload.data || []).map(model => model.id);
    small.ready = small.available_models.includes(small.model);
    if (!small.ready) small.error = '配置的小模型未在 LM Studio 模型列表中出现。';
  } catch (error) {
    if (exec.signal.aborted) throw error;
    small.error = error.message;
  }
  const providers = ctx.llm.listProviders();
  const provider = providers.find(item => item.id === config.largeProvider)
    || providers.find(item => item.name.toLowerCase() === config.largeProvider.toLowerCase());
  const large = { role: 'large', transport: 'dsh_llm', provider: provider?.id || config.largeProvider, ready: false, credential_source: 'DSH existing provider; no key copied' };
  if (provider) {
    const models = await ctx.llm.listModels(provider.id);
    large.available_models = models.map(model => ({ id: model.id, name: model.name }));
    const current = exec.agent?.model?.current();
    large.model = config.largeModel || (current?.provider === provider.id ? current.model : models[0]?.id) || null;
    large.ready = !!large.model && models.some(model => model.id === large.model);
    if (!large.ready) large.error = 'usa0 尚未公布所选模型。';
  } else {
    large.error = 'DSH 未注册指定供应商。';
    large.available_provider_ids = providers.map(item => item.id);
  }
  return { small, large, generation_performed: false, note: '模型目录检测不发起文本生成；历史回放仍显示原始运行所用模型。' };
}

export async function probeModel(ctx, config, exec, role) {
  const inspected = await inspectModels(ctx, config, exec);
  const selected = inspected[role];
  if (!selected?.ready) throw new Error(selected?.error || '模型不可用。');
  const signal = AbortSignal.any([exec.signal, AbortSignal.timeout(45000)]);
  const prompt = 'Reply with exactly P0_OK and no other text.';
  const request = { model: selected.model, messages: [{ role: 'user', content: prompt }], max_tokens: 128 };
  const started = Date.now();
  let text = '', usage = null;
  if (role === 'small') {
    const response = await fetch(`${selected.base_url}/chat/completions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...request, temperature: 0 }), signal,
    });
    if (!response.ok) throw new Error(`LM Studio HTTP ${response.status}`);
    const value = await response.json();
    text = value.choices?.[0]?.message?.content || '';
    usage = value.usage || null;
  } else {
    const info = await ctx.llm.resolveModelInfo(selected.provider, selected.model, signal);
    const reasoningEffort = info.reasoning?.efforts?.[0]?.id;
    for await (const chunk of ctx.llm.stream({
      provider: selected.provider, model: selected.model, maxTokens: 128,
      ...(reasoningEffort ? { reasoningEffort } : {}),
      messages: [{ role: 'user', content: [{ type: 'text', text: prompt }] }],
      signal, sessionId: exec.agent.session.id,
    })) {
      if (chunk.type === 'text-delta') text += chunk.text;
      if (chunk.type === 'usage') usage = chunk.usage;
    }
  }
  return {
    role, model: selected.model, provider: selected.provider || 'lm_studio',
    mode: 'connection_probe', request: { prompt, max_output_tokens: 128 },
    response: text.slice(0, 512), passed: text.trim() === 'P0_OK',
    latency_ms: Date.now() - started, usage,
    cost: 'Unknown; separate from historical research. DSH conversation calls are additional.',
  };
}
