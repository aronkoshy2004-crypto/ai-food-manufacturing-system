import os
import sys
import json
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEST_CASES = [
    {
        "commodity": "Peanuts",
        "type": "Dense Bulk Peanut Cluster (Real Intake Scan)",
        "path": os.path.join(PROJECT_ROOT, "static", "uploads", "raw", "20260910_012114_Screenshot_2026-09-09_221944.png"),
        "filename": "bulk_peanut_cluster.png"
    },
    {
        "commodity": "Peanuts",
        "type": "Dense Bulk Peanut Tray (165 Labeled Kernels)",
        "path": os.path.join(PROJECT_ROOT, "datasets", "raw_materials_combined", "images", "test", "peanut_th_t8_jpg.rf.1b3ce486d9f00aa56dad9e4f957de4e6.jpg"),
        "filename": "bulk_peanut_tray.jpg"
    },
    {
        "commodity": "Peanuts",
        "type": "Single / Isolated Peanut",
        "path": os.path.join(PROJECT_ROOT, "datasets", "raw_materials_combined", "images", "test", "peanut_aug_IMG20240607225203_jpg.rf.23998ad5bd1d0ee66d636d6fc899ae42.jpg"),
        "filename": "isolated_single_peanut.jpg"
    },
    {
        "commodity": "Corn",
        "type": "Dense Corn Cluster",
        "path": os.path.join(PROJECT_ROOT, "datasets", "raw_materials_combined", "images", "test", "corn_20220327_0107_jpg.rf.0902cfd33ed9e744116cdf33e7b66b09.jpg"),
        "filename": "corn_cluster.jpg"
    },
    {
        "commodity": "Sunflower Seeds",
        "type": "Sunflower Seed Cluster",
        "path": os.path.join(PROJECT_ROOT, "datasets", "raw_materials_combined", "images", "test", "sunflower_20250731_112859_jpg.rf.d8df887ed52efabf39ad5f4638014aa8.jpg"),
        "filename": "sunflower_cluster.jpg"
    }
]

def main():
    cookie_jar = urllib.request.HTTPCookieProcessor()
    opener = urllib.request.build_opener(cookie_jar)

    # 1. Login
    opener.open("http://127.0.0.1:5000/demo-login/QC")

    # 2. Verify model status
    status_resp = opener.open("http://127.0.0.1:5000/api/qc/ai-model-status")
    status_data = json.loads(status_resp.read().decode("utf-8"))
    print("=" * 80)
    print("ACTIVE MODEL STATUS:")
    print(f"  Model Name  : {status_data.get('model_name')}")
    print(f"  Model Path  : {status_data.get('model_path')}")
    print(f"  Status      : {status_data.get('status')}")
    print(f"  Classes     : {status_data.get('classes_count')}")
    print("=" * 80)

    results_summary = []

    boundary = "----FormBoundary7MA4YWxkTrZu0gW"

    for tc in TEST_CASES:
        filepath = tc["path"]
        if not os.path.exists(filepath):
            print(f"ERROR: Image not found: {filepath}")
            continue

        with open(filepath, "rb") as f:
            img_bytes = f.read()

        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"target_type\"\r\n\r\nlot\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"target_id\"\r\n\r\n1\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"confidence_threshold\"\r\n\r\n0.12\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{tc['filename']}\"\r\nContent-Type: image/jpeg\r\n\r\n".encode(),
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
        res_json = json.loads(resp.read().decode("utf-8"))
        data = res_json.get("data", {})

        tc_result = {
            "commodity": tc["commodity"],
            "type": tc["type"],
            "image_filename": tc["filename"],
            "annotated_image_url": data.get("annotated_image_url"),
            "model_version": data.get("model_version"),
            "inference_time_ms": data.get("inference_time_ms"),
            "total_defects_count": data.get("total_defects_count", 0),
            "healthy_specimens_count": data.get("healthy_specimens_count", 0),
            "summary": data.get("summary"),
            "defects": data.get("defects", []),
            "healthy": data.get("detected_healthy", [])
        }
        results_summary.append(tc_result)

        print(f"\n[{tc['commodity'].upper()} - {tc['type'].upper()}]")
        print(f"  Annotated URL : {data.get('annotated_image_url')}")
        print(f"  Inference Time: {data.get('inference_time_ms')} ms")
        print(f"  Summary       : {data.get('summary')}")
        print(f"  Defects Found : {data.get('total_defects_count', 0)}")
        for d in data.get("defects", []):
            bbox = d.get("bbox", {})
            bx = bbox.get("x", d.get("bbox_x"))
            by = bbox.get("y", d.get("bbox_y"))
            bw = bbox.get("w", d.get("bbox_w"))
            bh = bbox.get("h", d.get("bbox_h"))
            print(f"    * DEFECT  : {d['defect_class']} | Conf: {d.get('confidence_percent')} | BBox: [{bx}%, {by}%, {bw}%, {bh}%]")
        print(f"  Healthy Found : {data.get('healthy_specimens_count', 0)}")
        for h in data.get("detected_healthy", []):
            print(f"    * HEALTHY : {h['specimen_class']} | Conf: {h.get('confidence_percent')} | BBox: [{h['bbox_x']}%, {h['bbox_y']}%, {h['bbox_w']}%, {h['bbox_h']}%]")

    out_json = os.path.join(PROJECT_ROOT, "scratch", "live_inspection_test_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)
    print(f"\nSaved all test inspection results to: {out_json}")

if __name__ == "__main__":
    main()
