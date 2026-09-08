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
            "reply": "Hello! I am your FoodMan AI Assistant. You can ask me about FEFO inventory, traceability chains, QC queue, production batches, or cold-chain telemetry.",
            "suggestions": [
                "Check FEFO inventory",
                "How many lots in QC queue?",
                "Which products can be produced?",
                "Latest active alerts"
            ]
        })

    q_lower = user_query.lower()
    db = get_db()
    reply = ""
    suggestions = []

    # -------------------------------------------------------------------------
    # 1. TRACEABILITY QUERY (Batch code, Lot code, Truck/Dispatch code, PO code)
    # -------------------------------------------------------------------------
    code_match = re.search(r'(LOT-[\w-]+|RAW-LOT-[\w-]+|DSP-[\w-]+|PO-[\w-]+|GRN-[\w-]+|INV-[\w-]+)', user_query, re.IGNORECASE)
    if code_match or any(w in q_lower for w in ['trace', 'traceability', 'provenance', 'chain', 'truy xuất', 'nguồn gốc']):
        target_code = code_match.group(1).upper() if code_match else None
        
        if target_code:
            # Check if it's a production batch
            batch = db.query(ProductionBatch).filter(ProductionBatch.batch_code.ilike(f"%{target_code}%")).first()
            if batch:
                prod_name = batch.product.name if batch.product else "Finished Product"
                reply = (
                    f"### 🔍 Traceability Results for Batch: `{batch.batch_code}`\n\n"
                    f"- **Product:** {prod_name}\n"
                    f"- **Status:** `{batch.status}` | **Yield:** {batch.actual_quantity or batch.target_quantity:,} {batch.unit}\n"
                    f"- **Line:** {batch.line_name or 'Line A1 - Tetra Pak'}\n"
                    f"- **Consumed Materials:** {len(batch.consumed_materials)} QC-approved raw material lots\n"
                    f"- **Expiry Date:** {batch.expiry_date.strftime('%Y-%m-%d') if batch.expiry_date else 'N/A'}\n\n"
                    f"👉 [View Full 7-Tier Value Chain](/traceability?q={batch.batch_code})"
                )
                suggestions = ["View dispatch order for this batch", "Inspect raw material QC results", "FEFO inventory"]
                return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

            # Check if it's a raw material lot
            rm_lot = db.query(RawMaterialLot).filter(RawMaterialLot.lot_number.ilike(f"%{target_code}%")).first()
            if rm_lot:
                reply = (
                    f"### 🔍 Traceability Results for Raw Material Lot: `{rm_lot.lot_number}`\n\n"
                    f"- **Material:** {rm_lot.material_name} ({rm_lot.category or 'Raw Material'})\n"
                    f"- **Supplier:** {rm_lot.supplier_name} (Code: {rm_lot.supplier.code if rm_lot.supplier else 'N/A'})\n"
                    f"- **Intake Quantity:** {rm_lot.quantity} {rm_lot.unit}\n"
                    f"- **QC Status:** `{rm_lot.qc_status}`\n\n"
                    f"👉 [Detailed Inspection & Chain](/traceability?q={rm_lot.lot_number})"
                )
                suggestions = ["Batches using this lot", "Check Lab & AI defect report", "QC pending lots"]
                return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

            # Check if it's a dispatch
            disp = db.query(Dispatch).filter(Dispatch.dispatch_code.ilike(f"%{target_code}%")).first()
            if disp:
                reply = (
                    f"### 🚚 Dispatch Order & Cold Chain: `{disp.dispatch_code}`\n\n"
                    f"- **Customer:** {disp.customer.name if disp.customer else 'Customer'}\n"
                    f"- **Truck Plate / Driver:** {disp.license_plate} - {disp.driver_name}\n"
                    f"- **Status:** `{disp.status}` | **Quantity:** {disp.total_packages} Cartons\n"
                    f"- **Reefer Temp Sensor:** `❄ {disp.temp_sensor_celsius}°C` (Spec range: {disp.temp_spec_range})\n\n"
                    f"👉 [Trace shipment provenance](/traceability?q={disp.dispatch_code})"
                )
                suggestions = ["Check delivery destination", "Cold-chain compliance report", "FEFO inventory"]
                return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

        # Generic traceability guidance
        reply = (
            "### 🌐 End-to-End 7-Tier Traceability System\n\n"
            "I can retrieve full farm-to-fork records by tracking ID:\n"
            "- **Production Batch Code:** e.g. `LOT-2026-005`, `LOT-2026-089`\n"
            "- **Raw Material Lot:** e.g. `RAW-LOT-512`, `LOT-RM-2026-697`\n"
            "- **Outbound Dispatch Code:** e.g. `DSP-2026-004`, `DSP-2026-041`\n\n"
            "👉 [Open Traceability Explorer](/traceability)"
        )
        suggestions = ["Trace LOT-2026-005", "Trace RAW-LOT-512", "Trace DSP-2026-004"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 2. INVENTORY & FEFO QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['inventory', 'fefo', 'stock', 'warehouse', 'expiry', 'expiring', 'tồn kho', 'kho', 'hết hạn', 'cận hạn']):
        inventories = db.query(WarehouseInventory).order_by(WarehouseInventory.expiry_date.asc()).all()
        total_qty = sum(i.available_quantity for i in inventories)
        expiring_soon = [i for i in inventories if i.days_to_expiry <= 15]

        inv_items_text = ""
        for i in inventories[:5]:
            urgency = "🔴 Urgent" if i.days_to_expiry <= 15 else ("🟡 Attention" if i.days_to_expiry <= 45 else "🟢 Fresh")
            inv_items_text += f"- **{i.product.name if i.product else i.sku_code}** ({i.batch_code}): {i.available_quantity:,} {i.unit} — Bin: `{i.storage_bin}` — {i.days_to_expiry} days remaining ({urgency})\n"

        reply = (
            f"### 📦 FEFO Warehouse Inventory Report\n\n"
            f"- **Total Available Finished Goods:** `{total_qty:,.0f} Cartons`\n"
            f"- **Expiring Soon Lots (≤ 15 days):** `{len(expiring_soon)} lots` ⚠\n\n"
            f"**High Priority Lots (FEFO Sorted):**\n"
            f"{inv_items_text}\n"
            f"👉 [View Detailed FEFO Inventory Grid](/warehouse?view=inventory)"
        )
        suggestions = ["Create dispatch for expiring stock", "Check BOM produceability", "Active alerts"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 3. QC QUEUE & LAB / YOLO AI QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['qc', 'quality', 'lab', 'inspection', 'yolo', 'defect', 'queue', 'kiểm định', 'hàng chờ']):
        pending_lots = db.query(RawMaterialLot).filter(
            (RawMaterialLot.qc_status == 'PENDING_QC') | (RawMaterialLot.status == 'PENDING')
        ).all()
        recent_decisions = db.query(QCDecision).order_by(QCDecision.id.desc()).limit(3).all()

        pending_text = ""
        for l in pending_lots[:4]:
            pending_text += f"- **Lot {l.lot_number}**: {l.material_name} ({l.quantity} {l.unit}) from supplier *{l.supplier_name}*\n"

        dec_text = ""
        for d in recent_decisions:
            icon = "✅" if d.final_status == 'APPROVED' else ("⛔" if d.final_status == 'REJECTED' else "⏸")
            lot_num = d.raw_material_lot.lot_number if d.raw_material_lot else f"Lot #{d.raw_material_lot_id}"
            reason_snip = d.reason[:45] if d.reason else "Approved"
            dec_text += f"- {icon} **{lot_num}**: `{d.final_status}` — *\"{reason_snip}...\"*\n"

        reply = (
            f"### 🔬 Quality Control Status (QC & YOLO AI)\n\n"
            f"- **Pending Inspection Queue:** `{len(pending_lots)} raw material lots` waiting for review.\n"
            f"- **Safety Principle:** AI YOLO is assistive only — **100% of final gate approvals are signed off by human QC officers**.\n\n"
            f"**Current Lots Awaiting Inspection:**\n"
            f"{pending_text or 'No backlog. All lots have been processed.'}\n\n"
            f"**Recent QC Decisions:**\n"
            f"{dec_text}\n"
            f"👉 [Open QC Queue Review](/qc?view=queue)"
        )
        suggestions = ["View COA Library", "Production recommendations for approved lots", "Lab test records"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 4. PRODUCTION & BOM AVAILABILITY QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['production', 'batch', 'bom', 'recipe', 'produce', 'produceable', 'recommend', 'sản xuất', 'mẻ', 'công thức']):
        active_batches = db.query(ProductionBatch).filter_by(status='IN_PROGRESS').all()
        products = db.query(Product).all()

        active_text = ""
        for b in active_batches:
            active_text += f"- **{b.batch_code}**: {b.product.name if b.product else 'Product'} — Target: {b.target_quantity:,} {b.unit} (Line: {b.line_name})\n"

        reply = (
            f"### 🏭 Production Schedule & Progress\n\n"
            f"- **Active Production Batches:** `{len(active_batches)} batches` currently running on UHT & packaging lines.\n"
            f"- **Product Catalog (BOMs):** `{len(products)} standard recipes`.\n\n"
            f"**Live Running Batches:**\n"
            f"{active_text or 'Lines are clear and ready for the next scheduled batch.'}\n\n"
            f"👉 [View BOM Produceability Recommendations](/production?view=recommendations)\n"
            f"👉 [View 5-Stage Stepper Progress](/production?view=batches)"
        )
        suggestions = ["Create new production batch", "Check raw material stock", "Throughput report"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 5. DISPATCHES & COLD-CHAIN IOT QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['dispatch', 'shipment', 'delivery', 'truck', 'temperature', 'cold chain', 'reefer', 'xuất kho', 'vận tải', 'chuỗi lạnh']):
        dispatches = db.query(Dispatch).order_by(Dispatch.id.desc()).limit(4).all()
        disp_text = ""
        for d in dispatches:
            disp_text += f"- **{d.dispatch_code}** ➔ *{d.customer.name if d.customer else 'Customer'}*: {d.total_packages} Cartons | Truck `{d.license_plate}` | `❄ {d.temp_sensor_celsius}°C` ({d.status})\n"

        reply = (
            f"### 🚛 Logistics Fleet & Cold-Chain Monitoring\n\n"
            f"- **Reefer Temp Target:** `2.0°C - 6.0°C` (Real-time telemetry monitored via IoT sensors)\n\n"
            f"**Recent Dispatches:**\n"
            f"{disp_text}\n"
            f"👉 [Manage Outbound Dispatches](/warehouse?view=dispatches)"
        )
        suggestions = ["Create new dispatch order", "Dispatch trends report", "Check FEFO inventory"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 6. ALERTS & NOTIFICATIONS QUERY
    # -------------------------------------------------------------------------
    if any(w in q_lower for w in ['alert', 'alarm', 'warning', 'incident', 'notification', 'cảnh báo', 'thông báo']):
        unread_alerts = db.query(NotificationAlert).filter_by(is_read=False).order_by(NotificationAlert.id.desc()).limit(5).all()
        alert_text = ""
        for a in unread_alerts:
            icon = "🔴" if a.severity == 'CRITICAL' else "🟡"
            alert_text += f"- {icon} **[{a.module}] {a.title}**: {a.message}\n"

        reply = (
            f"### ⚠ System Notification Center\n\n"
            f"- **Unread Open Alerts:** `{len(unread_alerts)} alerts`\n\n"
            f"{alert_text or 'No critical alerts active. All systems are operating normally.'}\n\n"
            f"👉 [Open Alerts & Automation Rules](/alerts)"
        )
        suggestions = ["Run system check now", "View performance reports", "Check expiring stock"]
        return jsonify({"success": True, "reply": reply, "suggestions": suggestions})

    # -------------------------------------------------------------------------
    # 7. DEFAULT FALLBACK / HELP
    # -------------------------------------------------------------------------
    reply = (
        f"### 🤖 FoodMan Intelligent Assistant\n\n"
        f"I am ready to assist you with operations across the entire plant:\n\n"
        f"1. **Inventory & FEFO Expiry:** Ask *\"Check FEFO inventory\"* or *\"Which lots are expiring soon?\"*\n"
        f"2. **Traceability:** Search any tracking code, e.g. `LOT-2026-005`, `RAW-LOT-512`, `DSP-2026-004`\n"
        f"3. **Quality Control (QC):** Ask *\"How many lots in QC queue?\"* or *\"Latest inspection results\"*\n"
        f"4. **Production & BOM:** Ask *\"Which products can be produced?\"* or *\"Active batches running\"*\n"
        f"5. **Fleet & Cold Chain:** Ask *\"Current reefer temperature status\"*\n"
        f"6. **Alerts & Events:** Ask *\"Any open alerts requiring action?\"*"
    )
    suggestions = [
        "Check FEFO inventory",
        "How many lots in QC queue?",
        "Trace LOT-2026-005",
        "Latest active alerts"
    ]

    return jsonify({
        "success": True,
        "reply": reply,
        "suggestions": suggestions
    })
