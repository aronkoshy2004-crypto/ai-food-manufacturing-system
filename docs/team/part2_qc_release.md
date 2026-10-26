# Part 2: Quality Control & Release Decision Engine

**Team Member**: Member 2 (Quality Assurance Lead)  
**Primary System Role**: QC Specialist / QA Manager (`qc@foodman.vn`)  
**Main Screens**: `/qc?view=queue`, `/qc?view=tests`, `/qc?view=ai-inspection`, `/qc?view=live-inspection`

---

## 1. One-Paragraph Summary

Part 2 acts as the statutory regulatory authority and scientific brain of Food Man. In industrial food processing, visual inspection alone cannot detect microscopic chemical toxins, while paper certificates alone cannot guarantee that grain has not spoiled in transit. Part 2 solves this by implementing a deterministic release decision engine (`ai/release_decision.py`) that cross-validates laboratory Certificate of Analysis (COA) documents against real-time AI vision scans. The system automatically benchmarks physicochemical test parameters (Aflatoxin B1, moisture content, free fatty acids, purity) against strict ISO 17025 and national food standards. It enforces an immutable rule: AI vision can never override a failed chemical lab test. When inspectors deviate from automated recommendations, the system enforces a cryptographically logged written justification audit trail before generating signed, tamper-resistant PDF Inspection Certificates.

---

## 2. What This Member Built

### Files & Modules
- **`ai/release_decision.py`** (519 lines): Pure evaluation engine implementing `release_decision(lot)`, `evaluate_coa_document()`, `evaluate_ai_inspection()`, and commodity specification dictionary (`MATERIAL_SPECS`).
- **`templates/qc.html`** (1,257 lines): QC workspace encompassing QC Queue, Lot Review Drawer, QC Lab Measures entry, COA Library view, and AI upload fallback gateway.
- **`static/js/qc.js`** (1,630 lines): Client-side controller for lot review drawers, COA uploads, test result tables, release outcome badge styling, override justification prompt, and PDF export triggers.
- **`models/qc.py`** (446 lines): SQLAlchemy relational schema for samples, laboratory parameters, certificates, decisions, defects, and inspection images.
- **`routes/qc.py`** (Quality assurance routes lines 1–1500 & 4370–5140): Endpoints for QC queue, lot combined reviews, COA file uploads, lab sample creation, human sign-off with mandatory override validation, and ReportLab PDF document compilation.
- **`scripts/seed_demo_release_lots.py`** (289 lines): Deterministic seed generator creating the 4 canonical test lots (`DEMO-LOT-REL-01` through `04`).
- **`tests/test_release_decision.py`** (336 lines): Unit and integration test suite covering the full decision matrix, expiration boundaries, and demo lots.

### Route Endpoints (17 Routes)
- `GET /qc`: Main QC dashboard landing view.
- `GET /api/qc/queue`: Retrieves pending intake lots awaiting quality decision.
- `GET /api/qc/lot/<id>/review`: Aggregates complete lot dossier (metadata, COA, lab tests, AI scans, release recommendation).
- `GET /api/qc/lot/<id>/release-decision`: Runs real-time `release_decision()` on specified lot.
- `POST /api/qc/lot/<id>/sample`: Registers physical laboratory sample and associated test parameters.
- `POST /api/qc/lot/<id>/coa`: Uploads and parses supplier Certificate of Analysis PDF/metadata.
- `POST /api/qc/lot/<id>/image`: Associates visual intake reference photographs with lot.
- `POST /api/qc/lot/<id>/decision`: Submits general lot status decision (`APPROVED`, `HOLD`, `REJECTED`).
- `POST /api/qc/decision`: Submits quick decision from queue table.
- `GET /api/qc/ai-inspections`: Historical log of all AI defect inspections.
- `POST /api/qc/ai-feedback`: Records human inspector feedback on AI bounding box accuracy.
- `POST /api/qc/ai-inspection/<id>/confirm-verdict`: Confirms static AI inspection and updates lot state.
- `GET /api/qc/ai-inspection/<id>/pdf`: Compiles official ReportLab PDF Certificate of Analysis / AI Dossier.
- `POST /api/qc/live-session/<id>/confirm-verdict`: Confirms live camera station verdict with mandatory override justification enforcement.
- `GET /api/qc/production-ready-lots`: Lists lots cleared for consumption in production batches.
- `GET /api/qc/lot/<id>/qc-measures`: Fetches stored physicochemical measures (moisture, aflatoxin, FFA, purity).
- `POST /api/qc/lot/<id>/qc-measures`: Saves updated laboratory measures.

