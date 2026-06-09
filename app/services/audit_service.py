from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Date
from app.models.audit import AuditLog, UsageStats
from app.schemas.audit import AuditQueryRequest, UsageStatsRequest


class AuditService:
    MODULE_NAMES = {
        "patients": "患者档案",
        "records": "检查接入",
        "risks": "风险计算",
        "alerts": "提醒规则",
        "care_plans": "方案草稿",
        "follow_ups": "随访管理",
        "audit": "审计统计",
        "system": "系统管理",
    }

    @staticmethod
    def log_request(
        db: Session,
        request_id: str,
        endpoint: str,
        method: str,
        module: str,
        action: str,
        patient_id: Optional[int] = None,
        doctor_id: Optional[str] = None,
        department: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None,
        response_code: Optional[int] = None,
        response_summary: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        latency_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        log = AuditLog(
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            module=module,
            action=action,
            patient_id=patient_id,
            doctor_id=doctor_id,
            department=department,
            request_params=request_params,
            response_code=response_code,
            response_summary=response_summary,
            ip_address=ip_address,
            user_agent=user_agent,
            latency_ms=latency_ms,
            error_message=error_message,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def query_logs(
        db: Session, req: AuditQueryRequest
    ) -> Tuple[int, List[AuditLog]]:
        query = db.query(AuditLog)
        if req.module:
            query = query.filter(AuditLog.module == req.module)
        if req.action:
            query = query.filter(AuditLog.action == req.action)
        if req.patient_id:
            query = query.filter(AuditLog.patient_id == req.patient_id)
        if req.doctor_id:
            query = query.filter(AuditLog.doctor_id == req.doctor_id)
        if req.department:
            query = query.filter(AuditLog.department == req.department)
        if req.start_date:
            query = query.filter(AuditLog.created_at >= req.start_date)
        if req.end_date:
            query = query.filter(AuditLog.created_at <= req.end_date)

        total = query.count()
        items = (
            query.order_by(AuditLog.created_at.desc())
            .offset((req.page - 1) * req.page_size)
            .limit(req.page_size)
            .all()
        )
        return total, items

    @staticmethod
    def aggregate_daily_stats(db: Session) -> int:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)

        existing = (
            db.query(UsageStats)
            .filter(UsageStats.stat_date == yesterday_start)
            .first()
        )
        if existing:
            return 0

        stats_raw = (
            db.query(
                AuditLog.department,
                AuditLog.module,
                AuditLog.action,
                func.count(AuditLog.id),
                func.count(func.distinct(AuditLog.patient_id)),
                func.count(func.distinct(AuditLog.doctor_id)),
                func.avg(AuditLog.latency_ms),
                func.sum(func.if_(AuditLog.error_message.isnot(None), 1, 0)),
            )
            .filter(
                and_(
                    AuditLog.created_at >= yesterday_start,
                    AuditLog.created_at < today_start,
                )
            )
            .group_by(AuditLog.department, AuditLog.module, AuditLog.action)
            .all()
        )

        count = 0
        for dept, module, action, calls, patients, doctors, avg_lat, errors in stats_raw:
            stat = UsageStats(
                stat_date=yesterday_start,
                department=dept,
                module=module,
                action=action,
                call_count=calls,
                patient_count=patients,
                doctor_count=doctors,
                avg_latency_ms=int(avg_lat) if avg_lat is not None else None,
                error_count=int(errors),
            )
            db.add(stat)
            count += 1

        db.commit()
        return count

    @staticmethod
    def get_usage_stats(db: Session, req: UsageStatsRequest) -> Dict[str, Any]:
        query = db.query(AuditLog).filter(
            and_(AuditLog.created_at >= req.start_date, AuditLog.created_at <= req.end_date)
        )
        if req.department:
            query = query.filter(AuditLog.department == req.department)
        if req.module:
            query = query.filter(AuditLog.module == req.module)

        all_logs = query.all()

        total_calls = len(all_logs)
        total_patients = len({l.patient_id for l in all_logs if l.patient_id})
        total_doctors = len({l.doctor_id for l in all_logs if l.doctor_id})
        total_errors = len([l for l in all_logs if l.error_message])
        latencies = [l.latency_ms for l in all_logs if l.latency_ms is not None]
        avg_latency = int(sum(latencies) / len(latencies)) if latencies else None

        group_by = req.group_by or "day"
        breakdown_map = defaultdict(lambda: {
            "call_count": 0, "patient_count": set(), "doctor_count": set(),
            "latencies": [], "error_count": 0,
        })

        for log in all_logs:
            if group_by == "day":
                key = log.created_at.strftime("%Y-%m-%d")
            elif group_by == "module":
                key = log.module or "unknown"
            elif group_by == "department":
                key = log.department or "unknown"
            else:
                key = log.created_at.strftime("%Y-%m-%d")

            entry = breakdown_map[key]
            entry["call_count"] += 1
            if log.patient_id:
                entry["patient_count"].add(log.patient_id)
            if log.doctor_id:
                entry["doctor_count"].add(log.doctor_id)
            if log.latency_ms is not None:
                entry["latencies"].append(log.latency_ms)
            if log.error_message:
                entry["error_count"] += 1

        breakdown = []
        for period, data in breakdown_map.items():
            avg_lat = None
            if data["latencies"]:
                avg_lat = int(sum(data["latencies"]) / len(data["latencies"]))
            entry = {
                "period": period,
                "call_count": data["call_count"],
                "patient_count": len(data["patient_count"]),
                "doctor_count": len(data["doctor_count"]),
                "avg_latency_ms": avg_lat,
                "error_count": data["error_count"],
            }
            if req.department:
                entry["department"] = req.department
            if req.module:
                entry["module"] = req.module
            breakdown.append(entry)

        breakdown.sort(key=lambda x: x["period"])

        return {
            "total_calls": total_calls,
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "total_errors": total_errors,
            "avg_latency_ms": avg_latency,
            "breakdown": breakdown,
        }

    @staticmethod
    def get_dashboard_stats(
        db: Session, days: int = 30
    ) -> Dict[str, Any]:
        now = datetime.utcnow()
        start_date = now - timedelta(days=days)

        all_logs = (
            db.query(AuditLog)
            .filter(and_(AuditLog.created_at >= start_date, AuditLog.created_at <= now))
            .all()
        )

        total_calls = len(all_logs)
        total_patients = len({l.patient_id for l in all_logs if l.patient_id})
        active_doctors = len({l.doctor_id for l in all_logs if l.doctor_id})

        latencies = [l.latency_ms for l in all_logs if l.latency_ms is not None]
        avg_response_time = int(sum(latencies) / len(latencies)) if latencies else None

        total_errors = len([l for l in all_logs if l.error_message])
        error_rate = round(total_errors / total_calls * 100, 2) if total_calls > 0 else 0.0

        module_calls = defaultdict(int)
        for log in all_logs:
            module_calls[log.module or "system"] += 1

        top_modules = []
        for mod, count in sorted(module_calls.items(), key=lambda x: -x[1])[:7]:
            top_modules.append({
                "module": mod,
                "module_name": AuditService.MODULE_NAMES.get(mod, mod),
                "call_count": count,
                "call_percentage": round(count / total_calls * 100, 1) if total_calls > 0 else 0.0,
            })

        dept_calls = defaultdict(lambda: {"calls": 0, "patients": set()})
        for log in all_logs:
            dept = log.department or "未指定"
            dept_calls[dept]["calls"] += 1
            if log.patient_id:
                dept_calls[dept]["patients"].add(log.patient_id)

        top_departments = []
        for dept, data in sorted(dept_calls.items(), key=lambda x: -x[1]["calls"])[:7]:
            top_departments.append({
                "department": dept,
                "call_count": data["calls"],
                "patient_count": len(data["patients"]),
                "call_percentage": round(data["calls"] / total_calls * 100, 1) if total_calls > 0 else 0.0,
            })

        return {
            "period_start": start_date,
            "period_end": now,
            "total_calls": total_calls,
            "total_patients": total_patients,
            "active_doctors": active_doctors,
            "avg_response_time_ms": avg_response_time,
            "error_rate": error_rate,
            "top_modules": top_modules,
            "top_departments": top_departments,
        }
