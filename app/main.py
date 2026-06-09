from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import Base, engine
from app.middleware import AuditMiddleware
from app.routers.patient_router import router as patient_router
from app.routers.record_router import router as record_router
from app.routers.risk_router import router as risk_router
from app.routers.alert_router import router as alert_router
from app.routers.careplan_router import router as careplan_router
from app.routers.followup_router import router as followup_router
from app.routers.audit_router import router as audit_router

settings = get_settings()


def init_db():
    from app.models.patient import Patient, Visit
    from app.models.records import VitalSign, ECGRecord, LabRecord, MedicationRecord
    from app.models.risk_alert import RiskAssessment, Alert
    from app.models.plan_followup import CarePlan, FollowUp
    from app.models.audit import AuditLog, UsageStats
    Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "心内科辅助诊疗后端服务（仅辅助决策，不替代医生判断）\n\n"
        "能力模块：\n"
        "1. 患者档案：创建、合并就诊、时间线查询\n"
        "2. 检查接入：血压/心率/心电/检验/用药记录\n"
        "3. 风险计算：心衰/房颤/冠心病风险分层\n"
        "4. 提醒规则：危急值/禁忌用药/重复检查提示\n"
        "5. 方案草稿：检查建议+用药核对清单\n"
        "6. 随访管理：排期、症状记录、复诊提醒\n"
        "7. 审计统计：科室使用量+调用日志"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "x-doctor-id", "x-user-id", "x-department"],
)
app.add_middleware(AuditMiddleware)


@app.get("/health", tags=["系统"])
def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "modules": [
            "patients: 患者档案",
            "records: 检查接入",
            "risks: 风险计算",
            "alerts: 提醒规则",
            "care_plans: 方案草稿",
            "follow_ups: 随访管理",
            "audit: 审计统计",
        ],
        "disclaimer": "本服务为临床辅助决策系统，输出结果仅供参考，不替代医生的专业判断和诊疗决策。",
    }


prefix = settings.API_V1_PREFIX
app.include_router(patient_router, prefix=prefix)
app.include_router(record_router, prefix=prefix)
app.include_router(risk_router, prefix=prefix)
app.include_router(alert_router, prefix=prefix)
app.include_router(careplan_router, prefix=prefix)
app.include_router(followup_router, prefix=prefix)
app.include_router(audit_router, prefix=prefix)


@app.get("/", tags=["系统"])
def root():
    return {
        "message": f"欢迎使用 {settings.PROJECT_NAME}",
        "api_docs": "/docs",
        "api_prefix": prefix,
        "disclaimer": "辅助诊疗系统 - 不替代医生判断",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
