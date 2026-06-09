from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.records import VitalSign, ECGRecord, LabRecord, MedicationRecord
from app.schemas.records import (
    VitalSignCreate, ECGRecordCreate, LabRecordCreate, MedicationRecordCreate,
    RecordStatsResponse,
)


class RecordService:
    @staticmethod
    def create_vital_sign(db: Session, vs_in: VitalSignCreate) -> VitalSign:
        vs = VitalSign(**vs_in.model_dump())
        db.add(vs)
        db.commit()
        db.refresh(vs)
        return vs

    @staticmethod
    def batch_create_vital_signs(db: Session, records: List[VitalSignCreate]) -> List[VitalSign]:
        result = []
        for r in records:
            vs = VitalSign(**r.model_dump())
            db.add(vs)
            result.append(vs)
        db.commit()
        for vs in result:
            db.refresh(vs)
        return result

    @staticmethod
    def list_vital_signs(
        db: Session,
        patient_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        visit_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[VitalSign]:
        query = db.query(VitalSign).filter(VitalSign.patient_id == patient_id)
        if visit_id:
            query = query.filter(VitalSign.visit_id == visit_id)
        if start_time:
            query = query.filter(VitalSign.record_time >= start_time)
        if end_time:
            query = query.filter(VitalSign.record_time <= end_time)
        return query.order_by(VitalSign.record_time.desc()).limit(limit).all()

    @staticmethod
    def create_ecg(db: Session, ecg_in: ECGRecordCreate) -> ECGRecord:
        ecg = ECGRecord(**ecg_in.model_dump())
        db.add(ecg)
        db.commit()
        db.refresh(ecg)
        return ecg

    @staticmethod
    def list_ecg_records(
        db: Session, patient_id: int, limit: int = 50
    ) -> List[ECGRecord]:
        return (
            db.query(ECGRecord)
            .filter(ECGRecord.patient_id == patient_id)
            .order_by(ECGRecord.record_time.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def create_lab_record(db: Session, lab_in: LabRecordCreate) -> LabRecord:
        lab = LabRecord(**lab_in.model_dump())
        if lab.reference_low is not None and lab.reference_high is not None:
            if lab.test_value < lab.reference_low or lab.test_value > lab.reference_high:
                lab.is_abnormal = True
                if lab.test_value < lab.reference_low:
                    lab.abnormal_flag = "L"
                else:
                    lab.abnormal_flag = "H"
        db.add(lab)
        db.commit()
        db.refresh(lab)
        return lab

    @staticmethod
    def batch_create_lab_records(db: Session, records: List[LabRecordCreate]) -> List[LabRecord]:
        result = []
        for r in records:
            lab = LabRecord(**r.model_dump())
            if lab.reference_low is not None and lab.reference_high is not None:
                if lab.test_value < lab.reference_low or lab.test_value > lab.reference_high:
                    lab.is_abnormal = True
                    lab.abnormal_flag = "L" if lab.test_value < lab.reference_low else "H"
            db.add(lab)
            result.append(lab)
        db.commit()
        for lab in result:
            db.refresh(lab)
        return result

    @staticmethod
    def list_lab_records(
        db: Session,
        patient_id: int,
        lab_type: Optional[str] = None,
        abnormal_only: bool = False,
        limit: int = 200,
    ) -> List[LabRecord]:
        query = db.query(LabRecord).filter(LabRecord.patient_id == patient_id)
        if lab_type:
            query = query.filter(LabRecord.lab_type == lab_type)
        if abnormal_only:
            query = query.filter(LabRecord.is_abnormal == True)
        return query.order_by(LabRecord.record_time.desc()).limit(limit).all()

    @staticmethod
    def create_medication(db: Session, med_in: MedicationRecordCreate) -> MedicationRecord:
        med = MedicationRecord(**med_in.model_dump())
        db.add(med)
        db.commit()
        db.refresh(med)
        return med

    @staticmethod
    def batch_create_medications(
        db: Session, records: List[MedicationRecordCreate]
    ) -> List[MedicationRecord]:
        result = []
        for r in records:
            med = MedicationRecord(**r.model_dump())
            db.add(med)
            result.append(med)
        db.commit()
        for med in result:
            db.refresh(med)
        return result

    @staticmethod
    def list_medications(
        db: Session,
        patient_id: int,
        active_only: bool = False,
        limit: int = 100,
    ) -> List[MedicationRecord]:
        query = db.query(MedicationRecord).filter(MedicationRecord.patient_id == patient_id)
        if active_only:
            query = query.filter(MedicationRecord.is_active == True)
        return query.order_by(MedicationRecord.order_time.desc()).limit(limit).all()

    @staticmethod
    def get_record_stats(db: Session, patient_id: int) -> RecordStatsResponse:
        vs_count = db.query(VitalSign).filter(VitalSign.patient_id == patient_id).count()
        ecg_count = db.query(ECGRecord).filter(ECGRecord.patient_id == patient_id).count()
        lab_count = db.query(LabRecord).filter(LabRecord.patient_id == patient_id).count()
        med_count = db.query(MedicationRecord).filter(MedicationRecord.patient_id == patient_id).count()

        latest_times = []
        latest_vs = (
            db.query(VitalSign.record_time)
            .filter(VitalSign.patient_id == patient_id)
            .order_by(VitalSign.record_time.desc())
            .first()
        )
        if latest_vs:
            latest_times.append(latest_vs[0])
        latest_ecg = (
            db.query(ECGRecord.record_time)
            .filter(ECGRecord.patient_id == patient_id)
            .order_by(ECGRecord.record_time.desc())
            .first()
        )
        if latest_ecg:
            latest_times.append(latest_ecg[0])
        latest_lab = (
            db.query(LabRecord.record_time)
            .filter(LabRecord.patient_id == patient_id)
            .order_by(LabRecord.record_time.desc())
            .first()
        )
        if latest_lab:
            latest_times.append(latest_lab[0])
        latest_med = (
            db.query(MedicationRecord.order_time)
            .filter(MedicationRecord.patient_id == patient_id)
            .order_by(MedicationRecord.order_time.desc())
            .first()
        )
        if latest_med:
            latest_times.append(latest_med[0])

        latest = max(latest_times) if latest_times else None

        return RecordStatsResponse(
            patient_id=patient_id,
            vital_sign_count=vs_count,
            ecg_count=ecg_count,
            lab_count=lab_count,
            medication_count=med_count,
            latest_record_time=latest,
        )

    @staticmethod
    def check_duplicate_lab(
        db: Session,
        patient_id: int,
        test_code: str,
        within_hours: int = 24,
    ) -> Optional[LabRecord]:
        cutoff = datetime.utcnow() - timedelta(hours=within_hours)
        return (
            db.query(LabRecord)
            .filter(
                LabRecord.patient_id == patient_id,
                LabRecord.test_code == test_code,
                LabRecord.record_time >= cutoff,
            )
            .order_by(LabRecord.record_time.desc())
            .first()
        )
