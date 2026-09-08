"""
Production & Packaging Routes
PRD Phase 3
"""
import datetime
from flask import Blueprint, render_template, request, jsonify, session
from models import get_db
from models.user import User
from models.procurement import RawMaterial, RawMaterialLot
from models.qc import QCDecision
from models.production import (
    Product,
    Recipe,
    RecipeMaterial,
    ProductionBatch,
    BatchRawMaterial,
    ProductionProcessRecord,
    PackagingMaterial,
    PackagingRecord
)
from routes.auth import login_required, role_required

production_bp = Blueprint('production', __name__)

STANDARD_STAGES = [
    {"order": 1, "name": "Chuẩn bị nguyên liệu (Material Prep)", "param": "Nhiệt độ silo: 3.8°C, Kiểm tra seal"},
    {"order": 2, "name": "Phối trộn & Đồng hóa (Mixing & Homogenization)", "param": "Áp suất đồng hóa: 200 bar, Độ mịn đạt"},
    {"order": 3, "name": "Tiệt trùng nhiệt UHT (UHT Pasteurization)", "param": "Nhiệt độ: 138.5°C, Thời gian giữ nhiệt: 4s"},
    {"order": 4, "name": "Chiết rót vô trùng (Aseptic Filling)", "param": "Buồng chiết Class 100, Áp suất dương"},
    {"order": 5, "name": "Đóng gói & Hoàn thiện (Packaging & Palletizing)", "param": "Đóng thùng 24 hộp, Bọc màng PE tự động"}
]

@production_bp.route('/production')
@login_required
@role_required('Production', 'Admin')
def index():
    view = request.args.get('view', 'batches')
    user = session.get('user')
    permitted_modules = session.get('user_modules', ['production'])
    return render_template(
        'production.html',
        active_view=view,
        current_module='production',
        user=user,
        permitted_modules=permitted_modules
    )

# -----------------------------------------------------------------------------
# REST APIs
# -----------------------------------------------------------------------------

@production_bp.route('/api/production/recommendations', methods=['GET'])
@login_required
def get_recommendations():
    """
    Availability Check & Rule-Based Recommendation:
    Queries Member 2's approved lots vs recipe BOM requirements.
    Determines readiness pill: PRODUCEABLE (green) vs LACKING_MATERIALS (red).
    """
    db = get_db()
    products = db.query(Product).filter_by(is_active=True).all()
    
    # Query ONLY lots approved by QC (PRD §13 contract)
    approved_lots = db.query(RawMaterialLot).filter(
        RawMaterialLot.qc_status == 'APPROVED',
        RawMaterialLot.quantity > 0
    ).all()

    # Aggregate total approved quantity per raw_material_id
    approved_stock_by_rm = {}
    for lot in approved_lots:
        rm_id = lot.raw_material_id
        if rm_id:
            approved_stock_by_rm[rm_id] = approved_stock_by_rm.get(rm_id, 0.0) + lot.quantity

    recommendations = []
    for prod in products:
        recipe = prod.active_recipe
        if not recipe or not recipe.materials:
            continue

        can_produce = True
        missing_materials = []
        bom_status_list = []

        for bom in recipe.materials:
            available_qty = approved_stock_by_rm.get(bom.raw_material_id, 0.0)
            is_sufficient = available_qty >= bom.required_quantity
            if not is_sufficient:
                can_produce = False
                missing_materials.append({
                    "material_name": bom.raw_material.name if bom.raw_material else "N/A",
                    "required": bom.required_quantity,
                    "available": available_qty,
                    "shortage": round(bom.required_quantity - available_qty, 2),
                    "unit": bom.unit
                })

            bom_status_list.append({
                "raw_material_id": bom.raw_material_id,
                "material_name": bom.raw_material.name if bom.raw_material else "N/A",
                "required_quantity": bom.required_quantity,
                "available_approved_quantity": available_qty,
                "unit": bom.unit,
                "status": "SUFFICIENT" if is_sufficient else "DEFICIENT"
            })

        max_batches_possible = 9999
        for bom in recipe.materials:
            avail = approved_stock_by_rm.get(bom.raw_material_id, 0.0)
            if bom.required_quantity > 0:
                possible = int(avail / bom.required_quantity)
                if possible < max_batches_possible:
                    max_batches_possible = possible
        if max_batches_possible == 9999 or not can_produce:
            max_batches_possible = 0

        recommendations.append({
            "product_id": prod.id,
            "product_code": prod.code,
            "product_name": prod.name,
            "category": prod.category,
            "recipe_code": recipe.recipe_code,
            "standard_yield": recipe.standard_batch_yield,
            "yield_unit": recipe.yield_unit,
            "readiness": "PRODUCEABLE" if can_produce else "LACKING_MATERIALS",
            "readiness_pill_class": "pill-green" if can_produce else "pill-red",
            "readiness_label": "Sẵn sàng sản xuất" if can_produce else "Thiếu nguyên liệu",
            "max_batches_possible": max_batches_possible,
            "missing_materials": missing_materials,
            "bom_items": bom_status_list
        })

    return jsonify({
        "success": True,
        "count": len(recommendations),
        "data": recommendations
    })


