import time
import uuid
import json
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.database import SessionLocal
from app.services.audit_service import AuditService


class AuditMiddleware(BaseHTTPMiddleware):
    ENDPOINT_MODULE_MAP = {
        "patients": "patients",
        "records": "records",
        "risks": "risks",
        "alerts": "alerts",
        "care-plans": "care_plans",
        "follow-ups": "follow_ups",
        "audit": "audit",
    }

    SKIP_PATHS = {"/docs", "/redoc", "/openapi.json", "/health", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = str(uuid.uuid4())

        if any(request.url.path.startswith(p) for p in self.SKIP_PATHS):
            return await call_next(request)

        module = "system"
        path_parts = [p for p in request.url.path.strip("/").split("/") if p]
        for part in path_parts:
            if part in self.ENDPOINT_MODULE_MAP:
                module = self.ENDPOINT_MODULE_MAP[part]
                break

        action_parts = [request.method.lower()]
        path_parts = request.url.path.strip("/").split("/")
        if len(path_parts) >= 2:
            action_parts.append(path_parts[-1])
        action = "_".join(action_parts)

        patient_id = None
        try:
            path_items = path_parts
            for i, part in enumerate(path_items):
                if part.isdigit() and i > 0 and path_items[i-1] not in ["logs"]:
                    patient_id = int(part)
                    break
        except (ValueError, IndexError):
            pass

        doctor_id = request.headers.get("x-doctor-id") or request.headers.get("x-user-id")
        department = request.headers.get("x-department")
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        request_params = {}
        query_params = dict(request.query_params)
        if query_params:
            request_params["query"] = query_params

        body_bytes = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_text = body_bytes.decode("utf-8")
                    try:
                        body_json = json.loads(body_text)
                        for sensitive in ["password", "token"]:
                            if sensitive in body_json:
                                body_json[sensitive] = "***"
                        request_params["body"] = body_json
                        if patient_id is None and "patient_id" in body_json:
                            patient_id = body_json["patient_id"]
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_params["body_preview"] = body_text[:200]
            except Exception:
                pass

            async def receive():
                return {"type": "http.request", "body": body_bytes or b"", "more_body": False}
            request = Request(request.scope, receive)

        response: Response = await call_next(request)
        latency_ms = int((time.time() - start_time) * 1000)
        response_code = response.status_code

        response_summary = f"{response_code} {request.method} {request.url.path}"
        error_message = None
        if response_code >= 400:
            error_message = f"HTTP {response_code}"

        try:
            db = SessionLocal()
            try:
                AuditService.log_request(
                    db,
                    request_id=request_id,
                    endpoint=str(request.url.path),
                    method=request.method,
                    module=module,
                    action=action,
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    department=department,
                    request_params=request_params if request_params else None,
                    response_code=response_code,
                    response_summary=response_summary,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    latency_ms=latency_ms,
                    error_message=error_message,
                )
            finally:
                db.close()
        except Exception:
            pass

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-MS"] = str(latency_ms)
        return response
