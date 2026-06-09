import urllib.request
import json

def test_endpoint(url, method="GET", data=None, query=None):
    full_url = url
    if query:
        if isinstance(query, str):
            full_url = url + "?" + query
        else:
            from urllib.parse import urlencode
            full_url = url + "?" + urlencode(query)
    print(f"\n=== 测试 {method} {full_url} ===")
    try:
        req = urllib.request.Request(full_url, method=method)
        req.add_header("Content-Type", "application/json")
        if data:
            req.data = json.dumps(data).encode("utf-8")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print(f"状态码: {resp.status}")
            try:
                parsed = json.loads(body)
                print(f"响应: {json.dumps(parsed, ensure_ascii=False, indent=2)[:500]}")
            except:
                print(f"响应: {body[:300]}")
            return parsed if 'parsed' in locals() else body
    except Exception as e:
        print(f"错误: {e}")
        return None

BASE = "http://localhost:8000/api/v1"

test_endpoint("http://localhost:8000/health")

patient = test_endpoint(f"{BASE}/patients", "POST", {
    "patient_no": "P20260001",
    "name": "张三",
    "gender": "男",
    "birth_date": "1960-03-15",
    "id_card": "110101196003151234",
    "phone": "13800138000",
    "department": "心内科",
    "doctor_id": "DR001",
    "height": 172.5,
    "weight": 78,
    "smoking": True,
    "past_medical_history": "高血压10年，糖尿病5年",
})

pid = patient["id"] if patient else 1

test_endpoint(f"{BASE}/patients", "GET")
test_endpoint(f"{BASE}/patients/{pid}", "GET")

test_endpoint(f"{BASE}/patients/visits", "POST", {
    "patient_id": pid,
    "visit_no": "V20260609001",
    "visit_type": "门诊",
    "department": "心内科",
    "doctor_id": "DR001",
    "chief_complaint": "活动后胸闷气短2周，加重伴双下肢水肿3天",
    "diagnosis": [{"code": "I50.900", "name": "心力衰竭"}],
})

vs = test_endpoint(f"{BASE}/records/vital-signs", "POST", {
    "patient_id": pid,
    "systolic_bp": 185,
    "diastolic_bp": 115,
    "heart_rate": 128,
    "oxygen_saturation": 89,
    "source": "门诊护士站",
    "operator_id": "NURSE001",
})

test_endpoint(f"{BASE}/records/lab", "POST", {
    "patient_id": pid,
    "lab_type": "cardiac",
    "test_name": "NT-proBNP",
    "test_code": "NT_proBNP",
    "test_value": 8500,
    "test_unit": "pg/mL",
    "reference_low": 0,
    "reference_high": 125,
})

test_endpoint(f"{BASE}/records/lab", "POST", {
    "patient_id": pid,
    "lab_type": "cardiac",
    "test_name": "肌钙蛋白I",
    "test_code": "troponin_i",
    "test_value": 1.2,
    "test_unit": "ng/mL",
    "reference_low": 0,
    "reference_high": 0.04,
})

risk = test_endpoint(f"{BASE}/risks/calculate", "POST", {
    "patient_id": pid,
    "assessment_type": "heart_failure",
    "input_data": {
        "nyha_class": "IV",
        "nt_probnp": 8500,
        "ejection_fraction": 28,
        "creatinine": 1.8,
        "sodium": 133,
        "age": 66,
    },
})

test_endpoint(f"{BASE}/risks/calculate", "POST", {
    "patient_id": pid,
    "assessment_type": "coronary_artery_disease",
    "input_data": {
        "age": 66,
        "family_history_cad": True,
        "hypertension": True,
        "diabetes": True,
        "hyperlipidemia": True,
        "smoking": True,
        "known_cad_stenosis_ge50": True,
        "severe_angina": True,
        "st_depression_ge05mm": True,
        "positive_cardiac_marker": True,
        "rest_angina_within_24h": True,
    },
})

test_endpoint(f"{BASE}/alerts", "GET", None, {"patient_id": pid})

test_endpoint(f"{BASE}/care-plans/generate", "POST", {
    "patient_id": pid,
    "plan_type": "heart_failure",
    "author_id": "DR001",
})

test_endpoint(f"{BASE}/follow-ups/auto-schedule", "POST", {
    "patient_id": pid,
    "risks": {"heart_failure": "极高危", "coronary_artery_disease": "极高危"},
    "scenarios": ["post_discharge"],
    "assigned_doctor_id": "DR001",
})

test_endpoint(f"{BASE}/patients/{pid}/timeline", "GET")

test_endpoint(f"{BASE}/audit/dashboard", "GET")

print("\n=== 全部核心接口测试完成 ===")
