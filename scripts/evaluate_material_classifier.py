"""
Evaluate Material Classifier (models/material_cls.pt)
Phase 2 - Step 3: Comprehensive Multi-Level Evaluation

Evaluates:
(a) Per kernel on existing test crops (datasets_synth/crops/test/<material>/)
(b) Per scene on synthetic test scenes (datasets_synth/images/test/) via majority vote of classified kernels
(c) Per photo on existing test photos (datasets/raw_materials_combined/images/test/) using live detector + classifier

GATE Criteria:
- At least 97% per kernel for every material
- At least 95% per scene for every material
- At least 95% per photo for every material
"""

import os
import sys
import glob
import time
from collections import defaultdict, Counter
import cv2
import numpy as np
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.eval_material import derive_material_from_yolo_label, derive_material_from_filename
from ai.yolo_service import find_trained_model

MODEL_CLS_PATH = os.path.join(PROJECT_ROOT, 'models', 'material_cls.pt')
_active_det_path, _ = find_trained_model()
MODEL_DET_PATH = _active_det_path if _active_det_path else os.path.join(PROJECT_ROOT, 'models', 'best.pt')

TEST_CROPS_ROOT = os.path.join(PROJECT_ROOT, 'datasets_synth', 'crops', 'test')
SYNTH_TEST_IMG_DIR = os.path.join(PROJECT_ROOT, 'datasets_synth', 'images', 'test')
SYNTH_TEST_LBL_DIR = os.path.join(PROJECT_ROOT, 'datasets_synth', 'labels', 'test')
RAW_TEST_IMG_DIR = os.path.join(PROJECT_ROOT, 'datasets', 'raw_materials_combined', 'images', 'test')
RAW_TEST_LBL_DIR = os.path.join(PROJECT_ROOT, 'datasets', 'raw_materials_combined', 'labels', 'test')

MATERIALS = ['peanut', 'corn', 'sunflower']


def print_confusion_matrix(title: str, confusion: dict, materials: list):
    """Prints a formatted confusion matrix table and per-material accuracy."""
    print(f"\n{'-'*75}")
    print(f"{title.upper()} - CONFUSION MATRIX & ACCURACY")
    print(f"{'-'*75}")

    all_pred_cols = sorted(list(set(materials + [c for mat in materials for c in confusion[mat].keys()])))

    header_str = f"{'True \\ Pred':<14} | " + " | ".join(f"{c.capitalize():>12}" for c in all_pred_cols) + f" | {'Total':>8} | {'Accuracy':>10}"
    print(header_str)
    print("-" * len(header_str))

    total_correct = 0
    total_samples = 0
    acc_by_mat = {}

    for mat in materials:
        row_total = sum(confusion[mat].values())
        correct = confusion[mat][mat]
        total_correct += correct
        total_samples += row_total
        acc = (correct / row_total * 100.0) if row_total > 0 else 0.0
        acc_by_mat[mat] = acc

        cells = " | ".join(f"{confusion[mat][c]:>12}" for c in all_pred_cols)
        print(f"{mat.capitalize():<14} | {cells} | {row_total:>8} | {acc:>9.2f}%")

    print("-" * len(header_str))
    overall_acc = (total_correct / total_samples * 100.0) if total_samples > 0 else 0.0
    print(f"{'OVERALL':<14} | {'':>{len(all_pred_cols)*15 - 3}} | {total_samples:>8} | {overall_acc:>9.2f}%")
    print(f"{'-'*75}\n")
    return acc_by_mat, overall_acc


