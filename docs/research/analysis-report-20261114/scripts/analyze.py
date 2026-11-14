#!/usr/bin/env python3
"""Recompute report metrics and figures from archived RouteEvo run reports.

Run from any directory with Python 3.11+ and matplotlib 3.10.8:
    uv run --with matplotlib==3.10.8 python path/to/analyze.py
No model, benchmark, or network requests are made by this script.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
RESEARCH = ROOT / 'docs/research'
GENERATED = HERE / 'generated'
FIGURES = HERE / 'figures'
SOURCES: dict[str, str] = {}
VARIANTS = ['baseline', 'action_decisions', 'model_decisions', 'both_decisions']
LABELS = ['Baseline', 'Action D', 'Model D', 'Both D']
COLORS = ['#586779', '#008779', '#466BD4', '#D18527']


def source(path: Path) -> None:
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    source(path)
    return json.loads(path.read_text())


def elapsed(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def close(a: float, b: float, label: str) -> None:
    if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6):
        raise ValueError(f'{label}: {a} != {b}')


def price_report(report: dict, prices: dict) -> dict:
    """Apply the comparison's frozen prices to report usage, keeping missing usage unknown."""
    by_currency = defaultdict(lambda: {'known_amount': 0.0, 'unknown_usage_calls': 0})
    by_role = {}
    for model_key, usage in report['usage']['by_model'].items():
        role = model_key.split(':', 1)[0]
        price = prices['decisions' if role.startswith('router_') else role]
        known = ((usage['input_tokens'] or 0) * price['input_per_1m']
                 + (usage['output_tokens'] or 0) * price['output_per_1m']) / 1_000_000
        unknown = max(usage['input_tokens_unknown_calls'], usage['output_tokens_unknown_calls'])
        by_role[role] = {'currency': price['currency'], 'known_amount': round(known, 10),
                         'unknown_usage_calls': unknown, 'requests': usage['requests'],
                         'input_tokens_known': usage['input_tokens'],
                         'output_tokens_known': usage['output_tokens']}
        entry = by_currency[price['currency']]
        entry['known_amount'] += known
        entry['unknown_usage_calls'] += unknown
    for entry in by_currency.values():
        entry['known_amount'] = round(entry['known_amount'], 10)
        entry['amount'] = None if entry['unknown_usage_calls'] else entry['known_amount']
    return {'by_currency': dict(by_currency), 'by_role': by_role}


