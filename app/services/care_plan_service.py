from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.plan_followup import CarePlan
from app.models.risk_alert import RiskAssessment
from app.models.records import LabRecord, VitalSign, MedicationRecord
from app.models.patient import Patient, Visit
from app.schemas.plan_followup import CarePlanCreate, CarePlanUpdate, CarePlanGenerateRequest


class CarePlanService:
    EXAM_RULES = {
        "heart_failure": [
            {"code": "NT_proBNP", "name": "NT-proBNP", "priority": "required", "reason": "心衰诊断及预后评估核心指标"},
            {"code": "echocardiogram", "name": "超声心动图", "priority": "required", "reason": "评估射血分数及心室结构"},
            {"code": "ECG", "name": "12导联心电图", "priority": "required", "reason": "筛查心律失常和心肌缺血"},
            {"code": "CBC", "name": "血常规", "priority": "recommended", "reason": "排除贫血等加重因素"},
            {"code": "renal_electrolyte", "name": "肾功能+电解质", "priority": "required", "reason": "药物治疗前基线评估"},
            {"code": "liver_function", "name": "肝功能", "priority": "recommended", "reason": "基线评估及药物监测"},
            {"code": "chest_xray", "name": "胸部X线", "priority": "recommended", "reason": "评估肺淤血及心影大小"},
            {"code": "cardiac_MRI", "name": "心脏磁共振", "priority": "optional", "reason": "超声显像不佳时进一步评估"},
        ],
        "atrial_fibrillation": [
            {"code": "ECG", "name": "12导联心电图", "priority": "required", "reason": "房颤确诊及节律评估"},
            {"code": "echocardiogram", "name": "超声心动图", "priority": "required", "reason": "评估瓣膜病、左房大小及心功能"},
            {"code": "thyroid_function", "name": "甲状腺功能", "priority": "recommended", "reason": "排查甲亢诱发因素"},
            {"code": "renal_electrolyte", "name": "肾功能+电解质", "priority": "required", "reason": "抗凝/抗心律失常药物基线"},
            {"code": "CBC", "name": "血常规", "priority": "recommended", "reason": "抗凝前基线评估"},
            {"code": "liver_function", "name": "肝功能", "priority": "recommended", "reason": "药物治疗基线"},
            {"code": "holter", "name": "24h动态心电图", "priority": "recommended", "reason": "评估心率负荷及静默房颤"},
            {"code": "echo_TEE", "name": "经食管超声", "priority": "conditional", "reason": "复律前排除左房血栓"},
        ],
        "coronary_artery_disease": [
            {"code": "ECG", "name": "12导联心电图", "priority": "required", "reason": "心肌缺血/梗死征象评估"},
            {"code": "troponin", "name": "肌钙蛋白I/T", "priority": "required", "reason": "急性冠脉综合征确诊"},
            {"code": "CK_MB", "name": "CK-MB", "priority": "recommended", "reason": "辅助判断心肌损伤"},
            {"code": "echocardiogram", "name": "超声心动图", "priority": "required", "reason": "室壁运动及心功能评估"},
            {"code": "lipid_profile", "name": "血脂四项", "priority": "required", "reason": "危险因素及他汀治疗基线"},
            {"code": "coronary_angiography", "name": "冠脉造影", "priority": "conditional", "reason": "明确冠脉病变，指导血运重建"},
            {"code": "coronary_CTA", "name": "冠脉CTA", "priority": "optional", "reason": "低中度可疑患者的无创筛查"},
            {"code": "stress_test", "name": "运动负荷试验", "priority": "optional", "reason": "中低危患者缺血评估"},
            {"code": "renal_electrolyte", "name": "肾功能+电解质", "priority": "recommended", "reason": "造影剂及药物使用前评估"},
        ],
        "comprehensive": [
            {"code": "ECG", "name": "12导联心电图", "priority": "required", "reason": "心脏基础评估"},
            {"code": "echocardiogram", "name": "超声心动图", "priority": "recommended", "reason": "心脏结构功能评估"},
            {"code": "lipid_profile", "name": "血脂四项", "priority": "required", "reason": "冠心病风险评估"},
            {"code": "renal_electrolyte", "name": "肾功能+电解质", "priority": "recommended", "reason": "用药安全评估"},
            {"code": "liver_function", "name": "肝功能", "priority": "recommended", "reason": "基线评估"},
            {"code": "CBC", "name": "血常规", "priority": "recommended", "reason": "全身状况评估"},
            {"code": "glucose", "name": "空腹血糖", "priority": "recommended", "reason": "糖尿病筛查"},
            {"code": "BNP", "name": "BNP/NT-proBNP", "priority": "optional", "reason": "心衰筛查"},
        ],
    }

    DRUG_CLASS_CHECKLIST = {
        "ACEI_ARNI": [
            {"drug_class": "ACEI/ARNI", "status": "recommended", "indication": "HFrEF (EF<40%)", "check_points": ["血压监测", "肾功能监测", "血钾监测", "干咳/血管性水肿不良反应"]},
        ],
        "BetaBlocker": [
            {"drug_class": "β受体阻滞剂", "status": "recommended", "indication": "HFrEF、心梗后、心绞痛、房颤心率控制", "check_points": ["心率(目标55-60bpm)", "避免骤然停药", "哮喘/传导阻滞慎用", "液体潴留监测"]},
        ],
        "MRA": [
            {"drug_class": "醛固酮受体拮抗剂", "status": "recommended", "indication": "HFrEF (EF<35%)、心梗后EF降低", "check_points": ["血钾(目标<5.0)", "eGFR>30才可使用", "避免补钾剂联用"]},
        ],
        "SGLT2i": [
            {"drug_class": "SGLT2抑制剂", "status": "recommended", "indication": "全类型心衰(EF降低/轻度降低/保留)", "check_points": ["eGFR阈值", "泌尿生殖道感染", "酮症酸中毒风险", "血容量不足"]},
        ],
        "LoopDiuretics": [
            {"drug_class": "袢利尿剂", "status": "conditional", "indication": "心衰伴体液潴留", "check_points": ["体重监测(每日±1kg)", "电解质(低钾/低钠)", "肾功能", "尿量监测"]},
        ],
        "Anticoagulants": [
            {"drug_class": "口服抗凝剂", "status": "conditional", "indication": "房颤CHA₂DS₂-VASc≥2分、机械瓣、DVT/PE", "check_points": ["NOAC vs 华法林选择", "INR监测(华法林 2.0-3.0)", "出血风险评估(HAS-BLED)", "依从性评估"]},
        ],
        "Antiplatelets": [
            {"drug_class": "抗血小板药物", "status": "recommended", "indication": "ACS、冠脉支架、二级预防", "check_points": ["DAPT时长评估", "PPI联用保护胃黏膜", "出血倾向监测", "避免与NSAIDs联用"]},
        ],
        "Statins": [
            {"drug_class": "他汀类", "status": "recommended", "indication": "CAD、ACS、血脂异常、高危一级预防", "check_points": ["LDL-C达标评估", "肝功能监测", "肌痛/CK监测", "药物相互作用"]},
        ],
        "Nitrates": [
            {"drug_class": "硝酸酯类", "status": "conditional", "indication": "心绞痛症状缓解", "check_points": ["避免与PDE5抑制剂联用", "耐药性(需空白期)", "头痛不良反应", "低血压风险"]},
        ],
        "Antiarrhythmics": [
            {"drug_class": "抗心律失常药", "status": "conditional", "indication": "房颤复律/维持、室性心律失常", "check_points": ["胺碘酮:甲状腺/肺/肝功能监测", "ICD评估指征", "QT间期监测(Ⅲ类)", "促心律失常风险"]},
        ],
    }

    @staticmethod
    def _generate_exam_suggestions(
        risk_summaries: Dict[str, Any],
        existing_labs: List[LabRecord],
        plan_type: str,
    ) -> List[Dict[str, Any]]:
        suggestions = []
        existing_codes = {lab.test_code: lab.record_time for lab in existing_labs}

        exam_types = [plan_type] if plan_type in CarePlanService.EXAM_RULES else ["comprehensive"]
        for rtype, rlevel in risk_summaries.items():
            if rtype in CarePlanService.EXAM_RULES and rtype not in exam_types:
                exam_types.append(rtype)

        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=30)

        for exam_type in exam_types:
            for rule in CarePlanService.EXAM_RULES.get(exam_type, []):
                already_done = existing_codes.get(rule["code"])
                is_recent = already_done and already_done >= cutoff
                suggestions.append({
                    **rule,
                    "category": exam_type,
                    "last_done": already_done.isoformat() if already_done else None,
                    "is_recent": is_recent,
                    "recommendation": "建议执行" if not is_recent else "近期已完成，可酌情复查",
                })

        priority_order = {"required": 0, "recommended": 1, "conditional": 2, "optional": 3}
        suggestions.sort(key=lambda x: priority_order.get(x["priority"], 9))
        return suggestions

    @staticmethod
    def _generate_medication_checklist(
        risk_summaries: Dict[str, str],
        current_meds: List[MedicationRecord],
        ejection_fraction: Optional[float],
    ) -> List[Dict[str, Any]]:
        checklist = []
        med_names_lower = set()
        for m in current_meds:
            if m.is_active:
                med_names_lower.add((m.drug_name or "").lower())
                med_names_lower.add((m.generic_name or "").lower())

        hf_risk = risk_summaries.get("heart_failure", "")
        cad_risk = risk_summaries.get("coronary_artery_disease", "")
        af_risk = risk_summaries.get("atrial_fibrillation", "")

        key_classes = set()
        if hf_risk in ["高危", "极高危"] or (ejection_fraction is not None and ejection_fraction < 40):
            key_classes.update(["ACEI_ARNI", "BetaBlocker", "MRA", "SGLT2i", "LoopDiuretics"])
        if cad_risk in ["高危", "极高危"]:
            key_classes.update(["Antiplatelets", "Statins", "BetaBlocker", "Nitrates"])
        if af_risk in ["中危", "高危"]:
            key_classes.update(["Anticoagulants", "BetaBlocker", "Antiarrhythmics"])
        if not key_classes:
            key_classes.update(["Statins", "BetaBlocker"])

        for klass in key_classes:
            for item in CarePlanService.DRUG_CLASS_CHECKLIST.get(klass, []):
                in_use = False
                matched_meds = []
                for med in current_meds:
                    med_lower = (med.drug_name or "").lower()
                    if klass == "ACEI_ARNI" and any(k in med_lower for k in ["普利", "沙坦", "沙库巴曲", "pril", "sartan", "sacubitril"]):
                        in_use = True
                        matched_meds.append(med.drug_name)
                    elif klass == "BetaBlocker" and any(k in med_lower for k in ["洛尔", "olol"]):
                        in_use = True
                        matched_meds.append(med.drug_name)
                    elif klass == "MRA" and any(k in med_lower for k in ["螺内酯", "依普利酮", "spironolactone", "eplerenone"]):
                        in_use = True
                        matched_meds.append(med.drug_name)
                    elif klass == "SGLT2i" and any(k in med_lower for k in ["达格列净", "恩格列净", "卡格列净", "dapagliflozin", "empagliflozin", "canagliflozin"]):
                        in_use = True
                        matched_meds.append(med.drug_name)
                    elif klass == "LoopDiuretics" and any(k in med_lower for k in ["呋塞米", "托拉塞米", "布美他尼", "furosemide", "torasemide", "bumetanide"]):
                        in_use = True
                        matched_meds.append(med.drug_name)
                    elif klass == "Anticoagulants" and any(k in med_lower for k in ["华法林", "达比加群", "利伐沙班", "阿哌沙班", "warfarin", "dabigatran", "rivaroxaban", "apixaban"]):
                        in_use = True
                        matched_meds.append(med.drug_name)
                    elif klass == "Antiplatelets" and any(k in med_lower for k in ["阿司匹林", "氯吡格雷", "替格瑞洛", "aspirin", "clopidogrel", "ticagrelor"]):
                        in_use = True
                        matched_meds.append(med.drug_name)
                    elif klass == "Statins" and any(k in med_lower for k in ["他汀", "statin", "阿托伐", "瑞舒伐", "辛伐"]):
                        in_use = True
                        matched_meds.append(med.drug_name)
                    elif klass == "Nitrates" and any(k in med_lower for k in ["硝酸", "nitro", "异山梨酯"]):
                        in_use = True
                        matched_meds.append(med.drug_name)
                    elif klass == "Antiarrhythmics" and any(k in med_lower for k in ["胺碘酮", "普罗帕酮", "决奈达隆", "amiodarone", "propafenone", "dronedarone"]):
                        in_use = True
                        matched_meds.append(med.drug_name)

                checklist.append({
                    **item,
                    "current_usage": in_use,
                    "current_medications": matched_meds if matched_meds else None,
                    "action": "维持现有治疗，按核对点执行监测" if in_use else "评估是否需要起始该类药物治疗",
                })

        return checklist

    @staticmethod
    def generate_care_plan(db: Session, req: CarePlanGenerateRequest) -> CarePlan:
        from app.services.risk_engine_service import RiskEngineService
        from app.services.record_service import RecordService
        from app.models.risk_alert import Alert
        from datetime import datetime, timedelta

        patient_id = req.patient_id
        visit_id = req.visit_id

        risk_summaries = {}
        evidence_risks = []
        if req.include_risk_assessment:
            for atype in ["heart_failure", "atrial_fibrillation", "coronary_artery_disease"]:
                latest = RiskEngineService.get_latest_assessment(db, patient_id, atype)
                if latest:
                    if visit_id:
                        if latest.visit_id == visit_id:
                            risk_summaries[atype] = latest.risk_level
                            evidence_risks.append({
                                "id": latest.id,
                                "assessment_type": latest.assessment_type,
                                "risk_level": latest.risk_level,
                                "risk_score": latest.risk_score,
                                "assessment_date": latest.assessment_date.isoformat() if latest.assessment_date else None,
                            })
                    else:
                        risk_summaries[atype] = latest.risk_level
                        evidence_risks.append({
                            "id": latest.id,
                            "assessment_type": latest.assessment_type,
                            "risk_level": latest.risk_level,
                            "risk_score": latest.risk_score,
                            "assessment_date": latest.assessment_date.isoformat() if latest.assessment_date else None,
                        })

        existing_labs = RecordService.list_lab_records(db, patient_id, limit=500)
        if visit_id:
            visit_labs = [l for l in existing_labs if l.visit_id == visit_id]
            abnormal_labs = [l for l in visit_labs if l.is_abnormal]
        else:
            abnormal_labs = [l for l in existing_labs if l.is_abnormal]
            abnormal_labs = sorted(abnormal_labs, key=lambda x: x.record_time or x.created_at, reverse=True)[:20]
        evidence_abnormal_labs = [
            {
                "id": l.id,
                "test_code": l.test_code,
                "test_name": l.test_name,
                "test_value": l.test_value,
                "test_unit": l.test_unit,
                "abnormal_flag": l.abnormal_flag,
                "reference_low": l.reference_low,
                "reference_high": l.reference_high,
                "record_time": l.record_time.isoformat() if l.record_time else None,
            }
            for l in abnormal_labs
        ]

        current_meds = RecordService.list_medications(db, patient_id, active_only=True)
        if visit_id:
            visit_meds = [m for m in current_meds if m.visit_id == visit_id]
        else:
            visit_meds = current_meds
        evidence_active_meds = [
            {
                "id": m.id,
                "drug_name": m.drug_name,
                "generic_name": m.generic_name,
                "dosage": m.dosage,
                "frequency": m.frequency,
                "route": m.route,
                "start_date": m.start_date.isoformat() if m.start_date else None,
                "drug_category": m.drug_category,
            }
            for m in visit_meds
        ]

        unresolved_alerts_query = db.query(Alert).filter(
            Alert.patient_id == patient_id,
            Alert.is_resolved == False,
        )
        if visit_id:
            unresolved_alerts_query = unresolved_alerts_query.filter(Alert.visit_id == visit_id)
        unresolved_alerts = unresolved_alerts_query.order_by(Alert.alert_time.desc()).limit(50).all()
        evidence_unresolved_alerts = [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "alert_level": a.alert_level,
                "title": a.title,
                "content": a.content,
                "related_record_type": a.related_record_type,
                "related_record_id": a.related_record_id,
                "alert_time": a.alert_time.isoformat() if a.alert_time else None,
            }
            for a in unresolved_alerts
        ]

        latest_vs = RecordService.list_vital_signs(db, patient_id, limit=1)[0] if RecordService.list_vital_signs(db, patient_id, limit=1) else None

        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        ef = None
        for lab in existing_labs:
            if "ef" in (lab.test_code or "").lower() or "射血" in (lab.test_name or ""):
                try:
                    ef = float(lab.test_value)
                    break
                except (ValueError, TypeError):
                    pass

        exam_suggestions = CarePlanService._generate_exam_suggestions(
            risk_summaries, existing_labs, req.plan_type
        )

        medication_checklist = CarePlanService._generate_medication_checklist(
            risk_summaries, current_meds, ef
        ) if req.include_medication_check else []

        lifestyle_recs = []
        dietary_recs = []
        exercise_recs = []

        if patient:
            if patient.smoking:
                lifestyle_recs.append("强烈建议戒烟，戒烟可显著降低心血管事件风险")
            if patient.drinking:
                lifestyle_recs.append("限制酒精摄入，每日酒精量男性<25g，女性<15g")
        lifestyle_recs.append("保证充足睡眠(7-8小时/日)，避免熬夜和过度劳累")
        lifestyle_recs.append("心理压力管理，保持情绪稳定")

        hf_risk = risk_summaries.get("heart_failure")
        if hf_risk in ["高危", "极高危"]:
            dietary_recs.append("严格限钠: <2g钠/日(约<5g食盐)")
            dietary_recs.append("限制液体入量: 1500-2000mL/日，记录24h出入量")
        else:
            dietary_recs.append("中等限钠: <3g钠/日(约<7.5g食盐)")
        dietary_recs.append("DASH饮食: 富钾低钠，多蔬果全谷物，低脂乳制品")
        dietary_recs.append("减少饱和脂肪和反式脂肪摄入，增加Omega-3脂肪酸")
        dietary_recs.append("控制总热量，维持健康体重(BMI 18.5-23.9)")

        cad_risk = risk_summaries.get("coronary_artery_disease")
        if hf_risk in ["极高危"]:
            exercise_recs.append("急性期卧床休息，症状稳定后在监护下逐步开始活动")
        elif hf_risk == "高危":
            exercise_recs.append("心脏康复训练，从低强度开始，如床边坐起、慢走5-10分钟/次")
        elif hf_risk:
            exercise_recs.append("规律有氧运动: 快走30min×5次/周，可叠加阻力训练")
        elif cad_risk in ["极高危", "高危"]:
            exercise_recs.append("心脏康复计划，监护下中等强度有氧运动")
        else:
            exercise_recs.append("中等强度有氧运动 150min/周 + 阻力训练 2次/周")

        treatment_notes = []
        if risk_summaries:
            for rtype, rlevel in risk_summaries.items():
                name_map = {"heart_failure": "心衰", "atrial_fibrillation": "房颤", "coronary_artery_disease": "冠心病"}
                treatment_notes.append(f"【{name_map.get(rtype, rtype)}】风险等级: {rlevel}，需按对应路径管理")
        else:
            treatment_notes.append("暂无风险分层记录，建议完善评估后制定个体化方案")

        evidence_summary = {
            "generated_at": datetime.utcnow().isoformat(),
            "visit_id": visit_id,
            "risk_assessments": evidence_risks,
            "abnormal_labs": evidence_abnormal_labs,
            "active_medications": evidence_active_meds,
            "unresolved_alerts": evidence_unresolved_alerts,
            "latest_vital_sign": {
                "id": latest_vs.id,
                "systolic_bp": latest_vs.systolic_bp,
                "diastolic_bp": latest_vs.diastolic_bp,
                "heart_rate": latest_vs.heart_rate,
                "record_time": latest_vs.record_time.isoformat() if latest_vs.record_time else None,
            } if latest_vs else None,
            "patient_profile": {
                "age": (datetime.now().date() - patient.birth_date).days // 365 if patient and patient.birth_date else None,
                "gender": patient.gender if patient else None,
                "smoking": patient.smoking if patient else None,
                "drinking": patient.drinking if patient else None,
                "allergy_history": patient.allergy_history if patient else None,
                "past_medical_history": patient.past_medical_history if patient else None,
            } if patient else None,
        }

        care_plan = CarePlan(
            patient_id=patient_id,
            visit_id=visit_id,
            plan_type=req.plan_type,
            plan_date=datetime.utcnow(),
            status="draft",
            exam_suggestions=exam_suggestions,
            medication_checklist=medication_checklist,
            treatment_notes="\n".join(treatment_notes),
            lifestyle_recommendations="\n".join(lifestyle_recs),
            dietary_recommendations="\n".join(dietary_recs),
            exercise_recommendations="\n".join(exercise_recs),
            risk_assessment_summary=risk_summaries if risk_summaries else None,
            evidence_risk_ids=[r["id"] for r in evidence_risks],
            evidence_abnormal_lab_ids=[r["id"] for r in evidence_abnormal_labs],
            evidence_active_med_ids=[r["id"] for r in evidence_active_meds],
            evidence_unresolved_alert_ids=[r["id"] for r in evidence_unresolved_alerts],
            evidence_summary=evidence_summary,
            author_id=req.author_id,
        )
        db.add(care_plan)
        db.commit()
        db.refresh(care_plan)
        return care_plan

    @staticmethod
    def create_care_plan(db: Session, plan_in: CarePlanCreate) -> CarePlan:
        plan = CarePlan(**plan_in.model_dump())
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    @staticmethod
    def update_care_plan(db: Session, plan_id: int, plan_in: CarePlanUpdate) -> Optional[CarePlan]:
        plan = db.query(CarePlan).filter(CarePlan.id == plan_id).first()
        if not plan:
            return None
        update_data = plan_in.model_dump(exclude_unset=True)
        if "status" in update_data and update_data["status"] in ["reviewed", "approved"] and not plan.review_time:
            plan.review_time = datetime.utcnow()
        for key, value in update_data.items():
            setattr(plan, key, value)
        plan.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(plan)
        return plan

    @staticmethod
    def list_care_plans(db: Session, patient_id: int, limit: int = 50) -> List[CarePlan]:
        return (
            db.query(CarePlan)
            .filter(CarePlan.patient_id == patient_id)
            .order_by(CarePlan.plan_date.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_care_plan(db: Session, plan_id: int) -> Optional[CarePlan]:
        return db.query(CarePlan).filter(CarePlan.id == plan_id).first()

    @staticmethod
    def convert_plan_to_follow_up(
        db: Session,
        plan_id: int,
        req: "CarePlanToFollowUpRequest",
    ) -> "FollowUp":
        from app.models.plan_followup import FollowUp
        from app.schemas.plan_followup import FollowUpCreate
        from datetime import timedelta

        plan = CarePlanService.get_care_plan(db, plan_id)
        if not plan:
            raise ValueError("方案不存在")

        purpose = req.purpose
        suggestions = plan.exam_suggestions or []
        matched_idx = None

        if req.from_exam_index is not None:
            if 0 <= req.from_exam_index < len(suggestions):
                matched_idx = req.from_exam_index
        else:
            for i, s in enumerate(suggestions):
                txt = f"{s.get('test_name','')} {s.get('purpose','')} {s.get('description','')}"
                if any(k in txt for k in ["复诊", "复查", "随访", "return", "follow"]):
                    matched_idx = i
                    break
            if matched_idx is None and suggestions:
                matched_idx = 0

        if matched_idx is not None and not purpose:
            s = suggestions[matched_idx]
            parts = []
            if s.get("test_name"):
                parts.append(str(s["test_name"]))
            if s.get("purpose"):
                parts.append(str(s["purpose"]))
            if s.get("description"):
                parts.append(str(s["description"]))
            purpose = " | ".join(parts) if parts else (plan.plan_type or "方案") + "复诊"
        if not purpose:
            purpose = (plan.plan_type or "方案") + "复诊"

        if req.scheduled_date:
            scheduled = req.scheduled_date
        else:
            base = plan.plan_date or plan.created_at
            scheduled = base + timedelta(days=req.days_after or 14)

        fu_in = FollowUpCreate(
            patient_id=plan.patient_id,
            visit_id=plan.visit_id,
            follow_up_type=req.follow_up_type or "clinic",
            scheduled_date=scheduled,
            purpose=f"[方案#{plan.id}] {purpose}",
            assigned_doctor_id=req.assigned_doctor_id or plan.author_id,
        )
        fu = FollowUp(**fu_in.model_dump())
        fu.status = "scheduled"
        db.add(fu)
        db.commit()
        db.refresh(fu)
        return fu

    @staticmethod
    def get_audit_statistics(db: Session, period_days: int = 30) -> Dict[str, Any]:
        from app.models.risk_alert import Alert
        from app.models.plan_followup import FollowUp
        from datetime import datetime, timedelta, timezone

        since = datetime.utcnow() - timedelta(days=period_days)

        alerts_q = db.query(Alert).filter(Alert.created_at >= since)
        all_alerts = alerts_q.all()
        alerts_total = len(all_alerts)
        alerts_read = sum(1 for a in all_alerts if a.is_read)
        alerts_resolved = sum(1 for a in all_alerts if a.is_resolved)
        alerts_unresolved = alerts_total - alerts_resolved
        alerts_by_type = {}
        for a in all_alerts:
            alerts_by_type[a.alert_type] = alerts_by_type.get(a.alert_type, 0) + 1
        alerts_by_level = {}
        for a in all_alerts:
            alerts_by_level[a.alert_level] = alerts_by_level.get(a.alert_level, 0) + 1

        fus_q = db.query(FollowUp).filter(FollowUp.created_at >= since)
        all_fus = fus_q.all()
        fu_total = len(all_fus)
        fu_scheduled = sum(1 for f in all_fus if f.status == "scheduled")
        fu_completed = sum(1 for f in all_fus if f.status == "completed")
        fu_missed = sum(1 for f in all_fus if f.status == "missed")
        fu_cancelled = sum(1 for f in all_fus if f.status == "cancelled")
        fu_overdue = sum(1 for f in all_fus if f.status == "scheduled" and f.scheduled_date and f.scheduled_date < datetime.utcnow())

        plans_q = db.query(CarePlan).filter(CarePlan.created_at >= since)
        all_plans = plans_q.all()
        plan_total = len(all_plans)
        plans_by_status = {}
        for p in all_plans:
            plans_by_status[p.status or "draft"] = plans_by_status.get(p.status or "draft", 0) + 1
        plan_draft = sum(1 for p in all_plans if (p.status or "draft") == "draft")
        plan_issued = sum(1 for p in all_plans if p.status in {"reviewed", "approved", "signed", "issued"})

        def _pct(num, den):
            return round(num * 100.0 / den, 2) if den > 0 else 0.0

        return {
            "period_days": period_days,
            "alerts": {
                "total": alerts_total,
                "read": alerts_read,
                "read_rate_pct": _pct(alerts_read, alerts_total),
                "resolved": alerts_resolved,
                "unresolved": alerts_unresolved,
                "resolve_rate_pct": _pct(alerts_resolved, alerts_total),
                "by_type": alerts_by_type,
                "by_level": alerts_by_level,
            },
            "follow_ups": {
                "total": fu_total,
                "scheduled": fu_scheduled,
                "completed": fu_completed,
                "missed": fu_missed,
                "cancelled": fu_cancelled,
                "overdue": fu_overdue,
                "complete_rate_pct": _pct(fu_completed, fu_total),
            },
            "care_plans": {
                "total": plan_total,
                "draft": plan_draft,
                "issued": plan_issued,
                "by_status": plans_by_status,
            },
        }
