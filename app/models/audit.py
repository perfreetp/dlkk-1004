from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(50), index=True)
    endpoint = Column(String(200))
    method = Column(String(10))
    module = Column(String(50))
    action = Column(String(50))
    patient_id = Column(Integer, index=True)
    doctor_id = Column(String(50), index=True)
    department = Column(String(50))
    request_params = Column(JSON)
    response_code = Column(Integer)
    response_summary = Column(String(255))
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    latency_ms = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)


class UsageStats(Base):
    __tablename__ = "usage_stats"

    id = Column(Integer, primary_key=True, index=True)
    stat_date = Column(DateTime, index=True, nullable=False)
    department = Column(String(50), index=True)
    module = Column(String(50), index=True, nullable=False)
    action = Column(String(50), index=True)
    call_count = Column(Integer, default=0)
    patient_count = Column(Integer, default=0)
    doctor_count = Column(Integer, default=0)
    avg_latency_ms = Column(Integer)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
