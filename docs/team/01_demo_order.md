# Food Man — Combined Live Demo Script & Handover Protocol

**Total Run Time**: 8 to 10 Minutes  
**Target Audience**: Examiners, Academic Supervisors, Industrial Auditors  
**System Mode**: Production Build running on `http://localhost:5000` (or Cloudflare Tunnel URL)  
**Quick Role Switcher**: Click the user profile icon or navigate to `/demo-login/<role>` for 1-click credential handover.

---

## 1. Demo Roles & Pre-Flight Checklist

| Team Role | Team Member | Primary System Role | Demo Login Endpoint | Assigned Screen View |
| :--- | :--- | :--- | :--- | :--- |
| **Member 4** | Platform & Logistics Lead | Admin / Warehouse | `/demo-login/admin` | Executive Dashboard (`/dashboard`) |
| **Member 3** | Manufacturing & Intake Lead | Procurement / Production | `/demo-login/procurement` | Procurement & Intake (`/procurement`) |
| **Member 1** | Computer Vision & AI Lead | QC Inspector | `/demo-login/qc` | Inspection Station (`/qc/camera-station`) |
| **Member 2** | Quality Assurance Lead | QC Manager / Specialist | `/demo-login/qc` | QC Queue & Lot Review (`/qc?view=queue`) |
| **Member 3** | Manufacturing & Intake Lead | Production Supervisor | `/demo-login/production` | Batch Production (`/production?view=batches`) |
| **Member 4** | Platform & Logistics Lead | Logistics & Technologist | `/demo-login/warehouse` | Traceability (`/traceability`) & Food Tech (`/food-technologist`) |

### Pre-Flight Hardware Setup (60 Seconds Before Start)
1. Launch system via desktop shortcut or command line:
   ```bash
   python wsgi.py
   ```
2. Verify camera connection:
   - Built-in laptop webcam or smartphone connected via Iriun/DroidCam.
   - Place a clean sample dish of Corn or Peanuts on the desk next to the laptop.
3. Open Chrome or Edge at `http://localhost:5000`.

---

## 2. Combined Demo Execution Script

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TIMELINE OVERVIEW (9.0 Minutes Total)                                                             │
│ 00:00 - 01:00 : Member 4 (System Opening & Executive Dashboard)                                  │
│ 01:00 - 02:30 : Member 3 (Procurement, Supplier Vetting & Intake Lot Generation)                 │
│ 02:30 - 04:30 : Member 1 (AI Inspection Station, Hold-Steady 5f Lock & Majority Voting)          │
│ 04:30 - 06:30 : Member 2 (QC Lab Release Decision Engine, Demo Lots & Signed PDF)               │
│ 06:30 - 07:45 : Member 3 (Production Safety Gate, 5-Stage Stepper & Packaging)                  │
│ 07:45 - 09:00 : Member 4 (Warehouse FEFO, Cold-Chain Fleet, 7-Tier Traceability & Conclusion)   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Step 0: Opening & Architecture Overview (Member 4 — 1.0 Minute)

* **Logged In As**: Admin (`admin@foodman.vn` via `/demo-login/admin`)
* **Screen Displayed**: Executive Dashboard (`http://localhost:5000/dashboard`)
* **Spoken Script**:
  > *"Good morning committee and examiners. Welcome to **Food Man**, our integrated Food Manufacturing Execution and AI Quality Control System. In modern food manufacturing, safety standards require an unbroken digital chain of custody from incoming grain silos to supermarket shelves.*
  >
  > *Food Man addresses this across five operational pillars: Procurement Intake, Real-Time AI Computer Vision, Laboratory Release Compliance, 5-Stage Batch Production, and Cold-Chain FEFO Logistics. Today, our four team members will walk you through a live, end-to-end grain intake cycle.*
  >
  > *I will now hand over the keyboard to Member 3, who engineered our Procurement and Raw Material Intake pipeline."*
