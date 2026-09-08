"""
Food Man - Main Flask Application Factory & Server Entry Point
PRD Phase 0 to Phase 4 Complete Integration
"""
import os
import datetime
from flask import Flask
from config import Config
from models import init_db, get_db
from models.enums import RoleEnum, StatusEnum
from models.user import User
from models.schema_draft import (
    RawMaterialLot,
    QCInspection,
    WarehouseItem,
    DispatchOrder
)
from models.procurement import Supplier, RawMaterial, PurchaseOrder, PurchaseOrderItem
from models.qc import QCSample, QCTest, COADocument, InspectionImage, AIInspection, DetectedDefect, QCDecision
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
from models.warehouse import (
    WarehouseInventory,
    Customer,
    Dispatch,
    DispatchItem,
    AlertRule,
    NotificationAlert
)

from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.api import api_bp
from routes.procurement import procurement_bp
from routes.qc import qc_bp
from routes.production import production_bp
from routes.warehouse import warehouse_bp
from routes.traceability import traceability_bp
from routes.reports import reports_bp
from routes.chatbot import chatbot_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Database & Engine
    init_db(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(procurement_bp)
    app.register_blueprint(qc_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(warehouse_bp)
    app.register_blueprint(traceability_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(chatbot_bp)

    # Seed demo users & comprehensive domain data
    seed_initial_data()

    return app

def seed_initial_data():
    """Seeds users, suppliers, materials, lots, products, recipes, batches, warehouse, customers, and alerts."""
    db = get_db()

    # 1. Seed Users (Roles: Admin, Procurement, QC, Production, Warehouse)
    users_data = [
        {
            "email": "admin@foodman.vn",
            "password": "password123",
            "full_name": "Nguyễn Hoàng Minh",
            "role": RoleEnum.ADMIN.value,
            "avatar": "AD",
            "dept": "Ban Giám Đốc"
        },
        {
            "email": "procurement@foodman.vn",
            "password": "password123",
            "full_name": "Vũ Thu Thảo",
            "role": RoleEnum.PROCUREMENT.value,
            "avatar": "PR",
            "dept": "Phòng Thu Mua & Nguyên Liệu"
        },
        {
            "email": "qc@foodman.vn",
            "password": "password123",
            "full_name": "ThS. Phạm Thu Trang",
            "role": RoleEnum.QC.value,
            "avatar": "QC",
            "dept": "Phòng Kiểm Nghiệm Lab"
        },
        {
            "email": "production@foodman.vn",
            "password": "password123",
            "full_name": "Trần Minh Quân",
            "role": RoleEnum.PRODUCTION.value,
            "avatar": "TM",
            "dept": "Xưởng Chế Biến & Đóng Gói"
        },
        {
            "email": "warehouse@foodman.vn",
            "password": "password123",
            "full_name": "Hoàng Đình Tuấn",
            "role": RoleEnum.WAREHOUSE.value,
            "avatar": "WH",
            "dept": "Tổng Kho & Điều Phối Vận Tải"
        }
    ]

    for u in users_data:
        existing = db.query(User).filter_by(email=u["email"]).first()
        if not existing:
            new_user = User(
                email=u["email"],
                full_name=u["full_name"],
                role=u["role"],
                avatar_initials=u["avatar"],
                department=u["dept"]
            )
            new_user.set_password(u["password"])
            db.add(new_user)
    db.commit()

    user_admin = db.query(User).filter_by(email="admin@foodman.vn").first()
    user_proc = db.query(User).filter_by(email="procurement@foodman.vn").first()
    user_qc = db.query(User).filter_by(email="qc@foodman.vn").first()
    user_prod = db.query(User).filter_by(email="production@foodman.vn").first()
    user_wh = db.query(User).filter_by(email="warehouse@foodman.vn").first()

    # 2. Seed Suppliers
    if db.query(Supplier).count() == 0:
        db.add_all([
            Supplier(code="SUP-001", name="Nông trại Mộc Châu Farm Co.", contact_name="Trần Văn Hùng", email="mocchau@farm.vn", phone="0912.345.678", address="Mộc Châu, Sơn La", rating=4.9, status="APPROVED"),
            Supplier(code="SUP-002", name="Tetra Pak Thụy Điển", contact_name="Lars Lindqvist", email="contact@tetrapak.se", phone="028.3824.8888", address="Khu CN VSIP II, Bình Dương", rating=5.0, status="APPROVED"),
            Supplier(code="SUP-003", name="Đường Lam Sơn Thanh Hóa", contact_name="Lê Đình Thắng", email="sales@lasuco.vn", phone="0237.3861.234", address="Thọ Xuân, Thanh Hóa", rating=4.7, status="APPROVED"),
            Supplier(code="SUP-004", name="Fonterra Co-operative Group", contact_name="Sarah Jenkins", email="trade@fonterra.nz", phone="+64 9 374 9000", address="Auckland, New Zealand", rating=4.9, status="APPROVED")
        ])
        db.commit()

    sup_mocchau = db.query(Supplier).filter_by(code="SUP-001").first()
    sup_tetra = db.query(Supplier).filter_by(code="SUP-002").first()
    sup_lamson = db.query(Supplier).filter_by(code="SUP-003").first()

    # 3. Seed RawMaterials
    if db.query(RawMaterial).count() == 0:
        db.add_all([
            RawMaterial(code="RM-001", name="Sữa bò tươi Organic loại 1", category="Sữa tươi thô", standard_unit="Tấn", unit_weight="1,000 kg / bồn", storage_temp="Bồn vô trùng 3.5°C", shelf_life_days=3, min_stock_level=10.0),
            RawMaterial(code="RM-002", name="Màng tiệt trùng Tetra Brik Aseptic 250ml", category="Vật tư bao bì", standard_unit="Cuộn vỏ", unit_weight="5,000 hộp / cuộn", storage_temp="Kho khô 22°C", shelf_life_days=365, min_stock_level=50000.0),
            RawMaterial(code="RM-003", name="Đường mía tinh luyện RE Sucre", category="Gia vị & Phụ gia", standard_unit="Tấn", unit_weight="50 kg / bao", storage_temp="Kho khô Pallet C1", shelf_life_days=720, min_stock_level=5.0),
            RawMaterial(code="RM-004", name="Nước cam ép cô đặc Valencia 65° Brix", category="Nước ép cô đặc", standard_unit="Phuy", unit_weight="250 kg / phuy", storage_temp="Kho lạnh -18°C", shelf_life_days=365, min_stock_level=20.0)
        ])
        db.commit()

    rm_milk = db.query(RawMaterial).filter_by(code="RM-001").first()
    rm_tetra = db.query(RawMaterial).filter_by(code="RM-002").first()
    rm_sugar = db.query(RawMaterial).filter_by(code="RM-003").first()

    # 4. Seed PurchaseOrder with Items
    if db.query(PurchaseOrder).count() == 0:
        po1 = PurchaseOrder(
            po_number="PO-2026-001",
            supplier_id=sup_mocchau.id if sup_mocchau else 1,
            created_by_user_id=user_proc.id if user_proc else None,
            order_date=datetime.datetime.utcnow(),
            status="COMPLETED",
            total_amount=360000000.0,
            notes="Cung cấp sữa tươi organic tuần 36"
        )
        db.add(po1)
        db.flush()

        po_item1 = PurchaseOrderItem(
            purchase_order_id=po1.id,
            raw_material_id=rm_milk.id if rm_milk else 1,
            quantity_ordered=20.0,
            quantity_received=20.0,
            unit="Tấn",
            unit_price=18000000.0,
            subtotal=360000000.0
        )
        db.add(po_item1)
        db.commit()

    po_seed1 = db.query(PurchaseOrder).filter_by(po_number="PO-2026-001").first()

    # 5. Seed RawMaterialLots
    if db.query(RawMaterialLot).count() == 0:
        db.add_all([
            RawMaterialLot(
                lot_number="RAW-LOT-512",
                material_name="Sữa bò tươi Organic loại 1",
                category="Sữa tươi thô",
                supplier_name="Nông trại Mộc Châu Farm Co.",
                quantity=20.0,
                unit="Tấn",
                storage_condition="Bồn Silo vô trùng 3.5°C",
                status=StatusEnum.APPROVED.value,
                qc_status="APPROVED", # Approved by QC for Phase 3 Production availability check!
                unit_weight="1,000 kg / bồn",
                supplier_id=sup_mocchau.id if sup_mocchau else None,
                raw_material_id=rm_milk.id if rm_milk else None,
                purchase_order_id=po_seed1.id if po_seed1 else None,
                created_by_user_id=user_proc.id if user_proc else None
            ),
            RawMaterialLot(
                lot_number="RAW-LOT-513",
                material_name="Màng tiệt trùng Tetra Brik Aseptic 250ml",
                category="Vật tư bao bì",
                supplier_name="Tetra Pak Thụy Điển",
                quantity=450000.0,
                unit="Cuộn vỏ",
                storage_condition="Kho khô nhiệt độ 22°C",
                status=StatusEnum.APPROVED.value,
                qc_status="APPROVED", # Approved
                unit_weight="5,000 hộp / cuộn",
                supplier_id=sup_tetra.id if sup_tetra else None,
                raw_material_id=rm_tetra.id if rm_tetra else None,
                created_by_user_id=user_proc.id if user_proc else None
            ),
            RawMaterialLot(
                lot_number="RAW-LOT-514",
                material_name="Đường mía tinh luyện RE Sucre",
                category="Gia vị & Phụ gia",
                supplier_name="Đường Lam Sơn Thanh Hóa",
                quantity=15.0,
                unit="Tấn",
                storage_condition="Kho khô Pallet C1",
                status=StatusEnum.APPROVED.value,
                qc_status="APPROVED", # Approved
                unit_weight="50 kg / bao",
                supplier_id=sup_lamson.id if sup_lamson else None,
                raw_material_id=rm_sugar.id if rm_sugar else None,
                created_by_user_id=user_proc.id if user_proc else None
            ),
            RawMaterialLot(
                lot_number="RAW-LOT-515",
                material_name="Sữa bò tươi Organic loại 1",
                category="Sữa tươi thô",
                supplier_name="Nông trại Mộc Châu Farm Co.",
                quantity=12.0,
                unit="Tấn",
                storage_condition="Bồn Silo số 3",
                status=StatusEnum.PENDING.value,
                qc_status="PENDING_QC", # Pending in QC Queue
                unit_weight="1,000 kg / bồn",
                supplier_id=sup_mocchau.id if sup_mocchau else None,
                raw_material_id=rm_milk.id if rm_milk else None,
                created_by_user_id=user_proc.id if user_proc else None
            )
        ])
        db.commit()

    lot_milk = db.query(RawMaterialLot).filter_by(lot_number="RAW-LOT-512").first()

    # 6. Seed QC Decisions & AI Inspections for Lot 512
    if lot_milk and db.query(QCDecision).filter_by(raw_material_lot_id=lot_milk.id).count() == 0:
        sample = QCSample(
            sample_code="SMP-QC-512",
            raw_material_lot_id=lot_milk.id,
            sampler_user_id=user_qc.id if user_qc else None,
            storage_temp="4°C",
            sample_size="500ml / 5 mẫu ngẫu nhiên",
            notes="Lấy mẫu kiểm tra vi sinh & kháng sinh xe bồn"
        )
        db.add(sample)
        db.flush()

        db.add_all([
            QCTest(qc_sample_id=sample.id, parameter_name="Độ Brix", standard_spec=">= 11.5°Bx", measured_value="12.2°Bx", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Chỉ số pH", standard_spec="6.5 - 6.8 pH", measured_value="6.68 pH", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Kháng sinh Betalactam", standard_spec="Âm tính", measured_value="Âm tính", is_pass=True)
        ])

        db.add(COADocument(
            raw_material_lot_id=lot_milk.id,
            supplier_id=lot_milk.supplier_id,
            doc_number="COA-MC-2026-512",
            filename="COA-Organic-MocChau-Lot512.pdf",
            file_url="/static/docs/coa_mocchau_512.pdf",
            lab_accreditation="VILAS 102 / ISO 17025",
            is_verified=True
        ))

        img = InspectionImage(
            raw_material_lot_id=lot_milk.id,
            image_url="/static/img/sample_inspection.jpg",
            image_type="Niêm phong seal xe bồn"
        )
        db.add(img)
        db.flush()

        ai = AIInspection(
            inspection_image_id=img.id,
            raw_material_lot_id=lot_milk.id,
            model_version="YOLOv8x-FoodDefect-v2.1",
            inference_time_ms=42.5,
            total_defects_count=0,
            summary="Không phát hiện bất thường hay rò rỉ seal"
        )
        db.add(ai)

        db.add(QCDecision(
            raw_material_lot_id=lot_milk.id,
            decided_by_user_id=user_qc.id if user_qc else 1,
            final_status="APPROVED",
            reason="Đạt 100% chỉ tiêu vi sinh, hóa lý và COA hợp lệ",
            action_notes="Chấp thuận nhập kho sản xuất"
        ))
        db.commit()

    # 7. Seed Products, Recipes, and BOM (Phase 3)
    if db.query(Product).count() == 0:
        prod1 = Product(
            code="PROD-UHT-180",
            name="Sữa tiệt trùng Ít Đường 180ml UHT",
            category="Sữa tiệt trùng",
            unit="Thùng",
            shelf_life_days=180,
            target_batch_size=5000.0,
            storage_temp="Nhiệt độ phòng (22-28°C)",
            description="Thùng 48 hộp x 180ml, công nghệ tiệt trùng UHT Tetra Pak Thụy Điển"
        )
        prod2 = Product(
            code="PROD-ORG-1000",
            name="Sữa tươi tiệt trùng Nguyên Chất 1L",
            category="Sữa tiệt trùng",
            unit="Thùng",
            shelf_life_days=180,
            target_batch_size=4000.0,
            storage_temp="Nhiệt độ phòng (22-28°C)",
            description="Thùng 12 hộp x 1L, 100% sữa tươi nguyên chất Organic"
        )
        prod3 = Product(
            code="PROD-OJU-330",
            name="Nước cam ép tép Tự Nhiên 330ml Can",
            category="Nước ép trái cây",
            unit="Thùng",
            shelf_life_days=270,
            target_batch_size=3000.0,
            storage_temp="Nơi khô ráo, tránh ánh nắng trực tiếp",
            description="Thùng 24 lon x 330ml, chiết xuất cam Valencia giàu Vitamin C"
        )
        db.add_all([prod1, prod2, prod3])
        db.flush()

        # Recipes & BOM
        rcp1 = Recipe(
            recipe_code="RCP-UHT-01",
            product_id=prod1.id,
            version="v2.1",
            standard_batch_yield=5000.0,
            yield_unit="Thùng",
            standard_prep_time_minutes=240,
            is_active=True,
            notes="Công thức sữa tiệt trùng tiêu chuẩn đạt ISO 22000"
        )
        db.add(rcp1)
        db.flush()

        # BOM for rcp1
        if rm_milk and rm_tetra and rm_sugar:
            db.add_all([
                RecipeMaterial(recipe_id=rcp1.id, raw_material_id=rm_milk.id, required_quantity=4.5, unit="Tấn", tolerance_percent=1.5),
                RecipeMaterial(recipe_id=rcp1.id, raw_material_id=rm_tetra.id, required_quantity=5000.0, unit="Cuộn vỏ", tolerance_percent=2.0),
                RecipeMaterial(recipe_id=rcp1.id, raw_material_id=rm_sugar.id, required_quantity=0.25, unit="Tấn", tolerance_percent=1.0)
            ])

        rcp2 = Recipe(
            recipe_code="RCP-ORG-02",
            product_id=prod2.id,
            version="v1.0",
            standard_batch_yield=4000.0,
            yield_unit="Thùng",
            standard_prep_time_minutes=210,
            is_active=True
        )
        db.add(rcp2)
        db.flush()
        if rm_milk:
            db.add(RecipeMaterial(recipe_id=rcp2.id, raw_material_id=rm_milk.id, required_quantity=4.2, unit="Tấn", tolerance_percent=1.0))

        db.commit()

    prod_uht = db.query(Product).filter_by(code="PROD-UHT-180").first()
    rcp_uht = db.query(Recipe).filter_by(recipe_code="RCP-UHT-01").first()

    # 8. Seed ProductionBatches (Phase 3)
    if db.query(ProductionBatch).count() == 0:
        now = datetime.datetime.utcnow()
        batch1 = ProductionBatch(
            batch_code="LOT-2026-089",
            product_id=prod_uht.id if prod_uht else None,
            recipe_id=rcp_uht.id if rcp_uht else None,
            product_name="Sữa tiệt trùng Ít Đường 180ml UHT",
            line_name="Line A1 - Tetra Pak 250ml",
            target_quantity=5000.0,
            actual_quantity=5000.0,
            unit="Thùng",
            temperature_spec="138.5°C / 4s UHT",
            status="COMPLETE", # Completed & packaged, ready for Module 4 warehouse sync
            current_stage="Hoàn tất đóng gói & Kiểm nghiệm thành phẩm",
            stage_progress_percent=100,
            shift_manager_id=user_prod.id if user_prod else None,
            started_at=now - datetime.timedelta(days=2),
            completed_at=now - datetime.timedelta(days=1),
            mfg_date=now - datetime.timedelta(days=2),
            expiry_date=now + datetime.timedelta(days=178),
            notes="Mẻ sản xuất đạt chỉ tiêu chất lượng A+"
        )

        batch2 = ProductionBatch(
            batch_code="LOT-2026-090",
            product_id=prod_uht.id if prod_uht else None,
            recipe_id=rcp_uht.id if rcp_uht else None,
            product_name="Sữa tiệt trùng Ít Đường 180ml UHT",
            line_name="Line A1 - Tetra Pak 250ml",
            target_quantity=5000.0,
            actual_quantity=2500.0,
            unit="Thùng",
            temperature_spec="138.5°C / 4s UHT",
            status="IN_PROGRESS", # In progress on line
            current_stage="Tiệt trùng nhiệt UHT (UHT Pasteurization)",
            stage_progress_percent=60,
            shift_manager_id=user_prod.id if user_prod else None,
            started_at=now - datetime.timedelta(hours=4),
            mfg_date=now,
            expiry_date=now + datetime.timedelta(days=180),
            notes="Đang chạy giai đoạn tiệt trùng nhiệt"
        )
        db.add_all([batch1, batch2])
        db.flush()

        # Seed consumed raw material lots for batch1
        if lot_milk:
            db.add(BatchRawMaterial(
                production_batch_id=batch1.id,
                raw_material_lot_id=lot_milk.id,
                quantity_consumed=4.5,
                unit="Tấn"
            ))

        # Seed 5 process stages for batch1
        stage_names = [
            ("Chuẩn bị nguyên liệu (Material Prep)", "Nhiệt độ bồn: 3.5°C"),
            ("Phối trộn & Đồng hóa (Mixing & Homogenization)", "Áp suất đồng hóa: 200 bar"),
            ("Tiệt trùng nhiệt UHT (UHT Pasteurization)", "138.5°C / 4s UHT"),
            ("Chiết rót vô trùng (Aseptic Filling)", "Phòng sạch Class 100"),
            ("Đóng gói & Hoàn thiện (Packaging & Palletizing)", "Đóng 48 hộp/thùng")
        ]
        for idx, (stg_name, stg_param) in enumerate(stage_names):
            stg_start = now - datetime.timedelta(hours=48 - idx * 4)
            stg_end = stg_start + datetime.timedelta(hours=3)
            db.add(ProductionProcessRecord(
                production_batch_id=batch1.id,
                stage_name=stg_name,
                stage_order=idx + 1,
                status="COMPLETED",
                started_at=stg_start,
                ended_at=stg_end,
                parameters_log=stg_param,
                operator_id=user_prod.id if user_prod else None
            ))

        # Seed packaging record for batch1
        db.add(PackagingRecord(
            production_batch_id=batch1.id,
            carton_boxes_used=5000,
            packaging_seal_rolls_used=2.5,
            packages_completed=5000,
            waste_count=14,
            inspected_by_user_id=user_prod.id if user_prod else None,
            recorded_at=now - datetime.timedelta(days=1)
        ))

        db.commit()

    batch_complete = db.query(ProductionBatch).filter_by(batch_code="LOT-2026-089").first()

    # 9. Seed Customers (Phase 4)
    if db.query(Customer).count() == 0:
        db.add_all([
            Customer(
                customer_code="CUST-001",
                name="Tập đoàn Bán lẻ VinCommerce (WinMart)",
                tax_id="0106341306",
                contact_person="Trần Thị Bích Ngọc",
                phone="0904.221.889",
                email="purchasing@winmart.vn",
                delivery_address="Kho Tổng WinMart Miền Bắc, KCN Quang Minh, Mê Linh, Hà Nội",
                city="Hà Nội"
            ),
            Customer(
                customer_code="CUST-002",
                name="Chuỗi Siêu thị Bách Hóa Xanh",
                tax_id="0310471746",
                contact_person="Nguyễn Hoàng Nam",
                phone="0918.552.123",
                email="procurement@bachhoaxanh.com",
                delivery_address="Tổng kho Bách Hóa Xanh Tân Tạo, Bình Tân, TP. Hồ Chí Minh",
                city="TP. Hồ Chí Minh"
            ),
            Customer(
                customer_code="CUST-003",
                name="Trung tâm Bán sỉ MM Mega Market",
                tax_id="0302249586",
                contact_person="Vũ Đình Trọng",
                phone="0982.776.543",
                email="order@mmvietnam.com",
                delivery_address="MM Mega Market Thăng Long, Phạm Văn Đồng, Hà Nội",
                city="Hà Nội"
            )
        ])
        db.commit()

    cust_winmart = db.query(Customer).filter_by(customer_code="CUST-001").first()

    # 10. Seed Warehouse Inventory with FEFO Order (Phase 4)
    if db.query(WarehouseInventory).count() == 0 and batch_complete:
        now = datetime.datetime.utcnow()
        # Item 1: Expiring soon (10 days left) -> Urgency: EXPIRING_SOON (Red)
        inv1 = WarehouseInventory(
            sku_code="INV-SKU-001",
            production_batch_id=batch_complete.id,
            product_id=batch_complete.product_id,
            batch_code="LOT-2026-075",
            product_name="Sữa tiệt trùng Ít Đường 180ml UHT",
            initial_quantity=1200.0,
            available_quantity=850.0,
            allocated_quantity=350.0,
            unit="Thùng",
            unit_price=240000.0,
            storage_bin="Khu A - Kệ 01 Tầng 1 (Cận Hạn FEFO)",
            pallet_code="PLT-2026-042",
            mfg_date=now - datetime.timedelta(days=170),
            expiry_date=now + datetime.timedelta(days=10), # 10 days left!
            status="EXPIRING_SOON",
            audited_by_user_id=user_wh.id if user_wh else None
        )
        # Item 2: Medium expiry (35 days left) -> Urgency: ATTENTION (Amber)
        inv2 = WarehouseInventory(
            sku_code="INV-SKU-002",
            production_batch_id=batch_complete.id,
            product_id=batch_complete.product_id,
            batch_code="LOT-2026-080",
            product_name="Sữa tươi tiệt trùng Nguyên Chất 1L",
            initial_quantity=2000.0,
            available_quantity=1800.0,
            allocated_quantity=200.0,
            unit="Thùng",
            unit_price=320000.0,
            storage_bin="Khu B - Kệ 03 Tầng 2",
            pallet_code="PLT-2026-056",
            mfg_date=now - datetime.timedelta(days=145),
            expiry_date=now + datetime.timedelta(days=35), # 35 days left!
            status="NORMAL",
            audited_by_user_id=user_wh.id if user_wh else None
        )
        # Item 3: Fresh batch (178 days left) -> Urgency: FRESH (Green)
        inv3 = WarehouseInventory(
            sku_code="INV-SKU-003",
            production_batch_id=batch_complete.id,
            product_id=batch_complete.product_id,
            batch_code=batch_complete.batch_code,
            product_name=batch_complete.product_name,
            initial_quantity=5000.0,
            available_quantity=3500.0,
            allocated_quantity=1500.0,
            unit="Thùng",
            unit_price=240000.0,
            storage_bin="Khu A - Kệ 04 Tầng 2",
            pallet_code="PLT-2026-089",
            mfg_date=now - datetime.timedelta(days=2),
            expiry_date=now + datetime.timedelta(days=178), # 178 days left
            status="NORMAL",
            audited_by_user_id=user_wh.id if user_wh else None
        )
        db.add_all([inv1, inv2, inv3])
        db.commit()

    inv_fresh = db.query(WarehouseInventory).filter_by(batch_code="LOT-2026-089").first()

    # 11. Seed Dispatches (Phase 4)
    if db.query(Dispatch).count() == 0 and cust_winmart and inv_fresh:
        now = datetime.datetime.utcnow()
        dsp1 = Dispatch(
            dispatch_code="DSP-2026-041",
            customer_id=cust_winmart.id,
            dispatched_by_id=user_wh.id if user_wh else None,
            destination=cust_winmart.delivery_address,
            carrier_name="Đội xe lạnh Nhà Máy FoodMan",
            license_plate="29C-881.99",
            driver_name="Bùi Văn Hùng",
            driver_phone="0978.555.234",
            temp_sensor_celsius=3.8,
            temp_spec_range="2.0°C - 6.0°C",
            status="IN_TRANSIT",
            total_packages=1500.0,
            total_amount=360000000.0,
            scheduled_departure=now - datetime.timedelta(hours=2),
            notes="Xuất hàng theo chuẩn chuỗi lạnh FEFO cho chuỗi WinMart"
        )
        db.add(dsp1)
        db.flush()

        db.add(DispatchItem(
            dispatch_id=dsp1.id,
            inventory_id=inv_fresh.id,
            product_id=inv_fresh.product_id,
            batch_code=inv_fresh.batch_code,
            quantity=1500.0,
            unit="Thùng",
            unit_price=240000.0,
            subtotal=360000000.0
        ))
        db.commit()

    # 12. Seed Alert Rules & Notifications (Phase 4)
    if db.query(AlertRule).count() == 0:
        db.add_all([
            AlertRule(rule_code="RULE-FEFO-01", rule_name="Cảnh báo hạn sử dụng FEFO <= 15 ngày", rule_type="EXPIRING_SOON", threshold_value=15.0, severity="CRITICAL"),
            AlertRule(rule_code="RULE-STOCK-02", rule_name="Cảnh báo tồn kho an toàn dưới định mức", rule_type="LOW_STOCK", threshold_value=200.0, severity="WARNING"),
            AlertRule(rule_code="RULE-TEMP-03", rule_name="Cảnh báo biến thiên nhiệt độ xe lạnh > 6°C", rule_type="TEMP_EXCURSION", threshold_value=6.0, severity="CRITICAL")
        ])
        db.commit()

    if db.query(NotificationAlert).count() == 0:
        db.add_all([
            NotificationAlert(
                title="Cảnh báo FEFO: Hàng cận hạn sử dụng",
                message="Lô LOT-2026-075 (Sữa tiệt trùng Ít Đường 180ml) chỉ còn 10 ngày hết hạn. Ưu tiên xuất kho ngay!",
                module="Warehouse",
                severity="CRITICAL",
                is_read=False,
                reference_type="inventory",
                reference_id="LOT-2026-075"
            ),
            NotificationAlert(
                title="Lô sản xuất hoàn tất: LOT-2026-089",
                message="Mẻ sản xuất 5,000 Thùng sữa tiệt trùng đã qua đóng gói & kiểm định, sẵn sàng nhập kho.",
                module="Production",
                severity="INFO",
                is_read=False,
                reference_type="batch",
                reference_id="LOT-2026-089"
            ),
            NotificationAlert(
                title="Xe xuất kho khởi hành: DSP-2026-041",
                message="Xe lạnh 29C-881.99 đang vận chuyển 1,500 Thùng đến Kho Tổng WinMart (Nhiệt độ hiện tại: 3.8°C).",
                module="Warehouse",
                severity="INFO",
                is_read=True,
                reference_type="dispatch",
                reference_id="DSP-2026-041"
            )
        ])
        db.commit()

    print("[Food Man] Seed completed successfully. Full Phase 0 - Phase 4 enterprise state initialized.")

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