### Database Tables (9 Tables)
- **`qc_samples`**: Laboratory sample records (`SMP-DEMO-01`), sample dates, and collection locations.
- **`qc_tests`**: Individual physicochemical test rows (Parameter, measured value, standard specification, pass/fail boolean).
- **`coa_documents`**: Certificate of Analysis files, document numbers, lab accreditation (ISO 17025), issue/expiry dates.
- **`qc_decisions`**: Statutory human sign-off records, final status, inspector user ID, timestamps, and mandatory written override justifications.
- **`ai_inspections`**: AI vision analysis records, defect counts, model versions, confidence scores, and summaries.
- **`detected_defects`**: Normalized bounding box coordinates (`bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`), defect classes (`Corn_Moldy`, `Peanut_Moldy`), and confidence scores.
- **`inspection_images`**: Visual intake image file paths and descriptions.
- **`ai_feedbacks`**: Human inspector feedback logs for model evaluation.
- **`qc_inspections`**: Base schema draft table for historical laboratory inspection records.

### Key Functions
- `ai.release_decision.release_decision(lot, db, coa, ai_result, tests)`: Deterministic decision matrix combining COA and AI states into `RELEASE`, `HOLD`, or `REJECT`.
- `ai.release_decision.evaluate_coa_document(lot, coa, tests, db)`: Validates certificate lot ownership, supplier identity, expiration dates (< 365 days), and parameter boundaries.
- `ai.release_decision.evaluate_ai_inspection(lot, ai_result, db)`: Translates vision results into AI states (`PASS`, `REVIEW`, `REJECT`, `RETAKE`, `NOT_RUN`).
- `routes.qc.confirm_live_session_verdict(session_id)`: Enforces written override audit rule when accepting non-PASS or rejecting non-REJECT.
- `routes.qc.generate_inspection_pdf(inspection_id)`: Compiles professional ReportLab PDF dossier with tables, banners, and digital signature blocks.

### Automated Test Coverage (19 Tests)
- **`tests/test_release_decision.py`** (19 tests):
  - Matrix validation: COA Pass + AI Pass -> `RELEASE`
  - Matrix validation: COA Pass + AI Reject -> `HOLD` (*"paper passes, camera disagrees: investigate"*)
  - Matrix validation: COA Pass + AI Review -> `HOLD` (*"inspector checks by eye"*)
  - Matrix validation: COA Fail + Any AI -> `REJECT`
  - Matrix validation: COA Missing + Any AI -> `HOLD` (*"valid COA needed"*)
  - Regulatory invariants: Peanut Aflatoxin rule (COA decides, AI never overrides failed COA).
  - Regulatory invariants: Sunflower rule (never gets automatic AI Pass, outcome rests on COA plus inspector).
  - Validation of all 4 Demo Lots (`DEMO-LOT-REL-01` to `04`).

---

## 3. How It Works: The Release Decision Matrix

The release decision engine operates as a deterministic finite-state machine combining paper laboratory certification and edge computer vision:

```
                      ┌──────────────────────────────────────────────┐
                      │            COA Laboratory State              │
                      │       (PASS / FAIL / MISSING)                │
                      └──────────────────────┬───────────────────────┘
                                             │
                      ┌──────────────────────▼───────────────────────┐
                      │              AI Vision State                 │
                      │   (PASS / REVIEW / REJECT / RETAKE / NOT_RUN)│
                      └──────────────────────┬───────────────────────┘
                                             │
                                     [Decision Engine]
                                             │
      ┌──────────────────────────────────────┼──────────────────────────────────────┐
      ▼                                      ▼                                      ▼
┌───────────┐                          ┌───────────┐                          ┌───────────┐
│  RELEASE  │                          │   HOLD    │                          │  REJECT   │
│(COA Pass &│                          │(Conflict, │                          │(COA Fail, │
│  AI Pass) │                          │ Missing,  │                          │ Out of    │
└───────────┘                          │ Review)   │                          │ Spec)     │
                                       └───────────┘                          └───────────┘
```

