from sqlalchemy import select
from fastapi import HTTPException
from src.models import PeriodComparison,BenchmarkSet
from src.constants.enums import RunStatus

def list_comparisons(db):return db.scalars(select(PeriodComparison).order_by(PeriodComparison.id.desc())).all()

def get_comparison(db,id):
    item=db.get(PeriodComparison,id)
    if not item:raise HTTPException(404,'跨期比较档案不存在')
    return item

def create_comparison(db,data):
    from redis import Redis
    from src.config.settings import REDIS_URL
    before=db.get(BenchmarkSet,data.before_benchmark_id);after=db.get(BenchmarkSet,data.after_benchmark_id)
    if not before or not after:raise HTTPException(404,'参照集不存在')
    if before.period==after.period:raise HTTPException(422,'前后两期必须是不同季度，不能把同一期当作前后期比较')
    if before.id>after.id:raise HTTPException(422,'请按时间顺序把较早的参照集选为前期')
    if db.scalar(select(PeriodComparison).where(PeriodComparison.name==data.name)):raise HTTPException(409,'比较名称已存在')
    item=PeriodComparison(**data.model_dump(),status=RunStatus.QUEUED);db.add(item);db.commit()
    Redis.from_url(REDIS_URL).lpush('frontier:runs',str(item.id));return item

def execute_comparison(db,id):
    from src.services.observation_service import list_observations
    from src.services.productivity import compare_periods
    item=db.get(PeriodComparison,id)
    if not item or item.status not in (RunStatus.QUEUED,RunStatus.RUNNING):return
    item.status=RunStatus.RUNNING;db.commit()
    try:
        before=db.get(BenchmarkSet,item.before_benchmark_id);after=db.get(BenchmarkSet,item.after_benchmark_id)
        result=compare_periods(list_observations(db,before.id),list_observations(db,after.id),item.inputs,item.outputs,
            {'id':before.id,'code':before.code,'name':before.name,'period':before.period,'source_file':before.source_file},
            {'id':after.id,'code':after.code,'name':after.name,'period':after.period,'source_file':after.source_file})
        item.result=result;item.status=RunStatus.COMPLETED;item.error='';db.commit()
    except Exception as exc:
        db.rollback();item=db.get(PeriodComparison,id);item.status=RunStatus.FAILED;item.error=str(exc)[:600];db.commit()

