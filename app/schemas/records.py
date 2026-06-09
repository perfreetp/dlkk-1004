from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class VitalSignBase(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    record_time: Optional[datetime] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    heart_rate: Optional[float] = None
    respiratory_rate: Optional[float] = None
    temperature: Optional[float] = None
    oxygen_saturation: Optional[float] = None
    source: Optional[str] = Field(None, max_length=50)
    operator_id: Optional[str] = Field(None, max_length=50)
    remark: Optional[str] = None


class VitalSignCreate(VitalSignBase):
    pass


class VitalSignBatchCreate(BaseModel):
    records: List[VitalSignCreate]


class VitalSignResponse(VitalSignBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ECGRecordBase(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    record_time: Optional[datetime] = None
    ecg_type: Optional[str] = Field(None, max_length=50)
    heart_rate: Optional[float] = None
    rhythm: Optional[str] = Field(None, max_length=100)
    pr_interval: Optional[float] = None
    qrs_duration: Optional[float] = None
    qt_interval: Optional[float] = None
    qtc_interval: Optional[float] = None
    st_segment: Optional[str] = Field(None, max_length=100)
    t_wave: Optional[str] = Field(None, max_length=100)
    interpretation: Optional[str] = None
    is_abnormal: Optional[bool] = False
    abnormal_flags: Optional[List[str]] = None
    ecg_data_url: Optional[str] = Field(None, max_length=255)
    report_id: Optional[str] = Field(None, max_length=50)


class ECGRecordCreate(ECGRecordBase):
    pass


class ECGRecordResponse(ECGRecordBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class LabRecordBase(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    record_time: Optional[datetime] = None
    lab_type: Optional[str] = Field(None, max_length=50)
    test_name: str = Field(..., max_length=100)
    test_code: Optional[str] = Field(None, max_length=50)
    test_value: float
    test_unit: Optional[str] = Field(None, max_length=20)
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    is_abnormal: Optional[bool] = False
    abnormal_flag: Optional[str] = Field(None, max_length=10)
    report_id: Optional[str] = Field(None, max_length=50)
    specimen_type: Optional[str] = Field(None, max_length=50)


class LabRecordCreate(LabRecordBase):
    pass


class LabRecordBatchCreate(BaseModel):
    records: List[LabRecordCreate]


class LabRecordResponse(LabRecordBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MedicationRecordBase(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    order_time: Optional[datetime] = None
    drug_code: Optional[str] = Field(None, max_length=50)
    drug_name: str = Field(..., max_length=200)
    generic_name: Optional[str] = Field(None, max_length=200)
    drug_category: Optional[str] = Field(None, max_length=50)
    dosage: Optional[str] = Field(None, max_length=50)
    frequency: Optional[str] = Field(None, max_length=50)
    route: Optional[str] = Field(None, max_length=50)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    prescriber_id: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = True
    contraindication_flag: Optional[bool] = False
    remark: Optional[str] = None


class MedicationRecordCreate(MedicationRecordBase):
    pass


class MedicationRecordBatchCreate(BaseModel):
    records: List[MedicationRecordCreate]


class MedicationRecordResponse(MedicationRecordBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RecordStatsResponse(BaseModel):
    patient_id: int
    vital_sign_count: int
    ecg_count: int
    lab_count: int
    medication_count: int
    latest_record_time: Optional[datetime] = None
