from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Date, Float, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_no = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=False)
    birth_date = Column(Date, nullable=False)
    id_card = Column(String(18), unique=True, index=True)
    phone = Column(String(20))
    address = Column(String(255))
    blood_type = Column(String(5))
    height = Column(Float)
    weight = Column(Float)
    smoking = Column(Boolean, default=False)
    drinking = Column(Boolean, default=False)
    family_history = Column(Text)
    allergy_history = Column(Text)
    past_medical_history = Column(Text)
    department = Column(String(50))
    doctor_id = Column(String(50))
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    visits = relationship("Visit", back_populates="patient", cascade="all, delete-orphan")
    vital_signs = relationship("VitalSign", back_populates="patient", cascade="all, delete-orphan")
    ecg_records = relationship("ECGRecord", back_populates="patient", cascade="all, delete-orphan")
    lab_records = relationship("LabRecord", back_populates="patient", cascade="all, delete-orphan")
    medications = relationship("MedicationRecord", back_populates="patient", cascade="all, delete-orphan")
    risk_assessments = relationship("RiskAssessment", back_populates="patient", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="patient", cascade="all, delete-orphan")
    care_plans = relationship("CarePlan", back_populates="patient", cascade="all, delete-orphan")
    follow_ups = relationship("FollowUp", back_populates="patient", cascade="all, delete-orphan")


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_no = Column(String(50), unique=True, index=True, nullable=False)
    visit_type = Column(String(20), nullable=False)
    visit_date = Column(DateTime, default=datetime.now)
    department = Column(String(50))
    doctor_id = Column(String(50))
    chief_complaint = Column(Text)
    present_illness = Column(Text)
    diagnosis = Column(JSON)
    discharge_diagnosis = Column(JSON)
    is_emergency = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    patient = relationship("Patient", back_populates="visits")
