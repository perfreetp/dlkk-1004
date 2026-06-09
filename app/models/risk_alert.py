from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    assessment_type = Column(String(50), nullable=False)
    assessment_date = Column(DateTime, default=datetime.now)
    risk_level = Column(String(20), nullable=False)
    risk_score = Column(Float)
    score_details = Column(JSON)
    input_data = Column(JSON)
    recommendations = Column(Text)
    algorithm_version = Column(String(20))
    assessor = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)

    patient = relationship("Patient", back_populates="risk_assessments")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    alert_type = Column(String(50), nullable=False)
    alert_level = Column(String(20), nullable=False)
    alert_time = Column(DateTime, default=datetime.now)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    related_record_type = Column(String(50))
    related_record_id = Column(Integer)
    is_read = Column(Boolean, default=False)
    read_time = Column(DateTime)
    read_by = Column(String(50))
    is_resolved = Column(Boolean, default=False)
    resolve_time = Column(DateTime)
    resolve_note = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    patient = relationship("Patient", back_populates="alerts")
