from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.patient import (
    PatientCreate, PatientUpdate, PatientResponse, PatientListResponse,
    VisitCreate, VisitResponse, VisitMergeRequest, TimelineResponse,
)
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["患者档案管理"])


@router.post("", response_model=PatientResponse, summary="创建患者档案")
def create_patient(
    patient_in: PatientCreate,
    db: Session = Depends(get_db),
):
    existing = PatientService.get_patient_by_no(db, patient_in.patient_no)
    if existing:
        raise HTTPException(status_code=400, detail=f"患者编号 {patient_in.patient_no} 已存在")
    return PatientService.create_patient(db, patient_in)


@router.get("/{patient_id}", response_model=PatientResponse, summary="获取患者详情")
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return patient


@router.get("", response_model=PatientListResponse, summary="查询患者列表")
def list_patients(
    keyword: Optional[str] = Query(None, description="姓名/编号/身份证/手机号搜索"),
    department: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    total, items = PatientService.list_patients(db, keyword, department, skip, limit)
    return {"total": total, "items": items}


@router.put("/{patient_id}", response_model=PatientResponse, summary="更新患者信息")
def update_patient(
    patient_id: int,
    patient_in: PatientUpdate,
    db: Session = Depends(get_db),
):
    patient = PatientService.update_patient(db, patient_id, patient_in)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return patient


@router.post("/visits", response_model=VisitResponse, summary="登记就诊记录")
def add_visit(visit_in: VisitCreate, db: Session = Depends(get_db)):
    patient = PatientService.get_patient(db, visit_in.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return PatientService.add_visit(db, visit_in)


@router.get("/{patient_id}/visits", response_model=list[VisitResponse], summary="查询就诊记录")
def list_visits(patient_id: int, db: Session = Depends(get_db)):
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return PatientService.list_visits(db, patient_id)


@router.post("/visits/merge", summary="合并就诊记录")
def merge_visits(merge_in: VisitMergeRequest, db: Session = Depends(get_db)):
    try:
        result = PatientService.merge_visits(db, merge_in)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{patient_id}/timeline", response_model=TimelineResponse, summary="查询患者时间线")
def get_timeline(
    patient_id: int,
    limit: int = Query(200, ge=10, le=500),
    db: Session = Depends(get_db),
):
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    events = PatientService.get_timeline(db, patient_id, limit)
    return {"patient_id": patient_id, "events": events}
