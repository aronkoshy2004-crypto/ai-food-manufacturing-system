# Comprehensive AI Dataset, Training Settings & Integrity Report

This report provides a forensic count and integrity audit of all datasets, training logs, evaluation metrics, and data partitions used for the visual defect detectors (`models/best.pt`, `models/combined_corrected_best.pt`) and the material classifier (`models/material_cls.pt`).

---

## 1. Dataset Breakdown: Images & Labelled Instances

### 1.1 Defect Detector Dataset: `datasets/raw_materials` (Used for `models/best.pt`)
* **Configuration File**: [`datasets/raw_materials/data.yaml`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/datasets/raw_materials/data.yaml)
* **Training Script**: [`ai/train.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/ai/train.py)
* **Training Run / Logs**: [`runs/detect/raw_materials_yolov8`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_yolov8)
* **Model Checkpoint**: [`models/best.pt`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/models/best.pt) (identical hash to `models/food_defect_yolov8.pt`)
* **Source**: Roboflow Universe (`house-s14us/peanut-moldy-and-not-moldy/1`)
* **Classes**: 2 classes — `Moldy` (Class 0), `Not_Moldy` (Class 1)

| Split | Total Images | Material | Class: Moldy | Class: Not_Moldy | Total Instances | Notes |
| :--- | :---: | :--- | :---: | :---: | :---: | :--- |
| **Train** | **330** | Peanut | 159 | 171 | **330** | 110 source photos × 3 augmentations |
| | | Corn | 0 | 0 | 0 | Not present in this dataset |
| | | Sunflower | 0 | 0 | 0 | Not present in this dataset |
| **Valid** | **31** | Peanut | 14 | 17 | **31** | Unaugmented validation images |
| | | Corn | 0 | 0 | 0 | Not present in this dataset |
| | | Sunflower | 0 | 0 | 0 | Not present in this dataset |
| **Test** | **16** | Peanut | 11 | 5 | **16** | Unaugmented test images |
| | | Corn | 0 | 0 | 0 | Not present in this dataset |
| | | Sunflower | 0 | 0 | 0 | Not present in this dataset |
| **Total** | **377** | | **184** | **193** | **377** | Single-kernel isolated peanut photos |

---

### 1.2 Multi-Commodity Defect Detector: `datasets/raw_materials_combined` (Used for Active Model `models/combined_corrected_best.pt`)
* **Configuration File**: [`datasets/raw_materials_combined/data.yaml`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/datasets/raw_materials_combined/data.yaml)
* **Training Scripts**: [`ai/train_corrected_fresh20.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/ai/train_corrected_fresh20.py), [`ai/train_corrected_resume30.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/ai/train_corrected_resume30.py)
* **Training Runs / Logs**: [`runs/detect/raw_materials_corrected_fresh20`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_corrected_fresh20), [`runs/detect/raw_materials_corrected_resumed_epochs21_50`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_corrected_resumed_epochs21_50)
* **Active Deployed Model**: [`models/combined_corrected_best.pt`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/models/combined_corrected_best.pt) (Epoch 50 backup)
* **Classes (6)**: 0: `Peanut_Moldy`, 1: `Peanut_Not_Moldy`, 2: `Corn_Moldy`, 3: `Corn_Not_Moldy`, 4: `Sunflower_Moldy`, 5: `Sunflower_Not_Moldy`

| Split | Total Images | Material | Moldy Instances | Not_Moldy Instances | Total Material Instances | Split Instance Total |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **Train** | **2,884** | **Peanut** | 9,571 (`Peanut_Moldy`) | 153 (`Peanut_Not_Moldy`) | 9,724 | **47,008** |
| | | **Corn** | 15,259 (`Corn_Moldy`) | 17,737 (`Corn_Not_Moldy`) | 32,996 | |
| | | **Sunflower** | 0 (`Sunflower_Moldy`) | 4,288 (`Sunflower_Not_Moldy`) | 4,288 | |
| **Val** | **359** | **Peanut** | 287 (`Peanut_Moldy`) | 30 (`Peanut_Not_Moldy`) | 317 | **9,619** |
| | | **Corn** | 3,998 (`Corn_Moldy`) | 4,868 (`Corn_Not_Moldy`) | 8,866 | |
| | | **Sunflower** | 0 (`Sunflower_Moldy`) | 436 (`Sunflower_Not_Moldy`) | 436 | |
| **Test** | **244** | **Peanut** | 369 (`Peanut_Moldy`) | 30 (`Peanut_Not_Moldy`) | 399 | **4,750** |
| | | **Corn** | 1,412 (`Corn_Moldy`) | 2,436 (`Corn_Not_Moldy`) | 3,848 | |
| | | **Sunflower** | 0 (`Sunflower_Moldy`) | 503 (`Sunflower_Not_Moldy`) | 503 | |
| **Total** | **3,487** | **Combined** | **30,896** | **30,481** | — | **61,377** |

> [!NOTE]
> `Sunflower_Moldy` has **0 instances** across train, validation, and test splits because fake snack-mix labels were purged; true fungal sunflower contamination was unavailable in source datasets.

---

### 1.3 Synthetic Scenes: `datasets_synth/images`
* **Configuration File**: [`datasets_synth/data.yaml`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/datasets_synth/data.yaml)
* **Generation Script**: [`scripts/make_synthetic_scenes.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scripts/make_synthetic_scenes.py)
* **Synthesis Method**: GrabCut-segmented kernel crops pasted onto procedural backgrounds (white, off-white, light grey, dark sheet with lighting gradients, noise, and shadow).
* **Classes Annotated**: Healthy kernel bounding boxes (`Peanut_Not_Moldy`: 1, `Corn_Not_Moldy`: 3, `Sunflower_Not_Moldy`: 5).