def run_metrics(base: Path, entry: dict, prices: dict) -> dict:
    report_path = base / entry['run_id'] / 'report.json'
    report = read(report_path)
    for candidate in report['candidates']:
        path = report_path.parent / 'candidates' / (candidate['candidate_id'] + '.py')
        source(path)
        if SOURCES[str(path.relative_to(ROOT))] != candidate['code_sha256']:
            raise ValueError(f'Candidate checksum mismatch: {path}')
    iterations = report['iterations']
    proposed = [c for c in report['candidates'] if c['origin'] == 'model']
    passed = sum(any(e['correct'] for e in c['dev_evaluations']) for c in proposed)
    if len(proposed) != iterations['candidates_proposed'] or passed != iterations['candidates_passed']:
        raise ValueError(f'Candidate counts disagree: {report_path}')
    # The calls include failed requests; usage counters must not silently omit them.
    call_paths = sorted((report_path.parent / 'model_calls').glob('*.json'))
    for path in call_paths:
        source(path)
    if len(call_paths) != report['usage']['total']['requests']:
        raise ValueError(f'Call artifact count disagrees: {report_path}')
    final = report.get('final_evaluation')
    objective = final['objective'] if final else None
    cost = price_report(report, prices)
    timing = dict(report['timing'])
    timing['other_recorded_s'] = round(timing['wall_clock_total_s'] - timing['model_wait_s']
        - timing['dev_evaluation_s'] - (timing['final_evaluation_s'] or 0), 6)
    if timing['other_recorded_s'] < -0.01:
        raise ValueError(f'Timing components exceed total: {report_path}')
    # container_startup_s is a nested diagnostic, never added to the wall-time stack.
    trajectory = []
    best = None
    c0 = None
    for step in report['steps']:
        if step['action'] != 'run_validation':
            continue
        result = step['result']
        objective_dev = result.get('objective')
        if not result.get('correct') or not objective_dev:
            continue
        if step['candidate_id'] == 'c0':
            c0 = objective_dev['value']
        if not result.get('eligible_for_selection', True):
            continue
        value = objective_dev['value']
        best = value if best is None else max(best, value)
        trajectory.append({'candidate_id': step['candidate_id'], 'step': step['seq'],
             'elapsed_s': elapsed(report['started_at'], step['ended_at']),
             'candidate_dev_score': value, 'best_dev_score': best})
    for point in trajectory:
        point['best_dev_gain_pct'] = 100 * (point['best_dev_score'] / c0 - 1)
    return {
        'run_id': entry['run_id'], 'seq': entry['seq'], 'task_id': entry['task_id'],
        'variant': entry.get('variant'), 'mode': entry['mode'], 'repeat': entry['repeat'],
        'status': entry['status'], 'stop_reason': report['stop_reason'],
        'source_report': str(report_path.relative_to(ROOT)),
        'final_correct': bool(final['correct']) if final else None,
        'final_cases': final['case_count'] if final else 0,
        'final_score': objective['value'] if objective else None,
        'final_c0_score': objective['baseline'] if objective else None,
        'final_gain_pct': 100 * (objective['value'] / objective['baseline'] - 1) if objective else None,
        'best_candidate_id': report['best_candidate']['candidate_id'],
        'proposed': len(proposed), 'dev_passed': passed,
        'timing': timing, 'iterations': iterations, 'cost': cost,
        'usage': report['usage']['total'], 'dev_c0_score': c0,
        'dev_trajectory': trajectory,
        'loop_end_elapsed_s': elapsed(report['started_at'], report['loop_ended_at']),
    }


def cost_totals(runs: list[dict]) -> dict:
    totals = defaultdict(lambda: {'known_amount': 0.0, 'unknown_usage_calls': 0})
    for run in runs:
        for currency, item in run['cost']['by_currency'].items():
            totals[currency]['known_amount'] += item['known_amount']
            totals[currency]['unknown_usage_calls'] += item['unknown_usage_calls']
    for item in totals.values():
        item['known_amount'] = round(item['known_amount'], 10)
        item['amount'] = None if item['unknown_usage_calls'] else item['known_amount']
    return dict(totals)


