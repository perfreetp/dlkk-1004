import sys, os, json, urllib.request, urllib.error, traceback
from datetime import datetime, timedelta
from collections import Counter, defaultdict

LOG_FILE = "c:\\TraeProjects\\1004\\test_result.txt"
logf = open(LOG_FILE, "w", encoding="utf-8")
def pl(msg=""):
    print(msg, file=logf, flush=True)

pl("STARTING TEST at " + datetime.now().isoformat())

BASE = "http://localhost:8000/api/v1"
session = {}

def http(method, path, body=None):
    url = BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    pl(f"\n>>> {method} {url}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            txt = resp.read().decode("utf-8")
            pl(f"    [{resp.status}] OK")
            return resp.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        pl(f"    [ERROR {e.code}] {err[:500]}")
        return e.code, None

results = []
def check(name, cond, detail=""):
    tag = "[PASS]" if cond else "[FAIL]"
    results.append((name, cond, detail))
    pl(f"  {tag}: {name}" + (f"  -> {detail}" if detail else ""))

pl("="*80)
pl("Cardio Assist - 4 Requirements Regression Test")
pl("="*80)

try:
    # ============ Scene 1: Duplicate Exam ============
    pl("\n" + "="*60)
    pl("[Scene 1] Duplicate exam rules")
    pl("="*60)
    status, pa = http("POST", "/patients", {
        "patient_no": "P-REPEAT-01", "name": "重复检查",
        "gender": "male", "birth_date": "1970-01-01",
    })
    p1 = pa["id"]
    status, v1 = http("POST", "/patients/visits", {"patient_id": p1, "visit_no": "V-R1", "visit_type": "outpatient", "visit_time": datetime.now().isoformat()})
    v1_id = v1["id"]

    # 1a) First cTnI
    status, lab1 = http("POST", "/records/lab", {
        "patient_id": p1, "visit_id": v1_id,
        "test_name": "肌钙蛋白I", "test_code": "CTNI",
        "test_value": "0.02", "test_unit": "ng/mL",
        "record_time": datetime.now().isoformat(),
    })
    lab1_id = lab1["id"]
    status, alerts = http("GET", f"/alerts?patient_id={p1}&alert_type=duplicate_exam")
    dup_count = alerts["total"] if alerts else 0
    check("1a First cTnI -> NO duplicate alert", dup_count == 0, f"alerts={dup_count}")

    # 1b) Second cTnI
    status, lab2 = http("POST", "/records/lab", {
        "patient_id": p1, "visit_id": v1_id,
        "test_name": "肌钙蛋白I", "test_code": "CTNI",
        "test_value": "0.03", "test_unit": "ng/mL",
        "record_time": datetime.now().isoformat(),
    })
    lab2_id = lab2["id"]
    status, alerts = http("GET", f"/alerts?patient_id={p1}&alert_type=duplicate_exam&limit=50")
    dup_items = [a for a in alerts["items"] if a["related_record_id"] == lab2_id]
    check("1b Second cTnI -> SHOULD have duplicate alert", len(dup_items) >= 1,
          f"related-alerts={len(dup_items)}, title={dup_items[0]['title'] if dup_items else 'none'}")

    # 1c) Batch: 2x BNP (in-batch dup) + 1x cTnI (history dup)
    batch = [
        {"patient_id": p1, "visit_id": v1_id, "test_name": "BNP", "test_code": "BNP",
         "test_value": "120", "test_unit": "pg/mL", "record_time": datetime.now().isoformat()},
        {"patient_id": p1, "visit_id": v1_id, "test_name": "BNP", "test_code": "BNP",
         "test_value": "150", "test_unit": "pg/mL", "record_time": datetime.now().isoformat()},
        {"patient_id": p1, "visit_id": v1_id, "test_name": "肌钙蛋白I", "test_code": "CTNI",
         "test_value": "0.05", "test_unit": "ng/mL", "record_time": datetime.now().isoformat()},
    ]
    status, labs = http("POST", "/records/lab/batch", {"records": batch})
    trop_new_id = labs[2]["id"]
    bnp_new_id = labs[1]["id"]
    status, alerts = http("GET", f"/alerts?patient_id={p1}&alert_type=duplicate_exam&limit=100")
    in_batch = [a for a in alerts["items"] if a["related_record_id"] == bnp_new_id]
    history = [a for a in alerts["items"] if a["related_record_id"] == trop_new_id]
    check("1c In-batch duplicate (BNP x2) detected", len(in_batch) >= 1, f"in_batch={len(in_batch)}")
    check("1c History duplicate (cTnI again) detected", len(history) >= 1, f"history={len(history)}")

    # ============ Scene 2: Bidirectional drug contraindication ============
    pl("\n" + "="*60)
    pl("[Scene 2] Bidirectional drug contraindication")
    pl("="*60)
    status, pa = http("POST", "/patients", {"patient_no": "P-DRUG-2", "name": "双向禁忌2", "gender": "male", "birth_date": "1970-01-01"})
    p2 = pa["id"]
    status, v2 = http("POST", "/patients/visits", {"patient_id": p2, "visit_no": "V-D2", "visit_type": "outpatient", "visit_time": datetime.now().isoformat()})
    v2_id = v2["id"]

    # 2a) Nitroglycerin -> Sildenafil
    http("POST", "/records/medications", {"patient_id": p2, "visit_id": v2_id,
        "drug_name": "硝酸甘油片", "generic_name": "Nitroglycerin", "dose": "0.5mg", "frequency": "prn",
        "start_date": datetime.now().date().isoformat(), "is_active": True, "route": "sublingual"})
    http("POST", "/records/medications", {"patient_id": p2, "visit_id": v2_id,
        "drug_name": "西地那非片", "generic_name": "Sildenafil", "dose": "50mg", "frequency": "qd",
        "start_date": datetime.now().date().isoformat(), "is_active": True, "route": "oral"})
    status, alerts = http("GET", f"/alerts?patient_id={p2}&alert_type=drug_contraindication&limit=50")
    check("2a Nitrate -> Sildenafil intercepted", alerts["total"] >= 1,
          f"alerts={alerts['total']}, reason={alerts['items'][0]['content'][:120] if alerts['items'] else 'none'}")

    # 2b) Sildenafil -> Isosorbide (reverse)
    status, pa = http("POST", "/patients", {"patient_no": "P-DRUG-3", "name": "反向禁忌3", "gender": "male", "birth_date": "1970-01-01"})
    p3 = pa["id"]
    status, v3 = http("POST", "/patients/visits", {"patient_id": p3, "visit_no": "V-D3", "visit_type": "outpatient", "visit_time": datetime.now().isoformat()})
    v3_id = v3["id"]
    http("POST", "/records/medications", {"patient_id": p3, "visit_id": v3_id,
        "drug_name": "西地那非", "generic_name": "Sildenafil", "dose": "50mg", "frequency": "qd",
        "start_date": datetime.now().date().isoformat(), "is_active": True, "route": "oral"})
    http("POST", "/records/medications", {"patient_id": p3, "visit_id": v3_id,
        "drug_name": "单硝酸异山梨酯片", "generic_name": "Isosorbide Mononitrate", "dose": "40mg", "frequency": "qd",
        "start_date": datetime.now().date().isoformat(), "is_active": True, "route": "oral"})
    status, alerts = http("GET", f"/alerts?patient_id={p3}&alert_type=drug_contraindication&limit=50")
    check("2b Sildenafil -> Nitrate intercepted (reverse)", alerts["total"] >= 1, f"alerts={alerts['total']}")

    # 2c) Same batch: Captopril + Valsartan (ACEI+ARB bidirectional)
    status, pa = http("POST", "/patients", {"patient_no": "P-DRUG-4", "name": "同批配伍4", "gender": "male", "birth_date": "1970-01-01"})
    p4 = pa["id"]
    status, v4 = http("POST", "/patients/visits", {"patient_id": p4, "visit_no": "V-D4", "visit_type": "outpatient", "visit_time": datetime.now().isoformat()})
    v4_id = v4["id"]
    batch_meds = [
        {"patient_id": p4, "visit_id": v4_id, "drug_name": "卡托普利片", "generic_name": "Captopril",
         "dose": "25mg", "frequency": "tid", "start_date": datetime.now().date().isoformat(),
         "is_active": True, "route": "oral"},
        {"patient_id": p4, "visit_id": v4_id, "drug_name": "缬沙坦胶囊", "generic_name": "Valsartan",
         "dose": "80mg", "frequency": "qd", "start_date": datetime.now().date().isoformat(),
         "is_active": True, "route": "oral"},
    ]
    http("POST", "/records/medications/batch", {"records": batch_meds})
    status, alerts = http("GET", f"/alerts?patient_id={p4}&alert_type=drug_contraindication&limit=50")
    titles = [a.get("title","") for a in alerts["items"]]
    titles_lower = " ".join(titles).lower()
    has_acei_arb = "acei" in titles_lower or "arb" in titles_lower or "联用" in " ".join(titles)
    check("2c Same batch ACEI+ARB intercepted (bidirectional)", alerts["total"] >= 2 and has_acei_arb,
          f"alerts={alerts['total']}, titles={titles}")

    # ============ Scene 3: Merge visit ============
    pl("\n" + "="*60)
    pl("[Scene 3] Merge visit -> 8 record types migrated")
    pl("="*60)
    status, src_p = http("POST", "/patients", {"patient_no": "P-SRC-5", "name": "源患者5", "gender": "male", "birth_date": "1960-01-01"})
    p5 = src_p["id"]
    status, sv = http("POST", "/patients/visits", {"patient_id": p5, "visit_no": "V-SRC1", "visit_type": "outpatient", "visit_time": datetime.now().isoformat()})
    sv_id = sv["id"]

    http("POST", "/records/vital-signs", {"patient_id": p5, "visit_id": sv_id, "systolic_bp": 145, "diastolic_bp": 92, "heart_rate": 88, "measure_time": datetime.now().isoformat()})
    http("POST", "/records/ecg", {"patient_id": p5, "visit_id": sv_id, "rhythm": "窦性心律", "hr": 85, "qrs_duration_ms": 95, "qt_interval_ms": 380, "report_summary": "大致正常心电图", "record_time": datetime.now().isoformat()})
    http("POST", "/records/lab", {"patient_id": p5, "visit_id": sv_id, "test_name": "BNP", "test_code": "BNP", "test_value": "210", "test_unit": "pg/mL", "record_time": datetime.now().isoformat()})
    http("POST", "/records/medications", {"patient_id": p5, "visit_id": sv_id, "drug_name": "阿司匹林肠溶片", "generic_name": "Aspirin", "dose": "100mg", "frequency": "qd", "start_date": datetime.now().date().isoformat(), "is_active": True, "route": "oral"})
    http("POST", "/risks/calculate", {"patient_id": p5, "visit_id": sv_id,
        "assessment_type": "heart_failure", "input_data": {
            "age": 64, "gender": "male", "has_heart_failure": True, "nyha_class": 2,
            "bnp_pg_ml": 350, "ef_percent": 42, "creatinine_umol_l": 98,
            "sodium_mmol_l": 139, "has_diabetes": True, "has_hypertension": True
        }})
    http("POST", "/follow-ups", {"patient_id": p5, "visit_id": sv_id,
        "follow_up_type": "clinic",
        "scheduled_date": (datetime.now() + timedelta(days=30)).date().isoformat(),
        "notes": "出院后1月复查", "status": "scheduled"})
    http("POST", "/care-plans/generate", {"patient_id": p5, "visit_id": sv_id, "scenario": "heart_failure",
        "current_medications": [], "risks": {}, "symptoms": ["气短"]})

    status, dst_p = http("POST", "/patients", {"patient_no": "P-DST-6", "name": "目标患者6", "gender": "male", "birth_date": "1960-01-01"})
    p6 = dst_p["id"]
    status, tl = http("GET", f"/patients/{p6}/timeline")
    tl_total = len(tl["events"])
    check("3a Target patient timeline EMPTY before merge", tl_total == 0, f"before merge events={tl_total}")

    pl("\n--- Execute merge: source visit 1 -> target patient 6 ---")
    status, mg = http("POST", "/patients/visits/merge", {
        "source_visit_ids": [sv_id], "target_patient_id": p6,
        "reason": "Duplicate patient ID"
    })
    pl(json.dumps(mg, indent=2, ensure_ascii=False))

    status, tl = http("GET", f"/patients/{p6}/timeline")
    tl_events = tl["events"]
    check("3b Target timeline HAS events after merge", len(tl_events) > 0, f"events now={len(tl_events)}")
    types = [e["event_type"] for e in tl_events]
    check("3c visit migrated", "visit" in types, f"types={types}")
    check("3d vital_sign migrated", "vital_sign" in types)
    check("3e ecg migrated", "ecg" in types)
    check("3f lab migrated", "lab" in types)
    check("3g medication migrated", "medication" in types)
    check("3h risk migrated", "risk" in types)
    check("3i follow_up migrated", "follow_up" in types)
    pl(f"  Event type distribution: {dict(Counter(types))}")

    # ============ Scene 4: Multi-patient batch ============
    pl("\n" + "="*60)
    pl("[Scene 4] Multi-patient batch: no cross-contamination")
    pl("="*60)
    status, pa = http("POST", "/patients", {"patient_no": "P-X-7", "name": "患者X-华法林史", "gender": "male", "birth_date": "1950-01-01"})
    px = pa["id"]
    status, vx = http("POST", "/patients/visits", {"patient_id": px, "visit_no": "VX-1", "visit_type": "outpatient", "visit_time": datetime.now().isoformat()})
    vx_id = vx["id"]
    http("POST", "/records/medications", {"patient_id": px, "visit_id": vx_id,
        "drug_name": "华法林钠片", "generic_name": "Warfarin", "dose": "2.5mg", "frequency": "qd",
        "start_date": (datetime.now() - timedelta(days=60)).date().isoformat(),
        "is_active": True, "route": "oral"})

    status, pa = http("POST", "/patients", {"patient_no": "P-Y-8", "name": "患者Y-阿莫西林", "gender": "female", "birth_date": "1980-01-01"})
    py = pa["id"]
    status, pa = http("POST", "/patients", {"patient_no": "P-Z-9", "name": "患者Z-螺内酯", "gender": "male", "birth_date": "1965-01-01"})
    pz = pa["id"]

    multi_batch = [
        {"patient_id": px, "visit_id": vx_id, "drug_name": "布洛芬缓释胶囊", "generic_name": "Ibuprofen",
         "dose": "300mg", "frequency": "bid", "start_date": datetime.now().date().isoformat(),
         "is_active": True, "route": "oral"},
        {"patient_id": py, "visit_id": None, "drug_name": "阿莫西林胶囊", "generic_name": "Amoxicillin",
         "dose": "500mg", "frequency": "tid", "start_date": datetime.now().date().isoformat(),
         "is_active": True, "route": "oral"},
        {"patient_id": pz, "visit_id": None, "drug_name": "螺内酯片", "generic_name": "Spironolactone",
         "dose": "25mg", "frequency": "qd", "start_date": datetime.now().date().isoformat(),
         "is_active": True, "route": "oral"},
        {"patient_id": pz, "visit_id": None, "drug_name": "氯化钾缓释片", "generic_name": "Potassium Chloride",
         "dose": "1g", "frequency": "bid", "start_date": datetime.now().date().isoformat(),
         "is_active": True, "route": "oral"},
    ]
    http("POST", "/records/medications/batch", {"records": multi_batch})

    status, ax = http("GET", f"/alerts?patient_id={px}&alert_type=drug_contraindication&limit=50")
    all_x_content = " ".join(a["content"].lower() for a in ax["items"])
    x_ok = ax["total"] >= 1 and (("华法林" in " ".join(a["content"] for a in ax["items"])) or ("warfarin" in all_x_content) or ("nsaid" in all_x_content))
    check("4a Patient X (Warfarin + Ibuprofen) INTERCEPTED", x_ok,
          f"X alerts={ax['total']}, titles={[a['title'] for a in ax['items']]}")

    status, ay = http("GET", f"/alerts?patient_id={py}&alert_type=drug_contraindication&limit=50")
    check("4b Patient Y (Amoxicillin) NO false alert", ay["total"] == 0, f"Y alerts={ay['total']}")

    status, az = http("GET", f"/alerts?patient_id={pz}&alert_type=drug_contraindication&limit=50")
    all_z_content = " ".join(a["content"].lower() for a in az["items"])
    z_content_native = " ".join(a["content"] for a in az["items"])
    z_ok = az["total"] >= 1 and (("螺内酯" in z_content_native) or ("mra" in all_z_content) or ("potassium" in all_z_content) or ("钾" in z_content_native))
    check("4c Patient Z (Spironolactone + KCl) INTERCEPTED", z_ok,
          f"Z alerts={az['total']}, titles={[a['title'] for a in az['items']]}")

    # 4d No cross contamination
    all_content_y = " ".join(a["content"].lower() for a in ay["items"])
    no_cross = ("amoxicillin" not in all_x_content and "spironolactone" not in all_x_content and "potassium" not in all_x_content and
                "warfarin" not in all_content_y and "ibuprofen" not in all_content_y and
                "warfarin" not in all_z_content and "ibuprofen" not in all_z_content and "amoxicillin" not in all_z_content)
    check("4d NO cross-patient contamination", no_cross)

except Exception as e:
    pl(f"\n!!! UNHANDLED EXCEPTION: {e}")
    pl(traceback.format_exc())
    results.append(("SCRIPT EXCEPTION", False, str(e)))

# ============ Summary ============
pl("\n" + "="*80)
pl("SUMMARY")
pl("="*80)
total = len(results)
passes = sum(1 for _, c, _ in results if c)
fails = total - passes
for name, c, detail in results:
    tag = "[PASS]" if c else "[FAIL]"
    pl(f"{tag} {name}")
pl(f"\nTotal: {total}, Passed: {passes}, Failed: {fails}")
if fails == 0:
    pl("\n*** ALL 4 REQUIREMENTS VERIFIED! ***")
else:
    pl(f"\n!!! {fails} FAILED, please check code.")

logf.close()
print(f"TEST DONE: {passes}/{total} passed, {fails} failed. See test_result.txt")
sys.exit(0 if fails == 0 else 1)