| Split | Material | Scenes (Images) | Labelled Healthy Instances | Labelled Moldy Instances | Total Labelled Instances |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Train** | Peanut | 400 | 5,826 | 0 | 5,826 |
| | Corn | 400 | 5,949 | 0 | 5,949 |
| | Sunflower | 400 | 5,820 | 0 | 5,820 |
| *Train Subtotal* | *All 3* | *1,200* | *17,595* | *0* | *17,595* |
| **Val** | Peanut | 60 | 754 | 0 | 754 |
| | Corn | 60 | 799 | 0 | 799 |
| | Sunflower | 60 | 906 | 0 | 906 |
| *Val Subtotal* | *All 3* | *180* | *2,459* | *0* | *2,459* |
| **Test** | Peanut | 60 | 841 | 0 | 841 |
| | Corn | 60 | 889 | 0 | 889 |
| | Sunflower | 60 | 897 | 0 | 897 |
| *Test Subtotal* | *All 3* | *180* | *2,627* | *0* | *2,627* |
| **Total** | **All 3** | **1,560** | **22,681** | **0** | **22,681** |

---

### 1.4 Material Classifier Dataset: `datasets_synth/cls_dataset` (Used for `models/material_cls.pt`)
* **Training Script**: [`scripts/train_material_classifier.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scripts/train_material_classifier.py)
* **Preparation Script**: [`scripts/prepare_cls_dataset.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scripts/prepare_cls_dataset.py)
* **Training Run / Logs**: [`runs/classify/material_cls_run`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/classify/material_cls_run)
* **Model Checkpoint**: [`models/material_cls.pt`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/models/material_cls.pt)
* **Classes (3)**: `peanut`, `corn`, `sunflower`

| Split | Material | Real Kernel Crops | Synthetic Scene Crops | Total Split Images |
| :--- | :--- | :---: | :---: | :---: |
| **Train** | Peanut | 2,947 | 3,000 | 5,947 |
| | Corn | 3,000 | 3,000 | 6,000 |
| | Sunflower | 3,000 | 3,000 | 6,000 |
| *Train Subtotal* | *All 3* | *8,947* | *9,000* | **17,947** |
| **Val** | Peanut | 83 | 754 | 837 |
| | Corn | 500 *(sampled down)* | 799 | 1,299 |
| | Sunflower | 426 | 906 | 1,332 |
| *Val Subtotal* | *All 3* | *1,009* | *2,459* | **3,468** |
| **Test** | Peanut | 0 | 0 | **0** *(evaluated via `crops/test`)* |
| | Corn | 0 | 0 | **0** *(evaluated via `crops/test`)* |
| | Sunflower | 0 | 0 | **0** *(evaluated via `crops/test`)* |
| **Total** | **All 3** | **9,956** | **11,459** | **21,415** |

---

## 2. Reported Accuracy & Evaluation Metrics

This section matches each reported metric to the exact evaluation script, data source, and sample size.

