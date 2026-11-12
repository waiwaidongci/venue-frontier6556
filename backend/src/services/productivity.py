"""跨期生产率分解（Malmquist / CCR 投入导向）。

每个同编号场馆用四个径向效率分数构造分解：
  θ_b(x_b)  前期目标对前期参照
  θ_a(x_a)  后期目标对后期参照
  θ_a(x_b)  前期目标对后期参照（交叉）
  θ_b(x_a)  后期目标对前期参照（交叉）

  追赶 EC   = θ_a(x_a) / θ_b(x_b)
  前沿移动 TC = sqrt( θ_b(x_b)/θ_a(x_b) * θ_b(x_a)/θ_a(x_a) )
  总变化 TFP = EC * TC

θ>1 表示交叉参照下目标优于另一期前沿；不裁剪。任一分数为 0（零产出）
或任一求解非最优时，整条配对标记为无法比较，不计算也不填比值。
"""
import copy
import hashlib
import json
import math
from collections import Counter

import numpy as np

from src.constants.enums import INPUTS, OUTPUTS
from src.services.dea_solver import solve_dmu

ALGORITHM = 'malmquist-cross-period-crs-input-v1'
TOL = 1e-9
POLICY = (
    '前期与后期各自使用本期全部观察为参照；交叉参照使用另一期完整参照集。'
    '只按场馆编号配对分解；仅在单期出现的场馆单独列示，不参与配对。'
    '零产出或任一求解非最优时标记无法比较，返回空值而非填零或硬算比值。'
    '旧档案保留建立时的完整样本与指纹，源数据更新后请新建比较。'
)

_LABELS = {
    'own_before': '前期目标对前期参照',
    'own_after': '后期目标对后期参照',
    'before_against_after': '前期目标对后期参照（交叉）',
    'after_against_before': '后期目标对前期参照（交叉）',
}


def _validated(records, inputs, outputs, label):
    if not records:
        raise ValueError(f'{label}没有观察，无法进行跨期比较')
    if any(f not in INPUTS for f in inputs) or any(f not in OUTPUTS for f in outputs):
        raise ValueError('投入或产出字段不在允许集合内')
    if not inputs or not outputs:
        raise ValueError('至少选择一项投入和一项产出')
    codes = [r['venue_code'] for r in records]
    if len(set(codes)) != len(codes):
        raise ValueError(f'{label}存在重复场馆编号，无法配对')
    for record in records:
        for field in inputs:
            value = float(record[field])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{label} {record["venue_code"]} 的 {field} 必须为正有限值')
        for field in outputs:
            value = float(record[field])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'{label} {record["venue_code"]} 的 {field} 必须为非负有限值')
    return sorted(records, key=lambda r: r['venue_code'])


def _solve(x0, y0, x_ref, y_ref, xs, ys):
    try:
        solution = solve_dmu(x0, y0, x_ref, y_ref, xs, ys)
    except ValueError as exc:
        return {'status': 'invalid', 'theta': None, 'message': str(exc), 'zero_output': False}
    return {
        'status': solution.get('status'),
        'theta': solution.get('theta'),
        'message': solution.get('message', ''),
        'zero_output': bool(solution.get('zero_output', False)),
    }


def _not_comparable(pair, scores):
    failed = [(key, score) for key, score in scores.items() if score['status'] != 'optimal']
    if failed:
        infeasible = [(key, score) for key, score in failed if score['status'] == 'infeasible']
        key, score = (infeasible or failed)[0]
        if score['status'] == 'infeasible':
            reason = f'{_LABELS[key]}求解不可行：参照集无法覆盖该目标期产出，无法比较'
        else:
            reason = f'{_LABELS[key]}求解状态为 {score["status"]}，无法比较'
        pair.update(status='not_comparable', reason=reason, catch_up=None,
                    frontier_shift=None, total_change=None, direction='unavailable')
        return pair

    zero_periods = []
    if scores['own_before']['zero_output'] or scores['before_against_after']['zero_output']:
        zero_periods.append('前期')
    if scores['own_after']['zero_output'] or scores['after_against_before']['zero_output']:
        zero_periods.append('后期')
    if zero_periods:
        reason = f'{"/".join(zero_periods)}目标产出为零（径向θ=0），追赶与前沿比值未定义，无法比较'
        pair.update(status='not_comparable', reason=reason, catch_up=None,
                    frontier_shift=None, total_change=None, direction='unavailable')
        return pair

    thetas = [score['theta'] for score in scores.values()]
    if any(theta is None or not math.isfinite(float(theta)) or float(theta) <= TOL for theta in thetas):
        pair.update(status='not_comparable', reason='径向效率为0或不是有限正数，追赶与前沿比值未定义，无法比较',
                    catch_up=None, frontier_shift=None, total_change=None, direction='unavailable')
        return pair
    pair['status'] = 'comparable'
    return pair


def _direction(value):
    if value > 1 + TOL:
        return 'improved'
    if value < 1 - TOL:
        return 'regressed'
    return 'unchanged'


def _geometric_mean(values):
    if not values:
        return None
    return float(math.exp(sum(math.log(v) for v in values) / len(values)))


