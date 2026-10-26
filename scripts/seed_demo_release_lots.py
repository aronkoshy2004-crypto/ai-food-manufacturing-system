"""
Seed script for the four Demo Lots specified in Requirement 6:
1. DEMO-LOT-REL-01 (Corn): COA Pass + AI Pass -> RELEASE
2. DEMO-LOT-REL-02 (Corn): COA Pass + AI Reject -> HOLD
3. DEMO-LOT-REL-03 (Peanut): COA Fail (Aflatoxin 4.5 ppb) -> REJECT
4. DEMO-LOT-REL-04 (Peanut): COA Missing -> HOLD
"""
import os
import sys
import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from wsgi import app
from models import get_db
from models.procurement import Supplier, RawMaterialLot, RawMaterial
from models.qc import QCSample, QCTest, COADocument, InspectionImage, AIInspection, DetectedDefect


def seed_demo_release_lots():
    db = get_db()

    # Look up RawMaterial references for Corn and Peanut by code or name
    corn_mat = db.query(RawMaterial).filter(
        (RawMaterial.code == "RM-CORN-001") | (RawMaterial.name.ilike("%corn%"))
    ).first()
    peanut_mat = db.query(RawMaterial).filter(
        (RawMaterial.code == "RM-PEANUT-001") | (RawMaterial.name.ilike("%peanut%"))
    ).first()

    # Ensure demo supplier exists
    sup = db.query(Supplier).filter_by(code="SUP-DEMO-REL").first()
    if not sup:
        sup = Supplier(
            code="SUP-DEMO-REL",
            name="AgriGrain Certified Supply Ltd",
            contact_name="Quality Liaison",
            email="qc@agrigrain.example.com",
            phone="+84-90-1234567",
            status="APPROVED",
            is_active=True
        )
        db.add(sup)
        db.flush()

    now = datetime.datetime.utcnow()

    # Demo Lot 1: COA Pass + AI Pass -> RELEASE
    lot1 = db.query(RawMaterialLot).filter_by(lot_number="DEMO-LOT-REL-01").first()
    if not lot1:
        lot1 = RawMaterialLot(
            lot_number="DEMO-LOT-REL-01",
            material_name="Corn",
            category="Grain",
            supplier_name=sup.name,
            supplier_id=sup.id,
            raw_material_id=corn_mat.id if corn_mat else None,
            quantity=25.0,
            unit="Tons",
            storage_condition="Ambient dry storage < 22°C",
            status="PENDING",
            qc_status="PENDING_QC"
        )
        db.add(lot1)
        db.flush()

        s1 = QCSample(sample_code="SMP-DEMO-01", raw_material_lot_id=lot1.id, sample_date=now)
        db.add(s1)
        db.flush()
        db.add_all([
            QCTest(qc_sample_id=s1.id, parameter_name="Moisture Content", standard_spec="< 14.0%", measured_value="12.2%", is_pass=True),
            QCTest(qc_sample_id=s1.id, parameter_name="Aflatoxin B1", standard_spec="< 5.0 ppb", measured_value="1.2 ppb", is_pass=True),
            QCTest(qc_sample_id=s1.id, parameter_name="Purity Rate", standard_spec=">= 98.0%", measured_value="99.4%", is_pass=True)
        ])

        coa1 = COADocument(
            raw_material_lot_id=lot1.id,
            supplier_id=sup.id,
            doc_number="COA-DEMO-REL-01",
            filename="COA_Corn_Lot01_Certified.pdf",
            file_url="/static/docs/coa_corn_demo01.pdf",
            lab_accreditation="ISO 17025 / VILAS 102",
            is_verified=True,
            issued_date=now
        )
        db.add(coa1)

        img1 = InspectionImage(
            raw_material_lot_id=lot1.id,
            image_url="/static/uploads/raw/20261017_035528_test_corn.jpg",
            image_type="Corn intake visual specimen"
        )
        db.add(img1)
        db.flush()

        ai1 = AIInspection(
            inspection_image_id=img1.id,
            raw_material_lot_id=lot1.id,
            model_version="YOLOv8-Corn-v2",
            inference_time_ms=38.2,
            total_defects_count=0,
            summary="Specimen visually clean, zero defect kernels detected",
            avg_confidence=0.94,
            detected_material="Corn"
        )
        db.add(ai1)

    # Demo Lot 2: COA Pass + AI Reject -> HOLD
    lot2 = db.query(RawMaterialLot).filter_by(lot_number="DEMO-LOT-REL-02").first()
    if not lot2:
        lot2 = RawMaterialLot(
            lot_number="DEMO-LOT-REL-02",
            material_name="Corn",
            category="Grain",
            supplier_name=sup.name,
            supplier_id=sup.id,
            raw_material_id=corn_mat.id if corn_mat else None,
            quantity=20.0,
            unit="Tons",
            storage_condition="Ambient dry storage < 22°C",
            status="PENDING",
            qc_status="PENDING_QC"
        )
        db.add(lot2)
        db.flush()

        s2 = QCSample(sample_code="SMP-DEMO-02", raw_material_lot_id=lot2.id, sample_date=now)
        db.add(s2)
        db.flush()
        db.add_all([
            QCTest(qc_sample_id=s2.id, parameter_name="Moisture Content", standard_spec="< 14.0%", measured_value="11.8%", is_pass=True),
            QCTest(qc_sample_id=s2.id, parameter_name="Aflatoxin B1", standard_spec="< 5.0 ppb", measured_value="1.5 ppb", is_pass=True),
            QCTest(qc_sample_id=s2.id, parameter_name="Purity Rate", standard_spec=">= 98.0%", measured_value="99.1%", is_pass=True)
        ])

        coa2 = COADocument(
            raw_material_lot_id=lot2.id,
            supplier_id=sup.id,
            doc_number="COA-DEMO-REL-02",
            filename="COA_Corn_Lot02_Certified.pdf",
            file_url="/static/docs/coa_corn_demo02.pdf",
            lab_accreditation="ISO 17025 / VILAS 102",
            is_verified=True,
            issued_date=now
        )
        db.add(coa2)

        img2 = InspectionImage(
            raw_material_lot_id=lot2.id,
            image_url="/static/uploads/raw/20261017_035534_test_corn.jpg",
            image_type="Corn intake visual specimen"
        )
        db.add(img2)
        db.flush()

        ai2 = AIInspection(
            inspection_image_id=img2.id,
            raw_material_lot_id=lot2.id,
            model_version="YOLOv8-Corn-v2",
            inference_time_ms=41.0,
            total_defects_count=4,
            summary="Camera detected 4 damaged/discoloured kernels",
            avg_confidence=0.88,
            detected_material="Corn"
        )
        db.add(ai2)
        db.flush()

        for idx, (bx, by) in enumerate([(15, 20), (35, 40), (60, 55), (75, 30)]):
            db.add(DetectedDefect(
                ai_inspection_id=ai2.id,
                defect_class="Corn_Moldy",
                confidence=0.87,
                bbox_x=bx, bbox_y=by, bbox_w=12, bbox_h=12
            ))

    # Demo Lot 3: COA Fail -> REJECT (Peanut, Aflatoxin 4.5 ppb > 2.0 ppb)
    lot3 = db.query(RawMaterialLot).filter_by(lot_number="DEMO-LOT-REL-03").first()
    if not lot3:
        lot3 = RawMaterialLot(
            lot_number="DEMO-LOT-REL-03",
            material_name="Peanut",
            category="Oilseed",
            supplier_name=sup.name,
            supplier_id=sup.id,
            raw_material_id=peanut_mat.id if peanut_mat else None,
            quantity=15.0,
            unit="Tons",
            storage_condition="Cool storage 4-6°C",
            status="PENDING",
            qc_status="PENDING_QC"
        )
        db.add(lot3)
        db.flush()

        s3 = QCSample(sample_code="SMP-DEMO-03", raw_material_lot_id=lot3.id, sample_date=now)
        db.add(s3)
        db.flush()
        db.add_all([
            QCTest(qc_sample_id=s3.id, parameter_name="Moisture Content", standard_spec="< 8.0%", measured_value="7.2%", is_pass=True),
            QCTest(qc_sample_id=s3.id, parameter_name="Aflatoxin B1", standard_spec="< 2.0 ppb", measured_value="4.5 ppb", is_pass=False),
            QCTest(qc_sample_id=s3.id, parameter_name="Purity Rate", standard_spec=">= 98.0%", measured_value="99.0%", is_pass=True),
            QCTest(qc_sample_id=s3.id, parameter_name="Oil Content", standard_spec=">= 48.0%", measured_value="49.5%", is_pass=True)
        ])

        coa3 = COADocument(
            raw_material_lot_id=lot3.id,
            supplier_id=sup.id,
            doc_number="COA-DEMO-REL-03",
            filename="COA_Peanut_Lot03_FailedAflatoxin.pdf",
            file_url="/static/docs/coa_peanut_demo03.pdf",
            lab_accreditation="ISO 17025 / VILAS 102",
            is_verified=False,
            issued_date=now
        )
        db.add(coa3)

        img3 = InspectionImage(
            raw_material_lot_id=lot3.id,
            image_url="/static/uploads/raw/20261017_064108_test_peanut.jpg",
            image_type="Peanut visual specimen"
        )
        db.add(img3)
        db.flush()

        ai3 = AIInspection(
            inspection_image_id=img3.id,
            raw_material_lot_id=lot3.id,
            model_version="YOLOv8-Peanut-v1",
            inference_time_ms=39.5,
            total_defects_count=0,
            summary="Camera visual scan clean, but COA aflatoxin lab test failed",
            avg_confidence=0.91,
            detected_material="Peanut"
        )
        db.add(ai3)

    # Demo Lot 4: COA Missing -> HOLD
    lot4 = db.query(RawMaterialLot).filter_by(lot_number="DEMO-LOT-REL-04").first()
    if not lot4:
        lot4 = RawMaterialLot(
            lot_number="DEMO-LOT-REL-04",
            material_name="Peanut",
            category="Oilseed",
            supplier_name=sup.name,
            supplier_id=sup.id,
            raw_material_id=peanut_mat.id if peanut_mat else None,
            quantity=18.0,
            unit="Tons",
            storage_condition="Cool storage 4-6°C",
            status="PENDING",
            qc_status="PENDING_QC"
        )
        db.add(lot4)
        db.flush()

        img4 = InspectionImage(
            raw_material_lot_id=lot4.id,
            image_url="/static/uploads/raw/20261017_055631_test_peanut.jpg",
            image_type="Peanut visual specimen"
        )
        db.add(img4)
        db.flush()

        ai4 = AIInspection(
            inspection_image_id=img4.id,
            raw_material_lot_id=lot4.id,
            model_version="YOLOv8-Peanut-v1",
            inference_time_ms=36.1,
            total_defects_count=0,
            summary="Camera visual scan clean; no Certificate of Analysis on file",
            avg_confidence=0.93,
            detected_material="Peanut"
        )
        db.add(ai4)

    db.commit()
    print("[Food Man] Demo lots seeded successfully:")
    print("  1. DEMO-LOT-REL-01 (Corn): COA Pass + AI Pass -> Expected: RELEASE")
    print("  2. DEMO-LOT-REL-02 (Corn): COA Pass + AI Reject -> Expected: HOLD")
    print("  3. DEMO-LOT-REL-03 (Peanut): COA Fail (Aflatoxin 4.5 ppb) -> Expected: REJECT")
    print("  4. DEMO-LOT-REL-04 (Peanut): COA Missing -> Expected: HOLD")


if __name__ == "__main__":
    seed_demo_release_lots()
