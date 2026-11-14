// Archives the audited ALE formal batch (docs/research/native-formal-20261114/ale/results) for the dashboard,
// in the research-comparison-v1 shape. Real results; only bulky or machine-local fields are dropped.
//   node scripts/ale-formal-sample.mjs
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const dir = 'docs/research/native-formal-20261114/ale/results'
const src = JSON.parse(readFileSync(join(here, '..', '..', dir, 'comparison.json'), 'utf8'))
const out = join(here, '..', 'src', 'samples', 'research-ale-formal.json')

// Dropped: the frozen plan, wave/segment bookkeeping, per-run comparison configs and absolute worker paths.
const { plan: _plan, waves: _waves, execution_segments: _seg, assembly: _asm, ...batch } = src
const runs = src.runs.map(({ comparison_config: _cfg, report_path: _path, ...r }) => ({
  ...r,
  record: r.run_id ? `${dir}/${r.run_id}/report.json` : null,
}))

const sample = {
  api_contract: 'research-comparison-v1',
  study: 'feedback',
  dev_only: src.final_evaluation === false,
  ...batch,
  code_commit: src.code_sha ?? null,
  runs,
  source: { kind: 'archive', path: dir },
}
writeFileSync(out, JSON.stringify(sample) + '\n')
console.log(`wrote ${out}: ${runs.length} runs`)
