# Food Man — 15 Common Cross-System Questions & Answer Assignments

These 15 questions cover system-wide architecture, regulatory compliance, data integrity, and failure recovery. When an examiner directs a broad question to the team, use this guide to determine **who answers** and **what the exact, code-verified answer is**.

---

## Question Assignment Quick Reference

| # | Question Theme | Primary Respondent | Secondary Support |
| :---: | :--- | :--- | :--- |
| **1** | How does the system prevent contaminated food from reaching consumers? | **Member 2** (QC & Release Lead) | Member 3 (Production) |
| **2** | What happens if the physical camera or phone hardware fails during dock receiving? | **Member 1** (AI Vision Lead) | Member 2 (QC) |
| **3** | Why not let the AI model make the final decision to accept or reject automatically? | **Member 2** (QC & Release Lead) | Member 1 (AI Vision) |
| **4** | Can production operators bypass QC and use unapproved raw materials if there is a shortage? | **Member 3** (Manufacturing Lead) | Member 2 (QC) |
| **5** | If a customer reports a contaminated peanut jar, how quickly can you trace the source? | **Member 4** (Platform & Logistics Lead) | Member 3 (Manufacturing) |
| **6** | What is the difference between your YOLOv8 detector and the OpenCV colour screening? | **Member 1** (AI Vision Lead) | Member 2 (QC) |
| **7** | How does the system handle Sunflower seeds if there is no fungal mold training data? | **Member 1** (AI Vision Lead) | Member 2 (QC) |
| **8** | How do you ensure raw material lots are consumed in the correct order to avoid expiration? | **Member 4** (Platform & Logistics Lead) | Member 3 (Manufacturing) |
| **9** | What database does Food Man use, and how do you protect against data corruption? | **Member 4** (Platform & Logistics Lead) | Member 3 (Manufacturing) |
| **10** | What happens if a supplier delivers 20 tons of grain but the purchase order was for 15 tons? | **Member 3** (Manufacturing Lead) | Member 4 (Platform) |
| **11** | Why does peanut inspection have a specific mold recall limitation in your AI documentation? | **Member 1** (AI Vision Lead) | Member 2 (QC) |
| **12** | If the QC inspector disagrees with the AI recommendation, how is that conflict handled? | **Member 2** (QC & Release Lead) | Member 1 (AI Vision) |
| **13** | How do you secure different user roles so warehouse workers cannot edit recipes or approve lots? | **Member 4** (Platform & Logistics Lead) | Member 3 (Manufacturing) |
| **14** | How does the cold-chain temperature monitoring protect perishable finished goods? | **Member 4** (Platform & Logistics Lead) | Member 3 (Manufacturing) |
| **15** | How is the system deployed and accessed in a factory without public static IP addresses? | **Member 4** (Platform & Logistics Lead) | Member 1 (AI Vision) |

---

## Detailed Questions & Verified Answers

### Q1: How does the system prevent contaminated food from reaching consumers?
* **Answered By**: **Member 2** (QC & Release Lead)
* **Code-Verified Answer**:
  > *"Food Man enforces a multi-tier defense: First, at intake, raw materials cannot be accepted without passing both visual inspection and chemical COA verification (e.g. Aflatoxin B1 limits under 2.0 ppb for peanuts). Second, in `routes/production.py:create_batch()`, the backend queries `RawMaterialLot.qc_status == 'APPROVED'`. Any unapproved, held, or rejected lot is strictly rejected by the API with an HTTP 400 error. Third, production batches must complete all 5 process stages and pass final packaging integrity checks before syncing into warehouse FEFO inventory. Finally, our 7-tier traceability engine allows instant batch recall if post-dispatch defects are reported."*

### Q2: What happens if the physical camera or phone hardware fails during dock receiving?
* **Answered By**: **Member 1** (AI Vision Lead)
* **Code-Verified Answer**:
  > *"We have an immediate 5-second software fallback built directly into the system. Under `/qc?view=ai-inspection`, operators can upload static intake photos taken by standard digital cameras, mobile phones, or handheld dock tablets. The exact same YOLOv8 model runs backend inference on the uploaded image in under 800 milliseconds, producing bounding boxes and defect tallies without requiring the real-time WebRTC camera station."*

