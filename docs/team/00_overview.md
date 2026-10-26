# Food Man — Team Project Division & Architecture Overview

## 1. Whole Workflow in One Page

**Food Man** is an enterprise Food Manufacturing Execution System (MES) and AI-assisted Quality Control platform designed for grain and oilseed processing (Peanuts, Corn, Sunflower Seeds). The system enforces an unbroken end-to-end digital chain of custody across five operational tiers:

```
[Supplier Dock]                 [QC Lab Bench]                 [Production Line]             [Warehouse & Cold Chain]
       │                              │                                │                                │
┌──────▼──────┐               ┌───────▼────────┐               ┌───────▼────────┐               ┌───────▼────────┐
│   PART 3    │  Intake Lot   │     PART 1     │  AI Verdict   │     PART 2     │  APPROVED     │     PART 3     │
│ Procurement ├──────────────►│ AI Inspection  ├──────────────►│ QC & Release   ├──────────────►│   Production   │
│ PO & GRN    │  (PENDING_QC) │ Hold-Steady 5f │  (PASS/HOLD)  │ COA Validation │  Status Gate  │ 5-Stage Stepper│
└─────────────┘               └────────────────┘               └───────┬────────┘               └───────┬────────┘
                                                                       │                                │
                                                                       │ Signed PDF Certificate         │ Finished Product
                                                                       │                                │ (LOT-2026-xxx)
                                                                       ▼                                ▼
                                                               ┌────────────────────────────────────────────────┐
                                                               │                     PART 4                     │
                                                               │     Warehouse (FEFO), Dispatch (Cold Chain),   │
                                                               │     7-Tier Traceability & Enterprise Platform │
                                                               └────────────────────────────────────────────────┘
```

1. **Procurement (Part 3)**: Issues Purchase Orders (PO) to vetted agricultural suppliers. At the receiving dock, warehouse intake logs a Goods Receipt Note (GRN), triggering the creation of an uninspected Raw Material Lot (`PENDING` / `PENDING_QC`).
2. **AI Inspection (Part 1)**: The operator places a sample tray under the laptop inspection station or uses a smartphone camera via QR code. Dual neural networks (YOLOv8 defect detector + YOLOv8n-cls material classifier) and OpenCV CIE Lab colour screening evaluate grain health. A 5-frame hold-steady detector performs majority voting to lock a stable AI assessment (`PASS`, `REVIEW`, `REJECT`, or `RETAKE`).
3. **Quality Control & Release Decision (Part 2)**: The QC specialist evaluates the lot inside the QC Queue and Lot Drawer. The system runs the pure `release_decision()` engine, crossing the visual AI verdict with the accredited supplier laboratory Certificate of Analysis (COA) testing against ISO/QCVN limits (Aflatoxin B1, moisture, FFA, purity). Human overrides require a written justification. Upon approval, the lot status transitions to `APPROVED`, generating an official signed PDF Inspection Certificate.
4. **Production Execution (Part 3)**: Shift supervisors select a recipe and schedule a production batch. The system enforces a strict food safety lock: **only lots with status `APPROVED` can be allocated to Bill of Materials (BOM)**. If raw material is unapproved or deficient, batch creation is blocked. The batch progresses through 5 physical stages (Cleaning, Roasting/Pasteurization, Pressing, Filtration, Bottling), logs packaging material consumption, and yields finished goods.
5. **Warehouse, Dispatch & Traceability (Part 4)**: Finished goods are ingested into First-Expired, First-Out (FEFO) warehouse inventory. Outbound dispatch orders assign carrier trucks and log refrigerated cold-chain temperature telemetry (`temp_sensor_celsius`). The flagship 7-tier traceability engine allows regulators and customers to query any consumer bottle and immediately view the full upstream lineage back to the raw material lot, supplier farm, and QC laboratory dossier. Food Technologist dashboards, role-based access control, chatbot support, and Cloudflare tunneling complete the platform.

---

## 2. Team Ownership Matrix

The codebase is split into four balanced, non-overlapping modules:

