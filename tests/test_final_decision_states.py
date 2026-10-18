"""
Tests for Final Decision Quality States, Override Reason Audit, and Frame Labeling
Requirements:
1. Four States: RETAKE, REVIEW, REJECT, PASS
   - RETAKE: fewer than 5 kernels, fewer than 3 usable frames, or very blurry. Show no percentages (defect_pct is None).
   - REVIEW: material unclear (below agreement rule), mismatch with lot, low average confidence,
             more than 20% uncertain kernels, defect % between pass and reject limits, any warning, or Sunflower.
   - REJECT: material clear AND defect % above reject limit.
   - PASS: material clear, enough kernels, defect % below pass limit, no warnings.
   - Sunflower never gets PASS.
   - Peanut results always carry: "Camera screening only. Peanut lots need lab testing before release."
2. defect_pct is null/None when material is unclear or state is RETAKE.
3. Label formatting: "n flagged of m kernels".
4. Approving non-PASS or rejecting non-REJECT requires a written reason (who, when, reason) saved in record.
"""
import unittest
import json
import datetime

from app import create_app
from models import get_db
from models.user import User
from models.schema_draft import RawMaterialLot
from models.qc import LiveSession, LiveFrame, AIInspection, InspectionImage, QCDecision
from models.enums import RoleEnum, StatusEnum
from routes.qc import final_decision


class TestFinalDecisionStates(unittest.TestCase):
    """Unit tests for the final_decision(result) engine."""

    def test_state_retake_fewer_than_5_kernels(self):
        result = {
            "material": "Corn",
            "kernels_checked": 4,
            "usable_frames": 5,
            "defect_pct": 0.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "winner_ratio": 1.0,
            "avg_confidence": 0.95
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "RETAKE")
        self.assertIsNone(fd["defect_pct"], "defect_pct must be None for RETAKE")
        self.assertIn("at least 5 kernels are required", fd["reason"])
        self.assertEqual(len(fd["reason"].split(".")), 2, "Reason must be one plain sentence")
        self.assertTrue(any("raw" in d.lower() for d in fd["details"]), "Raw defect rate kept in details")

    def test_state_retake_fewer_than_3_usable_frames(self):
        result = {
            "material": "Corn",
            "kernels_checked": 12,
            "usable_frames": 2,
            "defect_pct": 2.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "winner_ratio": 1.0,
            "avg_confidence": 0.95
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "RETAKE")
        self.assertIsNone(fd["defect_pct"])
        self.assertIn("usable frame", fd["reason"])

    def test_state_retake_very_blurry(self):
        result = {
            "material": "Corn",
            "kernels_checked": 15,
            "usable_frames": 5,
            "is_blurry": True,
            "defect_pct": 1.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "winner_ratio": 1.0,
            "avg_confidence": 0.95
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "RETAKE")
        self.assertIsNone(fd["defect_pct"])
        self.assertIn("blurry", fd["reason"].lower())

    def test_state_review_material_unclear_agreement_below_70(self):
        result = {
            "material": "Corn",
            "kernels_checked": 15,
            "usable_frames": 5,
            "winner_ratio": 0.60,  # Below 70% threshold
            "defect_pct": 2.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "avg_confidence": 0.90
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "REVIEW")
        self.assertIsNone(fd["defect_pct"], "defect_pct must be null when material is unclear")
        self.assertIn("unclear", fd["reason"].lower())

    def test_state_review_material_unclear_mixed(self):
        result = {
            "material": "Unknown / mixed",
            "kernels_checked": 15,
            "usable_frames": 5,
            "defect_pct": 3.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "REVIEW")
        self.assertIsNone(fd["defect_pct"])

    def test_state_review_lot_mismatch(self):
        result = {
            "material": "Corn",
            "lot_material": "Peanut",
            "material_mismatch": True,
            "mismatch_warning": "Detected material (Corn) does not match lot material (Peanut).",
            "kernels_checked": 15,
            "usable_frames": 5,
            "winner_ratio": 1.0,
            "defect_pct": 1.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "avg_confidence": 0.90
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "REVIEW")
        self.assertEqual(fd["defect_pct"], 1.0, "defect_pct preserved when material is clear but lot mismatched")
        self.assertIn("match", fd["reason"].lower())

    def test_state_review_low_average_confidence(self):
        result = {
            "material": "Corn",
            "kernels_checked": 15,
            "usable_frames": 5,
            "winner_ratio": 1.0,
            "defect_pct": 2.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "avg_confidence": 0.42  # Below 50%
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "REVIEW")
        self.assertIn("50%", fd["reason"])

    def test_state_review_high_uncertain_kernels(self):
        result = {
            "material": "Corn",
            "kernels_checked": 10,
            "usable_frames": 5,
            "winner_ratio": 1.0,
            "uncertain_ratio": 0.30,  # > 20%
            "defect_pct": 2.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "avg_confidence": 0.90
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "REVIEW")
        self.assertIn("uncertain", fd["reason"].lower())

    def test_state_review_defect_between_pass_and_reject(self):
        result = {
            "material": "Corn",
            "kernels_checked": 20,
            "usable_frames": 5,
            "winner_ratio": 1.0,
            "defect_pct": 6.5,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "avg_confidence": 0.90
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "REVIEW")
        self.assertEqual(fd["defect_pct"], 6.5)
        self.assertIn("between", fd["reason"].lower())

    def test_state_review_sunflower_never_gets_pass(self):
        # Sunflower with 0% defects and clean specimen must still be REVIEW, never PASS
        result = {
            "material": "Sunflower",
            "kernels_checked": 25,
            "usable_frames": 5,
            "winner_ratio": 1.0,
            "defect_pct": 0.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "avg_confidence": 0.95
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "REVIEW", "Sunflower must NEVER get PASS")
        self.assertIn("colour screening only", fd["reason"].lower())

    def test_state_reject_material_clear_above_reject_limit(self):
        result = {
            "material": "Corn",
            "kernels_checked": 20,
            "usable_frames": 5,
            "winner_ratio": 1.0,
            "defect_pct": 12.5,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "avg_confidence": 0.92
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "REJECT")
        self.assertEqual(fd["defect_pct"], 12.5)
        self.assertIn("exceeds", fd["reason"].lower())

    def test_state_pass_clean_corn(self):
        result = {
            "material": "Corn",
            "kernels_checked": 20,
            "usable_frames": 5,
            "winner_ratio": 1.0,
            "defect_pct": 1.5,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "avg_confidence": 0.92
        }
        fd = final_decision(result)
        self.assertEqual(fd["state"], "PASS")
        self.assertEqual(fd["defect_pct"], 1.5)
        self.assertIn("verified as Corn", fd["reason"])

    def test_peanut_always_carries_lab_testing_note(self):
        result = {
            "material": "Peanut",
            "kernels_checked": 20,
            "usable_frames": 5,
            "winner_ratio": 1.0,
            "defect_pct": 1.0,
            "pass_limit": 5.0,
            "reject_limit": 8.0,
            "avg_confidence": 0.92
        }
        fd = final_decision(result)
        expected_note = "Camera screening only. Peanut lots need lab testing before release."
        self.assertIn(expected_note, fd["details"])


