"""
Warehouse, Inventory (FEFO), Customers & Dispatches Routes
PRD Phase 4
"""
import datetime
from flask import Blueprint, render_template, request, jsonify, session
from models import get_db
from models.user import User
from models.production import ProductionBatch, Product
from models.warehouse import (
    WarehouseInventory,
    Customer,
    Dispatch,
    DispatchItem,
    AlertRule,
    NotificationAlert
)
from routes.auth import login_required, role_required

warehouse_bp = Blueprint('warehouse', __name__)

@warehouse_bp.route('/warehouse')
@login_required
@role_required('Warehouse', 'Admin', 'Production', 'Procurement')
def index():
    view = request.args.get('view', 'inventory')
    user = session.get('user')
    permitted_modules = session.get('user_modules', ['warehouse'])
    return render_template(
        'warehouse.html',
        active_view=view,
        current_module='warehouse',
        user=user,
        permitted_modules=permitted_modules
    )

# -----------------------------------------------------------------------------
# REST APIs
# -----------------------------------------------------------------------------

@warehouse_bp.route('/api/warehouse/sync-batch/<int:batch_id>', methods=['POST'])
@login_required
def sync_batch_to_inventory(batch_id):
    """
    Sync finished approved batch into warehouse inventory.
    Strict gate: Only batches with status == 'COMPLETE' are admitted.
    """
    db = get_db()
    batch = db.query(ProductionBatch).filter_by(id=batch_id).first()
    if not batch:
        return jsonify({"success": False, "error": "Không tìm thấy lô sản xuất"}), 404

    if batch.status != 'COMPLETE':
        return jsonify({
            "success": False,
            "error": f"Lô sản xuất {batch.batch_code} đang ở trạng thái '{batch.status}'. Chỉ lô đã COMPLETE mới được nhập kho."
        }), 400

    # Check if inventory entry already exists
    existing = db.query(WarehouseInventory).filter_by(production_batch_id=batch.id).first()
    user_id = session.get('user', {}).get('id')
    qty = batch.actual_quantity or batch.target_quantity or 5000.0

    if existing:
        existing.available_quantity = qty
        existing.initial_quantity = qty
        existing.updated_at = datetime.datetime.utcnow()
        db.commit()
        return jsonify({
            "success": True,
            "message": f"Cập nhật thành công tồn kho thành phẩm cho lô {batch.batch_code}",
            "data": existing.to_dict()
        })

    count = db.query(WarehouseInventory).count() + 1
    sku_code = f"INV-SKU-{count:03d}"

    mfg = batch.mfg_date or datetime.datetime.utcnow()
    exp = batch.expiry_date
    if not exp:
        shelf_life = batch.product.shelf_life_days if batch.product else 180
        exp = mfg + datetime.timedelta(days=shelf_life)

    bin_locations = ["Khu A - Kệ 04 Tầng 2", "Khu B - Kệ 02 Tầng 1", "Khu C - Kệ trượt Pallet 05", "Khu D - Kho mát 18°C"]
    chosen_bin = bin_locations[count % len(bin_locations)]

    inventory = WarehouseInventory(
        sku_code=sku_code,
        production_batch_id=batch.id,
        product_id=batch.product_id,
        batch_code=batch.batch_code,
        product_name=batch.product_name,
        initial_quantity=qty,
        available_quantity=qty,
        allocated_quantity=0.0,
        unit=batch.unit or "Thùng",
        unit_price=240000.0,
        storage_bin=chosen_bin,
        pallet_code=f"PLT-2026-{count:03d}",
        storage_temperature="20-25°C Khô thoáng",
        mfg_date=mfg,
        expiry_date=exp,
        status="NORMAL",
        audited_by_user_id=user_id,
        received_at=datetime.datetime.utcnow()
    )
    db.add(inventory)

    # Trigger notification alert for newly received finished inventory
    alert = NotificationAlert(
        title=f"Nhập kho thành phẩm: {batch.product_name}",
        message=f"Lô {batch.batch_code} ({qty} {batch.unit}) đã nhập thành công vào vị trí {chosen_bin} (Hạn dùng: {exp.strftime('%d/%m/%Y')}).",
        module="Warehouse",
        severity="INFO",
        reference_type="batch",
        reference_id=batch.batch_code
    )
    db.add(alert)
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Đã nhập kho thành phẩm lô {batch.batch_code} vào hệ thống tồn kho FEFO",
        "data": inventory.to_dict()
    }), 201


