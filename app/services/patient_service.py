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
            sync_tag = ""
            fu_sync = getattr(fu, "plan_sync_status", None) or "synced"
            if fu_sync != "synced" and getattr(fu, "care_plan_id", None):
                sync_map = {"plan_updated": "方案已更新，请核对", "plan_withdrawn": "方案已撤回，请确认"}
                sync_tag = f" ⚠ {sync_map.get(fu_sync, '方案有变更')}"
            fu_status = status_map2.get(fu.status, fu.status)
            evt = TimelineEvent(
                event_type="follow_up",
                event_time=fu.scheduled_date,
                title=f"随访: {fu.follow_up_type} [{fu_status}]{sync_tag}",
                description=fu.purpose or f"预约: {fu.scheduled_date.strftime('%Y-%m-%d')}",
                related_id=fu.id,
                visit_id=vid,
                visit_no=vno,
                status=fu_status,
                level="high" if fu.status == "missed" or (fu_sync != "synced") else None,
                extra={
                    "assigned_doctor": fu.assigned_doctor_id,
                    "actual_date": fu.actual_date.isoformat() if fu.actual_date else None,
                    "reminder_sent": fu.reminder_sent,
                    "care_plan_id": getattr(fu, "care_plan_id", None),
                    "care_plan_snapshot": getattr(fu, "care_plan_snapshot", None),
                    "plan_sync_status": fu_sync,
                },
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

    @staticmethod
    def compare_visits(
        db: Session, patient_id: int, visit_id1: int, visit_id2: int
    ) -> Dict[str, Any]:
        from app.models.patient import Visit
        from app.models.records import VitalSign, ECGRecord, LabRecord, MedicationRecord
        from app.models.risk_alert import RiskAssessment
        from app.schemas.patient import CompareMetric, VisitCompareSummary

        patient = PatientService.get_patient(db, patient_id)
        if not patient:
            raise ValueError("患者不存在")

        v1 = db.query(Visit).filter(Visit.id == visit_id1, Visit.patient_id == patient_id).first()
        v2 = db.query(Visit).filter(Visit.id == visit_id2, Visit.patient_id == patient_id).first()
        if not v1 or not v2:
            raise ValueError("就诊不存在或不属于该患者")

        def _safe_float(val):
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        def _num_change(a, b):
            if a is None and b is None:
                return "unchanged", 0.0
            if a is None:
                return "new", None
            if b is None:
                return "removed", None
            da, db = _safe_float(a), _safe_float(b)
            if da is None or db is None:
                return "unchanged", 0.0
            diff = db - da
            if abs(diff) < 1e-9:
                return "unchanged", 0.0
            return ("increased" if diff > 0 else "decreased"), round(diff, 4)

        def _abnormal_change(abn_v1, abn_v2, val_v1=None, val_v2=None, ref_low=None, ref_high=None):
            def _is_abn(v, a):
                if a is not None:
                    return bool(a)
                if v is None or ref_low is None or ref_high is None:
                    return False
                try:
                    fv = float(v)
                    return fv < float(ref_low) or fv > float(ref_high)
                except (ValueError, TypeError):
                    return False
            a1 = _is_abn(val_v1, abn_v1)
            a2 = _is_abn(val_v2, abn_v2)
            if not a1 and not a2:
                # 双正常：若都有值→unchanged_normal，一个有一个无→unknown
                if val_v1 is None and val_v2 is None:
                    return "unknown"
                if val_v1 is None or val_v2 is None:
                    return "unchanged"
                return "unchanged_normal"
            if not a1 and a2:
                return "worsened"  # 正常→异常=变差
            if a1 and not a2:
                return "improved"  # 异常→正常=改善
            # 双异常：看趋势
            if val_v1 is None or val_v2 is None or ref_low is None or ref_high is None:
                return "unchanged_abnormal"
            try:
                f1, f2, lo, hi = float(val_v1), float(val_v2), float(ref_low), float(ref_high)
                def _deviation(x):
                    if x < lo: return lo - x
                    if x > hi: return x - hi
                    return 0.0
                d1, d2 = _deviation(f1), _deviation(f2)
                if abs(d2 - d1) < 1e-9:
                    return "unchanged_abnormal"
                return "improved" if d2 < d1 else "worsened"
            except (ValueError, TypeError):
                return "unchanged_abnormal"

        summary = {}
        for cat in ["vital_signs", "labs", "medications", "risks"]:
            summary[cat] = VisitCompareSummary()

        # === 1. Vital signs: 取两次就诊最近的一次生命体征 ===
        vs1 = db.query(VitalSign).filter(
            VitalSign.patient_id == patient_id, VitalSign.visit_id == visit_id1
        ).order_by(VitalSign.record_time.desc()).first()
        vs2 = db.query(VitalSign).filter(
            VitalSign.patient_id == patient_id, VitalSign.visit_id == visit_id2
        ).order_by(VitalSign.record_time.desc()).first()

        VITAL_REF = {
            "systolic_bp": (90.0, 140.0),
            "diastolic_bp": (60.0, 90.0),
            "heart_rate": (60.0, 100.0),
            "respiratory_rate": (12.0, 20.0),
            "temperature": (36.0, 37.3),
            "oxygen_saturation": (95.0, 100.0),
        }
        vital_map = {
            "收缩压": ("systolic_bp", "mmHg"),
            "舒张压": ("diastolic_bp", "mmHg"),
            "心率": ("heart_rate", "bpm"),
            "呼吸频率": ("respiratory_rate", "次/分"),
            "体温": ("temperature", "℃"),
            "血氧饱和度": ("oxygen_saturation", "%"),
        }
        vital_results = []
        for name, (field, unit) in vital_map.items():
            a = getattr(vs1, field, None) if vs1 else None
            b = getattr(vs2, field, None) if vs2 else None
            ctype, delta = _num_change(a, b)
            ref = VITAL_REF.get(field)
            abn_v1 = None
            abn_v2 = None
            if ref and a is not None:
                try: fa = float(a); abn_v1 = fa < ref[0] or fa > ref[1]
                except (ValueError, TypeError): abn_v1 = None
            if ref and b is not None:
                try: fb = float(b); abn_v2 = fb < ref[0] or fb > ref[1]
                except (ValueError, TypeError): abn_v2 = None
            abn_change = _abnormal_change(abn_v1, abn_v2, val_v1=a, val_v2=b, ref_low=ref[0] if ref else None, ref_high=ref[1] if ref else None)
            v1d = {"value": a, "unit": unit, "is_abnormal": abn_v1}
            v2d = {"value": b, "unit": unit, "is_abnormal": abn_v2}
            if ref:
                v1d["reference_low"] = ref[0]; v1d["reference_high"] = ref[1]
                v2d["reference_low"] = ref[0]; v2d["reference_high"] = ref[1]
            cm = CompareMetric(
                name=name, code=field, unit=unit,
                v1_value=a, v2_value=b, change_type=ctype, delta=delta,
                v1_details=v1d, v2_details=v2d, abnormal_change=abn_change,
                level="abnormal_v1" if abn_v1 else None,
            )
            if abn_v2: cm.level = "abnormal_v2" if not cm.level else "abnormal_both"
            vital_results.append(cm)
            setattr(summary["vital_signs"], ctype, getattr(summary["vital_signs"], ctype) + 1)
            if abn_change == "improved": summary["vital_signs"].improved += 1
            elif abn_change == "worsened": summary["vital_signs"].worsened += 1
            summary["vital_signs"].total += 1

        # === 2. Labs: 按 test_code 归并比较 ===
        labs1 = db.query(LabRecord).filter(
            LabRecord.patient_id == patient_id, LabRecord.visit_id == visit_id1
        ).all()
        labs2 = db.query(LabRecord).filter(
            LabRecord.patient_id == patient_id, LabRecord.visit_id == visit_id2
        ).all()
        map1 = {f"{l.test_code or l.test_name}": l for l in labs1}
        map2 = {f"{l.test_code or l.test_name}": l for l in labs2}
        all_keys = sorted(set(list(map1.keys()) + list(map2.keys())))
        lab_results = []
        for key in all_keys:
            a = map1.get(key)
            b = map2.get(key)
            code = (a.test_code if a else None) or (b.test_code if b else None)
            name = (a.test_name if a else None) or (b.test_name if b else None) or key
            unit = (a.test_unit if a else None) or (b.test_unit if b else None)
            va = a.test_value if a else None
            vb = b.test_value if b else None
            ctype, delta = _num_change(va, vb)
            abn_v1 = getattr(a, "is_abnormal", None) if a else None
            abn_v2 = getattr(b, "is_abnormal", None) if b else None
            ref_low = (a.reference_low if a else None) or (b.reference_low if b else None)
            ref_high = (a.reference_high if a else None) or (b.reference_high if b else None)
            abn_change = _abnormal_change(abn_v1, abn_v2, val_v1=va, val_v2=vb, ref_low=ref_low, ref_high=ref_high)
            abn_flag_v1 = getattr(a, "abnormal_flag", None) if a else None
            abn_flag_v2 = getattr(b, "abnormal_flag", None) if b else None
            v1d = {"value": va, "unit": unit, "is_abnormal": abn_v1, "abnormal_flag": abn_flag_v1,
                   "reference_low": a.reference_low if a else None, "reference_high": a.reference_high if a else None}
            v2d = {"value": vb, "unit": unit, "is_abnormal": abn_v2, "abnormal_flag": abn_flag_v2,
                   "reference_low": b.reference_low if b else None, "reference_high": b.reference_high if b else None}
            level = None
            if abn_v1: level = "abnormal_v1"
            if abn_v2: level = "abnormal_v2" if not level else "abnormal_both"
            lab_results.append(CompareMetric(
                name=name, code=code, unit=unit,
                v1_value=va, v2_value=vb, change_type=ctype, delta=delta, level=level,
                v1_details=v1d, v2_details=v2d, abnormal_change=abn_change,
            ))
            setattr(summary["labs"], ctype, getattr(summary["labs"], ctype) + 1)
            if abn_change == "improved": summary["labs"].improved += 1
            elif abn_change == "worsened": summary["labs"].worsened += 1
            summary["labs"].total += 1

        # === 3. Medications: 按 generic_name 归并，细分为停用/剂量/频次变化 ===
        meds1 = db.query(MedicationRecord).filter(
            MedicationRecord.patient_id == patient_id, MedicationRecord.visit_id == visit_id1
        ).all()
        meds2 = db.query(MedicationRecord).filter(
            MedicationRecord.patient_id == patient_id, MedicationRecord.visit_id == visit_id2
        ).all()
        mmap1 = {(m.generic_name or m.drug_name or "").lower(): m for m in meds1}
        mmap2 = {(m.generic_name or m.drug_name or "").lower(): m for m in meds2}
        all_med_keys = sorted(set(list(mmap1.keys()) + list(mmap2.keys())))
        med_results = []
        for key in all_med_keys:
            a = mmap1.get(key)
            b = mmap2.get(key)
            name = (a.drug_name if a else None) or (b.drug_name if b else None) or key
            gname = (a.generic_name if a else None) or (b.generic_name if b else None)
            # 激活状态判断
            active_v1 = bool(getattr(a, "is_active", False)) if a else False
            active_v2 = bool(getattr(b, "is_active", False)) if b else False
            dose_v1 = getattr(a, "dosage", None) if a else None
            dose_v2 = getattr(b, "dosage", None) if b else None
            freq_v1 = getattr(a, "frequency", None) if a else None
            freq_v2 = getattr(b, "frequency", None) if b else None
            route_v1 = getattr(a, "route", None) if a else None
            route_v2 = getattr(b, "route", None) if b else None

            if a and b:
                # 双都存在
                if active_v1 and not active_v2:
                    ctype = "discontinued"  # 明确停用：从active→inactive且V2有记录
                else:
                    dose_changed = (dose_v1 != dose_v2) and (dose_v1 is not None or dose_v2 is not None)
                    freq_changed = (freq_v1 != freq_v2) and (freq_v1 is not None or freq_v2 is not None)
                    if dose_changed and freq_changed:
                        ctype = "changed"  # 剂量+频次都变了
                    elif dose_changed:
                        ctype = "dosage_changed"
                    elif freq_changed:
                        ctype = "frequency_changed"
                    else:
                        ctype = "continued"
            elif b and not a:
                ctype = "new"
            else:
                # V1有V2完全没有记录（b is None）
                ctype = "removed"  # V2没这个药记录（不管V1是否active，按老逻辑removed）

            va = dose_v1
            vb = dose_v2
            v1d = {"dosage": dose_v1, "frequency": freq_v1, "route": route_v1, "is_active": active_v1}
            v2d = {"dosage": dose_v2, "frequency": freq_v2, "route": route_v2, "is_active": active_v2}
            if a: v1d["start_date"] = a.start_date.isoformat() if a.start_date else None
            if b: v2d["start_date"] = b.start_date.isoformat() if b.start_date else None
            med_results.append(CompareMetric(
                name=name, code=gname,
                v1_value=va, v2_value=vb, change_type=ctype,
                v1_details=v1d, v2_details=v2d,
            ))
            setattr(summary["medications"], ctype, getattr(summary["medications"], ctype) + 1)
            summary["medications"].total += 1

        # === 4. Risks: 按 assessment_type 归并 ===
        risks1 = db.query(RiskAssessment).filter(
            RiskAssessment.patient_id == patient_id, RiskAssessment.visit_id == visit_id1
        ).all()
        risks2 = db.query(RiskAssessment).filter(
            RiskAssessment.patient_id == patient_id, RiskAssessment.visit_id == visit_id2
        ).all()
        rmap1 = {r.assessment_type: r for r in risks1}
        rmap2 = {r.assessment_type: r for r in risks2}
        all_risk_keys = sorted(set(list(rmap1.keys()) + list(rmap2.keys())))
        risk_results = []
        RISK_ORDER = {"极低危": 0, "低危": 1, "中危": 2, "高危": 3, "极高危": 4}
        for atype in all_risk_keys:
            a = rmap1.get(atype)
            b = rmap2.get(atype)
            va = a.risk_level if a else None
            vb = b.risk_level if b else None
            if a and b:
                ia = RISK_ORDER.get(va, -1)
                ib = RISK_ORDER.get(vb, -1)
                if ib == ia:
                    ctype = "unchanged"
                elif ib > ia:
                    ctype = "increased"
                else:
                    ctype = "decreased"
            elif b and not a:
                ctype = "new"
            else:
                ctype = "removed"
            risk_results.append(CompareMetric(
                name=atype, code=atype,
                v1_value=va, v2_value=vb, change_type=ctype,
                delta=(b.risk_score - a.risk_score) if (a and b and a.risk_score is not None and b.risk_score is not None) else None,
            ))
            setattr(summary["risks"], ctype, getattr(summary["risks"], ctype) + 1)
            summary["risks"].total += 1

        # 总体汇总：把四个类别的计数器都累加
        total_summary = VisitCompareSummary()
        fields = [
            "increased", "decreased", "unchanged", "new", "removed", "continued",
            "discontinued", "dosage_changed", "frequency_changed", "changed",
            "improved", "worsened", "total",
        ]
        for cat in ["vital_signs", "labs", "medications", "risks"]:
            cs = summary[cat]
            for f in fields:
                setattr(total_summary, f, getattr(total_summary, f) + getattr(cs, f))

        return {
            "patient_id": patient_id,
            "visit1_id": visit_id1,
            "visit2_id": visit_id2,
            "visit1_no": v1.visit_no,
            "visit2_no": v2.visit_no,
            "visit1_time": v1.visit_date or v1.created_at,
            "visit2_time": v2.visit_date or v2.created_at,
            "vital_signs": [m.model_dump() for m in vital_results],
            "labs": [m.model_dump() for m in lab_results],
            "medications": [m.model_dump() for m in med_results],
            "risks": [m.model_dump() for m in risk_results],
            "summary": {k: v.model_dump() for k, v in summary.items()},
            "summary_total": total_summary.model_dump(),
        }
