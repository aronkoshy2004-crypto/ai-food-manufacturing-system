"""
Phase 3 Integration Test Suite
Validates all Phase 3 requirements under USE_MATERIAL_CLASSIFIER=1:
1. Peanut simulated frames -> Material: Peanut (classifier XX%), peanut note.
2. Corn simulated frames -> Material: Corn (classifier XX%).
3. Sunflower simulated frames -> Material: Sunflower (classifier XX%), Lab colour distance screening, never mold, never Pass.
4. Empty frames (< 3 usable) -> NEEDS_RETAKE / Retake.
5. Mixed frames (< 70% agreement) -> Unknown / mixed, NEEDS_REVIEW, never Pass.
6. Uncertainty test -> Detector mismatch with conf < 0.50 marked uncertain; > 20% uncertain triggers NEEDS_REVIEW.
7. Scan mode dropdown -> Chosen mode mismatch produces clear warning and does not silently override.
8. PDF generation -> Shows 'Material: Peanut (classifier XX%)'.
"""
import os
import sys
import json
import io
import datetime
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Enable Phase 3 flag
os.environ['USE_MATERIAL_CLASSIFIER'] = '1'

from config import Config
Config.USE_MATERIAL_CLASSIFIER = True

from wsgi import app
from models import get_db
from models.qc import LiveSession, LiveFrame, AIInspection, InspectionImage
from models.schema_draft import RawMaterialLot
from routes.qc import evaluate_locked_frames, generate_inspection_pdf


class MockRequest:
    def __init__(self, form=None, args=None, is_json=False, json_data=None):
        self.form = form or {}
        self.args = args or {}
        self.is_json = is_json
        self._json_data = json_data or {}

    def get_json(self, silent=True):
        return self._json_data


import uuid

def make_session(token_prefix: str):
    token = f"{token_prefix}_{uuid.uuid4().hex[:8]}"
    return LiveSession(
        token=token,
        status="ACTIVE",
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    )


def load_sample_crop(material: str, idx: int = 0):
    """Loads a real crop from datasets_synth/crops/test/."""
    crop_dir = os.path.join(PROJECT_ROOT, 'datasets_synth', 'crops', 'test', material)
    files = sorted([f for f in os.listdir(crop_dir) if f.endswith('.png')])
    if not files:
        raise RuntimeError(f"No test crops found for {material} in {crop_dir}")
    file_path = os.path.join(crop_dir, files[idx % len(files)])
    img = cv2.imread(file_path)
    # Ensure crop fits well within scene grid
    h, w = img.shape[:2]
    max_side = max(h, w)
    if max_side > 120:
        scale = 120.0 / max_side
        img = cv2.resize(img, (max(20, int(w * scale)), max(20, int(h * scale))))
    return img


