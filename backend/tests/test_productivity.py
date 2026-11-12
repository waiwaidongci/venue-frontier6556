"""跨期生产率分解的可手算样例与边界验证。

主样例（单投入单产出，CRS 下 θ = y/(e·x)，e 为该期参照集最高 y/x）:
             x     y    y/x
前期 P1  A   1     1     1
         B   1     2     2   ← 前期前沿 e_b=2
         C   1     1     1
后期 P2  A   1     2     2
         B   1     3     3   ← 后期前沿 e_a=3
         C   1     1     1

A: θ_b(x_b)=1/2；θ_a(x_a)=2/3；θ_a(x_b)=1/3；θ_b(x_a)=1
   EC=(2/3)/(1/2)=4/3；TC=sqrt((1/2)/(1/3)·(1)/(2/3))=1.5；TFP=2
B: θ_b=1；θ_a=1；θ_a(x_b)=2/3；θ_b(x_a)=3/2
   EC=1；TC=sqrt(1/(2/3)·(3/2)/1)=1.5；TFP=1.5
C: θ_b=1/2；θ_a=1/3；θ_a(x_b)=1/3；θ_b(x_a)=1/2
   EC=2/3；TC=sqrt((1/2)/(1/3)·(1/2)/(1/3))=1.5；TFP=1

即总变化 A=2、B=1.5、C=1。前沿整体从 e=2 外移到 e=3，TC 三者均为 1.5。
"""
import math

import pytest

from src.services.productivity import compare_periods

INPUTS = ['staff_hours']
OUTPUTS = ['visits']


def record(observation_id, code, x, y):
    return {'observation_id': observation_id, 'venue_code': code, 'venue_name': code,
            'staff_hours': x, 'energy_cost': 1, 'visits': y, 'programs': 0}


def hand_before():
    return [record(1, 'A', 1, 1), record(2, 'B', 1, 2), record(3, 'C', 1, 1)]


def hand_after():
    return [record(4, 'A', 1, 2), record(5, 'B', 1, 3), record(6, 'C', 1, 1)]


def test_hand_computable_decomposition():
    result = compare_periods(hand_before(), hand_after(), INPUTS, OUTPUTS)
    pairs = {p['venue_code']: p for p in result['pairs']}
    assert set(pairs) == {'A', 'B', 'C'}
    expected = {'A': (4 / 3, 1.5, 2.0), 'B': (1.0, 1.5, 1.5), 'C': (2 / 3, 1.5, 1.0)}
    scores = {
        'A': {'own_before': .5, 'own_after': 2 / 3, 'before_against_after': 1 / 3, 'after_against_before': 1.},
        'B': {'own_before': 1., 'own_after': 1., 'before_against_after': 2 / 3, 'after_against_before': 1.5},
        'C': {'own_before': .5, 'own_after': 1 / 3, 'before_against_after': 1 / 3, 'after_against_before': .5},
    }
    for code, (catch_up, frontier_shift, total) in expected.items():
        pair = pairs[code]
        assert pair['status'] == 'comparable', pair['reason']
        assert pair['catch_up'] == pytest.approx(catch_up, abs=1e-8)
        assert pair['frontier_shift'] == pytest.approx(frontier_shift, abs=1e-8)
        assert pair['total_change'] == pytest.approx(total, abs=1e-8)
        assert pair['total_change'] == pytest.approx(pair['catch_up'] * pair['frontier_shift'])
        for key, theta in scores[code].items():
            assert pair['scores'][key]['theta'] == pytest.approx(theta, abs=1e-8)
    assert result['summary']['paired_count'] == 3
    assert result['summary']['comparable_count'] == 3
    assert result['summary']['improved_count'] == 2
    assert result['summary']['unchanged_count'] == 1
    assert result['summary']['regressed_count'] == 0
    assert result['summary']['geometric_mean_total_change'] == pytest.approx((2 * 1.5 * 1) ** (1 / 3), abs=1e-8)


def test_frontier_regression_with_unchanged_catch_up():
    """标杆整体退步 0.8；A 的相对位置不变，EC=1，但 TC=0.8，TFP=0.8。"""
    before = [record(1, 'A', 1, .9), record(2, 'B', 1, 1.), record(3, 'C', 1, 1.)]
    after = [record(4, 'A', 1, .72), record(5, 'B', 1, .8), record(6, 'C', 1, .8)]
    result = compare_periods(before, after, INPUTS, OUTPUTS)
    pairs = {p['venue_code']: p for p in result['pairs']}
    a = pairs['A']
    assert a['scores']['own_before']['theta'] == pytest.approx(.9)
    assert a['scores']['own_after']['theta'] == pytest.approx(.9)
    assert a['scores']['before_against_after']['theta'] == pytest.approx(1.125)
    assert a['scores']['after_against_before']['theta'] == pytest.approx(.72)
    assert a['catch_up'] == pytest.approx(1.)
    assert a['frontier_shift'] == pytest.approx(.8, abs=1e-8)
    assert a['total_change'] == pytest.approx(.8, abs=1e-8)
    assert a['direction'] == 'regressed'
    assert pairs['B']['frontier_shift'] == pytest.approx(.8, abs=1e-8)


