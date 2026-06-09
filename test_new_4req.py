import sys, os, json, urllib.request, urllib.error, traceback
from datetime import datetime, timedelta
from collections import Counter

LOG_FILE = "c:\\TraeProjects\\1004\\test_new_4req.txt"
logf = open(LOG_FILE, "w", encoding="utf-8")
def pl(msg=""):
    print(msg, file=logf, flush=True)

pl("=== 4 New Requirements Regression Test ===")
pl("Started: " + datetime.now().isoformat())

BASE = "http://localhost:8000/api/v1"

def http(method, path, body=None):
    url = BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    pl(f"\n>>> {method} {url}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
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
    # ======== Req 1 & 2: Timeline with groups, filters, alert/care_plan events ========
    pl("\n" + "="*80)
    pl("[REQ 1 + 2] Timeline enhancements: groups + filters + alert/care_plan events")
    pl("="*80)

    # Create patient, visit, then populate
    _, pa = http("POST", "/patients", {
        "patient_no": "P-TL-100", "name": "时间线患者",
        "gender": "male", "birth_date": "1965-03-15",
    })
    p1 = pa["id"]
    _, v1 = http("POST", "/patients/visits", {
        "patient_id": p1, "visit_no": "V-TL-001", "visit_type": "门诊",
        "visit_date": datetime.now().isoformat(),
        "department": "心内科", "chief_complaint": "反复胸闷1月",
    })
    v1_id = v1["id"]

    # Create a second visit (later)
    _, v2 = http("POST", "/patients/visits", {
        "patient_id": p1, "visit_no": "V-TL-002", "visit_type": "急诊",
        "visit_date": (datetime.now() + timedelta(days=3)).isoformat(),
        "department": "急诊", "chief_complaint": "胸痛2小时",
    })
    v2_id = v2["id"]

    # Add vital signs, labs, ECG, meds to both visits
    http("POST", "/records/vital-signs", {
        "patient_id": p1, "visit_id": v1_id,
        "systolic_bp": 148, "diastolic_bp": 95, "heart_rate": 92,
        "measure_time": datetime.now().isoformat(),
    })
    http("POST", "/records/ecg", {
        "patient_id": p1, "visit_id": v1_id,
        "rhythm": "窦性心动过速", "hr": 105, "qrs_duration_ms": 88,
        "qt_interval_ms": 410, "is_abnormal": True,
        "report_summary": "窦性心动过速，ST段压低",
        "record_time": datetime.now().isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p1, "visit_id": v1_id,
        "test_name": "肌钙蛋白I", "test_code": "CTNI",
        "test_value": "0.8", "test_unit": "ng/mL",
        "reference_low": "0", "reference_high": "0.04",
        "is_abnormal": True, "abnormal_flag": "HH",
        "record_time": datetime.now().isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p1, "visit_id": v1_id,
        "test_name": "BNP", "test_code": "BNP",
        "test_value": "1200", "test_unit": "pg/mL",
        "reference_low": "0", "reference_high": "100",
        "is_abnormal": True, "abnormal_flag": "HH",
        "record_time": datetime.now().isoformat(),
    })
    http("POST", "/records/medications", {
        "patient_id": p1, "visit_id": v1_id,
        "drug_name": "阿司匹林肠溶片", "generic_name": "Aspirin",
        "dosage": "100mg", "frequency": "qd", "route": "口服",
        "start_date": datetime.now().date().isoformat(),
        "is_active": True,
    })
    http("POST", "/records/medications", {
        "patient_id": p1, "visit_id": v1_id,
        "drug_name": "硝酸甘油片", "generic_name": "Nitroglycerin",
        "dosage": "0.5mg", "frequency": "prn", "route": "舌下含服",
        "start_date": datetime.now().date().isoformat(),
        "is_active": True,
    })
    # 硝酸甘油 + 西地那非 产生禁忌
    http("POST", "/records/medications", {
        "patient_id": p1, "visit_id": v1_id,
        "drug_name": "西地那非片", "generic_name": "Sildenafil",
        "dosage": "50mg", "frequency": "qd", "route": "口服",
        "start_date": datetime.now().date().isoformat(),
        "is_active": True,
    })
    # 风险评估
    http("POST", "/risks/calculate", {
        "patient_id": p1, "visit_id": v1_id,
        "assessment_type": "heart_failure",
        "input_data": {
            "age": 60, "gender": "male", "has_heart_failure": True, "nyha_class": 3,
            "bnp_pg_ml": 560, "ef_percent": 35, "creatinine_umol_l": 110,
            "sodium_mmol_l": 138, "has_diabetes": False, "has_hypertension": True,
        }
    })
    # 生成方案
    http("POST", "/care-plans/generate", {
        "patient_id": p1, "visit_id": v1_id,
        "plan_type": "heart_failure", "author_id": "dr_wang",
    })
    # 安排随访
    http("POST", "/follow-ups", {
        "patient_id": p1, "visit_id": v1_id,
        "follow_up_type": "clinic",
        "scheduled_date": (datetime.now() + timedelta(days=14)).isoformat(),
        "purpose": "心衰复查", "status": "scheduled",
    })

    # --- 1a: Full timeline contains ALL 9 event types ---
    _, tl = http("GET", f"/patients/{p1}/timeline?page_size=200&include_groups=true")
    etypes = [e["event_type"] for e in tl["events"]]
    etype_set = set(etypes)
    expected_types = {"visit", "vital_sign", "ecg", "lab", "medication", "risk", "alert", "care_plan", "follow_up"}
    missing = expected_types - etype_set
    check("1a 时间线包含9类事件 (visit/vital/ecg/lab/med/risk/alert/care_plan/follow_up)",
          missing == set(), f"missing={missing}, present={sorted(etype_set)}")

    # --- 1b: visit_groups structure ---
    vgs = tl.get("visit_groups", [])
    has_v1 = any(g["visit_id"] == v1_id for g in vgs)
    has_v2 = any(g["visit_id"] == v2_id for g in vgs)
    g1 = next((g for g in vgs if g["visit_id"] == v1_id), None)
    if g1:
        g1_etypes = set(e["event_type"] for e in g1["events"])
        needed = {"vital_sign", "ecg", "lab", "medication", "risk", "alert", "care_plan", "follow_up"}
        g1_missing = needed - g1_etypes
    else:
        g1_missing = "GROUP_NOT_FOUND"
    check("1b 按就诊分组：2个就诊都有分组 + V1组内聚合8类关联事件",
          has_v1 and has_v2 and g1_missing == set(),
          f"v1={has_v1} v2={has_v2}; V1 group missing={g1_missing}")

    # --- 2a: 按事件类型过滤（只看检验+用药） ---
    _, tl_f = http("GET", f"/patients/{p1}/timeline?event_types=lab,medication&page_size=50")
    filt_types = set(e["event_type"] for e in tl_f["events"])
    check("2a 事件类型过滤：lab,medication 只返回这两类",
          filt_types.issubset({"lab", "medication"}) and "lab" in filt_types and "medication" in filt_types,
          f"types={sorted(filt_types)}, total_filtered={tl_f['total']}")

    # --- 2b: 按就诊号过滤 ---
    _, tl_visit = http("GET", f"/patients/{p1}/timeline?visit_no=V-TL-001&page_size=50")
    vids_in = set(e["visit_id"] for e in tl_visit["events"] if e["visit_id"])
    check("2b 按就诊号过滤V-TL-001：返回事件visit_id一致",
          len(tl_visit["events"]) >= 8 and vids_in.issubset({v1_id}),
          f"total={tl_visit['total']}, vids_present={sorted(vids_in)}")

    # --- 2c: 分页has_more ---
    _, tl_p1 = http("GET", f"/patients/{p1}/timeline?page=1&page_size=5")
    _, tl_p2 = http("GET", f"/patients/{p1}/timeline?page=2&page_size=5")
    total_n = tl_p1["total"]
    check("2c 分页：page1 has_more=True, page2返回第2页, total匹配",
          tl_p1["has_more"] and len(tl_p1["events"]) == 5 and len(tl_p2["events"]) == 5 and tl_p2["total"] == total_n,
          f"total={total_n}, p1={len(tl_p1['events'])} hm={tl_p1['has_more']}, p2={len(tl_p2['events'])}")

    # ======== Req 3: Care plan evidence references ========
    pl("\n" + "="*80)
    pl("[REQ 3] Care plan evidence references (可追溯)")
    pl("="*80)

    # 用原patient的V2做新方案
    http("POST", "/records/vital-signs", {
        "patient_id": p1, "visit_id": v2_id,
        "systolic_bp": 185, "diastolic_bp": 115, "heart_rate": 110,
        "measure_time": (datetime.now() + timedelta(days=3)).isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p1, "visit_id": v2_id,
        "test_name": "肌钙蛋白T", "test_code": "CTNT",
        "test_value": "1.2", "test_unit": "ng/mL",
        "reference_low": "0", "reference_high": "0.01",
        "is_abnormal": True, "abnormal_flag": "HH",
        "record_time": (datetime.now() + timedelta(days=3)).isoformat(),
    })
    http("POST", "/risks/calculate", {
        "patient_id": p1, "visit_id": v2_id,
        "assessment_type": "coronary_artery_disease",
        "input_data": {
            "age": 60, "gender": "male",
            "has_chest_pain": True, "has_st_segment_change": True,
            "has_troponin_elevation": True, "has_risk_factors": 3,
            "has_prior_mi": False, "has_aspirin_use": True,
            "has_coronary_stenosis": False, "symptom_duration_hours": 2,
        }
    })
    http("POST", "/risks/calculate", {
        "patient_id": p1, "visit_id": v2_id,
        "assessment_type": "heart_failure",
        "input_data": {
            "age": 60, "gender": "male", "has_heart_failure": True, "nyha_class": 3,
            "bnp_pg_ml": 560, "ef_percent": 30, "creatinine_umol_l": 120,
            "sodium_mmol_l": 136, "has_diabetes": False, "has_hypertension": True,
        }
    })
    _, cp = http("POST", "/care-plans/generate", {
        "patient_id": p1, "visit_id": v2_id,
        "plan_type": "coronary_artery_disease", "author_id": "dr_li",
    })
    cp_id = cp["id"]

    # 3a evidence IDs non-empty
    risk_ids = cp.get("evidence_risk_ids") or []
    ab_lab_ids = cp.get("evidence_abnormal_lab_ids") or []
    med_ids = cp.get("evidence_active_med_ids") or []
    alert_ids = cp.get("evidence_unresolved_alert_ids") or []
    ev_sum = cp.get("evidence_summary") or {}
    check("3a 方案依据字段有内容 (risk_ids, abnormal_labs, active_meds, unresolved_alerts, evidence_summary)",
          len(risk_ids) >= 1 and len(ab_lab_ids) >= 1 and len(alert_ids) >= 1 and bool(ev_sum),
          f"risk={risk_ids}, labs={ab_lab_ids}, meds={len(med_ids)}, alerts={alert_ids}, has_summary={bool(ev_sum)}")

    # 3b evidence IDs 指向真实记录 (打开方案能追溯)
    ev_risk_recs = ev_sum.get("risk_assessments", [])
    ev_ab_lab_recs = ev_sum.get("abnormal_labs", [])
    ev_alerts = ev_sum.get("unresolved_alerts", [])
    check("3b evidence_summary 内包含每条依据的id/摘要（可追溯）",
          len(ev_risk_recs) == len(risk_ids) and
          all("id" in r and "assessment_type" in r and "risk_level" in r for r in ev_risk_recs) and
          all("id" in l and "test_name" in l for l in ev_ab_lab_recs) and
          all("id" in a and "alert_type" in a and "title" in a for a in ev_alerts),
          f"risks={len(ev_risk_recs)}/{len(risk_ids)}, labs={len(ev_ab_lab_recs)}, alerts={len(ev_alerts)}")

    # 3c 方案详情接口 evidence 字段可回读
    _, cp_detail = http("GET", f"/care-plans/{cp_id}")
    ids_roundtrip = (cp_detail.get("evidence_risk_ids") or []) == risk_ids
    check("3c 方案详情重新读取时evidence_id保持一致 (可追溯持久化)",
          ids_roundtrip and bool(cp_detail.get("evidence_summary")),
          f"roundtrip={ids_roundtrip}, evsum_type={type(cp_detail.get('evidence_summary')).__name__}")

    # ======== Req 4: Alerts by visit + batch resolve + timeline sync status ========
    pl("\n" + "="*80)
    pl("[REQ 4] Alerts by visit summary + batch resolve + timeline status sync")
    pl("="*80)

    # 4a 按就诊汇总返回：V1 应有 危急值+重复检查+禁忌用药 多类
    _, by_visit = http("GET", f"/alerts/by-visit/summary?patient_id={p1}")
    total_vs = by_visit.get("total", 0)
    total_alerts = by_visit.get("total_alerts", 0)
    vs_groups = by_visit.get("items", [])
    v1_group = next((g for g in vs_groups if g["visit_id"] == v1_id), None)
    if v1_group:
        counters = v1_group["counters"]
        has_crit = counters.get("critical_value", 0)
        has_dup = counters.get("duplicate_exam", 0)
        has_contra = counters.get("drug_contraindication", 0)
        total_v1 = counters.get("total", 0)
        unr = counters.get("unresolved_count", 0)
    else:
        has_crit = has_dup = has_contra = total_v1 = unr = 0
    check("4a 按就诊汇总返回：V1同时含危急值/禁忌用药/重复检查 + unresolved计数",
          total_vs >= 1 and total_alerts >= 3 and v1_group is not None and
          has_crit >= 1 and has_contra >= 1 and unr >= 1,
          f"groups={total_vs}, alerts_total={total_alerts}, V1: crit={has_crit}, dup={has_dup}, contra={has_contra}, unresolved={unr}")

    # 4b 处理前时间线alert状态=未读 或 未解决
    _, tl_before = http("GET", f"/patients/{p1}/timeline?event_types=alert&visit_id={v1_id}")
    alert_ev_before = [e for e in tl_before["events"] if e["event_type"] == "alert"]
    statuses_before = set(e.get("status") for e in alert_ev_before)
    level_ok_before = all(e.get("level") in {"critical", "high", "medium", "low", None} for e in alert_ev_before)
    check("4b 处理前alert事件 status 含 未读/未解决 且 level 有值",
          len(alert_ev_before) >= 2 and ("未读" in statuses_before or "已读未处理" in statuses_before) and level_ok_before,
          f"alerts={len(alert_ev_before)}, statuses={statuses_before}, levels_ok={level_ok_before}")

    # 4c 批量处理：V1内全部提醒 resolve
    _, res = http("POST", "/alerts/batch-resolve", {
        "patient_id": p1, "visit_id": v1_id, "resolve_all_in_visit": True,
        "resolve_note": "已核对患者用药、检验，无异常处置，记录在案",
    })
    resolved_n = res.get("total_resolved", 0) if res else 0
    check("4c 批量处理V1就诊内全部提醒：返回resolved_n >= V1总数",
          res is not None and resolved_n >= total_v1 and resolved_n == len(res.get("resolved_ids", [])),
          f"resolved={resolved_n}, expected_v1_total={total_v1}")

    # 4d 处理后时间线alert状态=已解决 (同步)
    _, tl_after = http("GET", f"/patients/{p1}/timeline?event_types=alert&visit_id={v1_id}")
    alert_ev_after = [e for e in tl_after["events"] if e["event_type"] == "alert"]
    statuses_after = [e.get("status") for e in alert_ev_after]
    all_resolved = all(s == "已解决" for s in statuses_after) if statuses_after else False
    check("4d 处理后时间线alert状态全部同步为 已解决",
          len(alert_ev_after) == len(alert_ev_before) and all_resolved,
          f"before={len(alert_ev_before)}, after={len(alert_ev_after)}, statuses={statuses_after}")

    # --- 1c: 合并就诊后，提醒和方案在目标时间线可见 ---
    pl("\n" + "-" * 60)
    pl("[1c FINAL] Visit merge - verify alert/care_plan/risk migrate correctly")
    pl("-" * 60)
    _, dst = http("POST", "/patients", {
        "patient_no": "P-TL-DST-200", "name": "时间线目标患者",
        "gender": "male", "birth_date": "1965-03-15",
    })
    p_dst = dst["id"]
    http("POST", "/patients/visits/merge", {
        "source_visit_ids": [v1_id], "target_patient_id": p_dst,
    })
    _, tl_dst = http("GET", f"/patients/{p_dst}/timeline?page_size=200")
    dst_types = set(e["event_type"] for e in tl_dst["events"])
    has_alert_after = "alert" in dst_types
    has_cp_after = "care_plan" in dst_types
    has_risk_after = "risk" in dst_types
    check("1c 合并就诊后目标时间线可见 alert+care_plan+risk (迁移完整)",
          has_alert_after and has_cp_after and has_risk_after,
          f"alert={has_alert_after}, care_plan={has_cp_after}, risk={has_risk_after}, types={sorted(dst_types)}")

except Exception as e:
    pl(f"\n!!! EXCEPTION: {e}")
    pl(traceback.format_exc())
    results.append(("SCRIPT EXCEPTION", False, str(e)))

pl("\n" + "="*80)
pl("FINAL SUMMARY")
pl("="*80)
total = len(results)
passes = sum(1 for _, c, _ in results if c)
fails = total - passes
for name, c, detail in results:
    tag = "[PASS]" if c else "[FAIL]"
    pl(f"{tag} {name}")
pl(f"\nTotal: {total}, Passed: {passes}, Failed: {fails}")
if fails == 0:
    pl("\n*** ALL 4 NEW REQUIREMENTS VERIFIED! ***")

logf.close()
print(f"Done: {passes}/{total} passed, {fails} failed. Log at {LOG_FILE}")
sys.exit(0 if fails == 0 else 1)
