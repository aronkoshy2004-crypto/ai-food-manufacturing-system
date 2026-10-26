# Part 3: Procurement & Production Execution

**Team Member**: Member 3 (Manufacturing Lead)  
**Primary System Roles**: Procurement Officer (`procurement@foodman.vn`) & Production Supervisor (`production@foodman.vn`)  
**Main Screens**: `/procurement` (5 view tabs) & `/production` (3 view tabs)

---

## 1. One-Paragraph Summary

Part 3 represents the industrial physical engine of Food Man, executing both upstream raw material procurement and downstream factory batch manufacturing. It governs the end-to-end transformation of agricultural commodities: onboarding vetted suppliers, issuing multi-line Purchase Orders (PO), receiving physical deliveries via Goods Receipt Notes (GRN), and generating uninspected intake lots (`PENDING_QC`). In production, it converts approved raw materials into finished consumer goods using dynamic Bill of Materials (BOM) recipes. Most crucially, this module enforces Food Man's non-negotiable food safety invariant: **only raw material lots with status `APPROVED` can ever be consumed in production batches**. If an unapproved, quarantined, or rejected lot is selected, the server strictly aborts batch creation, providing an ironclad digital guarantee against food contamination before advancing products through a 5-stage manufacturing stepper.

---

## 2. What This Member Built

### Files & Modules
- **`templates/procurement.html`** (352 lines): Workspace for Procurement with 5 interactive views: Suppliers, Raw Materials Catalog, Intake Lots, Purchase Orders, and Goods Receipts (GRN).
- **`templates/production.html`** (284 lines): Manufacturing execution workspace featuring Recipes/BOM, Active Production Batches (card grid & 5-stage stepper), and BOM Readiness Planning.
- **`static/js/procurement.js`** (1,489 lines): Client controller handling PO creation modals, line item calculations, slide-over `DetailDrawer` dossiers, GRN intake generation, soft-deactivation/reactivation, and void actions.
- **`static/js/production.js`** (764 lines): Client controller for BOM readiness calculations, batch creation modals with approved lot filtering, 5-stage stepper advancement, and packaging logs.
- **`routes/procurement.py`** (704 lines): 19 REST endpoints managing suppliers, raw materials, purchase orders, goods receipts, and raw material intake lots.
- **`routes/production.py`** (579 lines): 11 REST endpoints managing BOM readiness checks, batch creation with strict approved-stock gates, stage progression, and packaging verification.
- **`models/procurement.py`** (278 lines): SQLAlchemy schema for `Supplier`, `RawMaterial`, `PurchaseOrder`, `PurchaseOrderItem`, `GoodsReceipt`, `GoodsReceiptItem`, and `RawMaterialLot`.
- **`models/production.py`** (319 lines): SQLAlchemy schema for `Product`, `Recipe`, `RecipeMaterial` (BOM), `ProductionBatch`, `BatchRawMaterial`, `ProductionProcessRecord`, `PackagingMaterial`, and `PackagingRecord`.

### Route Endpoints (30 Routes)
#### Procurement Routes (19 Endpoints)
- `GET /procurement`: Main procurement workspace landing view.
- `GET /api/procurement/suppliers`: Lists all active/inactive agricultural suppliers.
- `POST /api/procurement/suppliers`: Onboards a new certified supplier.
- `PUT /api/procurement/suppliers/<id>`: Updates supplier contact or certification details.
- `POST /api/procurement/suppliers/<id>/deactivate`: Soft-deactivates supplier.
- `POST /api/procurement/suppliers/<id>/reactivate`: Restores deactivated supplier.
- `GET /api/procurement/raw-materials`: Catalog of raw materials and standard units.
- `POST /api/procurement/raw-materials`: Registers new raw material SKU.
- `PUT /api/procurement/raw-materials/<id>`: Updates raw material storage conditions.
- `POST /api/procurement/raw-materials/<id>/deactivate`: Soft-deactivates raw material.
- `POST /api/procurement/raw-materials/<id>/reactivate`: Restores raw material.
- `GET /api/procurement/purchase-orders`: Lists purchase orders with fulfillment status.
- `POST /api/procurement/purchase-orders`: Issues multi-line purchase order.
- `POST /api/procurement/purchase-orders/<id>/void`: Voids a draft or pending PO.
- `GET /api/procurement/grn`: Lists Goods Receipt Notes (GRN).
- `POST /api/procurement/grn`: Records physical dock delivery, generates GRN and linked `RawMaterialLot`.
- `GET /api/procurement/lots`: Lists all raw material intake lots with QC status.
- `PUT /api/procurement/lots/<id>`: Updates lot storage conditions or location notes.
- `GET /api/procurement/stats`: Executive summary of supplier counts, open POs, and intake volume.

