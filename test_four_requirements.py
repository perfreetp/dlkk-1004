import urllib.request
import json
import time
from urllib.parse import urlencode
from collections import defaultdict

BASE = "http://localhost:8000/api/v1"

def api(method, path, data=None, query=None, print_body=False):
    full = f"{BASE}{path}"
    if query:
        full += "?" + urlencode(query)
    print(f"\n>>> {method} {full}")
    req = urllib.request.Request(full, method=method)
    req.add_header("Content-Type", "application/json")
    if data:
        req.data = json.dumps(data, ensure_ascii=False).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body)
            if print_body:
                print(f"    [{resp.status}] {json.dumps(parsed, ensure_ascii=False, indent=2)[:1500]}")
            else:
                print(f"    [{resp.status}] OK")
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"    [ERROR {e.code}] {err[:500]}")
        return e.code, None

results = []
def check(name, condition, detail=""):
    status = "[PASS]" if condition else "[FAIL]"
    results.append((name, condition, detail))
    print(f"  {status}: {name}" + (f"  -> {detail}" if detail else ""))

print("=" * 80)
print("心内科辅助诊疗服务 - 4项需求专项回归测试")
print("=" * 80)

# ================ 场景1：重复检查提醒（首次不误报+历史才报）================
print("\n" + "=" * 60)
print("【场景1】检验重复检查规则")
print("=" * 60)

# 创建患者A
_, pa = api("POST", "/patients", {
    "patient_no": "P-REPEAT-01", "name": "重复检查测试人",
    "gender": "男", "birth_date": "1970-01-01", "department": "心内科",
})
pa_id = pa["id"]

# 1a: 首次录入肌钙蛋白 - 不应产生重复检查提醒
print("\n--- 1a) 第一次录入肌钙蛋白（历史为空，不应有重复提醒）---")
_, lab1 = api("POST", "/records/lab", {
    "patient_id": pa_id, "lab_type": "cardiac",
    "test_name": "肌钙蛋白I", "test_code": "troponin_i",
    "test_value": 0.01, "test_unit": "ng/mL",
    "reference_low": 0, "reference_high": 0.04,
})
time.sleep(0.3)
_, alerts = api("GET", "/alerts", query={"patient_id": pa_id, "alert_type": "duplicate_exam"})
dup_count = alerts["total"]
check("首次录入无重复检查提示", dup_count == 0, f"重复提醒数={dup_count}（应为0）")

# 1b: 第二次录入肌钙蛋白 - 应触发重复提醒
print("\n--- 1b) 第二次录入肌钙蛋白（历史已有，应触发提醒）---")
_, lab2 = api("POST", "/records/lab", {
    "patient_id": pa_id, "lab_type": "cardiac",
    "test_name": "肌钙蛋白I", "test_code": "troponin_i",
    "test_value": 0.05, "test_unit": "ng/mL",
    "reference_low": 0, "reference_high": 0.04,
})
time.sleep(0.3)
_, alerts = api("GET", "/alerts", query={"patient_id": pa_id, "alert_type": "duplicate_exam"})
dup_items = [a for a in alerts["items"] if a["related_record_id"] == lab2["id"]]
check("第二次录入出现重复检查提示", len(dup_items) == 1,
      f"相关重复提醒数={len(dup_items)}（应为1）")
if dup_items:
    print(f"    提醒内容: {dup_items[0]['content'][:100]}...")

