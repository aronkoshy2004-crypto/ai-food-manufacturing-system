# 13-STEP END-TO-END DEMO SCRIPT (§12)
## FOOD MANUFACTURING EXECUTION & TRACEABILITY SYSTEM — FOOD MAN

---

### 1. Overview & Demonstration Accounts

The system is designed following modern industrial standards (**Theme Light #F5F6F8**, accent **Navy #162B4E**, 2-column card grid, and right-hand **Slide-in Detail Drawer**).

| Role | Demo User | Email / Username | Permissions & Modules |
| :--- | :--- | :--- | :--- |
| **Admin** | Nguyen Hoang Minh | `admin@foodman.vn` | Full control across all 6 modules |
| **Procurement** | Vu Thu Thao | `procurement@foodman.vn` | Suppliers, Raw Materials, Purchase Orders, Goods Receipt (GRN) |
| **QC Inspector** | Pham Thu Trang, MSc. | `qc@foodman.vn` | QC Queue, Lab Tests, COA Certificates, AI Defect Vision |
| **Production** | Tran Minh Quan | `production@foodman.vn` | BOM Recommendations, Batch Creation, 5-Stage Stepper, Packaging |
| **Warehouse** | Hoang Dinh Tuan | `warehouse@foodman.vn` | FEFO Inventory, Reefer Dispatches, IoT Sensors, Customers |

> **Quick Demo Login Links:**
> - `http://127.0.0.1:5000/demo-login/Admin`
> - `http://127.0.0.1:5000/demo-login/Procurement`
> - `http://127.0.0.1:5000/demo-login/QC`
> - `http://127.0.0.1:5000/demo-login/Production`
> - `http://127.0.0.1:5000/demo-login/Warehouse`

---

## 2. Detailed 13-Step Acceptance Scenario (§12)

```
[PO] -> [GRN] -> [QC & AI] -> [QC APPROVE] -> [BOM RECOMMEND] -> [BATCH] -> [PACKAGING] -> [FEFO WAREHOUSE] -> [DISPATCH] -> [DASHBOARD] -> [7-TIER TRACEABILITY]
```

---

### STEP 1: Role-Based Access Control & Navigation
- **Objective:** Demonstrate multi-user role enforcement and adaptive navigation.
- **Action steps:**
  1. Navigate to `http://127.0.0.1:5000/login`.
  2. Click each quick-login button: `Admin`, `Procurement`, `QC`, `Production`, `Warehouse`.
  3. Observe the left sidebar navigation (`Sidebar`):
     - *QC* account only sees *Quality & Lab*.
     - *Production* account only sees *Production & Packaging*.
     - *Admin* account sees all 6 modules with badge counts.
- **Verification points:**
  - Sidebar displays authorized modules strictly adhering to the role matrix.
  - Bottom-left profile displays user's full name and department.

---

### STEP 2: Supplier & Raw Material Master Data
- **Objective:** Establish certified supplier records (Organic / ISO 22000) and raw material catalog.
- **Action steps:**
  1. Log in with **Procurement** or **Admin** role.
  2. Navigate to: `http://127.0.0.1:5000/procurement?view=suppliers`.
  3. View 2-column supplier cards: `Moc Chau Farm Organic Co.`, `Tetra Pak Sweden`. Click a card to open the slide-in drawer (audit ratings, certifications).
  4. Switch to **"Raw Materials"** tab (`/procurement?view=raw-materials`):
     - View raw material code `RM-001` (Organic Fresh Cow Milk Grade 1).

---

### STEP 3: Multi-Line Purchase Order Creation
- **Objective:** Generate a raw material purchase order with multiple line items and auto-calculated totals.
- **Action steps:**
  1. Select **"Purchase Orders"** tab (`/procurement?view=po`).
  2. Click **`+ Create New Purchase Order`** in the top-right corner.
  3. In the creation modal:
     - Select supplier: *Moc Chau Farm Organic Co.*.
     - Add line 1: *Organic Fresh Cow Milk Grade 1* — Quantity: `25.0 Tons` — Unit price: `18,500,000 VND/Ton`.
     - Add line 2: *Refined Cane Sugar RE Sucre* — Quantity: `2.0 Tons` — Unit price: `22,000,000 VND/Ton`.
     - Calculated total amount: `506,500,000 VND`.
  4. Click **Save & Approve Purchase Order**.
- **Verification points:**
  - PO card appears immediately with code `PO-2026-xxxx` and status pill `APPROVED` (green).

---

### STEP 4: Goods Receipt (GRN) & Automated Lot Generation (`PENDING_QC`)
- **Objective:** Receive milk tanker delivery, record security seal integrity, and auto-generate raw material lot in pending QC state.
- **Action steps:**
  1. Select **"GRN Receipt"** tab (`/procurement?view=grn`).
  2. Click **`+ Create GRN Receipt`**:
     - Select PO created in Step 3.
     - Enter tanker license plate: `29C-882.15`.
     - Bill of lading: `BL-MC-0908`.
     - Notes: *Valve security seal intact, tanker temp 3.8°C*.
  3. Click **Confirm Goods Receipt**.
  4. Switch to **"Raw Material Lots"** tab (`/procurement?view=lots`):
     - Observe generated raw material lot: `LOT-RM-2026-xxx`.
     - Status pill displays amber: `PENDING_QC`.
- **Verification points:**
  - QC Queue badge count on the sidebar increases by +1.

---

### STEP 5: Lab Testing, COA Certification & YOLO AI Vision Inspection
- **Objective:** Perform microbiological and physicochemical screening, verify COA, and run YOLOv8 visual defect detection.
- **Action steps:**
  1. Log in with **QC Inspector** role (or use Admin) and navigate to `http://127.0.0.1:5000/qc`.
  2. In the **QC Queue**, locate the pending lot from Step 4.
  3. Click the card to open the **Wide Combined Review Drawer**:
     - **Section 1 (YOLO AI Vision):** Pallet/seal photo displayed with bounding boxes, defect labels (e.g. `Torn Seal: 94.2%`, `Crushed Corner: 88.5%`), inference latency: `~48ms` via `YOLOv8x-FoodDefect-v2.1`.
     - **Section 2 (Lab Test Table):** Brix Level `12.3°Bx`, pH `6.68`, Coliform `0 CFU/ml`, Betalactam Antibiotic `Negative` (All passed).
     - **Section 3 (COA Certificate):** Displays accredited lab report VILAS 102 / ISO 17025.
- **Verification points:**
  - Yellow advisory notice: *"YOLO AI RESULTS ARE ADVISORY ONLY AND DO NOT AUTO-APPROVE. LICENSED QC INSPECTOR CONFIRMATION REQUIRED."*
  - Known model limitations and dense cluster calibration details: see [AI Model Limitations](AI_MODEL_LIMITATIONS.md).

---

### STEP 6: Human-Only QC Gate Approval
- **Objective:** Enforce food safety compliance — AI never auto-approves; a licensed human inspector must make the final determination.
- **Action steps:**
  1. At the bottom of the QC review drawer, locate the action buttons: **`Approve`**, **`Hold`**, **`Reject`**.
  2. Enter decision notes: *Verified compliant with ISO 22000 standards, approved for production intake*.
  3. Click the green **`Approve Quality`** button.
  4. Success toast notification appears. Status pill turns `APPROVED` (Green).
- **Verification points:**
  - Lot exits the `QC Queue` and appears in the production availability endpoint (`/api/qc/production-ready-lots`).

---

### STEP 7: BOM Inventory Verification & Production Recommendations
- **Objective:** Rule engine cross-references approved QC lots against bill of materials formulas.
- **Action steps:**
  1. Navigate to **Production & Packaging**: `http://127.0.0.1:5000/production?view=recommendations`.
  2. Observe product recommendation cards:
     - Product card *UHT Low Sugar Milk 180ml*: Green pill `PRODUCEABLE` (Sufficient materials).
     - Displays maximum feasible batch count: *2 - 3 Batches*.
     - Products lacking ingredients display red pill `LACKING_MATERIALS` with ingredient deficit breakdown.

---

### STEP 8: Production Batch Creation Wizard Consuming Approved Lots
- **Objective:** Allocate approved material lots into `batch_raw_materials` table and instantiate 5 process stages.
- **Action steps:**
  1. On the produceable product card, click **`+ Create Production Batch`** (or use top header button).
  2. Input parameters:
     - Target yield: `5,000 Cartons`.
     - Line: `Line A1 - Tetra Pak Aseptic 250ml`.
  3. Click **Start Production**.
- **Verification points:**
  - New production batch created with identifier `LOT-2026-xxx`.
  - Initial status: `IN_PROGRESS` (Amber), progress bar at 20%.

---

### STEP 9: 5-Stage Stepper Timeline & Packaging Certification
- **Objective:** Progress batch through 5 processing milestones and log aseptic packaging compliance.
- **Action steps:**
  1. Switch to **"Production Batches"** tab (`/production?view=batches`).
  2. Click the batch card to open the **Stepper Timeline Drawer**:
     - *Stage 1: Material Preparation* [Completed]
     - *Stage 2: Mixing & Homogenization* [Completed]
     - *Stage 3: UHT Pasteurization* [Completed]
     - *Stage 4: Aseptic Filling* [Completed]
     - *Stage 5: Packaging & Palletizing* [Completed]
  3. Click **Advance Stage** until reaching 100%.
  4. Log packaging certificate: *5,000 5-ply cartons + Tetra Brik aseptic film*.
  5. Click **Confirm Batch Completion**.
- **Verification points:**
  - Batch status transitions to `COMPLETE` (Green).
  - Module 4 warehouse intake hook (`/api/production/completed-batches`) is activated.

---

### STEP 10: Warehouse Inventory Sync & FEFO Priority Ordering
- **Objective:** Only `COMPLETE` batches sync to warehouse inventory and automatically sort by First Expired, First Out (FEFO).
- **Action steps:**
  1. Navigate to **Warehouse & Logistics**: `http://127.0.0.1:5000/warehouse?view=inventory`.
  2. Observe warehouse inventory grid:
     - Completed batch appears with SKU code (e.g. `INV-SKU-xxx`), rack location (`Zone C - Pallet Flow Rack`).
     - Cards are strictly ordered by ascending expiration date (`expiry_date ASC`).
     - Items expiring within 15 days display red urgency badge: `EXPIRING_SOON`.
- **Verification points:**
  - Strict FEFO ordering guarantees near-expiry finished goods are allocated first.

---

### STEP 11: Reefer Dispatch Order & Live Inventory Decrement
- **Objective:** Create retail customer delivery, monitor refrigerated cargo temperature, and verify live stock decrement.
- **Action steps:**
  1. Switch to **"Dispatches"** tab (`/warehouse?view=dispatches`).
  2. Click **`+ Create New Dispatch`**:
     - Customer: *WinCommerce Retail Group (WinMart)*.
     - Select finished inventory lot from Step 10 (Available quantity: `5,000 Cartons`).
     - Dispatch quantity: `1,000 Cartons`.
     - Carrier fleet: *Truck 29C-998.11 (Driver: Le Van Tien)*.
  3. Click **Confirm Dispatch Departure**.
  4. Return to **"FEFO Inventory"** tab:
     - Available lot quantity decrements immediately: from `5,000` down to `4,000 Cartons`!
- **Verification points:**
  - Dispatch order `DSP-2026-xxx` displays cargo temperature sensor `❄ 3.8°C` (within compliant `2.0°C - 6.0°C` range).

---

### STEP 12: Central Executive Dashboard, Analytics & System Alert Engine
- **Objective:** Aggregate real-time executive KPIs, visualize Chart.js trend lines, and trigger intelligent alert scans.
- **Action steps:**
  1. Access **Executive Dashboard** (`/dashboard`):
     - View 4 KPI cards: *Stock Value (Billion VND)*, *Expiring Soon Count*, *Today's Dispatches*, *Open Alerts*.
     - Dual-line Chart.js comparing 7-day production vs. dispatch throughput.
     - Donut Chart breaking down product category distribution.
  2. Navigate to **Reports & Analytics** (`/reports`):
     - Review 3 advanced charts: *3-Stage Production Throughput*, *QC & AI Defect Distribution*, *Dispatch Volume & Reefer Temp Trend*.
     - Test time range filters: `7 Days`, `30 Days`, `90 Days`.
     - Click **"Export Report"** to download CSV summary.
  3. Navigate to **Alerts Center** (`/alerts`):
     - Click **"Run System Scan"** to trigger automated checks: Low stock thresholds, near-expiry lots, and pending QC backlogs.

---

### STEP 13: 7-Tier Flagship Traceability Chain
- **Objective:** Prove the unbroken chain of custody from organic dairy farm to retail consumer shelf.
- **Action steps:**
  1. Enter batch code (e.g. `LOT-2026-005` or `LOT-2026-089`) into the top search bar and press **Enter** (or visit `/traceability`).
  2. Screen renders the comprehensive **7-Tier Value Chain**:
     ```
     [1. Supplier] ──> [2. Raw Material Lot] ──> [3. QC & AI Testing] ──>
     [4. Production Batch]  ──> [5. Packaging] ──> [6. FEFO Inventory] ──> [7. Reefer Dispatch]
     ```
  3. Click each tier node:
     - **Tier 1**: View Ba Vi / Moc Chau Farm organic certifications.
     - **Tier 3**: View Lab 0 CFU Coliform tests and YOLO AI inspection scan.
     - **Tier 4 & 5**: View UHT pasteurization logs and Tetra Brik packaging spec.
     - **Tier 7**: View WinMart delivery details and reefer temperature log `3.8°C`.
- **Verification points:**
  - Full relational chain linked 100% accurately without missing nodes or stubbed placeholders.

---

### BONUS: FoodMan Operations AI Assistant (Chatbot)
- **Objective:** Interact with domain-specialized AI assistant for supply chain insights.
- **Action steps:**
  1. Click the floating Navy button at the bottom-right corner (`FoodMan AI Assistant`).
  2. Smart drawer opens:
     - Click suggested prompt: `⚡ FEFO Inventory` ➔ AI immediately responds with stock levels and near-expiry lots.
     - Ask: *"Trace batch LOT-2026-005"* ➔ AI summarizes the 7 tiers with navigation links.
     - Ask: *"How many lots are pending QC?"* ➔ AI reports queue metrics and human-only approval policy.
- **Verification points:**
  - AI assistant queries real-time database and returns formatted Markdown with badges and navigation links.

---

## 3. End-to-End Automated Continuous Test Command

To verify all 13 steps continuously in an automated end-to-end HTTP test (no manual database editing required):

```powershell
python "C:\Users\L E N O V O\.gemini\antigravity-ide\brain\433255af-d683-47ef-8854-6576f05b1fcc\scratch\test_phase5_continuous_acceptance.py"
```

Expected result: **13/13 Acceptance Criteria (§12) PASSED CONTINUOUSLY WITH 100% SUCCESS!**
