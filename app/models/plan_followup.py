from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class CarePlan(Base):
    __tablename__ = "care_plans"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    plan_type = Column(String(50), nullable=False)
    plan_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="draft")
    exam_suggestions = Column(JSON)
    medication_checklist = Column(JSON)
    treatment_notes = Column(Text)
    lifestyle_recommendations = Column(Text)
    dietary_recommendations = Column(Text)
    exercise_recommendations = Column(Text)
    risk_assessment_summary = Column(JSON)
    evidence_risk_ids = Column(JSON)
    evidence_abnormal_lab_ids = Column(JSON)
    evidence_active_med_ids = Column(JSON)
    evidence_unresolved_alert_ids = Column(JSON)
    evidence_summary = Column(JSON)
    author_id = Column(String(50))
    reviewer_id = Column(String(50))
    review_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="care_plans")


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    follow_up_type = Column(String(50), nullable=False)
    scheduled_date = Column(DateTime, nullable=False)
    actual_date = Column(DateTime)
    status = Column(String(20), default="scheduled")
    purpose = Column(Text)
    symptoms_recorded = Column(JSON)
    symptom_severity = Column(String(20))
    weight = Column(Float)
    blood_pressure = Column(String(30))
    heart_rate = Column(Float)
    medication_adherence = Column(String(50))
    adverse_events = Column(Text)
    examination_findings = Column(Text)
    next_scheduled_date = Column(DateTime)
    notes = Column(Text)
    reminder_sent = Column(Boolean, default=False)
    reminder_time = Column(DateTime)
    reminder_method = Column(String(50))
    assigned_doctor_id = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="follow_ups")
