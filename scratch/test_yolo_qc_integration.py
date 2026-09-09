import os
import sys
import io
import json

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from app import create_app
from models import get_db
from models.qc import AIInspection, InspectionImage, DetectedDefect, QCDecision
from models.procurement import RawMaterialLot
from models.production import Product, ProductionBatch


def create_test_image_bytes():
    # 1x1 red PNG bytes
    png_bytes = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02'
        b'\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01'
        b'\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    buf = io.BytesIO(png_bytes)
    return buf


def run_tests():
    app = create_app()
    client = app.test_client()

    with app.app_context():
        # Authenticate test client as QC Executive
        login_res = client.get('/demo-login/QC', follow_redirects=True)
        assert login_res.status_code == 200, f"Demo login failed: {login_res.status_code}"

        session = get_db()
        print("--- [TEST 1] AI Model Status API ---")
        res = client.get('/api/qc/ai-model-status')

        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        status_data = res.get_json()
        print(f"Model status response: {status_data}")
        assert 'status' in status_data
        assert 'message' in status_data
        assert 'training_workflow' in status_data
        print("✓ Test 1 Passed: /api/qc/ai-model-status reports status accurately without crashes.")


        print("\n--- [TEST 2] AI Inspect Raw Material Lot ---")
        test_lot = session.query(RawMaterialLot).first()
        assert test_lot is not None, "A raw material lot must exist in database"
        
        img_buf = create_test_image_bytes()
        data = {
            'image': (img_buf, 'dock_peanut_intake.jpg'),
            'target_type': 'lot',
            'target_id': str(test_lot.id),
            'confidence_threshold': '0.30'
        }
        res = client.post('/api/qc/ai-inspect', data=data, content_type='multipart/form-data')
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
        inspect_data = res.get_json()
        assert inspect_data['success'] is True
        ai_res = inspect_data['ai_result']
        print(f"Inspection Result: id={ai_res['inspection_id']}, model_status={ai_res['model_status']}")
        assert ai_res['raw_image_url'] is not None
        assert ai_res['annotated_image_url'] is not None
        assert 'timestamp' in ai_res
        assert 'defects' in ai_res
        
        # Verify in DB
        db_image = session.get(InspectionImage, ai_res['image_id'])
        assert db_image is not None
        assert db_image.raw_material_lot_id == test_lot.id
        
        db_ai = session.get(AIInspection, ai_res['inspection_id'])
        assert db_ai is not None
        assert db_ai.raw_material_lot_id == test_lot.id
        print("✓ Test 2 Passed: Lot image inspected, stored in DB and linked to lot.")

        print("\n--- [TEST 3] AI Inspect Finished Food Product ---")
        test_product = session.query(Product).first()
        if test_product:
            img_buf = create_test_image_bytes()
            data = {
                'image': (img_buf, 'finished_product_pack.jpg'),
                'target_type': 'product',
                'target_id': str(test_product.id)
            }
            res = client.post('/api/qc/ai-inspect', data=data, content_type='multipart/form-data')
            assert res.status_code == 200
            prod_ai = res.get_json()['ai_result']
            db_img = session.get(InspectionImage, prod_ai['image_id'])
            assert db_img.product_id == test_product.id
            print(f"✓ Test 3 Passed: Product image linked to product #{test_product.id}.")
        else:
            print("⚠ Test 3 Skipped: No product in DB.")

        print("\n--- [TEST 4] AI Inspect Production Batch ---")
        test_batch = session.query(ProductionBatch).first()
        if test_batch:
            img_buf = create_test_image_bytes()
            data = {
                'image': (img_buf, 'line_batch_inspection.jpg'),
                'target_type': 'batch',
                'target_id': str(test_batch.id)
            }
            res = client.post('/api/qc/ai-inspect', data=data, content_type='multipart/form-data')
            assert res.status_code == 200
            batch_ai = res.get_json()['ai_result']
            db_img = session.get(InspectionImage, batch_ai['image_id'])
            assert db_img.production_batch_id == test_batch.id
            print(f"✓ Test 4 Passed: Batch image linked to batch #{test_batch.id}.")
        else:
            print("⚠ Test 4 Skipped: No production batch in DB.")

        print("\n--- [TEST 5] Inspection History Query ---")
        res = client.get(f'/api/qc/ai-inspections?lot_id={test_lot.id}')
        assert res.status_code == 200
        history = res.get_json()
        assert history['count'] >= 1
        print(f"✓ Test 5 Passed: History returned {history['count']} inspections for lot {test_lot.id}.")

        print("\n--- [TEST 6] Four-Pillar QC Decision Gate (Sign-Off) ---")
        # 6a. Test HOLD decision
        res = client.post('/api/qc/decision', json={
            'target_type': 'lot',
            'target_id': test_lot.id,
            'final_status': 'HOLD',
            'reason': 'Awaiting further microbial confirmation',
            'action_notes': 'Placed in quarantine warehouse section B'
        })
        assert res.status_code == 200
        session.refresh(test_lot)
        assert test_lot.qc_status == 'HOLD', f"Expected HOLD, got {test_lot.qc_status}"
        print(f"✓ Test 6a Passed: HOLD decision recorded, lot status is {test_lot.qc_status}.")

        # 6b. Test REJECTED decision
        res = client.post('/api/qc/decision', json={
            'target_type': 'lot',
            'target_id': test_lot.id,
            'final_status': 'REJECTED',
            'reason': 'Moisture levels exceed specification limits',
            'action_notes': 'Marked for return to supplier'
        })
        assert res.status_code == 200
        session.refresh(test_lot)
        assert test_lot.qc_status == 'REJECTED', f"Expected REJECTED, got {test_lot.qc_status}"
        print(f"✓ Test 6b Passed: REJECTED decision recorded, lot status is {test_lot.qc_status}.")

        # 6c. Test APPROVED decision
        res = client.post('/api/qc/decision', json={
            'target_type': 'lot',
            'target_id': test_lot.id,
            'final_status': 'APPROVED',
            'reason': 'All 4 pillars verified: Lab PASS, COA valid, YOLO visual clean, Specs conform',
            'action_notes': 'Released to production storage silo 3'
        })
        assert res.status_code == 200
        session.refresh(test_lot)
        assert test_lot.qc_status == 'APPROVED', f"Expected APPROVED, got {test_lot.qc_status}"
        print(f"✓ Test 6c Passed: APPROVED decision recorded, lot status is {test_lot.qc_status}.")

        # Verify decision log in DB
        decisions = session.query(QCDecision).filter_by(raw_material_lot_id=test_lot.id).all()
        assert len(decisions) >= 3
        print(f"✓ Test 6d Passed: All {len(decisions)} decision audit logs properly recorded in DB.")

        print(f"✓ Test 6d Passed: All {len(decisions)} decision audit logs properly recorded in DB.")

        print("\n--- [TEST 7] Page Rendering ---")
        res = client.get('/qc?view=ai-inspection')
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "AI VISUAL INSPECTION WORKSPACE (YOLOv8)" in html
        assert "SPECIMEN PHOTO INGESTION" in html
        assert "YOLOv8 INSPECTION RESULT" in html
        assert "FINAL QUALITY DECISION GATE (HUMAN SPECIALIST SIGN-OFF)" in html
        assert "aiFileInput" in html
        print("✓ Test 7 Passed: /qc?view=ai-inspection renders full UI.")

        res = client.get('/dashboard')
        assert res.status_code == 200
        dash_html = res.get_data(as_text=True)
        assert "AI VISUAL QUALITY" in dash_html
        print("✓ Test 8 Passed: Dashboard features AI visual inspection widget.")

        print("\n==========================================")
        print("ALL YOLOv8 QC INTEGRATION TESTS PASSED! 🎉")
        print("==========================================")

if __name__ == '__main__':
    run_tests()
