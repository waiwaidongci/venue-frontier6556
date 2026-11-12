"""档案建立与验证：前后期不同季度、按时间顺序、名称唯一。"""
import pytest
from fastapi import HTTPException

from src.schemas.comparison import ComparisonInput
from src.services import comparison_service


class FakeDb:
    def __init__(self, benchmarks, duplicate_name=False):
        self.benchmarks = benchmarks
        self.duplicate_name = duplicate_name
        self.added = None

    def get(self, model, id):
        return self.benchmarks.get(id)

    def scalar(self, statement):
        return object() if self.duplicate_name else None

    def add(self, item):
        self.added = item

    def commit(self):
        pass


def make_input(name='跨期比较', before=1, after=2):
    return ComparisonInput(name=name, before_benchmark_id=before, after_benchmark_id=after,
                           inputs=['staff_hours'], outputs=['visits'])


def test_same_period_rejected():
    with pytest.raises(ValueError):
        ComparisonInput(name='同季', before_benchmark_id=1, after_benchmark_id=1)


def test_service_rejects_same_period_and_reverse_order(monkeypatch):
    class B:
        def __init__(self, id, period):
            self.id, self.period, self.code, self.name, self.source_file = id, period, f'B{id}', f'B{id}', 'x.csv'

    benchmarks = {1: B(1, '2026Q3'), 2: B(2, '2026Q2')}
    monkeypatch.setattr(comparison_service, 'BenchmarkSet', type('M', (), {}))
    db = FakeDb(benchmarks)
    monkeypatch.setattr(db, 'get', lambda model, id: benchmarks.get(id), raising=True)
    # 后期早于前期：按 id 顺序判定
    with pytest.raises(HTTPException) as exc:
        comparison_service.create_comparison(db, make_input(before=2, after=1))
    assert exc.value.status_code == 422
    assert '时间顺序' in exc.value.detail


def test_service_rejects_same_period_label(monkeypatch):
    class B:
        def __init__(self, id, period):
            self.id, self.period, self.code, self.name, self.source_file = id, period, f'B{id}', f'B{id}', 'x.csv'

    benchmarks = {1: B(1, '2026Q2'), 3: B(3, '2026Q2')}
    db = FakeDb(benchmarks)
    monkeypatch.setattr(db, 'get', lambda model, id: benchmarks.get(id), raising=True)
    with pytest.raises(HTTPException) as exc:
        comparison_service.create_comparison(db, make_input(before=1, after=3))
    assert exc.value.status_code == 422
    assert '不同季度' in exc.value.detail


def test_duplicate_name_rejected(monkeypatch):
    class B:
        def __init__(self, id, period):
            self.id, self.period, self.code, self.name, self.source_file = id, period, f'B{id}', f'B{id}', 'x.csv'

    benchmarks = {1: B(1, '2026Q2'), 2: B(2, '2026Q3')}
    db = FakeDb(benchmarks, duplicate_name=True)
    monkeypatch.setattr(db, 'get', lambda model, id: benchmarks.get(id), raising=True)
    with pytest.raises(HTTPException) as exc:
        comparison_service.create_comparison(db, make_input())
    assert exc.value.status_code == 409
