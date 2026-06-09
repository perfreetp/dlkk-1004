from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    id: int
    request_id: Optional[str]
    endpoint: Optional[str]
    method: Optional[str]
    module: Optional[str]
    action: Optional[str]
    patient_id: Optional[int]
    doctor_id: Optional[str]
    department: Optional[str]
    response_code: Optional[int]
    response_summary: Optional[str]
    ip_address: Optional[str]
    latency_ms: Optional[int]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogResponse]


class AuditQueryRequest(BaseModel):
    module: Optional[str] = None
    action: Optional[str] = None
    patient_id: Optional[int] = None
    doctor_id: Optional[str] = None
    department: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = 1
    page_size: int = 50


class UsageStatsRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    department: Optional[str] = None
    module: Optional[str] = None
    group_by: Optional[str] = "day"


class UsageStatsItem(BaseModel):
    period: str
    department: Optional[str] = None
    module: Optional[str] = None
    action: Optional[str] = None
    call_count: int
    patient_count: int
    doctor_count: int
    avg_latency_ms: Optional[int] = None
    error_count: int


class UsageStatsResponse(BaseModel):
    total_calls: int
    total_patients: int
    total_doctors: int
    total_errors: int
    avg_latency_ms: Optional[int]
    breakdown: List[UsageStatsItem]


class ModuleUsageItem(BaseModel):
    module: str
    module_name: str
    call_count: int
    call_percentage: float


class DepartmentUsageItem(BaseModel):
    department: str
    call_count: int
    patient_count: int
    call_percentage: float


class DashboardStatsResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_calls: int
    total_patients: int
    active_doctors: int
    avg_response_time_ms: Optional[int]
    error_rate: Optional[float]
    top_modules: List[ModuleUsageItem]
    top_departments: List[DepartmentUsageItem]
