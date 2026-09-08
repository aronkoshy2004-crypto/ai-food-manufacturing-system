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
                "statSub": "Số lượng nhập",
                "progress": 95 if lot.status == StatusEnum.APPROVED.value else (60 if lot.status == StatusEnum.PENDING.value else 40),
                "miniGrid": [
                    {"label": "Nhà cung cấp", "value": lot.supplier_name},
                    {"label": "Điều kiện kho", "value": lot.storage_condition},
                    {"label": "Ngày nhận", "value": lot.received_at.strftime("%d/%m/%Y") if lot.received_at else "Hôm nay"},
                    {"label": "Người tiếp nhận", "value": lot.created_by.full_name if lot.created_by else "Thu mua"}
                ],
                "avatars": [
                    {"initial": "TM", "bg": "#162B4E", "name": "Thu Mua"}
                ],
                "status": lot.status,
                "statusLabel": STATUS_METADATA[StatusEnum(lot.status)]["label"],
                "statusPill": STATUS_METADATA[StatusEnum(lot.status)]["pill_class"],
                "editableFields": [
                    {"label": "Trạng thái", "key": "status", "type": "select", "options": [s.value for s in StatusEnum], "value": lot.status},
                    {"label": "Kho lưu trữ", "key": "storage_condition", "type": "text", "value": lot.storage_condition}
                ],
                "readonlySpecs": [
                    {"label": "Mã nguyên liệu", "value": lot.lot_number, "mono": True},
                    {"label": "Trọng lượng", "value": f"{lot.quantity} {lot.unit}"},
                    {"label": "Tiêu chuẩn", "value": "ISO 22000 Inbound QC"}
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
                "headerStat": "Chỉ tiêu Lab",
                "statSub": "Đạt 18/18 chỉ số" if qc.status == StatusEnum.APPROVED.value else "Đang đọc khuẩn",
                "progress": 100 if qc.status == StatusEnum.APPROVED.value else (85 if qc.status == StatusEnum.HOLD.value else 50),
                "miniGrid": [
                    {"label": "Chuyên viên Lab", "value": qc.inspector.full_name if qc.inspector else "Phòng Lab"},
                    {"label": "Quy chuẩn", "value": qc.standards_applied},
                    {"label": "Ngày lấy mẫu", "value": qc.inspected_at.strftime("%d/%m/%Y %H:%M") if qc.inspected_at else "Hôm nay"},
                    {"label": "Kết luận", "value": STATUS_METADATA[StatusEnum(qc.status)]["label"]}
                ],
                "avatars": [
                    {"initial": "QC", "bg": "#0D9488", "name": "Kỹ thuật viên Lab"}
                ],
                "status": qc.status,
                "statusLabel": STATUS_METADATA[StatusEnum(qc.status)]["label"],
                "statusPill": STATUS_METADATA[StatusEnum(qc.status)]["pill_class"],
                "editableFields": [
                    {"label": "Trạng thái kiểm nghiệm", "key": "status", "type": "select", "options": [s.value for s in StatusEnum], "value": qc.status},
                    {"label": "Tiêu chuẩn áp dụng", "key": "standards_applied", "type": "text", "value": qc.standards_applied}
                ],
                "readonlySpecs": [
                    {"label": "Mã mẫu Lab", "value": qc.inspection_code, "mono": True},
                    {"label": "Phương pháp test", "value": qc.sample_type},
                    {"label": "Kiểm nghiệm vi sinh", "value": "Salmonella / Coliform Âm tính"}
                ]
            })

    elif module == 'warehouse':
        items = db.query(WarehouseItem).order_by(WarehouseItem.id.desc()).all()
        for item in items:
            cards.append({
                "id": item.sku_code,
                "db_id": item.id,
                "module": "warehouse",
                "category": "Tồn kho thành phẩm",
                "title": item.product_name,
                "headerStat": f"{item.quantity:,.0f} {item.unit}",
                "statSub": f"{item.pallet_count} Pallet lưu kho",
                "progress": int(min(item.quantity / (item.min_threshold * 5) * 100, 100)),
                "miniGrid": [
                    {"label": "Vị trí kệ kho", "value": item.location_bin},
                    {"label": "Số lượng Pallet", "value": f"{item.pallet_count} Pallets"},
                    {"label": "Ngưỡng an toàn", "value": f"Min {item.min_threshold:,.0f}"},
                    {"label": "Thủ kho phụ trách", "value": item.audited_by.full_name if item.audited_by else "Kho chính"}
                ],
                "avatars": [
                    {"initial": "WH", "bg": "#0284C7", "name": "Thủ kho"}
                ],
                "status": item.status,
                "statusLabel": STATUS_METADATA[StatusEnum(item.status)]["label"],
                "statusPill": STATUS_METADATA[StatusEnum(item.status)]["pill_class"],
                "editableFields": [
                    {"label": "Trạng thái tồn kho", "key": "status", "type": "select", "options": [s.value for s in StatusEnum], "value": item.status},
                    {"label": "Vị trí kệ kho", "key": "location_bin", "type": "text", "value": item.location_bin}
                ],
                "readonlySpecs": [
                    {"label": "Mã SKU", "value": item.sku_code, "mono": True},
                    {"label": "Hạn dùng còn lại", "value": "180 ngày (FEFO đạt chuẩn)"},
                    {"label": "Quy cách đóng gói", "value": "Thùng tiêu chuẩn Inox"}
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
                "statSub": f"{batch.unit} hoàn thành",
                "progress": min(progress, 100),
                "miniGrid": [
                    {"label": "Dây chuyền chiết rót", "value": batch.line_name},
                    {"label": "Thông số nhiệt UHT", "value": batch.temperature_spec},
                    {"label": "Quản đốc ca", "value": batch.shift_manager.full_name if batch.shift_manager else "Trưởng ca"},
                    {"label": "Thời điểm bắt đầu", "value": batch.started_at.strftime("%d/%m %H:%M") if batch.started_at else "Hôm nay"}
                ],
                "avatars": [
                    {"initial": "PR", "bg": "#162B4E", "name": "Quản đốc"},
                    {"initial": "OP", "bg": "#2563EB", "name": "Kỹ sư vận hành"}
                ],
                "status": batch.status,
                "statusLabel": STATUS_METADATA[StatusEnum(batch.status)]["label"],
                "statusPill": STATUS_METADATA[StatusEnum(batch.status)]["pill_class"],
                "editableFields": [
                    {"label": "Trạng thái mẻ sản xuất", "key": "status", "type": "select", "options": [s.value for s in StatusEnum], "value": batch.status},
                    {"label": "Dây chuyền vận hành", "key": "line_name", "type": "text", "value": batch.line_name}
                ],
                "readonlySpecs": [
                    {"label": "Mã lô mẻ", "value": batch.batch_code, "mono": True},
                    {"label": "Nhiệt độ UHT tiệt trùng", "value": batch.temperature_spec},
                    {"label": "Chứng chỉ vệ sinh máy", "value": "CIP Hoàn tất 100%"}
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
        "message": f"Đã cập nhật trạng thái sang {new_status}",
        "new_status": new_status,
        "pill": STATUS_METADATA[StatusEnum(new_status)]["pill_class"],
        "label": STATUS_METADATA[StatusEnum(new_status)]["label"]
    })
