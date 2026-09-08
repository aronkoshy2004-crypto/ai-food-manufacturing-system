"""
Procurement Routes: Suppliers, Raw Materials, Purchase Orders, GRN, and Lots
Phase 1 — Business Logic & REST Endpoints
"""
import datetime
import random
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from models import get_db
from models.enums import RoleEnum, StatusEnum, STATUS_METADATA
from models.user import User
from models.schema_draft import RawMaterialLot
from models.procurement import (
    Supplier,
    RawMaterial,
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceipt,
    GoodsReceiptItem
)
from routes.auth import login_required, get_current_user

procurement_bp = Blueprint('procurement', __name__)

# ==============================================================================
# UI ROUTE
# ==============================================================================
@procurement_bp.route('/procurement')
@login_required
def index():
    user = get_current_user()
    view = request.args.get('view', 'lots') # 'lots' | 'suppliers' | 'raw-materials' | 'po' | 'grn'
    
    db = get_db()
    # Query pending QC count for sidebar badge
    pending_qc_count = db.query(RawMaterialLot).filter(
        (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
    ).count()

    view_titles = {
        'lots': 'Lô nguyên liệu (Raw Material Lots)',
        'suppliers': 'Quản lý Nhà cung cấp (Suppliers)',
        'raw-materials': 'Danh mục Nguyên vật liệu & Bao bì (Raw Materials)',
        'po': 'Đơn đặt hàng mua (Purchase Orders)',
        'grn': 'Phiếu nhập kho (Goods Receipt Notes)'
    }

    breadcrumbs = {
        'lots': ["Trang chủ", "Mua hàng", "Lô nguyên liệu"],
        'suppliers': ["Trang chủ", "Mua hàng", "Nhà cung cấp"],
        'raw-materials': ["Trang chủ", "Mua hàng", "Danh mục nguyên liệu"],
        'po': ["Trang chủ", "Mua hàng", "Đơn mua hàng PO"],
        'grn': ["Trang chủ", "Mua hàng", "Phiếu nhập kho GRN"]
    }

    return render_template(
        'procurement.html',
        user=user,
        active_view=view,
        view_title=view_titles.get(view, 'Mua hàng'),
        breadcrumb=breadcrumbs.get(view, ["Trang chủ", "Mua hàng"]),
        pending_qc_count=pending_qc_count
    )


# ==============================================================================
# 1. SUPPLIERS API (CRUD)
# ==============================================================================
@procurement_bp.route('/api/procurement/suppliers', methods=['GET'])
@login_required
def get_suppliers():
    db = get_db()
    suppliers = db.query(Supplier).order_by(Supplier.id.desc()).all()
    return jsonify({
        "success": True,
        "count": len(suppliers),
        "data": [s.to_dict() for s in suppliers]
    })


@procurement_bp.route('/api/procurement/suppliers', methods=['POST'])
@login_required
def create_supplier():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "Tên nhà cung cấp là bắt buộc"}), 400

    db = get_db()
    code = data.get('code') or f"SUP-{random.randint(100, 999)}"
    
    supplier = Supplier(
        code=code,
        name=name,
        contact_name=data.get('contact_name', ''),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        address=data.get('address', 'Việt Nam'),
        rating=float(data.get('rating', 5.0)),
        status=data.get('status', 'APPROVED')
    )
    db.add(supplier)
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Đã tạo nhà cung cấp {supplier.name}",
        "data": supplier.to_dict()
    }), 201


@procurement_bp.route('/api/procurement/suppliers/<int:supplier_id>', methods=['PUT'])
@login_required
def update_supplier(supplier_id):
    data = request.get_json() or {}
    db = get_db()
    supplier = db.query(Supplier).filter_by(id=supplier_id).first()
    if not supplier:
        return jsonify({"error": "Không tìm thấy nhà cung cấp"}), 404

    if 'name' in data: supplier.name = data['name'].strip()
    if 'contact_name' in data: supplier.contact_name = data['contact_name'].strip()
    if 'email' in data: supplier.email = data['email'].strip()
    if 'phone' in data: supplier.phone = data['phone'].strip()
    if 'address' in data: supplier.address = data['address'].strip()
    if 'rating' in data: supplier.rating = float(data['rating'])
    if 'status' in data: supplier.status = data['status']

    db.commit()
    return jsonify({
        "success": True,
        "message": f"Cập nhật thành công nhà cung cấp {supplier.name}",
        "data": supplier.to_dict()
    })