* **Handover Action**:
  - Member 4 clicks the sidebar logout button or visits `http://localhost:5000/demo-login/procurement`.
  - Member 3 takes the keyboard.

---

### Step 1: Procurement, Supplier Vetting & GRN Intake (Member 3 — 1.5 Minutes)

* **Logged In As**: Procurement Officer (`procurement@foodman.vn`)
* **Screen Displayed**: Procurement Workspace (`http://localhost:5000/procurement?view=suppliers`)
* **Click Path**:
  1. Open **Suppliers** view (`/procurement?view=suppliers`).
  2. Click supplier card **AgriGrain Certified Supply Ltd** (`SUP-DEMO-REL`):
     - Show ISO 17025 certification badges, contact info, and rating (4.9/5.0).
  3. Switch to **Purchase Orders** tab (`/procurement?view=po`):
     - Click `PO-2026-001` to open the slide-over `DetailDrawer`. Point to the line items (Corn 25 Tons, unit price 8,500,000 VND).
  4. Switch to **Goods Receipts (GRN)** tab (`/procurement?view=grn`):
     - Click the newest receipt note. Point out delivery truck plate (`29C-438.12`) and linked raw material intake lots.
  5. Switch to **Raw Material Lots** tab (`/procurement?view=lots`):
     - Point out `DEMO-LOT-REL-01` (Corn, 25 Tons):
     - Highlight status badge: **`PENDING`** with QC status **`PENDING_QC`**.
* **Spoken Script**:
  > *"Thank you. I built the Procurement and Raw Material Intake infrastructure. Everything starts with verified suppliers. In our directory, every supplier must maintain active food safety certifications like VietGAP or ISO 22000.*
  >
  > *When shipments arrive at our intake dock under Purchase Order PO-2026-001, our receiving team creates a Goods Receipt Note (GRN). This automatically instantiates a new physical Raw Material Lot in our database.*
  >
  > *Notice that lot `DEMO-LOT-REL-01` is strictly flagged as `PENDING_QC`. Our system enforces an immutable rule: no unapproved lot can ever enter food manufacturing. To release this grain, it must pass both visual AI screening and chemical lab certification.*
  >
  > *I now hand over to Member 1, who engineered our AI Inspection Station to physically scan this lot."*
* **Handover Action**:
  - Member 3 clicks `/demo-login/qc`.
  - Member 1 takes the keyboard and positions the camera over the sample dish.

---

### Step 2: AI Inspection Station, 5-Frame Lock & Majority Voting (Member 1 — 2.0 Minutes)

* **Logged In As**: QC Inspector (`qc@foodman.vn`)
* **Screen Displayed**: Unified Laptop Inspection Station (`http://localhost:5000/qc/camera-station`)
* **Click Path**:
  1. In the top toolbar, select Target Lot: choose **`DEMO-LOT-REL-01 (Corn)`** from the dropdown.
  2. Point out the live telemetry overlay:
     - Real-time video canvas running at **1 FPS** on CPU.
     - Live bounding boxes identifying healthy corn kernels in green.
     - Material Classifier identifying grain type as **Corn**.
  3. Hover or hold the camera steady **15–20 cm above the sample dish**:
     - The bottom HUD displays: *"🎯 Hold steady..."*
     - The green locking progress bar advances: `20%` → `40%` → `60%` → `80%` → `100%`.
     - Sequence triggers: *"🔒 Locking sample... Frame 1 of 5 ... Frame 5 of 5"*.
  4. The **Final Result Card** appears:
     - Metrics: **Good: 100%**, **Defects: 0%**, Quality State: **✓ PASS**.
     - Point to the **Best 3 Specimen Frames** captured during the lock sequence.
  5. *(Optional Fallback if physical camera is offline)*:
     - Click `/qc?view=ai-inspection`.
     - Select `DEMO-LOT-REL-01`, pick `static/uploads/raw/20261017_035528_test_corn.jpg`, click **Run AI Inspection** (< 1 sec inference).
