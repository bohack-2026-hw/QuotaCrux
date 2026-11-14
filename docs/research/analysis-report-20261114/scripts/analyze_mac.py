#!/usr/bin/env python3
"""Recompute Mac exploratory metrics and timing figures from an exported archive.

This command reads local files only; it does not invoke models or benchmarks.
Use --source for an unmerged export and --source-commit for its full Git commit.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from analyze import report_font

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
DEFAULT_SOURCE = ROOT / 'docs/research/mac-exploratory-20261114'


def analyze(root: Path, commit: str) -> dict:
    sources={}
    def read(rel):
     p=root/rel;sources[rel]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
    def seconds(a,b):return (datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()
    comparison=read('openai/comparison.json');ledger=read('openai/ledger.json');manifest=read('export-manifest.json');prices=read('openai/evidence/pricing-gpt-6.1-sol.json')
    rows=[];mismatches=[];parse_failures=[]
    for r in comparison['runs']:
     rid=r['run_id'];report=read('openai/runs/'+rid+'/report.json');validations=[];calls=[]
     for step in report['steps']:
      if step['action']=='run_validation':
       v=step['result'];validations.append({'candidate_id':step['candidate_id'],'elapsed_s':seconds(report['started_at'],step['ended_at']),'correct':v.get('correct'),'status':v.get('status'),'speedup':v.get('speedup'),'candidate_median_s':v.get('candidate_median_s'),'baseline_median_s':v.get('baseline_median_s'),'best_candidate_id':v.get('best_candidate_id'),'best_replaced':v.get('best_replaced'),'failure':v.get('failure'),'timing_spread':v.get('timing_spread')})
     candidate_evidence=[]
     for c in report['candidates']:
      rel='openai/runs/'+rid+'/candidates/'+c['candidate_id']+'.py';p=root/rel;actual=hashlib.sha256(p.read_bytes()).hexdigest();sources[rel]=actual
      record={'candidate_id':c['candidate_id'],'parent':c['parent_candidate_id'],'path':rel,'recorded_sha256':c['code_sha256'],'exported_sha256':actual,'hash_matches_run':actual==c['code_sha256']}
      try:ast.parse(p.read_text());record['syntax_valid']=True
      except SyntaxError as exc:record['syntax_valid']=False;record['syntax_error']={'line':exc.lineno,'message':exc.msg};parse_failures.append(rel)
      if not record['hash_matches_run']:mismatches.append(rel)
      candidate_evidence.append(record)
     for c in ledger['tables']['model_calls']:
      if c['run_id']!=rid:continue
      calls.append({k:c[k] for k in ['call_id','status','model_requested','model_returned','latency_s','input_tokens','output_tokens','reasoning_tokens']})
     u=report['usage']['total'];estimate=(u['input_tokens']*prices['input_per_1m']+u['output_tokens']*prices['output_per_1m'])/1e6
     rows.append({'run_id':rid,'task_id':r['task_id'],'mode':r['mode'],'best_candidate':r['best_candidate_id'],'best_dev_speedup':r['best_dev']['speedup'],'timing':report['timing'],'stop_reason':report['stop_reason'],'stop_detail':report['stop_detail'],'candidate_evidence':candidate_evidence,'candidate_hypotheses':[{'candidate_id':s['candidate_id'],'hypothesis':s['hypothesis'],'purpose':s['purpose']} for s in report['steps'] if s['action']=='propose_candidate'],'validations':validations,'calls':calls,'usage':{k:u[k] for k in ['requests','input_tokens','output_tokens','reasoning_tokens']},'estimated_usd_frozen_rate':estimate})
    remote=[]
    for rel in ['remote/01-preload-proxy','remote/02-loaded-proxy','remote/03-bounded-proxy','remote/04-direct']:
     data=read(rel+'/ledger.json');calls=data['tables']['model_calls']
     remote.append({'path':rel,'runs':len(data['tables']['runs']),'model_candidates':sum(c['origin']=='model' for c in data['tables']['candidates']),'calls':[{'call_id':c['call_id'],'status':c['status'],'error_kind':c['error_kind'],'http_503':'HTTP 503' in (c['error_message'] or ''),'latency_s':c['latency_s'],'input_tokens':c['input_tokens'],'output_tokens':c['output_tokens'],'reasoning_tokens':c['reasoning_tokens']} for c in calls]})
    task_profiles={p.parent.name:read(str(p.relative_to(root))) for p in (root/'openai/tasks').glob('*/dev_profile.json')}
    checksum_count=0;checksum_bad=[]
    for line in (root/'SHA256SUMS').read_text().splitlines():
     h,rel=line.split('  ',1);checksum_count+=1
     if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=h:checksum_bad.append(rel)
    result={'schema_version':1,'source_commit':commit,'source_directory':'docs/research/mac-exploratory-20261114','execution_code_sha':manifest['execution_code_sha'],'scope':'Mac exploratory two-case dev records; final disabled; no experiments rerun','audit':{'export_checksum_count':checksum_count,'export_checksum_mismatches':checksum_bad,'candidate_count':sum(len(x['candidate_evidence']) for x in rows),'candidate_record_hash_mismatches':mismatches,'candidate_syntax_failures':parse_failures,'status':'needs_reexport' if mismatches or parse_failures or checksum_bad else 'verified_archive','root_cause':'BRACKETED_IPV6 sanitizer drops brackets from non-IP strings such as [0], [1:], [0.0]' if mismatches else None},'batch_wall_s':seconds(comparison['created_at'],comparison['ended_at']),'sum_slot_wall_s':sum(r['timing']['wall_clock_total_s'] for r in rows),'sum_model_wait_s':sum(r['timing']['model_wait_s'] for r in rows),'sum_dev_evaluation_s':sum(r['timing']['dev_evaluation_s'] for r in rows),'total_model_calls':sum(len(r['calls']) for r in rows),'model_candidate_count':sum(len(r['candidate_evidence'])-1 for r in rows),'model_candidate_dev_passed':sum(v['correct'] is True for r in rows for v in r['validations'] if v['candidate_id']!='c0'),'usage':{k:sum(r['usage'][k] for r in rows) for k in ['input_tokens','output_tokens','reasoning_tokens']},'estimated_usd_frozen_rate':round(sum(r['estimated_usd_frozen_rate'] for r in rows),6),'timing_definition':'For each repeat sum solve times across the two cases, then take median across five repeats; one warmup per case; imports, serialization and automatic cyclic GC excluded. Baseline remeasured for each candidate.','price_snapshot':prices,'runs':rows,'input_profiles':task_profiles,'remote':remote,'remote_503_calls':sum(c['http_503'] for r in remote for c in r['calls']),'manual_evaluation':read('remote/04-direct/evidence/manual-completion-evaluation.json'),'manual_metadata':read('remote/04-direct/evidence/manual-completion-metadata.json')}
    result['sources']=[{'path':'docs/research/mac-exploratory-20261114/'+p,'sha256':h} for p,h in sorted(sources.items())]

    return result


def timing_figure(data: dict) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import ScalarFormatter, NullFormatter

    plt.rcParams.update({'font.family': report_font(Path(__file__).read_text()), 'font.size': 11,
        'font.weight': 'normal', 'axes.titleweight': 'normal', 'axes.titlesize': 13,
        'axes.labelsize': 11, 'axes.edgecolor': '#CFD5DC', 'axes.labelcolor': '#233A54',
        'text.color': '#233A54', 'xtick.color': '#526478', 'ytick.color': '#526478',
        'axes.spines.top': False, 'axes.spines.right': False, 'figure.facecolor': 'white',
        'axes.facecolor': 'white', 'grid.color': '#E6EBF0', 'grid.linewidth': .7,
        'pdf.fonttype': 42, 'savefig.facecolor': 'white', 'axes.unicode_minus': False})
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.5), sharey=True)
    handles = []
    for ax, task, title in zip(axes, ['convolve_1d', 'pagerank'], ['卷积', 'PageRank']):
        for row, mode in enumerate(['feedback', 'independent']):
            run = next(r for r in data['runs'] if task in r['task_id'] and r['mode'] == mode)
            best = next(v for v in run['validations'] if v['candidate_id'] == run['best_candidate'])
            for key, label, color, dy in [('baseline', '基线', '#BD6C36', -.13),
                                          ('candidate', '最佳候选', '#087F8C', .13)]:
                median = 1000 * best[key + '_median_s']
                low, high = [1000 * x for x in best['timing_spread'][key + '_min_max_s']]
                marker = ax.errorbar(median, row + dy, xerr=[[median-low], [high-median]],
                    fmt='o', color=color, capsize=4, markersize=6, elinewidth=1.7,
                    markerfacecolor='white' if key == 'baseline' else color, markeredgewidth=1.4,
                    label=label if row == 0 and task == 'convolve_1d' else None)
                ax.annotate(f'{median:.3f}', (median, row+dy), xytext=(0, 9),
                    textcoords='offset points', ha='center', color=color, fontsize=9)
                if row == 0 and task == 'convolve_1d':
                    handles.append(marker)
        ax.set(title=title, ylim=(1.5, -.5), yticks=[0, 1],
               yticklabels=['反馈（F）', '独立（I）'], xlabel='两例总耗时（毫秒）')
        ax.grid(axis='x'); ax.set_axisbelow(True)
        if task == 'convolve_1d':
            ax.set(xlim=(.3, 1.4), xticks=[.4, .6, .8, 1.0, 1.2, 1.4])
        else:
            ax.set_xscale('log')
            ax.set(xlim=(.3, 16), xticks=[.3, 1, 3, 10], xlabel='两例总耗时（毫秒，对数轴）')
            ax.xaxis.set_major_formatter(ScalarFormatter())
            ax.xaxis.set_minor_formatter(NullFormatter())
    fig.legend(handles, ['基线', '最佳候选'], loc='upper center', ncol=2,
               frameon=False, bbox_to_anchor=(.52, 1.035))
    fig.subplots_adjust(top=.80, bottom=.20, left=.12, right=.98, wspace=.22)
    target = HERE / 'figures'
    target.mkdir(parents=True, exist_ok=True)
    fig.savefig(target / 'mac_timings.pdf', bbox_inches='tight',
        metadata={'Title': 'Mac exploratory solve timings', 'Author': 'QuotaCrux / 枢决',
                  'CreationDate': None, 'ModDate': None})
    fig.savefig(target / 'mac_timings.png', dpi=190, bbox_inches='tight')
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE,
                        help='Root directory of the locally exported Mac evidence bundle')
    parser.add_argument('--source-commit', help='Full 40-character Git commit containing the source archive')
    parser.add_argument('--plot-only', action='store_true',
                        help='Rebuild the figure from the checked-in mac-analysis.json')
    args = parser.parse_args()
    if args.plot_only:
        data = json.loads((HERE / 'generated/mac-analysis.json').read_text())
        timing_figure(data)
        print(f"Mac figure rebuilt from {data['source_commit']} ({data['audit']['status']}).")
        return
    root = args.source.resolve()
    if not root.is_dir():
        parser.error(f'Mac evidence directory is missing: {root}; provide --source. No files are downloaded.')
    commit = args.source_commit
    if commit is None:
        if root != DEFAULT_SOURCE:
            parser.error('--source-commit is required with an external --source')
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        parser.error('--source-commit must be a full 40-character lowercase Git SHA')
    data = analyze(root, commit)
    target = HERE / 'generated/mac-analysis.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    timing_figure(data)
    print(json.dumps({'source_commit': commit, 'audit_status': data['audit']['status'],
        'checksum_files': data['audit']['export_checksum_count'], 'runs': len(data['runs']),
        'model_calls': data['total_model_calls'], 'remote_503_calls': data['remote_503_calls'],
        'estimated_usd': data['estimated_usd_frozen_rate']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
