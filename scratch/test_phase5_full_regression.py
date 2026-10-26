"""
Phase 5 Comprehensive Regression & Security Verification Test Suite
Verifies:
1. Full module regression: Auth, Procurement, QC, Production, Warehouse, Traceability, Dashboard, Alerts.
2. Security enforcement: New pages & all app routes require login; only token-checked /capture/<token> is public.
3. Phone capture flow: Session creation, public token-checked capture page, frame streaming, 5-frame lock, reset-lock, inspector accept, PDF generation.
4. Laptop Inspection Station: Route protection, UI controls (camera dropdown, setup helper, flip toggle), internal session creation, simulated frame lock & accept.
5. Dashboard live card: Live card presence, summary API metrics, dynamic counter updates after simulated inspections.
6. QC Live Inspection UI: QR code and phone link hidden behind 'Pair a phone (advanced)' toggle button.
"""
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
from models.qc import LiveSession, LiveFrame, AIInspection
from models.enums import RoleEnum, StatusEnum

def generate_test_jpeg(color=(210, 160, 100), size=(640, 480)):
    """Generate a clean in-memory JPEG image for simulated frame streaming."""
    img = Image.new('RGB', size, color=color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    buf.seek(0)
    return buf.getvalue()

class TestPhase5FullRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db = get_db()
            self.admin_user = db.query(User).filter_by(role=RoleEnum.ADMIN.value).first()
            self.qc_user = db.query(User).filter_by(role=RoleEnum.QC.value).first()
            self.lot = db.query(RawMaterialLot).first()

    def login_user(self, email="admin@foodman.vn", password="password123"):
        self.client.get('/logout')
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    def logout_user(self):
        return self.client.get('/logout', follow_redirects=True)

    # =========================================================================
    # PART 1: SECURITY VERIFICATION (All pages login-protected, public token routes)
    # =========================================================================
    def test_01_security_unauthenticated_page_access_blocked(self):
        """Verify that all application pages and new camera station pages reject unauthenticated users."""
        self.logout_user()

        protected_pages = [
            '/dashboard',
            '/procurement',
            '/qc',
            '/qc?view=queue',
            '/qc?view=live-inspection',
            '/qc/camera-station',   # New Phase 2 page
            '/qc/station',          # New Phase 2 alias
            '/production',
            '/warehouse',
            '/traceability',
            '/alerts'
        ]

        for page in protected_pages:
            res = self.client.get(page)
            self.assertEqual(
                res.status_code, 302,
                f"Page {page} must redirect unauthenticated visitors to login (got {res.status_code})"
            )
            self.assertIn('/login', res.headers.get('Location', ''))

    def test_02_security_unauthenticated_api_access_blocked(self):
        """Verify that private APIs reject unauthenticated requests with 401 Unauthorized or 302 Redirect."""
        self.logout_user()

        protected_apis = [
            ('/api/dashboard/live-inspection-summary', 'GET'),
            ('/api/qc/live-session/create', 'POST'),
            ('/api/qc/ai-inspect', 'POST'),
            ('/api/alerts', 'GET'),
        ]

        for endpoint, method in protected_apis:
            if method == 'POST':
                res = self.client.post(endpoint, data={})
            else:
                res = self.client.get(endpoint)
            self.assertIn(
                res.status_code, [302, 401],
                f"API {endpoint} ({method}) must block unauthenticated calls with 401 or 302 (got {res.status_code})"
            )

    def test_03_security_only_token_checked_capture_routes_public(self):
        """Verify that only valid /capture/<token> and /api/capture/<token>/... are public."""
        self.logout_user()

        # Create a valid session first as QC user
        self.login_user("qc@foodman.vn", "password123")
        res_create = self.client.post('/api/qc/live-session/create', json={
            'lot_id': self.lot.id if self.lot else None
        })
        self.assertIn(res_create.status_code, [200, 201])
        token = res_create.get_json()['session']['token']
        self.logout_user()

        # Test valid token without login -> 200 OK
        res_capture = self.client.get(f'/capture/{token}')
        self.assertEqual(res_capture.status_code, 200, "Valid token capture page must be accessible without login")
        self.assertIn(b'QC Live Camera Capture', res_capture.data)

        # Test invalid token on capture page -> renders user-friendly invalid token screen
        res_invalid = self.client.get('/capture/invalid_token_123456789')
        self.assertEqual(res_invalid.status_code, 200)
        self.assertIn(b'Invalid Session Token', res_invalid.data)

        # Test invalid token on frame API -> 404 Not Found
        res_invalid_frame = self.client.post('/api/capture/invalid_token_123456789/frame', data={})
        self.assertEqual(res_invalid_frame.status_code, 404, "Invalid token frame API must return 404")

    # =========================================================================
    # PART 2: FULL MODULE REGRESSION (Procurement, QC, Production, Warehouse, Traceability, Dashboard, Alerts)
    # =========================================================================
    def test_04_module_auth_flows(self):
        """Verify standard email/password authentication and session teardown."""
        # 1. Invalid login fails
        res_fail = self.client.post('/login', data={'email': 'wrong@foodman.vn', 'password': 'bad'}, follow_redirects=True)
        self.assertEqual(res_fail.status_code, 200)
        self.assertIn(b'Invalid email or password', res_fail.data)

        # 2. Valid QC login succeeds
        res_ok = self.login_user("qc@foodman.vn", "password123")
        self.assertEqual(res_ok.status_code, 200)

        # 3. Logout clears session
        res_logout = self.logout_user()
        self.assertEqual(res_logout.status_code, 200)
        res_check = self.client.get('/qc')
        self.assertEqual(res_check.status_code, 302)

    def test_05_module_procurement(self):
        """Verify Procurement views load cleanly for authenticated Admin user."""
        self.login_user("admin@foodman.vn", "password123")
        res = self.client.get('/procurement')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Procurement', res.data)

    def test_06_module_qc_queue_and_file_upload_inspect(self):
        """Verify QC queue loads and file-based AI upload inspection functions normally."""
        self.login_user("qc@foodman.vn", "password123")
        res_queue = self.client.get('/qc?view=queue')
        self.assertEqual(res_queue.status_code, 200)
        self.assertIn(b'QC Sampling Queue', res_queue.data)

        # File-based inspection upload
        test_img_path = "static/uploads/raw/20260910_065827_corn_cluster.jpg"
        if not os.path.exists(test_img_path):
            test_img_bytes = generate_test_jpeg()
        else:
            with open(test_img_path, 'rb') as f:
                test_img_bytes = f.read()

        res_inspect = self.client.post(
            '/api/qc/ai-inspect',
            data={
                'target_type': 'lot',
                'target_id': str(self.lot.id) if self.lot else '1',
                'confidence_threshold': '0.25',
                'image': (io.BytesIO(test_img_bytes), 'specimen.jpg')
            },
            content_type='multipart/form-data'
        )
        self.assertEqual(res_inspect.status_code, 200)
        data = res_inspect.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('ai_result', data)

    def test_07_module_production(self):
        """Verify Production view loads cleanly."""
        self.login_user("admin@foodman.vn", "password123")
        res = self.client.get('/production')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Production', res.data)

    def test_08_module_warehouse(self):
        """Verify Warehouse view loads cleanly."""
        self.login_user("admin@foodman.vn", "password123")
        res = self.client.get('/warehouse')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Warehouse', res.data)

    def test_09_module_traceability(self):
        """Verify Traceability view loads cleanly."""
        self.login_user("admin@foodman.vn", "password123")
        res = self.client.get('/traceability')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Traceability', res.data)

    def test_10_module_alerts(self):
        """Verify Alerts view loads cleanly."""
        self.login_user("admin@foodman.vn", "password123")
        res = self.client.get('/alerts')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Alerts', res.data)

    def test_11_module_dashboard(self):
        """Verify Dashboard view loads cleanly for Admin."""
        self.login_user("admin@foodman.vn", "password123")
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Executive Overview', res.data)

    # =========================================================================
    # PART 3: PHONE CAPTURE FLOW (Stream, Multi-frame Lock, Reset, Accept, PDF)
    # =========================================================================
    def test_12_phone_capture_flow_complete(self):
        """Verify the complete phone capture cycle: stream -> 5-frame lock -> reset-lock -> lock -> accept -> report."""
        # 1. QC creates a live session
        self.login_user("qc@foodman.vn", "password123")
        res_create = self.client.post('/api/qc/live-session/create', json={
            'lot_id': self.lot.id if self.lot else None
        })
        self.assertIn(res_create.status_code, [200, 201])
        token = res_create.get_json()['session']['token']
        session_id = res_create.get_json()['session']['id']

        # 2. Simulate phone stream sending frames (unauthenticated public token route)
        self.logout_user()
        test_img_path = "static/uploads/raw/20260910_065827_corn_cluster.jpg"
        if os.path.exists(test_img_path):
            with open(test_img_path, 'rb') as f:
                jpeg_bytes = f.read()
        else:
            jpeg_bytes = generate_test_jpeg()

        # 1 FPS streaming frames
        res_frame = self.client.post(
            f'/api/capture/{token}/frame',
            data={'image': (io.BytesIO(jpeg_bytes), 'frame_stream.jpg')},
            content_type='multipart/form-data'
        )
        self.assertEqual(res_frame.status_code, 200)
        data_frame = res_frame.get_json()
        self.assertTrue(data_frame.get('success'))

        # 5 Lock frames triggers steady lock
        for i in range(1, 6):
            res_lock = self.client.post(
                f'/api/capture/{token}/frame',
                data={
                    'image': (io.BytesIO(jpeg_bytes), f'frame_{i}.jpg'),
                    'lock': 'true'
                },
                content_type='multipart/form-data'
            )
            self.assertEqual(res_lock.status_code, 200)
            data_lock = res_lock.get_json()
            self.assertTrue(data_lock.get('success'))

        self.assertIsNotNone(data_lock.get('locked_result'))

        # Reset lock
        res_reset = self.client.post(f'/api/capture/{token}/reset-lock')
        self.assertEqual(res_reset.status_code, 200)
        self.assertTrue(res_reset.get_json().get('success'))

        # Re-lock with 5 frames
        for i in range(1, 6):
            res_relock = self.client.post(
                f'/api/capture/{token}/frame',
                data={
                    'image': (io.BytesIO(jpeg_bytes), f'relock_{i}.jpg'),
                    'lock': 'true'
                },
                content_type='multipart/form-data'
            )
            self.assertEqual(res_relock.status_code, 200)

        # 3. QC Inspector logs in and submits ACCEPT verdict
        self.login_user("qc@foodman.vn", "password123")
        res_accept = self.client.post(
            f'/api/qc/live-session/{session_id}/confirm-verdict',
            data=json.dumps({
                'verdict': 'ACCEPT',
                'notes': 'Regression test approved high quality specimen.'
            }),
            content_type='application/json'
        )
        self.assertEqual(res_accept.status_code, 200)
        accept_data = res_accept.get_json()
        self.assertTrue(accept_data.get('success'))
        pdf_url = accept_data.get('pdf_url')
        self.assertIsNotNone(pdf_url)

        # 4. Generate PDF Report
        res_report = self.client.get(pdf_url)
        self.assertEqual(res_report.status_code, 200)
        self.assertEqual(res_report.headers.get('Content-Type'), 'application/pdf')
        self.assertGreater(len(res_report.data), 1000)

    # =========================================================================
    # PART 4: LAPTOP INSPECTION STATION (Routes, UI Controls, Setup Helper, Internal Session)
    # =========================================================================
    def test_13_inspection_station_ui_and_internal_session(self):
        """Verify the Inspection Station page elements, setup helper panel, and internal session flow."""
        self.login_user("qc@foodman.vn", "password123")

        # 1. Page loads at primary route and alias
        for route in ['/qc/camera-station', '/qc/station']:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} must load with 200 OK")
            html = res.data.decode('utf-8')
            # Verify UI controls
            self.assertIn('Inspection Station', html)
            self.assertIn('stationLotSelect', html)
            self.assertIn('stationCameraSelect', html)
            self.assertIn('flipCameraToggle', html)
            self.assertIn('btnToggleCameraSetup', html)
            self.assertIn('cameraSetupPanel', html)
            self.assertIn('btnTestCamera', html)
            self.assertIn('cameraDiagnosticBox', html)
            self.assertIn('testResolutionBadge', html)

        # 2. Extract internal session created behind the scenes
        with self.app.app_context():
            db = get_db()
            active_sess = db.query(LiveSession).filter_by(status="ACTIVE").order_by(LiveSession.id.desc()).first()
            self.assertIsNotNone(active_sess)
            station_token = active_sess.token
            station_id = active_sess.id

        # 3. Simulate station sending frames and locking
        test_img_path = "static/uploads/raw/20260910_065827_corn_cluster.jpg"
        if os.path.exists(test_img_path):
            with open(test_img_path, 'rb') as f:
                jpeg_bytes = f.read()
        else:
            jpeg_bytes = generate_test_jpeg()

        for i in range(1, 6):
            res_frame = self.client.post(
                f'/api/capture/{station_token}/frame',
                data={
                    'image': (io.BytesIO(jpeg_bytes), f'station_frame_{i}.jpg'),
                    'lock': 'true'
                },
                content_type='multipart/form-data'
            )
            self.assertEqual(res_frame.status_code, 200)

        # 4. Accept verdict on station session
        res_station_accept = self.client.post(
            f'/api/qc/live-session/{station_id}/confirm-verdict',
            data=json.dumps({
                'verdict': 'ACCEPT',
                'notes': 'Station inspection acceptance verified.'
            }),
            content_type='application/json'
        )
        self.assertEqual(res_station_accept.status_code, 200)
        self.assertTrue(res_station_accept.get_json().get('success'))

    # =========================================================================
    # PART 5: DASHBOARD LIVE INSPECTION CARD WITH SIMULATED FRAMES
    # =========================================================================
    def test_14_dashboard_live_card_and_summary_metrics(self):
        """Verify the Live Inspection card on /dashboard and real-time counter metrics API."""
        self.login_user("admin@foodman.vn", "password123")

        # 1. Verify card exists on dashboard
        res_dash = self.client.get('/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        html = res_dash.data.decode('utf-8')
        self.assertIn('dashLiveInspectionCard', html)
        self.assertIn('Live Camera QC Inspection', html)
        self.assertIn('btnToggleDashCamera', html)
        self.assertIn('dashCountChecked', html)
        self.assertIn('dashCountPass', html)
        self.assertIn('dashCountReview', html)
        self.assertIn('dashCountReject', html)

        # 2. Get baseline summary metrics
        res_metric_0 = self.client.get('/api/dashboard/live-inspection-summary')
        self.assertEqual(res_metric_0.status_code, 200)
        data_0 = res_metric_0.get_json()
        samples_before = data_0.get('counters', {}).get('samples_checked', 0)
        pass_before = data_0.get('counters', {}).get('pass', 0)

        # 3. Run simulated inspection and lock it
        res_create = self.client.post('/api/qc/live-session/create', json={
            'lot_id': self.lot.id if self.lot else None
        })
        dash_token = res_create.get_json()['session']['token']
        dash_id = res_create.get_json()['session']['id']

        test_img_path = "static/uploads/raw/20260910_065827_corn_cluster.jpg"
        if os.path.exists(test_img_path):
            with open(test_img_path, 'rb') as f:
                jpeg_bytes = f.read()
        else:
            jpeg_bytes = generate_test_jpeg()

        for i in range(1, 6):
            self.client.post(
                f'/api/capture/{dash_token}/frame',
                data={
                    'image': (io.BytesIO(jpeg_bytes), f'dash_frame_{i}.jpg'),
                    'lock': 'true'
                },
                content_type='multipart/form-data'
            )

        # 4. Check summary metrics updated
        res_metric_1 = self.client.get('/api/dashboard/live-inspection-summary')
        self.assertEqual(res_metric_1.status_code, 200)
        data_1 = res_metric_1.get_json()
        counters_before = data_0.get('counters', {})
        counters_after = data_1.get('counters', {})

        samples_before = counters_before.get('samples_checked', 0)
        samples_after = counters_after.get('samples_checked', 0)
        self.assertGreaterEqual(samples_after, samples_before + 1)

        total_verdicts_before = counters_before.get('pass', 0) + counters_before.get('review', 0) + counters_before.get('reject', 0)
        total_verdicts_after = counters_after.get('pass', 0) + counters_after.get('review', 0) + counters_after.get('reject', 0)
        self.assertGreaterEqual(total_verdicts_after, total_verdicts_before + 1)
        self.assertIsNotNone(data_1.get('latest_result'))

    # =========================================================================
    # PART 6: REQUIREMENT 3 — QR CODE HIDDEN BEHIND TOGGLE BUTTON
    # =========================================================================
    def test_15_qr_code_hidden_behind_pair_phone_advanced_button(self):
        """Verify Requirement 3: QR code & phone link hidden behind 'Pair a phone (advanced)' button."""
        self.login_user("qc@foodman.vn", "password123")
        res = self.client.get('/qc?view=live-inspection')
        self.assertEqual(res.status_code, 200)

        # 1. Button must exist with exact requested text
        self.assertIn(b'id="btnTogglePairPhone"', res.data)
        self.assertIn(b'Pair a phone (advanced)', res.data)

        # 2. Advanced container must be hidden by default
        self.assertIn(b'id="pairPhoneAdvancedContainer" style="display:none;"', res.data)

        # 3. Recommendation banner pointing to laptop station must be present
        self.assertIn(b'Primary: Laptop Inspection Station', res.data)
        self.assertIn(b'Open Inspection Station', res.data)

        # 4. QR and link elements must still exist inside the container (no routes or pages deleted)
        self.assertIn(b'id="sessionQrImg"', res.data)
        self.assertIn(b'id="sessionCaptureUrl"', res.data)
        self.assertIn(b'togglePairPhoneAdvanced', res.data)

if __name__ == '__main__':
    unittest.main()