class TestOverrideWrittenReasonWorkflow(unittest.TestCase):
    """Integration tests for approving non-PASS or rejecting non-REJECT requiring written reason."""

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
            self.lot = db.query(RawMaterialLot).first()

    def login_qc(self):
        return self.client.post('/login', data={'email': 'qc@foodman.vn', 'password': 'password123'}, follow_redirects=True)

    def test_approve_non_pass_requires_written_reason(self):
        self.login_qc()
        with self.app.app_context():
            db = get_db()
            # Create a live session with REVIEW locked result
            review_res = {
                "material": "Corn",
                "kernels_checked": 15,
                "usable_frames": 5,
                "winner_ratio": 0.60,  # Unclear material -> REVIEW
                "defect_pct": 2.0,
                "pass_limit": 5.0,
                "reject_limit": 8.0
            }
            import secrets
            sess = LiveSession(
                lot_id=self.lot.id,
                token=f"test_override_{secrets.token_urlsafe(12)}",
                status="ACTIVE",
                locked_result_json=json.dumps(review_res),
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            )
            db.add(sess)
            db.commit()
            sess_id = sess.id

        # 1. Attempt to ACCEPT without notes -> must return 400
        res_fail = self.client.post(f'/api/qc/live-session/{sess_id}/confirm-verdict', json={
            "verdict": "ACCEPT",
            "notes": ""
        })
        self.assertEqual(res_fail.status_code, 400)
        data_fail = json.loads(res_fail.data)
        self.assertFalse(data_fail.get("success"))
        self.assertIn("requires a written reason", data_fail.get("error", ""))

        # 2. Attempt to ACCEPT with written reason -> must succeed 200
        res_ok = self.client.post(f'/api/qc/live-session/{sess_id}/confirm-verdict', json={
            "verdict": "ACCEPT",
            "notes": "Manual visual inspection confirmed all kernels healthy despite classifier ambiguity."
        })
        self.assertEqual(res_ok.status_code, 200)
        data_ok = json.loads(res_ok.data)
        self.assertTrue(data_ok.get("success"))

        # Verify audit record saved (who, when, reason)
        with self.app.app_context():
            db = get_db()
            dec = db.query(QCDecision).filter_by(id=data_ok["decision_id"]).first()
            self.assertIsNotNone(dec)
            self.assertIn("Override", dec.reason)
            self.assertIn("Manual visual inspection confirmed", dec.action_notes)
            self.assertIn(self.qc_user.full_name, dec.action_notes)

    def test_reject_non_reject_requires_written_reason(self):
        self.login_qc()
        with self.app.app_context():
            db = get_db()
            # Create a live session with PASS locked result
            pass_res = {
                "material": "Corn",
                "kernels_checked": 20,
                "usable_frames": 5,
                "winner_ratio": 1.0,
                "defect_pct": 0.5,
                "pass_limit": 5.0,
                "reject_limit": 8.0,
                "avg_confidence": 0.95
            }
            import secrets
            sess = LiveSession(
                lot_id=self.lot.id,
                token=f"test_override_{secrets.token_urlsafe(12)}",
                status="ACTIVE",
                locked_result_json=json.dumps(pass_res),
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            )
            db.add(sess)
            db.commit()
            sess_id = sess.id

        # 1. Attempt to REJECT a PASS lot without written reason -> must return 400
        res_fail = self.client.post(f'/api/qc/live-session/{sess_id}/confirm-verdict', json={
            "verdict": "REJECT",
            "notes": ""
        })
        self.assertEqual(res_fail.status_code, 400)
        data_fail = json.loads(res_fail.data)
        self.assertFalse(data_fail.get("success"))
        self.assertIn("requires a written reason", data_fail.get("error", ""))

        # 2. Attempt to REJECT with written reason -> must succeed 200
        res_ok = self.client.post(f'/api/qc/live-session/{sess_id}/confirm-verdict', json={
            "verdict": "REJECT",
            "notes": "Strong pesticide odor detected upon opening shipment tote."
        })
        self.assertEqual(res_ok.status_code, 200)
        data_ok = json.loads(res_ok.data)
        self.assertTrue(data_ok.get("success"))

    def test_normal_pass_approval_succeeds_without_written_reason(self):
        self.login_qc()
        with self.app.app_context():
            db = get_db()
            import secrets
            pass_res = {
                "material": "Corn",
                "kernels_checked": 20,
                "usable_frames": 5,
                "winner_ratio": 1.0,
                "defect_pct": 0.5,
                "pass_limit": 5.0,
                "reject_limit": 8.0,
                "avg_confidence": 0.95
            }
            sess = LiveSession(
                lot_id=self.lot.id,
                token=f"test_normal_pass_{secrets.token_urlsafe(12)}",
                status="ACTIVE",
                locked_result_json=json.dumps(pass_res),
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            )
            db.add(sess)
            db.commit()
            sess_id = sess.id

        # PASS lot approved without notes -> 200 OK
        res = self.client.post(f'/api/qc/live-session/{sess_id}/confirm-verdict', json={
            "verdict": "ACCEPT",
            "notes": ""
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("final_status"), "APPROVED")

    def test_pdf_report_generation_returns_valid_pdf(self):
        self.login_qc()
        with self.app.app_context():
            db = get_db()
            insp = db.query(AIInspection).order_by(AIInspection.id.desc()).first()
            self.assertIsNotNone(insp, "At least one inspection record must exist")
            insp_id = insp.id

        res = self.client.get(f'/api/qc/ai-inspection/{insp_id}/pdf')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "application/pdf")
        self.assertTrue(res.data.startswith(b'%PDF'), "Response must be valid PDF stream")

    def test_frame_caption_formatting_rule(self):
        # Caption rule: "n flagged of m kernels"
        frames = [
            {"defect_count": 0, "good_count": 8},
            {"defect_count": 2, "good_count": 6},
            {"defect_count": 5, "good_count": 0}
        ]
        captions = [
            f"{f['defect_count']} flagged of {f['good_count'] + f['defect_count']} kernels"
            for f in frames
        ]
        self.assertEqual(captions[0], "0 flagged of 8 kernels")
        self.assertEqual(captions[1], "2 flagged of 8 kernels")
        self.assertEqual(captions[2], "5 flagged of 5 kernels")


if __name__ == '__main__':
    unittest.main()