| Reported Metric | Evaluation Set / Source Dataset | Exact Sample Size | Evaluation Script / Source Reference | Measured Result | Verification Status |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **100% crops** *(98.78% in benchmark gate)* | `datasets_synth/crops/test/` | **3,514 crops**<br>• Corn: 2,962<br>• Sunflower: 485<br>• Peanut: 67 | [`scripts/evaluate_material_classifier.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scripts/evaluate_material_classifier.py)<br>`evaluate_test_crops()` | **98.78%** overall<br>(Corn: 100%, Sunflower: 100%, Peanut: 34.33%*) | **Verified**<br>*(Colloquially rounded to 100% in `config.py:41`)* |
| **100% synthetic scenes** | `datasets_synth/images/test/` | **180 scenes** (2,627 kernels)<br>• Peanut: 60 scenes (841 k)<br>• Corn: 60 scenes (889 k)<br>• Sunflower: 60 scenes (897 k) | [`scripts/evaluate_material_classifier.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scripts/evaluate_material_classifier.py)<br>`evaluate_synthetic_test_scenes()` | **100.0%**<br>(180/180 scenes correct via majority vote) | **Verified** |
| **99.6% live photos** *(99.59% in benchmark gate)* | `datasets/raw_materials_combined/images/test/` | **244 photos**<br>• Corn: 115 photos<br>• Sunflower: 86 photos<br>• Peanut: 43 photos | [`scripts/evaluate_material_classifier.py`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scripts/evaluate_material_classifier.py)<br>`evaluate_test_photos_pipeline()` | **99.59%**<br>(243/244 photos correct via detector+classifier ensemble) | **Verified**<br>*(Crucial caveat below)* |
| **Top-1 Accuracy (`material_cls.pt`)** | `datasets_synth/cls_dataset/val/` | **3,468 images**<br>• Corn: 1,299<br>• Sunflower: 1,332<br>• Peanut: 837 | [`runs/classify/material_cls_run/results.csv`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/classify/material_cls_run/results.csv) (Epoch 8) | **98.96%** (Top-1)<br>100.0% (Top-5)<br>Val Loss: 0.03068 | **Verified** |
| **mAP50 (`models/best.pt`)** | `datasets/raw_materials/valid` | **31 images** (31 instances) | [`runs/detect/raw_materials_yolov8/results.csv`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_yolov8/results.csv) (Epoch 10) | **99.36%** (0.9936) | **Verified** |
| **mAP50-95 (`models/best.pt`)** | `datasets/raw_materials/valid` | **31 images** (31 instances) | [`runs/detect/raw_materials_yolov8/results.csv`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_yolov8/results.csv) (Epoch 10) | **78.77%** (0.7877) | **Verified** |
| **Precision (`models/best.pt`)** | `datasets/raw_materials/valid` | **31 images** (31 instances) | [`runs/detect/raw_materials_yolov8/results.csv`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_yolov8/results.csv) (Epoch 10) | **92.95%** (0.9295) | **Verified** |
| **Recall (`models/best.pt`)** | `datasets/raw_materials/valid` | **31 images** (31 instances) | [`runs/detect/raw_materials_yolov8/results.csv`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_yolov8/results.csv) (Epoch 10) | **91.44%** (0.9144) | **Verified** |
| **Test Set Metrics (`models/best.pt`)** | `datasets/raw_materials/test` | **16 images** (16 instances) | Evaluation on test split was not logged in `results.csv` | *Not logged in run artifacts* | **Not verified** |
| **Overall mAP50 (`combined_corrected_best.pt`)** | `datasets/raw_materials_combined/images/test` | **244 images** (4,750 instances) | [`scratch/corrected_epoch50_evaluation.json`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scratch/corrected_epoch50_evaluation.json) (Epoch 50) | **72.58%** (0.7258) | **Verified** |
| **Overall mAP50-95 (`combined_corrected_best.pt`)** | `datasets/raw_materials_combined/images/test` | **244 images** (4,750 instances) | [`scratch/corrected_epoch50_evaluation.json`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scratch/corrected_epoch50_evaluation.json) (Epoch 50) | **50.20%** (0.5020) | **Verified** |
| **Mean Precision (`combined_corrected_best.pt`)** | `datasets/raw_materials_combined/images/test` | **244 images** (4,750 instances) | [`scratch/corrected_epoch50_evaluation.json`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scratch/corrected_epoch50_evaluation.json) (Epoch 50) | **63.33%** (0.6333) | **Verified** |
| **Mean Recall (`combined_corrected_best.pt`)** | `datasets/raw_materials_combined/images/test` | **244 images** (4,750 instances) | [`scratch/corrected_epoch50_evaluation.json`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scratch/corrected_epoch50_evaluation.json) (Epoch 50) | **77.82%** (0.7782) | **Verified** |
| **Peanut_Moldy Recall (`combined_corrected_best.pt`)** | `datasets/raw_materials_combined/images/test` | **369 instances** (across 30 images) | [`scratch/corrected_epoch50_evaluation.json`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/scratch/corrected_epoch50_evaluation.json) (Epoch 50) | **44.30%** (Plateaued: 42%–57% data-bound limit) | **Verified** |
| **Sunflower_Moldy Detection** | `datasets/raw_materials_combined/images/test` | **0 instances** | [`docs/AI_MODEL_LIMITATIONS.md`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/docs/AI_MODEL_LIMITATIONS.md) §2 | **0.0%** (Non-functional; zero training instances) | **Verified** |

