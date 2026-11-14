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
import re
import statistics
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
RESEARCH = ROOT / 'docs/research'
GENERATED = HERE / 'generated'
FIGURES = HERE / 'figures'
SOURCES: dict[str, str] = {}
VARIANTS = ['baseline', 'action_decisions', 'model_decisions', 'both_decisions']
LABELS = ['基线路由', '动作决策', '模型决策', '双决策']
COLORS = ['#304B68', '#008779', '#466BD4', '#D18527']


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


def deep_analysis(data):
    """Analyze candidate outcomes and routing events without conflating c0 with running best."""
    batches = {}
    for name in ['feedback', 'routing']:
        runs = []
        for metric in data[name]['runs']:
            report = read(ROOT / metric['source_report'])
            validation_by_id = {s['evaluation_id']: s for s in report['steps']
                if s['action'] == 'run_validation' and s.get('evaluation_id')}
            candidates = []
            model_hashes = Counter()
            all_prior_hashes = {report['candidates'][0]['code_sha256']}
            c0_hash = report['candidates'][0]['code_sha256']
            running_best = metric['dev_c0_score']
            for candidate in report['candidates']:
                if candidate['origin'] != 'model':
                    continue
                evaluations = candidate['dev_evaluations']
                if len(evaluations) != 1:
                    raise ValueError('This frozen study expects one dev evaluation per proposed candidate')
                evaluation = evaluations[0]
                step = validation_by_id[evaluation['evaluation_id']]
                result = step['result']
                obj = evaluation['objective']
                correct = bool(evaluation['correct'])
                improved = correct and obj['value'] > obj['baseline']
                sha = candidate['code_sha256']
                exception_types = re.findall(r'(?m)^([A-Za-z]+(?:Error|Exception)):', (result.get('failure') or {}).get('stderr_tail', ''))
                previous_best = running_best
                if correct:
                    running_best = max(running_best, obj['value'])
                candidates.append({'candidate_id': candidate['candidate_id'], 'sha256': sha,
                    'evaluation_id': evaluation['evaluation_id'],
                    'correct': correct, 'outcome': 'correct_above_c0' if improved else 'correct_not_above_c0' if correct else 'failed',
                    'dev_score': obj['value'] if obj else None,
                    'new_best': bool(result.get('best_replaced', False)),
                    'failure_category': (result.get('failure') or {}).get('category', evaluation['status']) if not correct else None,
                    'failure_exception_type': exception_types[-1] if exception_types else None,
                    'score_delta_from_previous_best': obj['value'] - previous_best if correct else None,
                    'failure_detail': (result.get('failure') or {}).get('message') if not correct else None,
                    'elapsed_s': elapsed(report['started_at'], step['ended_at']),
                    'same_as_c0': sha == c0_hash,
                    'repeated_from_earlier_candidate': sha in all_prior_hashes})
                model_hashes[sha] += 1
                all_prior_hashes.add(sha)
            model_action_counts = Counter(s['action'] for s in report['steps'] if s['actor'] == 'model')
            decision_choices = defaultdict(Counter)
            for step in report['steps']:
                if step['actor'] == 'model' and step['action'] in ('route_action', 'route_model'):
                    decision_choices[step['action']][step['result'].get('choice', 'no_choice')] += 1
            upgrades = [{'step': s['seq'], 'elapsed_s': elapsed(report['started_at'], s['ended_at']),
                         'reason': s['result']} for s in report['steps'] if s['action'] == 'upgrade_model']
            role_usage = {}
            for key, usage in report['usage']['by_model'].items():
                role = key.split(':', 1)[0]
                role_usage[role] = {'requests': usage['requests'], 'ok': usage['ok'],
                     'errors': usage['errors'], 'latency_s': usage['latency_s'],
                     'mean_latency_s': usage['latency_s'] / usage['requests'],
                     'cost': metric['cost']['by_role'][role]}
            by_purpose = {purpose: {key: u[key] for key in ['requests', 'ok', 'errors', 'latency_s']}
                          for purpose, u in report['usage']['by_purpose'].items()}
            first_improvement = next((c for c in candidates if c['outcome'] == 'correct_above_c0'), None)
            runs.append({'run_id': metric['run_id'], 'task_id': metric['task_id'], 'mode': metric['mode'],
                'variant': metric['variant'], 'status': metric['status'], 'stop_reason': metric['stop_reason'],
                'stop_detail': report['stop_detail'], 'loop_elapsed_s': metric['loop_end_elapsed_s'],
                'final_score': metric['final_score'], 'best_candidate_id': metric['best_candidate_id'],
                'candidates': candidates, 'outcomes': dict(Counter(c['outcome'] for c in candidates)),
                'failure_categories': dict(Counter(c['failure_category'] for c in candidates if not c['correct'])),
                'api_errors': report['usage']['total']['errors'],
                'new_best_candidates': sum(c['new_best'] for c in candidates),
                'correct_without_new_best': sum(c['correct'] and not c['new_best'] for c in candidates),
                'correct_below_previous_best': sum(c['correct'] and c['score_delta_from_previous_best'] < 0 for c in candidates),
                'failure_exception_types': dict(Counter(c['failure_exception_type'] for c in candidates if c['failure_exception_type'])),
                'unique_model_code_hashes': len(model_hashes),
                'duplicate_model_code_occurrences': sum(n-1 for n in model_hashes.values()),
                'same_as_c0_candidates': sum(c['same_as_c0'] for c in candidates),
                'repeated_from_earlier_candidates': sum(c['repeated_from_earlier_candidate'] for c in candidates),
                'model_actor_action_counts': dict(model_action_counts),
                'decision_choice_counts': {k:dict(v) for k,v in decision_choices.items()},
                'role_usage': role_usage, 'purpose_usage': by_purpose,
                'first_improvement': first_improvement, 'upgrades': upgrades,
                'source_report': metric['source_report']})
        groups = []
        group_specs = [(g['task'],g['mode'],None) for g in data['feedback']['groups']] if name == 'feedback' else [(None,None,v) for v in VARIANTS]
        for task,mode,variant in group_specs:
            selected = [r for r in runs if r['variant']==variant] if variant else [r for r in runs if task in r['task_id'] and r['mode']==mode]
            candidates = [(r['run_id'],c) for r in selected for c in r['candidates']]
            hashes = defaultdict(list)
            for run_id,c in candidates:
                hashes[c['sha256']].append({'run_id':run_id,'candidate_id':c['candidate_id']})
            outcomes = Counter(c['outcome'] for _,c in candidates)
            failures = Counter(c['failure_category'] for _,c in candidates if not c['correct'])
            api_errors = Counter()
            for run in selected: api_errors.update(run['api_errors'])
            groups.append({'task':task,'mode':mode,'variant':variant,'runs':len(selected),
                'proposed':len(candidates),'outcomes':dict(outcomes),'failure_categories':dict(failures),
                'api_errors':dict(api_errors),'new_best_candidates':sum(c['new_best'] for _,c in candidates),
                'correct_without_new_best':sum(c['correct'] and not c['new_best'] for _,c in candidates),
                'correct_below_previous_best':sum(c['correct'] and c['score_delta_from_previous_best'] < 0 for _,c in candidates),
                'failure_exception_types':dict(Counter(c['failure_exception_type'] for _,c in candidates if c['failure_exception_type'])),
                'unique_code_hashes':len(hashes),'duplicate_code_occurrences':len(candidates)-len(hashes),
                'repeated_from_earlier_candidates_within_runs':sum(c['repeated_from_earlier_candidate'] for _,c in candidates),
                'same_as_c0_candidates':sum(c['same_as_c0'] for _,c in candidates),
                'duplicate_groups':[{'sha256':sha,'count':len(refs),'candidates':refs} for sha,refs in hashes.items() if len(refs)>1]})
        batches[name]={'runs':runs,'groups':groups}
    c0_metric = next(r for r in data['feedback']['runs'] if 'ahc026' in r['task_id'] and r['best_candidate_id']=='c0')
    c0_report = read(ROOT / c0_metric['source_report'])
    c0_case_scores = [case['score'] for case in c0_report['final_evaluation']['objective']['cases']]
    assert len(c0_case_scores)==15 and min(c0_case_scores)>1
    c0_energy = 10000*len(c0_case_scores)-sum(c0_case_scores)
    movement_energy = {'quantity':'ahc026 box-movement energy expenditure V; not CPU or device energy',
        'per_case_score_formula':'score = max(1, 10000 - V)',
        'aggregate_conversion':'sum(V) = 10000 * case_count - sum(score), valid here because every score > 1',
        'statement_source':'docs/research/native-routing/20261114/short-results/run-20261114T085616-894b/model_calls/m2.json',
        'c0_source':c0_metric['source_report'],'c0_case_scores':c0_case_scores,
        'c0_total_energy':c0_energy,'runs':[]}
    for metric, run in zip(data['routing']['runs'],batches['routing']['runs']):
        report=read(ROOT/metric['source_report'])
        assert report['candidates'][0]['code_sha256']==c0_report['candidates'][0]['code_sha256']
        scores=[case['score'] for case in report['final_evaluation']['objective']['cases']]
        assert len(scores)==15 and min(scores)>1 and metric['final_c0_score']==sum(c0_case_scores)
        energy=10000*len(scores)-sum(scores)
        item={'variant':metric['variant'],'case_count':len(scores),'minimum_case_score':min(scores),
            'final_case_scores':scores,'final_total_energy':energy,
            'energy_reduction_vs_c0':c0_energy-energy,'energy_reduction_vs_c0_pct':100*(1-energy/c0_energy),
            'source_report':metric['source_report']}
        movement_energy['runs'].append(item)
        run['box_movement_energy']=item
    return {'schema_version':1,'project':'QuotaCrux / 枢决','ahc026_movement_energy':movement_energy,
        'definitions':{
            'candidate_outcomes':'Mutually exclusive categories on the single dev evaluation per model candidate: correct_above_c0 = correct and score > c0; correct_not_above_c0 = correct and score <= c0; failed = incorrect or execution failure.',
            'new_best':'run_validation.result.best_replaced; distinct from exceeding c0.',
            'duplicate_code_occurrences':'Within each reported group, model-generated candidate count minus unique exact code SHA256 count. c0 excluded from the set; same_as_c0 counted separately.',
            'first_improvement':'First correct model candidate strictly above dev c0, using validation-ended timestamp minus episode-start; no statistical threshold.',
            'action_counts':'All steps with actor=model; includes invalid actions, API error steps, and finish. These are recorded events, not distinct HTTP requests.',
            'latency':'Usage ledger latency per role/purpose; generation includes analyze and finish as well as code proposals.',
            'sources':'Subset of the archived desktop report inputs already fingerprinted in analysis.json. Mac reports excluded.'},
        **batches,'source_files':[{'path':p,'sha256':h} for p,h in sorted(SOURCES.items())]}


