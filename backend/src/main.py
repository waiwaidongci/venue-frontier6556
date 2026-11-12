import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from redis import Redis
from src.config.database import Base,engine
from src.config.settings import SEED_DEMO,REDIS_URL
from src import models
from src.routes import auth,benchmarks,venues,observations,runs,cases,audit,comparisons
from src.middlewares.audit import AuditMiddleware
from src.middlewares.errors import ErrorMiddleware
from src.middlewares.rate_limit import RateLimitMiddleware
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if SEED_DEMO:
        try:
            from scripts.seed_demo import seed
            seed()
        except Exception:logging.exception("seed failed; app remains available")
    try:
        from src.config.database import Session
        from src.models import PeriodComparison
        from src.controllers.comparison_controller import resume_comparisons
        with Session() as db:resume_comparisons(db)  # 纯确定性计算，恢复未完成档案
    except Exception:logging.exception("comparison resume check failed")
    yield
app=FastAPI(title="栖原场馆效率评议席",lifespan=lifespan)
app.add_middleware(AuditMiddleware);app.add_middleware(RateLimitMiddleware);app.add_middleware(ErrorMiddleware)
for mod in (auth,benchmarks,venues,observations,runs,cases,audit,comparisons):app.include_router(mod.router)
@app.get("/health")
def health():
    with engine.connect() as conn:conn.execute(text("SELECT 1"))
    Redis.from_url(REDIS_URL).ping();return {"status":"ok"}