@production_bp.route('/api/production/batches', methods=['GET'])
@login_required
def get_batches():
    """
    Returns card grid data for production batches.
    Mirrors the reference's vehicle cards:
    header (batch# + qty/target as stat), stage progress bar, avatar stack, status pill.
    """
    db = get_db()
    batches = db.query(ProductionBatch).order_by(ProductionBatch.id.desc()).all()
    return jsonify({
        "success": True,
        "count": len(batches),
        "data": [b.to_dict() for b in batches]
    })


@production_bp.route('/api/production/batches/<int:batch_id>', methods=['GET'])
@login_required
def get_batch_detail(batch_id):
    """
    Returns batch detail for the right-hand slide-in drawer:
    stage timeline/stepper, packaging records, consumed lots list.
    """
    db = get_db()
    batch = db.query(ProductionBatch).filter_by(id=batch_id).first()
    if not batch:
        return jsonify({"success": False, "error": "Batch not found"}), 404
    return jsonify({
        "success": True,
        "data": batch.to_dict()
    })


@production_bp.route('/api/production/batches', methods=['POST'])
@login_required
def create_batch():
    """
    Batch creation wizard:
    Pick product -> allocate approved lots -> confirm.
    Enforces that allocated lots MUST be strictly APPROVED by QC.
    """
    db = get_db()
    payload = request.get_json() or {}
    product_id = payload.get('product_id')
    custom_target = payload.get('target_quantity')
    line_name = payload.get('line_name', 'Line A1 - Tetra Pak 250ml')
    user_id = session.get('user', {}).get('id')

    product = db.query(Product).filter_by(id=product_id).first()
    if not product:
        return jsonify({"success": False, "error": "Vui lòng chọn sản phẩm hợp lệ"}), 400

    recipe = product.active_recipe
    if not recipe:
        return jsonify({"success": False, "error": "Sản phẩm chưa có công thức sản xuất khả dụng"}), 400

    target_quantity = float(custom_target) if custom_target else recipe.standard_batch_yield

    # Check approved lots for BOM materials
    allocated_lots = []
    for bom in recipe.materials:
        needed_qty = bom.required_quantity * (target_quantity / recipe.standard_batch_yield)
        approved_lots = db.query(RawMaterialLot).filter(
            RawMaterialLot.raw_material_id == bom.raw_material_id,
            RawMaterialLot.qc_status == 'APPROVED',
            RawMaterialLot.quantity > 0
        ).order_by(RawMaterialLot.id.asc()).all()

        total_avail = sum(l.quantity for l in approved_lots)
        if total_avail < needed_qty:
            return jsonify({
                "success": False,
                "error": f"Không đủ nguyên liệu đạt chuẩn QC: {bom.raw_material.name} (Cần {needed_qty} {bom.unit}, có {total_avail} {bom.unit})"
            }), 400

        # Allocate specific approved lots
        remaining = needed_qty
        for lot in approved_lots:
            if remaining <= 0:
                break
            consume = min(lot.quantity, remaining)
            allocated_lots.append({
                "lot": lot,
                "quantity": consume,
                "unit": bom.unit
            })
            remaining -= consume

    # Generate batch code
    count = db.query(ProductionBatch).count() + 1
    batch_code = f"LOT-2026-{count:03d}"

    mfg_date = datetime.datetime.utcnow()
    shelf_life = product.shelf_life_days or 180
    expiry_date = mfg_date + datetime.timedelta(days=shelf_life)

    # Create batch
    new_batch = ProductionBatch(
        batch_code=batch_code,
        product_id=product.id,
        recipe_id=recipe.id,
        product_name=product.name,
        line_name=line_name,
        target_quantity=target_quantity,
        actual_quantity=0.0,
        unit=recipe.yield_unit,
        temperature_spec="138.5°C / 4s UHT" if "Sữa" in product.name else "85.0°C / 15s Pasteurize",
        status="IN_PROGRESS",
        current_stage="Chuẩn bị nguyên liệu (Material Prep)",
        stage_progress_percent=20,
        shift_manager_id=user_id,
        started_at=datetime.datetime.utcnow(),
        mfg_date=mfg_date,
        expiry_date=expiry_date,
        notes=payload.get('notes', 'Mẻ sản xuất khởi tạo qua Production Wizard')
    )
    db.add(new_batch)
    db.flush()

    # Record consumed lots and decrement lot quantities
    for alloc in allocated_lots:
        lot = alloc["lot"]
        consumed_qty = alloc["quantity"]
        brm = BatchRawMaterial(
            production_batch_id=new_batch.id,
            raw_material_lot_id=lot.id,
            quantity_consumed=consumed_qty,
            unit=alloc["unit"],
            recorded_at=datetime.datetime.utcnow()
        )
        db.add(brm)
        lot.quantity = max(0.0, lot.quantity - consumed_qty)

    # Initialize the 5 standard process stages
    now = datetime.datetime.utcnow()
    for idx, stg in enumerate(STANDARD_STAGES):
        is_first = (idx == 0)
        proc_record = ProductionProcessRecord(
            production_batch_id=new_batch.id,
            stage_name=stg["name"],
            stage_order=stg["order"],
            status="IN_PROGRESS" if is_first else "PENDING",
            started_at=now if is_first else None,
            parameters_log=stg["param"],
            operator_id=user_id
        )
        db.add(proc_record)

    db.commit()

    return jsonify({
        "success": True,
        "message": f"Khởi tạo thành công mẻ sản xuất {batch_code}",
        "data": new_batch.to_dict()
    }), 201