#### Production Routes (11 Endpoints)
- `GET /production`: Main production workspace landing view.
- `GET /api/production/recommendations`: Calculates BOM planning readiness and batch feasibility.
- `GET /api/production/batches`: Lists active production batches with progress and status pills.
- `GET /api/production/batches/<id>`: Detailed batch dossier with BOM allocations and process records.
- `POST /api/production/batches`: **Core Safety Gate** — Creates batch and consumes APPROVED lots only.
- `POST /api/production/batches/<id>/advance-stage`: Advances batch through 5 physical production stages.
- `POST /api/production/batches/<id>/packaging`: Logs carton boxes, seal roll rolls, and packaging waste.
- `GET /api/production/completed-batches`: Historical archive of finished goods batches.
- `GET /api/production/recipes`: Lists approved recipes and standard yields.
- `POST /api/production/recipes`: Creates new product recipe and standard yield specifications.
- `POST /api/production/recipes/<id>/ingredients`: Adds ingredient lines to a recipe Bill of Materials.

### Database Tables (15 Tables)
- **`suppliers`**: Agricultural vendors, tax codes, ratings (1–5), addresses, certifications.
- **`raw_materials`**: Catalog of commodities (Corn, Peanuts, Sunflower), units, storage specs.
- **`purchase_orders`**: Formal procurement orders, supplier foreign keys, order dates, total amounts.
- **`purchase_order_items`**: Line items per PO, required quantities, unit prices, currency.
- **`goods_receipts`**: Dock intake records, delivery note references, truck license plates (`29C-438.12`).
- **`goods_receipt_items`**: Physical quantities received per commodity.
- **`raw_material_lots`**: Physical intake lots, status (`PENDING`, `APPROVED`, `HOLD`, `REJECTED`), QC status (`PENDING_QC`), quantities.
- **`recipes`**: Production formulas, standard batch yields, target lines.
- **`recipe_materials`**: Bill of Materials (BOM) mapping: required quantity of raw material per standard batch.
- **`products`**: Finished consumer goods (e.g. `Pure Roasted Corn Snack Pack`, `Corn Milk UHT 250ml`).
- **`production_batches`**: Manufacturing batches (`LOT-2026-xxx`), line names, target/actual yields, status (`IN_PROGRESS`, `COMPLETED`).
- **`batch_raw_materials`**: Traceability junction linking allocated `RawMaterialLot` IDs to `ProductionBatch`.
- **`production_process_records`**: 5-stage audit log (Stage name, start/end timestamps, temperatures, shift managers).
- **`packaging_records`**: Carton counts, packaging roll consumption, inspected by, waste counts.
- **`packaging_materials`**: Packaging SKU catalog (Flexo cartons, PET bottles, foil rolls).

### Key Functions
- `routes.procurement.create_goods_receipt()`: Receives physical delivery, validates against PO, auto-generates `RawMaterialLot` with status `PENDING` and `qc_status = 'PENDING_QC'`.
- `routes.production.get_recommendations()`: Evaluates active inventory against recipe BOMs to determine `PRODUCEABLE` vs `LACKING_MATERIALS`.
- `routes.production.create_batch()`: Queries `RawMaterialLot.qc_status == 'APPROVED'`, blocks unapproved lots with HTTP 400, decrements available lot quantity, and binds lot IDs to `batch_raw_materials`.
- `routes.production.advance_stage()`: Advances the 5-stage manufacturing sequence and updates phase timestamps.
- `routes.production.record_packaging()`: Logs final carton and packaging material usage.