# ==============================================================================
# 2. RAW MATERIALS API (CRUD)
# ==============================================================================
@procurement_bp.route('/api/procurement/raw-materials', methods=['GET'])
@login_required
def get_raw_materials():
    db = get_db()
    materials = db.query(RawMaterial).order_by(RawMaterial.id.desc()).all()
    return jsonify({
        "success": True,
        "count": len(materials),
        "data": [m.to_dict() for m in materials]
    })


@procurement_bp.route('/api/procurement/raw-materials', methods=['POST'])
@login_required
def create_raw_material():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "Tên nguyên vật liệu là bắt buộc"}), 400

    db = get_db()
    code = data.get('code') or f"RM-{random.randint(100, 999)}"

    material = RawMaterial(
        code=code,
        name=name,
        category=data.get('category', 'Sữa tươi thô'),
        standard_unit=data.get('standard_unit', 'Tấn'),
        unit_weight=data.get('unit_weight', '1,000 kg / bồn'),
        storage_temp=data.get('storage_temp', 'Kho mát 4-6°C'),
        shelf_life_days=int(data.get('shelf_life_days', 180)),
        min_stock_level=float(data.get('min_stock_level', 5.0)),
        status=data.get('status', 'APPROVED')
    )
    db.add(material)
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Đã tạo nguyên liệu {material.name}",
        "data": material.to_dict()
    }), 201


@procurement_bp.route('/api/procurement/raw-materials/<int:material_id>', methods=['PUT'])
@login_required
def update_raw_material(material_id):
    data = request.get_json() or {}
    db = get_db()
    material = db.query(RawMaterial).filter_by(id=material_id).first()
    if not material:
        return jsonify({"error": "Không tìm thấy nguyên liệu"}), 404

    if 'name' in data: material.name = data['name'].strip()
    if 'category' in data: material.category = data['category'].strip()
    if 'standard_unit' in data: material.standard_unit = data['standard_unit'].strip()
    if 'unit_weight' in data: material.unit_weight = data['unit_weight'].strip()
    if 'storage_temp' in data: material.storage_temp = data['storage_temp'].strip()
    if 'shelf_life_days' in data: material.shelf_life_days = int(data['shelf_life_days'])
    if 'min_stock_level' in data: material.min_stock_level = float(data['min_stock_level'])
    if 'status' in data: material.status = data['status']

    db.commit()
    return jsonify({
        "success": True,
        "message": f"Cập nhật thành công nguyên liệu {material.name}",
        "data": material.to_dict()
    })


# ==============================================================================
# 3. PURCHASE ORDERS (MULTI-LINE PO CREATION)
# ==============================================================================
@procurement_bp.route('/api/procurement/purchase-orders', methods=['GET'])
@login_required
def get_purchase_orders():
    db = get_db()
    pos = db.query(PurchaseOrder).order_by(PurchaseOrder.id.desc()).all()
    return jsonify({
        "success": True,
        "count": len(pos),
        "data": [p.to_dict() for p in pos]
    })


