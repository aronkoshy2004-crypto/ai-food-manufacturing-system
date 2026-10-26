"""
Test Suite for Simplified Workflow & Food Technologist Dashboard (PRD Phase 4)
Tests:
1. Food Technologist Role & Auth:
   - Login with tech@foodman.vn / password123
   - Access to /food-technologist dashboard
   - Landing page redirect for FOOD_TECHNOLOGIST
2. ONE Inspection Station:
   - /qc/camera-station availability
   - Legacy view redirects (/qc?view=ai-inspection, /qc?view=live-inspection)
3. QC Lab Measures Recording API:
   - GET /api/qc/lot/<id>/qc-measures
   - POST /api/qc/lot/<id>/qc-measures (records moisture, aflatoxin B1, FFA, purity)
4. Merged Release Outcome Plain Labels:
   - GOOD (mapped from RELEASE)
   - NEEDS REVIEW (mapped from HOLD)
   - BAD (mapped from REJECT)
5. Food Technologist APIs & Exports:
   - GET /api/food-technologist/lots (filtering, search, stage tracker 1-7)
   - GET /api/food-technologist/lot/<id> (full 7-stage lifecycle)
   - GET /api/food-technologist/lot/<id>/pdf (ReportLab release dossier PDF)
   - GET /api/food-technologist/export/csv (CSV quality data export)
6. Handoff Notifications:
   - GRN intake alert to QC
   - Final verdict alert to Production / Warehouse
"""
import unittest
import json
import datetime
from app import create_app
from models import get_db
from models.user import User
from models.enums import RoleEnum, StatusEnum
from models.procurement import RawMaterialLot, Supplier
from models.qc import QCDecision, COADocument, QCSample, QCTest, AIInspection
from models.warehouse import NotificationAlert


