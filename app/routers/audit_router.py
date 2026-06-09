from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.audit import (
    AuditQueryRequest, AuditLogListResponse,
    UsageStatsRequest, UsageStatsResponse, DashboardStatsResponse,
)
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["审计统计"])


@router.post("/logs/query", response_model=AuditLogListResponse, summary="查询调用日志")
def query_logs(req: AuditQueryRequest, db: Session = Depends(get_db)):
    total, items = AuditService.query_logs(db, req)
    return {"total": total, "items": items}


@router.get("/logs", response_model=AuditLogListResponse, summary="简单查询日志")
def get_logs(
    module: Optional[str] = None,
    action: Optional[str] = None,
    patient_id: Optional[int] = None,
    doctor_id: Optional[str] = None,
    department: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    req = AuditQueryRequest(
        module=module, action=action, patient_id=patient_id,
        doctor_id=doctor_id, department=department,
        start_date=start_date, end_date=end_date,
        page=page, page_size=page_size,
    )
    total, items = AuditService.query_logs(db, req)
    return {"total": total, "items": items}


@router.post("/stats/aggregate-daily", summary="触发每日统计聚合")
def aggregate_daily(db: Session = Depends(get_db)):
    count = AuditService.aggregate_daily_stats(db)
    return {"aggregated_records": count, "status": "ok"}


@router.post("/stats/usage", response_model=UsageStatsResponse, summary="查询使用量统计")
def get_usage_stats(req: UsageStatsRequest, db: Session = Depends(get_db)):
    return AuditService.get_usage_stats(db, req)


@router.get("/dashboard", response_model=DashboardStatsResponse, summary="科室/模块使用看板")
def get_dashboard(
    days: int = Query(30, ge=1, le=365, description="统计天数范围"),
    db: Session = Depends(get_db),
):
    return AuditService.get_dashboard_stats(db, days)