@procurement_bp.route('/api/procurement/purchase-orders', methods=['POST'])
@login_required
def create_purchase_order():
    data = request.get_json() or {}
    supplier_id = data.get('supplier_id')
    items_data = data.get('items', [])

    if not supplier_id:
        return jsonify({"error": "Vui lòng chọn nhà cung cấp"}), 400
    if not items_data or len(items_data) == 0:
        return jsonify({"error": "Đơn hàng phải có ít nhất 1 dòng mặt hàng"}), 400

    db = get_db()
    user = get_current_user()

    po_number = f"PO-2026-{random.randint(1000, 9999)}"
    
    total_amount = 0.0
    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=supplier_id,
        created_by_user_id=user.id if user else None,
        order_date=datetime.datetime.utcnow(),
        status="APPROVED", # Ready for GRN intake
        notes=data.get('notes', 'Đơn hàng cung cấp nguyên liệu định kỳ')
    )
    db.add(po)
    db.flush() # Populate po.id

    for item in items_data:
        raw_material_id = item.get('raw_material_id')
        qty = float(item.get('quantity_ordered', 0.0))
        unit = item.get('unit', 'Tấn')
        unit_price = float(item.get('unit_price', 0.0))
        subtotal = qty * unit_price
        total_amount += subtotal

        po_item = PurchaseOrderItem(
            purchase_order_id=po.id,
            raw_material_id=raw_material_id,
            quantity_ordered=qty,
            quantity_received=0.0,
            unit=unit,
            unit_price=unit_price,
            subtotal=subtotal,
            notes=item.get('notes', '')
        )
        db.add(po_item)

    po.total_amount = total_amount
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Tạo thành công đơn mua hàng {po.po_number}",
        "data": po.to_dict()
    }), 201


# ==============================================================================
# 4. GRN ENTRY AGAINST A PO & AUTOMATIC RAW MATERIAL LOT GENERATION
# Output contract: On GRN completion -> auto-generate raw_material_lots with qc_status = PENDING_QC
# ==============================================================================
@procurement_bp.route('/api/procurement/grn', methods=['GET'])
@login_required
def get_goods_receipts():
    db = get_db()
    grns = db.query(GoodsReceipt).order_by(GoodsReceipt.id.desc()).all()
    return jsonify({
        "success": True,
        "count": len(grns),
        "data": [g.to_dict() for g in grns]
    })