def batch(name: str, rel: str, feedback: bool = False) -> dict:
    base = RESEARCH / rel
    comparison = read(base / 'comparison.json')
    prices = {'small': comparison['price_snapshot']} if feedback else comparison['price_snapshots']
    runs = [run_metrics(base, r, prices) for r in comparison['runs'] if r.get('run_id')]
    totals = {'planned': len(comparison['plan']), 'started': len(runs),
              'statuses': dict(Counter(r['status'] for r in runs)),
              'final_correct': sum(r['final_correct'] is True for r in runs),
              'final_cases_passed': sum(r['final_cases'] for r in runs if r['final_correct']),
              'c0_deliveries': sum(r['best_candidate_id'] == 'c0' for r in runs),
              'proposed': sum(r['proposed'] for r in runs),
              'dev_passed': sum(r['dev_passed'] for r in runs),
              'requests': sum(r['usage']['requests'] for r in runs),
              'known_input_tokens': sum(r['usage']['input_tokens'] or 0 for r in runs),
              'known_output_tokens': sum(r['usage']['output_tokens'] or 0 for r in runs),
              'sum_episode_wall_s': sum(r['timing']['wall_clock_total_s'] for r in runs),
              'sum_model_wait_s': sum(r['timing']['model_wait_s'] for r in runs),
              'sum_dev_evaluation_s': sum(r['timing']['dev_evaluation_s'] for r in runs),
              'sum_final_evaluation_s': sum(r['timing']['final_evaluation_s'] or 0 for r in runs)}
    totals['dev_pass_rate_pct'] = 100 * totals['dev_passed'] / totals['proposed']
    result = {'name': name, 'comparison_source': str((base / 'comparison.json').relative_to(ROOT)),
         'protocol': comparison['protocol'], 'limits': comparison['limits'], 'price_snapshots': prices,
         'batch_wall_s': elapsed(comparison['created_at'], comparison['ended_at']),
         'runs': runs, 'totals': totals, 'cost': cost_totals(runs)}
    if feedback:
        close(result['batch_wall_s'], comparison['batch_wall_clock_s'], 'feedback batch wall')
        result['interruption_gap_s'] = comparison['interruption_gap_s']
        result['active_batch_wall_s'] = comparison['active_batch_wall_clock_s']
        groups = []
        for task, modes in [('ahc024', ['feedback', 'independent']),
                            ('ahc026', ['feedback', 'independent', 'no_feedback'])]:
            for mode in modes:
                selected = [r for r in runs if task in r['task_id'] and r['mode'] == mode]
                scores = [r['final_score'] for r in selected]
                median = statistics.median(scores)
                groups.append({'task': task, 'mode': mode, 'n': len(selected),
                    'final_scores': scores, 'median_final_score': median,
                    'median_gain_pct': 100 * (median / selected[0]['final_c0_score'] - 1),
                    'proposed': sum(r['proposed'] for r in selected),
                    'dev_passed': sum(r['dev_passed'] for r in selected),
                    'c0_deliveries': sum(r['best_candidate_id'] == 'c0' for r in selected),
                    'requests': sum(r['usage']['requests'] for r in selected)})
        result['groups'] = groups
    return result


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.titlesize': 12, 'axes.titleweight': 'bold', 'axes.labelsize': 10,
        'axes.edgecolor': '#CFD5DC', 'axes.labelcolor': '#263546', 'text.color': '#263546',
        'xtick.color': '#586779', 'ytick.color': '#586779', 'axes.spines.top': False,
        'axes.spines.right': False, 'figure.facecolor': 'white', 'axes.facecolor': 'white',
        'grid.color': '#E6EBF0', 'grid.linewidth': .7, 'pdf.fonttype': 42,
        'savefig.facecolor': 'white', 'svg.fonttype': 'none'})


def save(fig, name):
    fig.savefig(FIGURES / (name + '.pdf'), bbox_inches='tight',
        metadata={'Title': name, 'Author': 'RouteEvo', 'CreationDate': None, 'ModDate': None})
    fig.savefig(FIGURES / (name + '.png'), dpi=180, bbox_inches='tight')
    plt.close(fig)


