import sys, os, json, urllib.request, urllib.error, traceback
from datetime import datetime, timedelta
from collections import Counter

LOG_FILE = "c:\\TraeProjects\\1004\\test_another_4req.txt"
logf = open(LOG_FILE, "w", encoding="utf-8")
def pl(msg=""):
    print(msg, file=logf, flush=True)

pl("=== ANOTHER 4 Reqs Regression Test (闭环+对比+汇总) ===")
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
    pl("\n[SETUP] 创建患者、2次就诊，分别录入差异数据")
    _, pa = http("POST", "/patients", {
        "patient_no": "P-CMP-2024", "name": "对比测试患者",
        "gender": "male", "birth_date": "1966-01-01",
    })
    p_id = pa["id"]

    # --- Visit 1: 初始就诊（轻） ---
    _, v1 = http("POST", "/patients/visits", {
        "patient_id": p_id, "visit_no": "V-CMP-001", "visit_type": "门诊",
        "visit_date": (datetime.now() - timedelta(days=30)).isoformat(),
        "department": "心内科", "chief_complaint": "偶发胸闷",
    })
    v1_id = v1["id"]

    http("POST", "/records/vital-signs", {
        "patient_id": p_id, "visit_id": v1_id,
        "systolic_bp": 135, "diastolic_bp": 82, "heart_rate": 75,
        "measure_time": (datetime.now() - timedelta(days=30)).isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p_id, "visit_id": v1_id,
        "test_name": "BNP", "test_code": "BNP",
        "test_value": "180", "test_unit": "pg/mL",
        "reference_low": "0", "reference_high": "100",
        "is_abnormal": True, "abnormal_flag": "H",
        "record_time": (datetime.now() - timedelta(days=30)).isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p_id, "visit_id": v1_id,
        "test_name": "肌酐", "test_code": "CREA",
        "test_value": "92", "test_unit": "μmol/L",
        "reference_low": "44", "reference_high": "133",
        "is_abnormal": False,
        "record_time": (datetime.now() - timedelta(days=30)).isoformat(),
    })
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v1_id,
        "drug_name": "阿司匹林肠溶片", "generic_name": "Aspirin",
        "dosage": "100mg", "frequency": "qd", "route": "口服",
        "start_date": (datetime.now() - timedelta(days=30)).date().isoformat(),
        "is_active": True,
    })
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v1_id,
        "drug_name": "美托洛尔缓释片", "generic_name": "Metoprolol",
        "dosage": "25mg", "frequency": "qd", "route": "口服",
        "start_date": (datetime.now() - timedelta(days=30)).date().isoformat(),
        "is_active": True,
    })
    http("POST", "/risks/calculate", {
        "patient_id": p_id, "visit_id": v1_id,
        "assessment_type": "heart_failure",
        "input_data": {
            "age": 58, "gender": "male", "has_heart_failure": False, "nyha_class": "II",
            "bnp": 180, "ejection_fraction": 50, "creatinine": 92,
            "sodium": 140,
        }
    })
    # 生成 V1 方案
    _, cp1 = http("POST", "/care-plans/generate", {
        "patient_id": p_id, "visit_id": v1_id,
        "plan_type": "hypertension", "author_id": "dr_zhang",
    })
    cp1_id = cp1["id"]
    pl(f"  V1方案ID: {cp1_id}, evidence_risks={cp1.get('evidence_risk_ids')}, evidence_active_med_ids数量={len(cp1.get('evidence_active_med_ids') or [])}")

    # --- Visit 2: 1个月后（病情加重） ---
    _, v2 = http("POST", "/patients/visits", {
        "patient_id": p_id, "visit_no": "V-CMP-002", "visit_type": "急诊",
        "visit_date": datetime.now().isoformat(),
        "department": "急诊心内科", "chief_complaint": "持续胸痛3小时",
    })
    v2_id = v2["id"]

    http("POST", "/records/vital-signs", {
        "patient_id": p_id, "visit_id": v2_id,
        "systolic_bp": 168, "diastolic_bp": 100, "heart_rate": 102,
        "measure_time": datetime.now().isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p_id, "visit_id": v2_id,
        "test_name": "BNP", "test_code": "BNP",
        "test_value": "1500", "test_unit": "pg/mL",
        "reference_low": "0", "reference_high": "100",
        "is_abnormal": True, "abnormal_flag": "HH",
        "record_time": datetime.now().isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p_id, "visit_id": v2_id,
        "test_name": "肌酐", "test_code": "CREA",
        "test_value": "92", "test_unit": "μmol/L",
        "reference_low": "44", "reference_high": "133",
        "is_abnormal": False,
        "record_time": datetime.now().isoformat(),
    })
    http("POST", "/records/lab", {
        "patient_id": p_id, "visit_id": v2_id,
        "test_name": "肌钙蛋白T", "test_code": "CTNT",
        "test_value": "2.3", "test_unit": "ng/mL",
        "reference_low": "0", "reference_high": "0.01",
        "is_abnormal": True, "abnormal_flag": "HH",
        "record_time": datetime.now().isoformat(),
    })
    # 新增1种新药，停用美托洛尔（V2不再有）
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v2_id,
        "drug_name": "阿司匹林肠溶片", "generic_name": "Aspirin",
        "dosage": "100mg", "frequency": "qd", "route": "口服",
        "start_date": datetime.now().date().isoformat(),
        "is_active": True,
    })
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v2_id,
        "drug_name": "阿托伐他汀钙片", "generic_name": "Atorvastatin",
        "dosage": "20mg", "frequency": "qn", "route": "口服",
        "start_date": datetime.now().date().isoformat(),
        "is_active": True,
    })
    # 硝酸甘油+西地那非 产生禁忌
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v2_id,
        "drug_name": "硝酸甘油片", "generic_name": "Nitroglycerin",
        "dosage": "0.5mg", "frequency": "prn", "route": "舌下含服",
        "start_date": datetime.now().date().isoformat(),
        "is_active": True,
    })
    http("POST", "/records/medications", {
        "patient_id": p_id, "visit_id": v2_id,
        "drug_name": "西地那非片", "generic_name": "Sildenafil",
        "dosage": "50mg", "frequency": "qd", "route": "口服",
        "start_date": datetime.now().date().isoformat(),
        "is_active": True,
    })
    http("POST", "/risks/calculate", {
        "patient_id": p_id, "visit_id": v2_id,
        "assessment_type": "heart_failure",
        "input_data": {
            "age": 59, "gender": "male", "has_heart_failure": True, "nyha_class": "IV",
            "bnp": 4000, "ejection_fraction": 22, "creatinine": 210,
            "sodium": 130,
        }
    })
    http("POST", "/risks/calculate", {
        "patient_id": p_id, "visit_id": v2_id,
        "assessment_type": "coronary_artery_disease",
        "input_data": {
            "age": 59, "gender": "male",
            "has_chest_pain": True, "has_st_segment_change": True,
            "has_troponin_elevation": True, "has_risk_factors": 4,
            "has_prior_mi": False, "has_aspirin_use": True,
            "has_coronary_stenosis": False, "symptom_duration_hours": 3,
        }
    })
    _, cp2 = http("POST", "/care-plans/generate", {
        "patient_id": p_id, "visit_id": v2_id,
        "plan_type": "coronary_artery_disease", "author_id": "dr_chen",
    })
    cp2_id = cp2["id"]
    pl(f"  V2方案ID: {cp2_id}, evidence_risks数量={len(cp2.get('evidence_risk_ids') or [])}, evidence_active_med_ids数量={len(cp2.get('evidence_active_med_ids') or [])}")

    # ======== Req 1: 方案依据隔离 + evidence_details ========
    pl("\n" + "="*80)
    pl("[REQ 1] 方案依据就诊隔离 + evidence_details 面板")
    pl("="*80)

    # 1a: V2方案的evidence_active_meds 只含 V2 本就诊下的 Aspirin/Atorvastatin/Nitroglycerin/Sildenafil (4种)
    cp2_med_ids = cp2.get("evidence_active_med_ids") or []
    cp2_med_details = []
    evsum2 = cp2.get("evidence_summary") or {}
    if "active_medications" in evsum2:
        cp2_med_details = evsum2["active_medications"]
    cp2_med_names = [m.get("generic_name") for m in cp2_med_details if m.get("generic_name")]
    # V2下没有 Metoprolol，所以方案里不应该有
    has_metoprolol = any("Metoprolol".lower() in (m or "").lower() for m in cp2_med_names)
    check("1a V2方案依据严格隔离：不含V1下的美托洛尔(Metoprolol)",
          len(cp2_med_ids) == 4 and not has_metoprolol,
          f"ids数量={len(cp2_med_ids)}, 药品通用名={cp2_med_names}")

    # 1b: evidence_details 结构完整（4组齐全）
    _, cp2_detail = http("GET", f"/care-plans/{cp2_id}")
    ed = cp2_detail.get("evidence_details") or {}
    grp_risk = ed.get("risk_assessments", [])
    grp_lab = ed.get("abnormal_labs", [])
    grp_med = ed.get("active_medications", [])
    grp_alert = ed.get("unresolved_alerts", [])
    check("1b 方案详情evidence_details包含4组(风险/异常检验/用药/未处理提醒)",
          len(grp_risk) >= 1 and len(grp_lab) >= 1 and len(grp_med) >= 1 and len(grp_alert) >= 1,
          f"groups: risk={len(grp_risk)}, labs={len(grp_lab)}, meds={len(grp_med)}, alerts={len(grp_alert)}")
    # 每组内的项有id可追溯
    has_id_trace = all("id" in r for r in grp_risk) and all("id" in l for l in grp_lab) and all("id" in a for a in grp_alert)
    check("1c evidence_details内每项都有id可追溯到原始记录",
          has_id_trace and len(grp_risk) == len(cp2_detail.get("evidence_risk_ids") or []),
          f"risk_ids={cp2_detail.get('evidence_risk_ids')}, grp_risk有id={all('id' in r for r in grp_risk)}")

    # ======== Req 2: 就诊对比视图 ========
    pl("\n" + "="*80)
    pl("[REQ 2] 就诊对比视图 (V1 vs V2)")
    pl("="*80)

    _, cmp = http("GET", f"/patients/{p_id}/visits/compare?visit_id1={v1_id}&visit_id2={v2_id}")
    cmp_vitals = cmp.get("vital_signs", [])
    cmp_labs = cmp.get("labs", [])
    cmp_meds = cmp.get("medications", [])
    cmp_risks = cmp.get("risks", [])
    cmp_summary = cmp.get("summary", {})

    # 2a: 生命体征收缩压 V1 135 → V2 168 = increased
    sbp = next((v for v in cmp_vitals if v.get("code") == "systolic_bp"), None)
    hr = next((v for v in cmp_vitals if v.get("code") == "heart_rate"), None)
    check("2a 生命体征对比：收缩压↑(135→168), 心率↑(75→102), delta计算正确",
          sbp and sbp.get("change_type") == "increased" and sbp.get("delta") == 33.0 and
          hr and hr.get("change_type") == "increased" and hr.get("delta") == 27.0,
          f"sbp: {sbp}; hr: {hr}")

    # 2b: 检验：BNP increased(180→1500)，CTNT new(只V2有)，CREA unchanged
    lab_bnp = next((l for l in cmp_labs if l.get("code") == "BNP"), None)
    lab_ctnt = next((l for l in cmp_labs if l.get("code") == "CTNT"), None)
    lab_crea = next((l for l in cmp_labs if l.get("code") == "CREA"), None)
    labs_detail_str = json.dumps([{"c": l.get("code"), "t": l.get("change_type"), "v1": l.get("v1_value"), "v2": l.get("v2_value")} for l in cmp_labs], ensure_ascii=False)
    check("2b 检验对比：BNP increased, CTNT new(V2新增), CREA unchanged",
          lab_bnp and lab_bnp.get("change_type") == "increased" and
          lab_ctnt and lab_ctnt.get("change_type") == "new" and
          lab_crea and lab_crea.get("change_type") == "unchanged",
          f"BNP: {(lab_bnp or {}).get('change_type')}, CTNT: {(lab_ctnt or {}).get('change_type')}, CREA: {(lab_crea or {}).get('change_type')}, ALL_LABS={labs_detail_str}")

    # 2c: 用药：Aspirin continued, Atorvastatin new(V2新增), Metoprolol removed(V2无)
    med_asp = next((m for m in cmp_meds if (m.get("code") or "").lower() == "aspirin"), None)
    med_ato = next((m for m in cmp_meds if (m.get("code") or "").lower() == "atorvastatin"), None)
    med_meto = next((m for m in cmp_meds if (m.get("code") or "").lower() == "metoprolol"), None)
    check("2c 用药对比：阿司匹林continued, 阿托伐他汀new(V2新增), 美托洛尔removed(V2无)",
          med_asp and med_asp.get("change_type") == "continued" and
          med_ato and med_ato.get("change_type") == "new" and
          med_meto and med_meto.get("change_type") == "removed",
          f"aspirin: {med_asp.get('change_type') if med_asp else None}, atorvastatin: {med_ato.get('change_type') if med_ato else None}, metoprolol: {med_meto.get('change_type') if med_meto else None}")

    # 2d: 风险heart_failure V1→V2 等级升高
    risk_hf = next((r for r in cmp_risks if r.get("code") == "heart_failure"), None)
    risk_cad = next((r for r in cmp_risks if r.get("code") == "coronary_artery_disease"), None)
    risks_detail_str = json.dumps([{"c": r.get("code"), "t": r.get("change_type"), "v1": r.get("v1_value"), "v2": r.get("v2_value")} for r in cmp_risks], ensure_ascii=False)
    check("2d 风险对比：心衰等级升高increased, CAD new(V2新增)",
          risk_hf and risk_hf.get("change_type") == "increased" and
          risk_cad and risk_cad.get("change_type") == "new",
          f"HF: {(risk_hf or {}).get('v1_value')}→{(risk_hf or {}).get('v2_value')} [{(risk_hf or {}).get('change_type')}]; CAD: {(risk_cad or {}).get('change_type')}; ALL_RISKS={risks_detail_str}")

    # 2e: summary计数总和匹配
    vs_total = cmp_summary.get("vital_signs", {}).get("total", 0)
    labs_total = cmp_summary.get("labs", {}).get("total", 0)
    meds_total = cmp_summary.get("medications", {}).get("total", 0)
    risks_total = cmp_summary.get("risks", {}).get("total", 0)
    check("2e 对比summary计数：各类总数=分组计数之和 (vital+lab+med+risk)",
          len(cmp_vitals) == vs_total and len(cmp_labs) == labs_total and len(cmp_meds) == meds_total and len(cmp_risks) == risks_total,
          f"vitals: {len(cmp_vitals)}/{vs_total}; labs: {len(cmp_labs)}/{labs_total}; meds: {len(cmp_meds)}/{meds_total}; risks: {len(cmp_risks)}/{risks_total}")

    # ======== Req 3: 提醒汇总一致性 + 组合查询 + 状态同步 ========
    pl("\n" + "="*80)
    pl("[REQ 3] 提醒汇总查询一致性 + 处理后状态同步")
    pl("="*80)

    # 3a: 总数与分组之和严格一致
    _, summ = http("GET", f"/alerts/by-visit/summary?patient_id={p_id}")
    total_alerts = (summ or {}).get("total_alerts", 0)
    sum_of_group_totals = sum(g["counters"]["total"] for g in (summ or {}).get("items", []))
    total_unresolved = (summ or {}).get("total_unresolved", 0)
    sum_of_unresolved = sum(g["counters"]["unresolved_count"] for g in (summ or {}).get("items", []))
    check("3a 提醒汇总校验：total_alerts=Σcounters.total, total_unresolved=Σcounters.unresolved_count",
          total_alerts == sum_of_group_totals and total_unresolved == sum_of_unresolved and total_alerts > 0,
          f"total_alerts={total_alerts}(Σ={sum_of_group_totals}), unresolved={total_unresolved}(Σ={sum_of_unresolved})")

    # 3b: 按alert_types= drug_contraindication,critical_value 过滤 → 总数与分组一致
    _, summ2 = http("GET", f"/alerts/by-visit/summary?patient_id={p_id}&alert_types=drug_contraindication,critical_value")
    ta2 = (summ2 or {}).get("total_alerts", 0)
    sgt2 = sum(g["counters"]["total"] for g in (summ2 or {}).get("items", []))
    # 每个分组的counters里只有drug_contraindication或critical_value
    group_types_all_ok = True
    for g in (summ2 or {}).get("items", []):
        c = g["counters"]
        if c.get("abnormal_value", 0) > 0 or c.get("duplicate_exam", 0) > 0 or c.get("other", 0) > 0:
            group_types_all_ok = False
    check("3b 组合查询alert_types：只返回指定类型 + 总数=Σ分组total",
          ta2 == sgt2 and ta2 > 0 and group_types_all_ok,
          f"filtered_total={ta2}, Σ={sgt2}, types_ok={group_types_all_ok}")

    # 3c: 按visit_no查询 → 只返回指定就诊的提醒
    _, summ3 = http("GET", f"/alerts/by-visit/summary?patient_id={p_id}&visit_no=V-CMP-002")
    group_visit_nos = set(g["visit_no"] for g in (summ3 or {}).get("items", []) if g.get("visit_no"))
    check("3c 按visit_no过滤后分组里的visit_no严格一致",
          group_visit_nos.issubset({"V-CMP-002"}) and (summ3 or {}).get("total_alerts", 0) > 0,
          f"visit_nos_in_groups={group_visit_nos}")

    # 3d: 处理后 total_unresolved 同步减少
    _, res = http("POST", "/alerts/batch-resolve", {
        "patient_id": p_id,
        "resolve_all_in_visit": False,
        "resolve_note": "一键处理所有未处理提醒",
    })
    resolved_n = res.get("total_resolved", 0) if res else 0
    _, summ_after = http("GET", f"/alerts/by-visit/summary?patient_id={p_id}")
    new_unresolved = (summ_after or {}).get("total_unresolved", 0)
    check("3d 批量处理后total_unresolved=0 (同步减少), resolve_rate 100%",
          new_unresolved == 0 and resolved_n >= total_unresolved,
          f"before_unresolved={total_unresolved}, after={new_unresolved}, resolved={resolved_n}")

    # 检查时间线alert状态是否同步为"已解决"
    _, tl_alerts = http("GET", f"/patients/{p_id}/timeline?event_types=alert&visit_id={v2_id}&page_size=50")
    alert_statuses = [e.get("status") for e in (tl_alerts or {}).get("events", [])]
    all_resolved = all(s == "已解决" for s in alert_statuses) if alert_statuses else False
    check("3e 处理后时间线alert事件状态全部为'已解决'（闭环同步）",
          len(alert_statuses) > 0 and all_resolved,
          f"alerts_in_timeline={len(alert_statuses)}, statuses={alert_statuses[:5]}")

    # ======== Req 4: 方案转随访 + 随访完成回写 + 审计统计 ========
    pl("\n" + "="*80)
    pl("[REQ 4] 方案→随访联动 + 随访完成回写 + 审计统计")
    pl("="*80)

    # 4a: 方案复诊建议一键转随访计划
    _, fu = http("POST", f"/care-plans/{cp2_id}/follow-up-convert", {
        "days_after": 7,
        "follow_up_type": "clinic",
        "purpose": "冠脉综合征出院后一周复查",
    })
    fu_id = fu.get("id") if fu else None
    fu_ok = (fu_id is not None and (fu or {}).get("patient_id") == p_id and
             (fu or {}).get("visit_id") == v2_id and
             "冠脉综合征" in ((fu or {}).get("purpose") or ""))
    check("4a 方案转随访成功：关联patient/visit/purpose含方案号",
          fu_ok,
          f"fu_id={fu_id}, pid={(fu or {}).get('patient_id')}, vid={(fu or {}).get('visit_id')}, purpose={(fu or {}).get('purpose')}")

    # 4b: 随访完成 → 时间线follow_up状态变为"已完成"
    if fu_id:
        http("PATCH", f"/follow-ups/{fu_id}/record", {
            "status": "completed",
            "actual_date": datetime.now().isoformat(),
            "examination_findings": "恢复良好，血压心率正常，无胸闷胸痛",
            "next_scheduled_date": (datetime.now() + timedelta(days=30)).isoformat(),
            "notes": "继续维持当前用药方案",
        })
    # 再创建一个V1下的随访（逾期未到，验证审计统计）
    _, fu2 = http("POST", f"/follow-ups", {
        "patient_id": p_id, "visit_id": v1_id,
        "follow_up_type": "phone",
        "scheduled_date": (datetime.now() - timedelta(days=5)).isoformat(),
        "purpose": "高血压电话随访",
    })
    fu2_id = fu2.get("id") if fu2 else None
    if fu2_id:
        # 手动把fu2标记为missed
        http("PATCH", f"/follow-ups/{fu2_id}/record", {
            "status": "missed",
            "notes": "患者未接听电话，未能完成随访",
        })
    _, tl_fus = http("GET", f"/patients/{p_id}/timeline?event_types=follow_up&page_size=20")
    fu_events = (tl_fus or {}).get("events", [])
    completed_fu = [e for e in fu_events if e.get("status") == "已完成"]
    missed_fu = [e for e in fu_events if e.get("status") == "逾期未到"]
    check("4b 随访完成回写时间线：1个'已完成' + 1个'逾期未到'状态都正确",
          len(completed_fu) >= 1 and len(missed_fu) >= 1,
          f"completed={len(completed_fu)}, missed={len(missed_fu)}, all_fu_statuses={[e.get('status') for e in fu_events]}")

    # 4c: 审计统计
    _, audit = http("GET", f"/care-plans/audit/statistics?period_days=60")
    a_alerts = (audit or {}).get("alerts", {})
    a_fus = (audit or {}).get("follow_ups", {})
    a_plans = (audit or {}).get("care_plans", {})
    # 处理后提醒 resolve_rate 应该 100%
    resolve_rate = a_alerts.get("resolve_rate_pct", -1)
    complete_rate = a_fus.get("complete_rate_pct", -1)
    alerts_total_in_audit = a_alerts.get("total", 0)
    fu_total_in_audit = a_fus.get("total", 0)
    plans_total_in_audit = a_plans.get("total", 0)
    check("4c 审计统计：提醒resolve_rate=100%, 随访完成率计算正确, 方案数>=2",
          resolve_rate == 100.0 and alerts_total_in_audit == total_alerts and
          fu_total_in_audit >= 2 and plans_total_in_audit >= 2,
          f"resolve_rate={resolve_rate}%, alerts_total={alerts_total_in_audit}, fu_total={fu_total_in_audit}, plans_total={plans_total_in_audit}, fu_complete_rate={complete_rate}%")

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
    pl("\n*** ALL 4 NEW REQS (对比+汇总+联动) VERIFIED! ***")

logf.close()
print(f"Done: {passes}/{total} passed, {fails} failed. Log at {LOG_FILE}")
sys.exit(0 if fails == 0 else 1)