@procurement_bp.route('/api/procurement/grn', methods=['POST'])
@login_required
def create_goods_receipt():
    """
    GRN entry against a PO.
    On GRN completion:
    - Creates GoodsReceipt & GoodsReceiptItem records
    - Updates PO items received quantities
    - AUTO-GENERATES RawMaterialLot records with qc_status = 'PENDING_QC'
    """
    data = request.get_json() or {}
    po_id = data.get('purchase_order_id')
    received_items = data.get('items', [])

    if not po_id:
        return jsonify({"error": "Vui lòng chọn mã đơn hàng PO"}), 400
    if not received_items or len(received_items) == 0:
        return jsonify({"error": "Vui lòng nhập danh sách mặt hàng thực nhận"}), 400

    db = get_db()
    user = get_current_user()
    po = db.query(PurchaseOrder).filter_by(id=po_id).first()
    if not po:
        return jsonify({"error": "Không tìm thấy đơn hàng PO"}), 404

    grn_number = f"GRN-2026-{random.randint(1000, 9999)}"
    
    grn = GoodsReceipt(
        grn_number=grn_number,
        purchase_order_id=po.id,
        receiver_user_id=user.id if user else None,
        received_date=datetime.datetime.utcnow(),
        delivery_note_ref=data.get('delivery_note_ref', f"BL-{random.randint(10000, 99999)}"),
        truck_plate=data.get('truck_plate', '29C-438.12'),
        status="COMPLETED",
        notes=data.get('notes', 'Kiểm đếm đạt quy cách nhập kho')
    )
    db.add(grn)
    db.flush()

    generated_lots = []

    for item_data in received_items:
        po_item_id = item_data.get('purchase_order_item_id')
        raw_material_id = item_data.get('raw_material_id')
        qty_recv = float(item_data.get('quantity_received', 0.0))
        unit = item_data.get('unit', 'Tấn')
        unit_weight = item_data.get('unit_weight', 'Quy cách chuẩn')

        # Update PO Item
        if po_item_id:
            po_item = db.query(PurchaseOrderItem).filter_by(id=po_item_id).first()
            if po_item:
                po_item.quantity_received += qty_recv
                if not raw_material_id:
                    raw_material_id = po_item.raw_material_id
                if not unit:
                    unit = po_item.unit

        # Create GRN Item
        grn_item = GoodsReceiptItem(
            goods_receipt_id=grn.id,
            purchase_order_item_id=po_item_id,
            raw_material_id=raw_material_id,
            quantity_received=qty_recv,
            unit=unit,
            unit_weight=unit_weight,
            notes=item_data.get('notes', '')
        )
        db.add(grn_item)

        # Retrieve Material & Supplier info
        material = db.query(RawMaterial).filter_by(id=raw_material_id).first()
        mat_name = material.name if material else "Nguyên liệu nhập kho"
        category = material.category if material else "Sản xuất chung"
        storage = material.storage_temp if material else "Kho mát 4-6°C"

        # ======================================================================
        # AUTO-GENERATE RawMaterialLot with qc_status = 'PENDING_QC'
        # ======================================================================
        lot_number = f"LOT-RM-2026-{random.randint(100, 999)}"
        new_lot = RawMaterialLot(
            lot_number=lot_number,
            material_name=mat_name,
            category=category,
            supplier_name=po.supplier.name if po.supplier else "Nhà cung cấp",
            quantity=qty_recv,
            unit=unit,
            storage_condition=storage,
            status=StatusEnum.PENDING.value,
            qc_status="PENDING_QC", # Required by PRD output contract for Module 2
            unit_weight=unit_weight,
            created_by_user_id=user.id if user else None,
            supplier_id=po.supplier_id,
            raw_material_id=raw_material_id,
            purchase_order_id=po.id,
            goods_receipt_id=grn.id,
            received_at=datetime.datetime.utcnow(),
            notes=f"Tự động tạo từ phiếu {grn_number} theo đơn {po.po_number}"
        )
        db.add(new_lot)
        generated_lots.append(new_lot)

    # Check if PO is completely fulfilled
    all_fulfilled = all(item.quantity_received >= item.quantity_ordered for item in po.items)
    po.status = "COMPLETED" if all_fulfilled else "PARTIAL_RECEIVED"

    db.commit()

    return jsonify({
        "success": True,
        "message": f"Hoàn tất lập phiếu nhập kho {grn_number}. Đã tự động khởi tạo {len(generated_lots)} lô nguyên liệu chờ kiểm định QC.",
        "grn": grn.to_dict(),
        "generated_lots": [lot.lot_number for lot in generated_lots],
        "generated_lot_ids": [lot.id for lot in generated_lots]
    }), 201