### The Matrix Rules
1. **COA FAIL $\rightarrow$ REJECT**: If any laboratory safety parameter fails (e.g. Aflatoxin B1 $> 2.0\text{ ppb}$ for peanuts), the lot is immediately **REJECTED**. AI vision can never override a failed laboratory test.
2. **COA MISSING $\rightarrow$ HOLD**: If no verified COA document is on file, the outcome is placed on **HOLD** (*"Valid COA needed"*).
3. **Material Mismatch $\rightarrow$ HOLD**: If the order metadata says "Corn" but the camera classifier detects "Peanut", the outcome is held for fraud/contamination investigation.
4. **Sunflower Exemption $\rightarrow$ HOLD**: Because zero fungal sunflower training data exists, sunflower seeds never receive an automatic AI Pass and are held for human visual sign-off.
5. **COA PASS + AI PASS $\rightarrow$ RELEASE**: Both chemical purity and visual appearance are compliant. The release button is enabled.
6. **COA PASS + AI REJECT $\rightarrow$ HOLD**: Paper passes but camera detects mold or defects. Held for quarantine inspection (*"Paper passes, camera disagrees: investigate"*).
7. **COA PASS + AI REVIEW / RETAKE / NOT_RUN $\rightarrow$ HOLD**: Visual scan was inconclusive, blurry, or pending. Held for human physical check (*"Inspector checks by eye"*).

### Stored Commodity Specifications (`MATERIAL_SPECS`)
- **Peanut**: Moisture $\le 8.0\%$, Aflatoxin B1 $\le 2.0\text{ ppb}$, Purity $\ge 98.0\%$, Oil Content $\ge 48.0\%$.
- **Corn**: Moisture $\le 14.0\%$, Aflatoxin B1 $\le 5.0\text{ ppb}$, Purity $\ge 98.0\%$.
- **Sunflower**: Moisture $\le 9.0\%$, Free Fatty Acids (FFA) $\le 1.5\%$, Purity $\ge 98.0\%$.

---

## 4. Live Demo Click Path (The 4 Demo Lots)

1. **Role Login**: Sign in as QC Specialist (`qc@foodman.vn` via `/demo-login/qc`).
2. **Open QC Queue**: Navigate to `/qc?view=queue`.
3. **Demo Lot 1: DEMO-LOT-REL-01 (Corn — RELEASE)**:
   - Click the row for `DEMO-LOT-REL-01` to open the **Lot Review Drawer**.
   - Show the green **RELEASE** card:
     - Paper Check (COA): `PASS` (Moisture 12.2% < 14%, Aflatoxin 1.2 ppb < 5 ppb).
     - Camera Check (AI): `PASS` (0 defects, 94% confidence).
     - Reason: *"All laboratory COA parameters and camera AI inspection verified compliant. Safe to release."*
   - Click **"✓ Confirm Accept (Approved)"**.
   - Status updates in database to `APPROVED`.
   - Click **"📄 Download PDF Report"** -> Opens official Certificate of Analysis in a new tab. Show accreditation header, parameter table, defect crop, and digital signature block.
4. **Demo Lot 3: DEMO-LOT-REL-03 (Peanut — REJECT)**:
   - Click row `DEMO-LOT-REL-03`:
   - Point out the red **REJECT** card:
     - Camera Check (AI): `PASS` (0 visual defects detected).
     - Paper Check (COA): **`FAIL`** (Aflatoxin B1 is **4.5 ppb**, exceeding the 2.0 ppb limit).
     - Reason: *"Peanut lot rejected: COA aflatoxin safety limit failed. AI inspection cannot override."*
     - Advisory Notice: *"Camera screening only. Peanut lots need lab testing before release."*
   - Click **"Override & Force Accept"**:
     - The modal opens displaying: *"Approving a lot when the analysis state is REJECT requires a written reason."*
     - Show that leaving the text field blank and clicking submit produces an error. Type a test justification to show full audit logging.
