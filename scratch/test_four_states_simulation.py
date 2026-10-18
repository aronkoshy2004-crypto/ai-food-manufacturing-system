"""
Comprehensive test script for simulating the 4 states (PASS, REVIEW, REJECT, RETAKE)
and verifying PDF report generation and final_decision object properties.
"""
import unittest
import os
import json
from app import create_app
from models import get_db
from models.user import User
from models.schema_draft import RawMaterialLot
from models.qc import LiveSession, AIInspection, QCDecision
from routes.qc import final_decision, generate_inspection_pdf

class TestFourStatesSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    def login_admin(self):
        return self.client.post('/login', data={
            'email': 'admin@foodman.vn',
            'password': 'password123'
        }, follow_redirects=True)

    def test_state_1_pass(self):
        res = {
            "material": "Corn",
            "kernels_checked": 21,
            "usable_frames": 5,
            "defect_pct": 0.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "winner_ratio": 1.0,
            "avg_confidence": 0.96
        }
        fd = final_decision(res)
        self.assertEqual(fd["state"], "PASS")
        self.assertEqual(fd["material"], "Corn")
        self.assertEqual(fd["kernels_checked"], 21)
        self.assertEqual(fd["defect_pct"], 0.0)
        self.assertIn("pass limit", fd["reason"])
        self.assertIn("standard sign-off", fd["next_step"])
        self.assertFalse(any("specimen" in d.lower() for d in fd["details"]))

    def test_state_2_review(self):
        # Material unclear -> defect_pct is null
        res = {
            "material": "Unknown / mixed",
            "kernels_checked": 12,
            "usable_frames": 5,
            "defect_pct": 3.5,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "winner_ratio": 0.55,
            "avg_confidence": 0.88
        }
        fd = final_decision(res)
        self.assertEqual(fd["state"], "REVIEW")
        self.assertIsNone(fd["defect_pct"], "defect_pct must be None when material is unclear")
        self.assertIn("unclear", fd["reason"].lower())
        self.assertIn("manually", fd["next_step"].lower())

    def test_state_3_reject(self):
        res = {
            "material": "Corn",
            "kernels_checked": 20,
            "usable_frames": 5,
            "defect_pct": 14.5,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "winner_ratio": 1.0,
            "avg_confidence": 0.94
        }
        fd = final_decision(res)
        self.assertEqual(fd["state"], "REJECT")
        self.assertEqual(fd["defect_pct"], 14.5)
        self.assertIn("exceeds the allowable reject limit", fd["reason"])
        self.assertIn("Quarantine lot immediately", fd["next_step"])

    def test_state_4_retake(self):
        # Fewer than 5 kernels -> RETAKE, defect_pct is null
        res = {
            "material": "Corn",
            "kernels_checked": 3,
            "usable_frames": 5,
            "defect_pct": 0.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "winner_ratio": 1.0,
            "avg_confidence": 0.95
        }
        fd = final_decision(res)
        self.assertEqual(fd["state"], "RETAKE")
        self.assertIsNone(fd["defect_pct"], "defect_pct must be None for RETAKE")
        self.assertIn("at least 5 kernels are required", fd["reason"])
        self.assertIn("rescan with at least 5 kernels", fd["next_step"])

    def test_peanut_footer_note(self):
        res = {
            "material": "Peanut",
            "kernels_checked": 25,
            "usable_frames": 5,
            "defect_pct": 1.5,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "winner_ratio": 1.0,
            "avg_confidence": 0.95
        }
        fd = final_decision(res)
        self.assertEqual(fd["state"], "PASS")
        self.assertTrue(any("camera screening only" in d.lower() for d in fd["details"]))

    def test_pdf_generation_with_rebuilt_component(self):
        self.login_admin()
        db = get_db()
        insp = db.query(AIInspection).order_by(AIInspection.id.desc()).first()
        if insp:
            res = self.client.get(f'/api/qc/ai-inspection/{insp.id}/pdf')
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.mimetype, 'application/pdf')
            self.assertGreater(len(res.data), 1000)

if __name__ == '__main__':
    unittest.main()
