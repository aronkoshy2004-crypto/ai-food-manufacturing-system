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
from models.qc import LiveSession
from models.enums import RoleEnum

class TestPhase4CameraSetupHelper(unittest.TestCase):
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
    # 1. Existing Flows Verification (Zero Regression)
    # --------------------------------------------------------------------------
    def test_01_existing_flows_intact(self):
        # 1. QC Login & Queue
        res_qc = self.login_user("qc@foodman.vn", "password123")
        self.assertEqual(res_qc.status_code, 200)

        res_queue = self.client.get('/qc?view=queue')
        self.assertEqual(res_queue.status_code, 200)
        self.assertIn(b'QC Sampling Queue', res_queue.data)

        # 2. QC AI Inspect Upload
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

        # 3. Admin Login & Dashboard
        self.client.get('/logout')
        self.login_user("admin@foodman.vn", "password123")
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'dashLiveInspectionCard', dash_res.data)

        # 4. Mobile Capture Page
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
    # 2. Phase 4: Camera Setup Panel Elements on Inspection Station
    # --------------------------------------------------------------------------
    def test_02_camera_setup_panel_rendered_on_station(self):
        self.login_user("qc@foodman.vn", "password123")
        res = self.client.get('/qc/camera-station')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # Requirement 1: Camera setup panel & test button & resolution
        self.assertIn('btnToggleCameraSetup', html)
        self.assertIn('Camera Setup', html)
        self.assertIn('cameraSetupPanel', html)
        self.assertIn('btnTestCamera', html)
        self.assertIn('Test Camera', html)
        self.assertIn('detectedCamerasList', html)
        self.assertIn('detectedCamerasCount', html)
        self.assertIn('testVideo', html)
        self.assertIn('testResolutionBadge', html)
        self.assertIn('cameraDiagnosticBox', html)

        # Requirement 3: Checklist on page
        self.assertIn('Phone-as-Webcam Quick Setup Checklist', html)
        self.assertIn('Install App', html)
        self.assertIn('Connect', html)
        self.assertIn('Select Camera', html)
        self.assertIn('USB', html)
        self.assertIn('Wi-Fi', html)

        # JS include
        self.assertIn('camera_station.js', html)

    # --------------------------------------------------------------------------
    # 3. Phase 4: Documentation docs/CAMERA_SETUP.md Verification
    # --------------------------------------------------------------------------
    def test_03_camera_setup_documentation_verified(self):
        doc_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'CAMERA_SETUP.md')
        self.assertTrue(os.path.exists(doc_path), "docs/CAMERA_SETUP.md must exist")

        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for core requirements in doc
        self.assertIn('1280', content)
        self.assertIn('720', content)
        self.assertIn('Checklist', content)
        self.assertIn('Iriun', content)
        self.assertIn('DroidCam', content)
        self.assertIn('USB', content)
        self.assertIn('Permission Denied', content)
        self.assertIn('Camera Used by Another App', content)
        self.assertIn('Zoom', content)
        self.assertIn('Teams', content)
        self.assertIn('No Camera Found', content)
        self.assertIn('Black Preview', content)

    # --------------------------------------------------------------------------
    # 4. Phase 4: Plain-Language Error Mapping Content Verification
    # --------------------------------------------------------------------------
    def test_04_js_plain_language_messages(self):
        js_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'camera_station.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js_code = f.read()

        # Requirement 1: Test camera resolution and detected cameras
        self.assertIn('startCameraTest', js_code)
        self.assertIn('stopCameraTest', js_code)
        self.assertIn('detectedCamerasList', js_code)
        self.assertIn('testResolutionBadge', js_code)

        # Requirement 2: Plain-language messages for all 4 scenarios
        self.assertIn('permission_denied', js_code)
        self.assertIn('Camera Permission Denied', js_code)

        self.assertIn('in_use', js_code)
        self.assertIn('Zoom', js_code)
        self.assertIn('Teams', js_code)

        self.assertIn('not_found', js_code)
        self.assertIn('No Camera Found', js_code)

        self.assertIn('black_preview', js_code)
        self.assertIn('Black Preview Detected', js_code)
        self.assertIn('Windows program is not running', js_code)

if __name__ == '__main__':
    unittest.main()
