import { createHash, randomUUID } from 'node:crypto';
import { constants } from 'node:fs';
import * as fs from 'node:fs/promises';
import path from 'node:path';

export const CASES = Object.freeze([
  { id: 'new-family', title: '新任务族：直接选择大模型', runId: 'run-20261114T041659-fa51', claim: 'new_family → large' },
  { id: 'upgrade', title: '根据验证反馈：小模型升级至大模型', runId: 'run-20261113T161733-7c5a', claim: 'small → large' },
  { id: 'reuse', title: '复验历史程序：研究引擎零模型调用', runId: 'run-20261114T041926-31a6', claim: 'verified program reuse' },
  { id: 'small-only', title: '小模型独立完成：最终正确但未达标', runId: 'run-20261113T224936-2ade', claim: 'small only; goal not met' },
]);

function within(root, target) {
  const relative = path.relative(root, target);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

export async function projectRoot(directory) {
  let current = await fs.realpath(directory);
  while (true) {
    try {
      await fs.access(path.join(current, '.git'), constants.F_OK);
      return current;
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    const parent = path.dirname(current);
    if (parent === current) throw new Error('请选择 RouteEvo Git 项目中的目录作为会话工作区。');
    current = parent;
  }
}

export async function executionProject(expectedRoot, execution) {
  const cwd = execution.agent?.session?.header?.cwd;
  const sessionId = execution.agent?.session?.id;
  if (!cwd || !sessionId) throw new Error('此工具需要 DSH 会话及项目工作区，请在 RouteEvo 项目中新建会话。');
  const [expected, actual] = await Promise.all([projectRoot(expectedRoot), projectRoot(cwd)]);
  if (actual !== expected) throw new Error('项目不匹配：请在 RouteEvo 工作区新建会话，并选择 QuotaCrux · 路由演示预设。其他项目的记忆不会被读取。');
  return { root: actual, sessionId: String(sessionId), projectId: createHash('sha256').update(actual).digest('hex').slice(0, 16) };
}

export async function loadCase(root, caseId) {
  root = await fs.realpath(root);
  const entry = CASES.find(item => item.id === caseId);
  if (!entry) throw new Error(`未知案例。可用：${CASES.map(item => item.id).join(', ')}`);
  const source = `docs/research/${entry.runId}/report.json`;
  const absolute = await fs.realpath(path.join(root, source));
  if (!within(root, absolute)) throw new Error('报告路径超出项目范围。');
  const stat = await fs.stat(absolute);
  if (stat.size > 5 * 1024 * 1024) throw new Error('报告超出 P0 读取上限。');
  const bytes = await fs.readFile(absolute);
  const report = JSON.parse(bytes.toString('utf8'));
  if (report.run_id !== entry.runId || report.status !== 'completed' ||
      !Array.isArray(report.scripted_model) || report.scripted_model.length ||
      !Array.isArray(report.steps) || !report.outcome || !report.usage?.total) {
    throw new Error('报告不是可用的真实已完成研究记录。');
  }
  const iterations = report.iterations || {};
  if (caseId === 'new-family' && (report.route?.reason !== 'new_family' || report.route?.route !== 'large')) throw new Error('报告缺少新任务族分流证据。');
  if (caseId === 'upgrade' && (!iterations.small_model_requests || !iterations.large_model_requests || !report.steps.some(step => step.action === 'upgrade_model'))) throw new Error('报告缺少真实升级与大小模型调用证据。');
  if (caseId === 'reuse' && (report.usage.total.requests !== 0 || !report.outcome.best_from_reuse || !report.outcome.final_correct)) throw new Error('报告不满足零模型复验交付条件。');
  if (caseId === 'small-only' && (!iterations.small_model_requests || iterations.large_model_requests || report.outcome.goal_met !== false)) throw new Error('报告不满足小模型未达标案例条件。');
  const timeline = report.steps.filter(step =>
    ['route_model', 'upgrade_model', 'reuse_candidate', 'propose_candidate', 'run_validation', 'finish'].includes(step.action),
  ).map(step => ({
    seq: step.seq, action: step.action, actor: step.actor, status: step.status,
    reason: step.purpose || null, next: step.next_decision || null,
    model_call_id: step.model_call_id || null,
    candidate_id: step.candidate_id || null,
    evidence: ['route_model', 'upgrade_model', 'reuse_candidate'].includes(step.action) ? step.result : null,
  }));
  const byModel = Object.entries(report.usage.by_model || {}).map(([model, usage]) => ({
    model, requests: usage.requests, input_tokens: usage.input_tokens, output_tokens: usage.output_tokens,
    cost_usd: usage.cost_usd, cost_status: usage.cost_status,
  }));
  return {
    case_id: entry.id, title: entry.title, mode: 'historical_replay',
    provenance: {
      run_id: entry.runId, source, source_path: absolute,
      report_sha256: createHash('sha256').update(bytes).digest('hex'),
      recorded_at: report.steps[0]?.started_at || null,
      replayed_at: new Date().toISOString(),
    },
    task: report.task, route: report.route || null, timeline,
    outcome: report.outcome, historical_usage: report.usage.total, historical_models: byModel,
    historical_timing: report.timing, iterations,
    accounting: '以上模型、费用与耗时来自原始历史研究；本次仅回放，没有重新运行实验。DSH 本轮对话调用另计。',
    memory_kind: 'verified_report_reference',
  };
}

async function memoryDirectory(project, create) {
  let directory = project.root;
  for (const segment of ['.quotacrux', 'p0', 'memory']) {
    directory = path.join(directory, segment);
    if (create) await fs.mkdir(directory, { recursive: true });
    const resolved = await fs.realpath(directory);
    if (!within(project.root, resolved)) throw new Error('共享记忆目录不能通过符号链接离开当前项目。');
  }
  return directory;
}

export async function remember(project, replay, signal) {
  signal?.throwIfAborted();
  // Re-read the trusted source rather than accepting caller-supplied conclusions.
  const verified = await loadCase(project.root, replay.case_id);
  if (verified.provenance.report_sha256 !== replay.provenance.report_sha256) throw new Error('报告在回放期间发生变化，请重新读取。');
  const directory = await memoryDirectory(project, true);
  const filename = `${verified.provenance.run_id}-${verified.provenance.report_sha256}.json`;
  const destination = path.join(directory, filename);
  const temporary = path.join(directory, `.pending-${randomUUID()}`);
  const entry = {
    version: 1, project_id: project.projectId, case_id: verified.case_id,
    run_id: verified.provenance.run_id, report_sha256: verified.provenance.report_sha256,
    saved_by_session: project.sessionId, saved_at: new Date().toISOString(),
    kind: 'verified_report_reference',
  };
  let created = false;
  try {
    await fs.writeFile(temporary, `${JSON.stringify(entry, null, 2)}\n`, { flag: 'wx', mode: 0o600, signal });
    signal?.throwIfAborted();
    try { await fs.link(temporary, destination); created = true; }
    catch (error) { if (error.code !== 'EEXIST') throw error; }
  } finally { await fs.rm(temporary, { force: true }); }
  return { saved: true, created, scope: 'project', project_id: project.projectId, memory_id: filename, kind: entry.kind };
}

export async function recall(project, signal) {
  signal?.throwIfAborted();
  let directory;
  try { directory = await memoryDirectory(project, false); }
  catch (error) { if (error.code === 'ENOENT') return { scope: 'project', project_id: project.projectId, entries: [], diagnostics: [], note: '此项目尚未保存研究证据，可以先查看案例，再回放并保存一份报告引用。' }; throw error; }
  const files = (await fs.readdir(directory)).filter(name => /^run-[\w-]+-[a-f0-9]{64}\.json$/.test(name)).sort();
  if (files.length > 100) throw new Error('P0 共享记忆超过 100 条，请检查目录。');
  const entries = [], diagnostics = [];
  for (const filename of files) {
    signal?.throwIfAborted();
    try {
      const full = path.join(directory, filename);
      const real = await fs.realpath(full);
      if (!within(directory, real)) throw new Error('记忆文件超出目录。');
      if ((await fs.stat(real)).size > 16 * 1024) throw new Error('记忆文件过大。');
      const saved = JSON.parse(await fs.readFile(real, { encoding: 'utf8', signal }));
      if (saved.version !== 1 || saved.project_id !== project.projectId || saved.kind !== 'verified_report_reference') throw new Error('记忆来源或版本不匹配。');
      const replay = await loadCase(project.root, saved.case_id);
      if (saved.report_sha256 !== replay.provenance.report_sha256 || saved.run_id !== replay.provenance.run_id || filename !== `${saved.run_id}-${saved.report_sha256}.json`) throw new Error('原始报告已变化或记忆索引不匹配。');
      entries.push({ case_id: replay.case_id, title: replay.title, run_id: saved.run_id,
        saved_by_session: saved.saved_by_session, saved_at: saved.saved_at,
        from_another_session: saved.saved_by_session !== project.sessionId,
        source: replay.provenance.source, report_sha256: saved.report_sha256,
        outcome: replay.outcome, kind: saved.kind,
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      diagnostics.push({ file: filename, error: error.message });
    }
  }
  return { scope: 'project', project_id: project.projectId, entries, diagnostics,
    note: '共享的是带哈希校验的历史研究报告引用；P0 尚未将新研究结果写入引擎经验快照。' };
}

export function renderReplay(replay) {
  const usage = replay.historical_usage;
  const decisions = replay.timeline.filter(step => ['route_model', 'upgrade_model', 'reuse_candidate'].includes(step.action));
  const lines = [
    `历史回放｜${replay.title}`,
    `原始运行：${replay.provenance.run_id}；时间：${replay.provenance.recorded_at}`,
    ...decisions.map(step => `决策 ${step.seq}：${step.reason}`),
    `结果：${replay.outcome.summary}`,
    `研究引擎模型请求：${usage.requests}（小模型 ${replay.iterations.small_model_requests || 0}，大模型 ${replay.iterations.large_model_requests || 0}）`,
    ...replay.historical_models.map(model => `历史模型：${model.model}；${model.requests} 次请求`),
    `历史 Token：输入 ${usage.input_tokens ?? '未知'}，输出 ${usage.output_tokens ?? '未知'}`,
    `历史费用：${usage.cost_usd == null ? '未知' : `$${usage.cost_usd}`}（${usage.cost_status}）；总耗时 ${replay.historical_timing?.wall_clock_total_s ?? '未知'} 秒`,
    `来源：${replay.provenance.source_path}`,
    `SHA-256：${replay.provenance.report_sha256}`,
    replay.accounting,
  ];
  if (replay.memory) lines.push(`已保存到当前项目共享记忆（${replay.memory.created ? '新增' : '已有'}报告引用），其他会话可检索。`);
  return lines.join('\n');
}

export function renderMemory(memory) {
  const lines = [`项目共享研究证据｜${memory.entries.length} 条`, `项目：${memory.project_id}`];
  for (const entry of memory.entries) {
    lines.push(`${entry.title}\n原始运行：${entry.run_id}\n${entry.outcome.summary}\n保存于 ${entry.saved_at}；${entry.from_another_session ? '来自同项目的另一个会话' : '由本会话保存'}\n报告：${entry.source}`);
  }
  for (const diagnostic of memory.diagnostics) lines.push(`已排除无效证据：${diagnostic.file}；${diagnostic.error}`);
  if (memory.note) lines.push(memory.note);
  return lines.join('\n\n');
}
