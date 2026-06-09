from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.plan_followup import FollowUp
from app.schemas.plan_followup import (
    FollowUpCreate, FollowUpRecordUpdate, FollowUpReminderRequest, ReminderResult,
)


class FollowUpService:
    FOLLOWUP_TYPE_SCHEDULE = {
        "heart_failure": {
            "极高危": {"days": 3, "label": "极高危心衰: 3日内复诊"},
            "高危": {"days": 7, "label": "高危心衰: 1周内复诊"},
            "中危": {"days": 14, "label": "中危心衰: 2周内复诊"},
            "低危": {"days": 30, "label": "低危心衰: 1月内复诊"},
        },
        "atrial_fibrillation": {
            "高危": {"days": 7, "label": "高危房颤: 1周内复诊(抗凝+心率)"},
            "中危": {"days": 21, "label": "中危房颤: 3周内复诊"},
            "低危": {"days": 90, "label": "低危房颤: 3月内复诊"},
        },
        "coronary_artery_disease": {
            "极高危": {"days": 3, "label": "ACS极高危: 3日内随诊"},
            "高危": {"days": 14, "label": "CAD高危: 2周内复诊"},
            "中危": {"days": 30, "label": "CAD中危: 1月内复诊"},
            "低危": {"days": 90, "label": "CAD低危: 3月内复诊"},
        },
        "post_pci": {"days": 30, "label": "PCI术后: 1月复诊"},
        "post_cabg": {"days": 30, "label": "CABG术后: 1月复诊"},
        "medication_adjustment": {"days": 14, "label": "调药后: 2周内复诊"},
        "post_discharge": {"days": 7, "label": "出院后: 1周内复诊"},
        "routine": {"days": 90, "label": "常规随访: 3月内"},
    }

    SYMPTOM_SEVERITY_SCORES = {
        "none": 0, "mild": 1, "moderate": 2, "severe": 3, "worsening": 4,
    }

    @staticmethod
    def create_follow_up(db: Session, fu_in: FollowUpCreate) -> FollowUp:
        fu = FollowUp(**fu_in.model_dump())
        fu.status = "scheduled"
        fu.reminder_sent = False
        db.add(fu)
        db.commit()
        db.refresh(fu)
        return fu

    @staticmethod
    def auto_schedule(
        db: Session,
        patient_id: int,
        visit_id: Optional[int],
        risk_summaries: Dict[str, str],
        scenarios: Optional[List[str]] = None,
        assigned_doctor_id: Optional[str] = None,
    ) -> List[FollowUp]:
        scheduled = []
        scenarios = scenarios or []

        for rtype, rlevel in risk_summaries.items():
            type_rule = FollowUpService.FOLLOWUP_TYPE_SCHEDULE.get(rtype, {})
            rule = type_rule.get(rlevel) if isinstance(type_rule, dict) else type_rule
            if rule and isinstance(rule, dict):
                fu = FollowUp(
                    patient_id=patient_id,
                    visit_id=visit_id,
                    follow_up_type=rtype,
                    scheduled_date=datetime.utcnow() + timedelta(days=rule["days"]),
                    status="scheduled",
                    purpose=rule["label"],
                    assigned_doctor_id=assigned_doctor_id,
                    reminder_sent=False,
                )
                db.add(fu)
                scheduled.append(fu)

        for scenario in scenarios:
            rule = FollowUpService.FOLLOWUP_TYPE_SCHEDULE.get(scenario)
            if rule and isinstance(rule, dict) and "days" in rule:
                fu = FollowUp(
                    patient_id=patient_id,
                    visit_id=visit_id,
                    follow_up_type=scenario,
                    scheduled_date=datetime.utcnow() + timedelta(days=rule["days"]),
                    status="scheduled",
                    purpose=rule["label"],
                    assigned_doctor_id=assigned_doctor_id,
                    reminder_sent=False,
                )
                db.add(fu)
                scheduled.append(fu)

        db.commit()
        for fu in scheduled:
            db.refresh(fu)
        return scheduled

    @staticmethod
    def get_follow_up(db: Session, fu_id: int) -> Optional[FollowUp]:
        return db.query(FollowUp).filter(FollowUp.id == fu_id).first()

    @staticmethod
    def list_follow_ups(
        db: Session,
        patient_id: Optional[int] = None,
        status: Optional[str] = None,
        doctor_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[int, int, int, int, List[FollowUp]]:
        query = db.query(FollowUp)
        if patient_id:
            query = query.filter(FollowUp.patient_id == patient_id)
        if status:
            query = query.filter(FollowUp.status == status)
        if doctor_id:
            query = query.filter(FollowUp.assigned_doctor_id == doctor_id)
        if start_date:
            query = query.filter(FollowUp.scheduled_date >= start_date)
        if end_date:
            query = query.filter(FollowUp.scheduled_date <= end_date)

        base_query = query
        now = datetime.utcnow()
        total = base_query.count()
        scheduled_count = base_query.filter(FollowUp.status == "scheduled").count()
        completed_count = base_query.filter(FollowUp.status == "completed").count()
        overdue_count = (
            base_query.filter(
                and_(FollowUp.status != "completed", FollowUp.scheduled_date < now)
            ).count()
        )

        items = query.order_by(FollowUp.scheduled_date.asc()).offset(skip).limit(limit).all()
        return total, scheduled_count, completed_count, overdue_count, items

    @staticmethod
    def record_follow_up(
        db: Session, fu_id: int, update_in: FollowUpRecordUpdate
    ) -> Optional[FollowUp]:
        fu = FollowUpService.get_follow_up(db, fu_id)
        if not fu:
            return None
        update_data = update_in.model_dump(exclude_unset=True)

        if "status" not in update_data or update_data.get("status") == "completed":
            update_data["status"] = "completed"
            if not fu.actual_date:
                fu.actual_date = datetime.utcnow()

        for key, value in update_data.items():
            setattr(fu, key, value)

        fu.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(fu)
        return fu

    @staticmethod
    def get_symptom_trend(
        db: Session, patient_id: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        records = (
            db.query(FollowUp)
            .filter(
                FollowUp.patient_id == patient_id,
                FollowUp.status == "completed",
            )
            .order_by(FollowUp.actual_date.desc())
            .limit(limit)
            .all()
        )

        trend = []
        for r in records:
            severity_score = FollowUpService.SYMPTOM_SEVERITY_SCORES.get(
                r.symptom_severity or "none", 0
            )
            trend.append({
                "follow_up_id": r.id,
                "follow_up_type": r.follow_up_type,
                "date": (r.actual_date or r.scheduled_date).isoformat(),
                "symptom_severity": r.symptom_severity,
                "severity_score": severity_score,
                "symptoms": r.symptoms_recorded,
                "weight": r.weight,
                "blood_pressure": r.blood_pressure,
                "heart_rate": r.heart_rate,
                "medication_adherence": r.medication_adherence,
                "adverse_events": r.adverse_events,
            })
        trend.reverse()
        return trend

    @staticmethod
    def send_reminders(
        db: Session, req: FollowUpReminderRequest
    ) -> List[ReminderResult]:
        results = []
        now = datetime.utcnow()
        cutoff = now + timedelta(days=req.days_before)

        query = db.query(FollowUp).filter(
            FollowUp.status.in_(["scheduled", "overdue"]),
            FollowUp.reminder_sent == False,
        )
        if req.follow_up_ids:
            query = query.filter(FollowUp.id.in_(req.follow_up_ids))
        else:
            query = query.filter(FollowUp.scheduled_date <= cutoff)

        follow_ups = query.all()

        for fu in follow_ups:
            is_overdue = fu.scheduled_date < now
            days_diff = (fu.scheduled_date.date() - now.date()).days

            if is_overdue:
                message = (
                    f"【已逾期提醒】患者ID {fu.patient_id} 随访已逾期{-days_diff}天，"
                    f"类型: {fu.follow_up_type}，原定日期: {fu.scheduled_date.strftime('%Y-%m-%d')}，"
                    f"目的: {fu.purpose or '常规随访'}，请尽快安排患者就诊。"
                )
            elif days_diff == 0:
                message = (
                    f"【当日复诊提醒】患者ID {fu.patient_id} 今日需复诊，"
                    f"类型: {fu.follow_up_type}，目的: {fu.purpose or '常规随访'}。"
                )
            else:
                message = (
                    f"【复诊提醒】患者ID {fu.patient_id} 将在{days_diff}天后复诊({fu.scheduled_date.strftime('%Y-%m-%d')})，"
                    f"类型: {fu.follow_up_type}，目的: {fu.purpose or '常规随访'}，请做好准备。"
                )

            fu.reminder_sent = True
            fu.reminder_time = now
            fu.reminder_method = req.reminder_method
            if is_overdue and fu.status == "scheduled":
                fu.status = "overdue"

            results.append(ReminderResult(
                follow_up_id=fu.id,
                patient_id=fu.patient_id,
                scheduled_date=fu.scheduled_date,
                reminder_sent=True,
                message=message,
            ))

        db.commit()
        return results
