from sqlalchemy import ForeignKey,String,JSON,DateTime
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime
from src.config.database import Base
class PeriodComparison(Base):
    __tablename__='period_comparisons'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(160),unique=True)
    before_benchmark_id:Mapped[int]=mapped_column(ForeignKey('benchmark_sets.id'))
    after_benchmark_id:Mapped[int]=mapped_column(ForeignKey('benchmark_sets.id'))
    inputs:Mapped[list]=mapped_column(JSON)
    outputs:Mapped[list]=mapped_column(JSON)
    status:Mapped[str]=mapped_column(String(20),default='queued')
    result:Mapped[dict]=mapped_column(JSON,default=dict)
    error:Mapped[str]=mapped_column(String(600),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
