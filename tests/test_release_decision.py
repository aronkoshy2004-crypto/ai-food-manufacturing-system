"""
Comprehensive Unit & Integration Tests for Combined Release Decision
Tests:
1. Matrix Rows:
   - COA PASS + AI PASS -> RELEASE
   - COA PASS + AI REVIEW -> HOLD ("inspector checks by eye")
   - COA PASS + AI RETAKE -> HOLD ("inspector checks by eye")
   - COA PASS + AI NOT_RUN -> HOLD ("inspector checks by eye")
   - COA PASS + AI REJECT -> HOLD ("paper passes, camera disagrees: investigate")
   - COA FAIL + AI PASS -> REJECT
   - COA FAIL + AI REJECT -> REJECT
   - COA FAIL + AI REVIEW/RETAKE/NOT_RUN -> REJECT
   - COA MISSING + Any AI -> HOLD ("valid COA needed")
2. Material mismatch between order and camera -> HOLD
3. Sunflower rule: Sunflower never gets an AI PASS -> HOLD
4. Peanut rule: COA aflatoxin result decides, AI never overrides failed COA, shows required advisory
5. Four Demo Lots:
   - Demo 1: COA pass with AI pass -> RELEASE
   - Demo 2: COA pass with AI reject -> HOLD
   - Demo 3: COA fail -> REJECT
   - Demo 4: COA missing -> HOLD
"""
import unittest
import datetime
from unittest.mock import MagicMock
from ai.release_decision import release_decision, evaluate_coa_document, evaluate_ai_inspection, MATERIAL_SPECS


class MockLot:
    def __init__(self, id=1, lot_number="LOT-CORN-001", material_name="Corn", supplier_id=10, supplier_name="AgriFarm Ltd"):
        self.id = id
        self.lot_number = lot_number
        self.material_name = material_name
        self.category = material_name
        self.supplier_id = supplier_id
        self.supplier_name = supplier_name
        self.qc_samples = []


class MockCOA:
    def __init__(self, id=1, raw_material_lot_id=1, supplier_id=10, doc_number="COA-TEST-001", notes="", issued_date=None, expiry_date=None):
        self.id = id
        self.raw_material_lot_id = raw_material_lot_id
        self.supplier_id = supplier_id
        self.doc_number = doc_number
        self.notes = notes
        self.issued_date = issued_date or datetime.datetime.utcnow()
        self.expiry_date = expiry_date
        self.supplier = None


class MockTest:
    def __init__(self, parameter_name, measured_value, standard_spec="", is_pass=True):
        self.parameter_name = parameter_name
        self.measured_value = measured_value
        self.standard_spec = standard_spec
        self.is_pass = is_pass


