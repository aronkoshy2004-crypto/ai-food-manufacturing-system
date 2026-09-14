import urllib.request
import json

cookie_jar = urllib.request.HTTPCookieProcessor()
opener = urllib.request.build_opener(cookie_jar)

# 1. Login
opener.open("http://127.0.0.1:5000/demo-login/QC")

# 2. Check AI Engine Status
status_resp = opener.open("http://127.0.0.1:5000/api/qc/ai-model-status")
status_data = json.loads(status_resp.read())
print(f"[LIVE CHECK] AI Model Status: {status_data.get('status')}, Model: {status_data.get('model_name')}")

# 3. Multipart Upload for Inspection
boundary = "----TestBoundary12345"
with open("static/uploads/raw/20260910_012114_Screenshot_2026-09-09_221944.png", "rb") as f:
    img_data = f.read()

parts = [
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"target_type\"\r\n\r\nlot\r\n".encode(),
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"target_id\"\r\n\r\n1\r\n".encode(),
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"confidence_threshold\"\r\n\r\n0.12\r\n".encode(),
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"bulk.png\"\r\nContent-Type: image/png\r\n\r\n".encode(),
    img_data,
    f"\r\n--{boundary}--\r\n".encode()
]
body = b"".join(parts)

req = urllib.request.Request(
    "http://127.0.0.1:5000/api/qc/ai-inspect",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
)

resp = opener.open(req)
res_json = json.loads(resp.read())
print(f"[LIVE CHECK] /api/qc/ai-inspect Success: {res_json.get('success')}")
print(f"[LIVE CHECK] Total Defects Count: {res_json['data']['total_defects_count']}")
for d in res_json["data"]["defects"]:
    print(f"  -> Defect: {d['defect_class']} | Severity: {d.get('severity', 'CRITICAL')} | Conf: {d['confidence_percent']}")
