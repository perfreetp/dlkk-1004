from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.risk_alert import (
    AlertResponse, AlertListResponse, AlertUpdate,
    AlertBatchResolveRequest, AlertBatchResolveResponse,
    VisitAlertSummaryListResponse,
)
from app.services.alert_service import AlertRuleService

router = APIRouter(prefix="/alerts", tags=["提醒规则"])


@router.get("", response_model=AlertListResponse, summary="查询提醒/警报列表")
def list_alerts(
    patient_id: Optional[int] = None,
    alert_type: Optional[str] = Query(None, description="critical_value/abnormal_value/drug_contraindication/duplicate_exam"),
    alert_level: Optional[str] = Query(None, description="critical/high/medium/low"),
    unread_only: bool = False,
    unresolved_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    total, unread, critical, items = AlertRuleService.list_alerts(
        db, patient_id, alert_type, alert_level, unread_only, unresolved_only, skip, limit
    )
    return {
        "total": total,
        "unread_count": unread,
        "critical_count": critical,
        "items": items,
    }


@router.get("/{alert_id}", response_model=AlertResponse, summary="获取单条提醒详情")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    from app.models.risk_alert import Alert
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return alert


@router.patch("/{alert_id}", response_model=AlertResponse, summary="标记提醒已读/已处理")
def update_alert(
    alert_id: int,
    update_in: AlertUpdate,
    x_doctor_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if update_in.is_read and x_doctor_id and not update_in.read_by:
        update_in.read_by = x_doctor_id
    alert = AlertRuleService.update_alert(db, alert_id, update_in)
    if not alert:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return alert


@router.post("/{alert_id}/read", response_model=AlertResponse, summary="快捷标记已读")
def mark_alert_read(
    alert_id: int,
    x_doctor_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    update = AlertUpdate(is_read=True, read_by=x_doctor_id)
    alert = AlertRuleService.update_alert(db, alert_id, update)
    if not alert:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertResponse, summary="标记已解决")
def resolve_alert(
    alert_id: int,
    resolve_note: Optional[str] = None,
    x_doctor_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    update = AlertUpdate(is_resolved=True, resolve_note=resolve_note, is_read=True, read_by=x_doctor_id)
    alert = AlertRuleService.update_alert(db, alert_id, update)
    if not alert:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return alert


@router.get("/by-visit/summary", response_model=VisitAlertSummaryListResponse, summary="按就诊维度汇总提醒")
def list_alerts_by_visit(
    patient_id: Optional[int] = Query(None),
    visit_id: Optional[int] = Query(None),
    visit_no: Optional[str] = Query(None),
    alert_types: Optional[str] = Query(None, description="提醒类型，多个用逗号分隔 critical_value,abnormal_value,drug_contraindication,duplicate_exam"),
    unresolved_only: bool = Query(False),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    types_list = [t.strip() for t in alert_types.split(",")] if alert_types else None
    return AlertRuleService.list_alerts_by_visit(
        db, patient_id, visit_id, visit_no, types_list, unresolved_only, unread_only
    )


@router.post("/batch-resolve", response_model=AlertBatchResolveResponse, summary="批量标记提醒已解决")
def batch_resolve_alerts(
    req: AlertBatchResolveRequest = Body(...),
    x_doctor_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if not req.alert_ids and not req.resolve_all_in_visit and not req.patient_id:
        raise HTTPException(status_code=400, detail="请指定alert_ids、resolve_all_in_visit+visit_id或patient_id")
    if req.resolve_all_in_visit and not req.visit_id:
        raise HTTPException(status_code=400, detail="resolve_all_in_visit需要同时指定visit_id")
    return AlertRuleService.batch_resolve_alerts(
        db, req.patient_id, req.visit_id, req.alert_ids,
        req.resolve_all_in_visit, req.resolve_note, x_doctor_id,
    )


@router.get("/rules/thresholds", summary="获取危急值阈值配置")
def get_thresholds():
    return {
        "vital_signs": AlertRuleService.CRITICAL_VS_THRESHOLDS,
        "lab_records": AlertRuleService.CRITICAL_LAB_THRESHOLDS,
        "alert_levels": {
            "critical": "红色-危急，需立即干预",
            "high": "橙色-高度关注，需尽快处理",
            "medium": "黄色-一般关注，建议评估",
            "low": "蓝色-提示信息",
        },
    }