| Metric | Part 1: AI Inspection | Part 2: QC & Release | Part 3: Procurement & Prod | Part 4: Warehouse & Platform | Total Measured |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Owner / Role** | Member 1 (AI Vision Lead) | Member 2 (Quality Assurance Lead) | Member 3 (Manufacturing Lead) | Member 4 (Platform & Logistics Lead) | 4 Team Members |
| **Primary Code Lines** | ~12,666 lines | ~7,669 lines | ~4,769 lines | ~14,660 lines | ~39,764 lines |
| **Route Endpoints** | 21 routes | 17 routes | 30 routes (19 Proc + 11 Prod) | 44 routes | 112 routes |
| **Database Tables** | 3 tables | 9 tables | 15 tables | 9 tables | 36 tables |
| **Dedicated Screens / Views** | 3 screens | 4 screens | 8 view tabs (5 Proc + 3 Prod) | 10 screens / views | 25 screens |
| **Automated Tests** | 23 tests | 19 tests | Smoke / integration tested | 10 tests | 52 tests |
| **Core Persona / Login** | `qc@foodman.vn` | `qc@foodman.vn` | `procurement@foodman.vn` & `production@foodman.vn` | `warehouse@foodman.vn`, `tech@foodman.vn`, `admin@foodman.vn` | 6 System Accounts |

### Granular Ownership Breakdown

#### Part 1: AI Inspection (Member 1)
- **Primary Screens**:
  - Unified Laptop Inspection Station (`/qc/camera-station`)
  - Phone-as-Webcam Mobile Capture (`/capture/<token>`)
  - Lab Colour Screening Calibration (`/qc/calibration`)
- **Backend Code & Services**:
  - `ai/yolo_service.py` (YOLOv8 defect detector, YOLOv8n-cls classifier loader, inference locking)
  - `ai/classical_kernel_finder.py` (CIE Lab paper background estimation, Otsu thresholding, distance-transform watershed splitting, per-kernel colour distance)
  - `routes/qc.py` (Station endpoints lines ~3600–4400: frame upload, rate limiting, downsampled steadiness check, 5-frame locking, majority voting, calibration endpoints)
  - `static/js/camera_station.js` (Webcam & phone stream handling, canvas bounding box rendering, 48x36 grayscale motion detection, locking animation)
  - `static/js/live_inspection.js` & `static/js/qc_calibration.js`
- **Database Tables**:
  - `live_sessions`, `live_frames`, `inspection_station_settings`
- **Tests**:
  - `tests/test_colour_screening_calibration.py` (5 tests)
  - `tests/test_final_decision_states.py` (18 tests)

#### Part 2: Quality Control & Release Decision (Member 2)
- **Primary Screens**:
  - QC Inspection Queue & Lot Review Drawer (`/qc?view=queue`)
  - QC Test Results & COA Library (`/qc?view=tests`)
  - Laboratory AI Inspection Upload Gateway (`/qc?view=ai-inspection`)
  - Live Inspection Monitoring Stream (`/qc?view=live-inspection`)
- **Backend Code & Services**:
  - `ai/release_decision.py` (`release_decision()`, `evaluate_coa_document()`, `evaluate_ai_inspection()`, `MATERIAL_SPECS`)
  - `routes/qc.py` (Queue, review, COA upload, lab sample recording, human sign-off override enforcement, ReportLab PDF dossier generation)
  - `models/qc.py` (`QCSample`, `QCTest`, `COADocument`, `AIInspection`, `DetectedDefect`, `InspectionImage`, `QCDecision`, `AIFeedback`)
  - `static/js/qc.js` (Slide-over lot drawer, release decision matrix badges, override modal, PDF trigger)
  - `scripts/seed_demo_release_lots.py` (Seeds `DEMO-LOT-REL-01` through `04`)
- **Database Tables**:
  - `qc_samples`, `qc_tests`, `coa_documents`, `ai_inspections`, `detected_defects`, `inspection_images`, `qc_decisions`, `ai_feedbacks`, `qc_inspections`
- **Tests**:
  - `tests/test_release_decision.py` (19 tests)