* **Spoken Script**:
  > *"Thank you. I engineered the AI Visual Inspection Station. In food receiving, single static photographs are vulnerable to motion blur, lighting glares, or transient shadows. To ensure industrial robustness, we built a dual-engine architecture with automated multi-frame locking.*
  >
  > *We combine an Ultralytics YOLOv8 defect detector, a secondary YOLOv8n-cls material classifier, and OpenCV CIE Lab Otsu colour segmentation. The camera feed streams directly into a client-side motion analyzer that downsamples frames to 48x36 grayscale.*
  >
  > *When I hold the camera steady for 2.8 seconds, the system automatically triggers a 5-frame locking burst. In the backend, our server performs spatial kernel tracking and majority voting across all 5 frames. This completely eliminates single-frame false alarms.*
  >
  > *For this corn lot, the 5-frame consensus confirms zero mold and 100% clean kernels, generating an AI quality state of `PASS`.*
  >
  > *However, food safety standards mandate that visual appearance alone is not enough—chemical toxins like Aflatoxin are invisible to cameras. I now hand over to Member 2 to demonstrate how our release decision engine validates the lab parameters."*
* **Handover Action**:
  - Member 1 stays logged in as QC or clicks `/qc?view=queue`.
  - Member 2 takes the keyboard.

---

### Step 3: Quality Control & Release Decision Engine (Member 2 — 2.0 Minutes)

* **Logged In As**: QC Specialist / Manager (`qc@foodman.vn`)
* **Screen Displayed**: QC Inspection Queue (`http://localhost:5000/qc?view=queue`)
* **Click Path**:
  1. In the QC Queue table, locate **`DEMO-LOT-REL-01`** (Corn):
     - Click the row to open the slide-over **Lot Review Drawer**.
     - Point out the **Release Decision Card**:
       - Paper Check (COA): `PASS` (Moisture 12.2% < 14%, Aflatoxin 1.2 ppb < 5 ppb).
       - Camera Check (AI): `PASS` (0 defects, 94% confidence).
       - Combined Outcome: **`RELEASE`** (Green banner: *"All laboratory COA parameters and camera AI inspection verified compliant. Safe to release."*).
  2. Click **"✓ Confirm Accept (Approved)"**:
     - System updates `RawMaterialLot.qc_status = 'APPROVED'`.
     - Click **"📄 Download PDF Report"**:
       - A new browser tab opens rendering the official signed Certificate of Analysis / AI Inspection Dossier generated dynamically via ReportLab.
  3. Close drawer, then click row **`DEMO-LOT-REL-03`** (Peanut):
     - Show the critical food safety boundary:
       - Camera Check (AI): `PASS` (Grain surface looks visually clean).
       - Paper Check (COA): **`FAIL`** (Lab HPLC detected Aflatoxin B1 at **4.5 ppb**, exceeding the strict statutory limit of **2.0 ppb**).
       - Combined Outcome: **`REJECT`** (Red banner: *"Peanut lot rejected: COA aflatoxin safety limit failed. AI inspection cannot override."*).
     - Point out the mandatory advisory note: *"Camera screening only. Peanut lots need lab testing before release."*
  4. Demonstrate Human Override Audit:
     - Click "Override & Force Accept". The modal appears demanding a **Written Justification** (Auditor name, timestamp, and formal reason). Show that submitting without a reason is blocked with HTTP 400.
* **Spoken Script**:
  > *"Thank you. I developed the Quality Control and Release Decision Engine. In regulatory food environments under HACCP and ISO 22000, AI must never be a black box that unilaterally releases food ingredients.*
  >
  > *Our pure `release_decision()` function evaluates a strict deterministic decision matrix combining chemical lab results and visual AI data. On `DEMO-LOT-REL-01`, both the ISO 17025 accredited COA and our YOLO vision engine agree. The release button is enabled, and approving it generates this official, cryptographically logged PDF Inspection Dossier.*
  >
  > *Crucially, examine `DEMO-LOT-REL-03`. The peanuts appear visually spotless, so a naive vision system would have approved them. However, our COA parser detected Aflatoxin B1 at 4.5 ppb—more than double the 2.0 ppb safety threshold. Our engine immediately forces a hard `REJECT`. AI vision can never override a failed chemical lab test.*
  >
  > *Furthermore, if an inspector attempts to override any non-pass verdict, the system requires a written regulatory reason logged to the permanent audit trail.*
  >
  > *With `DEMO-LOT-REL-01` now officially APPROVED, I hand back to Member 3 to show how Production consumes this cleared lot."*
