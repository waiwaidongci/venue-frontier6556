from sqlalchemy import select
from src.services.comparison_service import list_comparisons, create_comparison, get_comparison, execute_comparison
from src.models import PeriodComparison
from src.constants.enums import RunStatus

def resume_comparisons(db):
    """跨期比较是纯确定性计算：未完成的档案在服务恢复时按排队顺序续算。"""
    for item in db.scalars(select(PeriodComparison).where(PeriodComparison.status.in_([RunStatus.QUEUED,RunStatus.RUNNING])).order_by(PeriodComparison.id)).all():
        execute_comparison(db,item.id)
