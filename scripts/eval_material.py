"""
Material Identification Accuracy & Confusion Matrix Evaluation Script
Evaluates the CURRENT live pipeline against test sets and saved live frames.
Uses the EXACT same detection, material voting, and lock logic as the running application.

Usage:
    # 1. Evaluate directory where subfolders are material names:
    python scripts/eval_material.py --dir path/to/dataset

    # 2. Evaluate YOLO test dataset (deriving ground truth from label txt files):
    python scripts/eval_material.py --dataset datasets/raw_materials_combined/images/test

    # 3. Evaluate saved live inspection frames from database:
    python scripts/eval_material.py --live-frames
"""
import os
import sys
import argparse
import time
import json
from collections import defaultdict, Counter

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.yolo_service import run_yolo_visual_inspection, find_trained_model
from routes.qc import extract_material_name, get_mostly_detected_material


# Canonical mapping for YOLO combined dataset class IDs
# 0: Peanut_Moldy, 1: Peanut_Not_Moldy, 2: Corn_Moldy, 3: Corn_Not_Moldy, 4: Sunflower_Moldy, 5: Sunflower_Not_Moldy
CLASS_TO_MATERIAL = {
    0: "Peanut",
    1: "Peanut",
    2: "Corn",
    3: "Corn",
    4: "Sunflower",
    5: "Sunflower"
}


