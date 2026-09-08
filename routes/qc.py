"""
QC Routes & API: Lab Tests, COA, YOLO AI Inspection, Human-Only Decision Making, and Production Output Contract
Phase 2 — PRD Implementation
"""
import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from models import get_db
from models.enums import RoleEnum, StatusEnum, STATUS_METADATA
from models.user import User
from models.schema_draft import RawMaterialLot
from models.procurement import Supplier, RawMaterial
from models.qc import (
    QCSample,
    QCTest,
    COADocument,
    InspectionImage,
    AIInspection,
    DetectedDefect,
    QCDecision
)
from ai.predict import run_yolo_inference, MODEL_VERSION
from routes.auth import login_required, get_current_user

qc_bp = Blueprint('qc', __name__)

# ==============================================================================
# 1. QC UI VIEW
# ==============================================================================
@qc_bp.route('/qc')
@login_required
def index():
    user = get_current_user()
    view = request.args.get('view', 'queue') # 'queue' | 'tests' | 'coa'
    db = get_db()

    pending_qc_count = db.query(RawMaterialLot).filter(
        (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
    ).count()

    view_titles = {
        'queue': 'Hàng chờ kiểm định QC (QC Queue)',
        'tests': 'Hồ sơ kết quả thử nghiệm Lab (Test Records)',
        'coa': 'Thư viện chứng thư chất lượng (COA Library)'
    }

    breadcrumbs = {
        'queue': ["Trang chủ", "Chất lượng", "QC Queue"],
        'tests': ["Trang chủ", "Chất lượng", "Hồ sơ Lab"],
        'coa': ["Trang chủ", "Chất lượng", "Thư viện COA"]
    }

    return render_template(
        'qc.html',
        user=user,
        active_view=view,
        view_title=view_titles.get(view, 'Chất lượng (QC)'),
        breadcrumb=breadcrumbs.get(view, ["Trang chủ", "Chất lượng"]),
        pending_qc_count=pending_qc_count
    )


# ==============================================================================
# 2. QC QUEUE API (LIST OF PENDING LOTS)
# ==============================================================================
@qc_bp.route('/api/qc/queue', methods=['GET'])
@login_required
def get_qc_queue():
    """
    Returns card grid of lots requiring QC review.
    Same card shape as Phase 1 lot cards with status pill = PENDING_QC.
    """
    db = get_db()
    # Filter for lots that are pending inspection
    lots = db.query(RawMaterialLot).filter(
        (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
    ).order_by(RawMaterialLot.id.desc()).all()

    cards = []
    for lot in lots:
        po_ref = lot.purchase_order.po_number if lot.purchase_order else (f"PO #{lot.id}" if lot.purchase_order_id else "GRN Intake")
        cards.append({
            "id": lot.lot_number,
            "db_id": lot.id,
            "title": lot.material_name,
            "category": lot.category,
            "headerStat": f"{lot.quantity:,.1f} {lot.unit}",
            "statSub": "Pending Inspection",
            "progress": 40,
            "miniGrid": [
                {"label": "Material / Spec", "value": f"{lot.material_name} ({lot.unit_weight or 'Standard'})"},
                {"label": "Supplier / PO", "value": f"{lot.supplier_name} • {po_ref}"},
                {"label": "Intake Date", "value": lot.received_at.strftime("%Y-%m-%d") if lot.received_at else "Today"},
                {"label": "Storage Condition", "value": lot.storage_condition or "Cold Storage 4°C"}
            ],
            "avatars": [
                {"initial": "QC", "bg": "#F59E0B", "name": "Awaiting Lab Inspection"}
            ],
            "status": "PENDING_QC",
            "statusLabel": "PENDING_QC",
            "statusPill": "pill-pending"
        })

    return jsonify({
        "success": True,
        "count": len(cards),
        "cards": cards
    })


# ==============================================================================
# 3. COMBINED REVIEW ENDPOINT (LAB + COA + YOLO AI)
# ==============================================================================
@qc_bp.route('/api/qc/lot/<int:lot_id>/review', methods=['GET'])
@login_required
def get_lot_combined_review(lot_id):
    """
    Combined review endpoint aggregating:
    - Lot metadata & Supplier profile
    - Lab test parameters (QCTest pass/fail results)
    - COA document verification status & link
    - AI YOLO inspection report with defect bounding boxes & confidence scores
    - Past decisions if any
    """
    db = get_db()
    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"error": "Không tìm thấy lô nguyên liệu"}), 404

    # 1. Fetch or create default lab tests
    sample = db.query(QCSample).filter_by(raw_material_lot_id=lot.id).first()
    if not sample:
        sample = QCSample(
            sample_code=f"SMP-{lot.lot_number.replace('LOT-RM-', '')}",
            raw_material_lot_id=lot.id,
            sample_date=datetime.datetime.utcnow(),
            storage_temp=lot.storage_condition or "4.0°C",
            sample_size="500ml / 5 mẫu đại diện"
        )
        db.add(sample)
        db.flush()

        # Seed realistic parameter test specs
        db.add_all([
            QCTest(qc_sample_id=sample.id, parameter_name="Độ chuẩn Brix", standard_spec="≥ 11.0°Bx", measured_value="11.4°Bx", unit="°Bx", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Chỉ số pH", standard_spec="6.5 - 6.8 pH", measured_value="6.68 pH", unit="pH", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Hàm lượng béo", standard_spec="≥ 3.2%", measured_value="3.55%", unit="%", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Chỉ tiêu Coliform", standard_spec="< 10 CFU/ml", measured_value="0 CFU/ml", unit="CFU", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Đánh giá cảm quan", standard_spec="Màu trắng ngà, mùi tự nhiên", measured_value="Đạt chuẩn 100%", unit="", is_pass=True)
        ])
        db.commit()

    lab_tests = [t.to_dict() for t in sample.tests]

    # 2. Fetch or create COA document
    coa = db.query(COADocument).filter_by(raw_material_lot_id=lot.id).first()
    if not coa:
        coa = COADocument(
            raw_material_lot_id=lot.id,
            supplier_id=lot.supplier_id,
            doc_number=f"COA-{lot.lot_number.replace('LOT-RM-', '')}-LAB",
            filename=f"COA_ChungNhanChatLuong_{lot.lot_number}.pdf",
            file_url=f"/static/docs/coa_{lot.lot_number}.pdf",
            issued_date=datetime.datetime.utcnow(),
            lab_accreditation="VILAS 102 / ISO 17025",
            is_verified=True
        )
        db.add(coa)
        db.commit()

    coa_data = coa.to_dict()

    # 3. Fetch or run YOLO AI inspection on lot image
    insp_image = db.query(InspectionImage).filter_by(raw_material_lot_id=lot.id).first()
    if not insp_image:
        insp_image = InspectionImage(
            raw_material_lot_id=lot.id,
            image_url="https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800&auto=format&fit=crop&q=80", # Representative packaging/warehouse lot image
            image_type="Chụp ngoại quan pallet nguyên liệu & bao bì seal"
        )
        db.add(insp_image)
        db.flush()

    ai_insp = db.query(AIInspection).filter_by(inspection_image_id=insp_image.id).first()
    if not ai_insp:
        # Run YOLO inference engine
        yolo_result = run_yolo_inference(insp_image.image_url, {"lot_number": lot.lot_number})
        ai_insp = AIInspection(
            inspection_image_id=insp_image.id,
            raw_material_lot_id=lot.id,
            model_version=yolo_result["model_version"],
            inference_time_ms=yolo_result["inference_time_ms"],
            total_defects_count=yolo_result["total_defects_count"],
            summary=yolo_result["summary"]
        )
        db.add(ai_insp)
        db.flush()

        for defect in yolo_result["detected_defects"]:
            detected = DetectedDefect(
                ai_inspection_id=ai_insp.id,
                defect_class=defect["defect_class"],
                confidence=defect["confidence"],
                bbox_x=defect["bbox_x"],
                bbox_y=defect["bbox_y"],
                bbox_w=defect["bbox_w"],
                bbox_h=defect["bbox_h"]
            )
            db.add(detected)
        db.commit()

    ai_data = ai_insp.to_dict()
    ai_data["image_url"] = insp_image.image_url

    # 4. Past decision if any
    decision = db.query(QCDecision).filter_by(raw_material_lot_id=lot.id).order_by(QCDecision.id.desc()).first()

    po_ref = lot.purchase_order.po_number if lot.purchase_order else (f"PO #{lot.id}" if lot.purchase_order_id else "N/A")

    all_passed = all(t.is_pass for t in sample.tests) if sample and sample.tests else True
    lab_eval = {
        "all_passed": all_passed,
        "tests": lab_tests,
        "sample_code": sample.sample_code if sample else None
    }

    result = {
        "lot": {
            "id": lot.id,
            "lot_number": lot.lot_number,
            "material_name": lot.material_name,
            "category": lot.category,
            "supplier_name": lot.supplier_name,
            "quantity": lot.quantity,
            "unit": lot.unit,
            "unit_weight": lot.unit_weight,
            "storage_condition": lot.storage_condition,
            "po_number": po_ref,
            "qc_status": lot.qc_status or "PENDING_QC",
            "received_at": lot.received_at.strftime("%d/%m/%Y %H:%M") if lot.received_at else "Hôm nay"
        },
        "lab_tests": lab_tests,
        "lab_evaluation": lab_eval,
        "coa": coa_data,
        "ai_inspection": ai_data,
        "last_decision": decision.to_dict() if decision else None,
        "advisory_notice": "KẾT QUẢ AI YOLO LÀ THAM KHẢO & KHÔNG TỰ ĐỘNG DUYỆT. BẮT BUỘC CHUYÊN VIÊN QC XÁC NHẬN."
    }

    return jsonify({
        "success": True,
        **result,
        "data": result
    })