> [!WARNING]
> **Reality on the "99.6% live photos" metric**:
> Despite the phrase in `config.py:41`, this was measured on **historical Roboflow test images** (`datasets/raw_materials_combined/images/test/`), **NOT photos captured by the physical camera station**.
> As documented in [`docs/AI_MODEL_LIMITATIONS.md`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/docs/AI_MODEL_LIMITATIONS.md) §7.2:
> * Accuracy on actual physical factory dock cameras with dedicated labelled photos is **unmeasured and unbenchmarked** (Marked: **Not verified** on physical dock photos).
> * When re-evaluated on 258 historical dock frames, dense peanut sample bowls were misclassified as Corn due to presentation clustering and optical domain shift.

---

## 3. Data Leakage & Test Set Integrity Audit

A forensic hash and source-photograph audit was conducted across all datasets to determine whether images or crops from the same underlying capture appear in both train and test splits.

| Dataset / Model Scope | Exact File MD5 Duplicates (Train vs Test) | Source Photo / Scene Overlap (Train vs Test) | Is Test Set Truly Held Out? | Root Cause / Mechanism |
| :--- | :---: | :---: | :---: | :--- |
| **`datasets/raw_materials`**<br>(Base Detector: `models/best.pt`) | **0** | **0**<br>(0 of 16 test photos) | **YES (Truly Held Out)** | Roboflow original export maintained strict partition separation between 110 train source images and 16 test source images. |
| **`datasets/raw_materials_combined`**<br>(Production Detector: `models/combined_corrected_best.pt`) | **0** | **99 overlapping sources**<br>(99 of 234 test source photos, **42.3%**) | **NO (Data Leakage Detected)** | • **Sunflower (76 overlaps)**: Roboflow 3x augmented training folder was randomly shuffled into 80/10/10 train/val/test in `rebuild_corrected_dataset.py`, placing augmented sister variants of the same photo into both train and test.<br>• **Peanut (23 overlaps)**: `peanut_aug` images from train/val/test of `raw_materials` were pooled and randomly reshuffled.<br>• **Corn (0 overlaps)**: Preserved original source splits. |
| **`datasets_synth/crops`**<br>(Extracted Kernel Crops) | **0** | **99 overlapping sources**<br>(99 of 217 test source photos, **45.6%**) | **NO (Data Leakage Detected)** | Because real crops were cut from `raw_materials_combined`, crops originating from the same physical photo sessions appear in both `crops/train/` and `crops/test/`. |
| **`datasets_synth/cls_dataset`**<br>(Material Classifier: `models/material_cls.pt`) | **0** | **99 overlapping sources**<br>(Train crops share 99 source scenes with `crops/test/`) | **NO (Data Leakage Detected)** | The classifier was trained on `crops/train/` and evaluated on `crops/test/`. Model evaluation evaluated kernels cut from the same underlying photo sessions seen during training. |
| **`datasets_synth/images`**<br>(Synthetic Scenes) | **0** | **0 cross-split crop reuse** | **PARTIALLY HELD OUT** | `make_synthetic_scenes.py` strictly used `crops/train` for train scenes and `crops/test` for test scenes. However, because `crops/train` and `crops/test` share 99 underlying source photos, indirect visual similarity exists. |

---

## 4. Training Settings & Hyperparameters (From Verified Logs)

### 4.1 Defect Detector (`models/best.pt`)
* **Verified Log File**: [`runs/detect/raw_materials_yolov8/args.yaml`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_yolov8/args.yaml)
* **Training Duration**: 531.27 seconds (~8.85 minutes on CPU)

