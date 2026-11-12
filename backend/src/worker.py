import time
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import EfficiencyRun,PeriodComparison
from src.constants.enums import RunStatus
from src.services.run_service import execute_run
from src.services.comparison_service import execute_comparison
redis=Redis.from_url(REDIS_URL)
while True:
    Path('/tmp/heartbeat').touch()
    with Session() as db:
        run=db.scalar(select(EfficiencyRun).where(EfficiencyRun.status.in_([RunStatus.QUEUED,RunStatus.RUNNING])).order_by(EfficiencyRun.id))
        if run:execute_run(db,run.id);continue
        comparison=db.scalar(select(PeriodComparison).where(PeriodComparison.status.in_([RunStatus.QUEUED,RunStatus.RUNNING])).order_by(PeriodComparison.id))
        if comparison:execute_comparison(db,comparison.id);continue
        redis.brpop('frontier:runs',timeout=2)
    time.sleep(.1)
