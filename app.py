"""
Food Man - Main Flask Application Factory & Server Entry Point
PRD Phase 0 to Phase 4 Complete Integration
"""
import os
import datetime
from flask import Flask, jsonify, send_from_directory
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
from models.qc import QCSample, QCTest, COADocument, InspectionImage, AIInspection, DetectedDefect, QCDecision, LiveSession, LiveFrame
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
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True

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

    @app.route('/health', methods=['GET'])
    def health_check():
        """
        Lightweight health check endpoint for desktop launcher & uptime monitoring.
        """
        return jsonify({
            "status": "ok",
            "healthy": True,
            "service": "Food Man Enterprise System",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }), 200

    @app.route('/manifest.json', methods=['GET'])
    def web_manifest():
        """
        Web App Manifest for mobile PWA Add to Home Screen.
        """
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'manifest.json',
            mimetype='application/manifest+json'
        )

    @app.context_processor
    def inject_global_context():
        from routes.auth import get_current_user
        from models.enums import RoleEnum, ROLE_MODULE_PERMISSIONS, StatusEnum
        from models.schema_draft import RawMaterialLot
        
        user = get_current_user()
        permitted_modules = []
        pending_qc_count = 0
        if user:
            role_enum_match = None
            for r in RoleEnum:
                if r.value.lower() == (user.role or '').strip().lower():
                    role_enum_match = r
                    break
            if role_enum_match:
                permitted_modules = ROLE_MODULE_PERMISSIONS.get(role_enum_match, [])
            elif user.is_admin():
                permitted_modules = ROLE_MODULE_PERMISSIONS.get(RoleEnum.ADMIN, [])
            
            try:
                db = get_db()
                pending_qc_count = db.query(RawMaterialLot).filter(
                    (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
                ).count()
            except Exception:
                pending_qc_count = 0

        return {
            "current_user": user,
            "user": user,
            "permitted_modules": permitted_modules,
            "pending_qc_count": pending_qc_count
        }

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
            "full_name": "Nguyen Hoang Minh",
            "role": RoleEnum.ADMIN.value,
            "avatar": "AD",
            "dept": "Board of Directors"
        },
        {
            "email": "procurement@foodman.vn",
            "password": "password123",
            "full_name": "Vu Thu Thao",
            "role": RoleEnum.PROCUREMENT.value,
            "avatar": "PR",
            "dept": "Procurement & Raw Materials"
        },
        {
            "email": "qc@foodman.vn",
            "password": "password123",
            "full_name": "Pham Thu Trang, MSc.",
            "role": RoleEnum.QC.value,
            "avatar": "QC",
            "dept": "QC & Testing Lab"
        },
        {
            "email": "production@foodman.vn",
            "password": "password123",
            "full_name": "Tran Minh Quan",
            "role": RoleEnum.PRODUCTION.value,
            "avatar": "TM",
            "dept": "Processing & Packaging Plant"
        },
        {
            "email": "warehouse@foodman.vn",
            "password": "password123",
            "full_name": "Hoang Dinh Tuan",
            "role": RoleEnum.WAREHOUSE.value,
            "avatar": "WH",
            "dept": "Warehouse & Logistics"
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
            Supplier(code="SUP-001", name="Golden Grain & Oilseed Co.", contact_name="Tran Van Hung", email="goldengrain@agri.com", phone="0912.345.678", address="Son La Agribusiness Zone", rating=4.9, status="APPROVED"),
            Supplier(code="SUP-002", name="Sunrise Agri Seeds Corp.", contact_name="Lars Lindqvist", email="contact@sunriseseeds.com", phone="028.3824.8888", address="Dong Nai Agricultural Hub", rating=5.0, status="APPROVED"),
            Supplier(code="SUP-003", name="Central Plains Farm Collective", contact_name="Le Dinh Thang", email="sales@centralplains.com", phone="0237.3861.234", address="Dak Lak High Plains", rating=4.7, status="APPROVED"),
            Supplier(code="SUP-004", name="Pioneer Seed Partners", contact_name="Sarah Jenkins", email="trade@pioneerseed.com", phone="+64 9 374 9000", address="Canterbury Agricultural District", rating=4.9, status="APPROVED")
        ])
        db.commit()

    sup_1 = db.query(Supplier).filter_by(code="SUP-001").first()
    sup_2 = db.query(Supplier).filter_by(code="SUP-002").first()
    sup_3 = db.query(Supplier).filter_by(code="SUP-003").first()

    # 3. Seed RawMaterials - Exactly 3 initial materials (extensible data-driven catalog)
    if db.query(RawMaterial).count() == 0:
        db.add_all([
            RawMaterial(
                code="RM-PEANUT-001",
                name="Peanut",
                category="Oilseed",
                standard_unit="kg",
                unit_weight="50 kg / bag",
                storage_temp="Dry ventilated storage 15-20°C",
                shelf_life_days=365,
                min_stock_level=500.0
            ),
            RawMaterial(
                code="RM-CORN-001",
                name="Corn",
                category="Grain",
                standard_unit="kg",
                unit_weight="50 kg / bag",
                storage_temp="Dry grain silo 15-18°C",
                shelf_life_days=365,
                min_stock_level=1000.0
            ),
            RawMaterial(
                code="RM-SUNFLOWER-001",
                name="Sunflower Seeds",
                category="Oilseed",
                standard_unit="kg",
                unit_weight="25 kg / bag",
                storage_temp="Dry storage 15-20°C",
                shelf_life_days=270,
                min_stock_level=300.0
            )
        ])
        db.commit()

    rm_peanut = db.query(RawMaterial).filter_by(code="RM-PEANUT-001").first()
    rm_corn = db.query(RawMaterial).filter_by(code="RM-CORN-001").first()
    rm_sunflower = db.query(RawMaterial).filter_by(code="RM-SUNFLOWER-001").first()

    # 4. Seed PurchaseOrder with Items
    if db.query(PurchaseOrder).count() == 0 and rm_peanut and rm_corn:
        po1 = PurchaseOrder(
            po_number="PO-2026-001",
            supplier_id=sup_1.id if sup_1 else 1,
            created_by_user_id=user_proc.id if user_proc else None,
            order_date=datetime.datetime.utcnow(),
            status="COMPLETED",
            total_amount=271000000.0,
            notes="Initial supply of premium non-GMO oilseeds and grains"
        )
        db.add(po1)
        db.flush()

        db.add_all([
            PurchaseOrderItem(
                purchase_order_id=po1.id,
                raw_material_id=rm_peanut.id,
                quantity_ordered=5000.0,
                quantity_received=5000.0,
                unit="kg",
                unit_price=35000.0,
                subtotal=175000000.0
            ),
            PurchaseOrderItem(
                purchase_order_id=po1.id,
                raw_material_id=rm_corn.id,
                quantity_ordered=8000.0,
                quantity_received=8000.0,
                unit="kg",
                unit_price=12000.0,
                subtotal=96000000.0
            )
        ])
        db.commit()

    po_seed1 = db.query(PurchaseOrder).filter_by(po_number="PO-2026-001").first()

    # 5. Seed RawMaterialLots
    if db.query(RawMaterialLot).count() == 0 and rm_peanut and rm_corn and rm_sunflower:
        db.add_all([
            RawMaterialLot(
                lot_number="RAW-LOT-512",
                material_name="Peanut",
                category="Oilseed",
                supplier_name="Golden Grain & Oilseed Co.",
                quantity=5000.0,
                unit="kg",
                storage_condition="Dry Pallet Storage Room A",
                status=StatusEnum.APPROVED.value,
                qc_status="APPROVED",
                unit_weight="50 kg / bag",
                supplier_id=sup_1.id if sup_1 else None,
                raw_material_id=rm_peanut.id,
                purchase_order_id=po_seed1.id if po_seed1 else None,
                created_by_user_id=user_proc.id if user_proc else None
            ),
            RawMaterialLot(
                lot_number="RAW-LOT-513",
                material_name="Corn",
                category="Grain",
                supplier_name="Golden Grain & Oilseed Co.",
                quantity=8000.0,
                unit="kg",
                storage_condition="Grain Silo 02",
                status=StatusEnum.APPROVED.value,
                qc_status="APPROVED",
                unit_weight="50 kg / bag",
                supplier_id=sup_1.id if sup_1 else None,
                raw_material_id=rm_corn.id,
                created_by_user_id=user_proc.id if user_proc else None
            ),
            RawMaterialLot(
                lot_number="RAW-LOT-514",
                material_name="Sunflower Seeds",
                category="Oilseed",
                supplier_name="Sunrise Agri Seeds Corp.",
                quantity=3000.0,
                unit="kg",
                storage_condition="Dry Pallet Storage Room B",
                status=StatusEnum.APPROVED.value,
                qc_status="APPROVED",
                unit_weight="25 kg / bag",
                supplier_id=sup_2.id if sup_2 else None,
                raw_material_id=rm_sunflower.id,
                created_by_user_id=user_proc.id if user_proc else None
            ),
            RawMaterialLot(
                lot_number="RAW-LOT-515",
                material_name="Peanut",
                category="Oilseed",
                supplier_name="Central Plains Farm Collective",
                quantity=2000.0,
                unit="kg",
                storage_condition="Inbound Staging Bay 1",
                status=StatusEnum.PENDING.value,
                qc_status="PENDING_QC",
                unit_weight="50 kg / bag",
                supplier_id=sup_3.id if sup_3 else None,
                raw_material_id=rm_peanut.id,
                created_by_user_id=user_proc.id if user_proc else None
            )
        ])
        db.commit()

    lot_peanut = db.query(RawMaterialLot).filter_by(lot_number="RAW-LOT-512").first()

    # 6. Seed QC Decisions & AI Inspections for Lot 512 (Peanut)
    if lot_peanut and db.query(QCDecision).filter_by(raw_material_lot_id=lot_peanut.id).count() == 0:
        sample = QCSample(
            sample_code="SMP-QC-512",
            raw_material_lot_id=lot_peanut.id,
            sampler_user_id=user_qc.id if user_qc else None,
            storage_temp="20°C",
            sample_size="1,000g composite sample",
            notes="Sampling for moisture, aflatoxin, purity, and oil content"
        )
        db.add(sample)
        db.flush()

        db.add_all([
            QCTest(qc_sample_id=sample.id, parameter_name="Moisture Content", standard_spec="< 8.0%", measured_value="6.8%", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Aflatoxin B1", standard_spec="< 2.0 ppb", measured_value="0.2 ppb", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Purity Rate", standard_spec=">= 98.0%", measured_value="99.2%", is_pass=True),
            QCTest(qc_sample_id=sample.id, parameter_name="Oil Content", standard_spec=">= 48.0%", measured_value="50.4%", is_pass=True)
        ])

        db.add(COADocument(
            raw_material_lot_id=lot_peanut.id,
            supplier_id=lot_peanut.supplier_id,
            doc_number="COA-OILSEED-2026-512",
            filename="COA-GoldenGrain-Peanut-Lot512.pdf",
            file_url="/static/docs/coa_peanut_512.pdf",
            lab_accreditation="VILAS 102 / ISO 17025",
            is_verified=True
        ))

        img = InspectionImage(
            raw_material_lot_id=lot_peanut.id,
            image_url="/static/img/sample_inspection.jpg",
            image_type="Grain Bag Tamper-Evident Security Seal"
        )
        db.add(img)
        db.flush()

        ai = AIInspection(
            inspection_image_id=img.id,
            raw_material_lot_id=lot_peanut.id,
            model_version="YOLOv8x-FoodDefect-v2.1",
            inference_time_ms=42.5,
            total_defects_count=0,
            summary="No bag damage or seal tamper detected"
        )
        db.add(ai)

        db.add(QCDecision(
            raw_material_lot_id=lot_peanut.id,
            decided_by_user_id=user_qc.id if user_qc else 1,
            final_status="APPROVED",
            reason="Passed 100% moisture, aflatoxin, and purity specifications",
            action_notes="Approved for extraction and production intake"
        ))
        db.commit()

    # 7. Seed Products, Recipes, and BOM (Phase 3)
    if db.query(Product).count() == 0:
        prod1 = Product(
            code="PROD-OIL-01",
            name="Pure Roasted Peanut Oil 1L",
            category="Oilseed",
            unit="Bottles",
            shelf_life_days=365,
            target_batch_size=1000.0,
            storage_temp="Room temperature (20-25°C)",
            description="Case of 12 bottles x 1L, pure cold-pressed roasted peanut oil"
        )
        prod2 = Product(
            code="PROD-CRN-02",
            name="Refined Golden Corn Oil 1L",
            category="Grain",
            unit="Bottles",
            shelf_life_days=365,
            target_batch_size=1500.0,
            storage_temp="Room temperature (20-25°C)",
            description="Case of 12 bottles x 1L, 100% pure refined corn germ oil"
        )
        prod3 = Product(
            code="PROD-SUN-03",
            name="Cold-Pressed Sunflower Seed Oil 1L",
            category="Oilseed",
            unit="Bottles",
            shelf_life_days=365,
            target_batch_size=1000.0,
            storage_temp="Room temperature (20-25°C)",
            description="Case of 12 bottles x 1L, premium cold-pressed sunflower seed oil"
        )
        db.add_all([prod1, prod2, prod3])
        db.flush()

        # Recipes & BOM
        rcp1 = Recipe(
            recipe_code="RCP-PNT-01",
            product_id=prod1.id,
            version="v1.0",
            standard_batch_yield=1000.0,
            yield_unit="Bottles",
            standard_prep_time_minutes=240,
            is_active=True,
            notes="Cold-pressed roasted peanut oil extraction formula"
        )
        db.add(rcp1)
        db.flush()

        if rm_peanut:
            db.add(RecipeMaterial(recipe_id=rcp1.id, raw_material_id=rm_peanut.id, required_quantity=2200.0, unit="kg", tolerance_percent=1.5))

        rcp2 = Recipe(
            recipe_code="RCP-CRN-02",
            product_id=prod2.id,
            version="v1.0",
            standard_batch_yield=1500.0,
            yield_unit="Bottles",
            standard_prep_time_minutes=210,
            is_active=True,
            notes="Refined corn oil extraction and purification formula"
        )
        db.add(rcp2)
        db.flush()
        if rm_corn:
            db.add(RecipeMaterial(recipe_id=rcp2.id, raw_material_id=rm_corn.id, required_quantity=3200.0, unit="kg", tolerance_percent=1.0))

        rcp3 = Recipe(
            recipe_code="RCP-SUN-03",
            product_id=prod3.id,
            version="v1.0",
            standard_batch_yield=1000.0,
            yield_unit="Bottles",
            standard_prep_time_minutes=200,
            is_active=True,
            notes="Cold-pressed sunflower seed oil processing formula"
        )
        db.add(rcp3)
        db.flush()
        if rm_sunflower:
            db.add(RecipeMaterial(recipe_id=rcp3.id, raw_material_id=rm_sunflower.id, required_quantity=2400.0, unit="kg", tolerance_percent=1.0))

        db.commit()

    prod_peanut = db.query(Product).filter_by(code="PROD-OIL-01").first()
    rcp_peanut = db.query(Recipe).filter_by(recipe_code="RCP-PNT-01").first()

    # 8. Seed ProductionBatches (Phase 3)
    if db.query(ProductionBatch).count() == 0 and prod_peanut and rcp_peanut:
        now = datetime.datetime.utcnow()
        batch1 = ProductionBatch(
            batch_code="LOT-2026-089",
            product_id=prod_peanut.id,
            recipe_id=rcp_peanut.id,
            product_name="Pure Roasted Peanut Oil 1L",
            line_name="Line 1 - Cold Press & Bottling",
            target_quantity=1000.0,
            actual_quantity=1000.0,
            unit="Bottles",
            temperature_spec="125.0°C Roasting / Cold Press",
            status="COMPLETE",
            current_stage="Packaging & Bottling Completed",
            stage_progress_percent=100,
            shift_manager_id=user_prod.id if user_prod else None,
            started_at=now - datetime.timedelta(days=2),
            completed_at=now - datetime.timedelta(days=1),
            mfg_date=now - datetime.timedelta(days=2),
            expiry_date=now + datetime.timedelta(days=363),
            notes="Batch met quality standard A+"
        )

        batch2 = ProductionBatch(
            batch_code="LOT-2026-090",
            product_id=prod_peanut.id,
            recipe_id=rcp_peanut.id,
            product_name="Pure Roasted Peanut Oil 1L",
            line_name="Line 1 - Cold Press & Bottling",
            target_quantity=1000.0,
            actual_quantity=500.0,
            unit="Bottles",
            temperature_spec="125.0°C Roasting / Cold Press",
            status="IN_PROGRESS",
            current_stage="Screw Pressing & Oil Extraction",
            stage_progress_percent=60,
            shift_manager_id=user_prod.id if user_prod else None,
            started_at=now - datetime.timedelta(hours=4),
            mfg_date=now,
            expiry_date=now + datetime.timedelta(days=365),
            notes="Currently running screw pressing and oil extraction"
        )
        db.add_all([batch1, batch2])
        db.flush()

        if lot_peanut:
            db.add(BatchRawMaterial(
                production_batch_id=batch1.id,
                raw_material_lot_id=lot_peanut.id,
                quantity_consumed=2200.0,
                unit="kg"
            ))

        stage_names = [
            ("Grain Cleaning & De-stoning", "Vibrating screen 99.8% purity"),
            ("Conditioning & Roasting", "Roasting temp: 125°C / 20 min"),
            ("Screw Pressing & Extraction", "Hydraulic pressure: 250 bar"),
            ("Multi-Stage Filtration", "Leaf filter < 5 micron clarity"),
            ("Bottling & Capping", "Fill 1,000 ml / bottle")
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

        db.add(PackagingRecord(
            production_batch_id=batch1.id,
            carton_boxes_used=84,
            packaging_seal_rolls_used=1.0,
            packages_completed=1000,
            waste_count=4,
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
                name="WinCommerce Retail Group (WinMart)",
                tax_id="0106341306",
                contact_person="Tran Thi Bich Ngoc",
                phone="0904.221.889",
                email="purchasing@winmart.vn",
                delivery_address="WinMart Central DC Northern Division, Quang Minh IZ, Me Linh, Hanoi",
                city="Hanoi"
            ),
            Customer(
                customer_code="CUST-002",
                name="Bach Hoa Xanh Supermarket Chain",
                tax_id="0310471746",
                contact_person="Nguyen Hoang Nam",
                phone="0918.552.123",
                email="procurement@bachhoaxanh.com",
                delivery_address="Bach Hoa Xanh Central DC Tan Tao, Binh Tan, Ho Chi Minh City",
                city="Ho Chi Minh City"
            ),
            Customer(
                customer_code="CUST-003",
                name="MM Mega Market Wholesale Center",
                tax_id="0302249586",
                contact_person="Vu Dinh Trong",
                phone="0982.776.543",
                email="order@mmvietnam.com",
                delivery_address="MM Mega Market Thang Long, Pham Van Dong, Hanoi",
                city="Hanoi"
            )
        ])
        db.commit()

    cust_winmart = db.query(Customer).filter_by(customer_code="CUST-001").first()

    # 10. Seed Warehouse Inventory with FEFO Order (Phase 4)
    if db.query(WarehouseInventory).count() == 0 and batch_complete:
        now = datetime.datetime.utcnow()
        inv1 = WarehouseInventory(
            sku_code="INV-SKU-001",
            production_batch_id=batch_complete.id,
            product_id=batch_complete.product_id,
            batch_code="LOT-2026-075",
            product_name="Pure Roasted Peanut Oil 1L",
            initial_quantity=400.0,
            available_quantity=250.0,
            allocated_quantity=150.0,
            unit="Bottles",
            unit_price=125000.0,
            storage_bin="Zone A - Rack 01 Tier 1 (FEFO Near Expiry)",
            pallet_code="PLT-2026-042",
            mfg_date=now - datetime.timedelta(days=355),
            expiry_date=now + datetime.timedelta(days=10),
            status="EXPIRING_SOON",
            audited_by_user_id=user_wh.id if user_wh else None
        )
        inv2 = WarehouseInventory(
            sku_code="INV-SKU-002",
            production_batch_id=batch_complete.id,
            product_id=batch_complete.product_id,
            batch_code="LOT-2026-080",
            product_name="Refined Golden Corn Oil 1L",
            initial_quantity=800.0,
            available_quantity=600.0,
            allocated_quantity=200.0,
            unit="Bottles",
            unit_price=85000.0,
            storage_bin="Zone B - Rack 03 Tier 2",
            pallet_code="PLT-2026-056",
            mfg_date=now - datetime.timedelta(days=330),
            expiry_date=now + datetime.timedelta(days=35),
            status="NORMAL",
            audited_by_user_id=user_wh.id if user_wh else None
        )
        inv3 = WarehouseInventory(
            sku_code="INV-SKU-003",
            production_batch_id=batch_complete.id,
            product_id=batch_complete.product_id,
            batch_code=batch_complete.batch_code,
            product_name=batch_complete.product_name,
            initial_quantity=1000.0,
            available_quantity=800.0,
            allocated_quantity=200.0,
            unit="Bottles",
            unit_price=125000.0,
            storage_bin="Zone A - Rack 04 Tier 2",
            pallet_code="PLT-2026-089",
            mfg_date=now - datetime.timedelta(days=2),
            expiry_date=now + datetime.timedelta(days=363),
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
            carrier_name="FoodMan Logistics Fleet",
            license_plate="29C-881.99",
            driver_name="Bui Van Hung",
            driver_phone="0978.555.234",
            temp_sensor_celsius=21.5,
            temp_spec_range="18.0°C - 24.0°C",
            status="IN_TRANSIT",
            total_packages=200.0,
            total_amount=25000000.0,
            scheduled_departure=now - datetime.timedelta(hours=2),
            notes="Dispatched according to FEFO standard for WinMart"
        )
        db.add(dsp1)
        db.flush()

        db.add(DispatchItem(
            dispatch_id=dsp1.id,
            inventory_id=inv_fresh.id,
            product_id=inv_fresh.product_id,
            batch_code=inv_fresh.batch_code,
            quantity=200.0,
            unit="Bottles",
            unit_price=125000.0,
            subtotal=25000000.0
        ))
        db.commit()

    # 12. Seed Alert Rules & Notifications (Phase 4)
    if db.query(AlertRule).count() == 0:
        db.add_all([
            AlertRule(rule_code="RULE-FEFO-01", rule_name="FEFO Expiry Alert <= 15 days", rule_type="EXPIRING_SOON", threshold_value=15.0, severity="CRITICAL"),
            AlertRule(rule_code="RULE-STOCK-02", rule_name="Safety Stock Below Minimum Alert", rule_type="LOW_STOCK", threshold_value=200.0, severity="WARNING"),
            AlertRule(rule_code="RULE-TEMP-03", rule_name="Warehouse Storage Temperature Excursion Alert", rule_type="TEMP_EXCURSION", threshold_value=26.0, severity="CRITICAL")
        ])
        db.commit()

    if db.query(NotificationAlert).count() == 0:
        db.add_all([
            NotificationAlert(
                title="FEFO Alert: Expiring Soon",
                message="Batch LOT-2026-075 (Pure Roasted Peanut Oil 1L) has only 10 days until expiry. Prioritize immediate dispatch!",
                module="Warehouse",
                severity="CRITICAL",
                is_read=False,
                reference_type="inventory",
                reference_id="LOT-2026-075"
            ),
            NotificationAlert(
                title="Production Batch Completed: LOT-2026-089",
                message="Production batch of 1,000 bottles Pure Roasted Peanut Oil 1L bottled & verified, ready for warehouse intake.",
                module="Production",
                severity="INFO",
                is_read=False,
                reference_type="batch",
                reference_id="LOT-2026-089"
            ),
            NotificationAlert(
                title="Dispatch Departed: DSP-2026-041",
                message="Delivery truck 29C-881.99 is transporting 200 bottles to WinMart Central DC.",
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
