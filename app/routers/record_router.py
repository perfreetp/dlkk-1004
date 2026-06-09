from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.records import LabRecord, MedicationRecord
from app.schemas.records import (
    VitalSignCreate, VitalSignBatchCreate, VitalSignResponse,
    ECGRecordCreate, ECGRecordResponse,
    LabRecordCreate, LabRecordBatchCreate, LabRecordResponse,
    MedicationRecordCreate, MedicationRecordBatchCreate, MedicationRecordResponse,
    RecordStatsResponse,
)
from app.services.record_service import RecordService
from app.services.alert_service import AlertRuleService

router = APIRouter(prefix="/records", tags=["检查接入"])


@router.post("/vital-signs", response_model=VitalSignResponse, summary="录入生命体征(血压/心率等)")
def create_vital_sign(vs_in: VitalSignCreate, db: Session = Depends(get_db)):
    vs = RecordService.create_vital_sign(db, vs_in)
    AlertRuleService.check_vital_signs(db, vs)
    return vs


@router.post("/vital-signs/batch", response_model=List[VitalSignResponse], summary="批量录入生命体征")
def batch_create_vital_signs(batch_in: VitalSignBatchCreate, db: Session = Depends(get_db)):
    records = RecordService.batch_create_vital_signs(db, batch_in.records)
    for vs in records:
        AlertRuleService.check_vital_signs(db, vs)
    return records


@router.get("/{patient_id}/vital-signs", response_model=List[VitalSignResponse], summary="查询生命体征记录")
def list_vital_signs(
    patient_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return RecordService.list_vital_signs(db, patient_id, start_time, end_time, limit)


@router.post("/ecg", response_model=ECGRecordResponse, summary="录入心电图记录")
def create_ecg(ecg_in: ECGRecordCreate, db: Session = Depends(get_db)):
    return RecordService.create_ecg(db, ecg_in)


@router.get("/{patient_id}/ecg", response_model=List[ECGRecordResponse], summary="查询心电图记录")
def list_ecg(
    patient_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return RecordService.list_ecg_records(db, patient_id, limit)


@router.post("/lab", response_model=LabRecordResponse, summary="录入检验记录")
def create_lab(lab_in: LabRecordCreate, db: Session = Depends(get_db)):
    lab = RecordService.create_lab_record(db, lab_in)
    AlertRuleService.check_lab_record(db, lab)
    AlertRuleService.check_duplicate_exam(
        db, lab.patient_id, "lab", lab.test_code or "",
        exclude_record_ids=[lab.id], new_record_id=lab.id
    )
    return lab


@router.post("/lab/batch", response_model=List[LabRecordResponse], summary="批量录入检验记录")
def batch_create_lab(batch_in: LabRecordBatchCreate, db: Session = Depends(get_db)):
    labs = RecordService.batch_create_lab_records(db, batch_in.records)
    new_ids = [lab.id for lab in labs]
    patient_codes_seen = {}
    for lab in labs:
        AlertRuleService.check_lab_record(db, lab)
        key = (lab.patient_id, lab.test_code or "")
        if key in patient_codes_seen:
            first = patient_codes_seen[key]
            AlertRuleService._create_alert(
                db, lab.patient_id, lab.visit_id,
                alert_type="duplicate_exam",
                alert_level="medium",
                title=f"重复检查提示: {lab.test_name}",
                content=f"本批次内已存在相同检验【{first.test_name}】(首次值: {first.test_value}{first.test_unit or ''}，本次值: {lab.test_value}{lab.test_unit or ''}，请确认是否重复录入。",
                related_record_type="lab_record",
                related_record_id=lab.id,
            )
            db.commit()
        else:
            patient_codes_seen[key] = lab
            AlertRuleService.check_duplicate_exam(
                db, lab.patient_id, "lab", lab.test_code or "",
                exclude_record_ids=new_ids, new_record_id=lab.id
            )
    return labs


@router.get("/{patient_id}/lab", response_model=List[LabRecordResponse], summary="查询检验记录")
def list_lab(
    patient_id: int,
    lab_type: Optional[str] = None,
    abnormal_only: bool = False,
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    return RecordService.list_lab_records(db, patient_id, lab_type, abnormal_only, limit)


@router.post("/medications", response_model=MedicationRecordResponse, summary="录入用药记录")
def create_medication(med_in: MedicationRecordCreate, db: Session = Depends(get_db)):
    med = RecordService.create_medication(db, med_in)
    history = (
        db.query(MedicationRecord)
        .filter(
            MedicationRecord.patient_id == med.patient_id,
            MedicationRecord.is_active == True,
            MedicationRecord.id != med.id,
        )
        .all()
    )
    AlertRuleService.check_medication_safety(db, med, history, peer_meds=[med])
    return med


@router.post("/medications/batch", response_model=List[MedicationRecordResponse], summary="批量录入用药记录")
def batch_create_medications(batch_in: MedicationRecordBatchCreate, db: Session = Depends(get_db)):
    meds = RecordService.batch_create_medications(db, batch_in.records)
    AlertRuleService.check_batch_medication_safety(db, meds)
    return meds


@router.get("/{patient_id}/medications", response_model=List[MedicationRecordResponse], summary="查询用药记录")
def list_medications(
    patient_id: int,
    active_only: bool = False,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return RecordService.list_medications(db, patient_id, active_only, limit)


@router.get("/{patient_id}/stats", response_model=RecordStatsResponse, summary="获取患者检查记录统计")
def get_record_stats(patient_id: int, db: Session = Depends(get_db)):
    return RecordService.get_record_stats(db, patient_id)