class TestReleaseDecisionMatrix(unittest.TestCase):

    def setUp(self):
        self.corn_lot = MockLot(id=1, lot_number="LOT-CORN-01", material_name="Corn", supplier_id=10)
        self.valid_corn_coa = MockCOA(id=1, raw_material_lot_id=1, supplier_id=10, doc_number="COA-CORN-01")
        self.valid_corn_tests = [
            MockTest("Moisture Content", "12.5%", "< 14.0%", True),
            MockTest("Aflatoxin B1", "1.2 ppb", "< 5.0 ppb", True),
            MockTest("Purity Rate", "99.0%", ">= 98.0%", True),
        ]

    # --- 1. Matrix Combinations ---

    def test_coa_pass_ai_pass_yields_release(self):
        res = release_decision(
            self.corn_lot,
            coa=self.valid_corn_coa,
            tests=self.valid_corn_tests,
            ai_result={"state": "PASS", "total_defects_count": 0}
        )
        self.assertEqual(res["coa_state"], "PASS")
        self.assertEqual(res["ai_state"], "PASS")
        self.assertEqual(res["outcome"], "RELEASE")
        self.assertTrue(res["is_release_enabled"])

    def test_coa_pass_ai_review_yields_hold(self):
        res = release_decision(
            self.corn_lot,
            coa=self.valid_corn_coa,
            tests=self.valid_corn_tests,
            ai_result={"state": "REVIEW", "total_defects_count": 0}
        )
        self.assertEqual(res["coa_state"], "PASS")
        self.assertEqual(res["ai_state"], "REVIEW")
        self.assertEqual(res["outcome"], "HOLD")
        self.assertIn("inspector checks by eye", res["reason"].lower())

    def test_coa_pass_ai_retake_yields_hold(self):
        res = release_decision(
            self.corn_lot,
            coa=self.valid_corn_coa,
            tests=self.valid_corn_tests,
            ai_result={"state": "RETAKE"}
        )
        self.assertEqual(res["coa_state"], "PASS")
        self.assertEqual(res["ai_state"], "RETAKE")
        self.assertEqual(res["outcome"], "HOLD")
        self.assertIn("inspector checks by eye", res["reason"].lower())

    def test_coa_pass_ai_not_run_yields_hold(self):
        res = release_decision(
            self.corn_lot,
            coa=self.valid_corn_coa,
            tests=self.valid_corn_tests,
            ai_result=None  # NOT_RUN
        )
        self.assertEqual(res["coa_state"], "PASS")
        self.assertEqual(res["ai_state"], "NOT_RUN")
        self.assertEqual(res["outcome"], "HOLD")
        self.assertIn("inspector checks by eye", res["reason"].lower())

    def test_coa_pass_ai_reject_yields_hold(self):
        res = release_decision(
            self.corn_lot,
            coa=self.valid_corn_coa,
            tests=self.valid_corn_tests,
            ai_result={"state": "REJECT", "total_defects_count": 3}
        )
        self.assertEqual(res["coa_state"], "PASS")
        self.assertEqual(res["ai_state"], "REJECT")
        self.assertEqual(res["outcome"], "HOLD")
        self.assertIn("paper passes, camera disagrees", res["reason"].lower())

    def test_coa_fail_ai_pass_yields_reject(self):
        # Failing COA (moisture 15.5% > 14.0%)
        failing_tests = [
            MockTest("Moisture Content", "15.5%", "< 14.0%", True)
        ]
        res = release_decision(
            self.corn_lot,
            coa=self.valid_corn_coa,
            tests=failing_tests,
            ai_result={"state": "PASS", "total_defects_count": 0}
        )
        self.assertEqual(res["coa_state"], "FAIL")
        self.assertEqual(res["ai_state"], "PASS")
        self.assertEqual(res["outcome"], "REJECT")
        self.assertFalse(res["is_release_enabled"])

    def test_coa_fail_ai_reject_yields_reject(self):
        failing_tests = [MockTest("Aflatoxin B1", "8.2 ppb", "< 5.0 ppb", False)]
        res = release_decision(
            self.corn_lot,
            coa=self.valid_corn_coa,
            tests=failing_tests,
            ai_result={"state": "REJECT", "total_defects_count": 5}
        )
        self.assertEqual(res["coa_state"], "FAIL")
        self.assertEqual(res["ai_state"], "REJECT")
        self.assertEqual(res["outcome"], "REJECT")

    def test_coa_missing_yields_hold(self):
        res = release_decision(
            self.corn_lot,
            coa=None,
            ai_result={"state": "PASS", "total_defects_count": 0}
        )
        self.assertEqual(res["coa_state"], "MISSING")
        self.assertEqual(res["outcome"], "HOLD")
        self.assertIn("valid coa needed", res["reason"].lower())

    # --- 2. Material Mismatch ---

    def test_material_mismatch_yields_hold(self):
        res = release_decision(
            self.corn_lot,
            coa=self.valid_corn_coa,
            tests=self.valid_corn_tests,
            ai_result={"state": "PASS", "material_mismatch": True, "material": "Peanut"}
        )
        self.assertEqual(res["outcome"], "HOLD")
        self.assertIn("differs", res["reason"].lower())

    # --- 3. Sunflower Rules ---

    def test_sunflower_never_gets_ai_pass_and_yields_hold(self):
        sunflower_lot = MockLot(id=2, lot_number="LOT-SUN-01", material_name="Sunflower", supplier_id=10)
        sunflower_coa = MockCOA(id=2, raw_material_lot_id=2, supplier_id=10, doc_number="COA-SUN-01")
        sunflower_tests = [
            MockTest("Moisture Content", "7.5%", "< 9.0%", True),
            MockTest("Free Fatty Acids (FFA)", "0.8%", "< 1.5%", True),
            MockTest("Purity Rate", "99.5%", ">= 98.0%", True)
        ]
        # Even if AI detector would claim PASS
        res = release_decision(
            sunflower_lot,
            coa=sunflower_coa,
            tests=sunflower_tests,
            ai_result={"state": "PASS", "total_defects_count": 0}
        )
        self.assertEqual(res["coa_state"], "PASS")
        self.assertEqual(res["ai_state"], "REVIEW", "Sunflower must never receive AI PASS")
        self.assertEqual(res["outcome"], "HOLD")
        self.assertIn("sunflower", res["reason"].lower())
        self.assertIsNotNone(res["sunflower_advisory"])

    # --- 4. Peanut Rules ---

    def test_peanut_coa_aflatoxin_decides_ai_never_overrides(self):
        peanut_lot = MockLot(id=3, lot_number="LOT-PEANUT-01", material_name="Peanut", supplier_id=10)
        peanut_coa = MockCOA(id=3, raw_material_lot_id=3, supplier_id=10, doc_number="COA-PEANUT-01")

        # Failing aflatoxin: 3.5 ppb > 2.0 ppb
        peanut_tests_fail = [
            MockTest("Moisture Content", "6.5%", "< 8.0%", True),
            MockTest("Aflatoxin B1", "3.5 ppb", "< 2.0 ppb", True),
            MockTest("Purity Rate", "99.0%", ">= 98.0%", True),
            MockTest("Oil Content", "50.0%", ">= 48.0%", True)
        ]

        # Even with AI PASS (clean kernels), COA aflatoxin failure cannot be overridden
        res = release_decision(
            peanut_lot,
            coa=peanut_coa,
            tests=peanut_tests_fail,
            ai_result={"state": "PASS", "total_defects_count": 0}
        )
        self.assertEqual(res["coa_state"], "FAIL")
        self.assertEqual(res["outcome"], "REJECT")
        self.assertIn("aflatoxin", res["reason"].lower())
        self.assertIn("Camera screening only. Peanut lots need lab testing before release.", res["details"])

    def test_peanut_clean_coa_and_ai_pass_yields_release_with_advisory(self):
        peanut_lot = MockLot(id=3, lot_number="LOT-PEANUT-01", material_name="Peanut", supplier_id=10)
        peanut_coa = MockCOA(id=3, raw_material_lot_id=3, supplier_id=10, doc_number="COA-PEANUT-01")
        peanut_tests_pass = [
            MockTest("Moisture Content", "6.5%", "< 8.0%", True),
            MockTest("Aflatoxin B1", "0.5 ppb", "< 2.0 ppb", True),
            MockTest("Purity Rate", "99.0%", ">= 98.0%", True),
            MockTest("Oil Content", "50.0%", ">= 48.0%", True)
        ]
        res = release_decision(
            peanut_lot,
            coa=peanut_coa,
            tests=peanut_tests_pass,
            ai_result={"state": "PASS", "total_defects_count": 0}
        )
        self.assertEqual(res["coa_state"], "PASS")
        self.assertEqual(res["ai_state"], "PASS")
        self.assertEqual(res["outcome"], "RELEASE")
        self.assertEqual(res["peanut_advisory"], "Camera screening only. Peanut lots need lab testing before release.")

    # --- 5. COA Validation Rules (Ownership & Expiry) ---

    def test_coa_belonging_to_wrong_lot_fails(self):
        wrong_lot_coa = MockCOA(id=4, raw_material_lot_id=999, supplier_id=10)
        res = release_decision(self.corn_lot, coa=wrong_lot_coa, tests=self.valid_corn_tests)
        self.assertEqual(res["coa_state"], "FAIL")
        self.assertEqual(res["outcome"], "REJECT")
        self.assertIn("belongs to lot", res["reason"].lower())

    def test_coa_supplier_mismatch_fails(self):
        wrong_sup_coa = MockCOA(id=5, raw_material_lot_id=1, supplier_id=888)
        res = release_decision(self.corn_lot, coa=wrong_sup_coa, tests=self.valid_corn_tests)
        self.assertEqual(res["coa_state"], "FAIL")
        self.assertEqual(res["outcome"], "REJECT")
        self.assertIn("supplier", res["reason"].lower())

    def test_expired_coa_fails(self):
        expired_date = datetime.datetime.utcnow() - datetime.timedelta(days=10)
        expired_coa = MockCOA(id=6, raw_material_lot_id=1, supplier_id=10, expiry_date=expired_date)
        res = release_decision(self.corn_lot, coa=expired_coa, tests=self.valid_corn_tests)
        self.assertEqual(res["coa_state"], "FAIL")
        self.assertEqual(res["outcome"], "REJECT")
        self.assertIn("expired", res["reason"].lower())


