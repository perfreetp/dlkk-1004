import sys, os, json, urllib.request, urllib.error, traceback
from datetime import datetime, timedelta

LOG_FILE = "c:\\TraeProjects\\1004\\test_round5.txt"
logf = open(LOG_FILE, "w", encoding="utf-8")


def pl(msg=""):
    print(msg, file=logf, flush=True)


pl("=== ROUND 5: 4 New Reqs Test (隔离/对比/联动/审计) ===")
pl("Started: " + datetime.now().isoformat())

BASE = "http://localhost:8000/api/v1"


def http(method, path, body=None):
    url = BASE + path
    data = None
    headers = {"Content-Type": "application/json",
               "x-doctor-id": "D-R5", "x-department": "cardiology"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    pl(f"\n>>> {method} {url}")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            txt = resp.read().decode("utf-8")
            preview = txt[:200].replace("\n", " ")
            pl(f"    [{resp.status}] {preview}")
            return resp.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        pl(f"    [ERR {e.code}] {err[:300]}")
        return e.code, None


results = []


def check(name, cond, detail=""):
    tag = "[PASS]" if cond else "[FAIL]"
    results.append((name, cond, detail))
    pl(f"  {tag}: {name}" + (f"  ({detail})" if detail else ""))


try:
    # ======== Setup ========
    pl("\n[SETUP] 创建患者、2次就诊")
    _, pa = http("POST", "/patients", {
        "patient_no": "P-R5-001", "name": "王五（R5）",
        "gender": "male", "birth_date": "1957-03-10",
    })
    p_id = pa["id"]

    _, v1 = http("POST", "/patients/visits", {
        "patient_id": p_id, "visit_no": "V-R5-001", "visit_type": "门诊",
        "visit_date": (datetime.now() - timedelta(days=30)).isoformat(),
        "department": "心内科", "chief_complaint": "胸闷3月",
    })
    v1_id = v1["id"]

    _, v2 = http("POST", "/patients/visits", {
        "patient_id": p_id, "visit_no": "V-R5-002", "visit_type": "急诊",
        "visit_date": (datetime.now() - timedelta(days=2)).isoformat(),
        "department": "心内科急诊", "chief_complaint": "胸闷加重伴气促",
    })
    v2_id = v2["id"]

    # ============ V1 数据 ============
    pl("\n--- [V1 就诊数据] ---")
    http("POST", "/records/vital-signs", {
        "patient_id": p_id, "visit_id": v1_id,
        "systolic_bp": 165, "diastolic_bp": 98, "heart_rate": 82,
        "measure_time": (datetime.now() - timedelta(days=30)).isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p_id, "visit_id": v1_id,
        "test_name": "血红蛋白", "test_code": "HB",
        "test_value": "95", "test_unit": "g/L",
        "reference_low": "115", "reference_high": "150",
        "is_abnormal": True, "abnormal_flag": "L",
        "record_time": (datetime.now() - timedelta(days=30)).isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p_id, "visit_id": v1_id,
        "test_name": "肌酐", "test_code": "CREA",
        "test_value": "128", "test_unit": "μmol/L",
        "reference_low": "44", "reference_high": "106",
        "is_abnormal": True, "abnormal_flag": "H",
        "record_time": (datetime.now() - timedelta(days=30)).isoformat(),
    })
    # V1 风险：心衰低危
    http("POST", "/risks/calculate", {
        "patient_id": p_id, "visit_id": v1_id,
        "assessment_type": "heart_failure",
        "input_data": {
            "age": 68, "gender": "male", "has_heart_failure": False, "nyha_class": "I",
            "bnp": 80, "ejection_fraction": 55, "creatinine": 80, "sodium": 140,
        }
    })
    # V1 用药：美托洛尔、贝那普利、呋塞米
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v1_id,
        "drug_name": "美托洛尔缓释片", "generic_name": "Metoprolol",
        "dosage": "47.5mg", "frequency": "qd", "route": "口服",
        "start_date": (datetime.now() - timedelta(days=30)).date().isoformat(),
        "is_active": True,
    })
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v1_id,
        "drug_name": "盐酸贝那普利", "generic_name": "Benazepril",
        "dosage": "10mg", "frequency": "qd", "route": "口服",
        "start_date": (datetime.now() - timedelta(days=30)).date().isoformat(),
        "is_active": True,
    })
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v1_id,
        "drug_name": "呋塞米片", "generic_name": "Furosemide",
        "dosage": "20mg", "frequency": "qd", "route": "口服",
        "start_date": (datetime.now() - timedelta(days=30)).date().isoformat(),
        "is_active": True,
    })

    # ============ V2 数据 ============
    pl("\n--- [V2 就诊数据 (与V1差异明显)] ---")
    http("POST", "/records/vital-signs", {
        "patient_id": p_id, "visit_id": v2_id,
        "systolic_bp": 135, "diastolic_bp": 85, "heart_rate": 72,
        "measure_time": (datetime.now() - timedelta(days=2)).isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p_id, "visit_id": v2_id,
        "test_name": "血红蛋白", "test_code": "HB",
        "test_value": "122", "test_unit": "g/L",
        "reference_low": "115", "reference_high": "150",
        "is_abnormal": False, "abnormal_flag": "N",
        "record_time": (datetime.now() - timedelta(days=2)).isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p_id, "visit_id": v2_id,
        "test_name": "肌酐", "test_code": "CREA",
        "test_value": "185", "test_unit": "μmol/L",
        "reference_low": "44", "reference_high": "106",
        "is_abnormal": True, "abnormal_flag": "HH",
        "record_time": (datetime.now() - timedelta(days=2)).isoformat(),
    })
    # V2 风险：心衰极高危
    http("POST", "/risks/calculate", {
        "patient_id": p_id, "visit_id": v2_id,
        "assessment_type": "heart_failure",
        "input_data": {
            "age": 68, "gender": "male", "has_heart_failure": True, "nyha_class": "IV",
            "bnp": 2200, "ejection_fraction": 28, "creatinine": 220, "sodium": 130,
        }
    })
    # V2 用药：美托洛尔95mg(剂量变), 贝那普利bid(频次变), 呋塞米停用(is_active=False), 加沙库巴曲缬沙坦(新)
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v2_id,
        "drug_name": "美托洛尔缓释片", "generic_name": "Metoprolol",
        "dosage": "95mg", "frequency": "qd", "route": "口服",
        "start_date": (datetime.now() - timedelta(days=2)).date().isoformat(),
        "is_active": True,
    })
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v2_id,
        "drug_name": "盐酸贝那普利", "generic_name": "Benazepril",
        "dosage": "10mg", "frequency": "bid", "route": "口服",
        "start_date": (datetime.now() - timedelta(days=2)).date().isoformat(),
        "is_active": True,
    })
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v2_id,
        "drug_name": "呋塞米片", "generic_name": "Furosemide",
        "dosage": "20mg", "frequency": "qd", "route": "口服",
        "start_date": (datetime.now() - timedelta(days=30)).date().isoformat(),
        "end_date": (datetime.now() - timedelta(days=3)).date().isoformat(),
        "is_active": False,
    })
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v2_id,
        "drug_name": "沙库巴曲缬沙坦钠", "generic_name": "Sacubitril/Valsartan",
        "dosage": "100mg", "frequency": "bid", "route": "口服",
        "start_date": (datetime.now() - timedelta(days=2)).date().isoformat(),
        "is_active": True,
    })

    # ======== REQ1: 强就诊隔离 + 5类依据 ========
    pl("\n" + "=" * 80)
    pl("[REQ 1] 5类依据(风险/检验/用药/提醒/生命体征)强就诊隔离")
    pl("=" * 80)

    _, cp1 = http("POST", "/care-plans/generate", {
        "patient_id": p_id, "visit_id": v1_id,
        "plan_type": "chronic_management", "author_id": "D-R5",
        "include_visit_id": v1_id,
        "include_risk_assessment": True, "include_abnormal_labs": True,
        "include_active_medications": True, "include_unresolved_alerts": True,
        "include_vital_signs": True,
    })
    cp1_id = cp1["id"]
    ed1 = cp1.get("evidence_details") or {}
    r1_risks = ed1.get("risk_assessments", [])
    r1_hf = next((r for r in r1_risks if r.get("assessment_type") == "heart_failure"), None)
    check("1a V1方案的心衰风险=中危（不因V2的极高危而消失）",
          r1_hf and r1_hf.get("risk_level") == "中危",
          f"risk_level={r1_hf.get('risk_level') if r1_hf else None}")

    r1_vitals = ed1.get("vital_signs", [])
    check("1b V1方案有vital_signs数组", len(r1_vitals) >= 1, f"len={len(r1_vitals)}")
    if r1_vitals:
        vs1 = r1_vitals[0]
        check("1c V1生命体征=165/98（非V2的135/85）",
              vs1.get("systolic_bp") == 165 and vs1.get("diastolic_bp") == 98,
              f"sbp={vs1.get('systolic_bp')}, dbp={vs1.get('diastolic_bp')}")

    r1_meds = ed1.get("active_medications", [])
    r1_med_names = {m.get("generic_name") for m in r1_meds if m.get("generic_name")}
    check("1d V1用药=美托洛尔/贝那普利/呋塞米（不含沙库巴曲）",
          {"Metoprolol", "Benazepril", "Furosemide"}.issubset(r1_med_names)
          and "Sacubitril/Valsartan" not in r1_med_names,
          f"names={r1_med_names}")

    r1_labs = ed1.get("abnormal_labs", [])
    r1_lab_codes = {l.get("test_code") for l in r1_labs}
    check("1e V1异常检验=HB(L)+CREA(H)",
          {"HB", "CREA"}.issubset(r1_lab_codes), f"codes={r1_lab_codes}")

    # 再GET方案详情，证据和生成时一致
    _, cp1d = http("GET", f"/care-plans/{cp1_id}")
    ed1d = cp1d.get("evidence_details") or {}
    r1d_hf = next((r for r in ed1d.get("risk_assessments", []) if r.get("assessment_type") == "heart_failure"), None)
    check("1f GET V1详情心衰风险仍中危",
          r1d_hf and r1d_hf.get("risk_level") == "中危",
          f"risk_level={r1d_hf.get('risk_level') if r1d_hf else None}")

    # 生成V2方案
    _, cp2 = http("POST", "/care-plans/generate", {
        "patient_id": p_id, "visit_id": v2_id,
        "plan_type": "acute_coronary", "author_id": "D-R5",
        "include_visit_id": v2_id,
    })
    cp2_id = cp2["id"]
    ed2 = cp2.get("evidence_details") or {}
    r2_hf = next((r for r in ed2.get("risk_assessments", []) if r.get("assessment_type") == "heart_failure"), None)
    check("1g V2方案心衰风险=高危/极高危",
          r2_hf and r2_hf.get("risk_level") in {"高危", "极高危"},
          f"risk_level={r2_hf.get('risk_level') if r2_hf else None}")
    r2_med_names = {m.get("generic_name") for m in ed2.get("active_medications", []) if m.get("is_active")}
    check("1h V2方案含沙库巴曲缬沙坦",
          "Sacubitril/Valsartan" in r2_med_names, f"names={r2_med_names}")
    r2_vitals = ed2.get("vital_signs", [])
    check("1i V2方案有vital_signs", len(r2_vitals) >= 1)
    if r2_vitals:
        check("1j V2生命体征=135/85",
              r2_vitals[0].get("systolic_bp") == 135,
              f"sbp={r2_vitals[0].get('systolic_bp')}")

    # ======== REQ2: 就诊对比细化 ========
    pl("\n" + "=" * 80)
    pl("[REQ 2] 就诊对比细化（用药8态/检验参考范围/异常改善标签）")
    pl("=" * 80)

    _, cmp = http("GET", f"/patients/{p_id}/visits/compare?visit_id_1={v1_id}&visit_id_2={v2_id}")
    cmp_meds = (cmp or {}).get("medications") or []
    cmp_sum = (cmp or {}).get("summary_total") or (cmp or {}).get("summary") or {}
    meds_map = {m["name"]: m for m in cmp_meds}

    # 用药细分
    def med_has(name, ctype):
        return name in meds_map and meds_map[name].get("change_type") == ctype

    check("2a 呋塞米 discontinued (active→inactive)",
          med_has("呋塞米片", "discontinued"),
          f"实际={meds_map.get('呋塞米片', {}).get('change_type')}")
    check("2b 沙库巴曲缬沙坦 new (新增)",
          med_has("沙库巴曲缬沙坦钠", "new"),
          f"实际={meds_map.get('沙库巴曲缬沙坦钠', {}).get('change_type')}")
    check("2c 美托洛尔 dosage_changed (47.5→95)",
          med_has("美托洛尔缓释片", "dosage_changed"),
          f"实际={meds_map.get('美托洛尔缓释片', {}).get('change_type')}")
    check("2d 贝那普利 frequency_changed (qd→bid)",
          med_has("盐酸贝那普利", "frequency_changed"),
          f"实际={meds_map.get('盐酸贝那普利', {}).get('change_type')}")

    check("2e summary counters: discontinued>=1", cmp_sum.get("discontinued", 0) >= 1)
    check("2f summary counters: new>=1", cmp_sum.get("new", 0) >= 1)
    check("2g summary counters: dosage_changed>=1", cmp_sum.get("dosage_changed", 0) >= 1)
    check("2h summary counters: frequency_changed>=1", cmp_sum.get("frequency_changed", 0) >= 1)

    # 检验：参考范围+改善/变差
    cmp_labs = (cmp or {}).get("labs") or []
    hb = next((x for x in cmp_labs if (x.get("metric") or "") in ("HB", "血红蛋白", "血红")), None)
    if not hb:
        hb = next((x for x in cmp_labs if "HB" in str(x.get("metric", ""))), None)
    if hb:
        check("2i HB带reference_low/high",
              (hb.get("v2_details") or {}).get("reference_low") and
              (hb.get("v2_details") or {}).get("reference_high"),
              f"v2_details={hb.get('v2_details')}")
        check("2j HB L→N = improved",
              hb.get("abnormal_change") == "improved",
              f"actual={hb.get('abnormal_change')}")

    crea = next((x for x in cmp_labs if "CREA" in str(x.get("metric", "")) or "肌酐" in str(x.get("metric", ""))), None)
    if crea:
        check("2k CREA H→HH = worsened",
              crea.get("abnormal_change") == "worsened",
              f"actual={crea.get('abnormal_change')}")

    # 生命体征：参考范围+改善
    cmp_vs = (cmp or {}).get("vital_signs") or []
    sbp = next((x for x in cmp_vs if "收缩压" in str(x.get("metric", "")) or "systolic" in str(x.get("metric", "")).lower() or "SBP" in str(x.get("metric", ""))), None)
    if sbp:
        check("2l SBP带参考范围90/140",
              (sbp.get("v1_details") or {}).get("reference_low") == 90 and
              (sbp.get("v1_details") or {}).get("reference_high") == 140,
              f"actual={sbp.get('v1_details')}")
        check("2m SBP 165→135 = improved",
              sbp.get("abnormal_change") == "improved",
              f"actual={sbp.get('abnormal_change')}")

    check("2n summary improved>=1", cmp_sum.get("improved", 0) >= 1)
    check("2o summary worsened>=1", cmp_sum.get("worsened", 0) >= 1)

    # ======== REQ3: 随访-方案联动 ========
    pl("\n" + "=" * 80)
    pl("[REQ 3] 方案转随访联动追踪 + 方案变更提示")
    pl("=" * 80)

    http("PUT", f"/care-plans/{cp2_id}", {
        "status": "reviewed",
        "exam_suggestions": [
            {"test_name": "门诊复诊", "purpose": "血压/心率/BNP", "description": "两周后心内科门诊复诊"},
            {"test_name": "心脏超声", "purpose": "EF评估", "description": "1月后复查心超"},
        ],
    })
    _, cv = http("POST", f"/care-plans/{cp2_id}/follow-up-convert", {
        "from_exam_index": 0, "days_after": 14,
    })
    fu_id = cv["id"]
    check("3a 转随访成功", fu_id > 0)
    check("3b 随访带care_plan_id == cp2_id", cv.get("care_plan_id") == cp2_id, f"={cv.get('care_plan_id')}")
    check("3c 随访plan_sync_status==synced", cv.get("plan_sync_status") == "synced", f"={cv.get('plan_sync_status')}")
    check("3d 随访带care_plan_snapshot", (cv.get("care_plan_snapshot") or {}).get("plan_id") == cp2_id)

    _, fl = http("GET", f"/follow-ups?patient_id={p_id}")
    fl_items = (fl or {}).get("items") or []
    fl_fu = next((x for x in fl_items if x["id"] == fu_id), None)
    check("3e 随访列表含care_plan_id", fl_fu and fl_fu.get("care_plan_id") == cp2_id)

    _, tl = http("GET", f"/patients/{p_id}/timeline?event_types=follow_up&page_size=20")
    tl_evs = (tl or {}).get("events") or []
    tl_fu = next((e for e in tl_evs if (e.get("extra") or {}).get("care_plan_id") == cp2_id), None)
    check("3f 时间线follow_up事件含care_plan_id", bool(tl_fu), f"events={len(tl_evs)}")

    # 方案更新 → 关联随访plan_updated
    http("PUT", f"/care-plans/{cp2_id}", {
        "exam_suggestions": [
            {"test_name": "门诊复诊", "purpose": "BNP+电解质", "description": "调整为1周后复诊"},
        ],
    })
    _, fu2 = http("GET", f"/follow-ups/{fu_id}")
    check("3g 方案更新后→随访plan_updated",
          (fu2 or {}).get("plan_sync_status") == "plan_updated",
          f"actual={(fu2 or {}).get('plan_sync_status')}")
    _, tl2 = http("GET", f"/patients/{p_id}/timeline?event_types=follow_up&page_size=20")
    tl2_fu = next((e for e in (tl2 or {}).get("events", []) if (e.get("extra") or {}).get("care_plan_id") == cp2_id), None)
    check("3h 时间线标题带⚠", tl2_fu and "⚠" in (tl2_fu.get("title") or ""),
          f"title={tl2_fu.get('title') if tl2_fu else None}")
    check("3i 时间线level==high", tl2_fu and tl2_fu.get("level") == "high",
          f"level={tl2_fu.get('level') if tl2_fu else None}")

    # 方案撤回 → plan_withdrawn
    http("PUT", f"/care-plans/{cp2_id}", {
        "status": "cancelled", "treatment_notes": "患者转院,方案撤回",
    })
    _, fu3 = http("GET", f"/follow-ups/{fu_id}")
    check("3j 方案撤回→随访plan_withdrawn",
          (fu3 or {}).get("plan_sync_status") == "plan_withdrawn",
          f"actual={(fu3 or {}).get('plan_sync_status')}")

    # ======== REQ4: 审计统计多维筛选 ========
    pl("\n" + "=" * 80)
    pl("[REQ 4] 审计统计：多维过滤 + 3项闭环率 + 按天趋势")
    pl("=" * 80)

    # 再补1个提醒/风险保证有数据
    http("POST", "/risks/calculate", {
        "patient_id": p_id, "visit_id": v2_id,
        "assessment_type": "atrial_fibrillation",
        "input_data": {
            "age": 72, "chf": True, "hypertension": True, "stroke_history": False,
            "vascular_disease": True, "sex": "male", "creatinine": 130,
        }
    })

    _, s1 = http("GET", "/care-plans/audit/statistics?period_days=30")
    check("4a 统计有filters字段", "filters" in (s1 or {}))
    check("4b 统计有closed_loop_rates字段", "closed_loop_rates" in (s1 or {}))
    check("4c 统计有daily_trend数组", isinstance((s1 or {}).get("daily_trend"), list) and len((s1 or {}).get("daily_trend") or []) > 0)

    clr = (s1 or {}).get("closed_loop_rates") or {}
    check("4d 3项率齐全",
          "alert_process_rate_pct" in clr and "plan_to_follow_up_rate_pct" in clr and "follow_up_complete_rate_pct" in clr,
          f"keys={list(clr.keys())}")

    # 目前2方案,1转随访 → 转随访率>=50
    check("4e 方案转随访率>=50%", clr.get("plan_to_follow_up_rate_pct", 0) >= 50.0,
          f"={clr.get('plan_to_follow_up_rate_pct')}")

    dt = (s1 or {}).get("daily_trend") or []
    today = datetime.now().date().isoformat()
    tr_today = next((r for r in dt if r.get("date") == today), None)
    check("4f daily_trend含今日", bool(tr_today), f"today={today}, got={[r.get('date') for r in dt[:5]]}")
    if tr_today:
        cols = ["date", "alerts_total", "alerts_processed", "plans_total", "plans_to_fu", "fu_total", "fu_completed"]
        check("4g 今日行含7项列", all(c in tr_today for c in cols), f"keys={list(tr_today.keys())}")
        check("4h 今日plans_total>=2", tr_today.get("plans_total", 0) >= 2, f"={tr_today.get('plans_total')}")
        check("4i 今日plans_to_fu>=1", tr_today.get("plans_to_fu", 0) >= 1)

    # 按患者过滤
    _, sp = http("GET", f"/care-plans/audit/statistics?period_days=30&patient_id={p_id}")
    pl_cp = (sp or {}).get("care_plans") or {}
    check("4j 按患者过滤后方案数=2", pl_cp.get("total", -1) == 2, f"={pl_cp.get('total')}")

    # 按医生过滤 D-R5
    _, sd = http("GET", "/care-plans/audit/statistics?period_days=30&doctor_id=D-R5")
    sd_cp = (sd or {}).get("care_plans") or {}
    check("4k 按D-R5过滤后方案数>=2", sd_cp.get("total", 0) >= 2, f"={sd_cp.get('total')}")

    # 按医生过滤 D-XXX 不存在
    _, sx = http("GET", "/care-plans/audit/statistics?period_days=30&doctor_id=D-XXX")
    sx_cp = (sx or {}).get("care_plans") or {}
    check("4l 按不存在医生过滤=0", sx_cp.get("total", -1) == 0, f"={sx_cp.get('total')}")

    # 按时间段(10天前~昨天) —— 今天生成的方案不在内
    sd10 = (datetime.now() - timedelta(days=10)).isoformat()
    sd1 = (datetime.now() - timedelta(days=1)).isoformat()
    _, st = http("GET", f"/care-plans/audit/statistics?start_date={sd10}&end_date={sd1}")
    st_cp = (st or {}).get("care_plans") or {}
    check("4m 时间过滤后方案数=0(都是今天生成)", st_cp.get("total", -1) == 0, f"={st_cp.get('total')}")

    # ======== 汇总 ========
    pl("\n" + "=" * 80)
    pass_n = sum(1 for _, ok, _ in results if ok)
    fail_n = len(results) - pass_n
    pl(f"[TOTAL] PASS={pass_n} / FAIL={fail_n}")
    pl("=" * 80)
    if fail_n:
        pl("\n失败列表：")
        for nm, ok, dt in results:
            if not ok:
                pl(f"  - {nm}: {dt}")

except Exception as e:
    pl(f"\n[FATAL] 运行异常: {repr(e)}")
    pl(traceback.format_exc())

logf.close()

# 控制台也打印结论
print(f"\n=========== ROUND5 测试完成 ===========")
with open(LOG_FILE, encoding="utf-8") as f:
    for line in f.readlines()[-20:]:
        print(line.rstrip())