@warehouse_bp.route('/api/warehouse/inventory', methods=['GET'])
@login_required
def get_inventory():
    """
    Warehouse inventory card grid in strict FEFO (First Expired, First Out) order:
    nearest expiry first (ORDER BY expiry_date ASC).
    Calculates urgency pill: EXPIRING_SOON (red), ATTENTION (amber), FRESH (green).
    """
    db = get_db()
    items = db.query(WarehouseInventory).order_by(WarehouseInventory.expiry_date.asc()).all()

    # Automatically check for expiring soon items and log alerts
    now = datetime.datetime.utcnow()
    for item in items:
        days = item.days_to_expiry
        if days <= 15 and item.status != 'EXPIRING_SOON':
            item.status = 'EXPIRING_SOON'
            # Check if alert already logged
            exists_alert = db.query(NotificationAlert).filter_by(
                reference_id=item.batch_code,
                title="Cảnh báo FEFO: Hàng cận hạn sử dụng"
            ).first()
            if not exists_alert:
                alert = NotificationAlert(
                    title="Cảnh báo FEFO: Hàng cận hạn sử dụng",
                    message=f"Lô thành phẩm {item.batch_code} ({item.product_name}) chỉ còn {days} ngày hết hạn!",
                    module="Warehouse",
                    severity="CRITICAL" if days <= 7 else "WARNING",
                    reference_type="inventory",
                    reference_id=item.batch_code
                )
                db.add(alert)
    db.commit()

    return jsonify({
        "success": True,
        "count": len(items),
        "data": [item.to_dict() for item in items]
    })


@warehouse_bp.route('/api/warehouse/customers', methods=['GET', 'POST'])
@login_required
def handle_customers():
    db = get_db()
    if request.method == 'POST':
        payload = request.get_json() or {}
        code = f"CUST-00{db.query(Customer).count() + 1}"
        cust = Customer(
            customer_code=code,
            name=payload.get('name'),
            tax_id=payload.get('tax_id'),
            contact_person=payload.get('contact_person'),
            phone=payload.get('phone'),
            email=payload.get('email'),
            delivery_address=payload.get('delivery_address'),
            city=payload.get('city', 'Hà Nội')
        )
        db.add(cust)
        db.commit()
        return jsonify({"success": True, "data": cust.to_dict()}), 201

    customers = db.query(Customer).order_by(Customer.id.asc()).all()
    return jsonify({
        "success": True,
        "count": len(customers),
        "data": [c.to_dict() for c in customers]
    })


@warehouse_bp.route('/api/warehouse/dispatches', methods=['GET'])
@login_required
def get_dispatches():
    """
    Returns card grid data for outbound dispatch orders.
    Shows carrier, license plate, driver, cold-chain sensor chip, and status pill.
    """
    db = get_db()
    dispatches = db.query(Dispatch).order_by(Dispatch.id.desc()).all()
    return jsonify({
        "success": True,
        "count": len(dispatches),
        "data": [d.to_dict() for d in dispatches]
    })


