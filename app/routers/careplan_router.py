from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.plan_followup import (
    CarePlanCreate, CarePlanUpdate, CarePlanGenerateRequest, CarePlanResponse,
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
    return plan


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
