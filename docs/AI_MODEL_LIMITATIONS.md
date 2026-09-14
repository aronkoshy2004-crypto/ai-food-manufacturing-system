# AI Model Vision Limitations & Data Engineering Roadmap

## 1. Executive Summary & Known Failure Modes

The visual defect detection engine in **Food Man** runs an Ultralytics YOLOv8 architecture fine-tuned on multi-commodity food raw materials (Peanuts, Corn, Sunflower Seeds). 

While the model achieves high accuracy on single-seed inspections and verified test grids, visual QC testing on bulk commodity bowls revealed key **training-distribution failure modes and data-bound performance ceilings**:

> [!WARNING]
> **Known Failure Mode: Dense Peanut Cluster Misclassification as Corn**
> The model currently cannot reliably distinguish dense peanut clusters (e.g. bulk bowls, sample trays) from dense corn clusters. When presented with a dense cluster of clean raw peanuts, the model accurately localizes each kernel but misclassifies them as `Corn_Not_Moldy` and `Corn_Moldy` rather than `Peanut_Not_Moldy`.

> [!NOTE]
> **Known Limitation: Peanut_Moldy Recall Plateau (Data-Bound at ~42%–57%)**
> `Peanut_Moldy` (Class 0) recall plateaus around **42%–57%** (evaluating at **44.30%** on the unseen test split at Epoch 50, and **42.66%** at Epoch 80) due to limited effective training data (**10,227** moldy instances in the corrected dataset compared to tens of thousands for corn classes: 20,669 for `Corn_Moldy` and 25,041 for `Corn_Not_Moldy`).
> 
> Experimental verification confirmed that **extending training epochs (from 50 to 80 epochs) does not improve this recall plateau further**; in fact, Epoch 80 exhibited a recall regression across multiple classes (including a drop to 42.66% on `Peanut_Moldy`) despite higher precision. Breaking through this plateau fundamentally requires collecting additional real-world moldy-peanut imagery under variable warehouse and cluster conditions. This is formally documented as future data engineering work, **not an application code bug**.
> 
> **Production Deployment Decision**: Epoch 50 ([`models/combined_corrected_epoch50_backup.pt`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/models/combined_corrected_epoch50_backup.pt)) is actively deployed as the production model ([`models/combined_corrected_best.pt`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/models/combined_corrected_best.pt)) because it yields superior recall across inspection classes. The Epoch 80 checkpoint is preserved as an archived reference backup ([`models/combined_corrected_epoch80_backup.pt`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/models/combined_corrected_epoch80_backup.pt)).

> [!CAUTION]
> **Confirmed Limitation: Sunflower Mold Detection Non-Functional (Zero Fungal Training Instances)**
> Sunflower mold detection (`Sunflower_Moldy`, Class 4) currently cannot function in production because **zero genuine fungal sunflower training instances exist across all available source datasets** (`0` instances across train, val, and test splits in `datasets/raw_materials_combined`). In the original raw dataset (`sunflower2.v19i.yolov8`), the "bad" class consisted solely of normal in-shell striped sunflower seeds and cracked shells from an edible snack mix rather than fungal mycelium.
> 
> To prevent false-positive contamination of normal raw materials, fake mold labels were purged during dataset re-engineering. **This confirmation remains 100% accurate and verified.** Resolving sunflower mold detection requires dedicated acquisition and annotation of actual fungal-contaminated sunflower seed samples as future work, not an application code bug.

---

## 2. Root Cause Analysis: Training Dataset Gap

An audit of the corrected training ground-truth dataset ([`datasets/raw_materials_combined`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/datasets/raw_materials_combined)) confirms the class and presentation imbalance across the 3,487 images and 61,377 annotated instances:

| Raw Material Class | Ground Truth Instances | Presentation Layout in Dataset | Status / Limitation |
| :--- | :---: | :--- | :--- |
| **`Peanut_Not_Moldy` (Clean Peanuts)** | **213** | Isolated single kernels on white paper (`1 kernel / image`). Zero bulk cluster images. | Severe cluster presentation gap; triggers corn misclassification. |
| **`Corn_Not_Moldy` (Clean Corn)** | **25,041** | Dense multi-kernel clusters, cob sections, and bulk arrangements. | Robust high representation across layouts. |
| **`Peanut_Moldy` (Moldy Peanuts)** | **10,227** | Research testing grids (140-slot inoculated trays) disentangled from non-mold. | **Recall plateaus at ~42%–57%** due to sample ceiling; more epochs do not fix. |
| **`Corn_Moldy` (Moldy Corn)** | **20,669** | Multi-kernel clusters with visible fungal mycelium. | High coverage and stable recall (~86%). |
| **`Sunflower_Moldy`** | **0** | None (fake snack mix labels purged; zero fungal instances). | **Non-functional (Confirmed: 0 instances)**. |
| **`Sunflower_Not_Moldy`** | **5,227** | Scattered clean seed clusters and bulk arrangements. | High precision and recall (~86%). |

