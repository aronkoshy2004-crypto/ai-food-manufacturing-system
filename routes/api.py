"""
API Endpoints delivering generic prop-driven card data and detail drawer records
"""
from flask import Blueprint, jsonify, request, session
from models import get_db
from models.enums import StatusEnum, RoleEnum, STATUS_METADATA, ROLE_MODULE_PERMISSIONS
from models.schema_draft import RawMaterialLot, QCInspection, ProductionBatch, WarehouseItem, DispatchOrder
from routes.auth import login_required, get_current_user

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/cards', methods=['GET'])
@login_required
def get_cards():
    """
    Returns generic prop-driven record cards tailored for the requested module.
    Format adheres to:
    {
      id, title, category, headerStat, miniGrid: [{label, value}],
      avatars: [{initial, bg, name}], status, statusLabel, progress
    }
    """
    user = get_current_user()
    module = request.args.get('module', 'production').lower()
    db = get_db()
    
    cards = []

    if module == 'procurement':
        lots = db.query(RawMaterialLot).order_by(RawMaterialLot.id.desc()).all()
        for lot in lots:
            cards.append({
                "id": lot.lot_number,
                "db_id": lot.id,
                "module": "procurement",
                "category": lot.category,
                "title": f"{lot.material_name} - {lot.supplier_name}",
                "headerStat": f"{lot.quantity} {lot.unit}",
                "statSub": "Quantity Received",
                "progress": 95 if lot.status == StatusEnum.APPROVED.value else (60 if lot.status == StatusEnum.PENDING.value else 40),
                "miniGrid": [
                    {"label": "Supplier", "value": lot.supplier_name},
                    {"label": "Storage Condition", "value": lot.storage_condition},
                    {"label": "Received Date", "value": lot.received_at.strftime("%d/%m/%Y") if lot.received_at else "Today"},
                    {"label": "Received By", "value": lot.created_by.full_name if lot.created_by else "Procurement"}
                ],
                "avatars": [
                    {"initial": "TM", "bg": "#162B4E", "name": "Procurement"}
                ],
                "status": lot.status,
                "statusLabel": STATUS_METADATA[StatusEnum(lot.status)]["label"],
                "statusPill": STATUS_METADATA[StatusEnum(lot.status)]["pill_class"],
                "editableFields": [
                    {"label": "Status", "key": "status", "type": "select", "options": [s.value for s in StatusEnum], "value": lot.status},
                    {"label": "Storage Condition", "key": "storage_condition", "type": "text", "value": lot.storage_condition}
                ],
                "readonlySpecs": [
                    {"label": "Material Lot Code", "value": lot.lot_number, "mono": True},
                    {"label": "Quantity / Weight", "value": f"{lot.quantity} {lot.unit}"},
                    {"label": "Standard Spec", "value": "ISO 22000 Inbound QC"}
                ]
            })

    elif module == 'qc':
        qcs = db.query(QCInspection).order_by(QCInspection.id.desc()).all()
        for qc in qcs:
            cards.append({
                "id": qc.inspection_code,
                "db_id": qc.id,
                "module": "qc",
                "category": qc.sample_type,
                "title": qc.title,
                "headerStat": "Lab Test Specs",
                "statSub": "18/18 Parameters Passed" if qc.status == StatusEnum.APPROVED.value else "Culture Incubation Pending",
                "progress": 100 if qc.status == StatusEnum.APPROVED.value else (85 if qc.status == StatusEnum.HOLD.value else 50),
                "miniGrid": [
                    {"label": "Lab Specialist", "value": qc.inspector.full_name if qc.inspector else "QC Lab"},
                    {"label": "Standards Applied", "value": qc.standards_applied},
                    {"label": "Sampling Date", "value": qc.inspected_at.strftime("%d/%m/%Y %H:%M") if qc.inspected_at else "Today"},
                    {"label": "Conclusion", "value": STATUS_METADATA[StatusEnum(qc.status)]["label"]}
                ],
                "avatars": [
                    {"initial": "QC", "bg": "#0D9488", "name": "Lab Technician"}
                ],
                "status": qc.status,
                "statusLabel": STATUS_METADATA[StatusEnum(qc.status)]["label"],
                "statusPill": STATUS_METADATA[StatusEnum(qc.status)]["pill_class"],
                "editableFields": [
                    {"label": "Inspection Status", "key": "status", "type": "select", "options": [s.value for s in StatusEnum], "value": qc.status},
                    {"label": "Applied Standards", "key": "standards_applied", "type": "text", "value": qc.standards_applied}
                ],
                "readonlySpecs": [
                    {"label": "Lab Sample ID", "value": qc.inspection_code, "mono": True},
                    {"label": "Testing Method", "value": qc.sample_type},
                    {"label": "Microbiological Spec", "value": "Salmonella / Coliform Negative"}
                ]
            })

    elif module == 'warehouse':
        items = db.query(WarehouseItem).order_by(WarehouseItem.id.desc()).all()
        for item in items:
            cards.append({
                "id": item.sku_code,
                "db_id": item.id,
                "module": "warehouse",
                "category": "Finished Goods Stock",
                "title": item.product_name,
                "headerStat": f"{item.quantity:,.0f} {item.unit}",
                "statSub": f"{item.pallet_count} Pallets Stored",
                "progress": int(min(item.quantity / (item.min_threshold * 5) * 100, 100)),
                "miniGrid": [
                    {"label": "Storage Bin", "value": item.location_bin},
                    {"label": "Pallet Quantity", "value": f"{item.pallet_count} Pallets"},
                    {"label": "Safety Threshold", "value": f"Min {item.min_threshold:,.0f}"},
                    {"label": "Custodian", "value": item.audited_by.full_name if item.audited_by else "Main Warehouse"}
                ],
                "avatars": [
                    {"initial": "WH", "bg": "#0284C7", "name": "Warehouse Manager"}
                ],
                "status": item.status,
                "statusLabel": STATUS_METADATA[StatusEnum(item.status)]["label"],
                "statusPill": STATUS_METADATA[StatusEnum(item.status)]["pill_class"],
                "editableFields": [
                    {"label": "Inventory Status", "key": "status", "type": "select", "options": [s.value for s in StatusEnum], "value": item.status},
                    {"label": "Storage Bin", "key": "location_bin", "type": "text", "value": item.location_bin}
                ],
                "readonlySpecs": [
                    {"label": "SKU Code", "value": item.sku_code, "mono": True},
                    {"label": "Shelf Life Remaining", "value": "180 days (FEFO Compliant)"},
                    {"label": "Packaging Spec", "value": "Standard Packaging"}
                ]
            })

    else:  # production
        batches = db.query(ProductionBatch).order_by(ProductionBatch.id.desc()).all()
        for batch in batches:
            progress = int((batch.actual_quantity / batch.target_quantity * 100)) if batch.target_quantity > 0 else 0
            cards.append({
                "id": batch.batch_code,
                "db_id": batch.id,
                "module": "production",
                "category": batch.line_name,
                "title": batch.product_name,
                "headerStat": f"{batch.actual_quantity:,.0f} / {batch.target_quantity:,.0f}",
                "statSub": f"{batch.unit} completed",
                "progress": min(progress, 100),
                "miniGrid": [
                    {"label": "Filling Line", "value": batch.line_name},
                    {"label": "UHT Temp Spec", "value": batch.temperature_spec},
                    {"label": "Shift Manager", "value": batch.shift_manager.full_name if batch.shift_manager else "Shift Supervisor"},
                    {"label": "Start Time", "value": batch.started_at.strftime("%d/%m %H:%M") if batch.started_at else "Today"}
                ],
                "avatars": [
                    {"initial": "PR", "bg": "#162B4E", "name": "Production Manager"},
                    {"initial": "OP", "bg": "#2563EB", "name": "Line Operator"}
                ],
                "status": batch.status,
                "statusLabel": STATUS_METADATA[StatusEnum(batch.status)]["label"],
                "statusPill": STATUS_METADATA[StatusEnum(batch.status)]["pill_class"],
                "editableFields": [
                    {"label": "Batch Status", "key": "status", "type": "select", "options": [s.value for s in StatusEnum], "value": batch.status},
                    {"label": "Operating Line", "key": "line_name", "type": "text", "value": batch.line_name}
                ],
                "readonlySpecs": [
                    {"label": "Batch Code", "value": batch.batch_code, "mono": True},
                    {"label": "UHT Thermal Sterilization", "value": batch.temperature_spec},
                    {"label": "CIP Cleaning Certificate", "value": "CIP Completed 100%"}
                ]
            })

    return jsonify({
        "module": module,
        "count": len(cards),
        "cards": cards,
        "user_role": user.role
    })