#### Part 3: Procurement & Production (Member 3)
- **Primary Screens**:
  - Suppliers Directory (`/procurement?view=suppliers`)
  - Raw Materials Catalog (`/procurement?view=raw-materials`)
  - Raw Material Intake Lots (`/procurement?view=lots`)
  - Purchase Orders (`/procurement?view=po`)
  - Goods Receipt Notes (`/procurement?view=grn`)
  - Recipes & BOM Specifications (`/production?view=recipes`)
  - Active Production Batches with 5-stage stepper (`/production?view=batches`)
  - BOM Planning & Stock Readiness (`/production?view=recommendations`)
- **Backend Code & Services**:
  - `routes/procurement.py` (Suppliers, PO, GRN, lot intake, void PO, soft-deactivation)
  - `routes/production.py` (Batch creation, APPROVED lot allocation lock, 5-stage stepper, packaging log, recipe management)
  - `models/procurement.py` (`Supplier`, `RawMaterial`, `PurchaseOrder`, `PurchaseOrderItem`, `GoodsReceipt`, `GoodsReceiptItem`, `RawMaterialLot`)
  - `models/production.py` (`Product`, `Recipe`, `RecipeMaterial`, `ProductionBatch`, `BatchRawMaterial`, `ProductionProcessRecord`, `PackagingMaterial`, `PackagingRecord`)
  - `static/js/procurement.js` & `static/js/production.js`
- **Database Tables**:
  - `suppliers`, `raw_materials`, `purchase_orders`, `purchase_order_items`, `goods_receipts`, `goods_receipt_items`, `raw_material_lots`, `recipes`, `recipe_materials`, `products`, `production_batches`, `batch_raw_materials`, `production_process_records`, `packaging_records`, `packaging_materials`
- **Verification**:
  - Integration verified via `scripts/smoke_test_buttons.py` and batch creation automated tests.

#### Part 4: Warehouse, Dispatch, Traceability & Platform (Member 4)
- **Primary Screens**:
  - Finished Goods FEFO Inventory (`/warehouse?view=inventory`)
  - Customer Retail Channels (`/warehouse?view=customers`)
  - Dispatch Orders & Cold Chain Fleet (`/warehouse?view=dispatches`)
  - Full Farm-to-Fork 7-Tier Traceability Search (`/traceability`)
  - Food Technologist 7-Stage Quality Lifecycle Dashboard (`/food-technologist`)
  - Executive KPI Dashboard (`/dashboard`)
  - Cross-Module Operational Reports & CSV Export (`/reports`)
  - System Alerts Center (`/alerts`) & System Settings (`/settings`)
  - System Authentication & Demo Switcher (`/login`)
- **Backend Code & Services**:
  - `routes/warehouse.py` (FEFO stock inventory, customer channels, dispatch lifecycle, cold chain sensor logging)
  - `routes/traceability.py` (Omni-search, 7-tier graph resolution)
  - `routes/dashboard.py` (KPI calculations, Food Technologist API, alerts evaluation, settings)
  - `routes/reports.py` (Aggregations, CSV stream export)
  - `routes/auth.py` (Session auth, role-based decorators, demo logins)
  - `routes/chatbot.py` (Heuristic knowledge-base food processing chatbot)
  - `routes/api.py` & `app.py` (Global search, system health check, Web Manifest)
  - `models/warehouse.py`, `models/user.py`, `models/enums.py`
  - `scripts/launcher.py`, `scripts/tunnel_service.py`, `FoodMan.bat`, `StopFoodMan.bat`
- **Database Tables**:
  - `warehouse_inventory`, `warehouse_items`, `customers`, `dispatches`, `dispatch_items`, `dispatch_orders`, `notification_alerts`, `alert_rules`, `users`
- **Tests**:
  - `tests/test_food_technologist_workflow.py` (10 tests)

---

## 3. Hand-off Points Between Parts

The physical and digital hand-offs between members connect like interlocking cogs:

