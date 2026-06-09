from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.plan_followup import (
    CarePlanCreate, CarePlanUpdate, CarePlanGenerateRequest, CarePlanResponse,
    CarePlanToFollowUpRequest, AuditStatisticsResponse, FollowUpResponse,
)
from app.services.care_plan_service import CarePlanService

router = APIRouter(prefix="/care-plans", tags=["方案草稿"])


@router.post("/generate", response_model=CarePlanResponse, summary="智能生成诊疗方案草稿")
def generate_care_plan(
    req: CarePlanGenerateRequest,
    db: Session = Depends(get_db),
):
    plan = CarePlanService.generate_care_plan(db, req)
    return plan


@router.post("", response_model=CarePlanResponse, summary="手工创建方案")
def create_care_plan(plan_in: CarePlanCreate, db: Session = Depends(get_db)):
    return CarePlanService.create_care_plan(db, plan_in)


@router.get("/{plan_id}", response_model=CarePlanResponse, summary="获取方案详情")
def get_care_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = CarePlanService.get_care_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="方案不存在")
    resp = CarePlanResponse.model_validate(plan)
    if plan.evidence_summary:
        resp.evidence_details = plan.evidence_summary
    return resp


@router.put("/{plan_id}", response_model=CarePlanResponse, summary="更新方案草稿")
def update_care_plan(
    plan_id: int,
    plan_in: CarePlanUpdate,
    x_doctor_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if plan_in.status in ["reviewed", "approved"] and plan_in.reviewer_id is None:
        plan_in.reviewer_id = x_doctor_id
    plan = CarePlanService.update_care_plan(db, plan_id, plan_in)
    if not plan:
        raise HTTPException(status_code=404, detail="方案不存在")
    return plan


@router.get("/patient/{patient_id}", response_model=List[CarePlanResponse], summary="查询患者方案列表")
def list_care_plans(
    patient_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return CarePlanService.list_care_plans(db, patient_id, limit)


@router.get("/templates/exam-suggestions", summary="获取检查建议模板库")
def get_exam_templates():
    return {
        "templates": CarePlanService.EXAM_RULES,
    }


@router.get("/templates/medication-checklist", summary="获取用药核对清单模板")
def get_medication_templates():
    return {
        "drug_classes": CarePlanService.DRUG_CLASS_CHECKLIST,
    }


@router.post("/{plan_id}/follow-up-convert", response_model=FollowUpResponse, summary="方案复诊建议一键转随访计划")
def convert_plan_to_follow_up(
    plan_id: int,
    req: CarePlanToFollowUpRequest = Body(...),
    db: Session = Depends(get_db),
):
    try:
        fu = CarePlanService.convert_plan_to_follow_up(db, plan_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return fu


@router.get("/audit/statistics", response_model=AuditStatisticsResponse, summary="诊疗闭环审计统计（提醒处理率/随访完成率）")
def get_audit_statistics(
    period_days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    return CarePlanService.get_audit_statistics(db, period_days)