* **Handover Action**:
  - Member 2 clicks `/demo-login/production`.
  - Member 3 takes the keyboard.

---

### Step 4: Production Batch Safety Lock, 5-Stage Stepper & Packaging (Member 3 — 1.5 Minutes)

* **Logged In As**: Production Supervisor (`production@foodman.vn`)
* **Screen Displayed**: Production Workspace (`http://localhost:5000/production?view=batches`)
* **Click Path**:
  1. Click **BOM Planning & Readiness** tab (`/production?view=recommendations`):
     - Show the Bill of Materials readiness table: `Corn Milk UHT 250ml` shows **"Ready to Produce"** with green pill.
  2. Click **Production Batches** tab (`/production?view=batches`):
     - Click **"+ New Production Batch"** button to open the modal.
     - Select Product: `Pure Roasted Corn Snack Pack`.
     - Point out the lot allocation dropdown: only lots with status **`APPROVED`** (including our newly cleared `DEMO-LOT-REL-01`) appear. Unapproved lots (`PENDING` or `REJECTED`) are mathematically filtered out.
     - Click **"Create Batch"** -> Generates batch `LOT-2026-012`.
  3. In the batch card grid, click batch `LOT-2026-001` or the newly created batch:
     - Point out the **5-Stage Process Stepper**:
       - Stage 1: Cleaning & Destoning (`COMPLETED`)
       - Stage 2: Roasting / Pasteurization (`COMPLETED`)
       - Stage 3: Milling & Pressing (`IN_PROGRESS`)
       - Stage 4: Fine Filtration
       - Stage 5: Packaging & Boxing
     - Click **"Advance Stage"** to push the batch forward.
  4. Open Packaging modal: show logged carton boxes, seal roll usage, and waste counts.
* **Spoken Script**:
  > *"Back in production, our primary job is manufacturing integrity. On our BOM Planning screen, supervisors can see immediate production readiness based strictly on approved stock.*
  >
  > *When scheduling a new production batch, our backend queries the database for `RawMaterialLot.qc_status == 'APPROVED'`. If an operator attempts to use unapproved or rejected grain, the API aborts with HTTP 400. This provides 100% digital guarantee against cross-contamination.*
  >
  > *Once created, the batch executes through our standardized 5-stage physical stepper: from raw cleaning and roasting at 120°C, through extraction, filtration, and case packing. Every stage logs operating temperatures and operator sign-offs.*
  >
  > *Upon completing the packaging stage, the finished cartons are transferred to outbound storage. I now hand over to Member 4 to demonstrate Warehouse logistics and our 7-tier traceability graph."*
* **Handover Action**:
  - Member 3 clicks `/demo-login/warehouse`.
  - Member 4 takes the keyboard.

---

### Step 5: Warehouse FEFO, Cold-Chain Fleet & 7-Tier Traceability (Member 4 — 2.0 Minutes)

