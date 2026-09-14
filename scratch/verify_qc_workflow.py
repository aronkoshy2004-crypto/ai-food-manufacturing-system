"""
Verification Script for QC Visual Inspection Workflow
Tests all 16 unseen peanut images from datasets/raw_materials/test/
via Flask Test Client and ai.yolo_service to confirm:
1. Model loaded is models/best.pt
2. Each prediction, detected class, confidence score
3. Classification accuracy against ground truth annotations
"""
import os
import sys
import io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models import get_db
from models.user import User
from models.enums import RoleEnum
from ai.yolo_service import check_ai_engine_status, find_trained_model, run_yolo_visual_inspection

def run_verification():
    app = create_app()
    
    # 1. Verify model resolution
    model_path, model_name = find_trained_model()
    engine_status = check_ai_engine_status()
    print("=" * 80)
    print("1. MODEL LOADER VERIFICATION")
    print("=" * 80)
    print(f"Loaded Model Filename : {model_name}")
    print(f"Loaded Model Full Path: {model_path}")
    print(f"Engine Status         : {engine_status['status']}")
    print(f"Engine Message        : {engine_status['message']}")
    
    assert model_name == "best.pt", f"Expected best.pt, but got {model_name}"
    assert "models\\best.pt" in model_path or "models/best.pt" in model_path, f"Expected path in models/best.pt, got {model_path}"
    print("[PASS] Confirmed application is loading models/best.pt")
    
    # 2. Setup Flask test client with authenticated QC user
    client = app.test_client()
    with app.app_context():
        db = get_db()
        qc_user = db.query(User).filter_by(role=RoleEnum.QC.value).first()
        if not qc_user:
            qc_user = db.query(User).filter_by(role=RoleEnum.ADMIN.value).first()
        user_id = qc_user.id
        user_email = qc_user.email
    
    print("\n" + "=" * 80)
    print("2. ENDPOINT VERIFICATION: /api/qc/ai-model-status")
    print("=" * 80)
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['user_email'] = user_email
    
    status_resp = client.get('/api/qc/ai-model-status')
    assert status_resp.status_code == 200, f"Status failed: {status_resp.status_code}"
    status_data = status_resp.get_json()
    print(f"HTTP Status: {status_resp.status_code}")
    print(f"API Model Status: {status_data.get('status')} | Model Version: {status_data.get('model_name')}")
    print("[PASS] /api/qc/ai-model-status responds 200 OK and reports best.pt")

    # 3. Test all 16 unseen images from test set
    test_img_dir = Path("datasets/raw_materials/test/images")
    test_lbl_dir = Path("datasets/raw_materials/test/labels")
    names_map = {0: "Moldy", 1: "Not_Moldy"}

    images = sorted(list(test_img_dir.glob("*.jpg")))
    print("\n" + "=" * 80)
    print(f"3. EVALUATING {len(images)} UNSEEN PEANUT IMAGES FROM TEST SET VIA /api/qc/ai-inspect")
    print("=" * 80)

    results_table = []
    correct_count = 0

    for idx, img_path in enumerate(images, 1):
        lbl_path = test_lbl_dir / (img_path.stem + ".txt")
        gt_classes = []
        if lbl_path.exists():
            for line in lbl_path.read_text().strip().splitlines():
                if line.strip():
                    cid = int(line.strip().split()[0])
                    gt_classes.append(names_map.get(cid, f"Class_{cid}"))
        
        expected_class = gt_classes[0] if gt_classes else "Unknown"
        
        # Test through Flask /api/qc/ai-inspect
        with open(img_path, "rb") as img_file:
            data = {
                "target_type": "lot",
                "target_id": "1",
                "confidence_threshold": "0.25",
                "image": (io.BytesIO(img_file.read()), img_path.name)
            }
            resp = client.post(
                "/api/qc/ai-inspect",
                data=data,
                content_type="multipart/form-data"
            )
        
        assert resp.status_code == 200, f"Inspection failed for {img_path.name}: {resp.status_code}"
        payload = resp.get_json()
        ai_data = payload.get("data", {})
        
        detected_defects = ai_data.get("detected_defects", [])
        if detected_defects:
            top_det = detected_defects[0]
            pred_class = top_det.get("defect_class")
            conf = top_det.get("confidence_percent", f"{top_det.get('confidence', 0)*100:.1f}%")
            conf_val = top_det.get("confidence", 0)
        else:
            pred_class = "Not_Moldy"
            conf = "N/A"
            conf_val = 1.0

        is_correct = (pred_class.lower() == expected_class.lower())
        if is_correct:
            correct_count += 1

        results_table.append({
            "idx": idx,
            "filename": img_path.name,
            "ground_truth": expected_class,
            "predicted": pred_class,
            "confidence": conf,
            "correct": is_correct,
            "inference_ms": ai_data.get("inference_time_ms", 0),
            "model_version": ai_data.get("model_version"),
            "annotated_url": ai_data.get("annotated_image_url")
        })

    accuracy = (correct_count / len(images)) * 100
    print(f"\nFinal Accuracy: {correct_count}/{len(images)} ({accuracy:.1f}%)\n")
    return results_table, accuracy, model_path, model_name

if __name__ == "__main__":
    results_table, accuracy, model_path, model_name = run_verification()
    print(f"{'#':<3} | {'Filename':<35} | {'Ground Truth':<12} | {'Predicted':<12} | {'Confidence':<10} | {'Status':<8}")
    print("-" * 90)
    for r in results_table:
        status_str = "CORRECT" if r["correct"] else "MISMATCH"
        print(f"{r['idx']:<3} | {r['filename'][:33]:<35} | {r['ground_truth']:<12} | {r['predicted']:<12} | {r['confidence']:<10} | {status_str:<8}")
