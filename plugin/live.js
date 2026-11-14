import * as fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { randomUUID } from 'node:crypto';
import { completeModel } from './transport.js';
import { inspectModels } from './models.js';
import { initialState, reducePacket } from './live-state.js';

const activeProjects = new Set();

export async function engineDirectory(project) {
  let current = project.root;
  for (const part of ['.quotacrux', 'engine']) {
    current = path.join(current, part);
    await fs.mkdir(current, { recursive: true });
    const real = await fs.realpath(current);
    const relative = path.relative(project.root, real);
    if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('引擎数据目录不能离开当前项目。');
  }
  return current;
}

export async function lastRun(project) {
  const root = await engineDirectory(project);
  try {
    const value = JSON.parse(await fs.readFile(path.join(root, 'latest.json'), 'utf8'));
    return { ...value, read_saved: true };
  } catch (error) { if (error.code === 'ENOENT') return null; throw error; }
}

export async function executeResearch(ctx, config, exec, project, intent, text, publish) {
  if (activeProjects.has(project.projectId)) throw new Error('本项目已有研究正在运行，请等待完成或停止后再启动。');
  activeProjects.add(project.projectId);
  let stopFile;
  try {
    const directory = await engineDirectory(project);
    const available = await inspectModels(ctx, config, exec);
    if (!available.small.ready) throw new Error(available.small.error || '本机模型不可用');
    if (intent.remoteLimit && !available.large.ready) throw new Error(available.large.error || 'usa0 不可用；也可以明确选择“仅本地”');
    stopFile = path.join(directory, `stop-${randomUUID()}`);
    const request = { family: intent.family, text, session_id: project.sessionId,
      remote_limit: intent.remoteLimit, expert_review: intent.expertReview,
      small_base_url: config.smallBaseURL, small_model: available.small.model,
      large_provider: available.large.provider, large_model: available.large.model || config.largeModel || 'unused', stop_file: stopFile };
    let state = { ...initialState(), enabled: true, family: intent.family, input: text,
      status: 'starting', remote_limit: intent.remoteLimit, outer_model_requests: 0,
      policy: '本地优先；反馈触发升级或明确要求专家复核时才请求远程；每轮最多一次远程。' };
    publish(state, '引擎正在准备任务与沙箱');
    const worker = spawn(path.join(project.root, 'backend/.venv/bin/python'), ['-u', path.join(project.root, 'plugin/engine_worker.py')], {
      cwd: project.root, stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, QUOTACRUX_VAR_DIR: directory, QUOTACRUX_NO_DOTENV: '1',
        PYTHONPATH: path.join(project.root, 'backend/src'), PYTHONUNBUFFERED: '1' },
    });
    const closed = new Promise((resolve, reject) => { worker.once('error', reject); worker.once('close', (code, signal) => resolve({ code, signal })); });
    let stderr = '';
    worker.stderr.on('data', data => { stderr = (stderr + data).slice(-2000); });
    const cancel = () => { void fs.writeFile(stopFile, 'stop\n').catch(() => {}); };
    exec.signal.addEventListener('abort', cancel, { once: true });
    worker.stdin.write(JSON.stringify(request) + '\n');
    const lines = createInterface({ input: worker.stdout, crlfDelay: Infinity });
    let finished = false, remoteDispatched = 0;
    try {
      for await (const line of lines) {
        if (!line.trim()) continue;
        const packet = JSON.parse(line);
        if (packet.kind === 'model_request') {
          let response;
          if (packet.role === 'large' && ++remoteDispatched > intent.remoteLimit) {
            response = { ok: false, error_kind: 'config', error_message: 'Remote quota exceeded; request was not dispatched', usage: {} };
          } else if (exec.signal.aborted) {
            response = { ok: false, canceled: true, error_kind: 'timeout', error_message: 'User stopped the research', usage: {} };
          } else {
            response = await completeModel(ctx, config, exec, packet.role === 'small' ? available.small : available.large, packet);
          }
          if (!worker.stdin.destroyed) worker.stdin.write(JSON.stringify({ ...response, call_id: packet.call_id }) + '\n');
          continue;
        }
        state = reducePacket(state, packet);
        publish(state, state.headline, packet);
        if (packet.kind === 'result') finished = true;
      }
      const exit = await closed;
      if (!finished) throw new Error(state.error || `研究进程退出 ${exit.code ?? exit.signal}：${stderr.slice(-700)}`);
    } finally {
      exec.signal.removeEventListener('abort', cancel);
      if (worker.exitCode === null && worker.signalCode === null) {
        cancel();
        worker.stdin.end();
        await closed;
      }
    }
    const temp = path.join(directory, `latest-${randomUUID()}.json`);
    await fs.writeFile(temp, JSON.stringify(state, null, 2), { mode: 0o600 });
    await fs.rename(temp, path.join(directory, 'latest.json'));
    return state;
  } finally {
    activeProjects.delete(project.projectId);
    if (stopFile) await fs.rm(stopFile, { force: true });
  }
}
