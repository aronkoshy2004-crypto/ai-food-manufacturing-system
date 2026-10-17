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

class TestPhase2CameraStation(unittest.TestCase):
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

    def login_user(self, email="qc@foodman.vn", password="password123"):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    # --------------------------------------------------------------------------
    # 1. Existing Flows Verification
    # --------------------------------------------------------------------------
    def test_01_existing_login_and_dashboard(self):
        # Admin login has access to Dashboard
        res_admin = self.login_user("admin@foodman.vn", "password123")
        self.assertEqual(res_admin.status_code, 200)

        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'FOOD MAN', dash_res.data.upper())

        # QC login has access to QC Landing
        res_qc = self.login_user("qc@foodman.vn", "password123")
        self.assertEqual(res_qc.status_code, 200)

    def test_02_existing_qc_queue_and_lot_page(self):
        self.login_user("qc@foodman.vn", "password123")
        res_queue = self.client.get('/qc?view=queue')
        self.assertEqual(res_queue.status_code, 200)
        self.assertIn(b'QC Sampling Queue', res_queue.data)

        # Queue API
        res_api = self.client.get('/api/qc/queue')
        self.assertEqual(res_api.status_code, 200)
        data = json.loads(res_api.data)
        self.assertTrue(data.get('success', False))

    def test_03_existing_ai_inspection_upload(self):
        self.login_user("qc@foodman.vn", "password123")
        test_img_path = "static/uploads/raw/20260910_065827_corn_cluster.jpg"
        with open(test_img_path, 'rb') as f:
            img_bytes = f.read()

        data = {
            'target_type': 'lot',
            'target_id': str(self.lot.id),
            'confidence_threshold': '0.25',
            'image': (io.BytesIO(img_bytes), 'specimen.jpg')
        }
        res = self.client.post('/api/qc/ai-inspect', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        res_json = json.loads(res.data)
        self.assertTrue(res_json.get('success', False))
        self.assertIn('data', res_json)

    def test_04_existing_phone_capture_page(self):
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

        # Mobile capture page is public (token-checked)
        res = self.client.get(f'/capture/{token}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(token.encode(), res.data)
        self.assertIn(b'initLiveCamera', res.data)

    # --------------------------------------------------------------------------
    # 2. Inspection Station Access & Authentication
    # --------------------------------------------------------------------------
    def test_05_camera_station_requires_login(self):
        # Fresh client without cookies
        anon_client = self.app.test_client()
        res = anon_client.get('/qc/camera-station')
        # Must redirect to login
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers.get('Location', ''))

    def test_06_camera_station_renders_for_qc_user(self):
        self.login_user("qc@foodman.vn", "password123")
        res = self.client.get('/qc/camera-station')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # Check page elements
        self.assertIn("Inspection Station", html)
        self.assertIn("flipCameraToggle", html)
        self.assertIn("stationCameraSelect", html)
        self.assertIn("stationLotSelect", html)
        self.assertIn("CameraStationApp.init", html)
        self.assertIn("lanHttpWarningBanner", html)

        # Check that token and QR are NOT displayed to user
        self.assertNotIn("Scan QR code", html)
        self.assertNotIn("qr_data_url", html)

    def test_07_camera_station_alias_routes(self):
        self.login_user("qc@foodman.vn", "password123")
        # /qc/station alias
        res1 = self.client.get('/qc/station')
        self.assertEqual(res1.status_code, 200)

        # /qc?view=station redirect
        res2 = self.client.get('/qc?view=station')
        self.assertEqual(res2.status_code, 302)
        loc = res2.headers.get('Location', '')
        self.assertTrue('/qc/camera-station' in loc or '/qc/station' in loc)

    # --------------------------------------------------------------------------
    # 3. Dynamic Lot Linking
    # --------------------------------------------------------------------------
    def test_08_link_lot_endpoint(self):
        self.login_user("qc@foodman.vn", "password123")
        with self.app.app_context():
            db = get_db()
            sess = db.query(LiveSession).filter_by(status="ACTIVE").order_by(LiveSession.id.desc()).first()
            self.assertIsNotNone(sess)
            sess_id = sess.id

        # Link to lot
        res = self.client.post(
            f'/api/qc/live-session/{sess_id}/link-lot',
            data=json.dumps({'lot_id': self.lot.id}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('lot_id'), self.lot.id)

    # --------------------------------------------------------------------------
    # 4. Stream Frame Upload & 5-Frame Lock Sequence with Simulated Frames
    # --------------------------------------------------------------------------
    def test_09_stream_and_lock_sequence_simulated_frames(self):
        self.login_user("qc@foodman.vn", "password123")
        with self.app.app_context():
            db = get_db()
            sess = db.query(LiveSession).filter_by(status="ACTIVE").order_by(LiveSession.id.desc()).first()
            token = sess.token
            sess_id = sess.id

        test_img_path = "static/uploads/raw/20260910_065827_corn_cluster.jpg"
        with open(test_img_path, 'rb') as f:
            img_bytes = f.read()

        # 1 FPS streaming frame
        res_frame = self.client.post(
            f'/api/capture/{token}/frame',
            data={'image': (io.BytesIO(img_bytes), 'stream_frame.jpg')},
            content_type='multipart/form-data'
        )
        self.assertEqual(res_frame.status_code, 200)
        frame_data = json.loads(res_frame.data)
        self.assertTrue(frame_data.get('success'))
        self.assertIn('boxes', frame_data)

        # 5 Lock frames
        final_lock_result = None
        for i in range(1, 6):
            res_lock = self.client.post(
                f'/api/capture/{token}/frame',
                data={
                    'image': (io.BytesIO(img_bytes), f'lock_frame_{i}.jpg'),
                    'lock': 'true'
                },
                content_type='multipart/form-data'
            )
            self.assertEqual(res_lock.status_code, 200)
            lock_json = json.loads(res_lock.data)
            self.assertTrue(lock_json.get('success'))
            if lock_json.get('locked_result'):
                final_lock_result = lock_json['locked_result']

        self.assertIsNotNone(final_lock_result)
        self.assertEqual(final_lock_result.get('material'), 'Corn')

        # 5. Confirm Accept Verdict
        res_verdict = self.client.post(
            f'/api/qc/live-session/{sess_id}/confirm-verdict',
            data=json.dumps({
                'verdict': 'ACCEPT',
                'notes': 'Automated Inspection Station Sign-Off Test'
            }),
            content_type='application/json'
        )
        self.assertEqual(res_verdict.status_code, 200)
        v_data = json.loads(res_verdict.data)
        self.assertTrue(v_data.get('success'))
        self.assertIn('pdf_url', v_data)

        # 6. Verify PDF Report Download
        pdf_url = v_data['pdf_url']
        res_pdf = self.client.get(pdf_url)
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.content_type, 'application/pdf')

        # 7. Reset lock for next sample
        res_reset = self.client.post(f'/api/capture/{token}/reset-lock')
        self.assertEqual(res_reset.status_code, 200)
        r_data = json.loads(res_reset.data)
        self.assertTrue(r_data.get('success'))

if __name__ == '__main__':
    unittest.main()
