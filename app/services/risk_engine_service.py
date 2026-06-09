from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.risk_alert import RiskAssessment
from app.models.patient import Patient
from app.schemas.risk_alert import RiskAssessmentCreate


class RiskEngineService:
    ALGORITHM_VERSION = "v1.0"

    @staticmethod
    def calculate_heart_failure_risk(input_data: Dict[str, Any]) -> Tuple[str, float, Dict[str, Any]]:
        score_details = {}
        total_score = 0.0

        nyha_class = input_data.get("nyha_class", "")
        nyha_map = {"I": 1, "II": 2, "III": 3, "IV": 4}
        nyha_score = nyha_map.get(nyha_class, 0)
        score_details["nyha_class"] = {"value": nyha_class, "score": nyha_score}
        total_score += nyha_score * 2

        bnp = input_data.get("bnp")
        nt_probnp = input_data.get("nt_probnp")
        bnp_score = 0
        if bnp is not None:
            if bnp >= 1000:
                bnp_score = 4
            elif bnp >= 400:
                bnp_score = 3
            elif bnp >= 100:
                bnp_score = 2
            else:
                bnp_score = 1
            score_details["bnp"] = {"value": bnp, "unit": "pg/mL", "score": bnp_score}
        elif nt_probnp is not None:
            if nt_probnp >= 5000:
                bnp_score = 4
            elif nt_probnp >= 2000:
                bnp_score = 3
            elif nt_probnp >= 125:
                bnp_score = 2
            else:
                bnp_score = 1
            score_details["nt_probnp"] = {"value": nt_probnp, "unit": "pg/mL", "score": bnp_score}
        total_score += bnp_score * 1.5

        ejection_fraction = input_data.get("ejection_fraction")
        ef_score = 0
        if ejection_fraction is not None:
            if ejection_fraction < 30:
                ef_score = 4
            elif ejection_fraction < 40:
                ef_score = 3
            elif ejection_fraction < 50:
                ef_score = 2
            else:
                ef_score = 1
            score_details["ejection_fraction"] = {"value": ejection_fraction, "unit": "%", "score": ef_score}
        total_score += ef_score * 2

        creatinine = input_data.get("creatinine")
        renal_score = 0
        if creatinine is not None:
            if creatinine > 3.0:
                renal_score = 4
            elif creatinine > 2.0:
                renal_score = 3
            elif creatinine > 1.5:
                renal_score = 2
            elif creatinine > 1.2:
                renal_score = 1
            score_details["creatinine"] = {"value": creatinine, "unit": "mg/dL", "score": renal_score}
        total_score += renal_score

        sodium = input_data.get("sodium")
        sodium_score = 0
        if sodium is not None:
            if sodium < 130:
                sodium_score = 3
            elif sodium < 135:
                sodium_score = 2
            elif sodium < 137:
                sodium_score = 1
            score_details["sodium"] = {"value": sodium, "unit": "mmol/L", "score": sodium_score}
        total_score += sodium_score

        age = input_data.get("age", 0)
        age_score = 0
        if age >= 75:
            age_score = 3
        elif age >= 65:
            age_score = 2
        elif age >= 55:
            age_score = 1
        score_details["age"] = {"value": age, "score": age_score}
        total_score += age_score

        max_possible = 8.0 + 6.0 + 8.0 + 4.0 + 3.0 + 3.0
        normalized_score = min(round((total_score / max_possible) * 100, 1), 100.0)

        if normalized_score >= 70:
            risk_level = "极高危"
        elif normalized_score >= 50:
            risk_level = "高危"
        elif normalized_score >= 30:
            risk_level = "中危"
        elif normalized_score >= 15:
            risk_level = "低危"
        else:
            risk_level = "极低危"

        recommendations = RiskEngineService._get_hf_recommendations(risk_level, ejection_fraction, nyha_class)
        score_details["total_score"] = normalized_score
        score_details["recommendations"] = recommendations

        return risk_level, normalized_score, score_details

    @staticmethod
    def _get_hf_recommendations(risk_level: str, ef: Optional[float], nyha: str) -> str:
        recs = []
        if ef is not None and ef < 40:
            recs.append("HFrEF治疗: ACEI/ARB/ARNI + β受体阻滞剂 + MRA + SGLT2i四联疗法")
        elif ef is not None and 40 <= ef < 50:
            recs.append("HFmrEF治疗: 考虑ARNI/ACEI/ARB、β受体阻滞剂、MRA、SGLT2i")
        else:
            recs.append("HFpEF治疗: SGLT2i、MRAs、ARNI考虑使用")

        if risk_level in ["极高危", "高危"]:
            recs.append("建议紧急心内科会诊，考虑住院治疗")
            recs.append("严密监测生命体征、BNP/NT-proBNP动态变化")
        elif risk_level == "中危":
            recs.append("建议心内科专科评估，优化药物治疗方案")
            recs.append("1-2周内复诊，密切观察症状变化")
        elif risk_level == "低危":
            recs.append("继续当前治疗，定期门诊随访")
            recs.append("加强患者教育，监测体重变化")

        if nyha in ["III", "IV"]:
            recs.append("限制体力活动，必要时卧床休息")
            recs.append("严格限制钠水摄入(<2g钠/日)")

        return "; ".join(recs)

    @staticmethod
    def calculate_afib_risk(input_data: Dict[str, Any]) -> Tuple[str, float, Dict[str, Any]]:
        score_details = {}
        chads2_score = 0
        hasbled_score = 0

        age = input_data.get("age", 0)
        if age >= 75:
            chads2_score += 2
            hasbled_score += 1
            score_details["age_ge75"] = {"value": True, "chads2": 2, "hasbled": 1}
        elif age >= 65:
            chads2_score += 1
            score_details["age_65_74"] = {"value": True, "chads2": 1, "hasbled": 0}
        else:
            score_details["age_lt65"] = {"value": True, "chads2": 0, "hasbled": 0}

        if input_data.get("congestive_heart_failure"):
            chads2_score += 1
            hasbled_score += 1
        score_details["chf"] = {"value": input_data.get("congestive_heart_failure", False), "chads2": 1 if input_data.get("congestive_heart_failure") else 0, "hasbled": 1 if input_data.get("congestive_heart_failure") else 0}

        if input_data.get("hypertension"):
            chads2_score += 1
            hasbled_score += 1
        score_details["hypertension"] = {"value": input_data.get("hypertension", False), "chads2": 1 if input_data.get("hypertension") else 0, "hasbled": 1 if input_data.get("hypertension") else 0}

        if input_data.get("stroke_tia"):
            chads2_score += 2
            hasbled_score += 1
        score_details["stroke_tia"] = {"value": input_data.get("stroke_tia", False), "chads2": 2 if input_data.get("stroke_tia") else 0, "hasbled": 1 if input_data.get("stroke_tia") else 0}

        if input_data.get("diabetes"):
            chads2_score += 1
        score_details["diabetes"] = {"value": input_data.get("diabetes", False), "chads2": 1 if input_data.get("diabetes") else 0, "hasbled": 0}

        if input_data.get("vascular_disease"):
            chads2_score += 1
            hasbled_score += 1
        score_details["vascular_disease"] = {"value": input_data.get("vascular_disease", False), "chads2": 1 if input_data.get("vascular_disease") else 0, "hasbled": 1 if input_data.get("vascular_disease") else 0}

        gender = input_data.get("gender", "")
        if gender.lower() in ["female", "f", "女"]:
            chads2_score += 1
        score_details["female"] = {"value": gender.lower() in ["female", "f", "女"], "chads2": 1 if gender.lower() in ["female", "f", "女"] else 0, "hasbled": 0}

        if input_data.get("renal_dysfunction"):
            hasbled_score += 1
        if input_data.get("hepatic_dysfunction"):
            hasbled_score += 1
        if input_data.get("bleeding_history"):
            hasbled_score += 1
        if input_data.get("lablile_inr"):
            hasbled_score += 1
        if input_data.get("alcohol_use"):
            hasbled_score += 1
        if input_data.get("antiplatelet_drugs"):
            hasbled_score += 1

        score_details["chads2_vasc_total"] = chads2_score
        score_details["hasbled_total"] = hasbled_score

        if chads2_score >= 2:
            risk_level = "高危"
        elif chads2_score == 1:
            risk_level = "中危"
        else:
            risk_level = "低危"

        recommendations = []
        if chads2_score >= 2:
            recommendations.append("推荐口服抗凝治疗(OAC): NOAC优先，华法林备选(INR 2.0-3.0)")
        elif chads2_score == 1:
            recommendations.append("考虑口服抗凝治疗，平衡获益与出血风险")
        else:
            recommendations.append("低卒中风险，可暂不抗凝或仅抗血小板治疗")

        if hasbled_score >= 3:
            recommendations.append(f"HAS-BLED={hasbled_score}: 高出血风险，需定期监测并纠正可逆因素")
        else:
            recommendations.append(f"HAS-BLED={hasbled_score}: 出血风险可接受")

        recommendations.append("建议心室率控制: β受体阻滞剂或地高辛，目标静息HR<80bpm")
        recommendations.append("评估复律指征: 考虑节律控制策略(胺碘酮/普罗帕酮等)")

        return risk_level, float(chads2_score), score_details

    @staticmethod
    def calculate_cad_risk(input_data: Dict[str, Any]) -> Tuple[str, float, Dict[str, Any]]:
        score_details = {}
        timi_score = 0

        age = input_data.get("age", 0)
        if age >= 65:
            timi_score += 1
        score_details["age_ge65"] = {"value": age >= 65, "score": 1 if age >= 65 else 0}

        risk_count = 0
        for factor in ["family_history_cad", "hypertension", "diabetes", "hyperlipidemia", "smoking"]:
            if input_data.get(factor):
                risk_count += 1
        if risk_count >= 3:
            timi_score += 1
        score_details["risk_factors_ge3"] = {"value": risk_count >= 3, "count": risk_count, "score": 1 if risk_count >= 3 else 0}

        if input_data.get("known_cad_stenosis_ge50"):
            timi_score += 1
        score_details["known_cad"] = {"value": input_data.get("known_cad_stenosis_ge50", False), "score": 1 if input_data.get("known_cad_stenosis_ge50") else 0}

        if input_data.get("severe_angina"):
            timi_score += 1
        score_details["severe_angina"] = {"value": input_data.get("severe_angina", False), "score": 1 if input_data.get("severe_angina") else 0}

        if input_data.get("st_depression_ge05mm"):
            timi_score += 1
        score_details["st_depression"] = {"value": input_data.get("st_depression_ge05mm", False), "score": 1 if input_data.get("st_depression_ge05mm") else 0}

        if input_data.get("positive_cardiac_marker"):
            timi_score += 1
        score_details["cardiac_marker"] = {"value": input_data.get("positive_cardiac_marker", False), "score": 1 if input_data.get("positive_cardiac_marker") else 0}

        if input_data.get("rest_angina_within_24h"):
            timi_score += 1
        score_details["recent_angina"] = {"value": input_data.get("rest_angina_within_24h", False), "score": 1 if input_data.get("rest_angina_within_24h") else 0}

        score_details["timi_total"] = timi_score
        normalized_score = float(timi_score / 7.0 * 100)
        normalized_score = round(normalized_score, 1)

        if timi_score >= 5:
            risk_level = "极高危"
        elif timi_score >= 3:
            risk_level = "高危"
        elif timi_score >= 1:
            risk_level = "中危"
        else:
            risk_level = "低危"

        recommendations = []
        if risk_level == "极高危":
            recommendations.append("TIMI评分极高危，建议紧急有创策略(<2h)")
            recommendations.append("启动双抗+强效他汀+肝素/GPI治疗")
            recommendations.append("准备冠脉造影，评估血运重建指征")
        elif risk_level == "高危":
            recommendations.append("TIMI评分高危，建议早期有创策略(<24h)")
            recommendations.append("双抗治疗(阿司匹林+P2Y12抑制剂)")
            recommendations.append("高强度他汀、β受体阻滞剂、ACEI/ARB")
        elif risk_level == "中危":
            recommendations.append("TIMI评分中危，建议延迟有创策略(<72h)")
            recommendations.append("药物保守治疗基础上评估冠脉造影必要性")
        else:
            recommendations.append("TIMI评分低危，可考虑保守治疗")
            recommendations.append("完善冠脉CTA或运动试验进一步评估")

        recommendations.append("所有ACS患者: 生活方式干预+危险因素严格控制")
        recommendations.append("长期二级预防: 双抗/单抗+他汀+β受体阻滞剂+ACEI/ARB")

        return risk_level, normalized_score, score_details

    @staticmethod
    def calculate_risk(
        db: Session,
        patient_id: int,
        assessment_type: str,
        input_data: Dict[str, Any],
        visit_id: Optional[int] = None,
        assessor: Optional[str] = None,
    ) -> RiskAssessment:
        atype = assessment_type.lower()
        if atype in ["heart_failure", "hf", "心衰"]:
            risk_level, risk_score, details = RiskEngineService.calculate_heart_failure_risk(input_data)
            atype_display = "heart_failure"
        elif atype in ["atrial_fibrillation", "af", "afib", "房颤"]:
            risk_level, risk_score, details = RiskEngineService.calculate_afib_risk(input_data)
            atype_display = "atrial_fibrillation"
        elif atype in ["coronary_artery_disease", "cad", "冠心病"]:
            risk_level, risk_score, details = RiskEngineService.calculate_cad_risk(input_data)
            atype_display = "coronary_artery_disease"
        else:
            raise ValueError(f"不支持的评估类型: {assessment_type}")

        recommendations = details.pop("recommendations", "")

        assessment = RiskAssessment(
            patient_id=patient_id,
            visit_id=visit_id,
            assessment_type=atype_display,
            assessment_date=datetime.utcnow(),
            risk_level=risk_level,
            risk_score=risk_score,
            score_details=details,
            input_data=input_data,
            recommendations=recommendations,
            algorithm_version=RiskEngineService.ALGORITHM_VERSION,
            assessor=assessor,
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return assessment

    @staticmethod
    def list_assessments(
        db: Session,
        patient_id: int,
        assessment_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[RiskAssessment]:
        query = db.query(RiskAssessment).filter(RiskAssessment.patient_id == patient_id)
        if assessment_type:
            query = query.filter(RiskAssessment.assessment_type == assessment_type)
        return query.order_by(RiskAssessment.assessment_date.desc()).limit(limit).all()

    @staticmethod
    def get_latest_assessment(
        db: Session, patient_id: int, assessment_type: str
    ) -> Optional[RiskAssessment]:
        return (
            db.query(RiskAssessment)
            .filter(
                RiskAssessment.patient_id == patient_id,
                RiskAssessment.assessment_type == assessment_type,
            )
            .order_by(RiskAssessment.assessment_date.desc())
            .first()
        )
