import os
import json
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_test(img_rel_path, filename):
    cookie_jar = urllib.request.HTTPCookieProcessor()
    opener = urllib.request.build_opener(cookie_jar)
    opener.open("http://127.0.0.1:5000/demo-login/QC")

    img_path = os.path.join(PROJECT_ROOT, img_rel_path)
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    boundary = "----TestBoundaryBulkPeanut123"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"target_type\"\r\n\r\nlot\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"target_id\"\r\n\r\n1\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"confidence_threshold\"\r\n\r\n0.12\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\nContent-Type: image/jpeg\r\n\r\n".encode(),
        img_bytes,
        f"\r\n--{boundary}--\r\n".encode()
    ]
    body = b"".join(parts)
    req = urllib.request.Request(
        "http://127.0.0.1:5000/api/qc/ai-inspect",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    resp = opener.open(req)
    res = json.loads(resp.read().decode("utf-8"))
    return res.get("data", {})

def main():
    # 1. Test Dense Bulk Peanut Cluster
    print("=" * 80)
    print("RUNNING LIVE INSPECTION: DENSE BULK PEANUT CLUSTER TRAY")
    print("=" * 80)
    data = run_test(
        "datasets/raw_materials_combined/images/test/peanut_th_o2_jpg.rf.1f4aecb860ea5b664f926758694a8991.jpg",
        "bulk_peanut_cluster_o2.jpg"
    )

    print(f"Inspection ID:     {data.get('inspection_id')}")
    print(f"Model:             {data.get('model_version')}")
    print(f"Inference Time:    {data.get('inference_time_ms')} ms")
    print(f"Total Defects:     {data.get('total_defects_count')}")
    print(f"Summary:           {data.get('summary')}")
    print(f"Annotated URL:     {data.get('annotated_image_url')}")

    classes = {}
    for d in data.get("defects", []):
        c = d["defect_class"]
        classes[c] = classes.get(c, 0) + 1
    print(f"Defect Breakdown:  {classes}")

    print("\nTop 15 Peanut_Moldy Detections by Confidence:")
    sorted_d = sorted(data.get("defects", []), key=lambda x: x["confidence"], reverse=True)
    for i, d in enumerate(sorted_d[:15], 1):
        bbox = d.get("bbox", {})
        print(f"  {i:2d}. {d['defect_class']} | Conf: {d.get('confidence_percent')} | Box: [x={bbox.get('x')}%, y={bbox.get('y')}%, w={bbox.get('w')}%, h={bbox.get('h')}%]")

    # 2. Also Test a Healthy Peanut Specimen for comparison
    print("\n" + "=" * 80)
    print("RUNNING LIVE INSPECTION: HEALTHY PEANUT SPECIMEN")
    print("=" * 80)
    data_healthy = run_test(
        "datasets/raw_materials_combined/images/test/peanut_aug_IMG20240607225335_jpg.rf.a38026ce1494d35d6949b9093c2290ef.jpg",
        "healthy_peanut_specimen.jpg"
    )
    print(f"Inspection ID:     {data_healthy.get('inspection_id')}")
    print(f"Summary:           {data_healthy.get('summary')}")
    print(f"Total Defects:     {data_healthy.get('total_defects_count')}")
    print(f"Healthy Detected:  {data_healthy.get('healthy_specimens_count')}")
    for h in data_healthy.get("detected_healthy", []):
        print(f"  * {h['specimen_class']} | Conf: {h.get('confidence_percent')} | Status: {h.get('status')}")
    print(f"Annotated URL:     {data_healthy.get('annotated_image_url')}")

if __name__ == "__main__":
    main()