# 1c: 批量录入含同项目 - 批次内重复+历史重复分别提示
print("\n--- 1c) 批量录入（含历史重复+批次内重复，都应识别）---")
_, labs = api("POST", "/records/lab/batch", {"records": [
    {"patient_id": pa_id, "lab_type": "cardiac", "test_name": "BNP", "test_code": "bnp",
     "test_value": 50, "test_unit": "pg/mL", "reference_low": 0, "reference_high": 100},
    {"patient_id": pa_id, "lab_type": "cardiac", "test_name": "BNP", "test_code": "bnp",
     "test_value": 55, "test_unit": "pg/mL", "reference_low": 0, "reference_high": 100},
    {"patient_id": pa_id, "lab_type": "cardiac", "test_name": "肌钙蛋白I", "test_code": "troponin_i",
     "test_value": 0.03, "test_unit": "ng/mL", "reference_low": 0, "reference_high": 0.04},
]})
time.sleep(0.3)
_, alerts = api("GET", "/alerts", query={"patient_id": pa_id, "alert_type": "duplicate_exam", "limit": 100})
dup_items = alerts["items"]
bnp_new_ids = [l["id"] for l in labs if l["test_code"] == "bnp"]
trop_new_ids = [l["id"] for l in labs if l["test_code"] == "troponin_i"]
in_batch = [a for a in dup_items if "本批次内" in a["content"]]
historical = [a for a in dup_items if a["related_record_id"] in trop_new_ids]
check("批次内重复识别（BNP两条）", len(in_batch) >= 1, f"批次内类提醒数={len(in_batch)}")
check("历史重复识别（肌钙蛋白再次录入）", len(historical) >= 1, f"历史类提醒数={len(historical)}")

# ================ 场景2：用药禁忌双向识别 ================
print("\n" + "=" * 60)
print("【场景2】用药禁忌双向识别+禁忌原因清晰")
print("=" * 60)

_, pb = api("POST", "/patients", {
    "patient_no": "P-DRUG-01", "name": "用药测试人A",
    "gender": "男", "birth_date": "1965-01-01", "department": "心内科",
})
pb_id = pb["id"]

# 2a: 先录入硝酸甘油，再录入西地那非 -> 应拦截
print("\n--- 2a) 先录入硝酸甘油，再录入西地那非（正向：A药+B药）---")
_, med1 = api("POST", "/records/medications", {
    "patient_id": pb_id, "drug_name": "硝酸甘油片", "generic_name": "nitroglycerin",
    "drug_category": "硝酸酯类", "dosage": "0.5mg", "frequency": "舌下含服必要时", "is_active": True,
})
time.sleep(0.3)
_, med2 = api("POST", "/records/medications", {
    "patient_id": pb_id, "drug_name": "西地那非", "generic_name": "sildenafil",
    "drug_category": "PDE5抑制剂", "dosage": "50mg", "frequency": "QD", "is_active": True,
})
time.sleep(0.5)
_, alerts = api("GET", "/alerts", query={"patient_id": pb_id, "alert_type": "drug_contraindication", "limit": 50})
正向拦截 = [a for a in alerts["items"] if "硝酸甘油" in a["content"] and "西地那非" in a["content"]]
检查1 = len(正向拦截) > 0
check("正向顺序拦截（硝酸甘油→西地那非）", 检查1, f"命中数={len(正向拦截)}")
if 正向拦截:
    print(f"    禁忌标题: {正向拦截[0]['title']}")
    print(f"    原因内容: {正向拦截[0]['content'][:150]}...")

# 2b: 反向顺序 - 新建患者先录西地那非，再录硝酸甘油 -> 也应拦截
print("\n--- 2b) 反向顺序：先录西地那非，再录硝酸甘油（反向：B药+A药）---")
_, pb2 = api("POST", "/patients", {
    "patient_no": "P-DRUG-02", "name": "用药测试人B",
    "gender": "女", "birth_date": "1972-05-05", "department": "心内科",
})
pb2_id = pb2["id"]
api("POST", "/records/medications", {
    "patient_id": pb2_id, "drug_name": "枸橼酸西地那非片", "generic_name": "sildenafil citrate",
    "dosage": "50mg", "frequency": "QD", "is_active": True,
})
time.sleep(0.3)
api("POST", "/records/medications", {
    "patient_id": pb2_id, "drug_name": "硝酸异山梨酯片", "generic_name": "isosorbide dinitrate",
    "dosage": "10mg", "frequency": "TID", "is_active": True,
})
time.sleep(0.5)
_, alerts2 = api("GET", "/alerts", query={"patient_id": pb2_id, "alert_type": "drug_contraindication", "limit": 50})
反向拦截 = [a for a in alerts2["items"] if "硝酸" in a["content"] or "西地那非" in a["content"]]
检查2 = len(反向拦截) > 0
check("反向顺序拦截（西地那非→硝酸酯）", 检查2, f"命中数={len(反向拦截)}")

