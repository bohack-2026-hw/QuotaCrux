import assert from 'node:assert/strict';
import { test } from 'node:test';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CASES, executionProject, loadCase, recall, remember, renderReplay } from '../core.js';
import { inspectModels, localBaseURL } from '../models.js';

const repository = fileURLToPath(new URL('../../', import.meta.url));
const activeSignal = () => new AbortController().signal;
const execution = (cwd, id) => ({ agent: { session: { id, header: { cwd } } }, signal: activeSignal() });

async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'quotacrux-p0-test-'));
  t.after(() => fs.rm(root, { force: true, recursive: true }));
  await fs.mkdir(path.join(root, '.git'));
  const entry = CASES.find(item => item.id === 'reuse');
  const source = path.join('docs', 'research', entry.runId, 'report.json');
  await fs.mkdir(path.dirname(path.join(root, source)), { recursive: true });
  await fs.copyFile(path.join(repository, source), path.join(root, source));
  return { root, source, project: await executionProject(root, execution(root, 'session-a')) };
}

test('real archives preserve routing evidence, original models and unmet goals', async () => {
  for (const entry of CASES) {
    const replay = await loadCase(repository, entry.id);
    assert.equal(replay.mode, 'historical_replay');
    assert.equal(replay.provenance.run_id, entry.runId);
    assert.match(replay.provenance.report_sha256, /^[a-f0-9]{64}$/);
    assert.match(renderReplay(replay), /历史回放/);
  }
  const upgrade = await loadCase(repository, 'upgrade');
  assert.equal(upgrade.iterations.small_model_requests, 2);
  assert.equal(upgrade.iterations.large_model_requests, 1);
  assert(upgrade.timeline.some(step => step.action === 'upgrade_model'));
  assert.equal((await loadCase(repository, 'reuse')).historical_usage.requests, 0);
  const small = await loadCase(repository, 'small-only');
  assert.equal(small.outcome.final_correct, true);
  assert.equal(small.outcome.goal_met, false);
  assert.match(renderReplay(small), /未达标/);
});

test('a new session recalls the first session evidence without sharing chat', async t => {
  const { root, project } = await fixture(t);
  const replay = await loadCase(root, 'reuse');
  assert.equal((await remember(project, replay, activeSignal())).created, true);
  const second = await executionProject(root, execution(root, 'session-b'));
  const result = await recall(second, activeSignal());
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].saved_by_session, 'session-a');
  assert.equal(result.entries[0].from_another_session, true);
  assert.equal(result.entries[0].kind, 'verified_report_reference');
  assert.equal('messages' in result.entries[0], false);
});

test('concurrent repeat saves are idempotent and publish no partial files', async t => {
  const { root, project } = await fixture(t);
  const replay = await loadCase(root, 'reuse');
  const results = await Promise.all(Array.from({ length: 5 }, () => remember(project, replay, activeSignal())));
  assert.equal(results.filter(item => item.created).length, 1);
  assert.equal((await recall(project, activeSignal())).entries.length, 1);
  assert.equal((await fs.readdir(path.join(root, '.quotacrux/p0/memory'))).length, 1);
});

test('different projects stay isolated and subdirectories use the original project', async t => {
  const { root, project } = await fixture(t);
  await fs.mkdir(path.join(root, 'subdirectory'));
  assert.equal((await executionProject(root, execution(path.join(root, 'subdirectory'), 'b'))).projectId, project.projectId);
  const other = await fs.mkdtemp(path.join(os.tmpdir(), 'quotacrux-other-'));
  t.after(() => fs.rm(other, { force: true, recursive: true }));
  await fs.mkdir(path.join(other, '.git'));
  await assert.rejects(executionProject(root, execution(other, 'c')), /项目不匹配/);
  const foreignProject = await executionProject(other, execution(other, 'c'));
  assert.equal((await recall(foreignProject, activeSignal())).entries.length, 0);
});

test('edited evidence is excluded with a diagnostic rather than trusted from memory', async t => {
  const { root, source, project } = await fixture(t);
  await remember(project, await loadCase(root, 'reuse'), activeSignal());
  await fs.appendFile(path.join(root, source), '\n');
  const result = await recall(project, activeSignal());
  assert.equal(result.entries.length, 0);
  assert.match(result.diagnostics[0].error, /报告已变化/);
});

test('memory symlinks cannot cross the project boundary', async t => {
  const { root, project } = await fixture(t);
  const outside = await fs.mkdtemp(path.join(os.tmpdir(), 'quotacrux-outside-'));
  t.after(() => fs.rm(outside, { force: true, recursive: true }));
  await fs.symlink(outside, path.join(root, '.quotacrux'));
  await assert.rejects(remember(project, await loadCase(root, 'reuse'), activeSignal()), /超出|离开当前项目/);
  assert.deepEqual(await fs.readdir(outside), []);
});

test('canceled calls publish no memory', async t => {
  const { root, project } = await fixture(t);
  const signal = AbortSignal.abort();
  await assert.rejects(remember(project, await loadCase(root, 'reuse'), signal), { name: 'AbortError' });
  assert.equal((await recall(project, activeSignal())).entries.length, 0);
});

test('replay rejects scripted reports and unknown identifiers', async t => {
  const { root, source } = await fixture(t);
  const report = JSON.parse(await fs.readFile(path.join(root, source), 'utf8'));
  report.scripted_model = ['small'];
  await fs.writeFile(path.join(root, source), JSON.stringify(report));
  await assert.rejects(loadCase(root, 'reuse'), /真实已完成/);
  await assert.rejects(loadCase(root, '../other'), /未知案例/);
});

test('LM Studio configuration accepts only local HTTP endpoints', () => {
  assert.equal(localBaseURL('http://127.0.0.1:1234/v1/'), 'http://127.0.0.1:1234/v1');
  for (const value of ['https://example.com/v1', 'http://127.0.0.1.evil/v1', 'http://secret@localhost:1234/v1']) {
    assert.throws(() => localBaseURL(value), /本机 HTTP/);
  }
});

test('provider detection keeps usa0 credentials inside DSH and does not generate', async t => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ data: [{ id: 'local-qwen' }] }) });
  const llm = {
    listProviders: () => [{ id: 'usa0', name: 'USA0' }],
    listModels: async () => [{ id: 'large-model', name: 'Large model' }],
    stream() { assert.fail('Catalog checks must not generate'); },
  };
  const result = await inspectModels({ llm }, { smallBaseURL: 'http://localhost:1234/v1', smallModel: 'local-qwen', largeProvider: 'usa0' }, { signal: activeSignal() });
  assert.equal(result.small.ready, true);
  assert.equal(result.large.ready, true);
  assert.equal(result.large.provider, 'usa0');
  assert.equal(result.generation_performed, false);
  assert.equal(JSON.stringify(result).includes('apiKey'), false);
});
