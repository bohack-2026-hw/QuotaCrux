// Historical P0 tools remain available in their own preset.
import { fileURLToPath } from 'node:url';
import { CASES, executionProject, loadCase, remember, recall, renderReplay, renderMemory } from './core.js';
import { inspectModels, probeModel, localBaseURL } from './models.js';

export const inject = ['tools', 'systemPrompt', 'llm'];
export const defaults = Object.freeze({
  projectRoot: fileURLToPath(new URL('../', import.meta.url)),
  smallBaseURL: 'http://127.0.0.1:1234/v1',
  smallModel: 'gemma4u-26b',
  largeProvider: 'usa0',
  largeModel: '',
});

const instructions = `你是枢决 QuotaCrux 的路由演示助手，使用简洁中文。
用户询问已有研究、模型选择或项目记忆时，先调用 quotacrux_memory 检索本项目共享研究证据，再按需调用 quotacrux_cases 或 quotacrux_replay。
必须使用工具返回的数据解释路由依据和结果。quotacrux_replay 是历史回放，必须保留历史运行编号、原始模型和时间，不得说成刚执行的新实验。
P0 只提供历史报告引用的跨会话共享，不把回放冒充新学习或写入引擎经验快照。其他会话的聊天内容不共享。不要声称正在支持任意代码研究。
区分规则分流、模型决策和程序复用；最终正确和达到优化目标是两个结果。零模型调用只指研究引擎，不包含 DSH 对话模型。
模型连接信息通过 quotacrux_models 查看。只有用户明确要求连接探测时才调用 quotacrux_probe；探测会真实生成少量文本，和历史研究费用分开。
以 tool 返回的状态为准；不要使用 shell 或其他工具绕过项目边界。`;

export function apply(ctx, input = {}) {
  for (const [key, value] of Object.entries(input)) {
    if (!(key in defaults) || typeof value !== 'string') throw new Error(`无效的 QuotaCrux 配置项：${key}`);
  }
  const config = { ...defaults, ...input };
  localBaseURL(config.smallBaseURL);
  ctx.effect(() => ctx.systemPrompt.section({ name: 'quotacrux:p0', order: 200, text: instructions, interpolate: false }));
  function register(name, description, parameters, title, execute, render = value => JSON.stringify(value, null, 2)) {
    const properties = {}, required = [];
    for (const [key, { required: mandatory, ...schema }] of Object.entries(parameters)) {
      properties[key] = schema;
      if (mandatory) required.push(key);
    }
    ctx.effect(() => ctx.tools.register({
      name, description, parameters: { type: 'object', properties, required, additionalProperties: false },
      output: { schema: { type: 'object' }, render: (_args, value) => [{ type: 'text', text: render(value) }],
        presentationMeta: (_args, value) => value },
      presentCall: args => ({ card: 'generic', title: typeof title === 'function' ? title(args) : title, kind: name === 'quotacrux_probe' ? 'execute' : 'read' }),
      presentResult: (args, result) => ({ card: 'generic', title: typeof title === 'function' ? title(args) : title, content: result.content }),
      async execute(args, exec) {
        exec.signal.throwIfAborted();
        const project = await executionProject(config.projectRoot, exec);
        return execute(args, exec, project);
      },
    }));
  }
  register('quotacrux_cases', '列出可回放的真实研究案例；不启动新实验。', {}, '查看真实路由案例',
    async () => ({ mode: 'historical_replay', cases: CASES, phase: 'P0' }),
    value => ['真实研究案例｜历史回放', ...value.cases.map(entry => `${entry.id}：${entry.title}`), '选择案例标识即可回放；回放默认保存报告引用，供同项目新会话检索。'].join('\n'));
  register('quotacrux_replay', '回放一份真实研究报告，展示路由依据、验证结果及历史资源消耗。', {
    case_id: { type: 'string', required: true, enum: CASES.map(entry => entry.id), description: '案例标识。' },
    save_to_memory: { type: 'boolean', description: '是否保存报告引用到本项目共享记忆，默认 true；不写入引擎经验快照。' },
  }, args => `历史回放 · ${CASES.find(entry => entry.id === args?.case_id)?.title || '研究案例'}`, async (args, exec, project) => {
    const replay = await loadCase(project.root, args.case_id);
    if (args.save_to_memory !== false) replay.memory = await remember(project, replay, exec.signal);
    return replay;
  }, renderReplay);
  register('quotacrux_memory', '检索当前项目已保存的研究报告引用，供不同会话共享；不读取其他会话的聊天内容。', {}, '检索本项目共享研究证据',
    async (_args, exec, project) => recall(project, exec.signal), renderMemory);
  register('quotacrux_models', '检测本机 LM Studio 模型目录和 DSH 已配置 usa0 模型；不进行文本生成。', {}, '检查 LM Studio 与 usa0 配置',
    async (_args, exec) => inspectModels(ctx, config, exec));
  register('quotacrux_probe', '向选定模型发送固定的 P0_OK 提示词进行真实连接探测；不执行研究实验。', {
    role: { type: 'string', required: true, enum: ['small', 'large'], description: 'small 使用本机 LM Studio；large 使用 DSH 已配置的 usa0。' },
  }, args => `连接探测 · ${args?.role === 'small' ? 'LM Studio 小模型' : 'DSH usa0 大模型'}`, async (args, exec) => probeModel(ctx, config, exec, args.role));
}
