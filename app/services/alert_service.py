from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.risk_alert import Alert
from app.models.records import VitalSign, LabRecord, MedicationRecord
from app.schemas.records import VitalSignCreate, LabRecordCreate, MedicationRecordCreate
from app.schemas.risk_alert import AlertCreate, AlertUpdate


class AlertRuleService:
    CRITICAL_VS_THRESHOLDS = {
        "systolic_bp": {"low": 90, "high": 180, "critical_low": 80, "critical_high": 220},
        "diastolic_bp": {"low": 60, "high": 110, "critical_low": 50, "critical_high": 140},
        "heart_rate": {"low": 50, "high": 120, "critical_low": 40, "critical_high": 160},
        "oxygen_saturation": {"low": 92, "critical_low": 88},
    }

    CRITICAL_LAB_THRESHOLDS = {
        "troponin_i": {"high": 0.04, "critical_high": 0.4, "unit": "ng/mL"},
        "troponin_t": {"high": 0.01, "critical_high": 0.1, "unit": "ng/mL"},
        "bnp": {"high": 100, "critical_high": 1000, "unit": "pg/mL"},
        "nt_probnp": {"high": 125, "critical_high": 5000, "unit": "pg/mL"},
        "ck_mb": {"high": 25, "critical_high": 100, "unit": "U/L"},
        "myoglobin": {"high": 90, "critical_high": 500, "unit": "ng/mL"},
        "d_dimer": {"high": 0.5, "critical_high": 5, "unit": "mg/L"},
        "potassium": {"low": 3.5, "high": 5.5, "critical_low": 2.8, "critical_high": 6.5, "unit": "mmol/L"},
        "sodium": {"low": 135, "high": 147, "critical_low": 120, "critical_high": 160, "unit": "mmol/L"},
        "creatinine": {"high": 1.3, "critical_high": 3.5, "unit": "mg/dL"},
        "hemoglobin": {"low": 120, "critical_low": 70, "unit": "g/L"},
        "lactate": {"high": 2, "critical_high": 4, "unit": "mmol/L"},
    }

    CONTRAINDICATION_RULES = [
        {
            "category": "硝酸酯类_西地那非",
            "drugs": ["nitroglycerin", "nitroglycerine", "硝酸甘油", "单硝酸异山梨酯", "isosorbide"],
            "contraindicated_with": ["sildenafil", "西地那非", "tadalafil", "他达拉非", "vardenafil", "伐地那非"],
            "alert_level": "critical",
            "reason": "合用可导致严重低血压，危及生命",
        },
        {
            "category": "华法林_NSAIDs",
            "drugs": ["warfarin", "华法林"],
            "contraindicated_with": ["ibuprofen", "布洛芬", "diclofenac", "双氯芬酸", "naproxen", "萘普生", "indomethacin", "吲哚美辛"],
            "alert_level": "high",
            "reason": "增加出血风险，需严密监测INR",
        },
        {
            "category": "ACEI_ARB_联用",
            "drugs": ["captopril", "卡托普利", "enalapril", "依那普利", "lisinopril", "赖诺普利", "ramipril", "雷米普利", "perindopril", "培哚普利"],
            "contraindicated_with": ["valsartan", "缬沙坦", "losartan", "氯沙坦", "irbesartan", "厄贝沙坦", "telmisartan", "替米沙坦", "olmesartan", "奥美沙坦", "sacubitril", "沙库巴曲"],
            "alert_level": "high",
            "reason": "ACEI与ARB/ARNI联用增加肾损伤和高钾血症风险，不推荐",
        },
        {
            "category": "β受体阻滞剂_严重心动过缓",
            "drugs": ["metoprolol", "美托洛尔", "bisoprolol", "比索洛尔", "carvedilol", "卡维地洛", "atenolol", "阿替洛尔"],
            "conditions": ["severe_bradycardia", "advanced_av_block"],
            "alert_level": "high",
            "reason": "可能加重传导阻滞或心动过缓",
        },
        {
            "category": "地高辛_高钙血症",
            "drugs": ["digoxin", "地高辛"],
            "conditions": ["hypercalcemia", "hypokalemia"],
            "alert_level": "high",
            "reason": "电解质紊乱增加地高辛中毒风险",
        },
        {
            "category": "螺内酯_补钾剂",
            "drugs": ["spironolactone", "螺内酯", "eplerenone", "依普利酮"],
            "contraindicated_with": ["potassium chloride", "氯化钾", "potassium citrate", "枸橼酸钾"],
            "alert_level": "high",
            "reason": "MRA联合补钾剂显著增加高钾血症风险",
        },
    ]

    @staticmethod
    def _create_alert(
        db: Session,
        patient_id: int,
        visit_id: Optional[int],
        alert_type: str,
        alert_level: str,
        title: str,
        content: str,
        related_record_type: Optional[str] = None,
        related_record_id: Optional[int] = None,
    ) -> Alert:
        alert = Alert(
            patient_id=patient_id,
            visit_id=visit_id,
            alert_type=alert_type,
            alert_level=alert_level,
            alert_time=datetime.utcnow(),
            title=title,
            content=content,
            related_record_type=related_record_type,
            related_record_id=related_record_id,
        )
        db.add(alert)
        db.flush()
        return alert

    @staticmethod
    def check_vital_signs(db: Session, vs: VitalSign) -> List[Alert]:
        alerts = []
        patient_id = vs.patient_id
        visit_id = vs.visit_id

        checks = [
            ("systolic_bp", vs.systolic_bp, "收缩压"),
            ("diastolic_bp", vs.diastolic_bp, "舒张压"),
            ("heart_rate", vs.heart_rate, "心率"),
            ("oxygen_saturation", vs.oxygen_saturation, "血氧饱和度"),
        ]

        for param_name, value, display_name in checks:
            if value is None:
                continue
            thresholds = AlertRuleService.CRITICAL_VS_THRESHOLDS.get(param_name, {})

            if "critical_low" in thresholds and value < thresholds["critical_low"]:
                alerts.append(AlertRuleService._create_alert(
                    db, patient_id, visit_id,
                    alert_type="critical_value",
                    alert_level="critical",
                    title=f"危急值: {display_name}过低",
                    content=f"{display_name} = {value}，低于危急值阈值 {thresholds['critical_low']}，请立即处理！",
                    related_record_type="vital_sign",
                    related_record_id=vs.id,
                ))
            elif "critical_high" in thresholds and value > thresholds["critical_high"]:
                alerts.append(AlertRuleService._create_alert(
                    db, patient_id, visit_id,
                    alert_type="critical_value",
                    alert_level="critical",
                    title=f"危急值: {display_name}过高",
                    content=f"{display_name} = {value}，高于危急值阈值 {thresholds['critical_high']}，请立即处理！",
                    related_record_type="vital_sign",
                    related_record_id=vs.id,
                ))
            elif "low" in thresholds and value < thresholds["low"]:
                alerts.append(AlertRuleService._create_alert(
                    db, patient_id, visit_id,
                    alert_type="abnormal_value",
                    alert_level="high",
                    title=f"异常: {display_name}偏低",
                    content=f"{display_name} = {value}，低于正常下限 {thresholds['low']}，请关注。",
                    related_record_type="vital_sign",
                    related_record_id=vs.id,
                ))
            elif "high" in thresholds and value > thresholds["high"]:
                alerts.append(AlertRuleService._create_alert(
                    db, patient_id, visit_id,
                    alert_type="abnormal_value",
                    alert_level="high",
                    title=f"异常: {display_name}偏高",
                    content=f"{display_name} = {value}，高于正常上限 {thresholds['high']}，请关注。",
                    related_record_type="vital_sign",
                    related_record_id=vs.id,
                ))

        if alerts:
            db.commit()
            for a in alerts:
                db.refresh(a)
        return alerts

    @staticmethod
    def check_lab_record(db: Session, lab: LabRecord) -> List[Alert]:
        alerts = []
        patient_id = lab.patient_id
        visit_id = lab.visit_id

        test_code = (lab.test_code or "").lower()
        test_name = (lab.test_name or "").lower()

        matched_key = None
        for key in AlertRuleService.CRITICAL_LAB_THRESHOLDS:
            if key in test_code or key in test_name:
                matched_key = key
                break

        if matched_key:
            thresholds = AlertRuleService.CRITICAL_LAB_THRESHOLDS[matched_key]
            value = lab.test_value
            unit = thresholds.get("unit", lab.test_unit or "")

            if "critical_high" in thresholds and value > thresholds["critical_high"]:
                alerts.append(AlertRuleService._create_alert(
                    db, patient_id, visit_id,
                    alert_type="critical_value",
                    alert_level="critical",
                    title=f"危急值: {lab.test_name}显著升高",
                    content=f"{lab.test_name} = {value}{unit}，高于危急值阈值 {thresholds['critical_high']}{unit}，请立即处理！",
                    related_record_type="lab_record",
                    related_record_id=lab.id,
                ))
            elif "high" in thresholds and value > thresholds["high"]:
                alerts.append(AlertRuleService._create_alert(
                    db, patient_id, visit_id,
                    alert_type="abnormal_value",
                    alert_level="high",
                    title=f"异常: {lab.test_name}升高",
                    content=f"{lab.test_name} = {value}{unit}，高于参考上限 {thresholds['high']}{unit}。",
                    related_record_type="lab_record",
                    related_record_id=lab.id,
                ))

            if "critical_low" in thresholds and value < thresholds["critical_low"]:
                alerts.append(AlertRuleService._create_alert(
                    db, patient_id, visit_id,
                    alert_type="critical_value",
                    alert_level="critical",
                    title=f"危急值: {lab.test_name}显著降低",
                    content=f"{lab.test_name} = {value}{unit}，低于危急值阈值 {thresholds['critical_low']}{unit}，请立即处理！",
                    related_record_type="lab_record",
                    related_record_id=lab.id,
                ))
            elif "low" in thresholds and value < thresholds["low"]:
                alerts.append(AlertRuleService._create_alert(
                    db, patient_id, visit_id,
                    alert_type="abnormal_value",
                    alert_level="high",
                    title=f"异常: {lab.test_name}降低",
                    content=f"{lab.test_name} = {value}{unit}，低于参考下限 {thresholds['low']}{unit}。",
                    related_record_type="lab_record",
                    related_record_id=lab.id,
                ))

        if lab.is_abnormal and not alerts:
            alerts.append(AlertRuleService._create_alert(
                db, patient_id, visit_id,
                alert_type="abnormal_value",
                alert_level="medium",
                title=f"检验异常: {lab.test_name}",
                content=f"{lab.test_name} = {lab.test_value}{lab.test_unit or ''}，{lab.abnormal_flag or '异常'}，参考范围 {lab.reference_low or '-'}-{lab.reference_high or '-'}。",
                related_record_type="lab_record",
                related_record_id=lab.id,
            ))

        if alerts:
            db.commit()
            for a in alerts:
                db.refresh(a)
        return alerts

    @staticmethod
    def _med_names(med: MedicationRecord) -> set:
        return {(med.drug_name or "").lower(), (med.generic_name or "").lower()}

    @staticmethod
    def _match_any(name_set: set, keywords: List[str]) -> bool:
        return any(k.lower() in nm for k in keywords for nm in name_set)

    @staticmethod
    def check_medication_safety(
        db: Session,
        new_med: MedicationRecord,
        existing_meds: List[MedicationRecord],
        peer_meds: Optional[List[MedicationRecord]] = None,
        patient_conditions: Optional[List[str]] = None,
    ) -> List[Alert]:
        alerts = []
        patient_id = new_med.patient_id
        visit_id = new_med.visit_id
        patient_conditions = patient_conditions or []
        peer_meds = peer_meds or []

        new_names = AlertRuleService._med_names(new_med)
        new_med_id = new_med.id

        all_compare = []
        for m in existing_meds:
            if m.is_active and m.id != new_med_id:
                all_compare.append(("历史", m))
        for m in peer_meds:
            if m.is_active and m.id != new_med_id and m.patient_id == patient_id:
                all_compare.append(("本次同批", m))

        for rule in AlertRuleService.CONTRAINDICATION_RULES:
            rule_a = rule.get("drugs", [])
            rule_b = rule.get("contraindicated_with") or rule.get("conditions", [])
            has_condition_only = rule.get("conditions") and not rule.get("contraindicated_with")

            match_a_in_new = AlertRuleService._match_any(new_names, rule_a)
            match_b_in_new = AlertRuleService._match_any(new_names, rule_b) if not has_condition_only else False

            for source, other in all_compare:
                other_names = AlertRuleService._med_names(other)
                match_a_in_other = AlertRuleService._match_any(other_names, rule_a)
                match_b_in_other = AlertRuleService._match_any(other_names, rule_b) if not has_condition_only else False

                conflict = None
                if match_a_in_new and match_b_in_other:
                    conflict = f"新药【{new_med.drug_name}】与{source}用药【{other.drug_name}】"
                elif match_b_in_new and match_a_in_other:
                    conflict = f"新药【{new_med.drug_name}】与{source}用药【{other.drug_name}】"
                if conflict:
                    content = (
                        f"{conflict}存在配伍禁忌（类别: {rule['category']}）。\n"
                        f"组合: {', '.join(rule_a)} + {', '.join(rule_b)}\n"
                        f"原因: {rule['reason']}"
                    )
                    alerts.append(AlertRuleService._create_alert(
                        db, patient_id, visit_id,
                        alert_type="drug_contraindication",
                        alert_level=rule["alert_level"],
                        title=f"禁忌用药: {rule['category']}",
                        content=content,
                        related_record_type="medication",
                        related_record_id=new_med.id,
                    ))

            if has_condition_only and match_a_in_new:
                for cond in rule["conditions"]:
                    if cond in patient_conditions:
                        content = (
                            f"患者存在病情/指标[{cond}]，与新药【{new_med.drug_name}】存在禁忌（类别: {rule['category']}）。\n"
                            f"原因: {rule['reason']}"
                        )
                        alerts.append(AlertRuleService._create_alert(
                            db, patient_id, visit_id,
                            alert_type="drug_contraindication",
                            alert_level=rule["alert_level"],
                            title=f"用药禁忌: {rule['category']} - 病情不符",
                            content=content,
                            related_record_type="medication",
                            related_record_id=new_med.id,
                        ))
                        break

        seen_keys = set()
        dedup_alerts = []
        for a in alerts:
            key = (a.title, a.content[:150])
            if key not in seen_keys:
                seen_keys.add(key)
                dedup_alerts.append(a)

        if dedup_alerts:
            db.commit()
            for a in dedup_alerts:
                db.refresh(a)
        return dedup_alerts

    @staticmethod
    def check_batch_medication_safety(
        db: Session,
        all_new_meds: List[MedicationRecord],
    ) -> List[Alert]:
        from collections import defaultdict
        by_patient = defaultdict(list)
        for m in all_new_meds:
            by_patient[m.patient_id].append(m)

        all_alerts = []
        for patient_id, patient_meds in by_patient.items():
            history = (
                db.query(MedicationRecord)
                .filter(
                    MedicationRecord.patient_id == patient_id,
                    MedicationRecord.is_active == True,
                    MedicationRecord.id.notin_([m.id for m in patient_meds]),
                )
                .all()
            )
            for med in patient_meds:
                all_alerts.extend(
                    AlertRuleService.check_medication_safety(
                        db, med, history, peer_meds=patient_meds
                    )
                )
        return all_alerts

    @staticmethod
    def check_duplicate_exam(
        db: Session,
        patient_id: int,
        exam_type: str,
        exam_code: str,
        within_hours: int = 24,
        exclude_record_ids: Optional[List[int]] = None,
        new_record_id: Optional[int] = None,
    ) -> Optional[Alert]:
        if not exam_code:
            return None
        cutoff = datetime.utcnow() - timedelta(hours=within_hours)
        exclude_record_ids = exclude_record_ids or []

        if exam_type == "lab":
            query = db.query(LabRecord).filter(
                LabRecord.patient_id == patient_id,
                LabRecord.test_code == exam_code,
                LabRecord.record_time >= cutoff,
            )
            if exclude_record_ids:
                query = query.filter(LabRecord.id.notin_(exclude_record_ids))
            existing = query.order_by(LabRecord.record_time.desc()).first()

            if existing:
                dup_count = query.count()
                content = (
                    f"患者在{existing.record_time.strftime('%Y-%m-%d %H:%M')}"
                    f"已完成相同检验【{existing.test_name}】(值: {existing.test_value}{existing.test_unit or ''})，"
                    f"同期已有{dup_count}条同类记录，建议确认是否有必要重复。"
                )
                related_id = new_record_id if new_record_id is not None else existing.id
                visit_id = (
                    db.query(LabRecord.visit_id)
                    .filter(LabRecord.id == related_id)
                    .scalar()
                    if new_record_id is not None
                    else existing.visit_id
                )
                alert = AlertRuleService._create_alert(
                    db, patient_id, visit_id,
                    alert_type="duplicate_exam",
                    alert_level="medium",
                    title=f"重复检查提示: {existing.test_name}",
                    content=content,
                    related_record_type="lab_record",
                    related_record_id=related_id,
                )
                db.commit()
                db.refresh(alert)
                return alert
        return None

    @staticmethod
    def list_alerts(
        db: Session,
        patient_id: Optional[int] = None,
        alert_type: Optional[str] = None,
        alert_level: Optional[str] = None,
        unread_only: bool = False,
        unresolved_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[int, int, int, List[Alert]]:
        query = db.query(Alert)
        if patient_id:
            query = query.filter(Alert.patient_id == patient_id)
        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)
        if alert_level:
            query = query.filter(Alert.alert_level == alert_level)
        if unread_only:
            query = query.filter(Alert.is_read == False)
        if unresolved_only:
            query = query.filter(Alert.is_resolved == False)

        total = query.count()
        unread_count = query.filter(Alert.is_read == False).count()
        critical_count = query.filter(Alert.alert_level == "critical").count()

        items = query.order_by(Alert.alert_time.desc()).offset(skip).limit(limit).all()
        return total, unread_count, critical_count, items

    @staticmethod
    def update_alert(db: Session, alert_id: int, update_in: AlertUpdate) -> Optional[Alert]:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None
        update_data = update_in.model_dump(exclude_unset=True)

        if "is_read" in update_data and update_data["is_read"] and not alert.is_read:
            alert.read_time = datetime.utcnow()
        if "is_resolved" in update_data and update_data["is_resolved"] and not alert.is_resolved:
            alert.resolve_time = datetime.utcnow()

        for key, value in update_data.items():
            setattr(alert, key, value)

        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def run_all_checks(
        db: Session,
        patient_id: int,
        visit_id: Optional[int] = None,
        vital_sign: Optional[VitalSign] = None,
        lab_record: Optional[LabRecord] = None,
        medication: Optional[MedicationRecord] = None,
    ) -> List[Alert]:
        all_alerts = []

        if vital_sign:
            all_alerts.extend(AlertRuleService.check_vital_signs(db, vital_sign))

        if lab_record:
            all_alerts.extend(AlertRuleService.check_lab_record(db, lab_record))
            dup_alert = AlertRuleService.check_duplicate_exam(
                db, patient_id, "lab", lab_record.test_code or ""
            )
            if dup_alert:
                all_alerts.append(dup_alert)

        if medication:
            existing_meds = (
                db.query(MedicationRecord)
                .filter(MedicationRecord.patient_id == patient_id)
                .all()
            )
            all_alerts.extend(
                AlertRuleService.check_medication_safety(db, medication, existing_meds)
            )

        return all_alerts