def figures(data):
    style()
    runs = data['routing']['runs']
    fig, ax = plt.subplots(figsize=(8.7, 4.6))
    ax.set_axisbelow(True); ax.grid(axis='both')
    # Label near-coincident outcomes with leader lines to avoid implying separation.
    offsets = [(18, -24), (18, 20), (18, -65), (18, 20)]
    for run, label, color, offset in zip(runs, LABELS, COLORS, offsets):
        ax.scatter(run['timing']['wall_clock_total_s'], run['final_gain_pct'], s=95,
                   marker='s' if run['variant'] == 'baseline' else 'o', c=color, zorder=4)
        ax.annotate(f"{label}\n{run['final_score']:,}  |  +{run['final_gain_pct']:.3f}%",
            (run['timing']['wall_clock_total_s'], run['final_gain_pct']),
            xytext=offset, textcoords='offset points', fontsize=9, color=color,
            arrowprops={'arrowstyle': '-', 'color': color, 'lw': .7})
    ax.set(xlim=(70, 510), ylim=(-.3, 8.0), xlabel='Actual episode time, including final evaluation (s)',
           ylabel='Final score gain over c0 (%)', title='Final quality versus elapsed time')
    ax.axhline(0, color='#95A2AF', lw=.8, ls=':')
    fig.text(.125, .005, 'ahc026 | 15 final cases | c0 = 131,864 | one run per variant | loop limit: 360 s',
             fontsize=8.5, color='#586779')
    fig.subplots_adjust(bottom=.18, right=.97)
    save(fig, 'routing_tradeoff')

    fig, ax = plt.subplots(figsize=(8.7, 4.7))
    for run, label, color in zip(runs, LABELS, COLORS):
        points = run['dev_trajectory']
        xs = [p['elapsed_s'] for p in points] + [run['loop_end_elapsed_s']]
        ys = [p['best_dev_gain_pct'] for p in points] + [points[-1]['best_dev_gain_pct']]
        ax.step(xs, ys, where='post', color=color, lw=2, label=label)
        ax.scatter(xs[:-1], ys[:-1], s=20, color=color, zorder=4)
        ax.scatter(xs[-1], ys[-1], s=45, marker='s', facecolors='white', edgecolors=color, zorder=5)
    ax.set(xlim=(0, 370), ylim=(-.2, 6.9), xlabel='Elapsed time since episode start (s)',
        ylabel='Best dev score gain over dev c0 (%)', title='When improvements appeared during each research loop')
    ax.grid(); ax.set_axisbelow(True)
    ax.legend(loc='upper left', frameon=False, ncol=2)
    fig.text(.125, .005, '5 dev cases; dev c0 = 44,120. Dots: eligible validations. Open squares: loop end.\n'
             'Step curves carry the best observed dev score; final holdout scores are not used.',
             fontsize=8.5, color='#586779')
    fig.subplots_adjust(bottom=.22)
    save(fig, 'routing_trajectory')

    fig, axes = plt.subplots(1, 2, figsize=(8.7, 4.2), gridspec_kw={'width_ratios': [1, 1.5]})
    feedback = data['feedback']
    mode_labels = {'feedback': 'F', 'independent': 'I', 'no_feedback': 'N'}
    mode_colors = {'feedback': COLORS[1], 'independent': COLORS[2], 'no_feedback': COLORS[0]}
    for ax, task in zip(axes, ['ahc024', 'ahc026']):
        groups = [g for g in feedback['groups'] if g['task'] == task]
        for x, group in enumerate(groups):
            selected = [r for r in feedback['runs'] if task in r['task_id'] and r['mode'] == group['mode']]
            for dx, run in zip([-.12, 0, .12], selected):
                ax.scatter(x+dx, run['final_gain_pct'], s=50,
                    marker='X' if run['status'] == 'failed' else 'o',
                    facecolor='white' if run['best_candidate_id'] == 'c0' else mode_colors[group['mode']],
                    edgecolor=mode_colors[group['mode']], zorder=5, lw=1.3)
            ax.hlines(group['median_gain_pct'], x-.25, x+.25, color=mode_colors[group['mode']], lw=2.5)
            ax.text(x, group['median_gain_pct'] + (.13 if task == 'ahc026' else .13),
                    f"median {group['median_gain_pct']:.3f}%", ha='center', fontsize=8)
        ax.set_xticks(range(len(groups)), [mode_labels[g['mode']] for g in groups])
        ax.set(xlim=(-.55, len(groups)-.45), ylim=(-.35, 3.3 if task == 'ahc026' else .7),
               title=task, xlabel='Mode (three runs each)')
        ax.axhline(0, color='#AEB8C2', ls=':', lw=1);ax.grid(axis='y');ax.set_axisbelow(True)
    axes[0].set_ylabel('Final score gain over task-specific c0 (%)')
    fig.text(.125, -.005, 'F: feedback   I: independent   N: no feedback. Horizontal bars: medians.\n'
             'Open dots: c0 delivered. X: API-failed episode with a correct retained final candidate. Panel scales differ.',
             fontsize=8.5, color='#586779')
    fig.subplots_adjust(bottom=.23, wspace=.35)
    save(fig, 'feedback_ablation')

    fig, axes = plt.subplots(2, 2, figsize=(9.4, 7.3))
    xs = list(range(4))
    request_bottom = [0]*4
    for key, label, color in [('small_model_requests', 'Qwen generation', COLORS[1]),
                               ('large_model_requests', 'Sol generation', COLORS[2]),
                               ('routing_requests', 'Decisions', COLORS[3])]:
        vals = [r['iterations'][key] for r in runs]
        axes[0,0].bar(xs, vals, bottom=request_bottom, label=label, color=color, width=.6)
        for x, v, b in zip(xs, vals, request_bottom):
            if v: axes[0,0].text(x, b+v/2, str(v), ha='center', va='center', color='white', fontsize=9)
        request_bottom = [a+b for a,b in zip(request_bottom, vals)]
    axes[0,0].set(title='HTTP requests by role', ylabel='Requests', ylim=(0, 25))
    axes[0,0].axhline(20, color='#929CA8', linestyle=':', linewidth=1)
    axes[0,0].text(3.4,20.3,'cap 20',ha='right',fontsize=8,color='#586779')
    axes[0,0].legend(loc='upper left', fontsize=7.8, frameon=False, ncol=2)
    bottom = [0.]*4
    for key,label,color in [('model_wait_s','Model wait',COLORS[0]),('dev_evaluation_s','Dev judge',COLORS[1]),
                            ('final_evaluation_s','Final judge',COLORS[3]),('other_recorded_s','Residual','#C7D1DC')]:
        vals = [r['timing'][key] for r in runs]
        axes[0,1].bar(xs, vals, bottom=bottom, label=label, color=color, width=.6)
        bottom = [a+b for a,b in zip(bottom,vals)]
    axes[0,1].set(title='Recorded episode time', ylabel='Seconds', ylim=(0,510))
    axes[0,1].legend(loc='upper left', fontsize=7.8, frameon=False, ncol=2)
    for i,currency in enumerate(['CNY','USD']):
        ax=axes[1,i]
        vals=[r['cost']['by_currency'].get(currency,{}).get('known_amount',0) for r in runs]
        bars=ax.bar(xs,vals,color=COLORS,width=.6)
        if currency=='USD': bars[0].set_hatch('///')
        for x,v in zip(xs,vals):
            ax.text(x,v+max(vals)*.035,f'{v:.4f}'+('*' if currency=='USD' and x==0 else ''),ha='center',fontsize=8)
        ax.set(title=f'Known token cost ({currency})',ylabel=currency,ylim=(0,max(vals)*1.3))
    for ax in axes.flat:
        ax.set_xticks(xs,LABELS,fontsize=8.5);ax.grid(axis='y');ax.set_axisbelow(True)
    fig.text(.095, .005, '* Baseline USD is a known subtotal: one timed-out Sol request has unknown usage.\n'
            'Currencies are separate. Costs use frozen token rates; device cost is excluded. Startup timing is nested, not added.',
            fontsize=8.2,color='#586779')
    fig.subplots_adjust(hspace=.42,wspace=.3,bottom=.15)
    save(fig,'routing_resources')


