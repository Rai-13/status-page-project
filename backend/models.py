from sqlalchemy import Column, Integer, String, DateTime, Text
from database import Base
import datetime

class CheckResult(Base):
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, index=True)
    url = Column(String)
    status = Column(String) # up, down, degraded
    response_time_ms = Column(Integer)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    error_message = Column(Text, nullable=True)
