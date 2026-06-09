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
    visit_id: Optional[int] = None
    visit_no: Optional[str] = None
    status: Optional[str] = None
    level: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class TimelineVisitGroup(BaseModel):
    visit_id: int
    visit_no: str
    visit_type: str
    visit_time: datetime
    chief_complaint: Optional[str] = None
    diagnosis: Optional[List[Dict[str, Any]]] = None
    department: Optional[str] = None
    events: List[TimelineEvent]


class TimelineRequest(BaseModel):
    patient_id: Optional[int] = None
    event_types: Optional[List[str]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    visit_id: Optional[int] = None
    visit_no: Optional[str] = None
    page: int = 1
    page_size: int = 50


class TimelineResponse(BaseModel):
    patient_id: int
    total: int
    page: int
    page_size: int
    has_more: bool
    events: List[TimelineEvent]
    visit_groups: Optional[List[TimelineVisitGroup]] = None


class CompareMetric(BaseModel):
    name: str
    code: Optional[str] = None
    unit: Optional[str] = None
    v1_value: Optional[Any] = None
    v2_value: Optional[Any] = None
    change_type: str  # increased / decreased / unchanged / new / removed / continued / discontinued / dosage_changed / frequency_changed / changed
    delta: Optional[float] = None
    level: Optional[str] = None
    v1_details: Optional[Dict[str, Any]] = None
    v2_details: Optional[Dict[str, Any]] = None
    abnormal_change: Optional[str] = None  # improved / worsened / unchanged / new_abnormal / resolved_normal / unknown


class VisitCompareSummary(BaseModel):
    increased: int = 0
    decreased: int = 0
    unchanged: int = 0
    new: int = 0
    removed: int = 0
    continued: int = 0
    discontinued: int = 0  # 停用
    dosage_changed: int = 0  # 剂量变化
    frequency_changed: int = 0  # 频次变化
    changed: int = 0  # 其他变化
    improved: int = 0  # 异常→正常
    worsened: int = 0  # 正常→异常
    total: int = 0


class VisitCompareResponse(BaseModel):
    patient_id: int
    visit1_id: int
    visit2_id: int
    visit1_no: Optional[str] = None
    visit2_no: Optional[str] = None
    visit1_time: Optional[datetime] = None
    visit2_time: Optional[datetime] = None
    vital_signs: List[CompareMetric] = []
    labs: List[CompareMetric] = []
    medications: List[CompareMetric] = []
    risks: List[CompareMetric] = []
    summary: Dict[str, VisitCompareSummary] = {}
    summary_total: Optional[VisitCompareSummary] = None
