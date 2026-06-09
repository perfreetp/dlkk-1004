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
    def get_timeline(
        db: Session,
        patient_id: int,
        event_types: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        visit_id: Optional[int] = None,
        visit_no: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        include_groups: bool = True,
    ) -> Dict[str, Any]:
        from collections import defaultdict
        from app.schemas.patient import TimelineVisitGroup

        patient = PatientService.get_patient(db, patient_id)
        if not patient:
            return {"patient_id": patient_id, "total": 0, "page": page, "page_size": page_size, "has_more": False, "events": [], "visit_groups": []}

        visit_map: Dict[int, Visit] = {}
        for v in patient.visits:
            visit_map[v.id] = v

        if visit_no:
            target = db.query(Visit).filter(
                Visit.patient_id == patient_id, Visit.visit_no == visit_no
            ).first()
            if target:
                visit_id = target.id
            else:
                return {"patient_id": patient_id, "total": 0, "page": page, "page_size": page_size, "has_more": False, "events": [], "visit_groups": []}

        if visit_id is not None:
            if visit_id not in visit_map:
                return {"patient_id": patient_id, "total": 0, "page": page, "page_size": page_size, "has_more": False, "events": [], "visit_groups": []}

        allowed = set(event_types) if event_types else None

        def _in_time(t: Optional[datetime]) -> bool:
            if not t:
                return False
            if start_time and t < start_time:
                return False
            if end_time and t > end_time:
                return False
            return True

        def _ok_vid(vid: Optional[int]) -> bool:
            if visit_id is None:
                return True
            return vid == visit_id

        def _ok_etype(et: str) -> bool:
            if allowed is None:
                return True
            return et in allowed

        events: List[TimelineEvent] = []
        visit_events: Dict[int, List[TimelineEvent]] = defaultdict(list)

        def _append(evt: TimelineEvent, v_id: Optional[int]):
            events.append(evt)
            if v_id:
                visit_events[v_id].append(evt)

        def _visit_info(vid: Optional[int]):
            if vid and vid in visit_map:
                v = visit_map[vid]
                return v.id, v.visit_no
            return None, None

        for visit in patient.visits:
            if not _ok_etype("visit"):
                continue
            if not _in_time(visit.visit_date or visit.created_at):
                continue
            if not _ok_vid(visit.id):
                continue
            evt = TimelineEvent(
                event_type="visit",
                event_time=visit.visit_date or visit.created_at,
                title=f"{visit.visit_type}就诊",
                description=visit.chief_complaint or f"就诊编号: {visit.visit_no}",
                related_id=visit.id,
                visit_id=visit.id,
                visit_no=visit.visit_no,
                status=visit.diagnosis and "已诊" or "就诊中",
                level=None,
                extra={"department": visit.department, "diagnosis": visit.diagnosis},
            )
            _append(evt, visit.id)

        for vs in patient.vital_signs:
            if not _ok_etype("vital_sign"):
                continue
            if not _in_time(vs.record_time or vs.created_at):
                continue
            if not _ok_vid(vs.visit_id):
                continue
            title_parts = []
            if vs.systolic_bp and vs.diastolic_bp:
                title_parts.append(f"BP {vs.systolic_bp}/{vs.diastolic_bp}")
            if vs.heart_rate:
                title_parts.append(f"HR {vs.heart_rate}")
            vid, vno = _visit_info(vs.visit_id)
            evt = TimelineEvent(
                event_type="vital_sign",
                event_time=vs.record_time or vs.created_at,
                title="生命体征: " + (", ".join(title_parts) if title_parts else "记录"),
                description=vs.remark or "",
                related_id=vs.id,
                visit_id=vid,
                visit_no=vno,
                status=None,
                level=None,
                extra={"source": vs.source},
            )
            _append(evt, vs.visit_id)

        for ecg in patient.ecg_records:
            if not _ok_etype("ecg"):
                continue
            if not _in_time(ecg.record_time or ecg.created_at):
                continue
            if not _ok_vid(ecg.visit_id):
                continue
            vid, vno = _visit_info(ecg.visit_id)
            evt = TimelineEvent(
                event_type="ecg",
                event_time=ecg.record_time or ecg.created_at,
                title=f"心电检查: {ecg.ecg_type or '常规'}",
                description=ecg.interpretation or f"心率 {ecg.heart_rate or '-'} bpm",
                related_id=ecg.id,
                visit_id=vid,
                visit_no=vno,
                status="异常" if ecg.is_abnormal else "正常",
                level="high" if ecg.is_abnormal else None,
                extra={"is_abnormal": ecg.is_abnormal, "rhythm": ecg.rhythm},
            )
            _append(evt, ecg.visit_id)

        for lab in patient.lab_records:
            if not _ok_etype("lab"):
                continue
            if not _in_time(lab.record_time or lab.created_at):
                continue
            if not _ok_vid(lab.visit_id):
                continue
            flag = "异常" if lab.is_abnormal else "正常"
            lvl = "high" if lab.is_abnormal and lab.abnormal_flag in ["HH", "LL", "CRITICAL"] else ("medium" if lab.is_abnormal else None)
            vid, vno = _visit_info(lab.visit_id)
            evt = TimelineEvent(
                event_type="lab",
                event_time=lab.record_time or lab.created_at,
                title=f"检验: {lab.test_name} = {lab.test_value}{lab.test_unit or ''} [{flag}]",
                description=f"参考范围: {lab.reference_low or '-'}-{lab.reference_high or '-'}",
                related_id=lab.id,
                visit_id=vid,
                visit_no=vno,
                status=flag,
                level=lvl,
                extra={"lab_type": lab.lab_type, "abnormal_flag": lab.abnormal_flag},
            )
            _append(evt, lab.visit_id)

        for med in patient.medications:
            if not _ok_etype("medication"):
                continue
            if not _in_time(med.order_time or med.created_at):
                continue
            if not _ok_vid(med.visit_id):
                continue
            vid, vno = _visit_info(med.visit_id)
            status_str = "在用" if med.is_active else "停用"
            evt = TimelineEvent(
                event_type="medication",
                event_time=med.order_time or med.created_at,
                title=f"用药: {med.drug_name}",
                description=f"{med.dosage} {med.frequency} {med.route}",
                related_id=med.id,
                visit_id=vid,
                visit_no=vno,
                status=status_str,
                level=None,
                extra={"is_active": med.is_active, "category": med.drug_category},
            )
            _append(evt, med.visit_id)

        for risk in patient.risk_assessments:
            if not _ok_etype("risk"):
                continue
            if not _in_time(risk.assessment_date or risk.created_at):
                continue
            if not _ok_vid(risk.visit_id):
                continue
            vid, vno = _visit_info(risk.visit_id)
            rlvl = risk.risk_level or ""
            if "极高" in rlvl or "critical" in rlvl.lower():
                disp_level = "critical"
            elif "高" in rlvl or "high" in rlvl.lower():
                disp_level = "high"
            elif "中" in rlvl or "medium" in rlvl.lower():
                disp_level = "medium"
            elif "低" in rlvl or "low" in rlvl.lower():
                disp_level = "low"
            else:
                disp_level = None
            evt = TimelineEvent(
                event_type="risk",
                event_time=risk.assessment_date or risk.created_at,
                title=f"风险评估: {risk.assessment_type} [{risk.risk_level}]",
                description=risk.recommendations or f"评分: {risk.risk_score}",
                related_id=risk.id,
                visit_id=vid,
                visit_no=vno,
                status=risk.risk_level,
                level=disp_level,
                extra={"risk_score": risk.risk_score, "assessor": risk.assessor},
            )
            _append(evt, risk.visit_id)

        for alert in patient.alerts:
            if not _ok_etype("alert"):
                continue
            if not _in_time(alert.alert_time or alert.created_at):
                continue
            if not _ok_vid(alert.visit_id):
                continue
            vid, vno = _visit_info(alert.visit_id)
            if alert.is_resolved:
                status_str = "已解决"
            elif alert.is_read:
                status_str = "已读未处理"
            else:
                status_str = "未读"
            evt = TimelineEvent(
                event_type="alert",
                event_time=alert.alert_time or alert.created_at,
                title=f"提醒: [{alert.alert_level}] {alert.title}",
                description=alert.content or f"类型: {alert.alert_type}",
                related_id=alert.id,
                visit_id=vid,
                visit_no=vno,
                status=status_str,
                level=alert.alert_level,
                extra={"alert_type": alert.alert_type, "is_resolved": alert.is_resolved, "is_read": alert.is_read, "related_record_type": alert.related_record_type, "related_record_id": alert.related_record_id},
            )
            _append(evt, alert.visit_id)

        for plan in patient.care_plans:
            if not _ok_etype("care_plan"):
                continue
            if not _in_time(plan.plan_date or plan.created_at):
                continue
            if not _ok_vid(plan.visit_id):
                continue
            vid, vno = _visit_info(plan.visit_id)
            status_map = {"draft": "草稿", "reviewed": "已审核", "approved": "已签发", "executing": "执行中", "completed": "已完成"}
            evt = TimelineEvent(
                event_type="care_plan",
                event_time=plan.plan_date or plan.created_at,
                title=f"诊疗方案: [{status_map.get(plan.status, plan.status)}] {plan.plan_type}",
                description=plan.treatment_notes or f"作者: {plan.author_id or '-'}",
                related_id=plan.id,
                visit_id=vid,
                visit_no=vno,
                status=status_map.get(plan.status, plan.status),
                level=None,
                extra={"status": plan.status, "author_id": plan.author_id, "reviewer_id": plan.reviewer_id, "review_time": plan.review_time.isoformat() if plan.review_time else None},
            )
            _append(evt, plan.visit_id)

        for fu in patient.follow_ups:
            if not _ok_etype("follow_up"):
                continue
            if not _in_time(fu.scheduled_date):
                continue
            if not _ok_vid(fu.visit_id):
                continue
            vid, vno = _visit_info(fu.visit_id)
            status_map2 = {"scheduled": "已预约", "completed": "已完成", "cancelled": "已取消", "missed": "逾期未到"}
            evt = TimelineEvent(
                event_type="follow_up",
                event_time=fu.scheduled_date,
                title=f"随访: {fu.follow_up_type} [{status_map2.get(fu.status, fu.status)}]",
                description=fu.purpose or f"预约: {fu.scheduled_date.strftime('%Y-%m-%d')}",
                related_id=fu.id,
                visit_id=vid,
                visit_no=vno,
                status=status_map2.get(fu.status, fu.status),
                level="high" if fu.status == "missed" else None,
                extra={"assigned_doctor": fu.assigned_doctor_id, "actual_date": fu.actual_date.isoformat() if fu.actual_date else None, "reminder_sent": fu.reminder_sent},
            )
            _append(evt, fu.visit_id)

        events.sort(key=lambda e: e.event_time, reverse=True)
        total = len(events)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_events = events[start_idx:end_idx]
        has_more = end_idx < total

        visit_groups = []
        if include_groups:
            for v_id in sorted(visit_events.keys(), key=lambda i: visit_map[i].visit_date or visit_map[i].created_at, reverse=True):
                if v_id not in visit_map:
                    continue
                if visit_id is not None and v_id != visit_id:
                    continue
                v = visit_map[v_id]
                v_evts = sorted(visit_events[v_id], key=lambda e: e.event_time, reverse=True)
                visit_groups.append(TimelineVisitGroup(
                    visit_id=v.id,
                    visit_no=v.visit_no,
                    visit_type=v.visit_type,
                    visit_time=v.visit_date or v.created_at,
                    chief_complaint=v.chief_complaint,
                    diagnosis=v.diagnosis,
                    department=v.department,
                    events=v_evts,
                ))

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
            "events": paged_events,
            "visit_groups": visit_groups,
        }