# 2c: 同一批次同时录入ACEI+缬沙坦 -> 应双向识别
print("\n--- 2c) 同批次同时录入卡托普利+缬沙坦（配伍禁忌应双向识别）---")
_, pb3 = api("POST", "/patients", {
    "patient_no": "P-DRUG-03", "name": "用药测试人C",
    "gender": "男", "birth_date": "1968-08-08", "department": "心内科",
})
pb3_id = pb3["id"]
_, meds_batch = api("POST", "/records/medications/batch", {"records": [
    {"patient_id": pb3_id, "drug_name": "卡托普利片", "generic_name": "captopril",
     "dosage": "25mg", "frequency": "TID", "is_active": True},
    {"patient_id": pb3_id, "drug_name": "缬沙坦胶囊", "generic_name": "valsartan",
     "dosage": "80mg", "frequency": "QD", "is_active": True},
]})
time.sleep(0.5)
_, alerts3 = api("GET", "/alerts", query={"patient_id": pb3_id, "alert_type": "drug_contraindication", "limit": 50})
配伍拦截 = [a for a in alerts3["items"] if "本次同批" in a["content"]]
检查3 = len(配伍拦截) >= 1
check("批次内配伍拦截（ACEI+ARB双向识别）", 检查3, f"命中数={len(配伍拦截)}")
if 配伍拦截:
    print(f"    提醒类别: {配伍拦截[0]['title']}")
    print(f"    提醒内容: {配伍拦截[0]['content'][:200]}...")

# ================ 场景3：合并就诊+关联数据迁移 ================
print("\n" + "=" * 60)
print("【场景3】就诊合并后8类数据归入目标患者")
print("=" * 60)

# 源患者S
_, ps = api("POST", "/patients", {
    "patient_no": "P-SRC-001", "name": "源患者（将合并）",
    "gender": "男", "birth_date": "1955-03-03", "department": "心内科",
})
ps_id = ps["id"]

# 源患者下的就诊V1
_, v1 = api("POST", "/patients/visits", {
    "patient_id": ps_id, "visit_no": "V-SRC-001", "visit_type": "住院",
    "department": "心内科CCU", "doctor_id": "DR-007",
    "chief_complaint": "持续性胸痛4小时",
    "diagnosis": [{"code": "I21.9", "name": "急性ST段抬高型心肌梗死"}],
    "is_emergency": True,
})
v1_id = v1["id"]

# 在源患者下录入各类关联数据（绑定visit_id）
api("POST", "/records/vital-signs", {"patient_id": ps_id, "visit_id": v1_id,
    "systolic_bp": 145, "diastolic_bp": 95, "heart_rate": 98, "source": "CCU"})
api("POST", "/records/ecg", {"patient_id": ps_id, "visit_id": v1_id,
    "ecg_type": "12导联常规", "heart_rate": 102, "rhythm": "窦性心动过速",
    "st_segment": "V1-V4 ST段弓背向上抬高0.3-0.5mV",
    "is_abnormal": True, "interpretation": "急性前壁心肌梗死图形"})
api("POST", "/records/lab", {
    "patient_id": ps_id, "visit_id": v1_id, "lab_type": "cardiac",
    "test_name": "高敏肌钙蛋白T", "test_code": "troponin_t",
    "test_value": 2.5, "test_unit": "ng/mL", "reference_low": 0, "reference_high": 0.01})
api("POST", "/records/medications", {
    "patient_id": ps_id, "visit_id": v1_id, "drug_name": "阿司匹林肠溶片", "generic_name": "aspirin",
    "dosage": "300mg", "frequency": "一次顿服", "is_active": True})