@production_bp.route('/api/production/batches/<int:batch_id>/advance-stage', methods=['POST'])
@login_required
def advance_stage(batch_id):
    """
    Advance batch to next stage in the timeline stepper.
    Records stage end timestamp and next stage start timestamp.
    """
    db = get_db()
    batch = db.query(ProductionBatch).filter_by(id=batch_id).first()
    if not batch:
        return jsonify({"success": False, "error": "Batch not found"}), 404

    now = datetime.datetime.utcnow()
    stages = sorted(batch.process_records, key=lambda s: s.stage_order)
    current_idx = -1

    for idx, s in enumerate(stages):
        if s.status == "IN_PROGRESS":
            current_idx = idx
            break

    if current_idx == -1:
        # If all completed or none in progress, find first pending
        for idx, s in enumerate(stages):
            if s.status == "PENDING":
                current_idx = idx
                s.status = "IN_PROGRESS"
                s.started_at = now
                break

    if current_idx != -1:
        # Complete current stage
        curr = stages[current_idx]
        curr.status = "COMPLETED"
        curr.ended_at = now
        
        # Advance to next stage if available
        if current_idx + 1 < len(stages):
            next_stage = stages[current_idx + 1]
            next_stage.status = "IN_PROGRESS"
            next_stage.started_at = now
            batch.current_stage = next_stage.stage_name
            batch.stage_progress_percent = int((current_idx + 2) / len(stages) * 100)
        else:
            # All stages completed
            batch.current_stage = "Hoàn tất các công đoạn (Chờ đóng gói & nhập kho)"
            batch.stage_progress_percent = 100

    db.commit()
    return jsonify({
        "success": True,
        "message": "Đã ghi nhận mốc thời gian hoàn tất công đoạn",
        "data": batch.to_dict()
    })


