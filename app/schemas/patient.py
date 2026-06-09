from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PatientBase(BaseModel):
    patient_no: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    gender: str = Field(..., max_length=10)
    birth_date: date
    id_card: Optional[str] = Field(None, max_length=18)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=255)
    blood_type: Optional[str] = Field(None, max_length=5)
    height: Optional[float] = None
    weight: Optional[float] = None
    smoking: Optional[bool] = False
    drinking: Optional[bool] = False
    family_history: Optional[str] = None
    allergy_history: Optional[str] = None
    past_medical_history: Optional[str] = None
    department: Optional[str] = Field(None, max_length=50)
    doctor_id: Optional[str] = Field(None, max_length=50)


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    smoking: Optional[bool] = None
    drinking: Optional[bool] = None
    family_history: Optional[str] = None
    allergy_history: Optional[str] = None
    past_medical_history: Optional[str] = None
    department: Optional[str] = None
    doctor_id: Optional[str] = None
    status: Optional[str] = None


class PatientResponse(PatientBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatientListResponse(BaseModel):
    total: int
    items: List[PatientResponse]


class VisitBase(BaseModel):
    patient_id: int
    visit_no: str = Field(..., max_length=50)
    visit_type: str = Field(..., max_length=20)
    visit_date: Optional[datetime] = None
    department: Optional[str] = Field(None, max_length=50)
    doctor_id: Optional[str] = Field(None, max_length=50)
    chief_complaint: Optional[str] = None
    present_illness: Optional[str] = None
    diagnosis: Optional[List[Dict[str, Any]]] = None
    discharge_diagnosis: Optional[List[Dict[str, Any]]] = None
    is_emergency: Optional[bool] = False


class VisitCreate(VisitBase):
    pass


class VisitMergeRequest(BaseModel):
    target_patient_id: int
    source_visit_ids: List[int]
    merge_note: Optional[str] = None


class VisitResponse(VisitBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TimelineEvent(BaseModel):
    event_type: str
    event_time: datetime
    title: str
    description: str
    related_id: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None


class TimelineResponse(BaseModel):
    patient_id: int
    events: List[TimelineEvent]