| Hand-off Sequence | Producer Part | Consumer Part | Hand-off Artifact / Data Contract | Safety Rule / Enforced Invariant |
| :--- | :--- | :--- | :--- | :--- |
| **Hand-off 1** | **Part 3** (Procurement) | **Part 1** (AI Inspection) | `RawMaterialLot` record with `lot_number`, `material_name`, status `PENDING`, `qc_status = 'PENDING_QC'`. | Lot cannot enter production until cleared by QC. Available immediately in the Inspection Station lot selector. |
| **Hand-off 2** | **Part 1** (AI Inspection) | **Part 2** (QC & Release) | `LiveSession.locked_result_json` containing 5-frame majority voted decision state (`PASS`, `REVIEW`, `REJECT`, `RETAKE`), defect count, and best 3 frames. | Visual inspection is strictly advisory; AI cannot unilaterally authorize release without COA verification. |
| **Hand-off 3** | **Part 2** (QC & Release) | **Part 3** (Production) | Updated `RawMaterialLot.qc_status = 'APPROVED'` and signed PDF inspection certificate. | **Hard Constraint**: `routes/production.py:create_batch()` queries `RawMaterialLot.qc_status == 'APPROVED'`. If status is PENDING, HOLD, or REJECTED, batch creation aborts with HTTP 400. |
| **Hand-off 4** | **Part 3** (Production) | **Part 4** (Warehouse) | Completed `ProductionBatch` record (`LOT-2026-xxx`) with yield quantity, manufacturing date, and expiry date. | Finished goods automatically sync into `WarehouseInventory` table with FEFO expiry tracking. |
| **Hand-off 5** | **Part 4** (Traceability) | **All Parts (1–3)** | 7-Tier Traceability Omni-Search: links customer dispatch back through inventory, packaging, production batch, QC/AI records, raw material lots, and supplier farm. | Any consumer SKU code, batch code, or dispatch note resolves the unbroken chain in < 200ms. |

---

## 4. Live Demo Schedule (Total Time: 7 to 10 Minutes)

| Step | Member / Speaker | Screen Shown | Role Logged In | Key Actions & Storyline | Duration |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **0** | **Member 4** (Intro) | System Architecture & Executive Dashboard (`/dashboard`) | Admin (`admin@foodman.vn`) | High-level system overview, 5 business pillars, active plant counters. Switch to Procurement. | 1.0 min |
| **1** | **Member 3** (Procurement) | Procurement & Intake (`/procurement?view=lots`) | Procurement (`procurement@foodman.vn`) | Show supplier directory, PO-2026-001, GRN delivery intake, and show newly created raw material lot in `PENDING_QC`. Hand off to Member 1. | 1.5 min |
| **2** | **Member 1** (AI Vision) | Inspection Station (`/qc/camera-station`) | QC (`qc@foodman.vn`) | Select lot, show live camera detection (1 FPS), hold camera steady for 2.8s, trigger 5-frame locking, show majority voting verdict and best 3 frames. | 2.0 min |
| **3** | **Member 2** (QC Release) | QC Queue & Lot Drawer (`/qc?view=queue`) | QC (`qc@foodman.vn`) | Open `DEMO-LOT-REL-01` (Release) and `DEMO-LOT-REL-03` (Reject). Demonstrate COA lab evaluation, explain release matrix, execute human sign-off with override modal, download official PDF Certificate of Analysis. | 2.0 min |
| **4** | **Member 3** (Production) | Production Batches (`/production?view=batches`) | Production (`production@foodman.vn`) | Open batch creation modal. Show that only APPROVED lots can be consumed. Advance 5-stage stepper (Cleaning → Bottling) and log packaging. | 1.5 min |
| **5** | **Member 4** (Logistics & Trace) | Warehouse & Traceability (`/traceability`) | Warehouse (`warehouse@foodman.vn`) | Show FEFO inventory urgency, dispatch order with cold-chain sensor (3.8°C), run 7-tier traceability search on `LOT-2026-089`, and present Food Technologist lifecycle. Wrap up. | 2.0 min |
| **Total** | **Full Team** | **End-to-End Supply Chain** | **4 Distinct Roles** | **Seamless multi-role workflow demonstration** | **9.0 min** |