@api_bp.route('/cards/<module>/<int:item_id>/status', methods=['POST'])
@login_required
def update_card_status(module, item_id):
    """
    Updates status of a record card using the shared StatusEnum vocabulary.
    """
    data = request.get_json() or {}
    new_status = data.get('status')

    if new_status not in [s.value for s in StatusEnum]:
        return jsonify({"error": "Invalid status", "allowed": [s.value for s in StatusEnum]}), 400

    db = get_db()
    model_map = {
        'procurement': RawMaterialLot,
        'qc': QCInspection,
        'production': ProductionBatch,
        'warehouse': WarehouseItem
    }

    model = model_map.get(module)
    if not model:
        return jsonify({"error": f"Unknown module '{module}'"}), 404

    record = db.query(model).filter_by(id=item_id).first()
    if not record:
        return jsonify({"error": "Record not found"}), 404

    record.status = new_status
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Successfully updated status to {new_status}",
        "new_status": new_status,
        "pill": STATUS_METADATA[StatusEnum(new_status)]["pill_class"],
        "label": STATUS_METADATA[StatusEnum(new_status)]["label"]
    })


@api_bp.route('/search', methods=['GET'])
@login_required
def global_search():
    """
    Role-filtered debounced global search across suppliers, raw materials, lots,
    batches, POs, GRNs, customers, and dispatches.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get('q', '').strip()
    if not q or len(q) < 1:
        return jsonify({"success": True, "results": {}, "total": 0})

    role = (user.role or "").strip().title()
    db = get_db()

    # Determine allowed search categories based on role
    allowed = set()
    if role == "Admin":
        allowed = {"suppliers", "raw_materials", "lots", "batches", "purchase_orders", "goods_receipts", "customers", "dispatches"}
    elif role == "Procurement":
        allowed = {"suppliers", "raw_materials", "lots", "purchase_orders", "goods_receipts"}
    elif role == "Qc":
        allowed = {"lots", "batches", "raw_materials", "suppliers"}
    elif role == "Production":
        allowed = {"batches", "raw_materials", "lots"}
    elif role == "Warehouse":
        allowed = {"lots", "dispatches", "customers", "goods_receipts"}
    else:
        allowed = {"lots", "batches"}

    from models.procurement import Supplier, RawMaterial, PurchaseOrder, GoodsReceipt
    from models.warehouse import Customer, Dispatch
    from models.production import ProductionBatch

    results = {}
    total_count = 0

    # 1. Suppliers
    if "suppliers" in allowed:
        suppliers = db.query(Supplier).filter(
            Supplier.name.ilike(f"%{q}%") |
            Supplier.code.ilike(f"%{q}%") |
            Supplier.contact_name.ilike(f"%{q}%")
        ).limit(5).all()
        if suppliers:
            results["Suppliers"] = [{
                "id": s.id,
                "title": s.name,
                "subtitle": f"{s.code} • {s.contact_name or 'Active Supplier'}",
                "url": f"/procurement?view=suppliers&open=supplier_{s.id}",
                "badge": s.code,
                "badge_class": "badge-blue"
            } for s in suppliers]
            total_count += len(suppliers)

    # 2. Raw Materials
    if "raw_materials" in allowed:
        raw_materials = db.query(RawMaterial).filter(
            RawMaterial.name.ilike(f"%{q}%") |
            RawMaterial.code.ilike(f"%{q}%") |
            RawMaterial.category.ilike(f"%{q}%")
        ).limit(5).all()
        if raw_materials:
            results["Raw Materials"] = [{
                "id": rm.id,
                "title": rm.name,
                "subtitle": f"{rm.code} • {rm.category}",
                "url": f"/procurement?view=raw-materials&open=raw_material_{rm.id}",
                "badge": rm.code,
                "badge_class": "badge-amber"
            } for rm in raw_materials]
            total_count += len(raw_materials)

    # 3. Raw Material Lots
    if "lots" in allowed:
        lots = db.query(RawMaterialLot).filter(
            RawMaterialLot.lot_number.ilike(f"%{q}%") |
            RawMaterialLot.material_name.ilike(f"%{q}%") |
            RawMaterialLot.supplier_name.ilike(f"%{q}%")
        ).limit(5).all()
        if lots:
            results["Lots"] = [{
                "id": l.id,
                "title": f"Lot: {l.lot_number}",
                "subtitle": f"{l.material_name} • {l.supplier_name} ({l.quantity} {l.unit})",
                "url": f"/procurement?view=lots&open={l.lot_number}",
                "badge": l.qc_status or l.status,
                "badge_class": "badge-green" if (l.qc_status == "APPROVED" or l.status == "APPROVED") else "badge-amber"
            } for l in lots]
            total_count += len(lots)

    # 4. Production Batches
    if "batches" in allowed:
        batches = db.query(ProductionBatch).filter(
            ProductionBatch.batch_code.ilike(f"%{q}%") |
            ProductionBatch.product_name.ilike(f"%{q}%")
        ).limit(5).all()
        if batches:
            results["Batches"] = [{
                "id": b.id,
                "title": f"Batch: {b.batch_code}",
                "subtitle": f"{b.product_name} • {b.current_stage or b.status}",
                "url": f"/production?view=batches&open={b.id}",
                "badge": b.status,
                "badge_class": "badge-blue"
            } for b in batches]
            total_count += len(batches)

    # 5. Purchase Orders
    if "purchase_orders" in allowed:
        pos = db.query(PurchaseOrder).filter(
            PurchaseOrder.po_number.ilike(f"%{q}%") |
            PurchaseOrder.supplier.has(Supplier.name.ilike(f"%{q}%"))
        ).limit(5).all()
        if pos:
            results["Purchase Orders"] = [{
                "id": po.id,
                "title": f"PO: {po.po_number}",
                "subtitle": f"{po.supplier.name if po.supplier else 'Vendor'} • {po.status}",
                "url": f"/procurement?view=po&open={po.id}",
                "badge": po.status,
                "badge_class": "badge-blue"
            } for po in pos]
            total_count += len(pos)

    # 6. Goods Receipts (GRNs)
    if "goods_receipts" in allowed:
        grns = db.query(GoodsReceipt).filter(
            GoodsReceipt.grn_number.ilike(f"%{q}%") |
            GoodsReceipt.truck_plate.ilike(f"%{q}%") |
            GoodsReceipt.delivery_note_ref.ilike(f"%{q}%")
        ).limit(5).all()
        if grns:
            results["Goods Receipts"] = [{
                "id": grn.id,
                "title": f"GRN: {grn.grn_number}",
                "subtitle": f"Truck {grn.truck_plate or 'N/A'} • Waybill: {grn.delivery_note_ref or 'N/A'}",
                "url": f"/procurement?view=grn&open={grn.id}",
                "badge": grn.status,
                "badge_class": "badge-green"
            } for grn in grns]
            total_count += len(grns)

    # 7. Customers
    if "customers" in allowed:
        customers = db.query(Customer).filter(
            Customer.name.ilike(f"%{q}%") |
            Customer.customer_code.ilike(f"%{q}%") |
            Customer.contact_person.ilike(f"%{q}%")
        ).limit(5).all()
        if customers:
            results["Customers"] = [{
                "id": c.id,
                "title": c.name,
                "subtitle": f"{c.customer_code} • Contact: {c.contact_person or c.phone or 'Active'}",
                "url": f"/warehouse?view=customers&open={c.id}",
                "badge": c.customer_code,
                "badge_class": "badge-blue"
            } for c in customers]
            total_count += len(customers)

    # 8. Dispatches
    if "dispatches" in allowed:
        dispatches = db.query(Dispatch).filter(
            Dispatch.dispatch_code.ilike(f"%{q}%") |
            Dispatch.destination.ilike(f"%{q}%") |
            Dispatch.carrier_name.ilike(f"%{q}%") |
            Dispatch.license_plate.ilike(f"%{q}%")
        ).limit(5).all()
        if dispatches:
            results["Dispatches"] = [{
                "id": d.id,
                "title": f"Dispatch: {d.dispatch_code}",
                "subtitle": f"{d.carrier_name or 'Fleet'} • Dest: {d.destination} • {d.license_plate}",
                "url": f"/warehouse?view=dispatches&open={d.id}",
                "badge": d.status,
                "badge_class": "badge-green" if d.status == "DELIVERED" else "badge-amber"
            } for d in dispatches]
            total_count += len(dispatches)

    return jsonify({
        "success": True,
        "query": q,
        "role": role,
        "total": total_count,
        "results": results
    })