def evaluate_test_crops(cls_model: YOLO):
    """
    (a) Per kernel on the existing test crops:
    datasets_synth/crops/test/{peanut,corn,sunflower}/*.png
    """
    print("\n" + "=" * 75)
    print("(A) EVALUATION: PER KERNEL ON EXISTING TEST CROPS")
    print(f"Source Directory: {TEST_CROPS_ROOT}")
    print("=" * 75)

    confusion = defaultdict(Counter)
    wrong_crops = []
    total_crops = 0

    t0 = time.time()

    for material in MATERIALS:
        mat_dir = os.path.join(TEST_CROPS_ROOT, material)
        files = sorted(glob.glob(os.path.join(mat_dir, '*.png')))
        total_crops += len(files)
        print(f"  Evaluating {len(files)} {material} test crops...")

        # Batch inference for speed
        batch_size = 64
        for i in range(0, len(files), batch_size):
            batch_files = files[i:i + batch_size]
            results = cls_model(batch_files, verbose=False, imgsz=96)
            for fpath, r in zip(batch_files, results):
                pred_idx = r.probs.top1
                pred_name = r.names[pred_idx].lower()
                confusion[material][pred_name] += 1

                if pred_name != material:
                    conf = float(r.probs.top1conf)
                    wrong_crops.append({
                        "file": os.path.basename(fpath),
                        "true": material,
                        "predicted": pred_name,
                        "confidence": conf
                    })

    dt = time.time() - t0
    acc_by_mat, overall_acc = print_confusion_matrix("Per-Kernel Test Crops", confusion, MATERIALS)
    print(f"Evaluated {total_crops} test crops in {dt:.2f}s ({total_crops/dt:.1f} crops/s).")

    if wrong_crops:
        print(f"Wrong Crops ({len(wrong_crops)}):")
        for w in wrong_crops[:15]:
            print(f"  - {w['file']}: True={w['true']}, Pred={w['predicted']} (conf={w['confidence']:.2f})")
        if len(wrong_crops) > 15:
            print(f"  ... and {len(wrong_crops)-15} more.")

    return acc_by_mat, wrong_crops


def evaluate_synthetic_test_scenes(cls_model: YOLO):
    """
    (b) Per scene on the synthetic test scenes (classify every kernel, majority vote).
    datasets_synth/images/test/*.jpg
    """
    print("\n" + "=" * 75)
    print("(B) EVALUATION: PER SCENE ON SYNTHETIC TEST SCENES (MAJORITY VOTE)")
    print(f"Source Directory: {SYNTH_TEST_IMG_DIR}")
    print("=" * 75)

    scene_files = sorted(glob.glob(os.path.join(SYNTH_TEST_IMG_DIR, '*.jpg')))
    confusion = defaultdict(Counter)
    wrong_scenes = []

    t0 = time.time()

    for s_path in scene_files:
        base = os.path.splitext(os.path.basename(s_path))[0]
        # True material from filename: synth_<mat>_test_xxxx
        parts = base.split('_')
        true_mat = parts[1].lower() if len(parts) >= 2 else None
        if true_mat not in MATERIALS:
            continue

        lbl_path = os.path.join(SYNTH_TEST_LBL_DIR, f"{base}.txt")
        if not os.path.exists(lbl_path):
            continue

        img = cv2.imread(s_path)
        if img is None:
            continue
        H, W = img.shape[:2]

        kernel_crops = []
        with open(lbl_path, 'r', encoding='utf-8') as lf:
            for line in lf:
                p = line.strip().split()
                if len(p) < 5:
                    continue
                xc, yc, bw, bh = [float(v) for v in p[1:5]]
                x1 = max(0, int(round((xc - bw / 2.0) * W)))
                y1 = max(0, int(round((yc - bh / 2.0) * H)))
                x2 = min(W, int(round((xc + bw / 2.0) * W)))
                y2 = min(H, int(round((yc + bh / 2.0) * H)))

                crop = img[y1:y2, x1:x2]
                if crop.size > 0:
                    kernel_crops.append(crop)

        if not kernel_crops:
            continue

        # Classify all kernels in this scene
        res = cls_model(kernel_crops, verbose=False, imgsz=96)
        votes = Counter()
        for r in res:
            p_name = r.names[r.probs.top1].lower()
            votes[p_name] += 1

        winner_mat = votes.most_common(1)[0][0]
        confusion[true_mat][winner_mat] += 1

        if winner_mat != true_mat:
            wrong_scenes.append({
                "scene": base,
                "true": true_mat,
                "predicted": winner_mat,
                "votes": dict(votes),
                "total_kernels": len(kernel_crops)
            })

    dt = time.time() - t0
    acc_by_mat, overall_acc = print_confusion_matrix("Per-Scene Synthetic Test", confusion, MATERIALS)
    print(f"Evaluated {len(scene_files)} synthetic scenes in {dt:.2f}s ({len(scene_files)/dt:.1f} scenes/s).")

    if wrong_scenes:
        print(f"Wrong Scenes ({len(wrong_scenes)}):")
        for ws in wrong_scenes:
            print(f"  - {ws['scene']}: True={ws['true']}, Pred={ws['predicted']}, Votes={ws['votes']}")
    else:
        print("  [PERFECT] All synthetic test scenes correctly classified via majority vote!")

    return acc_by_mat, wrong_scenes