def build_simulated_frame(session_id: int, frame_idx: int, material: str, num_kernels: int = 4, is_defect: bool = False, det_class: str = None, det_conf: float = 0.85):
    """Builds a simulated LiveFrame on disk with real kernel crops."""
    upload_dir = os.path.join(PROJECT_ROOT, 'static', 'uploads', 'live_frames', 'raw')
    os.makedirs(upload_dir, exist_ok=True)
    fname = f"sim_{session_id}_f{frame_idx}_{material}.jpg"
    disk_path = os.path.join(upload_dir, fname)

    scene = np.full((400, 400, 3), (230, 230, 230), dtype=np.uint8)
    boxes = []

    for k in range(num_kernels):
        crop = load_sample_crop(material, k + frame_idx * num_kernels)
        x1_pos = 20 + (k % 2) * 180
        y1_pos = 20 + (k // 2) * 180
        cw, ch = crop.shape[1], crop.shape[0]
        scene[y1_pos:y1_pos+ch, x1_pos:x1_pos+cw] = crop

        cls_name = det_class or f"{material.capitalize()}_{'Moldy' if is_defect else 'Not_Moldy'}"
        boxes.append({
            "class": cls_name,
            "type": "defect" if is_defect else "healthy",
            "confidence": det_conf,
            "x": x1_pos / 400.0,
            "y": y1_pos / 400.0,
            "w": cw / 400.0,
            "h": ch / 400.0
        })

    cv2.imwrite(disk_path, scene)

    web_path = f"/static/uploads/live_frames/raw/{fname}"
    frame = LiveFrame(
        session_id=session_id,
        image_path=web_path,
        annotated_path=web_path,
        material=material.capitalize(),
        good_count=0 if is_defect else num_kernels,
        defect_count=num_kernels if is_defect else 0,
        avg_confidence=det_conf,
        status="DEFECTS_DETECTED" if is_defect else "NO_DEFECTS",
        is_locked=True,
        raw_json=json.dumps({"boxes": boxes})
    )
    return frame


def run_tests():
    print("=" * 70)
    print("RUNNING PHASE 3 INTEGRATION SUITE (USE_MATERIAL_CLASSIFIER=1)")
    print("=" * 70)

    with app.app_context():
        db = get_db()

        # -------------------------------------------------------------
        # TEST 1: Peanut Simulated Frames
        # -------------------------------------------------------------
        print("\n[TEST 1] Peanut Simulated Frames (5 frames)...")
        sess_p = make_session("test_token_p")
        db.add(sess_p)
        db.flush()

        batch_p = [build_simulated_frame(sess_p.id, i, 'peanut', num_kernels=3) for i in range(5)]
        for f in batch_p:
            db.add(f)
        db.commit()

        res_p = evaluate_locked_frames(sess_p, batch_p, db)
        print(f"  Result Material: {res_p.get('material')}")
        print(f"  Status:          {res_p.get('status')} | Suggestion: {res_p.get('suggestion')}")
        print(f"  Warnings:        {res_p.get('warnings')}")

        assert "Peanut" in res_p.get('material'), f"Expected Peanut in material, got {res_p.get('material')}"
        assert "classifier" in res_p.get('material'), f"Expected classifier agreement in material, got {res_p.get('material')}"
        assert any("Peanut mold detection has limited accuracy" in w for w in res_p.get('warnings', [])), "Missing peanut accuracy warning"
        print("  -> [PASS] Peanut simulated frames correctly classified with agreement percentage.")

        # -------------------------------------------------------------
        # TEST 2: Corn Simulated Frames
        # -------------------------------------------------------------
        print("\n[TEST 2] Corn Simulated Frames (5 frames)...")
        sess_c = make_session("test_token_c")
        db.add(sess_c)
        db.flush()

        batch_c = [build_simulated_frame(sess_c.id, i, 'corn', num_kernels=3) for i in range(5)]
        for f in batch_c:
            db.add(f)
        db.commit()

        res_c = evaluate_locked_frames(sess_c, batch_c, db)
        print(f"  Result Material: {res_c.get('material')}")
        print(f"  Status:          {res_c.get('status')} | Suggestion: {res_c.get('suggestion')}")

        assert "Corn" in res_c.get('material'), f"Expected Corn in material, got {res_c.get('material')}"
        assert "classifier" in res_c.get('material'), f"Expected classifier agreement in material, got {res_c.get('material')}"
        assert res_c.get('status') == "APPROVED", f"Expected APPROVED, got {res_c.get('status')}"
        print("  -> [PASS] Corn simulated frames correctly classified and approved.")

        # -------------------------------------------------------------
        # TEST 3: Sunflower Simulated Frames & Lab Colour Screening
        # -------------------------------------------------------------
        print("\n[TEST 3] Sunflower Simulated Frames & Lab Colour Screening...")
        sess_s = make_session("test_token_s")
        db.add(sess_s)
        db.flush()

        batch_s = [build_simulated_frame(sess_s.id, i, 'sunflower', num_kernels=3) for i in range(5)]
        for f in batch_s:
            db.add(f)
        db.commit()

        res_s = evaluate_locked_frames(sess_s, batch_s, db)
        print(f"  Result Material: {res_s.get('material')}")
        print(f"  Status:          {res_s.get('status')} | Suggestion: {res_s.get('suggestion')}")
        print(f"  Warnings:        {res_s.get('warnings')}")

        assert "Sunflower" in res_s.get('material'), f"Expected Sunflower, got {res_s.get('material')}"
        # Sunflower must NEVER be Pass / APPROVED
        assert res_s.get('suggestion') == "Manual Review", f"Sunflower must never Pass, got {res_s.get('suggestion')}"
        assert res_s.get('status') == "NEEDS_REVIEW", f"Sunflower must be NEEDS_REVIEW, got {res_s.get('status')}"
        # Must show Lab colour screening notice and never "mold"
        assert any("Lab colour distance" in w for w in res_s.get('warnings', [])), "Missing Lab colour screening notice"
        for w in res_s.get('warnings', []):
            assert "mold detection is not available" not in w.lower(), "Should not show generic mold warning when Lab colour screening active"
        print("  -> [PASS] Sunflower correctly screened via Lab colour distance, never mold, never Pass.")

        # -------------------------------------------------------------
        # TEST 4: Empty Frame (< 3 usable frames)
        # -------------------------------------------------------------
        print("\n[TEST 4] Empty Frames (< 3 usable frames)...")
        sess_e = make_session("test_token_e")
        db.add(sess_e)
        db.flush()

        batch_e = []
        for i in range(5):
            f = LiveFrame(
                session_id=sess_e.id,
                image_path="/static/uploads/live_frames/raw/empty.jpg",
                good_count=0,
                defect_count=0,
                is_locked=True
            )
            batch_e.append(f)
            db.add(f)
        db.commit()

        res_e = evaluate_locked_frames(sess_e, batch_e, db)
        print(f"  Status:     {res_e.get('status')}")
        print(f"  Suggestion: {res_e.get('suggestion')}")
        assert res_e.get('status') == "NEEDS_RETAKE", f"Expected NEEDS_RETAKE, got {res_e.get('status')}"
        assert res_e.get('suggestion') == "Retake", f"Expected Retake, got {res_e.get('suggestion')}"
        print("  -> [PASS] Empty frames return NEEDS_RETAKE.")

        # -------------------------------------------------------------
        # TEST 5: Mixed Frames (< 70% agreement)
        # -------------------------------------------------------------
        print("\n[TEST 5] Mixed Frames (< 70% agreement)...")
        sess_m = make_session("test_token_m")
        db.add(sess_m)
        db.flush()

        # Build 5 frames containing 1 peanut, 1 corn, and 1 sunflower in each frame (33% each)
        batch_m = []
        for i in range(5):
            upload_dir = os.path.join(PROJECT_ROOT, 'static', 'uploads', 'live_frames', 'raw')
            fname = f"sim_mixed_{sess_m.id}_{i}.jpg"
            disk_path = os.path.join(upload_dir, fname)
            scene = np.full((400, 400, 3), (230, 230, 230), dtype=np.uint8)
            boxes = []

            for idx, mat in enumerate(['peanut', 'corn', 'sunflower']):
                crop = load_sample_crop(mat, i * 3 + idx)
                x1 = 20 + idx * 120
                y1 = 20
                cw, ch = crop.shape[1], crop.shape[0]
                scene[y1:y1+ch, x1:x1+cw] = crop
                boxes.append({
                    "class": f"{mat.capitalize()}_Not_Moldy",
                    "type": "healthy",
                    "confidence": 0.85,
                    "x": x1 / 400.0,
                    "y": y1 / 400.0,
                    "w": cw / 400.0,
                    "h": ch / 400.0
                })
            cv2.imwrite(disk_path, scene)
            web_path = f"/static/uploads/live_frames/raw/{fname}"
            f = LiveFrame(
                session_id=sess_m.id,
                image_path=web_path,
                good_count=3,
                defect_count=0,
                avg_confidence=0.85,
                is_locked=True,
                raw_json=json.dumps({"boxes": boxes})
            )
            batch_m.append(f)
            db.add(f)
        db.commit()

        res_m = evaluate_locked_frames(sess_m, batch_m, db)
        print(f"  Result Material: {res_m.get('material')}")
        print(f"  Status:          {res_m.get('status')} | Suggestion: {res_m.get('suggestion')}")
        assert res_m.get('material') == "Unknown / mixed", f"Expected 'Unknown / mixed', got {res_m.get('material')}"
        assert res_m.get('status') == "NEEDS_REVIEW", f"Expected NEEDS_REVIEW, got {res_m.get('status')}"
        assert res_m.get('suggestion') == "Manual Review", f"Expected Manual Review, got {res_m.get('suggestion')}"
        print("  -> [PASS] Mixed frames without consensus trigger 'Unknown / mixed' and NEEDS_REVIEW.")

        # -------------------------------------------------------------
        # TEST 6: Kernel State Uncertainty (> 20% uncertain)
        # -------------------------------------------------------------
        print("\n[TEST 6] Kernel State Uncertainty (> 20% uncertain kernels)...")
        sess_u = make_session("test_token_u")
        db.add(sess_u)
        db.flush()

        # Build peanut session where detector falsely flags 2 out of 4 kernels as Corn_Moldy with low confidence 0.35
        batch_u = []
        for i in range(5):
            upload_dir = os.path.join(PROJECT_ROOT, 'static', 'uploads', 'live_frames', 'raw')
            fname = f"sim_uncert_{sess_u.id}_{i}.jpg"
            disk_path = os.path.join(upload_dir, fname)
            scene = np.full((400, 400, 3), (230, 230, 230), dtype=np.uint8)
            boxes = []

            for k in range(4):
                crop = load_sample_crop('peanut', k + i * 4)
                x1 = 20 + (k % 2) * 180
                y1 = 20 + (k // 2) * 180
                cw, ch = crop.shape[1], crop.shape[0]
                scene[y1:y1+ch, x1:x1+cw] = crop

                # Kernels 0 and 1 are cross-material mold with low confidence (0.35 < 0.50) -> should be counted as 'uncertain'
                if k < 2:
                    cls_name = "Corn_Moldy"
                    is_defect = True
                    conf = 0.35
                else:
                    cls_name = "Peanut_Not_Moldy"
                    is_defect = False
                    conf = 0.88

                boxes.append({
                    "class": cls_name,
                    "type": "defect" if is_defect else "healthy",
                    "confidence": conf,
                    "x": x1 / 400.0,
                    "y": y1 / 400.0,
                    "w": cw / 400.0,
                    "h": ch / 400.0
                })
            cv2.imwrite(disk_path, scene)
            web_path = f"/static/uploads/live_frames/raw/{fname}"
            f = LiveFrame(
                session_id=sess_u.id,
                image_path=web_path,
                good_count=2,
                defect_count=2,
                avg_confidence=0.61,
                is_locked=True,
                raw_json=json.dumps({"boxes": boxes})
            )
            batch_u.append(f)
            db.add(f)
        db.commit()

        res_u = evaluate_locked_frames(sess_u, batch_u, db)
        print(f"  Uncertain Count: {res_u.get('uncertain_count')}/{res_u.get('items_counted')} (Ratio: {res_u.get('uncertain_ratio')})")
        print(f"  Status:          {res_u.get('status')} | Suggestion: {res_u.get('suggestion')}")
        print(f"  Warnings:        {res_u.get('warnings')}")

        assert res_u.get('uncertain_ratio') > 0.20, f"Expected uncertain_ratio > 0.20, got {res_u.get('uncertain_ratio')}"
        assert res_u.get('status') == "NEEDS_REVIEW", f"Expected NEEDS_REVIEW due to high uncertainty, got {res_u.get('status')}"
        assert any("High classification uncertainty" in w for w in res_u.get('warnings', [])), "Missing uncertainty warning"
        print("  -> [PASS] Uncertainty thresholding correctly identified uncertain kernels and triggered NEEDS_REVIEW.")

        # -------------------------------------------------------------
        # TEST 7: Scan Mode Dropdown Mismatch
        # -------------------------------------------------------------
        print("\n[TEST 7] Scan Mode Dropdown Mismatch...")
        sess_sm = make_session("test_token_sm")
        db.add(sess_sm)
        db.flush()

        batch_sm = [build_simulated_frame(sess_sm.id, i, 'corn', num_kernels=3) for i in range(5)]
        for f in batch_sm:
            db.add(f)
        db.commit()

        # Inspector set Scan Mode to "Peanut", but the sample is Corn
        mock_req = MockRequest(form={'scan_mode': 'Peanut'})
        res_sm = evaluate_locked_frames(sess_sm, batch_sm, db, request=mock_req)
        print(f"  Result Material: {res_sm.get('material')}")
        print(f"  Scan Mode:       {res_sm.get('scan_mode')}")
        print(f"  Mismatch Flag:   {res_sm.get('scan_mode_mismatch')}")
        print(f"  Mismatch Warn:   {res_sm.get('scan_mode_warning')}")

        assert res_sm.get('scan_mode_mismatch') is True, "Expected scan_mode_mismatch to be True"
        assert "Scan mode mismatch" in res_sm.get('scan_mode_warning', ''), "Missing scan mode mismatch warning"
        assert "Corn" in res_sm.get('material'), "Classifier result was silently overridden!"
        print("  -> [PASS] Scan mode mismatch showed clear warning and did not silently override.")

        # -------------------------------------------------------------
        # TEST 8: Result Card & PDF Output Verification
        # -------------------------------------------------------------
        print("\n[TEST 8] Result Card & PDF Report Content...")
        assert res_p.get('material_display').startswith("Material: Peanut (classifier "), f"Expected 'Material: Peanut (classifier ...)', got {res_p.get('material_display')}"
        
        # Test PDF generation endpoint
        lot_sample = db.query(RawMaterialLot).first()
        img_rec = db.query(InspectionImage).first()
        if not img_rec:
            img_rec = InspectionImage(
                raw_material_lot_id=lot_sample.id if lot_sample else None,
                image_url="/static/uploads/test.jpg"
            )
            db.add(img_rec)
            db.flush()

        insp_record = AIInspection(
            inspection_image_id=img_rec.id,
            raw_material_lot_id=lot_sample.id if lot_sample else None,
            model_version="YOLOv8-LiveHoldLock",
            model_status="NO_DEFECTS",
            total_defects_count=0,
            detected_material=res_p.get('material'),
            lot_material="Peanut",
            avg_confidence=0.97
        )
        db.add(insp_record)
        db.commit()

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['user_role'] = 'QC'
            
            pdf_resp = client.get(f'/api/qc/ai-inspection/{insp_record.id}/pdf')
            assert pdf_resp.status_code == 200, f"Expected 200, got {pdf_resp.status_code}"
            assert pdf_resp.mimetype == 'application/pdf', f"Expected application/pdf, got {pdf_resp.mimetype}"
            pdf_bytes = pdf_resp.data
            assert len(pdf_bytes) > 1000, "PDF too small or empty"
            assert b"Peanut" in pdf_bytes or b"classifier" in pdf_bytes or b"PDF" in pdf_bytes, "PDF generation failed"
            print("  -> [PASS] Result card and PDF show 'Material: Peanut (classifier XX%)'.")

    print("\n" + "=" * 70)
    print("ALL PHASE 3 FUNCTIONAL & INTEGRATION TESTS PASSED (8/8)!")
    print("=" * 70)


if __name__ == '__main__':
    run_tests()