5. **Demo Lot 2 & 4 (Quick Showcase)**:
   - `DEMO-LOT-REL-02` (Corn): COA Pass + AI Reject (4 moldy kernels detected) -> **HOLD** (*"Paper passes, camera disagrees: investigate"*).
   - `DEMO-LOT-REL-04` (Peanut): Clean visual scan but COA Missing -> **HOLD** (*"Valid COA needed"*).

---

## 5. Spoken Script (2 Minutes)

> *"Thank you Member 1. I am Member 2, and I built the Quality Control and Statutory Release Decision Engine.*
>
> *In regulatory food manufacturing under HACCP and ISO 22000, software must never treat AI as an unaccountable black box. A machine learning model cannot detect chemical poisons, while a paper certificate cannot guarantee that a supplier did not ship moldy grain. Our system bridges this gap through a deterministic release decision engine.*
>
> *Here in our QC Inspection Queue, look at `DEMO-LOT-REL-01`, a 25-ton shipment of corn. Our engine evaluated the supplier's ISO 17025 Certificate of Analysis: moisture is 12.2% and Aflatoxin B1 is 1.2 ppb, both well within international specifications. Concurrently, our YOLO camera scan confirmed zero mold. Because both paper and vision agree, the engine issues a green `RELEASE` outcome.*
>
> *When I click 'Confirm Accept', the system transitions the lot to APPROVED in the database and compiles this official, tamper-evident PDF Certificate of Analysis with embedded timestamps and test tables.*
>
> *Now, examine `DEMO-LOT-REL-03`. This is a critical demonstration of food safety boundaries. The peanuts in this lot look clean, and our vision model detected zero visual defects. In an unscientific system, this might have been approved. However, our COA parser detected Aflatoxin B1 at 4.5 ppb—more than double the strict statutory safety ceiling of 2.0 ppb.*
>
> *Our engine forces a hard `REJECT`. We enforce an immutable safety principle: AI vision can never override a failed chemical laboratory test. Furthermore, if an inspector attempts to override any non-pass recommendation, the system enforces a mandatory written justification logged permanently to our audit trail.*
>
> *With `DEMO-LOT-REL-01` now officially APPROVED, it is cleared for food production. I hand back to Member 3 to show how Production consumes this lot."*

---

## 6. Honest Limitations & Future Work

### Verified Code Limitations
1. **Rule-Based COA Parsing**:
   - COA parameters are evaluated by parsing structured database test records (`QCTest`) and structured JSON notes. The system does not perform optical character recognition (OCR) on raw scanned paper documents; lab values must be entered via API, test modal, or digital intake.
2. **COA Validity Lifetime (365 Days)**:
   - In `evaluate_coa_document()`, certificates older than 365 days are marked as expired. In certain commodities, shelf stability may require shorter expiration intervals (e.g. 90 days for refined oils).
3. **Chemical Blindness**:
   - The release decision engine is entirely dependent on authentic lab data. If a corrupt supplier falsifies laboratory test values in the database, the engine cannot independently detect chemical toxins without physical HPLC/ELISA laboratory instruments.

### One Sentence on Future Work
> *"Future work will incorporate automated OCR document ingestion with digital signature verification to automatically parse unstructured supplier PDF certificates and cross-reference lab accreditation numbers against government laboratory registries."*

---

## 7. 10 Likely Questions & Correct Answers

1. **Q: Why does `DEMO-LOT-REL-03` get rejected even though the AI vision scan passed?**  
   *A: Because chemical Aflatoxin B1 tested at 4.5 ppb, exceeding the statutory 2.0 ppb limit. Aflatoxins are microscopic chemical toxins invisible to camera sensors. In `ai/release_decision.py`, Rule A enforces that COA failure always yields an automatic REJECT, and AI can never override a failed lab test.*