def test_unit_scaling_invariance():
    before, after = hand_before(), hand_after()
    base = compare_periods(before, after, INPUTS, OUTPUTS)
    scaled = compare_periods(
        [{**r, 'staff_hours': r['staff_hours'] * 1000, 'visits': r['visits'] * 3} for r in before],
        [{**r, 'staff_hours': r['staff_hours'] * 1000, 'visits': r['visits'] * 3} for r in after],
        INPUTS, OUTPUTS,
    )
    for left, right in zip(base['pairs'], scaled['pairs']):
        assert left['catch_up'] == pytest.approx(right['catch_up'], abs=1e-8)
        assert left['frontier_shift'] == pytest.approx(right['frontier_shift'], abs=1e-8)
        assert left['total_change'] == pytest.approx(right['total_change'], abs=1e-8)


def test_missing_venue_is_listed_not_paired():
    result = compare_periods([record(1, 'A', 1, 1), record(2, 'C', 1, 1)], hand_after(), INPUTS, OUTPUTS)
    assert [p['venue_code'] for p in result['pairs']] == ['A', 'C']
    assert [r['venue_code'] for r in result['only_after']] == ['B']
    assert result['summary']['paired_count'] == 2
    assert result['summary']['only_after_count'] == 1
    assert result['only_after'][0]['visits'] == 3
    assert result['only_after'][0]['venue_name'] == 'B'


def test_zero_output_is_not_comparable_not_zero():
    before = [record(1, 'A', 1, 1), record(2, 'B', 1, 0), record(3, 'C', 1, 1)]
    result = compare_periods(before, hand_after(), INPUTS, OUTPUTS)
    b = next(p for p in result['pairs'] if p['venue_code'] == 'B')
    assert b['status'] == 'not_comparable'
    assert b['catch_up'] is None and b['frontier_shift'] is None and b['total_change'] is None
    assert b['direction'] == 'unavailable'
    assert '产出为零' in b['reason']
    assert b['scores']['own_before']['theta'] == 0
    assert result['summary']['not_comparable_count'] == 1
    assert all(p['total_change'] is not None for p in result['pairs'] if p['venue_code'] != 'B')


def test_infeasible_cross_reference_is_not_comparable(monkeypatch):
    """交叉参照不可行时整对标记无法比较，不强行填比值。"""
    import src.services.productivity as productivity
    real = productivity.solve_dmu
    calls = {'n': 0}

    def fake(x0, y0, x_ref, y_ref, input_scale=None, output_scale=None):
        calls['n'] += 1
        if calls['n'] == 4:  # 第一对场馆的 after_against_before 交叉求解
            return {'status': 'infeasible', 'theta': None, 'message': 'infeasible', 'zero_output': False}
        return real(x0, y0, x_ref, y_ref, input_scale, output_scale)

    monkeypatch.setattr(productivity, 'solve_dmu', fake)
    result = compare_periods(hand_before(), hand_after(), INPUTS, OUTPUTS)
    a = result['pairs'][0]
    assert a['status'] == 'not_comparable'
    assert a['total_change'] is None
    assert '不可行' in a['reason']


def test_solver_failure_other_than_infeasible(monkeypatch):
    import src.services.productivity as productivity
    real = productivity.solve_dmu

    def fake(x0, y0, x_ref, y_ref, input_scale=None, output_scale=None):
        solution = real(x0, y0, x_ref, y_ref, input_scale, output_scale)
        solution['status'] = 'numerical_error'
        solution['theta'] = None
        return solution

    monkeypatch.setattr(productivity, 'solve_dmu', fake)
    result = compare_periods(hand_before(), hand_after(), INPUTS, OUTPUTS)
    assert all(p['status'] == 'not_comparable' for p in result['pairs'])
    assert result['summary']['comparable_count'] == 0
    assert all('求解状态为 numerical_error' in p['reason'] for p in result['pairs'])


def test_duplicate_code_and_empty_period_rejected():
    with pytest.raises(ValueError, match='重复场馆编号'):
        compare_periods([record(1, 'A', 1, 1), record(2, 'A', 1, 2)], hand_after(), INPUTS, OUTPUTS)
    with pytest.raises(ValueError, match='没有观察'):
        compare_periods([], hand_after(), INPUTS, OUTPUTS)
    with pytest.raises(ValueError, match='必须为正有限值'):
        compare_periods([record(1, 'A', 0, 1), record(2, 'B', 1, 2)], hand_after(), INPUTS, OUTPUTS)


def test_fingerprint_changes_with_sample_and_keeps_original_sample():
    first = compare_periods(hand_before(), hand_after(), INPUTS, OUTPUTS)
    altered = hand_before()
    altered[1] = {**altered[1], 'visits': 2.5}
    second = compare_periods(altered, hand_after(), INPUTS, OUTPUTS)
    assert first['fingerprint'] != second['fingerprint']
    assert first['sample']['before'] != second['sample']['before']
    assert first['sample']['before'][1]['visits'] == 2
    assert second['sample']['before'][1]['visits'] == 2.5
    assert first['sample']['before'] == sorted(hand_before(), key=lambda r: r['venue_code'])