---

## 3. How It Works (Step-by-Step Flow)

```
[Supplier Onboarding] ──► [Purchase Order (PO)] ──► [Dock Delivery & GRN]
                                                               │
                                                               ▼
                                                    [RawMaterialLot Created]
                                                    (Status: PENDING_QC)
                                                               │
                                                               ▼ (Hand-off to Part 1 & Part 2)
                                                    [QC Approval Gate]
                                                    (Status: APPROVED)
                                                               │
                                                               ▼ (Hand-off to Production)
[Select Recipe / BOM] ──► [Verify Approved Stock] ──► [Create Production Batch]
                                                               │
    ┌──────────────────────────────────────────────────────────┘
    ▼
[5-Stage Stepper: Cleaning ──► Roasting ──► Pressing ──► Filtration ──► Packaging]
    │
    ▼
[Finished Goods: LOT-2026-xxx] ──► (Hand-off to Part 4: Warehouse FEFO)
```

1. **Procurement Intake**:
   - Procurement creates a Purchase Order (e.g. `PO-2026-001` for 25 Tons of Corn from AgriGrain Ltd).
   - When the delivery truck arrives at the factory gate, dock workers create a Goods Receipt Note (GRN), verifying delivery notes and truck license plates.
   - The GRN automatically generates a new record in `raw_material_lots` (`DEMO-LOT-REL-01`).
   - The lot is initialized with status `PENDING` and `qc_status = 'PENDING_QC'`.
2. **The QC Gate Hand-off**:
   - The lot is locked. Production cannot touch it.
   - Part 1 (AI Inspection) scans the grain; Part 2 (Release Engine) certifies the COA.
   - Once Part 2 signs off, the lot status updates to `APPROVED`.
3. **BOM Allocation & Batch Execution**:
   - Production reviews BOM Planning (`/production?view=recommendations`).
   - The supervisor creates a new batch. In `routes/production.py:create_batch()`, the backend executes:
     ```python
     approved_lots = db.query(RawMaterialLot).filter(
         RawMaterialLot.raw_material_id == bom.raw_material_id,
         RawMaterialLot.qc_status == 'APPROVED',
         RawMaterialLot.quantity > 0
     ).all()
     ```
   - If stock is insufficient or unapproved, the server aborts with an HTTP 400 error.
   - The server decrements the lot balance, generates batch code `LOT-2026-xxx`, and initializes the 5-stage process stepper:
     - **Stage 1**: Grain Cleaning & Shelling
     - **Stage 2**: Roasting / Thermal Pasteurization (e.g. 120°C / 20 min)
     - **Stage 3**: Screw Press Oil Extraction / Milling
     - **Stage 4**: Multi-Stage Oil Filtration
     - **Stage 5**: Packaging, Sealing & Capping
4. **Packaging & Warehouse Transfer**:
   - The operator logs completed cases (e.g. 168 carton boxes) and waste count.
   - The batch completes and syncs directly into Part 4's FEFO warehouse inventory.

---

## 4. Live Demo Click Path (Step-by-Step)

### Phase 1: Procurement Intake (1.5 Minutes)
1. **Login**: Sign in as Procurement Officer (`procurement@foodman.vn` via `/demo-login/procurement`).
2. **Suppliers**: Open `/procurement?view=suppliers`. Click **AgriGrain Certified Supply Ltd** (`SUP-DEMO-REL`). Show ratings and certifications.
3. **Purchase Orders**: Switch to `/procurement?view=po`. Click `PO-2026-001` to open the slide-over `DetailDrawer`. Point to 25 Tons Corn line item.
4. **Goods Receipts**: Switch to `/procurement?view=grn`. Show delivery receipt note and truck plate `29C-438.12`.
5. **Raw Material Lots**: Switch to `/procurement?view=lots`. Point out newly created lot **`DEMO-LOT-REL-01`**:
   - Highlight yellow status badge: **`PENDING`** with QC status **`PENDING_QC`**.
   - Emphasize to the audience: *"This grain cannot enter food production until Member 1 and Member 2 certify it."*