def report_font(extra_text: str = ''):
    """Convert a glyph subset of the specified CFF font for valid PDF Type 42 embedding."""
    original = Path('/usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-Regular.otf')
    font_manager.fontManager.addfont(str(original))
    characters = set(Path(__file__).read_text() + extra_text) | set(chr(i) for i in range(32, 127))
    fingerprint = hashlib.sha256(original.read_bytes() + Path(__file__).read_bytes()
                                 + extra_text.encode()).hexdigest()[:16]
    converted = Path(tempfile.gettempdir()) / f'quotacrux-report-sans-{fingerprint}.ttf'
    if not converted.exists():
        from fontTools import subset
        from fontTools.fontBuilder import FontBuilder
        from fontTools.ttLib import TTFont
        from fontTools.pens.cu2quPen import Cu2QuPen
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        original_font = TTFont(original)
        subsetter = subset.Subsetter()
        subsetter.populate(unicodes=[ord(char) for char in characters])
        subsetter.subset(original_font)
        order = original_font.getGlyphOrder()
        glyph_set = original_font.getGlyphSet()
        quadratic_glyphs = {}
        for name in order:
            pen = TTGlyphPen(glyph_set)
            glyph_set[name].draw(Cu2QuPen(pen, max_err=0.7, reverse_direction=True))
            quadratic_glyphs[name] = pen.glyph()
        builder = FontBuilder(original_font['head'].unitsPerEm, isTTF=True)
        builder.setupGlyphOrder(order)
        builder.setupCharacterMap(original_font.getBestCmap())
        builder.setupGlyf(quadratic_glyphs)
        builder.setupHorizontalMetrics(original_font['hmtx'].metrics)
        builder.setupHorizontalHeader(ascent=original_font['hhea'].ascent, descent=original_font['hhea'].descent)
        builder.setupNameTable({'familyName':'QuotaCrux Report Sans','styleName':'Regular',
            'uniqueFontIdentifier':'QuotaCrux Report Sans Regular','fullName':'QuotaCrux Report Sans Regular',
            'psName':'QuotaCruxReportSans-Regular','version':'Version 1.0',
            'copyright':original_font['name'].getDebugName(0) or '',
            'licenseDescription':original_font['name'].getDebugName(13) or '',
            'licenseInfoURL':original_font['name'].getDebugName(14) or ''})
        os2 = original_font['OS/2']
        builder.setupOS2(sTypoAscender=os2.sTypoAscender,sTypoDescender=os2.sTypoDescender,
            usWinAscent=os2.usWinAscent,usWinDescent=os2.usWinDescent)
        builder.setupPost()
        builder.font['head'].created = builder.font['head'].modified = 2082844800
        builder.save(converted)
    font_manager.fontManager.addfont(str(converted))
    return 'QuotaCrux Report Sans'


