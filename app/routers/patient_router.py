from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Body
from sqlalchemy.orm import Session
from app.database import get_db
from datetime import datetime
from app.schemas.patient import (
    PatientCreate, PatientUpdate, PatientResponse, PatientListResponse,
    VisitCreate, VisitResponse, VisitMergeRequest, TimelineResponse,
    TimelineRequest, VisitCompareResponse,
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


@router.get("/{patient_id}/timeline", response_model=TimelineResponse, summary="查询患者时间线（GET简单查询）")
def get_timeline(
    patient_id: int,
    event_types: Optional[str] = Query(None, description="逗号分隔，如 lab,medication,alert"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    visit_id: Optional[int] = Query(None),
    visit_no: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    include_groups: bool = Query(True, description="是否返回按就诊分组视图"),
    db: Session = Depends(get_db),
):
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    et_list = [t.strip() for t in event_types.split(",")] if event_types else None
    result = PatientService.get_timeline(
        db, patient_id, et_list, start_time, end_time,
        visit_id, visit_no, page, page_size, include_groups
    )
    return {"patient_id": patient_id, **result}


@router.post("/{patient_id}/timeline/query", response_model=TimelineResponse, summary="查询患者时间线（POST复杂查询）")
def query_timeline(
    patient_id: int,
    req: TimelineRequest = Body(...),
    include_groups: bool = Query(True, description="是否返回按就诊分组视图"),
    db: Session = Depends(get_db),
):
    patient = PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    req_pid = req.patient_id
    if req_pid is not None and req_pid != patient_id:
        raise HTTPException(status_code=400, detail="路径patient_id与请求体不一致")
    result = PatientService.get_timeline(
        db, patient_id, req.event_types, req.start_time, req.end_time,
        req.visit_id, req.visit_no, req.page, req.page_size, include_groups
    )
    return {"patient_id": patient_id, **result}


@router.get("/{patient_id}/visits/compare", response_model=VisitCompareResponse, summary="两次就诊指标对比视图")
def compare_visits(
    patient_id: int,
    visit_id1: Optional[int] = Query(None, description="就诊1 ID"),
    visit_id2: Optional[int] = Query(None, description="就诊2 ID"),
    visit_id_1: Optional[int] = Query(None, description="就诊1 ID (下划线格式)"),
    visit_id_2: Optional[int] = Query(None, description="就诊2 ID (下划线格式)"),
    db: Session = Depends(get_db),
):
    v1 = visit_id1 if visit_id1 is not None else visit_id_1
    v2 = visit_id2 if visit_id2 is not None else visit_id_2
    if v1 is None or v2 is None:
        raise HTTPException(status_code=422, detail="visit_id1/visit_id_1 和 visit_id2/visit_id_2 必须提供")
    try:
        result = PatientService.compare_visits(db, patient_id, v1, v2)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