### Phase 2: Production Execution (1.5 Minutes — After Member 2 Approves Lot)
1. **Login**: Switch to Production Supervisor (`production@foodman.vn` via `/demo-login/production`).
2. **BOM Readiness**: Open `/production?view=recommendations`. Show that `Corn Milk UHT 250ml` shows green **"Ready to Produce"** because `DEMO-LOT-REL-01` was approved by Member 2.
3. **Create Batch**:
   - Switch to `/production?view=batches`.
   - Click **"+ New Production Batch"**.
   - Select Product: `Pure Roasted Corn Snack Pack`.
   - Show the lot allocation selector: point out that only **`APPROVED`** lots appear in the dropdown. Unapproved lots (`PENDING` or `REJECTED`) are blocked.
   - Click **"Create Batch"** -> Generates `LOT-2026-012`.
4. **Advance 5-Stage Stepper**:
   - Click the batch card to view the stepper.
   - Click **"Advance Stage"** to progress from Cleaning to Roasting. Point out temperature parameters (`120°C`).
   - Click **"Record Packaging"** -> Enter 168 cartons, 2 rolls, 4 waste. Submit and show batch completion.

---

## 5. Spoken Script (2 Minutes)

> *"Hello committee. I am Member 3, and I built the Procurement Intake and Manufacturing Execution pipeline for Food Man.*
>
> *A food factory is only as safe as its incoming agricultural supply chain. In our Procurement module, every supplier must be vetted and certified. Under Purchase Order PO-2026-001, we ordered 25 tons of raw corn from AgriGrain Ltd. When the shipment arrives at our receiving dock, our warehouse crew issues a Goods Receipt Note (GRN) logging the truck plate and bill of lading.*
>
> *This automatically generates a new raw material lot in our database, `DEMO-LOT-REL-01`. As you can see on screen, it is strictly locked in `PENDING_QC` status. Under our manufacturing rules, uninspected raw material can never be allocated to factory equipment. It must first be scanned by Member 1's vision station and certified by Member 2's laboratory release engine.*
>
> *(After Member 1 and Member 2 complete the approval)*
>
> *Now that Member 2 has signed off on `DEMO-LOT-REL-01`, watch how Production responds. Here on our BOM Readiness dashboard, the system calculates ingredient availability in real time.*
>
> *When I open our New Production Batch modal, our backend queries the database for approved stock. If an operator attempts to allocate unapproved, quarantined, or rejected lots, the request is rejected with HTTP 400. Because our corn lot is certified APPROVED, the system clears it for manufacturing.*
>
> *Once created, the batch executes through our standardized 5-stage manufacturing stepper: grain cleaning, roasting at 120°C, extraction, filtration, and case packaging. Each stage logs process temperatures and operator IDs.*
>
> *Finally, we log our packaging records and case quantities. The batch is marked COMPLETED and immediately transfers to Member 4 for FEFO warehouse management and cold-chain dispatch."*

---

## 6. Honest Limitations & Future Work

### Verified Code Limitations
1. **Single-Facility Stock Model**:
   - The current schema assumes a single centralized manufacturing plant. Multi-site multi-factory inventory transfers (e.g. shipping corn between Hanoi and Da Nang plants) are not modeled.
2. **BOM Scaling Linear Model**:
   - Recipe BOM calculations scale strictly linearly with target batch yield. Non-linear industrial yield losses (e.g. fixed startup evaporator flush loss) must be accounted for in packaging waste logs rather than the BOM formula.
3. **Manual Stepper Advancement**:
   - Advancing the 5 process stages is performed via UI clicks by the shift supervisor; there is no live IoT SCADA PLC connection directly pulling roasting oven thermocouple readings into the database.

### One Sentence on Future Work
> *"Future work will integrate OPC-UA industrial automation protocols to automatically advance production stages directly from programmable logic controllers (PLCs) and temperature sensors on the roasting and packaging lines."*