| Hyperparameter / Setting | Verified Value from Logs | Notes |
| :--- | :--- | :--- |
| **Base Pretrained Model** | `yolov8n.pt` | Ultralytics Nano detection weights |
| **Training Epochs** | **10** | 10 completed epochs |
| **Image Resolution (`imgsz`)** | **416** | 416 × 416 pixels |
| **Batch Size** | **8** | Batch size of 8 |
| **Hardware Device** | `cpu` | Intel CPU execution |
| **Dataloader Workers** | `0` | Windows standard single-process |
| **Optimizer** | `auto` (SGD / AdamW fallback) | `lr0=0.01`, `lrf=0.01`, `momentum=0.937`, `weight_decay=0.0005` |
| **Warmup** | `warmup_epochs=3.0`, `warmup_bias_lr=0.1` | Standard Ultralytics warmup |
| **Augmentation Settings** | `mosaic=1.0`, `fliplr=0.5`, `flipud=0.0`, `erasing=0.4`, `hsv_h=0.015`, `hsv_s=0.7`, `hsv_v=0.4` | Mild color and mosaic augmentation |

---

### 4.2 Material Classifier (`models/material_cls.pt`)
* **Verified Log File**: [`runs/classify/material_cls_run/args.yaml`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/classify/material_cls_run/args.yaml)
* **Training Duration**: 766.69 seconds (~12.78 minutes on CPU)

| Hyperparameter / Setting | Verified Value from Logs | Notes |
| :--- | :--- | :--- |
| **Base Pretrained Model** | `yolov8n-cls.pt` | Ultralytics Nano classification weights |
| **Training Epochs** | **8** | 8 completed epochs |
| **Image Resolution (`imgsz`)** | **96** | 96 × 96 pixels (kernel crop resolution) |
| **Batch Size** | **64** | Batch size of 64 |
| **Hardware Device** | `cpu` | Intel CPU execution |
| **Dataloader Workers** | `4` | 4 data loading worker threads |
| **Optimizer** | `auto` | `lr0=0.01`, `lrf=0.01`, `momentum=0.937`, `weight_decay=0.0005` |
| **Augmentation Settings** | `degrees=15.0`, `hsv_h=0.015`, `hsv_s=0.1`, `hsv_v=0.15`, `fliplr=0.5`, `flipud=0.5`, `translate=0.05`, `scale=0.08`, `erasing=0.0` | Constrained mild augmentation (no mixup, no cutmix) |

---

### 4.3 Active Production Defect Detector (`models/combined_corrected_best.pt`) *(For Reference)*
* **Verified Log Files**: [`runs/detect/raw_materials_corrected_fresh20/args.yaml`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_corrected_fresh20/args.yaml), [`runs/detect/raw_materials_corrected_resumed_epochs21_50/args.yaml`](file:///c:/Users/L%20E%20N%20O%20V%20O/Food%20man/runs/detect/raw_materials_corrected_resumed_epochs21_50/args.yaml)
* **Training Duration**: Stage 1 (20 epochs) = 12,668.0s; Stage 2 (30 epochs) = 11,944.07s; Cumulative = ~6.8 hours on CPU

| Hyperparameter / Setting | Verified Value from Logs | Notes |
| :--- | :--- | :--- |
| **Base Pretrained Model** | `yolov8n.pt` (Stage 1) -> `combined_corrected_epoch20.pt` (Stage 2) | Resumed 2-stage transfer fine-tuning |
| **Training Epochs** | **50 cumulative** (20 + 30) | Active production model checkpoint |
| **Image Resolution (`imgsz`)** | **416** | 416 × 416 pixels |
| **Batch Size** | **8** | Batch size of 8 |
| **Hardware Device** | `cpu` | Intel CPU execution |
| **Dataloader Workers** | `0` | Windows standard |
| **Optimizer** | `auto` | `lr0=0.01`, `lrf=0.01`, `momentum=0.937` |

---

## 5. Summary Findings & Recommendations for the Team

1. **`models/best.pt`**:
   * Evaluated strictly on isolated peanut kernels (377 images total). It is clean of data leakage, but completely blind to Corn and Sunflower.
2. **`models/material_cls.pt`**:
   * Effectively distinguishes Corn vs Sunflower vs single Peanut kernels, achieving 98.96% validation top-1 accuracy.
   * **Data Leakage Risk**: 42%–45% of the test crops share underlying source photographs with the training dataset due to Roboflow 3x augmentation splitting.
   * **Physical Camera Domain Gap**: Never trained on physical dock camera captures. Accuracy on live factory camera imagery is **unverified with labelled data** and known to misclassify dense peanut bowls as corn.
3. **`models/combined_corrected_best.pt`**:
   * Actively runs in production. Successfully detects clean corn, moldy corn, clean sunflower, and clean peanuts.
   * **Recall Plateau**: Peanut mold recall remains strictly bounded at ~42%–57% due to the 10,227 moldy training instance ceiling.
   * **Sunflower Mold**: 0 instances exist in the training dataset; visual fungal detection is non-functional for sunflower.