### Q3: Why not let the AI model make the final decision to accept or reject automatically?
* **Answered By**: **Member 2** (QC & Release Lead)
* **Code-Verified Answer**:
  > *"In statutory food safety (HACCP and ISO 22000), visual appearance cannot detect lethal chemical toxins such as Aflatoxin B1, Ochratoxin A, heavy metals, or free fatty acid rancidity. A kernel can look visually perfect while carrying toxic fungal metabolites, as demonstrated in our demo lot `DEMO-LOT-REL-03`. Furthermore, AI models have statistical confidence intervals and edge-case blind spots. Therefore, the AI is strictly advisory: statutory legal authority remains with the certified human QC specialist."*

### Q4: Can production operators bypass QC and use unapproved raw materials if there is a shortage?
* **Answered By**: **Member 3** (Manufacturing Lead)
* **Code-Verified Answer**:
  > *"No. The block is enforced at the database query level in `routes/production.py:create_batch()`. When a batch is requested, the server calculates required ingredients from the recipe BOM and filters `RawMaterialLot` specifically by `qc_status == 'APPROVED'` and `quantity > 0`. If approved stock is less than the required amount, the request is aborted with `{"success": false, "error": "Insufficient QC-approved raw materials"}`. Frontend UI buttons are also disabled, preventing operators from forcing batch creation."*

### Q5: If a customer reports a contaminated peanut jar, how quickly can you trace the source?
* **Answered By**: **Member 4** (Platform & Logistics Lead)
* **Code-Verified Answer**:
  > *"In under 200 milliseconds. Entering the batch code or barcode into `/traceability` executes our unbroken 7-tier recursive graph search in `routes/traceability.py`. It links the customer dispatch order directly back to the warehouse bin, packaging line records, production batch temperature logs, QC chemical test values, raw material intake lots, and the original supplier farm details including VietGAP certification and delivery truck plate."*

### Q6: What is the difference between your YOLOv8 detector and the OpenCV colour screening?
* **Answered By**: **Member 1** (AI Vision Lead)
* **Code-Verified Answer**:
  > *"YOLOv8 is a deep convolutional object detector trained to localize individual kernels and recognize complex morphological textures such as visible fungal mycelium, insect boring holes, and broken kernels. OpenCV CIE Lab screening is a classical mathematical engine that models local paper illumination to compute Delta E Euclidean colour distance from median grain color. CIE Lab is ideal for detecting subtle pigment discoloration, surface scorch, and non-mold defects without requiring GPU training."*

### Q7: How does the system handle Sunflower seeds if there is no fungal mold training data?
* **Answered By**: **Member 1** (AI Vision Lead)
* **Code-Verified Answer**:
  > *"We maintain strict engineering honesty: because zero genuine fungal sunflower images exist in the open dataset, our system never claims to detect sunflower mold. In `ai/release_decision.py:evaluate_ai_inspection()`, sunflower lots are programmatically prevented from ever receiving an automatic `PASS`. The system runs CIE Lab colour distance screening only, labels deviations as 'Discoloured', and routes the lot to `REVIEW` (Needs Review) requiring physical human verification."*

### Q8: How do you ensure raw material lots and finished goods are consumed in the correct order to avoid expiration?
* **Answered By**: **Member 4** (Platform & Logistics Lead)
* **Code-Verified Answer**:
  > *"We enforce First-Expired, First-Out (FEFO) logic. In `models/warehouse.py`, `WarehouseInventory` calculates `days_to_expiry` and assigns an urgency category (`FRESH`, `EXPIRING_SOON` under 30 days, or `EXPIRED`). In production allocation (`routes/production.py`), the system allocates approved lots ordered by earliest received date and expiry. Outbound dispatch pick-lists automatically suggest lots with the closest expiry date to minimize factory waste."*

### Q9: What database does Food Man use, and how do you protect against data corruption?
* **Answered By**: **Member 4** (Platform & Logistics Lead)
* **Code-Verified Answer**:
  > *"Food Man uses an embedded SQLite database (`food_man.db`) managed through SQLAlchemy ORM with foreign key cascades and transactional ACID guarantees. Database modifications are wrapped in atomic commit blocks with rollback handlers. For production deployments, SQLAlchemy's abstraction allows switching to PostgreSQL by updating `DATABASE_URI` in `config.py` without rewriting application code."*

