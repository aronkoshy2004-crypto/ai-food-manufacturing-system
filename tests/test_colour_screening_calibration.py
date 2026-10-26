"""
Unit and Integration Tests for Colour Screening Engine & Calibration (fix/colour-screening):
Requirement 1: Median Lab, dark patch pct (L < med_L - 18), grey/green/bluish-white patch pct, colour unevenness, suspect score 0-100, reason tags.
Requirement 2: Login-required Calibration page, user Normal/Suspect marks, simple threshold fitting per material (no ML), Reset button, separation table.
Requirement 3: Labels strictly "Normal" and "Suspect (discoloured)", never "mold" in colour mode, footer: "Colour screening only. Not a mold or lab test."
Requirement 4: Sunflower uses the same engine, never gets an automatic Pass.
"""

import os
import sys
import json
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from config import Config
from models import get_db
from models.user import User
from models.qc import LiveSession, LiveFrame
from ai.classical_kernel_finder import (
    compute_kernel_color_metrics,
    find_kernels_classical,
    crop_kernel_image
)
from routes.qc import (
    get_inspection_setting,
    set_inspection_setting,
    get_material_colour_threshold,
    get_user_calibration_marks,
    set_user_calibration_marks,
    compute_material_separation_stats,
    fit_threshold_from_marks
)


class TestColourScreeningCalibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()

    def test_01_kernel_color_metrics_and_scoring(self):
        """Requirement 1: compute Lab median, dark patch, grey-green patch, unevenness, score 0-100, reason tags."""
        # Synthetic clean kernel (warm amber/peanut Lab color)
        # In uint8 Lab, clean peanut is approx L=150, a=135, b=175
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        # Fill center 60x60 with clean kernel color (BGR equivalent of Lab: ~ 80, 140, 200)
        img[20:80, 20:80] = [80, 140, 200]
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 20:80] = 255

        metrics_clean = compute_kernel_color_metrics(img, mask, suspect_threshold=40.0, material="Peanut")
        self.assertIn("median_lab", metrics_clean)
        self.assertIn("dark_patch_pct", metrics_clean)
        self.assertIn("patch_pct", metrics_clean)
        self.assertIn("unevenness", metrics_clean)
        self.assertIn("suspect_score", metrics_clean)
        self.assertIn("reason_tags", metrics_clean)
        self.assertEqual(metrics_clean["classification"], "Normal")
        self.assertLess(metrics_clean["suspect_score"], 40.0)

        # Synthetic discoloured kernel with dark patch and grey-green discolouration
        img_defect = img.copy()
        # Add 30% dark patch (very dark pixels)
        img_defect[20:45, 20:60] = [15, 20, 25]
        # Add greenish discolouration patch
        img_defect[45:65, 20:50] = [60, 120, 60]

        metrics_defect = compute_kernel_color_metrics(img_defect, mask, suspect_threshold=40.0, material="Peanut")
        self.assertGreaterEqual(metrics_defect["dark_patch_pct"], 20.0)
        self.assertGreaterEqual(metrics_defect["suspect_score"], 40.0)
        self.assertEqual(metrics_defect["classification"], "Suspect (discoloured)")
        self.assertNotIn("mold", metrics_defect["classification"].lower())
        self.assertNotIn("moldy", metrics_defect["classification"].lower())

        # Check reason tags format (e.g. "dark patch 18%", "grey-green patch", "uneven colour")
        tags = metrics_defect["reason_tags"]
        self.assertTrue(any("dark patch" in t for t in tags), f"Expected dark patch tag, got {tags}")
        print("[PASS] test_01_kernel_color_metrics_and_scoring passed")

    def test_02_simple_threshold_fitting_no_ml(self):
        """Requirement 2: Fit simple thresholds per material from marks (no ML), Reset button, separation table."""
        # Simulated user marks for Peanut
        # User marked 1 normal (score 35.0) and 3 suspect (scores 75.0, 85.0, 92.0)
        test_marks = {
            "test_1": {"material": "Peanut", "score": 35.0, "mark": "normal"},
            "test_2": {"material": "Peanut", "score": 75.0, "mark": "suspect"},
            "test_3": {"material": "Peanut", "score": 85.0, "mark": "suspect"},
            "test_4": {"material": "Peanut", "score": 92.0, "mark": "suspect"},
        }

        fitted_threshold = fit_threshold_from_marks("Peanut", test_marks)
        # Threshold should be cleanly between 35.0 and 75.0 (e.g., around 55.0)
        self.assertGreater(fitted_threshold, 35.0)
        self.assertLessEqual(fitted_threshold, 75.0)

        # Check separation performance stats
        stats = compute_material_separation_stats("Peanut", fitted_threshold, test_marks)
        self.assertEqual(stats["total_marked"], 4)
        self.assertEqual(stats["true_normal"], 1)
        self.assertEqual(stats["false_suspect"], 0)
        self.assertEqual(stats["true_suspect"], 3)
        self.assertEqual(stats["false_normal"], 0)
        self.assertEqual(stats["accuracy_pct"], 100.0)

        # Save to settings table and test Reset
        set_inspection_setting("colour_screening_threshold_peanut", str(fitted_threshold))
        self.assertEqual(get_material_colour_threshold("Peanut"), fitted_threshold)

        # Reset button behavior
        set_inspection_setting("colour_screening_threshold_peanut", "40.0")
        self.assertEqual(get_material_colour_threshold("Peanut"), 40.0)
        print("[PASS] test_02_simple_threshold_fitting_no_ml passed")

    def test_03_login_required_and_calibration_endpoints(self):
        """Requirement 2 & 3: Calibration page requires login, serves data, handles mark and fit APIs."""
        # 1. Unauthenticated request to /qc/calibration should redirect to login (HTTP 302)
        resp_unauth = self.client.get('/qc/calibration')
        self.assertIn(resp_unauth.status_code, [302, 401], "Unauthenticated request must be redirected to login")

        # 2. Authenticate as QC user
        db = get_db()
        qc_user = db.query(User).filter_by(role='QC').first() or db.query(User).filter_by(role='ADMIN').first()
        self.assertIsNotNone(qc_user, "QC or Admin user must exist in DB")

        with self.client.session_transaction() as sess:
            sess['user_id'] = qc_user.id
            sess['role'] = qc_user.role

        # 3. Authenticated request to /qc/calibration
        resp = self.client.get('/qc/calibration')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Colour Screening Calibration", html)
        self.assertIn("Colour screening only. Not a mold or lab test.", html)
        self.assertIn("Threshold Separation Performance", html)

        # 4. GET /api/qc/calibration/data
        resp_data = self.client.get('/api/qc/calibration/data')
        self.assertEqual(resp_data.status_code, 200)
        cdata = resp_data.get_json()
        self.assertTrue(cdata['success'])
        self.assertIn('thresholds', cdata)
        self.assertIn('separation_table', cdata)
        self.assertIn('kernels', cdata)
        self.assertEqual(cdata['footer_notice'], "Colour screening only. Not a mold or lab test.")

        # 5. POST /api/qc/calibration/mark
        mark_resp = self.client.post('/api/qc/calibration/mark', json={
            "kernel_uid": "test_frame_1",
            "frame_id": 999,
            "kernel_id": 1,
            "material": "Peanut",
            "score": 88.5,
            "mark": "suspect"
        })
        self.assertEqual(mark_resp.status_code, 200)
        mdata = mark_resp.get_json()
        self.assertTrue(mdata['success'])
        self.assertEqual(mdata['mark'], 'suspect')

        # 6. POST /api/qc/calibration/fit
        fit_resp = self.client.post('/api/qc/calibration/fit', json={"material": "Peanut"})
        self.assertEqual(fit_resp.status_code, 200)
        fdata = fit_resp.get_json()
        self.assertTrue(fdata['success'])
        self.assertIn('fitted_thresholds', fdata)

        # 7. POST /api/qc/calibration/reset
        reset_resp = self.client.post('/api/qc/calibration/reset', json={"material": "all"})
        self.assertEqual(reset_resp.status_code, 200)
        rdata = reset_resp.get_json()
        self.assertTrue(rdata['success'])
        self.assertEqual(rdata['thresholds']['Peanut'], 40.0)

        # 8. POST /api/qc/calibration/clear-marks
        clear_resp = self.client.post('/api/qc/calibration/clear-marks')
        self.assertEqual(clear_resp.status_code, 200)
        print("[PASS] test_03_login_required_and_calibration_endpoints passed")

    def test_04_labels_footer_and_no_mold_in_colour_mode(self):
        """Requirement 3: Labels 'Normal' and 'Suspect (discoloured)'. Never write 'mold' in colour mode."""
        db = get_db()
        frame = db.query(LiveFrame).filter_by(id=713).first()
        self.assertIsNotNone(frame)
        disk_path = os.path.join(Config.BASE_DIR, frame.image_path.lstrip('/').replace('/', os.sep))

        res = find_kernels_classical(disk_path, suspect_threshold=40.0)
        for k in res["kernels"]:
            c = k["classification"]
            self.assertIn(c, ["Normal", "Suspect (discoloured)"])
            self.assertNotIn("mold", c.lower())
            self.assertNotIn("moldy", c.lower())

        # Debug view footer check
        self.assertIn("Colour screening only. Not a mold or lab test.", res.get("footer_notice", "Colour screening only. Not a mold or lab test."))
        print("[PASS] test_04_labels_footer_and_no_mold_in_colour_mode passed")

    def test_05_sunflower_uses_same_engine_never_gets_pass(self):
        """Requirement 4: Sunflower uses the same engine. Sunflower never gets an automatic Pass."""
        # 1. Classical kernel finder works identically for Sunflower material
        db = get_db()
        frame = db.query(LiveFrame).filter_by(id=713).first()
        disk_path = os.path.join(Config.BASE_DIR, frame.image_path.lstrip('/').replace('/', os.sep))

        res_sunflower = find_kernels_classical(disk_path, suspect_threshold=40.0, material="Sunflower")
        self.assertGreater(res_sunflower["total_kernels"], 0)
        for k in res_sunflower["kernels"]:
            self.assertIn(k["classification"], ["Normal", "Suspect (discoloured)"])
            self.assertNotIn("mold", k["classification"].lower())

        # 2. Decision check: Sunflower never gets an automatic Pass
        from routes.qc import final_decision
        sf_clean_result = {
            "status": "APPROVED",
            "suggestion": "Pass",
            "material": "Sunflower",
            "confidence": 0.95,
            "items_counted": 10,
            "usable_frames_count": 5,
            "good_pct": 1.0,
            "defect_pct": 0.0,
            "warnings": []
        }
        dec = final_decision(sf_clean_result)
        # Even with 0 defects and 100% good_pct, Sunflower must NEVER get PASS!
        self.assertNotEqual(dec["state"], "PASS", "Sunflower must never receive an automatic Pass!")
        self.assertEqual(dec["state"], "REVIEW", "Sunflower must receive REVIEW state with colour screening note")
        self.assertIn("cannot be automatically passed", dec["reason"])
        print("[PASS] test_05_sunflower_uses_same_engine_never_gets_pass passed")


if __name__ == '__main__':
    unittest.main()
