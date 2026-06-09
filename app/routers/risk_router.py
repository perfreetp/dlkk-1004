from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.risk_alert import (
    RiskAssessmentRequest, RiskAssessmentResponse, RiskResultSummary,
    RiskBatchCalculateRequest,
)
from app.services.risk_engine_service import RiskEngineService

router = APIRouter(prefix="/risks", tags=["风险计算"])


@router.post("/calculate", response_model=RiskAssessmentResponse, summary="计算单患者单类型风险")
def calculate_risk(
    req: RiskAssessmentRequest,
    x_doctor_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        return RiskEngineService.calculate_risk(
            db,
            patient_id=req.patient_id,
            assessment_type=req.assessment_type,
            input_data=req.input_data,
            visit_id=req.visit_id,
            assessor=x_doctor_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/calculate/batch", response_model=List[RiskResultSummary], summary="批量计算患者风险")
def batch_calculate_risk(req: RiskBatchCalculateRequest, db: Session = Depends(get_db)):
    results = []
    for pid in req.patient_ids:
        for atype in req.assessment_types:
            latest = RiskEngineService.get_latest_assessment(db, pid, atype)
            results.append(RiskResultSummary(
                patient_id=pid,
                assessment_type=atype,
                risk_level=latest.risk_level if latest else "未评估",
                risk_score=latest.risk_score if latest else None,
            ))
    return results


@router.get("/{patient_id}", response_model=List[RiskAssessmentResponse], summary="查询患者风险评估历史")
def list_assessments(
    patient_id: int,
    assessment_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return RiskEngineService.list_assessments(db, patient_id, assessment_type, limit)


@router.get("/{patient_id}/latest/{assessment_type}", response_model=RiskAssessmentResponse, summary="获取最新风险评估")
def get_latest_assessment(patient_id: int, assessment_type: str, db: Session = Depends(get_db)):
    result = RiskEngineService.get_latest_assessment(db, patient_id, assessment_type)
    if not result:
        raise HTTPException(status_code=404, detail="暂无该类型的风险评估记录")
    return result


@router.get("/algorithms/supported", summary="获取支持的风险评估算法")
def get_supported_algorithms():
    return {
        "algorithms": [
            {
                "type": "heart_failure",
                "name": "心衰风险分层",
                "description": "基于NYHA分级、BNP/NT-proBNP、EF、肾功能等综合评分",
                "version": RiskEngineService.ALGORITHM_VERSION,
                "inputs": ["nyha_class", "bnp/nt_probnp", "ejection_fraction", "creatinine", "sodium", "age"],
                "outputs": ["风险等级(极高危/高危/中危/低危/极低危)", "标准化评分(0-100)"],
            },
            {
                "type": "atrial_fibrillation",
                "name": "房颤卒中+出血风险",
                "description": "CHA₂DS₂-VASc卒中评分 + HAS-BLED出血评分",
                "version": RiskEngineService.ALGORITHM_VERSION,
                "inputs": ["age", "chf", "hypertension", "diabetes", "stroke_tia", "vascular_disease", "gender", "肾功能/肝功能/出血史等"],
                "outputs": ["CHA₂DS₂-VASc(0-9分)", "HAS-BLED(0-9分)", "卒中风险分层"],
            },
            {
                "type": "coronary_artery_disease",
                "name": "冠心病/ACS TIMI风险",
                "description": "TIMI评分评估UA/NSTEMI患者预后及侵入策略时机",
                "version": RiskEngineService.ALGORITHM_VERSION,
                "inputs": ["age>=65", "危险因素>=3", "冠脉狭窄>=50%", "ST段压低", "24h内发作>=2次", "心肌标志物", "严重心绞痛"],
                "outputs": ["TIMI评分(0-7分)", "风险等级(极高危/高危/中危/低危)"],
            },
        ]
    }