@warehouse_bp.route('/api/warehouse/dispatches', methods=['POST'])
@login_required
def create_dispatch():
    """
    Create outbound dispatch order with LIVE INVENTORY DECREMENT (FEFO allocation).
    """
    db = get_db()
    payload = request.get_json() or {}
    customer_id = payload.get('customer_id')
    items_data = payload.get('items', [])
    carrier_name = payload.get('carrier_name', 'Đội xe lạnh Nhà Máy FoodMan')
    license_plate = payload.get('license_plate', '29C-881.99')
    driver_name = payload.get('driver_name', 'Bùi Văn Hùng')
    user_id = session.get('user', {}).get('id')

    customer = db.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        return jsonify({"success": False, "error": "Vui lòng chọn khách hàng nhận hàng"}), 400

    if not items_data:
        return jsonify({"success": False, "error": "Vui lòng chọn ít nhất 1 mặt hàng xuất kho"}), 400

    # Validate inventory availability and perform LIVE DECREMENT
    allocated_items = []
    total_packages = 0.0
    total_amount = 0.0

    for item_req in items_data:
        inventory_id = item_req.get('inventory_id')
        req_qty = float(item_req.get('quantity', 0))

        if req_qty <= 0:
            continue

        inv = db.query(WarehouseInventory).filter_by(id=inventory_id).first()
        if not inv:
            return jsonify({"success": False, "error": f"Không tìm thấy tồn kho ID {inventory_id}"}), 400

        if inv.available_quantity < req_qty:
            return jsonify({
                "success": False,
                "error": f"Tồn kho khả dụng không đủ cho {inv.product_name} (Lô {inv.batch_code}). Khả dụng: {inv.available_quantity}, Yêu cầu: {req_qty}"
            }), 400

        # Live decrement from available stock
        inv.available_quantity -= req_qty
        inv.allocated_quantity += req_qty
        subtotal = req_qty * inv.unit_price

        allocated_items.append({
            "inventory": inv,
            "quantity": req_qty,
            "unit": inv.unit,
            "unit_price": inv.unit_price,
            "subtotal": subtotal
        })

        total_packages += req_qty
        total_amount += subtotal

    # Create dispatch
    count = db.query(Dispatch).count() + 1
    dispatch_code = f"DSP-2026-{count:03d}"

    new_dispatch = Dispatch(
        dispatch_code=dispatch_code,
        customer_id=customer.id,
        dispatched_by_id=user_id,
        destination=customer.delivery_address,
        carrier_name=carrier_name,
        license_plate=license_plate,
        driver_name=driver_name,
        driver_phone="0978.555.234",
        temp_sensor_celsius=3.8,
        temp_spec_range="2.0°C - 6.0°C",
        status="IN_TRANSIT",
        total_packages=total_packages,
        total_amount=total_amount,
        scheduled_departure=datetime.datetime.utcnow(),
        notes=payload.get('notes', 'Xuất kho giao hàng theo chuẩn chuỗi cung ứng lạnh FEFO')
    )
    db.add(new_dispatch)
    db.flush()

    # Add items
    for alloc in allocated_items:
        inv = alloc["inventory"]
        d_item = DispatchItem(
            dispatch_id=new_dispatch.id,
            inventory_id=inv.id,
            product_id=inv.product_id,
            batch_code=inv.batch_code,
            quantity=alloc["quantity"],
            unit=alloc["unit"],
            unit_price=alloc["unit_price"],
            subtotal=alloc["subtotal"]
        )
        db.add(d_item)

    # Log notification alert
    alert = NotificationAlert(
        title=f"Khởi hành xe xuất kho: {dispatch_code}",
        message=f"Chuyến xe {license_plate} (Tài xế: {driver_name}) đã xuất kho vận chuyển {total_packages} kiện đến {customer.name}.",
        module="Warehouse",
        severity="INFO",
        reference_type="dispatch",
        reference_id=dispatch_code
    )
    db.add(alert)
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Tạo thành công lệnh xuất kho {dispatch_code} và đã trừ tồn kho trực tiếp",
        "data": new_dispatch.to_dict()
    }), 201


@warehouse_bp.route('/api/warehouse/dispatches/<int:dispatch_id>/advance-status', methods=['POST'])
@login_required
def advance_dispatch_status(dispatch_id):
    """
    Advance dispatch order from IN_TRANSIT to DELIVERED.
    """
    db = get_db()
    dispatch = db.query(Dispatch).filter_by(id=dispatch_id).first()
    if not dispatch:
        return jsonify({"success": False, "error": "Dispatch not found"}), 404

    payload = request.get_json() or {}
    new_status = payload.get('status', 'DELIVERED')
    dispatch.status = new_status
    if new_status == 'DELIVERED':
        dispatch.completed_at = datetime.datetime.utcnow()

    db.commit()
    return jsonify({
        "success": True,
        "message": f"Đã cập nhật trạng thái đơn vận chuyển {dispatch.dispatch_code} thành {new_status}",
        "data": dispatch.to_dict()
    })
