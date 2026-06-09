from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RiskAssessmentRequest(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    assessment_type: str = Field(..., max_length=50)
    input_data: Dict[str, Any]


class RiskAssessmentBase(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    assessment_type: str = Field(..., max_length=50)
    assessment_date: Optional[datetime] = None
    risk_level: str = Field(..., max_length=20)
    risk_score: Optional[float] = None
    score_details: Optional[Dict[str, Any]] = None
    input_data: Optional[Dict[str, Any]] = None
    recommendations: Optional[str] = None
    algorithm_version: Optional[str] = Field(None, max_length=20)
    assessor: Optional[str] = Field(None, max_length=50)


class RiskAssessmentCreate(RiskAssessmentBase):
    pass


class RiskAssessmentResponse(RiskAssessmentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RiskBatchCalculateRequest(BaseModel):
    patient_ids: List[int]
    assessment_types: List[str]


class RiskResultSummary(BaseModel):
    patient_id: int
    assessment_type: str
    risk_level: str
    risk_score: Optional[float] = None


class AlertBase(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    alert_type: str = Field(..., max_length=50)
    alert_level: str = Field(..., max_length=20)
    alert_time: Optional[datetime] = None
    title: str = Field(..., max_length=200)
    content: Optional[str] = None
    related_record_type: Optional[str] = Field(None, max_length=50)
    related_record_id: Optional[int] = None


class AlertCreate(AlertBase):
    pass


class AlertUpdate(BaseModel):
    is_read: Optional[bool] = None
    read_by: Optional[str] = None
    is_resolved: Optional[bool] = None
    resolve_note: Optional[str] = None


class AlertResponse(AlertBase):
    id: int
    is_read: bool
    read_time: Optional[datetime]
    read_by: Optional[str]
    is_resolved: bool
    resolve_time: Optional[datetime]
    resolve_note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    total: int
    unread_count: int
    critical_count: int
    items: List[AlertResponse]
