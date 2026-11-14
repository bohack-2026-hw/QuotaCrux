import { defaults } from './p0.js';
import { LOCAL_PROVIDER } from './local-adapter.js';
import { executionProject } from './core.js';
import { executeResearch } from './live.js';
import { renderLive } from './live-state.js';
import { NativeResearchLog } from './native-log.js';

export const inject = ['llm', 'tools', 'systemPrompt'];

const instructions = `你是枢决，一个本地优先的通用助手，主模型是用户本机 LM Studio 中的 Gemma。
所有请求都正常处理，包括问候、问答、分析、写作、代码生成和项目工作。普通回复直接输出自然语言，不套成工具调用，不要求用户从几个演示任务中选一个。
按需使用已提供的文件和终端工具执行项目工作；没执行的操作不要说成已完成。
只有遇到你无法可靠解决的复杂推理、连续失败的诊断，或用户明确要求远程专家时，才使用 remote_llm 求助。简单问候、翻译和普通代码问题优先自己完成。远程每轮最多一次，把具体原因、独立子任务和必要上下文交给它；收到结果后继续正常回答。
research_optimize 是可选优化，不是输入白名单。它只对已具备独立正确性及性能验证的分组聚合、日志统计、区间合并基准运行实验。不适用的请求继续正常处理，不拒绝、不冒充已完成验证。
保持回复简洁。必须区分实际执行、模型建议、开发验证与独立最终验证。`;

export function apply(ctx, input = {}) {
  const config = { ...defaults, ...input };
  const turns = new WeakMap();
  const chooseLocal = agent => agent.model.select({ provider: LOCAL_PROVIDER, model: config.smallModel });
  ctx.on('agent/created', ({ agent }) => chooseLocal(agent));
  ctx.on('agent/inbox/claimed', ({ agent }) => {
    if (agent.model.current()?.provider !== LOCAL_PROVIDER) chooseLocal(agent);
  });
  ctx.on('agent/pre-step', (payload, next) => {
    if (turns.get(payload.agent)?.turn !== payload.turn) turns.set(payload.agent, { turn: payload.turn, remote: 0 });
    turns.get(payload.agent).step = payload.step;
    return next();
  });
  ctx.effect(() => ctx.systemPrompt.section({ name: 'quotacrux:local-first', order: 200, text: instructions, interpolate: false }));
  ctx.effect(() => ctx.tools.register({
    name: 'remote_llm', description: '向已配置的远程专家模型求助，处理本机模型难以可靠完成的独立子任务。每轮最多一次。',
    parameters: { type: 'object', additionalProperties: false, required: ['reason', 'task'], properties: {
      reason: { type: 'string', description: '本次为什么需要远程帮助。' },
      task: { type: 'string', description: '请远程模型完成的具体问题，包含必要上下文。' },
    } },
    output: { schema: { type: 'object' },
      render: (_args, value) => [{ type: 'text', text: `远程大模型调用\n提供方：${value.provider}\n模型：${value.model}\n触发原因：${value.reason}\n具体工作：${value.task}\n\n返回结果：\n${value.answer}\n\n耗时：${value.latency_s} 秒\n用量：${JSON.stringify(value.usage)}\n费用：未知（未配置费率）` }],
      presentationMeta: (_args, value) => ({ quotacrux_remote: value }),
    },
    async execute(args, exec) {
      const state = turns.get(exec.agent);
      if (!state) throw new Error('远程求助需要一个活动会话轮次。');
      if (state.remote >= 1) throw new Error('本轮一次远程额度已使用，请在本地继续完成任务。');
      const provider = ctx.llm.listProviders().find(item => item.id === config.largeProvider || item.name.toLowerCase() === config.largeProvider.toLowerCase());
      if (!provider) throw new Error('DSH 的 usa0 供应商未就绪。');
      const models = await ctx.llm.listModels(provider.id);
      const model = config.largeModel || models.find(item => item.id === 'deepseek-v4.1-flash')?.id || models[0]?.id;
      if (!model) throw new Error('usa0 未提供可用模型。');
      state.remote += 1;
      const started = Date.now();
      const signal = AbortSignal.any([exec.signal, AbortSignal.timeout(90000)]);
      const info = await ctx.llm.resolveModelInfo(provider.id, model, signal);
      const reasoningEffort = info.reasoning?.efforts?.[0]?.id;
      let answer = '', usage = null, finish;
      for await (const chunk of ctx.llm.stream({ provider: provider.id, model,
        system: '你是按需求助的远程专家。只完成给定子任务，给出简洁、可核验的结论；不声称执行过没有执行的工具或测试。',
        messages: [{ role: 'user', content: [{ type: 'text', text: args.task }] }],
        maxTokens: 2048, ...(reasoningEffort ? { reasoningEffort } : {}), signal, sessionId: exec.agent.session.id,
      })) {
        if (chunk.type === 'text-delta') answer += chunk.text;
        if (chunk.type === 'usage') usage = chunk.usage;
        if (chunk.type === 'finish') finish = chunk.reason;
      }
      if (!finish || ['error', 'aborted'].includes(finish.kind)) throw new Error(finish?.failure?.message || '远程请求未正常完成');
      if (!answer) throw new Error('远程模型没有返回可用内容。');
      return { provider: provider.id, model, reason: args.reason, task: args.task, answer, usage,
        latency_s: Math.round((Date.now() - started) / 10) / 100, finish: finish.kind };
    },
  }));
  ctx.effect(() => ctx.tools.register({
    name: 'research_optimize', description: '可选地运行现有 QuotaCrux 核心的真实代码性能实验。只适用于已提供独立测试的三类基准；其他任务正常处理。',
    parameters: { type: 'object', additionalProperties: false, required: ['family', 'request'], properties: {
      family: { type: 'string', enum: ['groupagg', 'logstats', 'intervals'] },
      request: { type: 'string', description: '用户的具体优化要求。' },
      expert_review: { type: 'boolean', description: '用户明确要求远程复核时才设 true。' },
    } },
    output: { schema: { type: 'object' }, render: (_args, value) => [{ type: 'text', text: renderLive(value) }],
      presentationMeta: (_args, value) => ({ quotacrux_live: value }),
    },
    async execute(args, exec) {
      const project = await executionProject(config.projectRoot, exec);
      const turn = turns.get(exec.agent);
      const remoteLimit = Math.max(0, 1 - (turn?.remote || 0));
      const log = turn ? new NativeResearchLog(exec.agent.session, turn.turn, turn.step, true) : null;
      let latest;
      const result = await executeResearch(ctx, config, exec, project,
        { family: args.family, remoteLimit, expertReview: !!args.expert_review }, args.request,
        (state, _title, packet) => {
          latest = state;
          if (packet?.kind === 'engine_event' && packet.event.type === 'model_started' && packet.event.payload.role === 'large' && turn) turn.remote += 1;
          log?.progress(state, _title, packet);
        });
      if (latest) log?.closePending(latest);
      return result;
    },
  }));
}
