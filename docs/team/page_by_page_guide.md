# Food Man — Complete Page-by-Page Student Guide

This guide explains all 18 core menu pages in **Food Man**. Written in plain language for students and examiners, each section details what the screen shows, every button and its exact action, the underlying API endpoints and database tables, and what record statuses change before and after each user action.

---

## Special Explanations Required by Audit

### 1. Why the QC Inspection Queue Badge Shows Exactly 13

In the navigation sidebar, the QC Inspection Queue item displays a notification counter badge:
```html
<span id="sidebarQcQueueBadge" class="nav-badge-count">{{ pending_qc_count }}</span>
```
This number is calculated automatically by the global Flask context processor in [`app.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/app.py#L116-L118):
```python
pending_qc_count = db.query(RawMaterialLot).filter(
    (RawMaterialLot.qc_status == "PENDING_QC") | (RawMaterialLot.status == StatusEnum.PENDING.value)
).count()
```
When queried against the live database ([`food_man.db`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/food_man.db)), this filter evaluates to **exactly 13 rows**:

| Lot ID | Lot Number | Material | Status | QC Status | Origin / Note |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **4** | `RAW-LOT-515` | Peanut | `PENDING` | `PENDING_QC` | Dock Intake Batch |
| **10** | `LOT-RM-2026-216` | Peanut | `PENDING` | `PENDING_QC` | Factory Delivery Lot |
| **11** | `LOT-RM-2026-274` | Peanut | `PENDING` | `PENDING_QC` | Factory Delivery Lot |
| **12** | `LOT-RM-2026-918` | Peanut | `PENDING` | `PENDING_QC` | Factory Delivery Lot |
| **19** | `DEMO-LOT-REL-02` | Corn | `PENDING` | `PENDING_QC` | Demo Lot (COA Pass + AI Reject $\rightarrow$ Hold) |
| **20** | `DEMO-LOT-REL-03` | Peanut | `PENDING` | `PENDING_QC` | Demo Lot (COA Fail $\rightarrow$ Reject) |
| **21** | `DEMO-LOT-REL-04` | Peanut | `PENDING` | `PENDING_QC` | Demo Lot (COA Missing $\rightarrow$ Hold) |
| **22** | `LOT-RM-2026-374` | Peanut | `PENDING` | `PENDING_QC` | Factory Delivery Lot |
| **23** | `LOT-RM-2026-777` | Peanut | `PENDING` | `PENDING_QC` | Factory Delivery Lot |
| **24** | `LOT-RM-2026-215` | Peanut | `PENDING` | `PENDING_QC` | Factory Delivery Lot |
| **25** | `LOT-RM-2026-853` | Corn | `PENDING` | `PENDING_QC` | Factory Delivery Lot |
| **26** | `LOT-RM-2026-547` | Peanut | `PENDING` | `PENDING_QC` | Factory Delivery Lot |
| **27** | `LOT-RM-2026-167` | Peanut | `PENDING` | `PENDING_QC` | Factory Delivery Lot |
| **Total** | **13 Lots** | — | — | — | **Matches the sidebar badge count of 13** |

*(Note: `DEMO-LOT-REL-01` has ID 18, and its status is `APPROVED` after clearance, which is why only 3 demo lots plus 10 real intake lots remain in the pending queue).*

---

### 2. Complete Alert Rules and Trigger Logic (Alerts Center)

The automated proactive alerts engine operates via `POST /api/alerts/evaluate` in [`routes/dashboard.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/routes/dashboard.py#L550-L650). It scans four operational criteria and compares live records against rules in the `alert_rules` table:

#### Registered Rules in Database (`alert_rules` table):
1. **`RULE-FEFO-01` ("FEFO Expiry Alert <= 15 days")**:
   - **Type**: `EXPIRING_SOON`
   - **Threshold**: $\le 15.0$ days
   - **Severity**: `CRITICAL`
   - **Trigger Condition**: Scans `WarehouseInventory`. If `days_to_expiry <= 15`, generates a `CRITICAL` alert: *"Batch [batch_code] expires on [date]. Prioritize for immediate dispatch."*
2. **`RULE-STOCK-02` ("Safety Stock Below Minimum Alert")**:
   - **Type**: `LOW_STOCK`
   - **Threshold**: $\le 200.0$ units
   - **Severity**: `WARNING`
   - **Trigger Condition**: Scans `RawMaterial`. If `current_approved_stock <= min_stock_level`, generates a `WARNING` (or `CRITICAL` if stock is 0): *"Current stock has fallen below safety threshold. Urgent PO required."* Also checks `WarehouseInventory` for SKUs with `available_quantity <= 500`.
3. **`RULE-TEMP-03` ("Warehouse Storage Temperature Excursion Alert")**:
   - **Type**: `TEMP_EXCURSION`
   - **Threshold**: $> 26.0^\circ\text{C}$
   - **Severity**: `CRITICAL`
   - **Trigger Condition**: Triggered when ambient warehouse sensor exceeds $26.0^\circ\text{C}$ for dry grain storage or when refrigerated dispatch telemetry exceeds truck specification (e.g. $> 6.0^\circ\text{C}$).
4. **`RULE-004` ("Audit Excursion Rule")**:
   - **Type**: `TEMP_EXCURSION`
   - **Threshold**: $> 6.0^\circ\text{C}$
   - **Severity**: `WARNING`
   - **Trigger Condition**: Triggers an audit notice when cold-chain dispatch temperature breaches $6.0^\circ\text{C}$.
5. **QC Backlog Scan (Automated)**:
   - **Trigger Condition**: Queries `RawMaterialLot` where `qc_status == 'PENDING_QC'` or `status == 'PENDING'`. Generates an alert for every lot awaiting QC review, ensuring incoming dock deliveries are not forgotten.

---

## Page-by-Page Detailed Breakdown (18 Menu Pages)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ MODULE 1: SUPPLIERS & PROCUREMENT                                                 │
│ Page 1: Suppliers                                                                │
│ Page 2: Raw Materials Catalog                                                    │
│ Page 3: Raw Material Lots & Intake                                               │
│ Page 4: Purchase Orders (PO)                                                     │
│ Page 5: Goods Receipts (GRN)                                                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│ MODULE 2: QUALITY CONTROL & AI INSPECTION                                        │
│ Page 6: QC Inspection Queue                                                      │
│ Page 7: AI Camera Inspection Station                                             │
│ Page 8: QC Test Results & COA Library                                            │
├──────────────────────────────────────────────────────────────────────────────────┤
│ MODULE 3: BATCH & PRODUCTION                                                     │
│ Page 9: Recipes & BOM Specifications                                             │
│ Page 10: Production Batches                                                      │
│ Page 11: BOM Planning & Readiness                                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│ MODULE 4: WAREHOUSE & DISPATCH                                                   │
│ Page 12: Finished Goods FEFO Inventory                                           │
│ Page 13: Customer Channels                                                       │
│ Page 14: Dispatch Orders & Cold Chain                                            │
├──────────────────────────────────────────────────────────────────────────────────┤
│ MODULE 5: TRACEABILITY, DASHBOARD & ENTERPRISE                                   │
│ Page 15: 7-Tier Full Traceability Search                                         │
│ Page 16: Executive KPI Dashboard                                                 │
│ Page 17: Operational Analytics & Reports                                         │
│ Page 18: Alerts & Notifications Center                                           │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

### Page 1: Suppliers
* **Route**: `GET /procurement?view=suppliers` $\rightarrow$ `routes.procurement.index()`
* **Template**: [`templates/procurement.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/procurement.html)
* **JavaScript**: [`static/js/procurement.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/procurement.js)
* **What it shows**: A card directory of all agricultural vendors who supply raw grain to the factory. Each card displays the supplier's company name (e.g., *AgriGrain Certified Supply Ltd*), vendor code (`SUP-DEMO-REL`), contact person, email, phone, physical farm address, star rating (out of 5.0), and active food safety certification badges (VietGAP, GlobalGAP, ISO 22000).
* **Buttons & Actions**:
  1. **`+ Add Supplier` Button (`#btnOpenSupplierModal`)**: Opens a modal window to onboard a new vendor with text inputs for name, code, contact details, rating, and certifications.
  2. **`Save Supplier` Modal Submit Button**: Dispatches `POST /api/procurement/suppliers`. Creates a new row in the `suppliers` database table.
  3. **Supplier Card Click (`.record-card-box`)**: Opens the slide-over `DetailDrawer` displaying the vendor's full address, active order history, and linked shipments.
  4. **`Deactivate Supplier` Drawer Button**: Dispatches `POST /api/procurement/suppliers/<id>/deactivate`. Checks whether the vendor has active unfulfilled purchase orders; if none exist, soft-deactivates the supplier.
  5. **`Reactivate Supplier` Drawer Button**: Dispatches `POST /api/procurement/suppliers/<id>/reactivate`. Re-enables a retired supplier.
  6. **`Show Inactive` Checkbox**: Toggles client-side display of archived suppliers.
* **APIs Used**: `GET /api/procurement/suppliers`, `POST /api/procurement/suppliers`, `PUT /api/procurement/suppliers/<id>`, `POST /api/procurement/suppliers/<id>/deactivate`, `POST /api/procurement/suppliers/<id>/reactivate`.
* **Database Tables**: `suppliers`, `purchase_orders`.
* **Status Changes**:
  - Before Onboarding: Vendor does not exist.
  - After Onboarding: New row in `suppliers` with `status = 'APPROVED'` and `is_active = 1`.
  - After Deactivation: `status` becomes `'INACTIVE'`, `is_active = 0`.
  - After Reactivation: `status` becomes `'APPROVED'`, `is_active = 1`.

---

### Page 2: Raw Materials Catalog
* **Route**: `GET /procurement?view=raw-materials` $\rightarrow$ `routes.procurement.index()`
* **Template**: [`templates/procurement.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/procurement.html)
* **JavaScript**: [`static/js/procurement.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/procurement.js)
* **What it shows**: The master catalog of raw ingredients used by the plant (Peanuts, Corn, Sunflower Seeds). Displays material code (`RM-PEANUT-001`), category (`Oilseed`, `Grain`), standard measurement unit (`kg`, `Tons`), optimal storage temperature (`4-6°C Cool storage`), shelf-life days, and minimum safety stock threshold.
* **Buttons & Actions**:
  1. **`+ Add Raw Material` Button (`#btnOpenRmModal`)**: Opens a modal to define a new commodity SKU.
  2. **`Save Material` Modal Submit Button**: Dispatches `POST /api/procurement/raw-materials`. Inserts a new row into `raw_materials`.
  3. **Material Card Click**: Opens `DetailDrawer` showing stored physicochemical limits (maximum moisture, aflatoxin ceilings) and current warehouse stock.
  4. **`Deactivate Material` Drawer Button**: Dispatches `POST /api/procurement/raw-materials/<id>/deactivate`. Checks if active intake lots exist; if safe, sets `is_active = 0`.
  5. **`Reactivate Material` Drawer Button**: Dispatches `POST /api/procurement/raw-materials/<id>/reactivate`.
* **APIs Used**: `GET /api/procurement/raw-materials`, `POST /api/procurement/raw-materials`, `PUT /api/procurement/raw-materials/<id>`, `POST /api/procurement/raw-materials/<id>/deactivate`, `POST /api/procurement/raw-materials/<id>/reactivate`.
* **Database Tables**: `raw_materials`, `raw_material_lots`.
* **Status Changes**:
  - After Creation: Row in `raw_materials` with `status = 'ACTIVE'`, `is_active = 1`.
  - After Deactivation: `is_active = 0`, `status = 'DEACTIVATED'`.

---

### Page 3: Raw Material Lots
* **Route**: `GET /procurement?view=lots` $\rightarrow$ `routes.procurement.index()`
* **Template**: [`templates/procurement.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/procurement.html)
* **JavaScript**: [`static/js/procurement.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/procurement.js)
* **What it shows**: An inventory card grid of all physical raw grain lots delivered to the dock. Displays Lot number (e.g. `DEMO-LOT-REL-01`, `RAW-LOT-515`), commodity name, supplier name, delivered quantity and unit, storage condition, received date, and visual QC status pill (`PENDING_QC`, `APPROVED`, `HOLD`, `REJECTED`).
* **Buttons & Actions**:
  1. **Lot Card Click (`.record-card-box`)**: Opens `DetailDrawer` displaying origin PO, linked Goods Receipt Note (GRN), delivery truck plate, and direct link to the QC Inspection page.
  2. **Status Filter Pills (`All`, `Pending QC`, `Approved`, `Hold`, `Rejected`)**: Filters the visible card grid in real time without page reload.
  3. **Search Input**: Filters cards by lot number or supplier.
  4. **`Update Storage Notes` Drawer Button**: Dispatches `PUT /api/procurement/lots/<id>` updating warehouse bin location or notes.
* **APIs Used**: `GET /api/procurement/lots`, `PUT /api/procurement/lots/<id>`.
* **Database Tables**: `raw_material_lots`, `suppliers`, `purchase_orders`, `goods_receipts`.
* **Status Changes**:
  - Updating storage condition does not change QC status. Status mutations on lots only occur when Member 2 (QC) signs off on the QC Inspection page.

---

### Page 4: Purchase Orders (PO)
* **Route**: `GET /procurement?view=po` $\rightarrow$ `routes.procurement.index()`
* **Template**: [`templates/procurement.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/procurement.html)
* **JavaScript**: [`static/js/procurement.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/procurement.js)
* **What it shows**: Formal purchasing contracts with suppliers. Displays PO number (`PO-2026-001`), supplier name, issue date, expected delivery date, total price in VND, number of line items, and fulfillment status (`PENDING`, `PARTIAL_RECEIVED`, `COMPLETED`, `CANCELLED`).
* **Buttons & Actions**:
  1. **`+ Create Purchase Order` Button (`#btnOpenPoModal`)**: Opens a modal to author an order.
  2. **`+ Add Line Item` Button in modal**: Dynamically appends a new ingredient row (select raw material, enter quantity, enter unit price).
  3. **`Save Purchase Order` Button**: Calculates total amount and submits `POST /api/procurement/purchase-orders`. Creates records in `purchase_orders` and `purchase_order_items`.
  4. **PO Card Click**: Opens `DetailDrawer` showing itemized lines, linked GRNs, and fulfillment progress.
  5. **`Void PO` Button in drawer**: Dispatches `POST /api/procurement/purchase-orders/<id>/void`. Voids unfulfilled orders with a confirmation prompt.
  6. **`Receive Goods` Shortcut Button**: Opens the GRN modal pre-populated with this PO's data.
* **APIs Used**: `GET /api/procurement/purchase-orders`, `POST /api/procurement/purchase-orders`, `POST /api/procurement/purchase-orders/<id>/void`.
* **Database Tables**: `purchase_orders`, `purchase_order_items`, `suppliers`, `goods_receipts`.
* **Status Changes**:
  - On Creation: PO status is initialized to `'PENDING'`.
  - On Void: Status transitions from `'PENDING'` $\rightarrow$ `'CANCELLED'`.
  - On Receipt (via GRN): Status transitions from `'PENDING'` $\rightarrow$ `'COMPLETED'` (or `'PARTIAL_RECEIVED'`).

---

### Page 5: Goods Receipts (GRN)
* **Route**: `GET /procurement?view=grn` $\rightarrow$ `routes.procurement.index()`
* **Template**: [`templates/procurement.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/procurement.html)
* **JavaScript**: [`static/js/procurement.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/procurement.js)
* **What it shows**: Dock delivery intake notes confirming the physical arrival of trucks. Displays GRN number (`GRN-2026-001`), linked PO number, arrival date and time, delivery truck license plate (`29C-438.12`), bill of lading reference, and the list of auto-generated raw material lots.
* **Buttons & Actions**:
  1. **`+ Receive Goods (GRN)` Button (`#btnOpenGrnModal`)**: Opens dock intake modal.
  2. **`Save Goods Receipt` Button in modal**: Submits `POST /api/procurement/grn`. Creates a row in `goods_receipts`, rows in `goods_receipt_items`, updates the linked PO to `COMPLETED`, and automatically instantiates a new row in `raw_material_lots`.
  3. **GRN Card Click**: Opens `DetailDrawer` showing delivery truck plate, driver reference, and direct clickable links to the newly created raw material lots.
  4. **`Print GRN` Button**: Triggers browser print layout for physical filing.
* **APIs Used**: `GET /api/procurement/grn`, `POST /api/procurement/grn`.
* **Database Tables**: `goods_receipts`, `goods_receipt_items`, `purchase_orders`, `raw_material_lots`.
* **Status Changes**:
  - Linked `purchase_orders`: Status updates from `'PENDING'` $\rightarrow$ `'COMPLETED'`.
  - Auto-generated `raw_material_lots`: Created with `status = 'PENDING'` and `qc_status = 'PENDING_QC'`.

---

### Page 6: QC Inspection Queue
* **Route**: `GET /qc?view=queue` $\rightarrow$ `routes.qc.index()`
* **Template**: [`templates/qc.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/qc.html)
* **JavaScript**: [`static/js/qc.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/qc.js)
* **What it shows**: The primary workbench for the Quality Assurance specialist. Displays a table of all raw material lots in `PENDING_QC` status waiting for inspection. Columns show Lot Number, Commodity, Supplier, Delivered Quantity, Intake Date, and Current Decision State.
* **Buttons & Actions**:
  1. **Table Row Click**: Dispatches `GET /api/qc/lot/<id>/review` and opens the **Multi-Pillar Lot Review Drawer**.
  2. **`Approve (APPROVED)` Button in drawer**: Dispatches `POST /api/qc/lot/<id>/decision` with `{"decision": "APPROVED"}`. Mutates database record, decrements the pending sidebar badge, and removes the lot from the pending queue.
  3. **`Hold (HOLD)` Button in drawer**: Dispatches decision with `{"decision": "HOLD"}`. Flags the lot as Quarantined.
  4. **`Reject (REJECTED)` Button in drawer**: Dispatches decision with `{"decision": "REJECTED"}`. Rejects the shipment.
  5. **`Override & Force Decision` Button**: If the inspector chooses to approve a lot that the AI or COA flagged as defective, this modal appears requiring a written regulatory reason.
  6. **`Download PDF Report` Button**: Dispatches `GET /api/qc/ai-inspection/<id>/pdf` and downloads the ReportLab dossier.
* **APIs Used**: `GET /api/qc/queue`, `GET /api/qc/lot/<id>/review`, `GET /api/qc/lot/<id>/release-decision`, `POST /api/qc/lot/<id>/decision`.
* **Database Tables**: `raw_material_lots`, `qc_samples`, `qc_tests`, `coa_documents`, `ai_inspections`, `qc_decisions`.
* **Status Changes**:
  - Before Action: `RawMaterialLot.status = 'PENDING'`, `qc_status = 'PENDING_QC'`.
  - After Approve: `status = 'APPROVED'`, `qc_status = 'APPROVED'`.
  - After Hold: `status = 'HOLD'`, `qc_status = 'HOLD'`.
  - After Reject: `status = 'REJECTED'`, `qc_status = 'REJECTED'`.

---

### Page 7: AI Camera Inspection Station
* **Route**: `GET /qc/camera-station` $\rightarrow$ `routes.qc.camera_station()`
* **Template**: [`templates/camera_station.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/camera_station.html)
* **JavaScript**: [`static/js/camera_station.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/camera_station.js)
* **What it shows**: The real-time edge vision inspection console. Shows live camera video with dynamic green (healthy) and red (defective) bounding box overlays, detected commodity type, Good % and Defect % meters, camera diagnostics, hold-steady progress bar, and final 5-frame consensus verdict card with the best 3 frame photographs.
* **Buttons & Actions**:
  1. **`Select Target Lot` Dropdown**: Binds the active camera session to an incoming raw material lot.
  2. **`⚙️ Camera Setup` Toolbar Button**: Opens the diagnostic drawer.
  3. **`📹 Test Camera` Button in drawer**: Dispatches device enumeration, displays camera resolution (e.g. `1280x720 HD`), and runs a 1.5-second black-screen luminance diagnostic.
  4. **Hold-Steady Locking Sequence (Automated)**: Triggered when the user holds the camera steady for 2.8s over at least 3 kernels.
  5. **`Confirm Accept (Approved)` Button on final card**: Dispatches `POST /api/qc/live-session/<id>/confirm-verdict` with `ACCEPT`. Enforces written reason if AI state was not PASS.
  6. **`Confirm Reject` Button**: Dispatches `confirm-verdict` with `REJECT`.
  7. **`Scan Next Sample` Button**: Resets camera canvas, clears locked state, and prepares for next tray.
  8. **`Download PDF Report` Button**: Triggers generation of signed AI Inspection Dossier.
* **APIs Used**: `POST /api/qc/live-session/create`, `POST /api/capture/<token>/frame`, `POST /api/qc/live-session/<id>/confirm-verdict`, `POST /api/qc/live-session/<id>/reset-lock`, `GET /api/qc/ai-model-status`.
* **Database Tables**: `live_sessions`, `live_frames`, `raw_material_lots`, `inspection_station_settings`, `ai_inspections`, `detected_defects`.
* **Status Changes**:
  - `live_sessions`: Created with `status = 'ACTIVE'` $\rightarrow$ updates to `status = 'CLOSED'` upon confirmation.
  - Linked `raw_material_lots`: Updates from `'PENDING_QC'` $\rightarrow$ `'APPROVED'` or `'REJECTED'`.

---

### Page 8: QC Test Results and COA
* **Route**: `GET /qc?view=tests` $\rightarrow$ `routes.qc.index()`
* **Template**: [`templates/qc.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/qc.html)
* **JavaScript**: [`static/js/qc.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/qc.js)
* **What it shows**: The laboratory testing archive and Certificate of Analysis library. Displays tested chemical/physical parameters (Moisture, Aflatoxin B1, FFA, Purity), test method standards (e.g. `ISO 17025`, `AOAC`), measured values, pass/fail status, and uploaded supplier PDF certificates.
* **Buttons & Actions**:
  1. **`+ Add Lab Sample` Button**: Opens modal to register a physical laboratory sample code (`SMP-DEMO-01`) and enter measured test parameters.
  2. **`Upload COA Document` Button**: Opens modal to upload supplier PDF certificate and enter document number and issuing laboratory.
  3. **`View Certificate File` Link**: Opens uploaded PDF in a new tab.
  4. **`Run Release Evaluation` Button**: Dispatches `GET /api/qc/lot/<id>/release-decision` to test compliance against stored `MATERIAL_SPECS`.
* **APIs Used**: `POST /api/qc/lot/<id>/sample`, `POST /api/qc/lot/<id>/coa`, `GET /api/qc/lot/<id>/release-decision`, `GET /api/qc/lot/<id>/qc-measures`, `POST /api/qc/lot/<id>/qc-measures`.
* **Database Tables**: `qc_samples`, `qc_tests`, `coa_documents`, `raw_material_lots`.
* **Status Changes**:
  - `COADocument`: Created with `is_verified = True` or `False`.
  - `QCTest`: Created with `is_pass = True` or `False`.

---

### Page 9: Recipes / BOM
* **Route**: `GET /production?view=recipes` $\rightarrow$ `routes.production.index()`
* **Template**: [`templates/production.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/production.html)
* **JavaScript**: [`static/js/production.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/production.js)
* **What it shows**: Master manufacturing formulas and Bill of Materials (BOM) specifications for finished products (e.g., *Corn Milk UHT 250ml*, *Pure Roasted Corn Snack Pack*). Displays recipe code (`RCP-CORN-01`), standard batch yield, yield unit (`Cases`), production line assignment, and ingredient quantities required per batch.
* **Buttons & Actions**:
  1. **`+ New Recipe` Button (`#btnOpenRecipeModal`)**: Opens recipe creation modal.
  2. **`+ Add Ingredient` Button in modal**: Appends a line item to select a raw material and specify required quantity per standard batch.
  3. **`Save Recipe` Button**: Submits `POST /api/production/recipes`. Inserts rows into `recipes` and `recipe_materials`.
  4. **Recipe Card Click**: Expands detailed ingredient ratio breakdown.
* **APIs Used**: `GET /api/production/recipes`, `POST /api/production/recipes`, `POST /api/production/recipes/<id>/ingredients`.
* **Database Tables**: `recipes`, `recipe_materials`, `products`, `raw_materials`.
* **Status Changes**:
  - Recipe record created with status `'ACTIVE'`.

---

### Page 10: Production Batches
* **Route**: `GET /production?view=batches` $\rightarrow$ `routes.production.index()`
* **Template**: [`templates/production.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/production.html)
* **JavaScript**: [`static/js/production.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/production.js)
* **What it shows**: The manufacturing floor execution console. Displays active production batches (`LOT-2026-001`), product name, production line, target quantity, actual completed quantity, progress bar, and status pill (`IN_PROGRESS`, `COMPLETED`, `PAUSED`).
* **Buttons & Actions**:
  1. **`+ New Production Batch` Button (`#btnOpenLaunchModal`)**: Opens batch launch modal.
  2. **`Product Selection` Dropdown**: Automatically pulls the active recipe BOM.
  3. **`Allocate Raw Material Lot` Dropdown**: **CRITICAL FOOD SAFETY GATE** — Populates ONLY lots with `qc_status == 'APPROVED'`. Unapproved lots are filtered out.
  4. **`Launch Batch` Submit Button**: Submits `POST /api/production/batches`. Validates approved stock, decrements raw material lot balance, and initializes batch `LOT-2026-xxx`.
  5. **Batch Card Click**: Opens batch dossier with the **5-Stage Process Stepper**:
     - Stage 1: Cleaning & Shelling
     - Stage 2: Roasting & Thermal Processing (120°C)
     - Stage 3: Milling & Pressing
     - Stage 4: Multi-Stage Filtration
     - Stage 5: Bottling, Capping & Case Packing
  6. **`Advance Stage` Stepper Button**: Submits `POST /api/production/batches/<id>/advance-stage`. Progresses the physical stage and logs timestamps.
  7. **`Record Packaging` Button**: Submits `POST /api/production/batches/<id>/packaging`. Logs carton boxes, seal rolls, and packaging waste.
* **APIs Used**: `GET /api/production/batches`, `GET /api/production/batches/<id>`, `POST /api/production/batches`, `POST /api/production/batches/<id>/advance-stage`, `POST /api/production/batches/<id>/packaging`.
* **Database Tables**: `production_batches`, `batch_raw_materials`, `production_process_records`, `packaging_records`, `raw_material_lots`.
* **Status Changes**:
  - `RawMaterialLot.quantity`: Decremented by the amount consumed.
  - `ProductionBatch.status`: Created as `'IN_PROGRESS'` $\rightarrow$ transitions to `'COMPLETED'` when stage 5 and packaging are completed.

---

### Page 11: BOM Planning and Readiness
* **Route**: `GET /production?view=recommendations` $\rightarrow$ `routes.production.index()`
* **Template**: [`templates/production.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/production.html)
* **JavaScript**: [`static/js/production.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/production.js)
* **What it shows**: Proactive inventory feasibility calculation. Cross-references all recipes against currently available QC-approved stock in the warehouse. Shows a green **Ready to Produce** or red **Lacking Materials** pill, maximum batches possible, and lists exact ingredient shortages.
* **Buttons & Actions**:
  1. **`Launch Batch` Action Button**: Directly opens the New Batch modal pre-populated with the ready product.
  2. **`View Shortages` Toggle**: Displays missing ingredient amounts in kg or tons.
  3. **Refresh Button**: Re-queries `/api/production/recommendations`.
* **APIs Used**: `GET /api/production/recommendations`.
* **Database Tables**: `recipes`, `recipe_materials`, `raw_materials`, `raw_material_lots`.
* **Status Changes**:
  - Read-only analytics; no database status mutation.

---

### Page 12: FEFO Inventory
* **Route**: `GET /warehouse?view=inventory` $\rightarrow$ `routes.warehouse.index()`
* **Template**: [`templates/warehouse.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/warehouse.html)
* **JavaScript**: [`static/js/warehouse.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/warehouse.js)
* **What it shows**: Finished consumer goods stored in the warehouse organized by **First-Expired, First-Out (FEFO)** rules. Displays SKU code (`INV-SKU-001`), product name, storage bin coordinates (e.g. `Zone A - Rack 04 Shelf 2`), pallet code, available quantity, manufacturing date, expiry date, days to expiry, and urgency pill (**FRESH**, **EXPIRING_SOON** $\le 30$ days, **EXPIRED**).
* **Buttons & Actions**:
  1. **`+ Stock Adjustment` Button (`#btnOpenAdjustModal`)**: Opens modal to record inventory count corrections or damaged box write-offs.
  2. **Inventory Card Click**: Opens `DetailDrawer` showing linked production batch and dispatch allocations.
  3. **Filter Pills (`All`, `Fresh`, `Expiring Soon`)**: Filters visible pallets by shelf-life urgency.
  4. **Search Bar**: Real-time text search by SKU code or product name.
* **APIs Used**: `GET /api/warehouse/inventory`, `POST /api/warehouse/sync-batch/<id>`.
* **Database Tables**: `warehouse_inventory`, `production_batches`, `products`.
* **Status Changes**:
  - Syncing completed batch inserts new inventory row with `available_quantity = batch.actual_quantity` and urgency computed dynamically.

---

### Page 13: Customer Channels
* **Route**: `GET /warehouse?view=customers` $\rightarrow$ `routes.warehouse.index()`
* **Template**: [`templates/warehouse.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/warehouse.html)
* **JavaScript**: [`static/js/warehouse.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/warehouse.js)
* **What it shows**: Retail supermarket and distributor partner accounts (e.g., *VinMart Supermarket Northern Division*, *BigC Central Vietnam*). Displays customer code, credit terms, delivery address, contact person, phone, and active dispatch history.
* **Buttons & Actions**:
  1. **`+ Add Customer` Button (`#btnAddCustomerPartner`)**: Opens customer onboarding modal.
  2. **`Save Customer` Button in modal**: Submits `POST /api/warehouse/customers`. Inserts new row into `customers`.
  3. **Customer Card Click**: Opens `DetailDrawer` showing order history and active dispatches.
* **APIs Used**: `GET /api/warehouse/customers`, `POST /api/warehouse/customers`.
* **Database Tables**: `customers`, `dispatches`.
* **Status Changes**:
  - New customer created with status `'ACTIVE'`.

---

### Page 14: Dispatch Orders
* **Route**: `GET /warehouse?view=dispatches` $\rightarrow$ `routes.warehouse.index()`
* **Template**: [`templates/warehouse.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/warehouse.html)
* **JavaScript**: [`static/js/warehouse.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/warehouse.js)
* **What it shows**: Outbound refrigerated delivery orders. Displays dispatch code (`DSP-2026-041`), destination, carrier fleet name, truck license plate (`29C-881.99`), driver phone, scheduled departure, and real-time cold-chain container temperature telemetry (`temp_sensor_celsius = 3.8°C`).
* **Buttons & Actions**:
  1. **`+ Create Dispatch Order` Button (`#btnOpenDispatchModal`)**: Opens delivery creation modal.
  2. **`Save Dispatch` Button in modal**: Submits `POST /api/warehouse/dispatches`. Decrements finished goods inventory and creates `dispatches` and `dispatch_items` records in `SCHEDULED` status.
  3. **Dispatch Card Click**: Opens `DetailDrawer` showing itemized product cases, driver contact, and temperature telemetry.
  4. **`Advance Status` Drawer Button**: Dispatches `POST /api/warehouse/dispatches/<id>/advance-status` (`SCHEDULED` $\rightarrow$ `LOADING` $\rightarrow$ `IN_TRANSIT` $\rightarrow$ `DELIVERED`).
  5. **`Void Dispatch` Drawer Button**: Submits `POST /api/warehouse/dispatches/<id>/void`. Voids order and restores stock to warehouse inventory.
* **APIs Used**: `GET /api/warehouse/dispatches`, `POST /api/warehouse/dispatches`, `POST /api/warehouse/dispatches/<id>/advance-status`, `POST /api/warehouse/dispatches/<id>/void`.
* **Database Tables**: `dispatches`, `dispatch_items`, `warehouse_inventory`, `customers`.
* **Status Changes**:
  - Dispatch transitions: `'SCHEDULED'` $\rightarrow$ `'LOADING'` $\rightarrow$ `'IN_TRANSIT'` $\rightarrow$ `'DELIVERED'`.
  - Void: Transitions to `'CANCELLED'` and restores inventory.

---

### Page 15: Traceability
* **Route**: `GET /traceability` $\rightarrow$ `routes.traceability.index()`
* **Template**: [`templates/traceability.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/traceability.html)
* **JavaScript**: [`static/js/traceability.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/traceability.js)
* **What it shows**: The flagship Farm-to-Fork 7-tier value chain graph. Entering any identifier (batch code `LOT-2026-089`, intake lot `RAW-LOT-512`, or dispatch note `DSP-2026-041`) renders the complete upstream and downstream supply chain sequence:
  - **Tier 1 (Supplier)**: Origin farm, VietGAP certification, and contacts.
  - **Tier 2 (Intake Lot)**: Delivery quantity, PO number, and truck plate.
  - **Tier 3 (QC & Lab)**: Chemical Aflatoxin test values, ISO 17025 COA, and YOLO AI defect scan.
  - **Tier 4 (Production)**: 5 manufacturing stages, roasting temperatures (120°C), and shift managers.
  - **Tier 5 (Packaging)**: Carton box count, seal rolls used, and waste metrics.
  - **Tier 6 (Warehouse)**: Bin coordinates (`Zone A-04`) and FEFO expiry status.
  - **Tier 7 (Dispatch)**: Truck plate (`29C-881.99`), cold-chain temperature (3.8°C), and supermarket destination.
* **Buttons & Actions**:
  1. **Omni-Search Bar (`#traceSearchInput`)**: Text input for batch, lot, or dispatch codes.
  2. **`Search` Button**: Dispatches `GET /api/traceability/chain/<identifier>` and animates the 7-tier card sequence.
  3. **Sample Search Pills**: Quick-click shortcuts for `LOT-2026-089`, `RAW-LOT-512`, and `DSP-2026-041`.
  4. **Tier Node Accordions**: Expands detailed parameters (e.g. laboratory test values or roasting oven logs).
* **APIs Used**: `GET /api/traceability/search?q=...`, `GET /api/traceability/chain/<identifier>`.
* **Database Tables**: `production_batches`, `batch_raw_materials`, `raw_material_lots`, `suppliers`, `qc_samples`, `qc_tests`, `coa_documents`, `ai_inspections`, `production_process_records`, `packaging_records`, `warehouse_inventory`, `dispatches`.
* **Status Changes**:
  - Read-only graph query engine; no status mutation.

---

### Page 16: Executive Dashboard
* **Route**: `GET /dashboard` $\rightarrow$ `routes.dashboard.index()`
* **Template**: [`templates/dashboard.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/dashboard.html)
* **JavaScript**: [`static/js/dashboard.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/dashboard.js) & [`static/js/dashboard_live_card.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/dashboard_live_card.js)
* **What it shows**: The plant manager command center. Displays:
  - 4 Executive KPI Cards: Total Finished Goods Stock Value, Active Production Batches, QC Queue Pending Lots, Today's Scheduled Dispatches.
  - Live AI Inspection Card: Samples inspected today, Pass/Review/Reject counters, and latest specimen photo.
  - Daily Production Volume and Defect Rate trend charts.
  - Recent batches table with status pills.
* **Buttons & Actions**:
  1. **KPI Card Drill-Downs (`#kpiCardInventory`, `#kpiCardBatches`, `#kpiCardQc`, `#kpiCardDispatches`)**: Wrapped in active links jumping to the corresponding operational modules.
  2. **Date Range Filter (`#axionDateRangeSelect`)**: Re-queries `/api/dashboard/charts` for 7d, 30d, or 90d periods.
  3. **BOM Component Dropdown (`#bomProductSelect`)**: Filters BOM donut chart by product SKU.
  4. **Batch Options Menu Button (`⋮`)**: Opens popover with shortcuts to Inspect Stage, Trace Value Chain, or QC Gate.
* **APIs Used**: `GET /api/dashboard/stats`, `GET /api/dashboard/charts`, `GET /api/dashboard/live-inspection-summary`.
* **Database Tables**: `warehouse_inventory`, `production_batches`, `raw_material_lots`, `dispatches`, `live_sessions`, `live_frames`.
* **Status Changes**:
  - Read-only aggregation and navigation center.

---

### Page 17: Operational Analytics
* **Route**: `GET /reports` $\rightarrow$ `routes.reports.index()`
* **Template**: [`templates/reports.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/reports.html)
* **JavaScript**: [`static/js/reports.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/reports.js)
* **What it shows**: Cross-department business intelligence reporting. Displays aggregated metrics for manufacturing throughput, QC pass/defect rates, warehouse storage utilization, and cold-chain compliance.
* **Buttons & Actions**:
  1. **Time Horizon Dropdown (`7 Days`, `30 Days`, `90 Days`)**: Updates analytical aggregations.
  2. **`Export CSV` Button (`#btnExportSummaryCsv`)**: Dispatches `GET /api/reports/export-csv?period=...` to generate and download a live CSV file compiled from active database records.
  3. **Module Filter Pills (`All`, `QC & Defects`, `Production`, `Warehouse`)**: Toggles report categories.
* **APIs Used**: `GET /api/reports/analytics`, `GET /api/reports/export-csv`.
* **Database Tables**: `production_batches`, `ai_inspections`, `raw_material_lots`, `dispatches`, `warehouse_inventory`.
* **Status Changes**:
  - Read-only analytical queries and file stream generation.

---

### Page 18: Alerts Center
* **Route**: `GET /alerts` $\rightarrow$ `routes.dashboard.alerts_view()`
* **Template**: [`templates/alerts.html`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/templates/alerts.html)
* **JavaScript**: [`static/js/alerts.js`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/static/js/alerts.js)
* **What it shows**: Central repository of factory safety warnings. Notifications are grouped by severity (`CRITICAL`, `WARNING`, `INFO`) and module (`Warehouse`, `QC`, `Procurement`). Displays rule codes, error messages, lot/batch tags, and resolution status.
* **Buttons & Actions**:
  1. **`Mark as Read` Button on alert card**: Submits `POST /api/alerts/<id>/read`. Updates `NotificationAlert.is_read = 1`.
  2. **`Clear All Acknowledged` Button**: Submits `POST /api/alerts/clear-all`. Purges resolved notifications.
  3. **`Run Alert Evaluation` Button**: Submits `POST /api/alerts/evaluate`. Manually triggers the automated evaluation engine across inventory, shelf-life, and QC backlog.
  4. **`+ New Alert Rule` Button**: Submits `POST /api/alerts/rules` to configure dynamic threshold alerts.
* **APIs Used**: `GET /api/alerts`, `POST /api/alerts/<id>/read`, `POST /api/alerts/clear-all`, `POST /api/alerts/evaluate`, `POST /api/alerts/rules`.
* **Database Tables**: `notification_alerts`, `alert_rules`, `raw_materials`, `warehouse_inventory`, `raw_material_lots`.
* **Status Changes**:
  - `NotificationAlert.is_read`: Changes from `False` $\rightarrow$ `True`.

---

## Unverified Items Audit (Marked as "Not Verified")

In accordance with strict verification rules, the following behaviors in the code have been audited and identified as simulated or not verified:

1. **Material Classifier Dock Camera Accuracy (`not verified`)**:
   - The classifier model (`models/material_cls.pt`) was trained on Roboflow crops and synthetic scenes. Its quantitative accuracy on live factory camera imagery under actual dock ambient lighting has **not been verified with labeled ground-truth photos**.
2. **Refrigerated Vehicle Live GPS/IoT Satellite Feed (`not verified`)**:
   - The cold-chain temperature telemetry (`temp_sensor_celsius = 3.8°C` on dispatch order `DSP-2026-041`) is stored and updated via REST API; it is a software simulation and is **not verified against an active cellular or satellite hardware IoT modem**.
3. **Automated SCADA PLC Line Synchronization (`not verified`)**:
   - The 5-stage manufacturing stepper (roasting oven temperature at 120°C, pressing pressure at 180 bar) is advanced through web UI user interaction; it is **not verified against live physical factory PLC sensors or industrial OPC-UA networks**.
4. **OCR Parsing of Uploaded Supplier COA PDFs (`not verified`)**:
   - Laboratory parameter validation parses structured relational database rows (`QCTest`) and JSON notes; optical character recognition (OCR) of raw scanned paper PDFs is **not verified / not implemented**.
