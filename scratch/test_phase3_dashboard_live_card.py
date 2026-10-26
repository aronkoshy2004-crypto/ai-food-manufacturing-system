import unittest
import io
import json
import os
import secrets
import datetime
from PIL import Image

from app import create_app
from models import get_db
from models.user import User
from models.schema_draft import RawMaterialLot
from models.qc import LiveSession, LiveFrame, AIInspection, InspectionImage
from models.enums import RoleEnum, StatusEnum

class TestPhase3DashboardLiveCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db = get_db()
            self.qc_user = db.query(User).filter_by(role=RoleEnum.QC.value).first()
            self.admin_user = db.query(User).filter_by(role=RoleEnum.ADMIN.value).first()
            self.lot = db.query(RawMaterialLot).first()

    def login_user(self, email="admin@foodman.vn", password="password123"):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    # --------------------------------------------------------------------------
    # 1. Existing Flows Verification (Zero Regression)
    # --------------------------------------------------------------------------
    def test_01_existing_flows_intact(self):
        # 1. Admin login & Dashboard access
        res_admin = self.login_user("admin@foodman.vn", "password123")
        self.assertEqual(res_admin.status_code, 200)

        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'BOM Specifications', dash_res.data)
        self.assertIn(b'Live Plant Batches', dash_res.data)

        # 2. QC login & Queue
        res_qc = self.login_user("qc@foodman.vn", "password123")
        self.assertEqual(res_qc.status_code, 200)
        res_queue = self.client.get('/qc?view=queue')
        self.assertEqual(res_queue.status_code, 200)

        # 3. QC AI Inspect upload
        test_img_path = "static/uploads/raw/20260910_065827_corn_cluster.jpg"
        with open(test_img_path, 'rb') as f:
            img_bytes = f.read()
        res_inspect = self.client.post(
            '/api/qc/ai-inspect',
            data={
                'target_type': 'lot',
                'target_id': str(self.lot.id),
                'confidence_threshold': '0.25',
                'image': (io.BytesIO(img_bytes), 'specimen.jpg')
            },
            content_type='multipart/form-data'
        )
        self.assertEqual(res_inspect.status_code, 200)
        self.assertTrue(json.loads(res_inspect.data).get('success'))

        # 4. Station page
        res_station = self.client.get('/qc/camera-station')
        self.assertEqual(res_station.status_code, 200)
        self.assertIn(b'Inspection Station', res_station.data)

        # 5. Mobile capture
        with self.app.app_context():
            db = get_db()
            token = secrets.token_urlsafe(32)
            sess = LiveSession(
                token=token,
                status="ACTIVE",
                created_at=datetime.datetime.utcnow(),
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=2)
            )
            db.add(sess)
            db.commit()

        res_cap = self.client.get(f'/capture/{token}')
        self.assertEqual(res_cap.status_code, 200)

    # --------------------------------------------------------------------------
    # 2. Phase 3: Dashboard Live Inspection Card Elements & Design Integrity
    # --------------------------------------------------------------------------
    def test_02_dashboard_live_inspection_card_rendered(self):
        self.login_user("admin@foodman.vn", "password123")
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # Requirement 1: Dedicated live inspection card & button
        self.assertIn('dashLiveInspectionCard', html)
        self.assertIn('btnToggleDashCamera', html)
        self.assertIn('Start Live Inspection', html)
        self.assertIn('dashLivePreviewWrap', html)
        self.assertIn('dashLiveVideo', html)
        self.assertIn('dashOverlayCanvas', html)
        self.assertIn('dashHudGuidance', html)

        # Requirement 2: Latest final result
        self.assertIn('dashLatestResultBox', html)
        self.assertIn('dashLatestMaterial', html)
        self.assertIn('dashLatestGoodPct', html)
        self.assertIn('dashLatestDefectPct', html)
        self.assertIn('dashLatestSuggestion', html)
        self.assertIn('dashLatestTime', html)

        # Requirement 3: Counters for today
        self.assertIn('dashCountChecked', html)
        self.assertIn('dashCountPass', html)
        self.assertIn('dashCountReview', html)
        self.assertIn('dashCountReject', html)

        # Requirement 5: Insecure LAN banner with Open localhost version button
        self.assertIn('dashLanWarningBanner', html)
        self.assertIn('btnDashOpenLocalhost', html)
        self.assertIn('Open localhost version', html)

        # Script include
        self.assertIn('dashboard_live_card.js', html)

    # --------------------------------------------------------------------------
    # 3. Phase 3: Live Inspection Summary API Endpoint
    # --------------------------------------------------------------------------
    def test_03_summary_api_requires_login(self):
        anon_client = self.app.test_client()
        res = anon_client.get('/api/dashboard/live-inspection-summary')
        self.assertIn(res.status_code, [302, 401])

    def test_04_summary_api_returns_valid_structure(self):
        self.login_user("admin@foodman.vn", "password123")
        res = self.client.get('/api/dashboard/live-inspection-summary')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)

        self.assertTrue(data.get('success'))
        self.assertIn('counters', data)
        counters = data['counters']
        self.assertIn('samples_checked', counters)
        self.assertIn('pass', counters)
        self.assertIn('review', counters)
        self.assertIn('reject', counters)

        self.assertIn('latest_result', data)
        if data['latest_result']:
            lr = data['latest_result']
            self.assertIn('material', lr)
            self.assertIn('good_pct', lr)
            self.assertIn('defect_pct', lr)
            self.assertIn('suggestion', lr)
            self.assertIn('time', lr)

    # --------------------------------------------------------------------------
    # 4. Phase 3: Simulated Live Session Lock Updates Dashboard Summary API
    # --------------------------------------------------------------------------
    def test_05_summary_api_updates_after_simulated_live_inspection(self):
        self.login_user("admin@foodman.vn", "password123")

        # Create live session
        res_create = self.client.post('/api/qc/live-session/create', json={})
        self.assertIn(res_create.status_code, [200, 201])
        c_json = json.loads(res_create.data)
        token = c_json['session']['token']
        sess_id = c_json['session']['id']

        # Link lot
        self.client.post(
            f'/api/qc/live-session/{sess_id}/link-lot',
            data=json.dumps({'lot_id': self.lot.id}),
            content_type='application/json'
        )

        test_img_path = "static/uploads/raw/20260910_065827_corn_cluster.jpg"
        with open(test_img_path, 'rb') as f:
            img_bytes = f.read()

        # Execute 5-frame lock sequence
        for i in range(1, 6):
            res_frame = self.client.post(
                f'/api/capture/{token}/frame',
                data={
                    'image': (io.BytesIO(img_bytes), f'dash_lock_{i}.jpg'),
                    'lock': 'true'
                },
                content_type='multipart/form-data'
            )
            self.assertEqual(res_frame.status_code, 200)

        # Now query the summary API
        res_summary = self.client.get('/api/dashboard/live-inspection-summary')
        self.assertEqual(res_summary.status_code, 200)
        sum_data = json.loads(res_summary.data)

        self.assertTrue(sum_data['success'])
        self.assertGreaterEqual(sum_data['counters']['samples_checked'], 1)
        latest = sum_data['latest_result']
        self.assertIsNotNone(latest)
        self.assertEqual(latest['material'], 'Corn')
        self.assertIn(latest['suggestion'], ['Pass', 'Review', 'Reject'])
        self.assertTrue(latest['time'] != '')

if __name__ == '__main__':
    unittest.main()