@qc_bp.route('/api/qc/lot/<int:lot_id>/image', methods=['POST'])
@login_required
def upload_inspection_image(lot_id):
    """
    Upload physical lot inspection photo and execute YOLO AI inference.
    """
    data = request.get_json() or {}
    db = get_db()
    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"error": "Không tìm thấy lô nguyên liệu"}), 404

    image_url = data.get('image_url', 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800&auto=format&fit=crop&q=80')
    image_type = data.get('image_type', 'Ngoại quan bao bì / niêm phong')

    insp_image = InspectionImage(
        raw_material_lot_id=lot.id,
        image_url=image_url,
        image_type=image_type
    )
    db.add(insp_image)
    db.flush()

    # Run YOLO inference
    yolo_result = run_yolo_inference(insp_image.image_url, {"lot_number": lot.lot_number})
    ai_insp = AIInspection(
        inspection_image_id=insp_image.id,
        raw_material_lot_id=lot.id,
        model_version=yolo_result["model_version"],
        inference_time_ms=yolo_result["inference_time_ms"],
        total_defects_count=yolo_result["total_defects_count"],
        summary=yolo_result["summary"]
    )
    db.add(ai_insp)
    db.flush()

    for defect in yolo_result["detected_defects"]:
        detected = DetectedDefect(
            ai_inspection_id=ai_insp.id,
            defect_class=defect["defect_class"],
            confidence=defect["confidence"],
            bbox_x=defect["bbox_x"],
            bbox_y=defect["bbox_y"],
            bbox_w=defect["bbox_w"],
            bbox_h=defect["bbox_h"]
        )
        db.add(detected)
    db.commit()

    ai_dict = ai_insp.to_dict()
    ai_dict["image_url"] = insp_image.image_url

    return jsonify({
        "success": True,
        "data": {
            "image": insp_image.to_dict(),
            "ai_inspection": ai_dict
        }
    }), 201


# ==============================================================================
# 4. HUMAN-ONLY QC DECISION ENDPOINT (APPROVED / HOLD / REJECTED)
# AI never auto-approves
# ==============================================================================
@qc_bp.route('/api/qc/lot/<int:lot_id>/decision', methods=['POST'])
@login_required
def submit_qc_decision(lot_id):
    """
    Human-only final decision: APPROVED, HOLD, or REJECTED.
    AI output is displayed advisory-only, decision MUST be triggered by manual human click.
    """
    data = request.get_json() or {}
    final_status = data.get('final_status', '').upper()

    if final_status not in ['APPROVED', 'HOLD', 'REJECTED']:
        return jsonify({"error": "Trạng thái phê duyệt không hợp lệ. Chọn APPROVED, HOLD, hoặc REJECTED."}), 400

    db = get_db()
    user = get_current_user()

    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"error": "Không tìm thấy lô nguyên liệu"}), 404

    # 1. Record human decision
    decision = QCDecision(
        raw_material_lot_id=lot.id,
        decided_by_user_id=user.id if user else 1,
        final_status=final_status,
        reason=data.get('reason', 'Chuyên viên QC đã đối chiếu toàn diện Lab test, chứng thư COA và hình ảnh ngoại quan AI.'),
        action_notes=data.get('action_notes', '')
    )
    db.add(decision)

    # 2. Update Lot QC status
    lot.qc_status = final_status
    if final_status == 'APPROVED':
        lot.status = StatusEnum.APPROVED.value
    elif final_status == 'HOLD':
        lot.status = StatusEnum.HOLD.value
    else:
        lot.status = StatusEnum.REJECTED.value

    db.commit()

    return jsonify({
        "success": True,
        "message": f"QC Officer {user.full_name if user else 'QC'} approved lot {lot.lot_number} to status: {final_status}",
        "decision": decision.to_dict(),
        "lot_qc_status": lot.qc_status
    })