* **Logged In As**: Warehouse Manager (`warehouse@foodman.vn`) / Food Technologist (`tech@foodman.vn`)
* **Screen Displayed**: Warehouse Inventory (`http://localhost:5000/warehouse?view=inventory`)
* **Click Path**:
  1. In **FEFO Inventory** view (`/warehouse?view=inventory`):
     - Point to the expiration urgency pills: **FRESH**, **EXPIRING_SOON** (< 30 days), and shelf-life tracking.
     - Show storage bin coordinates (e.g. `Zone B - Cold Rack 02`).
  2. Switch to **Dispatch Orders** tab (`/warehouse?view=dispatches`):
     - Click active dispatch `DSP-2026-041` for customer **VinMart Supermarket Northern Division**.
     - Point out carrier plate `29C-881.99`, refrigerated container telemetry **`3.8°C`** (compliant with 2.0°C–6.0°C spec), and live delivery status.
  3. Navigate to **Full Traceability Search** (`/traceability`):
     - In the omni-search bar, query batch code **`LOT-2026-089`** (or click the sample tag).
     - The interactive **7-Tier Value Chain Graph** expands instantly:
       - **Tier 1 (Supplier)**: Golden Grain & Oilseed Co. (VietGAP certified farm, Moc Chau).
       - **Tier 2 (Intake Lot)**: RAW-LOT-512 (2,000 kg peanut intake).
       - **Tier 3 (QC & Lab)**: Aflatoxin 0.1 ppb, COA ISO 17025, YOLOv8 visual clearance, approved by MSc. Pham Thu Trang.
       - **Tier 4 (Production)**: Batch LOT-2026-089, 5 process stages logged.
       - **Tier 5 (Packaging)**: 2,000 PET bottles, 168 cartons, Flexo sealing rolls.
       - **Tier 6 (Warehouse)**: Bin Zone A-04, FEFO Fresh status.
       - **Tier 7 (Dispatch)**: Cold-chain truck `29C-881.99`, 3.8°C sensor, delivered to VinMart DC.
  4. Quick glance at **Food Technologist Dashboard** (`/food-technologist`):
     - Show 7-stage quality lifecycle tracker, plain outcome labels (**GOOD**, **NEEDS REVIEW**, **BAD**), and CSV/PDF export.
  5. Conclude presentation.
* **Spoken Script**:
  > *"To complete our factory cycle, finished goods enter our warehouse under automated First-Expired, First-Out (FEFO) rules to prevent spoilage and prioritize older compliant stock.*
  >
  > *When dispatches leave for retail partners like VinMart, our platform monitors refrigerated vehicle telemetry in real time. Here on `DSP-2026-041`, the temperature sensor reads 3.8°C, proving the cold-chain was maintained throughout transit.*
  >
  > *Finally, observe our flagship 7-Tier Farm-to-Fork Traceability Engine. If a consumer or regulatory auditor queries a bottle barcode in a supermarket, our system resolves the entire value chain in under 200 milliseconds: from the delivery truck, back through warehouse binning, carton packaging, production roasting records, laboratory COA testing, AI camera scans, all the way back to the originating supplier farm in Moc Chau.*
  >
  > *We have also built a dedicated Food Technologist workspace, automated desktop launchers with Cloudflare tunneling, and full role-based access control across all 5 industrial roles.*
  >
  > *This concludes our live demonstration of Food Man. We are now ready for your questions."*

---

## 3. Keyboard & Screen Handover Summary Table

| Handover Point | Speaker Departing | Speaker Arriving | Fast URL Shortcut | Visual Confirmation on Screen |
| :---: | :---: | :---: | :---: | :---: |
| **H1 (Min 01:00)** | Member 4 | Member 3 | `http://localhost:5000/demo-login/procurement` | Topbar displays: *"Vu Thu Thao (Procurement)"* |
| **H2 (Min 02:30)** | Member 3 | Member 1 | `http://localhost:5000/demo-login/qc` then `/qc/camera-station` | Inspection Station HUD opens with live camera preview |
| **H3 (Min 04:30)** | Member 1 | Member 2 | `http://localhost:5000/qc?view=queue` | QC queue table loads with demo lots list |
| **H4 (Min 06:30)** | Member 2 | Member 3 | `http://localhost:5000/demo-login/production` | Topbar displays: *"Tran Minh Quan (Production)"* |
| **H5 (Min 07:45)** | Member 3 | Member 4 | `http://localhost:5000/demo-login/warehouse` then `/traceability` | 7-Tier Traceability Omni-Search bar appears |