class TestFoodTechnologistWorkflow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        self.client = self.app.test_client()
        self.db = get_db()

    def login(self, email, password):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # --------------------------------------------------------------------------
    # 1. Food Technologist Role & Auth
    # --------------------------------------------------------------------------
    def test_01_food_technologist_login_and_access(self):
        """Food Technologist user can log in and view dedicated dashboard"""
        res = self.login('tech@foodman.vn', 'password123')
        self.assertEqual(res.status_code, 200)

        # Access dashboard
        dash_res = self.client.get('/food-technologist')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'Food Technologist Audit Command', dash_res.data)
        self.assertIn(b'Dr. Aris Thorne, PhD', dash_res.data)
        self.logout()

    def test_02_landing_url_for_food_technologist(self):
        """Food Technologist lands directly on /food-technologist upon login"""
        with self.client:
            self.login('tech@foodman.vn', 'password123')
            # Root redirects to designated landing
            res = self.client.get('/', follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/food-technologist', res.headers.get('Location', ''))
            self.logout()

    # --------------------------------------------------------------------------
    # 2. ONE Inspection Station & Soft Redirection
    # --------------------------------------------------------------------------
    def test_03_camera_station_accessible(self):
        """Camera station is accessible for QC and Technologist"""
        self.login('tech@foodman.vn', 'password123')
        res = self.client.get('/qc/camera-station')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Inspection Station', res.data)
        self.logout()

    def test_04_legacy_views_redirect_to_camera_station(self):
        """Legacy ai-inspection and live-inspection views redirect to camera-station"""
        self.login('admin@foodman.vn', 'password123')
        res_ai = self.client.get('/qc?view=ai-inspection', follow_redirects=False)
        self.assertEqual(res_ai.status_code, 302)
        loc_ai = res_ai.headers.get('Location', '')
        self.assertTrue(any(sub in loc_ai for sub in ['/qc/camera-station', '/qc/station']))

        res_live = self.client.get('/qc?view=live-inspection', follow_redirects=False)
        self.assertEqual(res_live.status_code, 302)
        loc_live = res_live.headers.get('Location', '')
        self.assertTrue(any(sub in loc_live for sub in ['/qc/camera-station', '/qc/station']))
        self.logout()

    # --------------------------------------------------------------------------
    # 3. QC Lab Measures Recording API
    # --------------------------------------------------------------------------
    def test_05_qc_measures_get_and_post(self):
        """GET and POST /api/qc/lot/<id>/qc-measures saves tests and updates release decision"""
        self.login('qc@foodman.vn', 'password123')
        lot = self.db.query(RawMaterialLot).first()
        self.assertIsNotNone(lot)

        # GET measures
        get_res = self.client.get(f'/api/qc/lot/{lot.id}/qc-measures')
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json
        self.assertTrue(data.get('success'))

        # POST measures
        post_payload = {
            "coa_doc_number": f"COA-TEST-{lot.id}",
            "lab_accreditation": "VILAS 102 / ISO 17025",
            "moisture": "7.2%",
            "aflatoxin_b1": "1.3 ppb",
            "ffa": "0.7%",
            "purity": "99.1%",
            "notes": "Automated test recording"
        }
        post_res = self.client.post(
            f'/api/qc/lot/{lot.id}/qc-measures',
            data=json.dumps(post_payload),
            content_type='application/json'
        )
        self.assertEqual(post_res.status_code, 200)
        post_data = post_res.json
        self.assertTrue(post_data.get('success'))
        self.assertIn('release_decision', post_data)
        self.assertIn(post_data['release_decision']['plain_label'], ['GOOD', 'NEEDS REVIEW', 'BAD'])
        self.logout()

    # --------------------------------------------------------------------------
    # 4. Food Technologist APIs: Lots, Detail Journey, PDF, and CSV
    # --------------------------------------------------------------------------
    def test_06_api_food_technologist_lots(self):
        """GET /api/food-technologist/lots returns all lots with stage and outcome info"""
        self.login('tech@foodman.vn', 'password123')
        res = self.client.get('/api/food-technologist/lots')
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertTrue(data.get('success'))
        self.assertGreater(data.get('count', 0), 0)

        # Verify structure of first lot
        first_lot = data['lots'][0]
        self.assertIn('lot_number', first_lot)
        self.assertIn('ai_result', first_lot)
        self.assertIn('qc_measures', first_lot)
        self.assertIn('outcome', first_lot)
        self.assertIn('stage', first_lot)
        self.assertIn(first_lot['outcome']['plain_label'], ['GOOD', 'NEEDS REVIEW', 'BAD'])
        self.assertIn(first_lot['stage']['number'], [1, 2, 3, 4, 5, 6, 7])
        self.logout()

    def test_07_api_food_technologist_lot_detail_7_stages(self):
        """GET /api/food-technologist/lot/<id> returns complete 7-stage lifecycle"""
        self.login('tech@foodman.vn', 'password123')
        lot = self.db.query(RawMaterialLot).first()
        self.assertIsNotNone(lot)

        res = self.client.get(f'/api/food-technologist/lot/{lot.id}')
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertTrue(data.get('success'))
        journey = data['journey']

        # Check all 7 stages present
        self.assertIn('stage_1_supplier_po', journey)
        self.assertIn('stage_2_arrival_grn', journey)
        self.assertIn('stage_3_inspection_station', journey)
        self.assertIn('stage_4_qc_measures', journey)
        self.assertIn('stage_5_qc_signoff', journey)
        self.assertIn('stage_6_production', journey)
        self.assertIn('stage_7_warehouse_dispatch', journey)
        self.logout()

    def test_08_api_food_technologist_lot_pdf(self):
        """GET /api/food-technologist/lot/<id>/pdf generates valid PDF dossier"""
        self.login('tech@foodman.vn', 'password123')
        lot = self.db.query(RawMaterialLot).first()
        self.assertIsNotNone(lot)

        res = self.client.get(f'/api/food-technologist/lot/{lot.id}/pdf')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'application/pdf')
        self.assertTrue(res.data.startswith(b'%PDF'))
        self.logout()

    def test_09_api_food_technologist_export_csv(self):
        """GET /api/food-technologist/export/csv exports quality audit CSV"""
        self.login('tech@foodman.vn', 'password123')
        res = self.client.get('/api/food-technologist/export/csv')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.mimetype)
        self.assertIn(b'Lot Number,Material,Category,Supplier', res.data)
        self.logout()

    # --------------------------------------------------------------------------
    # 5. Handoff Notifications
    # --------------------------------------------------------------------------
    def test_10_qc_handoff_notification_alerts(self):
        """QC decision confirmation creates downstream handoff notification alerts"""
        from routes.qc import create_qc_handoff_alert
        lot = self.db.query(RawMaterialLot).first()
        self.assertIsNotNone(lot)

        # Test Approved -> Production handoff
        create_qc_handoff_alert(self.db, lot, 'APPROVED', 'QC Specialist Test')
        self.db.commit()

        alert = self.db.query(NotificationAlert).filter(
            NotificationAlert.reference_id == lot.lot_number,
            NotificationAlert.module == "Production"
        ).order_by(NotificationAlert.id.desc()).first()

        self.assertIsNotNone(alert)
        self.assertIn("Lot Released", alert.title)
        self.assertIn("ready for batch production", alert.message)


if __name__ == '__main__':
    unittest.main()