def style():
    plt.rcParams.update({'font.family':report_font(),'font.size':11,
        'font.weight':'normal','axes.titleweight':'normal','axes.titlesize':13,
        'axes.labelsize':11,'axes.edgecolor':'#CFD5DC','axes.labelcolor':'#233A54','text.color':'#233A54',
        'xtick.color':'#526478','ytick.color':'#526478','axes.spines.top':False,
        'axes.spines.right':False,'figure.facecolor':'white','axes.facecolor':'white',
        'grid.color':'#E6EBF0','grid.linewidth':.7,'pdf.fonttype':42,
        'savefig.facecolor':'white','svg.fonttype':'none','axes.unicode_minus':False})


def save(fig,name):
    fig.savefig(FIGURES/(name+'.pdf'),bbox_inches='tight',
        metadata={'Title':name,'Author':'QuotaCrux / 枢决','CreationDate':None,'ModDate':None})
    fig.savefig(FIGURES/(name+'.png'),dpi=190,bbox_inches='tight')
    plt.close(fig)


def figures(data,deep):
    style()
    runs=data['routing']['runs']
    fig,ax=plt.subplots(figsize=(6.8,3.9))
    ax.grid();ax.set_axisbelow(True)
    offsets=[(15,-21),(15,19),(15,-57),(15,18)]
    for run,label,color,offset in zip(runs,LABELS,COLORS,offsets):
        x=run['timing']['wall_clock_total_s'];y=run['final_gain_pct']
        ax.scatter(x,y,s=65,marker='s' if run['variant']=='baseline' else 'o',color=color,zorder=4)
        ax.annotate(f'{label}\n+{y:.3f}%',(x,y),xytext=offset,textcoords='offset points',fontsize=10,
            color=color,arrowprops={'arrowstyle':'-','color':color,'lw':.7})
    ax.set(xlim=(70,510),ylim=(-.25,8.1),xlabel='研究总耗时（秒，含最终评测）',
        ylabel='最终得分相对初始程序的提升（%）',title='相同预算下的质量与耗时')
    ax.axhline(0,color='#A0ADBA',lw=.8,ls=':')
    fig.subplots_adjust(left=.13,bottom=.18,right=.97,top=.87)
    save(fig,'routing_tradeoff')

    fig,ax=plt.subplots(figsize=(6.8,4.0))
    for run,label,color in zip(runs,LABELS,COLORS):
        points=run['dev_trajectory']
        xs=[p['elapsed_s'] for p in points]+[run['loop_end_elapsed_s']]
        ys=[p['best_dev_gain_pct'] for p in points]+[points[-1]['best_dev_gain_pct']]
        ax.step(xs,ys,where='post',color=color,lw=1.8,label=label)
        ax.scatter(xs[:-1],ys[:-1],s=18,color=color,zorder=4)
        ax.scatter(xs[-1],ys[-1],s=42,marker='s',facecolor='white',edgecolor=color,zorder=5)
    ax.set(xlim=(0,370),ylim=(-.2,7.5),xlabel='自研究启动起的耗时（秒）',
        ylabel='最佳开发得分相对初始程序的提升（%）',title='改进在研究过程中的出现时刻')
    ax.grid();ax.set_axisbelow(True);ax.legend(loc='upper left',frameon=False,ncol=2,fontsize=10)
    fig.subplots_adjust(left=.13,bottom=.18,right=.97,top=.87)
    save(fig,'routing_trajectory')

    fig,axes=plt.subplots(1,2,figsize=(6.8,3.9),gridspec_kw={'width_ratios':[1,1.45]})
    mode_labels={'feedback':'反馈','independent':'独立','no_feedback':'无反馈'}
    mode_colors={'feedback':COLORS[1],'independent':COLORS[2],'no_feedback':COLORS[0]}
    for ax,task in zip(axes,['ahc024','ahc026']):
        groups=[g for g in data['feedback']['groups'] if g['task']==task]
        for x,g in enumerate(groups):
            selected=[r for r in data['feedback']['runs'] if task in r['task_id'] and r['mode']==g['mode']]
            for dx,run in zip([-.13,0,.13],selected):
                ax.scatter(x+dx,run['final_gain_pct'],s=45,marker='X' if run['status']=='failed' else 'o',
                    facecolor='white' if run['best_candidate_id']=='c0' else mode_colors[g['mode']],
                    edgecolor=mode_colors[g['mode']],zorder=5,lw=1.2)
            ax.hlines(g['median_gain_pct'],x-.25,x+.25,color=mode_colors[g['mode']],lw=2)
            ax.text(x,g['median_gain_pct']+.15,f"{g['median_gain_pct']:.3f}%",ha='center',fontsize=9)
        ax.set_xticks(range(len(groups)),[mode_labels[g['mode']] for g in groups],fontsize=10)
        ax.set(xlim=(-.5,len(groups)-.5),ylim=(-.25,3.3 if task=='ahc026' else 1.1),
            title=task,xlabel='研究策略（每组 3 次）')
        ax.axhline(0,color='#A0ADBA',ls=':',lw=.8);ax.grid(axis='y');ax.set_axisbelow(True)
    axes[0].set_ylabel('最终得分相对初始程序的提升（%）')
    fig.subplots_adjust(left=.13,bottom=.19,wspace=.32,right=.97,top=.87)
    save(fig,'feedback_ablation')

    fig,axes=plt.subplots(2,2,figsize=(7.2,6.1));xs=list(range(4))
    bottom=[0]*4
    for key,label,color in [('small_model_requests','Qwen 生成',COLORS[1]),
                           ('large_model_requests','Sol 生成',COLORS[2]),('routing_requests','决策 API',COLORS[3])]:
        vals=[r['iterations'][key] for r in runs]
        axes[0,0].bar(xs,vals,bottom=bottom,label=label,color=color,width=.6)
        for x,v,b in zip(xs,vals,bottom):
            if v:axes[0,0].text(x,b+v/2,str(v),ha='center',va='center',color='white',fontsize=10)
        bottom=[a+b for a,b in zip(bottom,vals)]
    axes[0,0].set(title='模型与决策请求',ylabel='请求次数',ylim=(0,28))
    axes[0,0].axhline(20,color='#9CAAB7',ls=':',lw=.9)
    axes[0,0].legend(loc='upper left',fontsize=8.5,frameon=False,ncol=2)
    bottom=[0.]*4
    for key,label,color in [('model_wait_s','模型等待',COLORS[0]),('dev_evaluation_s','开发评测',COLORS[1]),
                            ('final_evaluation_s','最终评测',COLORS[3]),('other_recorded_s','其他','#C7D1DC')]:
        vals=[r['timing'][key] for r in runs]
        axes[0,1].bar(xs,vals,bottom=bottom,label=label,color=color,width=.6)
        bottom=[a+b for a,b in zip(bottom,vals)]
    axes[0,1].set(title='研究耗时构成',ylabel='秒',ylim=(0,530))
    axes[0,1].legend(loc='upper left',fontsize=8.5,frameon=False,ncol=2)
    for i,currency in enumerate(['CNY','USD']):
        ax=axes[1,i];vals=[r['cost']['by_currency'].get(currency,{}).get('known_amount',0) for r in runs]
        bars=ax.bar(xs,vals,color=COLORS,width=.6)
        if currency=='USD':
            bars[0].set_hatch('///')
            bars[0].set_edgecolor('white')
        for x,v in zip(xs,vals):
            ax.text(x,v+max(vals)*.035,f'{v:.4f}'+('*' if currency=='USD' and x==0 else ''),ha='center',fontsize=9)
        ax.set(title=f'已知费用（{currency}）',ylabel=currency,ylim=(0,max(vals)*1.3))
    for ax in axes.flat:
        ax.set_xticks(xs,LABELS,fontsize=9,rotation=15);ax.grid(axis='y');ax.set_axisbelow(True)
    fig.subplots_adjust(hspace=.46,wspace=.33,bottom=.12,left=.11,right=.98,top=.92)
    save(fig,'routing_resources')

    fig,axes=plt.subplots(1,2,figsize=(7.2,4.0),gridspec_kw={'width_ratios':[1.25,1]})
    for ax,name,title in zip(axes,['feedback','routing'],['固定 Qwen：研究策略对照','混合模型：路由对照']):
        groups=deep[name]['groups'];xs=list(range(len(groups)));bottom=[0]*len(groups)
        for key,label,color in [('correct_above_c0','正确且优于初始',COLORS[1]),
              ('correct_not_above_c0','正确但未优于初始',COLORS[3]),('failed','失败','#C16B64')]:
            vals=[g['outcomes'].get(key,0) for g in groups]
            ax.bar(xs,vals,bottom=bottom,color=color,width=.64,label=label)
            for x,v,b in zip(xs,vals,bottom):
                if v:ax.text(x,b+v/2,str(v),ha='center',va='center',color='white',fontsize=10)
            bottom=[a+b for a,b in zip(bottom,vals)]
        labels=[g['task'].replace('ahc','')+'\n'+mode_labels[g['mode']] for g in groups] if name=='feedback' else [v.replace('路由','\n路由').replace('决策','\n决策') for v in LABELS]
        ax.set_xticks(xs,labels,fontsize=9);ax.set(title=title,ylabel='模型候选数',ylim=(0,max(bottom)*1.17))
        ax.grid(axis='y');ax.set_axisbelow(True)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=3,frameon=False,fontsize=9)
    fig.subplots_adjust(left=.09,right=.99,bottom=.24,top=.85,wspace=.31)
    save(fig,'candidate_outcomes')

    action=data['routing']['runs'][1];points=action['dev_trajectory']
    fig,ax=plt.subplots(figsize=(6.8,3.9));xs=list(range(len(points)))
    actual=[p['candidate_dev_score'] for p in points];best=[p['best_dev_score'] for p in points]
    ax.plot(xs,actual,color=COLORS[2],marker='o',ms=5,lw=1.7,label='本次候选得分',zorder=3)
    ax.step(xs,best,color=COLORS[1],where='post',lw=1.8,label='保留的最佳得分',zorder=2)
    for x,value in zip(xs,actual):
        if x in [0,3,4,6,7]:ax.annotate(f'{value:,}',(x,value),xytext=(0,10 if x%2 else -19),textcoords='offset points',ha='center',fontsize=9,color=COLORS[0])
    ax.scatter([5],[actual[5]],s=65,color=COLORS[3],zorder=5)
    ax.annotate('c5：46,725\n回退后保留 c4',xy=(5,actual[5]),xytext=(4.3,45100),fontsize=10,color=COLORS[3],
        arrowprops={'arrowstyle':'->','color':COLORS[3],'lw':1})
    ax.set_xticks(xs,[p['candidate_id'] for p in points]);ax.set(xlim=(-.3,7.6),ylim=(43600,47700),
        xlabel='候选提交顺序',ylabel='开发集总分（5 个用例）',title='动作决策案例：探索新方案并保留最佳结果')
    ax.legend(loc='upper left',frameon=False,fontsize=10);ax.grid();ax.set_axisbelow(True)
    fig.subplots_adjust(left=.14,bottom=.18,right=.98,top=.87)
    save(fig,'action_case')


def exports(data,deep):
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
    movement=deep['ahc026_movement_energy']
    macros['ReportInitialMovementEnergy']=movement['c0_total_energy']
    for label,item in zip(['Baseline','Action','Model','Both'],movement['runs']):
        macros[f'Report{label}MovementEnergy']=item['final_total_energy']
        macros[f'Report{label}MovementReduction']=f"{item['energy_reduction_vs_c0_pct']:.3f}"
    (GENERATED/'metrics.tex').write_text('% Generated by scripts/analyze.py; desktop metrics only.\n'+
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
    data={'schema_version':1,'scope':'Desktop archived reports; Mac exploration is analyzed separately in mac-analysis.json.',
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
    deep=deep_analysis(data)
    (GENERATED/'deep-analysis.json').write_text(json.dumps(deep,ensure_ascii=False,indent=2)+'\n')
    exports(data,deep);figures(data,deep)
    print(json.dumps({'source_files':len(SOURCES),'feedback':feedback['totals'],
      'routing':routing['totals'],'contrasts':routing['contrasts'],'desktop_cost':data['desktop_cost']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
