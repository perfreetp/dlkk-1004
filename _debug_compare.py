import urllib.request, json
resp = urllib.request.urlopen("http://localhost:8000/api/v1/patients/1/visits/compare?visit_id1=1&visit_id2=2", timeout=30)
txt = resp.read().decode()
d = json.loads(txt)
print("=== LABS ===")
for l in d["labs"]:
    print(f"  {l['code']} ({l['name']}): {l['v1_value']} -> {l['v2_value']}  change={l['change_type']}")
print("=== RISKS ===")
for r in d["risks"]:
    print(f"  {r['code']}: {r['v1_value']} -> {r['v2_value']}  change={r['change_type']}")
print("=== MEDS ===")
for m in d["medications"]:
    print(f"  {m['code']} ({m['name']}): {m['v1_value']} -> {m['v2_value']}  change={m['change_type']}")