class TestFourDemoLots(unittest.TestCase):
    """
    Requirement 6: Create four demo lots:
    1. COA pass with AI pass -> RELEASE
    2. COA pass with AI reject -> HOLD
    3. COA fail -> REJECT
    4. COA missing -> HOLD
    """

    def test_demo_lot_1_coa_pass_ai_pass(self):
        lot1 = MockLot(id=101, lot_number="DEMO-LOT-REL-01", material_name="Corn", supplier_id=1)
        coa1 = MockCOA(id=101, raw_material_lot_id=101, supplier_id=1, doc_number="COA-DEMO-01")
        tests1 = [
            MockTest("Moisture Content", "12.0%", "< 14.0%", True),
            MockTest("Aflatoxin B1", "1.0 ppb", "< 5.0 ppb", True),
            MockTest("Purity Rate", "99.2%", ">= 98.0%", True)
        ]
        res1 = release_decision(lot1, coa=coa1, tests=tests1, ai_result={"state": "PASS", "total_defects_count": 0})
        self.assertEqual(res1["coa_state"], "PASS")
        self.assertEqual(res1["ai_state"], "PASS")
        self.assertEqual(res1["outcome"], "RELEASE")

    def test_demo_lot_2_coa_pass_ai_reject(self):
        lot2 = MockLot(id=102, lot_number="DEMO-LOT-REL-02", material_name="Corn", supplier_id=1)
        coa2 = MockCOA(id=102, raw_material_lot_id=102, supplier_id=1, doc_number="COA-DEMO-02")
        tests2 = [
            MockTest("Moisture Content", "12.0%", "< 14.0%", True),
            MockTest("Aflatoxin B1", "1.0 ppb", "< 5.0 ppb", True),
            MockTest("Purity Rate", "99.2%", ">= 98.0%", True)
        ]
        res2 = release_decision(lot2, coa=coa2, tests=tests2, ai_result={"state": "REJECT", "total_defects_count": 4})
        self.assertEqual(res2["coa_state"], "PASS")
        self.assertEqual(res2["ai_state"], "REJECT")
        self.assertEqual(res2["outcome"], "HOLD")
        self.assertIn("paper passes, camera disagrees", res2["reason"].lower())

    def test_demo_lot_3_coa_fail(self):
        lot3 = MockLot(id=103, lot_number="DEMO-LOT-REL-03", material_name="Peanut", supplier_id=2)
        coa3 = MockCOA(id=103, raw_material_lot_id=103, supplier_id=2, doc_number="COA-DEMO-03")
        # Failing aflatoxin (4.8 ppb > 2.0 ppb limit)
        tests3 = [
            MockTest("Moisture Content", "7.0%", "< 8.0%", True),
            MockTest("Aflatoxin B1", "4.8 ppb", "< 2.0 ppb", True),
            MockTest("Purity Rate", "99.0%", ">= 98.0%", True)
        ]
        res3 = release_decision(lot3, coa=coa3, tests=tests3, ai_result={"state": "PASS", "total_defects_count": 0})
        self.assertEqual(res3["coa_state"], "FAIL")
        self.assertEqual(res3["outcome"], "REJECT")

    def test_demo_lot_4_coa_missing(self):
        lot4 = MockLot(id=104, lot_number="DEMO-LOT-REL-04", material_name="Peanut", supplier_id=3)
        res4 = release_decision(lot4, coa=None, ai_result={"state": "PASS", "total_defects_count": 0})
        self.assertEqual(res4["coa_state"], "MISSING")
        self.assertEqual(res4["outcome"], "HOLD")
        self.assertIn("valid coa needed", res4["reason"].lower())


if __name__ == "__main__":
    unittest.main()