def exports(data):
    fb=data['feedback']; rt=data['routing']; r=rt['runs']; c=data['desktop_cost']
    macros={
      'ReportFeedbackRuns':len(fb['runs']), 'ReportFeedbackCandidates':fb['totals']['proposed'],
      'ReportFeedbackPassed':fb['totals']['dev_passed'], 'ReportFeedbackPassRate':f"{fb['totals']['dev_pass_rate_pct']:.1f}",
      'ReportFeedbackCZero':fb['totals']['c0_deliveries'],'ReportFeedbackRequests':fb['totals']['requests'],
      'ReportFeedbackWall':f"{fb['batch_wall_s']:.3f}",'ReportRoutingWall':f"{rt['batch_wall_s']:.3f}",
      'ReportRoutingRequests':rt['totals']['requests'],'ReportRoutingCandidates':rt['totals']['proposed'],
      'ReportBaselineGain':f"{r[0]['final_gain_pct']:.3f}",'ReportActionGain':f"{r[1]['final_gain_pct']:.3f}",
      'ReportModelGain':f"{r[2]['final_gain_pct']:.3f}",'ReportBothGain':f"{r[3]['final_gain_pct']:.3f}",
      'ReportActionVsBaselinePct':f"{data['routing']['contrasts']['action_vs_baseline_score_pct']:.3f}",
      'ReportBothWallReductionPct':f"{data['routing']['contrasts']['both_vs_baseline_wall_reduction_pct']:.2f}",
      'ReportDesktopCNY':f"{c['CNY']['known_amount']:.6f}",'ReportDesktopUSD':f"{c['USD']['known_amount']:.7f}",
      'ReportRoutingCNY':f"{rt['cost']['CNY']['known_amount']:.6f}",
      'ReportRoutingUSD':f"{rt['cost']['USD']['known_amount']:.7f}",
    }
    (GENERATED/'metrics.tex').write_text('% Generated by scripts/analyze.py; values exclude Mac issue-only reports.\n'+
        '\n'.join('\\newcommand{\\'+name+'}{'+str(value)+'}' for name,value in macros.items())+'\n')
    labels=['LLM / rule','Decisions / rule','LLM / Decisions','Decisions / Decisions']
    (GENERATED/'routing_rows.tex').write_text('\n'.join(
       f"{label} & {run['final_score']} & {run['final_gain_pct']:.3f}\\% & {run['timing']['wall_clock_total_s']:.3f} & "
       f"{run['iterations']['small_model_requests']}/{run['iterations']['large_model_requests']}/{run['iterations']['routing_requests']} \\\\"
       for run,label in zip(r,labels))+'\n')
    short={'feedback':'F','independent':'I','no_feedback':'N'}
    (GENERATED/'feedback_rows.tex').write_text('\n'.join(
        f"{g['task']} & {short[g['mode']]} & {' / '.join(str(x) for x in g['final_scores'])} & {g['median_final_score']} & "
        f"{g['median_gain_pct']:.3f}\\% & {g['dev_passed']}/{g['proposed']} & {g['c0_deliveries']} \\\\"
        for g in fb['groups'])+'\n')


