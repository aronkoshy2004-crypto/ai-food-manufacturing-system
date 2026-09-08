"""
FoodMan AI Assistant (Chatbot) Routes & Knowledge Engine
Phase 6 — Advanced Features & Polish
Provides domain-aware intelligent assistance across:
- Real-time inventory & FEFO status
- End-to-end 7-tier traceability queries
- QC inspection queue, Lab pass rates & YOLO defect reports
- Production batch progress & BOM availability recommendations
- Active cold-chain dispatches & temperature IoT sensors
- Open system alerts & critical events
"""
import re
import datetime
from flask import Blueprint, request, jsonify, session
from models import get_db
from models.user import User
from models.procurement import RawMaterialLot, RawMaterial, Supplier, PurchaseOrder
from models.qc import QCSample, QCTest, QCDecision, AIInspection, DetectedDefect
from models.production import ProductionBatch, Product, Recipe, RecipeMaterial
from models.warehouse import WarehouseInventory, Dispatch, NotificationAlert
from routes.auth import login_required, get_current_user

chatbot_bp = Blueprint('chatbot', __name__)

@chatbot_bp.route('/api/chatbot/query', methods=['POST'])
@login_required
def query_chatbot():
    data = request.get_json() or {}
    user_query = data.get('message', '').strip()
    if not user_query:
        return jsonify({
            "success": False,
            "reply": "Xin chào! Tôi là Trợ lý AI FoodMan. Bạn có thể hỏi tôi về tồn kho FEFO, truy xuất nguồn gốc, hàng chờ QC, tiến độ mẻ sản xuất hoặc cảnh báo chuỗi lạnh.",
            "suggestions": [
                "Kiểm tra tồn kho FEFO",
                "Có bao nhiêu lô chờ QC?",
                "Khả năng sản xuất sản phẩm nào?",
                "Cảnh báo mở gần nhất"
            ]
        })

    q_lower = user_query.lower()
    db = get_db()
    reply = ""
    suggestions = []
    entities = []

    # -------------------------------------------------------------------------
    # 1. TRACEABILITY QUERY (Mã lô, mã batch, mã xe, mã PO)
    # -------------------------------------------------------------------------
    code_match = re.search(r'(LOT-[\w-]+|RAW-LOT-[\w-]+|DSP-[\w-]+|PO-[\w-]+|GRN-[\w-]+|INV-[\w-]+)', user_query, re.IGNORECASE)
    if code_match or any(w in q_lower for w in ['truy xuất', 'trace', 'nguồn gốc', 'mắt xích']):
        target_code = code_match.group(1).upper() if code_match else None
        
        if target_code:
            # Check if it's a production batch
            batch = db.query(ProductionBatch).filter(ProductionBatch.batch_code.ilike(f"%{target_code}%")).first()
            if batch:
                prod_name = batch.product.name if batch.product else "Thành phẩm"
                reply = (
                    f"### 🔍 Kết Quả Truy Xuất Lô Sản Xuất: `{batch.batch_code}`\n\n"
                    f"- **Sản phẩm:** {prod_name}\n"
                    f"- **Trạng thái:** `{batch.status}` | **Sản lượng:** {batch.actual_quantity or batch.target_quantity:,} {batch.unit}\n"
                    f"- **Dây chuyền:** {batch.line_name or 'Line A1 - Tetra Pak'}\n"
                    f"- **Nguyên liệu tiêu thụ:** {len(batch.consumed_materials)} lô nguyên liệu đạt chuẩn QC\n"
                    f"- **Hạn sử dụng:** {batch.expiry_date.strftime('%d/%m/%Y') if batch.expiry_date else 'N/A'}\n\n"
                    f"👉 [Xem chuỗi 7 mắt xích toàn trình](/traceability?q={batch.batch_code})"
                )
                suggestions = ["Xem lệnh xuất kho của lô này", "Kiểm tra kết quả QC nguyên liệu", "Tồn kho FEFO"]
                return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

            # Check if it's a raw material lot
            rm_lot = db.query(RawMaterialLot).filter(RawMaterialLot.lot_number.ilike(f"%{target_code}%")).first()
            if rm_lot:
                reply = (
                    f"### 🔍 Kết Quả Truy Xuất Lô Nguyên Liệu: `{rm_lot.lot_number}`\n\n"
                    f"- **Nguyên liệu:** {rm_lot.material_name} ({rm_lot.category or 'Nguyên liệu'})\n"
                    f"- **Nhà cung cấp:** {rm_lot.supplier_name} (Mã: {rm_lot.supplier.code if rm_lot.supplier else 'N/A'})\n"
                    f"- **Khối lượng nhận:** {rm_lot.quantity} {rm_lot.unit}\n"
                    f"- **Trạng thái QC:** `{rm_lot.qc_status}`\n\n"
                    f"👉 [Chi tiết kiểm định và truy xuất](/traceability?q={rm_lot.lot_number})"
                )
                suggestions = ["Xem các mẻ đã sử dụng lô này", "Kiểm tra báo cáo Lab & AI", "Danh sách lô chờ QC"]
                return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

            # Check if it's a dispatch
            disp = db.query(Dispatch).filter(Dispatch.dispatch_code.ilike(f"%{target_code}%")).first()
            if disp:
                reply = (
                    f"### 🚚 Lệnh Xuất Kho & Chuỗi Lạnh: `{disp.dispatch_code}`\n\n"
                    f"- **Khách hàng:** {disp.customer.name if disp.customer else 'Khách hàng'}\n"
                    f"- **Biển số xe / Lái xe:** {disp.license_plate} - {disp.driver_name}\n"
                    f"- **Trạng thái:** `{disp.status}` | **Khối lượng:** {disp.total_packages} Thùng\n"
                    f"- **Nhiệt độ cảm biến lạnh:** `❄ {disp.temp_sensor_celsius}°C` (Tiêu chuẩn: {disp.temp_spec_range})\n\n"
                    f"👉 [Truy xuất nguồn gốc chuyến hàng](/traceability?q={disp.dispatch_code})"
                )
                suggestions = ["Kiểm tra vị trí giao hàng", "Báo cáo tuân thủ chuỗi lạnh", "Tồn kho FEFO"]
                return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

        # Generic traceability guidance
        reply = (
            "### 🌐 Hệ Thống Truy Xuất Nguồn Gốc Toàn Trình (7 Tầng)\n\n"
            "Tôi có thể hỗ trợ bạn tra cứu mọi thông tin theo mã định danh:\n"
            "- **Mã Lô Sản Xuất:** e.g. `LOT-2026-005`, `LOT-2026-089`\n"
            "- **Mã Lô Nguyên Liệu:** e.g. `RAW-LOT-512`, `LOT-RM-2026-697`\n"
            "- **Mã Lệnh Xuất Kho:** e.g. `DSP-2026-004`, `DSP-2026-041`\n\n"
            "👉 [Mở màn hình Truy xuất nguồn gốc](/traceability)"
        )
        suggestions = ["Truy xuất LOT-2026-005", "Truy xuất RAW-LOT-512", "Truy xuất DSP-2026-004"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 2. INVENTORY & FEFO QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['tồn kho', 'kho', 'inventory', 'fefo', 'hết hạn', 'cận hạn']):
        inventories = db.query(WarehouseInventory).order_by(WarehouseInventory.expiry_date.asc()).all()
        total_qty = sum(i.available_quantity for i in inventories)
        expiring_soon = [i for i in inventories if i.days_to_expiry <= 15]

        inv_items_text = ""
        for i in inventories[:5]:
            urgency = "🔴 Cận hạn" if i.days_to_expiry <= 15 else ("🟡 Chú ý" if i.days_to_expiry <= 45 else "🟢 Tươi mới")
            inv_items_text += f"- **{i.product.name if i.product else i.sku_code}** ({i.batch_code}): {i.available_quantity:,} {i.unit} — Vị trí: `{i.storage_bin}` — Còn {i.days_to_expiry} ngày ({urgency})\n"

        reply = (
            f"### 📦 Báo Cáo Tồn Kho Thành Phẩm FEFO\n\n"
            f"- **Tổng tồn kho khả dụng:** `{total_qty:,.0f} Thùng`\n"
            f"- **Lô cận hạn (≤ 15 ngày):** `{len(expiring_soon)} Lô` ⚠\n\n"
            f"**Danh sách các lô ưu tiên xuất kho theo FEFO:**\n"
            f"{inv_items_text}\n"
            f"👉 [Xem bảng tồn kho FEFO chi tiết](/warehouse?view=inventory)"
        )
        suggestions = ["Tạo lệnh xuất kho cho hàng cận hạn", "Khả năng sản xuất bổ sung", "Cảnh báo mở"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 3. QC QUEUE & LAB / YOLO AI QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['qc', 'kiểm định', 'lab', 'phòng lab', 'yolo', 'khuyết tật', 'hàng chờ']):
        pending_lots = db.query(RawMaterialLot).filter(
            (RawMaterialLot.qc_status == 'PENDING_QC') | (RawMaterialLot.status == 'PENDING')
        ).all()
        recent_decisions = db.query(QCDecision).order_by(QCDecision.id.desc()).limit(3).all()

        pending_text = ""
        for l in pending_lots[:4]:
            pending_text += f"- **Lô {l.lot_number}**: {l.material_name} ({l.quantity} {l.unit}) từ NCC *{l.supplier_name}*\n"

        dec_text = ""
        for d in recent_decisions:
            icon = "✅" if d.final_status == 'APPROVED' else ("⛔" if d.final_status == 'REJECTED' else "⏸")
            lot_num = d.raw_material_lot.lot_number if d.raw_material_lot else f"Lô #{d.raw_material_lot_id}"
            reason_snip = d.reason[:45] if d.reason else "Đã duyệt"
            dec_text += f"- {icon} **{lot_num}**: `{d.final_status}` — *\"{reason_snip}...\"*\n"

        reply = (
            f"### 🔬 Tình Hình Kiểm Định Chất Lượng (QC & YOLO AI)\n\n"
            f"- **Hàng chờ kiểm nghiệm:** `{len(pending_lots)} lô nguyên liệu` đang chờ duyệt.\n"
            f"- **Nguyên tắc an toàn:** AI YOLO chỉ đóng vai trò khuyến nghị — **100% quyết định do chuyên viên QC xác nhận**.\n\n"
            f"**Các lô đang chờ kiểm định:**\n"
            f"{pending_text or 'Hiện không có lô nào tồn đọng.'}\n\n"
            f"**Phê duyệt gần nhất:**\n"
            f"{dec_text}\n"
            f"👉 [Đến màn hình Hàng chờ QC](/qc?view=queue)"
        )
        suggestions = ["Xem thư viện COA", "Đề xuất sản xuất theo lô đã duyệt", "Truy xuất kết quả Lab"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 4. PRODUCTION & BOM AVAILABILITY QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['sản xuất', 'bom', 'mẻ', 'công thức', 'khả năng sản xuất', 'đề xuất']):
        active_batches = db.query(ProductionBatch).filter_by(status='IN_PROGRESS').all()
        products = db.query(Product).all()

        active_text = ""
        for b in active_batches:
            active_text += f"- **{b.batch_code}**: {b.product.name if b.product else 'Sản phẩm'} — Sản lượng mục tiêu: {b.target_quantity:,} {b.unit} (Line: {b.line_name})\n"

        reply = (
            f"### 🏭 Kế Hoạch & Tiến Độ Sản Xuất\n\n"
            f"- **Mẻ sản xuất đang vận hành:** `{len(active_batches)} mẻ` trên dây chuyền tiệt trùng UHT & chiết rót.\n"
            f"- **Danh mục công thức (BOM):** `{len(products)} sản phẩm tiêu chuẩn`.\n\n"
            f"**Lô sản xuất đang chạy:**\n"
            f"{active_text or 'Dây chuyền đang sẵn sàng nhận lệnh mới.'}\n\n"
            f"👉 [Xem Đề xuất sản xuất & Kế hoạch BOM](/production?view=recommendations)\n"
            f"👉 [Xem Chi tiết tiến độ 5 công đoạn](/production?view=batches)"
        )
        suggestions = ["Khởi tạo mẻ sản xuất mới", "Kiểm tra tồn kho nguyên liệu", "Báo cáo năng suất"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 5. DISPATCHES & COLD-CHAIN IOT QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['xuất kho', 'xe', 'chuyến', 'vận tải', 'chuỗi lạnh', 'nhiệt độ']):
        dispatches = db.query(Dispatch).order_by(Dispatch.id.desc()).limit(4).all()
        disp_text = ""
        for d in dispatches:
            disp_text += f"- **{d.dispatch_code}** ➔ *{d.customer.name if d.customer else 'Khách hàng'}*: {d.total_packages} Thùng | Xe `{d.license_plate}` | `❄ {d.temp_sensor_celsius}°C` ({d.status})\n"

        reply = (
            f"### 🚛 Điều Phối Vận Tải & Giám Sát Chuỗi Lạnh\n\n"
            f"- **Tiêu chuẩn nhiệt độ xe lạnh:** `2.0°C - 6.0°C` (Kiểm soát realtime qua cảm biến IoT)\n\n"
            f"**Các chuyến xe gần nhất:**\n"
            f"{disp_text}\n"
            f"👉 [Đến màn hình Quản lý Lệnh xuất kho](/warehouse?view=dispatches)"
        )
        suggestions = ["Tạo lệnh xuất kho mới", "Báo cáo xu hướng xuất kho", "Kiểm tra tồn kho FEFO"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 6. ALERTS & NOTIFICATIONS QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['cảnh báo', 'alert', 'nguy cơ', 'sự cố', 'thông báo']):
        unread_alerts = db.query(NotificationAlert).filter_by(is_read=False).order_by(NotificationAlert.id.desc()).limit(5).all()
        alert_text = ""
        for a in unread_alerts:
            icon = "🔴" if a.severity == 'CRITICAL' else "🟡"
            alert_text += f"- {icon} **[{a.module}] {a.title}**: {a.message}\n"

        reply = (
            f"### ⚠ Trung Tâm Cảnh Báo Hệ Thống\n\n"
            f"- **Cảnh báo đang mở chưa đọc:** `{len(unread_alerts)} cảnh báo`\n\n"
            f"{alert_text or 'Hiện không có cảnh báo nghiêm trọng nào đang mở. Hệ thống ổn định 100%.'}\n\n"
            f"👉 [Mở Trung tâm cảnh báo đầy đủ](/alerts)"
        )
        suggestions = ["Quét kiểm tra hệ thống ngay", "Xem báo cáo hiệu suất", "Kiểm tra hàng cận hạn"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 7. DEFAULT FALLBACK / HELP
    # -------------------------------------------------------------------------
    reply = (
        f"### 🤖 Trợ Lý AI Điều Hành FoodMan\n\n"
        f"Tôi đã sẵn sàng hỗ trợ bạn theo dõi và điều hành toàn diện nhà máy:\n\n"
        f"1. **Tồn kho & Hạn dùng (FEFO):** Hỏi *\"Kiểm tra tồn kho thành phẩm?\"* hoặc *\"Lô nào sắp hết hạn?\"*\n"
        f"2. **Truy xuất nguồn gốc:** Nhập trực tiếp mã lô, e.g. `LOT-2026-005`, `RAW-LOT-512`, `DSP-2026-004`\n"
        f"3. **Kiểm định chất lượng (QC):** Hỏi *\"Có bao nhiêu lô chờ QC?\"* hoặc *\"Kết quả kiểm định gần nhất?\"*\n"
        f"4. **Sản xuất & BOM:** Hỏi *\"Khả năng sản xuất sản phẩm nào?\"* hoặc *\"Mẻ sản xuất đang chạy?\"*\n"
        f"5. **Vận tải & Chuỗi lạnh:** Hỏi *\"Nhiệt độ các xe lạnh hiện tại?\"*\n"
        f"6. **Cảnh báo mở:** Hỏi *\"Hôm nay có cảnh báo gì cần xử lý?\"*"
    )
    suggestions = [
        "Kiểm tra tồn kho FEFO",
        "Có bao nhiêu lô chờ QC?",
        "Truy xuất LOT-2026-005",
        "Cảnh báo mở gần nhất"
    ]

    return jsonify({
        "success": True,
        "reply": reply,
        "suggestions": suggestions
    })