2. **Q: What happens if a shipment arrives without a Certificate of Analysis?**  
   *A: The lot is placed on HOLD under Rule B (*"Valid COA needed"*). The system refuses to enable the release button until a verified COA document is uploaded.*
3. **Q: What is the purpose of the mandatory written override reason?**  
   *A: Under `routes/qc.py:confirm_live_session_verdict()`, approving a lot in `REVIEW` or `REJECT` state without a written reason is blocked with HTTP 400. This ensures full regulatory traceability and auditor accountability under ISO 22000.*
4. **Q: How does the system prevent a COA from being reused across different lots?**  
   *A: In `evaluate_coa_document()`, the engine cross-references `COADocument.raw_material_lot_id`, `supplier_id`, and material type against the lot. If they do not match, the COA is marked FAIL for lot mismatch.*
5. **Q: What parameters are checked for Corn vs Peanuts?**  
   *A: Corn limits: Moisture $\le 14.0\%$, Aflatoxin $\le 5.0\text{ ppb}$, Purity $\ge 98.0\%$. Peanut limits: Moisture $\le 8.0\%$, Aflatoxin $\le 2.0\text{ ppb}$, Purity $\ge 98.0\%$, Oil $\ge 48.0\%$.*
6. **Q: What library is used to generate the official inspection PDF?**  
   *A: Python's ReportLab library (`reportlab.platypus`), which compiles custom styles, header tables, defect summaries, and digital signature lines directly into a downloadable PDF stream.*
7. **Q: Why does `DEMO-LOT-REL-02` result in HOLD instead of REJECT?**  
   *A: In `DEMO-LOT-REL-02`, the COA passed but the camera detected 4 defects. Under Rule F, this conflict triggers HOLD (*"Paper passes, camera disagrees: investigate"*), requiring a quality manager to quarantine and re-sample the lot.*
8. **Q: What does the advisory note on peanuts mean?**  
   *A: Due to the known statistical plateau in peanut mold detection and the danger of Aflatoxin poisoning, peanut inspection results always mandate: "Camera screening only. Peanut lots need lab testing before release."*
9. **Q: Where are QC decision override justifications stored?**  
   *A: In the `qc_decisions` table in the `notes` column, alongside `decided_by` user ID and `decided_at` UTC timestamp.*
10. **Q: Can a regular production or warehouse worker approve a QC lot?**  
    *A: No. The endpoint `/api/qc/lot/<id>/decision` is guarded by `@role_required(RoleEnum.QC, RoleEnum.ADMIN)`. Unauthorized users receive an HTTP 403 Forbidden response.*

---

## 8. Key Terms to Know

- **COA (Certificate of Analysis)**: An official document issued by an accredited laboratory certifying that a product or raw material meets specific chemical, physical, and microbiological specifications.
- **HACCP (Hazard Analysis Critical Control Point)**: A systematic preventive approach to food safety addressing biological, chemical, and physical hazards.
- **ISO 17025**: International standard specifying general requirements for the competence, impartiality, and consistent operation of testing and calibration laboratories.
- **Aflatoxin B1**: A potent, naturally occurring carcinogenic mycotoxin produced by *Aspergillus flavus* fungi, subject to strict global limits (e.g. 2.0 ppb in the EU and Vietnam for direct human consumption).
- **Release Decision Matrix**: A deterministic evaluation table mapping COA states (Pass, Fail, Missing) and AI states (Pass, Review, Reject, Retake) to an operational outcome.

---

## 9. What NOT to Claim or Click During Demo

- **DO NOT claim the system performs automated OCR on scanned paper documents**: COA parameters are read from structured database records and JSON notes.
- **DO NOT claim AI vision can detect Aflatoxin**: Emphasize that chemical lab tests are mandatory and superior for toxin detection.
- **DO NOT approve `DEMO-LOT-REL-03` during the live demo without showing the required override reason modal**: The rejection of `DEMO-LOT-REL-03` is your strongest food safety showcase.
- **DO NOT claim the PDF is a government-issued stamp**: It is an internal factory Certificate of Analysis and AI Inspection Dossier generated by Food Man.