---

## 7. 10 Likely Questions & Correct Answers

1. **Q: How does the backend prevent an unapproved lot from being used in production?**  
   *A: In `routes/production.py:create_batch()`, the database query explicitly filters `RawMaterialLot.qc_status == 'APPROVED'`. If available approved stock is less than the recipe requirement, the server returns an HTTP 400 error: "Insufficient QC-approved raw materials."*
2. **Q: What happens if a production recipe requires multiple raw materials?**  
   *A: In `models/production.py`, a `Recipe` has a one-to-many relationship with `RecipeMaterial`. The `create_batch()` function iterates through every BOM item and verifies that approved lots exist for all required ingredients before creating the batch.*
3. **Q: Can a Purchase Order be edited once goods have been received?**  
   *A: No. Once a Goods Receipt Note (GRN) has been issued against a PO, the PO status changes to `PARTIAL_RECEIVED` or `COMPLETED`. Voiding or modifying line items is locked to preserve financial integrity.*
4. **Q: What information is captured on a Goods Receipt Note (GRN)?**  
   *A: Delivery date, receiving warehouse user ID, supplier reference, delivery note / bill of lading ref, delivery truck license plate, physical quantities received, and auto-generated raw material lot IDs.*
5. **Q: How does the system calculate how many batches can be produced?**  
   *A: In `routes/production.py:get_recommendations()`, the system calculates `int(available_approved_qty / bom.required_qty)` across all recipe ingredients and takes the mathematical minimum (`min()`), showing the limiting bottleneck ingredient.*
6. **Q: What are the 5 production stages in the manufacturing stepper?**  
   *A: Stage 1: Material Cleaning & Shelling; Stage 2: Roasting & Thermal Processing; Stage 3: Milling & Pressing; Stage 4: Multi-Stage Filtration; Stage 5: Bottling, Capping & Case Packing.*
7. **Q: Where are packaging material losses and defective boxes recorded?**  
   *A: In the `packaging_records` table, which logs `carton_boxes_used`, `packaging_seal_rolls_used`, `packages_completed`, and `waste_count` alongside the inspecting supervisor ID.*
8. **Q: How are lot quantities updated when a batch is created?**  
   *A: In `create_batch()`, the system decrements `RawMaterialLot.quantity` by the consumed amount and creates a junction record in `batch_raw_materials` storing the exact quantity allocated for full traceability.*
9. **Q: Can an inactive supplier receive a Purchase Order?**  
   *A: No. The supplier selector filters out suppliers where `is_active == False` or `status == 'DEACTIVATED'`.*
10. **Q: What user role is required to advance a production batch stage?**  
    *A: `RoleEnum.PRODUCTION` or `RoleEnum.ADMIN`. The endpoint `/api/production/batches/<id>/advance-stage` rejects unauthorized roles.*

---

## 8. Key Terms to Know

- **BOM (Bill of Materials)**: The comprehensive list of raw materials, ingredients, and quantities required to manufacture one standard batch of finished product.
- **GRN (Goods Receipt Note)**: A formal industrial document confirming the physical receipt of goods at the dock, verifying delivery quantities against a purchase order.
- **UHT (Ultra-High Temperature)**: Thermal food sterilization method processing liquid food at over 135°C for 2–5 seconds.
- **Stepper Flow**: Sequential manufacturing state machine ensuring process stages are completed in physical chronological order.
- **Lot Allocation Lock**: Database invariant preventing unapproved inventory from being reserved or consumed.

---

## 9. What NOT to Claim or Click During Demo

- **DO NOT claim automated IoT SCADA / PLC hardware integration**: Be honest that stage advancement is currently operator-logged.
- **DO NOT attempt to create a batch using an unapproved lot without explaining the error**: If showing the rejection, clearly explain: *"Watch how the system rejects this with an HTTP 400 error."*
- **DO NOT claim multi-factory ERP synchronization**: Food Man is currently optimized as a unified single-plant MES.
- **DO NOT click "Void PO" on an active demo purchase order**: Keep `PO-2026-001` intact for the demo narrative.
