from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.models.patient import Patient, Visit
from app.models.records import VitalSign, ECGRecord, LabRecord, MedicationRecord
from app.models.risk_alert import RiskAssessment, Alert
from app.models.plan_followup import CarePlan, FollowUp
from app.schemas.patient import PatientCreate, PatientUpdate, VisitCreate, VisitMergeRequest, TimelineEvent


class PatientService:
    @staticmethod
    def create_patient(db: Session, patient_in: PatientCreate) -> Patient:
        patient = Patient(**patient_in.model_dump())
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return patient

    @staticmethod
    def get_patient(db: Session, patient_id: int) -> Optional[Patient]:
        return db.query(Patient).filter(Patient.id == patient_id).first()

    @staticmethod
    def get_patient_by_no(db: Session, patient_no: str) -> Optional[Patient]:
        return db.query(Patient).filter(Patient.patient_no == patient_no).first()

    @staticmethod
    def list_patients(
        db: Session,
        keyword: Optional[str] = None,
        department: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[int, List[Patient]]:
        query = db.query(Patient)
        if keyword:
            query = query.filter(
                or_(
                    Patient.name.contains(keyword),
                    Patient.patient_no.contains(keyword),
                    Patient.id_card.contains(keyword) if keyword else False,
                    Patient.phone.contains(keyword) if keyword else False,
                )
            )
        if department:
            query = query.filter(Patient.department == department)
        total = query.count()
        patients = query.order_by(Patient.created_at.desc()).offset(skip).limit(limit).all()
        return total, patients

    @staticmethod
    def update_patient(db: Session, patient_id: int, patient_in: PatientUpdate) -> Optional[Patient]:
        patient = PatientService.get_patient(db, patient_id)
        if not patient:
            return None
        update_data = patient_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(patient, key, value)
        patient.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(patient)
        return patient

    @staticmethod
    def add_visit(db: Session, visit_in: VisitCreate) -> Visit:
        visit = Visit(**visit_in.model_dump())
        db.add(visit)
        db.commit()
        db.refresh(visit)
        return visit

    @staticmethod
    def get_visit(db: Session, visit_id: int) -> Optional[Visit]:
        return db.query(Visit).filter(Visit.id == visit_id).first()

    @staticmethod
    def list_visits(db: Session, patient_id: int) -> List[Visit]:
        return (
            db.query(Visit)
            .filter(Visit.patient_id == patient_id)
            .order_by(Visit.visit_date.desc())
            .all()
        )

    @staticmethod
    def merge_visits(db: Session, merge_in: VisitMergeRequest) -> dict:
        target = PatientService.get_patient(db, merge_in.target_patient_id)
        if not target:
            raise ValueError("目标患者不存在")

        related_models = [
            (VitalSign, "vital_signs"),
            (ECGRecord, "ecg_records"),
            (LabRecord, "lab_records"),
            (MedicationRecord, "medication_records"),
            (RiskAssessment, "risk_assessments"),
            (Alert, "alerts"),
            (CarePlan, "care_plans"),
            (FollowUp, "follow_ups"),
        ]

        merged_visit_count = 0
        merged_details: Dict[str, int] = {}

        for visit_id in merge_in.source_visit_ids:
            visit = PatientService.get_visit(db, visit_id)
            if not visit:
                continue
            if visit.patient_id == merge_in.target_patient_id:
                continue

            old_patient_id = visit.patient_id
            visit.patient_id = merge_in.target_patient_id
            merged_visit_count += 1

            for model, label in related_models:
                if hasattr(model, "visit_id"):
                    query = db.query(model).filter(model.visit_id == visit_id)
                else:
                    query = db.query(model).filter(
                        and_(
                            model.patient_id == old_patient_id,
                        )
                    )
                rel_count = query.count()
                if rel_count > 0:
                    query.update(
                        {model.patient_id: merge_in.target_patient_id},
                        synchronize_session=False,
                    )
                    merged_details[label] = merged_details.get(label, 0) + rel_count

        db.commit()
        return {
            "target_patient_id": merge_in.target_patient_id,
            "merged_visit_count": merged_visit_count,
            "merged_related_records": merged_details,
            "note": merge_in.merge_note,
        }

    @staticmethod
    def get_timeline(db: Session, patient_id: int, limit: int = 200) -> List[TimelineEvent]:
        patient = PatientService.get_patient(db, patient_id)
        if not patient:
            return []

        events = []

        for visit in patient.visits:
            events.append(TimelineEvent(
                event_type="visit",
                event_time=visit.visit_date or visit.created_at,
                title=f"{visit.visit_type}就诊",
                description=visit.chief_complaint or f"就诊编号: {visit.visit_no}",
                related_id=visit.id,
                extra={"department": visit.department, "diagnosis": visit.diagnosis},
            ))

        for vs in patient.vital_signs:
            title_parts = []
            if vs.systolic_bp and vs.diastolic_bp:
                title_parts.append(f"BP {vs.systolic_bp}/{vs.diastolic_bp}")
            if vs.heart_rate:
                title_parts.append(f"HR {vs.heart_rate}")
            events.append(TimelineEvent(
                event_type="vital_sign",
                event_time=vs.record_time or vs.created_at,
                title="生命体征: " + (", ".join(title_parts) if title_parts else "记录"),
                description=vs.remark or "",
                related_id=vs.id,
                extra={"source": vs.source},
            ))

        for ecg in patient.ecg_records:
            events.append(TimelineEvent(
                event_type="ecg",
                event_time=ecg.record_time or ecg.created_at,
                title=f"心电检查: {ecg.ecg_type or '常规'}",
                description=ecg.interpretation or f"心率 {ecg.heart_rate or '-'} bpm",
                related_id=ecg.id,
                extra={"is_abnormal": ecg.is_abnormal, "rhythm": ecg.rhythm},
            ))

        for lab in patient.lab_records:
            flag = "异常" if lab.is_abnormal else "正常"
            events.append(TimelineEvent(
                event_type="lab",
                event_time=lab.record_time or lab.created_at,
                title=f"检验: {lab.test_name} = {lab.test_value}{lab.test_unit or ''} [{flag}]",
                description=f"参考范围: {lab.reference_low or '-'}-{lab.reference_high or '-'}",
                related_id=lab.id,
                extra={"lab_type": lab.lab_type, "abnormal_flag": lab.abnormal_flag},
            ))

        for med in patient.medications:
            events.append(TimelineEvent(
                event_type="medication",
                event_time=med.order_time or med.created_at,
                title=f"用药: {med.drug_name}",
                description=f"{med.dosage} {med.frequency} {med.route}",
                related_id=med.id,
                extra={"is_active": med.is_active, "category": med.drug_category},
            ))

        for risk in patient.risk_assessments:
            events.append(TimelineEvent(
                event_type="risk",
                event_time=risk.assessment_date or risk.created_at,
                title=f"风险评估: {risk.assessment_type} [{risk.risk_level}]",
                description=risk.recommendations or f"评分: {risk.risk_score}",
                related_id=risk.id,
                extra={"risk_score": risk.risk_score},
            ))

        for fu in patient.follow_ups:
            status = fu.status
            events.append(TimelineEvent(
                event_type="follow_up",
                event_time=fu.scheduled_date,
                title=f"随访: {fu.follow_up_type} [{status}]",
                description=fu.purpose or f"预约: {fu.scheduled_date.strftime('%Y-%m-%d')}",
                related_id=fu.id,
                extra={"assigned_doctor": fu.assigned_doctor_id},
            ))

        events.sort(key=lambda e: e.event_time, reverse=True)
        return events[:limit]