api("POST", "/risks/calculate", {
    "patient_id": ps_id, "visit_id": v1_id,
    "assessment_type": "coronary_artery_disease",
    "input_data": {"age": 71, "family_history_cad": True, "hypertension": True,
                   "diabetes": True, "hyperlipidemia": True, "smoking": True,
                   "known_cad_stenosis_ge50": True, "severe_angina": True,
                   "st_depression_ge05mm": True, "positive_cardiac_marker": True,
                   "rest_angina_within_24h": True}})
api("POST", "/follow-ups", {
    "patient_id": ps_id, "visit_id": v1_id,
    "follow_up_type": "post_pci",
    "scheduled_date": "2026-07-09T10:00:00",
    "purpose": "PCI术后1月复诊", "assigned_doctor_id": "DR-007"})
api("POST", "/care-plans/generate", {
    "patient_id": ps_id, "visit_id": v1_id,
    "plan_type": "coronary_artery_disease", "author_id": "DR-007"})

time.sleep(1.0)

# 创建目标患者T
_, pt = api("POST", "/patients", {
    "patient_no": "P-TGT-001", "name": "目标患者（合并接收方）",
    "gender": "男", "birth_date": "1955-03-03", "department": "心内科",
})
pt_id = pt["id"]

# 查合并前目标患者时间线
_, tl_before = api("GET", f"/patients/{pt_id}/timeline")
before_count = len(tl_before["events"])
check("合并前目标患者时间线为空", before_count == 0, f"事件数={before_count}")

# 执行合并
print(f"\n--- 执行就诊合并: 源患者{ps_id}就诊{v1_id} -> 目标患者{pt_id} ---")
_, merge_r = api("POST", "/patients/visits/merge", {
    "target_patient_id": pt_id, "source_visit_ids": [v1_id],
    "merge_note": "患者编号重复，合并为同一患者档案"
}, print_body=True)

# 查合并后目标患者时间线
time.sleep(0.8)
_, tl_after = api("GET", f"/patients/{pt_id}/timeline")
after_count = len(tl_after["events"])
合并类型 = defaultdict(int)
for e in tl_after["events"]:
    合并类型[e["event_type"]] += 1

check("合并后目标患者时间线事件数显著增加", after_count > 5,
      f"合并前{before_count}条，合并后{after_count}条")
check("就诊记录迁移", 合并类型["visit"] >= 1, f"visit类={合并类型.get('visit',0)}")
check("生命体征迁移", 合并类型["vital_sign"] >= 1, f"vital_sign类={合并类型.get('vital_sign',0)}")
check("心电记录迁移", 合并类型["ecg"] >= 1, f"ecg类={合并类型.get('ecg',0)}")
check("检验记录迁移", 合并类型["lab"] >= 1, f"lab类={合并类型.get('lab',0)}")
check("用药记录迁移", 合并类型["medication"] >= 1, f"medication类={合并类型.get('medication',0)}")
check("风险评估迁移", 合并类型["risk"] >= 1, f"risk类={合并类型.get('risk',0)}")
check("随访安排迁移", 合并类型["follow_up"] >= 1, f"follow_up类={合并类型.get('follow_up',0)}")
print(f"    合并后各类别分布: {dict(合并类型)}")

# ================ 场景4：批量多患者用药，按患者分组不串不漏 ================
print("\n" + "=" * 60)
print("【场景4】多患者混合批量用药：按患者分组，不串不漏")
print("=" * 60)

# 患者X（已有华法林）
_, px = api("POST", "/patients", {
    "patient_no": "P-BATCH-X", "name": "批量患者X（华法林史）",
    "gender": "女", "birth_date": "1958-02-02", "department": "心内科",
})
px_id = px["id"]
api("POST", "/records/medications", {
    "patient_id": px_id, "drug_name": "华法林钠片", "generic_name": "warfarin sodium",
    "dosage": "2.5mg", "frequency": "QD", "is_active": True,
})