def compare_periods(before_records, after_records, inputs, outputs, before_meta=None, after_meta=None):
    inputs = list(inputs)
    outputs = list(outputs)
    before = _validated(before_records, inputs, outputs, '前期')
    after = _validated(after_records, inputs, outputs, '后期')
    before_meta = dict(before_meta or {'code': '', 'name': '前期', 'period': '前期'})
    after_meta = dict(after_meta or {'code': '', 'name': '后期', 'period': '后期'})

    xb = np.array([[r[f] for f in inputs] for r in before], float)
    yb = np.array([[r[f] for f in outputs] for r in before], float)
    xa = np.array([[r[f] for f in inputs] for r in after], float)
    ya = np.array([[r[f] for f in outputs] for r in after], float)
    # 统一缩放：两期所有观察共用同一组正比例因子，四类分数和全部比值对单位缩放不变。
    xs = np.maximum(np.maximum(xb.max(axis=0), xa.max(axis=0)), 1e-12)
    ys = np.maximum(np.maximum(yb.max(axis=0), ya.max(axis=0)), 1.0)

    before_by_code = {r['venue_code']: r for r in before}
    after_by_code = {r['venue_code']: r for r in after}
    paired_codes = sorted(set(before_by_code) & set(after_by_code))

    pairs = []
    for code in paired_codes:
        rb = before_by_code[code]
        ra = after_by_code[code]
        x0b = np.array([rb[f] for f in inputs], float)
        y0b = np.array([rb[f] for f in outputs], float)
        x0a = np.array([ra[f] for f in inputs], float)
        y0a = np.array([ra[f] for f in outputs], float)
        scores = {
            'own_before': _solve(x0b, y0b, xb, yb, xs, ys),
            'own_after': _solve(x0a, y0a, xa, ya, xs, ys),
            'before_against_after': _solve(x0b, y0b, xa, ya, xs, ys),
            'after_against_before': _solve(x0a, y0a, xb, yb, xs, ys),
        }
        theta_bb = scores['own_before']['theta']
        theta_aa = scores['own_after']['theta']
        theta_ab = scores['before_against_after']['theta']
        theta_ba = scores['after_against_before']['theta']
        pair = {
            'venue_code': code,
            'venue_name': ra.get('venue_name') or rb.get('venue_name') or code,
            'before_observation_id': rb.get('observation_id'),
            'after_observation_id': ra.get('observation_id'),
            'before': {f: rb[f] for f in inputs + outputs},
            'after': {f: ra[f] for f in inputs + outputs},
            'scores': {
                key: {'theta': score['theta'], 'status': score['status'],
                      'zero_output': score['zero_output'], 'message': score['message']}
                for key, score in scores.items()
            },
            'catch_up': None,
            'frontier_shift': None,
            'total_change': None,
            'direction': 'unavailable',
            'status': 'not_comparable',
            'reason': '',
        }
        pair = _not_comparable(pair, scores)
        if pair['status'] == 'comparable':
            catch_up = float(theta_aa) / float(theta_bb)
            frontier_shift = math.sqrt(
                (float(theta_bb) / float(theta_ab)) * (float(theta_ba) / float(theta_aa))
            )
            total_change = catch_up * frontier_shift
            pair.update(
                status='comparable',
                reason='',
                catch_up=catch_up,
                frontier_shift=frontier_shift,
                total_change=total_change,
                direction=_direction(total_change),
            )
        pairs.append(pair)

    only_before = [copy.deepcopy(r) for r in before if r['venue_code'] not in after_by_code]
    only_after = [copy.deepcopy(r) for r in after if r['venue_code'] not in before_by_code]
    comparable = [p for p in pairs if p['status'] == 'comparable']
    counts = Counter(p['direction'] for p in comparable)
    result = {
        'algorithm': ALGORITHM,
        'policy': POLICY,
        'before': dict(before_meta),
        'after': dict(after_meta),
        'inputs': inputs,
        'outputs': outputs,
        'input_scales': dict(zip(inputs, xs.tolist())),
        'output_scales': dict(zip(outputs, ys.tolist())),
        'sample': {'before': copy.deepcopy(before), 'after': copy.deepcopy(after)},
        'pairs': pairs,
        'only_before': only_before,
        'only_after': only_after,
        'summary': {
            'before_count': len(before),
            'after_count': len(after),
            'paired_count': len(pairs),
            'comparable_count': len(comparable),
            'not_comparable_count': len(pairs) - len(comparable),
            'only_before_count': len(only_before),
            'only_after_count': len(only_after),
            'improved_count': counts['improved'],
            'regressed_count': counts['regressed'],
            'unchanged_count': counts['unchanged'],
            'geometric_mean_catch_up': _geometric_mean([p['catch_up'] for p in comparable]),
            'geometric_mean_frontier_shift': _geometric_mean([p['frontier_shift'] for p in comparable]),
            'geometric_mean_total_change': _geometric_mean([p['total_change'] for p in comparable]),
        },
    }
    snapshot = {
        'algorithm': ALGORITHM,
        'policy': POLICY,
        'before': result['before'],
        'after': result['after'],
        'inputs': inputs,
        'outputs': outputs,
        'input_scales': result['input_scales'],
        'output_scales': result['output_scales'],
        'sample': result['sample'],
    }
    result['fingerprint'] = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    ).hexdigest()
    return result