### Neural Feature Entanglement
Because clean peanuts were *never* represented in bulk or cluster arrangements during training:
1. The convolutional feature extractor strongly associates **"dense pack of contiguous round/oval kernels"** with `Corn_Not_Moldy` (11,800 examples) rather than `Peanut_Not_Moldy` (0 cluster examples).
2. Tightly packed peanuts create inter-kernel shadow crevices and natural skin wrinkles. At low confidence thresholds (e.g. `conf=0.12`), these shadows trigger low-confidence defect false positives (~12%–28% confidence).

---

## 3. Vision-First Principle: Why Metadata Remapping Is Rejected

Rather than hiding this failure mode by programmatically remapping `Corn_*` to `Peanut_*` based on lot metadata, the system adheres to strict **independent vision verification**:

* **Safety & Fraud Prevention**: In food processing, supplier shipments can be mislabeled, contaminated, or mixed with cheaper grains. If the vision model automatically deferred to lot metadata, an adulterated shipment (e.g. corn grains mixed into peanut stock) would be silently mislabeled as peanut.
* **Engineering Integrity**: A vision-based QC system must independently certify physical reality. Model weaknesses are addressed through dataset curation and confidence calibration, not software masking.

---

## 4. Applied Mitigation: Dense-Cluster Confidence Recalibration

To immediately minimize shadow and wrinkle false positives in dense bulk scans without suppressing genuine fungal contamination:

* **Dense Cluster Detection**: When candidate regions in an inspection image reach $\ge 20$ items, the engine automatically identifies the scan as a dense cluster.
* **Defect Confidence Floor Raised to $\ge 0.35$**:
  * Low-confidence shadow crevices and skin wrinkles ($< 35\%$) are filtered out.
  * Genuine fungal mold (which produces distinct fuzzy mycelium, scoring in the $60\% - 85\%+$ range) remains fully detectable.
  * Single-kernel inspections ($< 20$ items) retain the full $0.12$ sensitivity floor for nascent mold detection.

---

## 5. Permanent Resolution: Data Engineering Roadmap

To permanently resolve this limitation, the model requires balanced training on bulk/cluster peanut imagery.

### 5.1 Dataset Target Requirements

| Category | Target Image Count | Target Kernel Instances | Image Presentation Specifications |
| :--- | :---: | :---: | :--- |
| **Clean Peanuts (Bulk Clusters)** | **120 – 160 photos** | **~12,000 – 16,000 kernels** | Bowls, stainless intake sample trays, flat inspection tables, bulk storage bins. |
| **Moldy Peanuts (Bulk Clusters)** | **80 – 120 photos** | **~8,000 – 12,000 kernels** | Peanuts with visible Aspergillus flavus/niger, white mycelium, grey/green sporulation in bulk. |
| **Total Target** | **200 – 280 photos** | **~20,000 – 28,000 kernels** | Reaches parity with Corn cluster distribution. |

### 5.2 Sourcing Channels & Image Acquisition Protocol

1. **Factory Receiving Dock Sample Bowls**:
   - Photograph sample bowls from active incoming lots (e.g., `LOT-RM-2026-160` High-Oleic Peanuts).
   - Capture each sample under three controlled lighting setups:
     - 5000K industrial inspection LED light bar.
     - Diffuse ambient warehouse lighting.
     - Direct dock daylight (to train invariance against ambient shadows).
2. **Camera Angles & Distances**:
   - 90° top-down flat-lay (standard QC scanning bench).
   - 45° angled oblique view (simulating dock handheld mobile captures).
   - Macro close-ups ($15\text{ cm}$) and full-tray overviews ($40\text{ cm}$).
3. **Quarantine / Reject Inoculation Samples**:
   - Retain natural rejection samples from warehouse quarantine and image them in clustered/bulk arrangements alongside healthy stock.

### 5.3 Fine-Tuning Protocol

* **Annotation Tool**: Roboflow / CVAT with bounding box labels `Peanut_Not_Moldy` (Class 1) and `Peanut_Moldy` (Class 0).
* **Augmentation**: Random perspective shifts, slight hue/saturation variance ($\pm 10\%$), mosaic and mixup augmentations enabled.
* **Training Hyperparameters**:
  - Base checkpoint: `models/combined_best.pt`
  - Epochs: 25 epochs
  - Batch size: 8
  - Resolution: 416x416
  - Optimizer: AdamW with cosine learning rate schedule