def main():
    GENERATED.mkdir(parents=True,exist_ok=True);FIGURES.mkdir(parents=True,exist_ok=True)
    feedback=batch('Desktop feedback ablation','native-formal-20261114/ale/results',True)
    routing=batch('Desktop 360-second routing study','native-routing/20261114/short-results')
    stopped=batch('Stopped 900-second routing batch','native-routing/20261114/long-batch-stopped')
    baseline,action,model,both=routing['runs']
    routing['contrasts']={'action_vs_baseline_score_delta':action['final_score']-baseline['final_score'],
       'action_vs_baseline_score_pct':100*(action['final_score']/baseline['final_score']-1),
       'model_vs_baseline_score_delta':model['final_score']-baseline['final_score'],
       'both_vs_baseline_wall_reduction_pct':100*(1-both['timing']['wall_clock_total_s']/baseline['timing']['wall_clock_total_s'])}
    all_runs=feedback['runs']+routing['runs']+stopped['runs']
    data={'schema_version':1,'scope':'Desktop archived reports only; Mac issue-only exploration excluded.',
      'definitions':{'final_gain_pct':'100 * (final_score / final_c0_score - 1)',
         'dev_trajectory':'Eligible correct dev validations from report.steps, timestamped at validation end; carry max observed score until loop end.',
         'wall_time':'report.timing.wall_clock_total_s; includes final; startup diagnostic overlaps measured stages.',
         'cost':'Frozen comparison price snapshots applied to report usage by model; unknown usage yields null total with known subtotal.',
         'replication':'15 feedback episodes; 4 routing episodes; 2 started stopped-batch episodes, kept separate.'},
      'feedback':feedback,'routing':routing,'stopped_routing':stopped,'desktop_cost':cost_totals(all_runs),
      'source_files':[{'path':p,'sha256':h} for p,h in sorted(SOURCES.items())]}
    # Check study-level invariants before emitting a report from the frozen archive.
    assert feedback['totals']['proposed']==96 and feedback['totals']['dev_passed']==60
    assert feedback['totals']['c0_deliveries']==8 and feedback['totals']['final_correct']==15
    assert routing['totals']['requests']==61 and routing['totals']['proposed']==24
    close(data['desktop_cost']['CNY']['known_amount'],8.015241,'desktop CNY')
    close(data['desktop_cost']['USD']['known_amount'],1.5759592,'desktop USD')
    (GENERATED/'analysis.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    exports(data);figures(data)
    print(json.dumps({'source_files':len(SOURCES),'feedback':feedback['totals'],
      'routing':routing['totals'],'contrasts':routing['contrasts'],'desktop_cost':data['desktop_cost']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
