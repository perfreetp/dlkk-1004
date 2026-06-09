from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel as _BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.plan_followup import (
    FollowUpCreate, FollowUpRecordUpdate, FollowUpReminderRequest,
    FollowUpResponse, FollowUpListResponse, ReminderResult,
)
from app.services.followup_service import FollowUpService

router = APIRouter(prefix="/follow-ups", tags=["随访管理"])


class AutoScheduleRequest(_BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    risks: Optional[Dict[str, str]] = None
    scenarios: Optional[List[str]] = None
    assigned_doctor_id: Optional[str] = None


@router.post("", response_model=FollowUpResponse, summary="安排随访")
def create_follow_up(fu_in: FollowUpCreate, db: Session = Depends(get_db)):
    return FollowUpService.create_follow_up(db, fu_in)


@router.post("/auto-schedule", response_model=List[FollowUpResponse], summary="基于风险自动排期随访")
def auto_schedule(
    req: AutoScheduleRequest,
    db: Session = Depends(get_db),
):
    risks = req.risks or {}
    scenarios = req.scenarios or []
    return FollowUpService.auto_schedule(db, req.patient_id, req.visit_id, risks, scenarios, req.assigned_doctor_id)


@router.get("/{fu_id}", response_model=FollowUpResponse, summary="获取随访详情")
def get_follow_up(fu_id: int, db: Session = Depends(get_db)):
    fu = FollowUpService.get_follow_up(db, fu_id)
    if not fu:
        raise HTTPException(status_code=404, detail="随访不存在")
    return fu


@router.get("", response_model=FollowUpListResponse, summary="查询随访列表")
def list_follow_ups(
    patient_id: Optional[int] = None,
    status: Optional[str] = Query(None, description="scheduled/completed/overdue/cancelled"),
    doctor_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    total, scheduled, completed, overdue, items = FollowUpService.list_follow_ups(
        db, patient_id, status, doctor_id, start_date, end_date, skip, limit
    )
    return {
        "total": total,
        "scheduled_count": scheduled,
        "completed_count": completed,
        "overdue_count": overdue,
        "items": items,
    }


@router.patch("/{fu_id}/record", response_model=FollowUpResponse, summary="记录随访结果/症状变化")
def record_follow_up(
    fu_id: int,
    update_in: FollowUpRecordUpdate,
    db: Session = Depends(get_db),
):
    fu = FollowUpService.record_follow_up(db, fu_id, update_in)
    if not fu:
        raise HTTPException(status_code=404, detail="随访不存在")
    return fu


@router.get("/{patient_id}/symptom-trend", response_model=List[Dict[str, Any]], summary="查询患者症状变化趋势")
def get_symptom_trend(
    patient_id: int,
    limit: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
):
    return FollowUpService.get_symptom_trend(db, patient_id, limit)


@router.post("/send-reminders", response_model=List[ReminderResult], summary="批量推送复诊提醒")
def send_reminders(req: FollowUpReminderRequest, db: Session = Depends(get_db)):
    return FollowUpService.send_reminders(db, req)


@router.get("/schedule/rules", summary="获取随访排期规则")
def get_schedule_rules():
    return {
        "rules": FollowUpService.FOLLOWUP_TYPE_SCHEDULE,
        "severity_scores": FollowUpService.SYMPTOM_SEVERITY_SCORES,
    }