def derive_material_from_yolo_label(label_path: str) -> str:
    """Reads a YOLO label .txt file and determines the true material."""
    if not os.path.isfile(label_path):
        return None
    mats = set()
    with open(label_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                try:
                    cls_id = int(parts[0])
                    if cls_id in CLASS_TO_MATERIAL:
                        mats.add(CLASS_TO_MATERIAL[cls_id])
                except ValueError:
                    pass
    if len(mats) == 1:
        return list(mats)[0]
    elif len(mats) > 1:
        return "Mixed"
    return None


def derive_material_from_filename(filename: str) -> str:
    """Extracts canonical material name from filename keywords."""
    f = filename.lower()
    if "peanut" in f or "groundnut" in f:
        return "Peanut"
    if "corn" in f or "maize" in f:
        return "Corn"
    if "sunflower" in f:
        return "Sunflower"
    return None


def run_lock_logic_for_detections(yolo_res: dict) -> tuple:
    """
    Simulates the lock logic from routes/qc.py:evaluate_locked_frames
    on the detections of a photo.
    Returns (winner_mat, winner_ratio, is_mixed)
    """
    mat_conf_totals = defaultdict(float)
    for d in yolo_res.get("detected_defects", []):
        mat = extract_material_name(d.get("defect_class", ""))
        conf = float(d.get("confidence", 0.0))
        if mat:
            mat_conf_totals[mat] += conf
    for h in yolo_res.get("detected_healthy", []):
        mat = extract_material_name(h.get("specimen_class") or h.get("defect_class", ""))
        conf = float(h.get("confidence", 0.0))
        if mat:
            mat_conf_totals[mat] += conf

    total_conf = sum(mat_conf_totals.values())
    if total_conf > 0:
        winner_mat = max(mat_conf_totals, key=mat_conf_totals.get)
        winner_conf = mat_conf_totals[winner_mat]
        winner_ratio = winner_conf / total_conf
    else:
        winner_mat = "None"
        winner_ratio = 0.0

    # From routes/qc.py:1758: winner_ratio < 0.60 -> "Mixed / uncertain material"
    is_mixed = (winner_ratio < 0.60 or winner_mat == "None")
    lock_pred = "Mixed / uncertain material" if is_mixed else winner_mat
    return lock_pred, winner_ratio, is_mixed


def evaluate_items(item_list: list, title: str):
    """
    Evaluates a list of items: dict(path=..., true_material=..., [optional session_id=...])
    Runs detection, material voting, and lock logic, then prints report and confusion matrix.
    """
    print(f"\n{'='*70}")
    print(f"RUNNING MATERIAL IDENTIFICATION EVALUATION: {title}")
    print(f"Total samples to evaluate: {len(item_list)}")
    model_path, model_name = find_trained_model()
    print(f"Active Model: {model_name} ({model_path})")
    print(f"{'='*70}\n")

    results = []
    start_time = time.time()

    # Track overall and per-material counts
    confusion = defaultdict(lambda: Counter())
    materials_seen = set()
    pred_materials_seen = set()

    for idx, item in enumerate(item_list, 1):
        img_path = item["path"]
        true_mat = item["true_material"]
        materials_seen.add(true_mat)

        # 1. Run live detection
        t0 = time.time()
        yolo_res = run_yolo_visual_inspection(img_path)
        infer_ms = (time.time() - t0) * 1000

        # 2. Run live material voting
        pred_mat = get_mostly_detected_material(yolo_res)
        pred_label = pred_mat if pred_mat else "None / Undetected"
        pred_materials_seen.add(pred_label)

        # 3. Run live lock logic
        lock_pred, winner_ratio, is_mixed = run_lock_logic_for_detections(yolo_res)

        # Detection breakdown
        defects = yolo_res.get("detected_defects", [])
        healthy = yolo_res.get("detected_healthy", [])
        total_boxes = len(defects) + len(healthy)

        # Record confusion
        confusion[true_mat][pred_label] += 1
        is_correct = (pred_mat == true_mat)

        results.append({
            "idx": idx,
            "filename": os.path.basename(img_path),
            "path": img_path,
            "true_material": true_mat,
            "predicted_material": pred_label,
            "is_correct": is_correct,
            "lock_prediction": lock_pred,
            "winner_ratio": winner_ratio,
            "is_mixed": is_mixed,
            "infer_ms": infer_ms,
            "total_boxes": total_boxes,
            "defects_count": len(defects),
            "healthy_count": len(healthy),
            "defects": defects,
            "healthy": healthy
        })

        if idx % 25 == 0 or idx == len(item_list):
            print(f"  Processed {idx}/{len(item_list)} images (elapsed: {time.time()-start_time:.1f}s)...")

    total_time = time.time() - start_time
    avg_fps = len(item_list) / total_time if total_time > 0 else 0

    # 4. Generate Report
    print(f"\n{'-'*70}")
    print(f"EVALUATION SUMMARY: {title}")
    print(f"Total Images: {len(item_list)} | Total Time: {total_time:.1f}s | Avg Speed: {avg_fps:.1f} img/s")
    print(f"{'-'*70}\n")

    # Accuracy per true material
    print("ACCURACY PER MATERIAL:")
    print(f"{'Material':<16} | {'Total':<8} | {'Correct':<8} | {'Wrong':<8} | {'Accuracy':<10}")
    print(f"{'-'*16}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*10}")

    total_correct = 0
    total_samples = len(item_list)

    sorted_mats = sorted(list(materials_seen))
    for mat in sorted_mats:
        mat_total = sum(confusion[mat].values())
        mat_correct = confusion[mat][mat]
        mat_wrong = mat_total - mat_correct
        total_correct += mat_correct
        acc_pct = (mat_correct / mat_total * 100.0) if mat_total > 0 else 0.0
        print(f"{mat:<16} | {mat_total:<8} | {mat_correct:<8} | {mat_wrong:<8} | {acc_pct:>8.2f}%")

    overall_acc = (total_correct / total_samples * 100.0) if total_samples > 0 else 0.0
    print(f"{'-'*16}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*10}")
    print(f"{'OVERALL':<16} | {total_samples:<8} | {total_correct:<8} | {total_samples - total_correct:<8} | {overall_acc:>8.2f}%\n")

    # 5. Confusion Matrix Table
    # Rows: True, Columns: Predicted
    all_cols = sorted(list(set(sorted_mats + list(pred_materials_seen))))
    print("CONFUSION MATRIX (Rows: True Material -> Columns: Predicted Material):")
    header_str = f"{'True \\ Pred':<16} | " + " | ".join(f"{c:>16}" for c in all_cols)
    print(header_str)
    print("-" * len(header_str))
    for mat in sorted_mats:
        row_str = f"{mat:<16} | " + " | ".join(f"{confusion[mat][c]:>16}" for c in all_cols)
        print(row_str)
    print("-" * len(header_str))

    # 6. List Every Wrong Photo
    wrong_items = [r for r in results if not r["is_correct"]]
    print(f"\n{'-'*70}")
    print(f"WRONG PREDICTIONS LIST ({len(wrong_items)} / {len(results)} failed):")
    print(f"{'-'*70}")
    if not wrong_items:
        print("  [PERFECT] No errors! All photos were correctly classified.")
    else:
        for idx, w in enumerate(wrong_items, 1):
            print(f"\n[{idx}] File: {w['filename']}")
            print(f"    Path: {w['path']}")
            print(f"    True Material:      {w['true_material']}")
            print(f"    Predicted Material: {w['predicted_material']} (Lock: {w['lock_prediction']} ratio={w['winner_ratio']:.2f})")
            print(f"    Detections:         Total={w['total_boxes']} (Defects={w['defects_count']}, Healthy={w['healthy_count']})")
            # Print sample classes detected
            detected_classes = Counter()
            for d in w['defects']:
                detected_classes[d.get('defect_class', 'Defect')] += 1
            for h in w['healthy']:
                detected_classes[h.get('specimen_class', 'Healthy')] += 1
            print(f"    Class Breakdown:    {dict(detected_classes)}")

    print(f"\n{'='*70}\n")
    return {
        "title": title,
        "total_samples": total_samples,
        "total_correct": total_correct,
        "overall_accuracy": round(overall_acc, 2),
        "per_material": {
            mat: {
                "total": sum(confusion[mat].values()),
                "correct": confusion[mat][mat],
                "accuracy": round((confusion[mat][mat] / sum(confusion[mat].values()) * 100.0), 2) if sum(confusion[mat].values()) > 0 else 0.0
            }
            for mat in sorted_mats
        },
        "wrong_count": len(wrong_items),
        "wrong_items": wrong_items
    }


def collect_from_folder_structure(root_dir: str) -> list:
    """
    Collects photos where each subfolder name is the true material:
    e.g. root_dir/Peanut/1.jpg, root_dir/Corn/2.jpg
    """
    items = []
    if not os.path.isdir(root_dir):
        return items

    for entry in os.listdir(root_dir):
        sub_path = os.path.join(root_dir, entry)
        if os.path.isdir(sub_path):
            mat_name = extract_material_name(entry) or entry
            for fname in os.listdir(sub_path):
                ext = os.path.splitext(fname)[1].lower()
                if ext in ('.jpg', '.jpeg', '.png', '.webp'):
                    items.append({
                        "path": os.path.join(sub_path, fname),
                        "true_material": mat_name
                    })
    return items


def collect_from_dataset_test(dataset_test_dir: str) -> list:
    """
    Collects photos from datasets/raw_materials_combined/images/test,
    deriving ground truth from the corresponding labels/test directory.
    """
    items = []
    if not os.path.isdir(dataset_test_dir):
        return items

    # Derive labels dir
    labels_dir = dataset_test_dir.replace("images" + os.sep + "test", "labels" + os.sep + "test")
    if not os.path.isdir(labels_dir):
        # Try alternate path manipulation
        labels_dir = os.path.abspath(os.path.join(dataset_test_dir, "..", "..", "labels", "test"))

    for fname in sorted(os.listdir(dataset_test_dir)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.webp'):
            base = os.path.splitext(fname)[0]
            label_file = os.path.join(labels_dir, base + ".txt")
            true_mat = derive_material_from_yolo_label(label_file)
            if not true_mat:
                true_mat = derive_material_from_filename(fname)
            if true_mat:
                items.append({
                    "path": os.path.join(dataset_test_dir, fname),
                    "true_material": true_mat
                })
    return items


def collect_from_saved_live_frames(db_path: str = "food_man.db") -> list:
    """
    Collects saved live frames from the SQLite database where the linked lot
    identifies the true material.
    """
    import sqlite3
    items = []
    if not os.path.isfile(db_path):
        return items

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        SELECT lf.id, lf.session_id, ls.lot_id, rml.material_name, lf.image_path, lf.is_locked
        FROM live_frames lf
        JOIN live_sessions ls ON lf.session_id = ls.id
        JOIN raw_material_lots rml ON ls.lot_id = rml.id
    ''')
    rows = c.fetchall()
    conn.close()

    for r in rows:
        f_id, s_id, lot_id, mat_name, img_path, is_locked = r
        clean_rel = img_path.lstrip('/')
        disk_path = os.path.join(PROJECT_ROOT, clean_rel)
        if os.path.isfile(disk_path):
            true_mat = extract_material_name(mat_name)
            if true_mat:
                items.append({
                    "path": disk_path,
                    "true_material": true_mat,
                    "session_id": s_id,
                    "frame_id": f_id,
                    "is_locked": bool(is_locked)
                })

    # Also check static/uploads/raw for any live dock/camera test images with material in name
    raw_dir = os.path.join(PROJECT_ROOT, 'static', 'uploads', 'raw')
    if os.path.isdir(raw_dir):
        for f in sorted(os.listdir(raw_dir)):
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.jpg', '.jpeg', '.png', '.webp') and "_infer_" not in f:
                true_mat = derive_material_from_filename(f)
                if true_mat:
                    items.append({
                        "path": os.path.join(raw_dir, f),
                        "true_material": true_mat,
                        "session_id": None,
                        "frame_id": None,
                        "is_locked": False
                    })

    return items


def main():
    parser = argparse.ArgumentParser(description="Evaluate material identification accuracy on photos.")
    parser.add_argument("--dir", type=str, help="Path to directory containing material subfolders or images.")
    parser.add_argument("--dataset", type=str, default="datasets/raw_materials_combined/images/test", help="Path to YOLO test images directory.")
    parser.add_argument("--live-frames", action="store_true", help="Evaluate saved live frames from database and upload directories.")
    parser.add_argument("--all", action="store_true", help="Run on both dataset test images and live frames.")

    args = parser.parse_args()

    # If no flags specified, default to running on both test set and live frames
    run_all = args.all or (not args.dir and not args.live_frames and args.dataset)

    reports = []

    if args.dir:
        items = collect_from_folder_structure(args.dir)
        if not items:
            # Fallback to test label derivation if flat
            items = collect_from_dataset_test(args.dir)
        if not items:
            print(f"Error: No valid image files with material ground truth found in {args.dir}")
            sys.exit(1)
        rep = evaluate_items(items, f"Custom Directory: {args.dir}")
        reports.append(rep)

    if run_all or (args.dataset and not args.dir):
        test_path = os.path.abspath(os.path.join(PROJECT_ROOT, args.dataset))
        test_items = collect_from_dataset_test(test_path)
        if test_items:
            rep = evaluate_items(test_items, f"YOLO Test Set ({args.dataset})")
            reports.append(rep)
        else:
            print(f"Warning: No test images found at {test_path}")

    if run_all or args.live_frames:
        live_items = collect_from_saved_live_frames()
        if live_items:
            rep = evaluate_items(live_items, "Saved Live Frames & Camera Captures")
            reports.append(rep)
        else:
            print("Warning: No live frames with ground truth found.")


if __name__ == "__main__":
    main()
