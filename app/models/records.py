from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class VitalSign(Base):
    __tablename__ = "vital_signs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    record_time = Column(DateTime, default=datetime.now)
    systolic_bp = Column(Float)
    diastolic_bp = Column(Float)
    heart_rate = Column(Float)
    respiratory_rate = Column(Float)
    temperature = Column(Float)
    oxygen_saturation = Column(Float)
    source = Column(String(50))
    operator_id = Column(String(50))
    remark = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    patient = relationship("Patient", back_populates="vital_signs")


class ECGRecord(Base):
    __tablename__ = "ecg_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    record_time = Column(DateTime, default=datetime.now)
    ecg_type = Column(String(50))
    heart_rate = Column(Float)
    rhythm = Column(String(100))
    pr_interval = Column(Float)
    qrs_duration = Column(Float)
    qt_interval = Column(Float)
    qtc_interval = Column(Float)
    st_segment = Column(String(100))
    t_wave = Column(String(100))
    interpretation = Column(Text)
    is_abnormal = Column(Boolean, default=False)
    abnormal_flags = Column(JSON)
    ecg_data_url = Column(String(255))
    report_id = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)

    patient = relationship("Patient", back_populates="ecg_records")


class LabRecord(Base):
    __tablename__ = "lab_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    record_time = Column(DateTime, default=datetime.now)
    lab_type = Column(String(50))
    test_name = Column(String(100))
    test_code = Column(String(50))
    test_value = Column(Float)
    test_unit = Column(String(20))
    reference_low = Column(Float)
    reference_high = Column(Float)
    is_abnormal = Column(Boolean, default=False)
    abnormal_flag = Column(String(10))
    report_id = Column(String(50))
    specimen_type = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)

    patient = relationship("Patient", back_populates="lab_records")


class MedicationRecord(Base):
    __tablename__ = "medication_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    order_time = Column(DateTime, default=datetime.now)
    drug_code = Column(String(50))
    drug_name = Column(String(200), nullable=False)
    generic_name = Column(String(200))
    drug_category = Column(String(50))
    dosage = Column(String(50))
    frequency = Column(String(50))
    route = Column(String(50))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    prescriber_id = Column(String(50))
    is_active = Column(Boolean, default=True)
    contraindication_flag = Column(Boolean, default=False)
    remark = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    patient = relationship("Patient", back_populates="medications")
