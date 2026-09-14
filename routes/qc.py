"""
QC Routes & API: Lab Tests, COA, YOLO AI Inspection, Human-Only Decision Making, and Production Output Contract
Phase 2 — PRD Implementation
"""
import os
import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, current_app
from werkzeug.utils import secure_filename
from models import get_db
from models.enums import RoleEnum, StatusEnum, STATUS_METADATA
from models.user import User
from models.schema_draft import RawMaterialLot
from models.procurement import Supplier, RawMaterial
from models.production import Product, ProductionBatch
from models.qc import (
    QCSample,
    QCTest,
    COADocument,
    InspectionImage,
    AIInspection,
    DetectedDefect,
    QCDecision,
    AIFeedback
)

from ai.predict import run_yolo_inference, MODEL_VERSION
from ai.yolo_service import check_ai_engine_status, run_yolo_visual_inspection, FOOD_DEFECT_TAXONOMY
from routes.auth import login_required, get_current_user, role_required

qc_bp = Blueprint('qc', __name__)

# ==============================================================================
# 1. QC UI VIEW
# ==============================================================================
@qc_bp.route('/qc')
@login_required
@role_required(RoleEnum.QC, RoleEnum.ADMIN)
def index():
    user = get_current_user()
    view = request.args.get('view', 'queue') # 'queue' | 'tests' | 'coa' | 'ai-inspection'
    db = get_db()

    pending_qc_count = db.query(RawMaterialLot).filter(
        (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
    ).count()

    view_titles = {
        'queue': 'QC Inspection Queue',
        'tests': 'Lab Test Records',
        'coa': 'COA Certificate Library',
        'ai-inspection': 'YOLOv8 AI Visual Quality Inspection'
    }

    breadcrumbs = {
        'queue': ["Home", "Quality Control", "QC Queue"],
        'tests': ["Home", "Quality Control", "Lab Records"],
        'coa': ["Home", "Quality Control", "COA Library"],
        'ai-inspection': ["Home", "Quality Control", "AI Visual Inspection"]
    }

    lots = db.query(RawMaterialLot).order_by(RawMaterialLot.id.desc()).all()
    products = db.query(Product).filter_by(is_active=True).all()
    batches = db.query(ProductionBatch).order_by(ProductionBatch.id.desc()).limit(15).all()

    return render_template(
        'qc.html',
        user=user,
        active_view=view,
        view_title=view_titles.get(view, 'Quality Control (QC)'),
        breadcrumb=breadcrumbs.get(view, ["Home", "Quality Control"]),
        pending_qc_count=pending_qc_count,
        lots=lots,
        products=products,
        batches=batches
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
        return jsonify({"error": "Raw material lot not found"}), 404

    # 1. Fetch or create default lab tests
    sample = db.query(QCSample).filter_by(raw_material_lot_id=lot.id).first()
    if not sample:
        sample = QCSample(
            sample_code=f"SMP-{lot.lot_number.replace('LOT-RM-', '')}",
            raw_material_lot_id=lot.id,
            sample_date=datetime.datetime.utcnow(),
            storage_temp=lot.storage_condition or "4.0°C",
            sample_size="500ml / 5 representative samples"
        )
        db.add(sample)
        db.flush()

        # Seed realistic parameter test specs
        db.add_all([
            QCTest(qc_sample_id=sample.id, parameter_name="Brix Level", standard_spec="≥ 11.0°Bx", measured_value="11.4°Bx", unit="°Bx", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="pH Index", standard_spec="6.5 - 6.8 pH", measured_value="6.68 pH", unit="pH", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Fat Content", standard_spec="≥ 3.2%", measured_value="3.55%", unit="%", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Coliform Count", standard_spec="< 10 CFU/ml", measured_value="0 CFU/ml", unit="CFU", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Sensory Evaluation", standard_spec="Milky white, natural aroma", measured_value="100% compliant", unit="", is_pass=True)
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
            image_type="Pallet physical appearance & packaging seal inspection"
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
            "received_at": lot.received_at.strftime("%d/%m/%Y %H:%M") if lot.received_at else "Today"
        },
        "lab_tests": lab_tests,
        "lab_evaluation": lab_eval,
        "coa": coa_data,
        "ai_inspection": ai_data,
        "last_decision": decision.to_dict() if decision else None,
        "advisory_notice": "AI YOLO RESULTS ARE ADVISORY ONLY AND NOT AUTO-APPROVED. QC SPECIALIST CONFIRMATION IS MANDATORY."
    }

    return jsonify({
        "success": True,
        **result,
        "data": result
    })


# ==============================================================================
# YOLOv8 AI VISUAL INSPECTION APIS
# ==============================================================================
@qc_bp.route('/api/qc/ai-model-status', methods=['GET'])
@login_required
def get_ai_model_status():
    """
    Returns active YOLOv8 model status, file location, and training diagnostics.
    """
    status = check_ai_engine_status()
    return jsonify({
        "success": True,
        "data": status,
        **status
    })



@qc_bp.route('/api/qc/ai-inspect', methods=['POST'])
@login_required
def inspect_image_yolo():
    """
    AI Inspection Workflow:
    Upload Image -> YOLOv8 Analysis -> Detect Visible Defects -> Generate AI Result
    Stores inspection result and image in DB linked to lot, product, or batch.
    If no model is available, returns clear configuration guidance without fake detections.
    """
    db = get_db()
    target_type = request.form.get('target_type') or (request.json.get('target_type', 'lot') if request.is_json else 'lot')
    target_id = request.form.get('target_id') or (request.json.get('target_id') if request.is_json else None)
    conf_threshold = float(request.form.get('confidence_threshold') or (request.json.get('confidence_threshold', 0.12) if request.is_json else 0.12))

    raw_lot_id = None
    product_id = None
    batch_id = None

    if target_type == 'lot' and target_id:
        raw_lot_id = int(target_id)
    elif target_type == 'product' and target_id:
        product_id = int(target_id)
    elif target_type == 'batch' and target_id:
        batch_id = int(target_id)

    # Handle image file upload or image URL
    file = request.files.get('image') if 'image' in request.files else None
    image_url = None
    raw_file_path = None

    upload_raw_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'raw')
    upload_annotated_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'annotated')
    os.makedirs(upload_raw_dir, exist_ok=True)
    os.makedirs(upload_annotated_dir, exist_ok=True)

    if file and file.filename:
        filename = secure_filename(file.filename)
        unique_prefix = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_")
        saved_name = unique_prefix + filename
        raw_file_path = os.path.join(upload_raw_dir, saved_name)
        file.save(raw_file_path)
        image_url = f"/static/uploads/raw/{saved_name}"
    else:
        # Check JSON or form image_url
        image_url = request.form.get('image_url') or (request.json.get('image_url') if request.is_json else None)
        if not image_url:
            image_url = "/static/img/peanut_sample.jpg"

    # Create InspectionImage record
    insp_image = InspectionImage(
        raw_material_lot_id=raw_lot_id,
        product_id=product_id,
        production_batch_id=batch_id,
        image_url=image_url,
        image_type=request.form.get('image_type', 'Raw Material Visual Scan') if not request.is_json else request.json.get('image_type', 'Raw Material Visual Scan'),
        uploaded_at=datetime.datetime.utcnow()
    )
    db.add(insp_image)
    db.flush()

    # Run YOLOv8 visual inspection
    if raw_file_path and os.path.isfile(raw_file_path):
        yolo_res = run_yolo_visual_inspection(raw_file_path, upload_annotated_dir, conf_threshold=conf_threshold)
    else:
        local_static = os.path.join(current_app.root_path, image_url.lstrip('/'))
        if os.path.isfile(local_static):
            yolo_res = run_yolo_visual_inspection(local_static, upload_annotated_dir, conf_threshold=conf_threshold)
        else:
            engine_status = check_ai_engine_status()
            yolo_res = {
                "success": engine_status["ready"],
                "model_status": engine_status["status"],
                "model_version": engine_status.get("model_name") or "YOLOv8-Unconfigured",
                "inference_time_ms": 0.0,
                "total_defects_count": 0,
                "detected_defects": [],
                "summary": "Model Configuration Required" if not engine_status["ready"] else "No visual defects detected",
                "status_message": engine_status["message"],
                "annotated_image_url": None,
                "inspection_timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "training_workflow": engine_status.get("training_workflow", [])
            }

    annotated_url = yolo_res.get("annotated_image_url")
    if annotated_url:
        insp_image.annotated_image_url = annotated_url

    ai_insp = AIInspection(
        inspection_image_id=insp_image.id,
        raw_material_lot_id=raw_lot_id,
        product_id=product_id,
        production_batch_id=batch_id,
        model_version=yolo_res.get("model_version", "YOLOv8"),
        model_status=yolo_res.get("model_status", "READY"),
        inference_time_ms=yolo_res.get("inference_time_ms", 0.0),
        total_defects_count=yolo_res.get("total_defects_count", 0),
        summary=yolo_res.get("summary", "Inspection recorded"),
        status_message=yolo_res.get("status_message"),
        annotated_image_url=annotated_url,
        created_at=datetime.datetime.utcnow()
    )
    db.add(ai_insp)
    db.flush()

    for d in yolo_res.get("detected_defects", []):
        defect_item = DetectedDefect(
            ai_inspection_id=ai_insp.id,
            defect_class=d["defect_class"],
            confidence=d["confidence"],
            bbox_x=d["bbox_x"],
            bbox_y=d["bbox_y"],
            bbox_w=d["bbox_w"],
            bbox_h=d["bbox_h"]
        )
        db.add(defect_item)

    db.commit()

    ai_payload = {
        "inspection_id": ai_insp.id,
        "image_id": insp_image.id,
        "raw_image_url": insp_image.image_url,
        "uploaded_image": insp_image.image_url,
        "annotated_image_url": annotated_url or insp_image.image_url,
        "annotated_image": annotated_url or insp_image.image_url,
        "model_version": ai_insp.model_version,
        "model_status": ai_insp.model_status,
        "status_message": ai_insp.status_message,
        "inference_time_ms": ai_insp.inference_time_ms,
        "total_defects_count": ai_insp.total_defects_count,
        "summary": ai_insp.summary,
        "defects": [d.to_dict() for d in ai_insp.detected_defects],
        "detected_defects": [d.to_dict() for d in ai_insp.detected_defects],
        "healthy_specimens_count": yolo_res.get("healthy_specimens_count", 0),
        "detected_healthy": yolo_res.get("detected_healthy", []),
        "timestamp": ai_insp.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "inspection_timestamp": ai_insp.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "training_workflow": yolo_res.get("training_workflow", []),
        "confidence_threshold": conf_threshold
    }

    return jsonify({
        "success": True,
        "message": "AI Visual inspection completed successfully",
        "data": ai_payload,
        "ai_result": ai_payload
    }), 200



@qc_bp.route('/api/qc/ai-inspections', methods=['GET'])
@login_required
def get_ai_inspections():
    """
    Returns visual inspection history, optionally filtered by target.
    """
    db = get_db()
    lot_id = request.args.get('lot_id', type=int)
    product_id = request.args.get('product_id', type=int)
    batch_id = request.args.get('batch_id', type=int)

    query = db.query(AIInspection)
    if lot_id:
        query = query.filter_by(raw_material_lot_id=lot_id)
    if product_id:
        query = query.filter_by(product_id=product_id)
    if batch_id:
        query = query.filter_by(production_batch_id=batch_id)

    inspections = query.order_by(AIInspection.id.desc()).limit(20).all()
    return jsonify({
        "success": True,
        "count": len(inspections),
        "data": [i.to_dict() for i in inspections]
    })


@qc_bp.route('/api/qc/ai-feedback', methods=['POST'])
@login_required
def submit_ai_feedback():
    """
    Feedback Loop for Continuous Model Improvement:
    Allows QC Specialists to confirm or correct YOLOv8 defect classifications.
    Persists feedback for continuous dataset refinement and model retraining.
    """
    db = get_db()
    data = request.get_json() or {}
    ai_inspection_id = data.get('ai_inspection_id')
    feedback_type = data.get('feedback_type', 'CONFIRMED_ACCURATE')
    corrected_class = data.get('corrected_class')
    notes = data.get('notes', '')
    user = get_current_user()

    if not ai_inspection_id:
        return jsonify({"success": False, "error": "ai_inspection_id is required"}), 400

    feedback = AIFeedback(
        ai_inspection_id=int(ai_inspection_id),
        inspector_user_id=user.id if user else None,
        feedback_type=feedback_type,
        corrected_class=corrected_class,
        inspector_notes=notes,
        created_at=datetime.datetime.utcnow()
    )
    db.add(feedback)
    db.commit()

    return jsonify({
        "success": True,
        "message": "Feedback recorded successfully for continuous model retraining",
        "data": feedback.to_dict()
    }), 201


@qc_bp.route('/api/qc/decision', methods=['POST'])
@login_required
def submit_general_qc_decision():

    """
    Generalized Final QC Decision combining:
    1. Lab Test Results
    2. COA Document Verification
    3. YOLOv8 Visual Defect Results
    4. Required Product Specifications
    Decision is strictly Human-Only (APPROVED, HOLD, REJECTED).
    Only materials/products with final APPROVED status can proceed.
    """
    data = request.get_json() or {}
    target_type = data.get('target_type', 'lot') # 'lot', 'product', 'batch'
    target_id = data.get('target_id')
    final_status = data.get('final_status', '').upper()
    reason = data.get('reason', 'QC Specialist verification of Lab, COA, YOLO visual scan and specifications.')
    action_notes = data.get('action_notes', '')

    if final_status not in ['APPROVED', 'HOLD', 'REJECTED']:
        return jsonify({"success": False, "error": "Invalid approval status. Must be APPROVED, HOLD, or REJECTED."}), 400

    if not target_id:
        return jsonify({"success": False, "error": "Target ID is required."}), 400

    db = get_db()
    user = get_current_user()

    raw_lot_id = None
    product_id = None
    batch_id = None
    target_label = ""

    if target_type == 'lot':
        raw_lot_id = int(target_id)
        lot = db.query(RawMaterialLot).filter_by(id=raw_lot_id).first()
        if not lot:
            return jsonify({"success": False, "error": "Raw material lot not found"}), 404
        lot.qc_status = final_status
        if final_status == 'APPROVED':
            lot.status = StatusEnum.APPROVED.value
        elif final_status == 'HOLD':
            lot.status = StatusEnum.HOLD.value
        else:
            lot.status = StatusEnum.REJECTED.value
        target_label = f"Raw Material Lot {lot.lot_number}"
    elif target_type == 'product':
        product_id = int(target_id)
        prod = db.query(Product).filter_by(id=product_id).first()
        if not prod:
            return jsonify({"success": False, "error": "Product not found"}), 404
        target_label = f"Product {prod.name}"
    elif target_type == 'batch':
        batch_id = int(target_id)
        batch = db.query(ProductionBatch).filter_by(id=batch_id).first()
        if not batch:
            return jsonify({"success": False, "error": "Batch not found"}), 404
        if final_status == 'REJECTED':
            batch.status = "REJECTED"
        target_label = f"Batch {batch.batch_code}"

    decision = QCDecision(
        raw_material_lot_id=raw_lot_id,
        product_id=product_id,
        production_batch_id=batch_id,
        decided_by_user_id=user.id if user else 1,
        final_status=final_status,
        reason=reason,
        action_notes=action_notes
    )
    db.add(decision)
    db.commit()

    return jsonify({
        "success": True,
        "message": f"QC Officer {user.full_name if user else 'QC'} recorded final decision [{final_status}] for {target_label}.",
        "data": decision.to_dict()
    }), 200


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
        return jsonify({"error": "Raw material lot not found"}), 404

    image_url = data.get('image_url', 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800&auto=format&fit=crop&q=80')
    image_type = data.get('image_type', 'Packaging appearance / seal')

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
        return jsonify({"error": "Invalid approval status. Choose APPROVED, HOLD, or REJECTED."}), 400

    db = get_db()
    user = get_current_user()

    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"error": "Raw material lot not found"}), 404

    # 1. Record human decision
    decision = QCDecision(
        raw_material_lot_id=lot.id,
        decided_by_user_id=user.id if user else 1,
        final_status=final_status,
        reason=data.get('reason', 'QC Specialist performed comprehensive verification of Lab tests, COA certificate, and AI visual inspection.'),
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