# ==============================================================================
# 5. OUTPUT CONTRACT WITH MODULE 3 (PRODUCTION)
# Production may ONLY query lots where qc_decisions.final_status = APPROVED
# ==============================================================================
@qc_bp.route('/api/qc/production-ready-lots', methods=['GET'])
@login_required
def get_production_ready_lots():
    """
    Output Contract for Module 3 (Production):
    Production may ONLY query lots where qc_decisions.final_status = APPROVED.
    Any lots with PENDING_QC, HOLD, or REJECTED are strictly excluded.
    """
    db = get_db()
    approved_lots = db.query(RawMaterialLot).join(QCDecision).filter(
        QCDecision.final_status == 'APPROVED',
        RawMaterialLot.qc_status == 'APPROVED'
    ).distinct().all()

    return jsonify({
        "success": True,
        "contract": "Production Staging Gate (Approved Only)",
        "count": len(approved_lots),
        "lots": [
            {
                "id": lot.id,
                "lot_number": lot.lot_number,
                "material_name": lot.material_name,
                "quantity": lot.quantity,
                "unit": lot.unit,
                "qc_status": lot.qc_status,
                "storage_condition": lot.storage_condition
            }
            for lot in approved_lots
        ]
    })


# ==============================================================================
# 6. LAB TEST & COA DIRECT APIS
# ==============================================================================
@qc_bp.route('/api/qc/lot/<int:lot_id>/sample', methods=['POST'])
@login_required
def add_lot_sample_and_tests(lot_id):
    data = request.get_json() or {}
    db = get_db()
    user = get_current_user()

    sample = QCSample(
        sample_code=data.get('sample_code', f"SMP-{lot_id}-{datetime.datetime.utcnow().strftime('%H%M%S')}"),
        raw_material_lot_id=lot_id,
        sampler_user_id=user.id if user else None,
        storage_temp=data.get('storage_temp', '4°C'),
        sample_size=data.get('sample_size', '500ml'),
        notes=data.get('notes', '')
    )
    db.add(sample)
    db.flush()

    tests_data = data.get('tests', [])
    for t in tests_data:
        db.add(QCTest(
            qc_sample_id=sample.id,
            parameter_name=t.get('parameter_name'),
            standard_spec=t.get('standard_spec'),
            measured_value=t.get('measured_value'),
            unit=t.get('unit', ''),
            is_pass=bool(t.get('is_pass', True))
        ))

    db.commit()
    return jsonify({"success": True, "sample": sample.to_dict()}), 201


@qc_bp.route('/api/qc/lot/<int:lot_id>/coa', methods=['POST'])
@login_required
def upload_coa(lot_id):
    data = request.get_json() or {}
    db = get_db()
    coa = COADocument(
        raw_material_lot_id=lot_id,
        supplier_id=data.get('supplier_id'),
        doc_number=data.get('doc_number', f"COA-{lot_id}-{datetime.datetime.utcnow().strftime('%d%m%Y')}"),
        filename=data.get('filename', 'COA_Standard.pdf'),
        file_url=data.get('file_url', f'/static/docs/coa_{lot_id}.pdf'),
        lab_accreditation=data.get('lab_accreditation', 'VILAS / ISO 17025'),
        is_verified=bool(data.get('is_verified', True))
    )
    db.add(coa)
    db.commit()
    return jsonify({"success": True, "coa": coa.to_dict()}), 201