def evaluate_test_photos_pipeline(cls_model: YOLO, det_model: YOLO):
    """
    (c) Per photo on the existing test photos, using the full live pipeline
    with the material classifier plugged in.
    datasets/raw_materials_combined/images/test/*.jpg
    """
    print("\n" + "=" * 75)
    print("(C) EVALUATION: PER PHOTO ON EXISTING TEST PHOTOS (LIVE PIPELINE + CLASSIFIER)")
    print(f"Source Directory: {RAW_TEST_IMG_DIR}")
    print("=" * 75)

    photo_files = sorted(glob.glob(os.path.join(RAW_TEST_IMG_DIR, '*.jpg')) +
                         glob.glob(os.path.join(RAW_TEST_IMG_DIR, '*.png')))

    confusion = defaultdict(Counter)
    wrong_photos = []

    t0 = time.time()

    for p_path in photo_files:
        base = os.path.splitext(os.path.basename(p_path))[0]
        lbl_path = os.path.join(RAW_TEST_LBL_DIR, f"{base}.txt")

        # Ground truth
        true_mat_str = derive_material_from_yolo_label(lbl_path)
        if not true_mat_str:
            true_mat_str = derive_material_from_filename(os.path.basename(p_path))
        if not true_mat_str:
            continue

        true_mat = true_mat_str.lower()
        if true_mat not in MATERIALS:
            continue

        img = cv2.imread(p_path)
        if img is None:
            continue
        H, W = img.shape[:2]

        # 1. Run live detector to find kernels (conf=0.12 standard live threshold)
        det_res = det_model(img, verbose=False, conf=0.12)
        boxes = det_res[0].boxes if det_res else []

        # If zero boxes found at default threshold (e.g. dark or low-contrast kernels), retry with low threshold
        if len(boxes) == 0:
            det_res_low = det_model(img, verbose=False, conf=0.05)
            boxes = det_res_low[0].boxes if det_res_low else []

        # Tally detector votes
        det_votes = Counter()
        for b in boxes:
            cls_name = det_res[0].names[int(b.cls[0].item())].lower()
            if 'peanut' in cls_name: det_votes['peanut'] += 1
            elif 'corn' in cls_name: det_votes['corn'] += 1
            elif 'sunflower' in cls_name: det_votes['sunflower'] += 1

        detected_crops = []
        if len(boxes) > 0:
            for b in boxes:
                xyxy = b.xyxy[0].cpu().numpy()
                x1 = max(0, int(round(xyxy[0])))
                y1 = max(0, int(round(xyxy[1])))
                x2 = min(W, int(round(xyxy[2])))
                y2 = min(H, int(round(xyxy[3])))
                crop = img[y1:y2, x1:x2]
                if crop.size > 0:
                    detected_crops.append(crop)

        # 2. Classify detected kernels with material classifier
        cls_votes = Counter()
        if detected_crops:
            cls_res = cls_model(detected_crops, verbose=False, imgsz=96)
            for r in cls_res:
                p_name = r.names[r.probs.top1].lower()
                cls_votes[p_name] += 1
        else:
            # Fallback: classify center crop / whole image
            ch, cw = int(H * 0.7), int(W * 0.7)
            cy1, cx1 = (H - ch) // 2, (W - cw) // 2
            center_crop = img[cy1:cy1+ch, cx1:cx1+cw]
            fallback_res = cls_model(center_crop if center_crop.size > 0 else img, verbose=False, imgsz=96)
            p_name = fallback_res[0].names[fallback_res[0].probs.top1].lower()
            cls_votes[p_name] += 1

        # 3. Ensemble voting: detector votes + classifier votes
        combined_votes = Counter()
        for m in MATERIALS:
            combined_votes[m] = det_votes[m] + cls_votes[m]

        pred_mat = combined_votes.most_common(1)[0][0] if combined_votes else "none"

        confusion[true_mat][pred_mat] += 1

        if pred_mat != true_mat:
            wrong_photos.append({
                "photo": os.path.basename(p_path),
                "true": true_mat,
                "predicted": pred_mat,
                "boxes_detected": len(detected_crops),
                "votes": dict(combined_votes)
            })

    dt = time.time() - t0
    acc_by_mat, overall_acc = print_confusion_matrix("Per-Photo Test Set (Pipeline + Classifier)", confusion, MATERIALS)
    print(f"Evaluated {len(photo_files)} test photos in {dt:.2f}s ({len(photo_files)/dt:.1f} photos/s).")

    if wrong_photos:
        print(f"Wrong Photos ({len(wrong_photos)}):")
        for wp in wrong_photos:
            print(f"  - {wp['photo']}: True={wp['true']}, Pred={wp['predicted']}, Boxes={wp['boxes_detected']}, Votes={wp['votes']}")
    else:
        print("  [PERFECT] All test photos correctly identified!")

    return acc_by_mat, wrong_photos


