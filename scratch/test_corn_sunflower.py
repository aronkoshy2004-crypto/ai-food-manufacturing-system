import urllib.request
import json

cookie_jar = urllib.request.HTTPCookieProcessor()
opener = urllib.request.build_opener(cookie_jar)
opener.open("http://127.0.0.1:5000/demo-login/QC")

def inspect_img(img_path):
    boundary = "----LiveTestBoundary123"
    with open(img_path, "rb") as f:
        img_data = f.read()
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"target_type\"\r\n\r\nlot\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"target_id\"\r\n\r\n1\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"confidence_threshold\"\r\n\r\n0.12\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"test.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode(),
        img_data,
        f"\r\n--{boundary}--\r\n".encode()
    ]
    req = urllib.request.Request(
        "http://127.0.0.1:5000/api/qc/ai-inspect",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    resp = opener.open(req)
    return json.loads(resp.read())

print("Testing Corn Moldy Image...")
corn_res = inspect_img("datasets/raw_materials_combined/images/test/corn_20220327_0107_jpg.rf.0902cfd33ed9e744116cdf33e7b66b09.jpg")
print(f"  -> Model: {corn_res['data']['model_version']}")
print(f"  -> Status: {corn_res['data']['model_status']}")
print(f"  -> Total Defects: {corn_res['data']['total_defects_count']}")
print(f"  -> Defect Types: {set(d['defect_class'] for d in corn_res['data']['defects'])}")
print(f"  -> Summary: {corn_res['data']['summary']}")

print("\nTesting Clean Sunflower Seed Image...")
sunflower_clean_res = inspect_img("datasets/raw_materials_combined/images/test/sunflower_20250903_214217_jpg.rf.1fba1b8d4b5a8a0d185747db1c3d2764.jpg")
print(f"  -> Model: {sunflower_clean_res['data']['model_version']}")
print(f"  -> Status: {sunflower_clean_res['data']['model_status']}")
print(f"  -> Total Defects: {sunflower_clean_res['data']['total_defects_count']}")
print(f"  -> Summary: {sunflower_clean_res['data']['summary']}")

print("\nTesting Moldy Sunflower Seed Image...")
sunflower_mold_res = inspect_img("datasets/raw_materials_combined/images/test/sunflower_20250731_112859_jpg.rf.d8df887ed52efabf39ad5f4638014aa8.jpg")
print(f"  -> Model: {sunflower_mold_res['data']['model_version']}")
print(f"  -> Status: {sunflower_mold_res['data']['model_status']}")
print(f"  -> Total Defects: {sunflower_mold_res['data']['total_defects_count']}")
print(f"  -> Defect Types: {set(d['defect_class'] for d in sunflower_mold_res['data']['defects'])}")
print(f"  -> Summary: {sunflower_mold_res['data']['summary']}")