# ==============================================================================
# 5. RAW MATERIAL LOTS SCREEN API (CARD GRID & DETAIL DRAWER DATA)
# ==============================================================================
@procurement_bp.route('/api/procurement/lots', methods=['GET'])
@login_required
def get_lots():
    """
    Returns card-grid ready lots with:
    - header: lot number + received-qty stat top-right
    - mini-grid: material / unit weight, supplier / PO ref
    - status pill: PENDING_QC (amber), APPROVED (green), REJECTED/HOLD (red-ish)
    """
    db = get_db()
    lots = db.query(RawMaterialLot).order_by(RawMaterialLot.id.desc()).all()

    cards = []
    for lot in lots:
        # Determine status pill based on qc_status
        qc_status = lot.qc_status or "PENDING_QC"
        if qc_status == "PENDING_QC":
            pill_class = "pill-pending"
            pill_label = "PENDING_QC"
        elif qc_status == "APPROVED":
            pill_class = "pill-approved"
            pill_label = "APPROVED"
        elif qc_status == "HOLD":
            pill_class = "pill-hold"
            pill_label = "HOLD"
        else: # REJECTED
            pill_class = "pill-rejected"
            pill_label = "REJECTED"

        po_ref = lot.purchase_order.po_number if lot.purchase_order else (f"PO Ref #{lot.id}" if lot.purchase_order_id else "Nhập trực tiếp")
        grn_ref = lot.goods_receipt.grn_number if lot.goods_receipt else "GRN Chuẩn"

        cards.append({
            "id": lot.lot_number,
            "db_id": lot.id,
            "title": lot.material_name,
            "category": lot.category,
            "headerStat": f"{lot.quantity:,.1f} {lot.unit}",
            "statSub": "Số lượng thực nhận",
            "progress": 100 if qc_status == "APPROVED" else (40 if qc_status == "PENDING_QC" else 75),
            "qc_status": qc_status,
            "miniGrid": [
                {"label": "Nguyên liệu / Quy cách", "value": f"{lot.material_name} ({lot.unit_weight or 'Bao tiêu'})"},
                {"label": "Nhà cung cấp / PO", "value": f"{lot.supplier_name} • {po_ref}"},
                {"label": "Ngày nhận kho", "value": lot.received_at.strftime("%d/%m/%Y") if lot.received_at else "Hôm nay"},
                {"label": "Kho lưu trữ", "value": lot.storage_condition or "Kho mát"}
            ],
            "avatars": [
                {"initial": "PR", "bg": "#162B4E", "name": "Thu mua"},
                {"initial": "QC", "bg": "#F59E0B", "name": "Chờ duyệt QC"}
            ],
            "status": qc_status,
            "statusLabel": pill_label,
            "statusPill": pill_class,
            "editableFields": [
                {"label": "Nguyên vật liệu", "key": "material_name", "type": "text", "value": lot.material_name},
                {"label": "Nhà cung cấp", "key": "supplier_name", "type": "text", "value": lot.supplier_name},
                {"label": "Đơn vị tính", "key": "unit", "type": "select", "options": ["Tấn", "Kg", "Lít", "Cuộn vỏ", "Kiện"], "value": lot.unit},
                {"label": "Điều kiện bảo quản", "key": "storage_condition", "type": "text", "value": lot.storage_condition or "Kho mát 4-6°C"}
            ],
            "readonlySpecs": [
                {"label": "Mã đơn hàng PO", "value": po_ref, "mono": True},
                {"label": "Số phiếu nhập GRN", "value": grn_ref, "mono": True},
                {"label": "Số lượng thực nhận", "value": f"{lot.quantity:,.1f} {lot.unit}"},
                {"label": "Trạng thái kiểm định QC", "value": f"{qc_status} (Module 2 Target)"}
            ]
        })

    return jsonify({
        "success": True,
        "count": len(cards),
        "cards": cards
    })


@procurement_bp.route('/api/procurement/lots/<int:lot_id>', methods=['PUT'])
@login_required
def update_lot(lot_id):
    """
    Update lot details from the slide-in detail drawer
    """
    data = request.get_json() or {}
    db = get_db()
    lot = db.query(RawMaterialLot).filter_by(id=lot_id).first()
    if not lot:
        return jsonify({"error": "Không tìm thấy lô nguyên liệu"}), 404

    if 'material_name' in data: lot.material_name = data['material_name'].strip()
    if 'supplier_name' in data: lot.supplier_name = data['supplier_name'].strip()
    if 'unit' in data: lot.unit = data['unit'].strip()
    if 'storage_condition' in data: lot.storage_condition = data['storage_condition'].strip()
    if 'qc_status' in data:
        lot.qc_status = data['qc_status']
        if data['qc_status'] == 'APPROVED':
            lot.status = StatusEnum.APPROVED.value
        elif data['qc_status'] == 'PENDING_QC':
            lot.status = StatusEnum.PENDING.value

    db.commit()
    return jsonify({
        "success": True,
        "message": f"Cập nhật thành công thông tin lô {lot.lot_number}",
        "lot_id": lot.id
    })


@procurement_bp.route('/api/procurement/stats', methods=['GET'])
@login_required
def get_stats():
    db = get_db()
    pending_qc_count = db.query(RawMaterialLot).filter(
        (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
    ).count()
    return jsonify({
        "pending_qc_lots": pending_qc_count,
        "total_suppliers": db.query(Supplier).count(),
        "total_materials": db.query(RawMaterial).count(),
        "total_pos": db.query(PurchaseOrder).count()
    })