def main():
    print("=" * 75)
    print("PHASE 2 EVALUATION SUITE: MATERIAL CLASSIFIER")
    print(f"Classifier Model: {MODEL_CLS_PATH}")
    print(f"Detector Model:   {MODEL_DET_PATH}")
    print("=" * 75)

    if not os.path.exists(MODEL_CLS_PATH):
        print(f"Error: Classifier model not found at {MODEL_CLS_PATH}!")
        sys.exit(1)

    cls_model = YOLO(MODEL_CLS_PATH)
    det_model = YOLO(MODEL_DET_PATH)

    # (a) Per-kernel on existing test crops
    crops_acc, wrong_crops = evaluate_test_crops(cls_model)

    # (b) Per-scene on synthetic test scenes
    scenes_acc, wrong_scenes = evaluate_synthetic_test_scenes(cls_model)

    # (c) Per-photo on existing test photos (live pipeline + classifier)
    photos_acc, wrong_photos = evaluate_test_photos_pipeline(cls_model, det_model)

    # GATE VERIFICATION
    print("\n" + "=" * 75)
    print("PHASE 2 GATE VERIFICATION SUMMARY")
    print("=" * 75)
    print(f"{'Evaluation Scope':<32} | {'Peanut':<10} | {'Corn':<10} | {'Sunflower':<10} | {'Gate Target':<12} | {'Status'}")
    print("-" * 32 + "-+-" + "-" * 10 + "-+-" + "-" * 10 + "-+-" + "-" * 10 + "-+-" + "-" * 12 + "-+-" + "-" * 8)

    # Checks
    gate_passed = True

    # 1. Per-kernel
    k_p, k_c, k_s = crops_acc.get('peanut', 0), crops_acc.get('corn', 0), crops_acc.get('sunflower', 0)
    k_pass = (k_p >= 97.0 and k_c >= 97.0 and k_s >= 97.0)
    if not k_pass:
        gate_passed = False
    print(f"{'(a) Per-Kernel Test Crops':<32} | {k_p:>9.2f}% | {k_c:>9.2f}% | {k_s:>9.2f}% | {'>= 97.0%':<12} | {'[PASS]' if k_pass else '[FAIL]'}")

    # 2. Per-scene
    s_p, s_c, s_s = scenes_acc.get('peanut', 0), scenes_acc.get('corn', 0), scenes_acc.get('sunflower', 0)
    s_pass = (s_p >= 95.0 and s_c >= 95.0 and s_s >= 95.0)
    if not s_pass:
        gate_passed = False
    print(f"{'(b) Per-Scene Synthetic Tests':<32} | {s_p:>9.2f}% | {s_c:>9.2f}% | {s_s:>9.2f}% | {'>= 95.0%':<12} | {'[PASS]' if s_pass else '[FAIL]'}")

    # 3. Per-photo
    p_p, p_c, p_s = photos_acc.get('peanut', 0), photos_acc.get('corn', 0), photos_acc.get('sunflower', 0)
    p_pass = (p_p >= 95.0 and p_c >= 95.0 and p_s >= 95.0)
    if not p_pass:
        gate_passed = False
    print(f"{'(c) Per-Photo Test Pipeline':<32} | {p_p:>9.2f}% | {p_c:>9.2f}% | {p_s:>9.2f}% | {'>= 95.0%':<12} | {'[PASS]' if p_pass else '[FAIL]'}")

    print("-" * 32 + "-+-" + "-" * 10 + "-+-" + "-" * 10 + "-+-" + "-" * 10 + "-+-" + "-" * 12 + "-+-" + "-" * 8)
    overall_status = "GATE PASSED" if gate_passed else "GATE FAILED"
    print(f"FINAL DECISION: {overall_status}")
    print("=" * 75 + "\n")

    return {
        "gate_passed": gate_passed,
        "crops_acc": crops_acc,
        "scenes_acc": scenes_acc,
        "photos_acc": photos_acc,
        "wrong_crops_count": len(wrong_crops),
        "wrong_scenes_count": len(wrong_scenes),
        "wrong_photos_count": len(wrong_photos)
    }


if __name__ == '__main__':
    main()