### Q10: What happens if a supplier delivers 20 tons of grain but the purchase order was for 15 tons?
* **Answered By**: **Member 3** (Manufacturing Lead)
* **Code-Verified Answer**:
  > *"During intake under `/procurement?view=grn`, warehouse intake staff record the actual physical weight delivered on the Goods Receipt Note. The GRN item logs the true delivered quantity (20 Tons) while maintaining a foreign key reference to the original PO line item (15 Tons). The resulting `RawMaterialLot` is created with the actual 20 Tons in `PENDING_QC`. The PO status updates to reflect over-delivery or partial fulfillment, alerting procurement to reconcile the supplier invoice."*

### Q11: Why does peanut inspection have a specific mold recall limitation in your AI documentation?
* **Answered By**: **Member 1** (AI Vision Lead)
* **Code-Verified Answer**:
  > *"As documented in `docs/AI_MODEL_LIMITATIONS.md`, peanut mold recall plateaus at ~42%–57% because the training dataset contained only 10,227 moldy peanut instances compared to over 45,000 for corn, and clean peanuts were photographed only as isolated single kernels on white paper. Furthermore, dense peanut clusters create inter-kernel shadow crevices. We mitigated this by raising the defect confidence floor to 0.35 in dense clusters and enforcing a mandatory on-screen advisory: 'Camera screening only. Peanut lots need lab testing before release.'"*

### Q12: If the QC inspector disagrees with the AI recommendation, how is that conflict handled?
* **Answered By**: **Member 2** (QC & Release Lead)
* **Code-Verified Answer**:
  > *"The human inspector retains statutory authority to override the system, but the action is strictly audited. Under `routes/qc.py:confirm_live_session_verdict()`, approving a lot whose analysis state is `REVIEW` or `REJECT` requires a non-empty written reason. The inspector's name, user ID, UTC timestamp, and justification are permanently stored in the `QCDecision` audit log and printed on the official PDF certificate."*

### Q13: How do you secure different user roles so warehouse workers cannot edit recipes or approve lots?
* **Answered By**: **Member 4** (Platform & Logistics Lead)
* **Code-Verified Answer**:
  > *"We enforce Role-Based Access Control (RBAC) at two levels: route decorators and sidebar UI filtering. In `routes/auth.py`, routes are protected by `@login_required` and `@role_required(RoleEnum.QC, RoleEnum.ADMIN)`. If a warehouse operator directly accesses `/qc` or `/production`, the server blocks the request and redirects them to their authorized dashboard. In `templates/base.html`, navigation items only render if the module exists in `permitted_modules`."*

### Q14: How does the cold-chain temperature monitoring protect perishable finished goods?
* **Answered By**: **Member 4** (Platform & Logistics Lead)
* **Code-Verified Answer**:
  > *"In `routes/warehouse.py`, dispatch records store carrier details, destination, and live `temp_sensor_celsius` telemetry against `temp_spec_range` (e.g. 2.0°C to 6.0°C for dairy and nut milks). If a vehicle's cooling unit fails and temperature exceeds specifications, the dispatch order status is flagged with a temperature breach alert, warning receiving supermarket distribution centers before goods are unloaded."*

### Q15: How is the system deployed and accessed in a factory without public static IP addresses?
* **Answered By**: **Member 4** (Platform & Logistics Lead)
* **Code-Verified Answer**:
  > *"We built an automated hybrid launcher in `scripts/launcher.py` and `scripts/tunnel_service.py`. When `FoodMan.bat` is executed, the system launches the local WSGI HTTP server on port 5000 and concurrently spins up an encrypted Cloudflare Zero-Trust tunnel (`cloudflared.exe`). The tunnel publishes a secure public HTTPS URL (e.g. `https://foodman-live.trycloudflare.com`) written to `.public_url`. Dock workers can scan the dynamic QR code on their smartphones and access camera capture without firewall configuration."*