@production_bp.route('/api/production/batches/<int:batch_id>/packaging', methods=['POST'])
@login_required
def record_packaging(batch_id):
    """
    Record packaging materials consumed and certify batch completion.
    Completes batch and sets actual_quantity.
    """
    db = get_db()
    batch = db.query(ProductionBatch).filter_by(id=batch_id).first()
    if not batch:
        return jsonify({"success": False, "error": "Batch not found"}), 404

    payload = request.get_json() or {}
    cartons = int(payload.get('carton_boxes_used', batch.target_quantity or 5000))
    seal_rolls = float(payload.get('packaging_seal_rolls_used', 2.5))
    completed_pkgs = int(payload.get('packages_completed', cartons))
    waste_count = int(payload.get('waste_count', 12))
    user_id = session.get('user', {}).get('id')

    # Add or update packaging record
    pkg_record = db.query(PackagingRecord).filter_by(production_batch_id=batch.id).first()
    if not pkg_record:
        pkg_record = PackagingRecord(
            production_batch_id=batch.id,
            carton_boxes_used=cartons,
            packaging_seal_rolls_used=seal_rolls,
            packages_completed=completed_pkgs,
            waste_count=waste_count,
            inspected_by_user_id=user_id,
            recorded_at=datetime.datetime.utcnow(),
            notes=payload.get('notes', 'Đóng gói đạt tiêu chuẩn ISO 22000')
        )
        db.add(pkg_record)
    else:
        pkg_record.carton_boxes_used = cartons
        pkg_record.packaging_seal_rolls_used = seal_rolls
        pkg_record.packages_completed = completed_pkgs
        pkg_record.waste_count = waste_count
        pkg_record.inspected_by_user_id = user_id
        pkg_record.recorded_at = datetime.datetime.utcnow()

    # Mark batch COMPLETE
    batch.actual_quantity = completed_pkgs
    batch.status = "COMPLETE"
    batch.current_stage = "Hoàn tất đóng gói & Kiểm nghiệm thành phẩm"
    batch.stage_progress_percent = 100
    batch.completed_at = datetime.datetime.utcnow()

    # Complete all process stages
    for s in batch.process_records:
        if s.status != "COMPLETED":
            s.status = "COMPLETED"
            if not s.started_at:
                s.started_at = datetime.datetime.utcnow()
            s.ended_at = datetime.datetime.utcnow()

    db.commit()

    return jsonify({
        "success": True,
        "message": f"Ghi nhận đóng gói thành công cho lô {batch.batch_code}. Lô đã chuyển trạng thái COMPLETE.",
        "data": batch.to_dict()
    })


@production_bp.route('/api/production/completed-batches', methods=['GET'])
@login_required
def get_completed_batches():
    """
    Output contract for Module 4 (Warehouse):
    Delivers batches ready for warehouse inventory ingestion:
    Batch ID, Product ID, quantity, mfg/expiry dates, final status = COMPLETE.
    """
    db = get_db()
    completed = db.query(ProductionBatch).filter_by(status='COMPLETE').all()
    
    contract_data = []
    for b in completed:
        contract_data.append({
            "batch_id": b.id,
            "batch_code": b.batch_code,
            "product_id": b.product_id,
            "product_name": b.product_name,
            "quantity": b.actual_quantity or b.target_quantity,
            "unit": b.unit,
            "mfg_date": b.mfg_date.strftime("%Y-%m-%d") if b.mfg_date else datetime.datetime.utcnow().strftime("%Y-%m-%d"),
            "expiry_date": b.expiry_date.strftime("%Y-%m-%d") if b.expiry_date else None,
            "final_status": b.status
        })

    return jsonify({
        "success": True,
        "count": len(contract_data),
        "data": contract_data
    })