# 患者Y（干净，无既往禁忌用药）
_, py = api("POST", "/patients", {
    "patient_no": "P-BATCH-Y", "name": "批量患者Y（无禁忌史）",
    "gender": "男", "birth_date": "1980-07-07", "department": "心内科",
})
py_id = py["id"]

# 患者Z（干净）
_, pz = api("POST", "/patients", {
    "patient_no": "P-BATCH-Z", "name": "批量患者Z（无禁忌史）",
    "gender": "女", "birth_date": "1985-09-09", "department": "心内科",
})
pz_id = pz["id"]

time.sleep(0.3)

# 批量混合录入：X用布洛芬（华法林+NSAIDs禁忌）、Y用阿莫西林（无禁忌）、Z用螺内酯+氯化钾（配伍禁忌）
print("\n--- 批量录入：X(华法林史+布洛芬/禁忌), Y(阿莫西林/无), Z(螺内酯+氯化钾/配伍) ---")
_, mixed_meds = api("POST", "/records/medications/batch", {"records": [
    {"patient_id": px_id, "drug_name": "布洛芬缓释胶囊", "generic_name": "ibuprofen",
     "dosage": "300mg", "frequency": "BID", "is_active": True},
    {"patient_id": py_id, "drug_name": "阿莫西林胶囊", "generic_name": "amoxicillin",
     "dosage": "0.5g", "frequency": "TID", "is_active": True},
    {"patient_id": pz_id, "drug_name": "螺内酯片", "generic_name": "spironolactone",
     "dosage": "25mg", "frequency": "QD", "is_active": True},
    {"patient_id": pz_id, "drug_name": "氯化钾缓释片", "generic_name": "potassium chloride",
     "dosage": "1g", "frequency": "TID", "is_active": True},
]})

time.sleep(1.0)

# 检查各患者禁忌提醒
_, alerts_x = api("GET", "/alerts", query={"patient_id": px_id, "alert_type": "drug_contraindication", "limit": 50})
_, alerts_y = api("GET", "/alerts", query={"patient_id": py_id, "alert_type": "drug_contraindication", "limit": 50})
_, alerts_z = api("GET", "/alerts", query={"patient_id": pz_id, "alert_type": "drug_contraindication", "limit": 50})

x_hits = len(alerts_x["items"])
y_hits = len(alerts_y["items"])
z_hits = len(alerts_z["items"])

x正确 = x_hits >= 1 and all("华法林" in a["content"] or "布洛芬" in a["content"] for a in alerts_x["items"])
y正确 = y_hits == 0  # 无禁忌
z正确 = z_hits >= 1 and any("螺内酯" in a["content"] and "氯化钾" in a["content"] for a in alerts_z["items"])
no串扰 = (
    not any("螺内酯" in a["content"] or "氯化钾" in a["content"] for a in alerts_x["items"])
    and not any("华法林" in a["content"] for a in alerts_z["items"])
    and not any("阿莫西林" in a["content"] for a in alerts_x["items"] + alerts_z["items"])
)

check("患者X（华法林+布洛芬）禁忌被正确识别", x正确, f"X命中={x_hits},内容正确={x正确}")
check("患者Y（阿莫西林）无禁忌，不误报", y正确, f"Y命中={y_hits}（应为0）")
check("患者Z（螺内酯+氯化钾同批）配伍被识别", z正确, f"Z命中={z_hits},内容正确={z正确}")
check("三患者之间禁忌不串扰", no串扰, "无跨患者禁忌错误命中")

# ================ 汇总 ================
print("\n" + "=" * 80)
print("回归测试汇总结果")
print("=" * 80)
total = len(results)
passes = sum(1 for _, c, _ in results if c)
fails = total - passes
for name, c, detail in results:
    tag = "[PASS]" if c else "[FAIL]"
    print(f"{tag} {name}")
print(f"\n总计: {total}项, 通过: {passes}, 失败: {fails}")
if fails == 0:
    print("*** 4项需求全部验证通过! ***")
else:
    print(f"! {fails}项未通过，请检查相关代码。")
