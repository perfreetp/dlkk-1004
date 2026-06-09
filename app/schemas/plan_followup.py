from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CarePlanBase(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    plan_type: str = Field(..., max_length=50)
    plan_date: Optional[datetime] = None
    status: Optional[str] = Field("draft", max_length=20)
    exam_suggestions: Optional[List[Dict[str, Any]]] = None
    medication_checklist: Optional[List[Dict[str, Any]]] = None
    treatment_notes: Optional[str] = None
    lifestyle_recommendations: Optional[str] = None
    dietary_recommendations: Optional[str] = None
    exercise_recommendations: Optional[str] = None
    risk_assessment_summary: Optional[Dict[str, Any]] = None
    evidence_risk_ids: Optional[List[int]] = None
    evidence_abnormal_lab_ids: Optional[List[int]] = None
    evidence_active_med_ids: Optional[List[int]] = None
    evidence_unresolved_alert_ids: Optional[List[int]] = None
    evidence_summary: Optional[Dict[str, Any]] = None
    author_id: Optional[str] = Field(None, max_length=50)
    reviewer_id: Optional[str] = Field(None, max_length=50)


class CarePlanCreate(CarePlanBase):
    pass


class CarePlanUpdate(BaseModel):
    status: Optional[str] = None
    exam_suggestions: Optional[List[Dict[str, Any]]] = None
    medication_checklist: Optional[List[Dict[str, Any]]] = None
    treatment_notes: Optional[str] = None
    lifestyle_recommendations: Optional[str] = None
    dietary_recommendations: Optional[str] = None
    exercise_recommendations: Optional[str] = None
    reviewer_id: Optional[str] = None


class CarePlanGenerateRequest(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    plan_type: str = Field("comprehensive", max_length=50)
    include_risk_assessment: Optional[bool] = True
    include_medication_check: Optional[bool] = True
    author_id: Optional[str] = None


class CarePlanResponse(CarePlanBase):
    id: int
    review_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    evidence_details: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class FollowUpBase(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    follow_up_type: str = Field(..., max_length=50)
    scheduled_date: datetime
    purpose: Optional[str] = None
    assigned_doctor_id: Optional[str] = Field(None, max_length=50)


class FollowUpCreate(FollowUpBase):
    pass


class FollowUpRecordUpdate(BaseModel):
    actual_date: Optional[datetime] = None
    status: Optional[str] = None
    symptoms_recorded: Optional[Dict[str, Any]] = None
    symptom_severity: Optional[str] = None
    weight: Optional[float] = None
    blood_pressure: Optional[str] = None
    heart_rate: Optional[float] = None
    medication_adherence: Optional[str] = None
    adverse_events: Optional[str] = None
    examination_findings: Optional[str] = None
    next_scheduled_date: Optional[datetime] = None
    notes: Optional[str] = None


class FollowUpReminderRequest(BaseModel):
    follow_up_ids: Optional[List[int]] = None
    reminder_method: Optional[str] = "system"
    days_before: Optional[int] = 3


class FollowUpResponse(FollowUpBase):
    id: int
    status: str
    actual_date: Optional[datetime]
    symptoms_recorded: Optional[Dict[str, Any]]
    symptom_severity: Optional[str]
    weight: Optional[float]
    blood_pressure: Optional[str]
    heart_rate: Optional[float]
    medication_adherence: Optional[str]
    adverse_events: Optional[str]
    examination_findings: Optional[str]
    next_scheduled_date: Optional[datetime]
    notes: Optional[str]
    reminder_sent: bool
    reminder_time: Optional[datetime]
    reminder_method: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FollowUpListResponse(BaseModel):
    total: int
    scheduled_count: int
    completed_count: int
    overdue_count: int
    items: List[FollowUpResponse]


class CarePlanToFollowUpRequest(BaseModel):
    scheduled_date: Optional[datetime] = None
    follow_up_type: Optional[str] = "clinic"
    purpose: Optional[str] = None
    assigned_doctor_id: Optional[str] = None
    days_after: Optional[int] = 14
    from_exam_index: Optional[int] = Field(None, description="从exam_suggestions数组中取第几个建议，不传默认第一个含'复诊/复查'的")


class AuditStatisticsResponse(BaseModel):
    period_days: int = 30
    alerts: Dict[str, Any] = {}
    follow_ups: Dict[str, Any] = {}
    care_plans: Dict[str, Any] = {}


class ReminderResult(BaseModel):
    follow_up_id: int
    patient_id: int
    scheduled_date: datetime
    reminder_sent: bool
    message: str
