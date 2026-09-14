"""
YOLOv8 Resumed Training Pipeline (Stage 2: Epochs 11-20)
Resumes training from models/combined_best.pt on datasets/raw_materials_combined/data.yaml
Preserves models/best.pt strictly untouched.
"""
import os
import sys
import csv
import shutil
import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_YAML = PROJECT_ROOT / "datasets" / "raw_materials_combined" / "data.yaml"
MODELS_DIR = PROJECT_ROOT / "models"
COMBINED_BEST_MODEL = MODELS_DIR / "combined_best.pt"
EXISTING_BEST_MODEL = MODELS_DIR / "best.pt"
EPOCH10_EVAL_JSON = PROJECT_ROOT / "scratch" / "combined_training_evaluation.json"
OUT_EVAL_JSON = PROJECT_ROOT / "scratch" / "resumed_training_evaluation.json"

def get_file_md5(filepath: Path) -> str:
    if not filepath.exists():
        return "NOT_EXISTS"
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def main():
    print("=" * 80)
    print("YOLOV8 COMBINED RESUMED TRAINING PIPELINE (STAGE 2: EPOCHS 11-20)")
    print("=" * 80)

    # 1. Baseline MD5 checks
    if not COMBINED_BEST_MODEL.exists():
        print(f"ERROR: Base weights not found at {COMBINED_BEST_MODEL}")
        sys.exit(1)
    
    pre_train_best_md5 = get_file_md5(EXISTING_BEST_MODEL)
    pre_train_combined_md5 = get_file_md5(COMBINED_BEST_MODEL)
    print(f"Pre-training models/best.pt MD5          : {pre_train_best_md5}")
    print(f"Pre-training models/combined_best.pt MD5 : {pre_train_combined_md5}")

    from ultralytics import YOLO

    epochs = 10
    batch = 8
    imgsz = 416
    run_name = "raw_materials_combined_resumed_epochs11_20"
    run_dir = PROJECT_ROOT / "runs" / "detect" / run_name

    print(f"\n[STARTING RESUMED TRAINING]")
    print(f"  - Starting Weights : {COMBINED_BEST_MODEL}")
    print(f"  - Dataset          : {DATA_YAML}")
    print(f"  - Additional Epochs: {epochs} (Cumulative Epochs 11-20)")
    print(f"  - Batch size       : {batch}")
    print(f"  - Image size       : {imgsz}")
    print(f"  - Device           : cpu")
    print(f"  - Output Dir       : {run_dir}")

    import gc
    import torch
    torch.set_num_threads(4)
    gc.collect()

    if run_dir.exists():
        print(f"Cleaning previous run dir: {run_dir}")
        shutil.rmtree(run_dir, ignore_errors=True)

    # Load from existing combined_best.pt weights
    model = YOLO(str(COMBINED_BEST_MODEL))
    train_results = model.train(
        data=str(DATA_YAML),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device="cpu",
        name=run_name,
        exist_ok=True,
        workers=0,
        plots=True,
        verbose=True
    )

    save_dir = Path(train_results.save_dir) if hasattr(train_results, "save_dir") else run_dir
    best_weights = save_dir / "weights" / "best.pt"

    print("\n" + "=" * 80)
    print("TRAINING COMPLETED — UPDATING COMBINED WEIGHTS")
    print("=" * 80)

    if not best_weights.exists():
        print(f"ERROR: Could not locate best weights at {best_weights}")
        sys.exit(1)

    # Backup previous combined_best.pt to combined_epoch10_backup.pt
    backup_path = MODELS_DIR / "combined_epoch10_backup.pt"
    shutil.copy2(COMBINED_BEST_MODEL, backup_path)
    print(f"Backed up Epoch 10 weights to: {backup_path}")

    # Update models/combined_best.pt with new best weights
    shutil.copy2(best_weights, COMBINED_BEST_MODEL)
    print(f"Updated models/combined_best.pt with new best weights (Epoch 20)!")

    # Verify models/best.pt integrity
    post_train_best_md5 = get_file_md5(EXISTING_BEST_MODEL)
    print(f"Post-training models/best.pt MD5: {post_train_best_md5}")
    assert pre_train_best_md5 == post_train_best_md5, "CRITICAL ALERT: models/best.pt was modified!"
    print("[VERIFIED] models/best.pt is 100% UNTOUCHED and PRESERVED.")

    # Parse new results.csv
    results_csv = save_dir / "results.csv"
    loss_curves = []
    if results_csv.exists():
        try:
            with open(results_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                field_map = {col: col.strip() for col in reader.fieldnames}
                for row in reader:
                    cleaned = {field_map[k]: v.strip() for k, v in row.items()}
                    ep = int(cleaned.get("epoch", 0)) + 10  # Epochs 11-20
                    loss_curves.append({
                        "epoch": ep,
                        "train_box_loss": round(float(cleaned.get("train/box_loss", 0)), 4),
                        "train_cls_loss": round(float(cleaned.get("train/cls_loss", 0)), 4),
                        "train_dfl_loss": round(float(cleaned.get("train/dfl_loss", 0)), 4),
                        "val_box_loss": round(float(cleaned.get("val/box_loss", 0)), 4),
                        "val_cls_loss": round(float(cleaned.get("val/cls_loss", 0)), 4),
                        "val_dfl_loss": round(float(cleaned.get("val/dfl_loss", 0)), 4),
                        "mAP50": round(float(cleaned.get("metrics/mAP50(B)", 0)), 4),
                        "mAP50_95": round(float(cleaned.get("metrics/mAP50-95(B)", 0)), 4)
                    })
        except Exception as e:
            print(f"Warning reading results.csv: {e}")

    # Evaluate on test split
    print("\n" + "=" * 80)
    print("EVALUATING UPDATED MODEL (EPOCH 20) ON UNSEEN TEST SPLIT")
    print("=" * 80)

    eval_model = YOLO(str(COMBINED_BEST_MODEL))
    test_metrics = eval_model.val(
        data=str(DATA_YAML),
        split="test",
        device="cpu",
        plots=True,
        save_json=True
    )

    box_metrics = test_metrics.box
    names = test_metrics.names
    p_array = box_metrics.p
    r_array = box_metrics.r
    map50_array = box_metrics.ap50
    map_array = box_metrics.ap

    per_class_metrics_ep20 = []
    for cid in range(len(names)):
        cname = names.get(cid, f"Class_{cid}")
        p = round(float(p_array[cid]), 4) if cid < len(p_array) else 0.0
        r = round(float(r_array[cid]), 4) if cid < len(r_array) else 0.0
        ap50 = round(float(map50_array[cid]), 4) if cid < len(map50_array) else 0.0
        ap = round(float(map_array[cid]), 4) if cid < len(map_array) else 0.0
        per_class_metrics_ep20.append({
            "class_id": cid,
            "class_name": cname,
            "precision": p,
            "recall": r,
            "mAP50": ap50,
            "mAP50_95": ap
        })

    # Load Epoch 10 evaluation for side-by-side comparison
    ep10_data = {}
    if EPOCH10_EVAL_JSON.exists():
        try:
            with open(EPOCH10_EVAL_JSON, "r", encoding="utf-8") as f:
                ep10_data = json.load(f)
        except Exception as e:
            print(f"Warning reading Epoch 10 data: {e}")

    ep10_by_class = {c["class_name"]: c for c in ep10_data.get("per_class", [])}

    comparison_table = []
    for c20 in per_class_metrics_ep20:
        cname = c20["class_name"]
        c10 = ep10_by_class.get(cname, {})

        p10 = c10.get("precision", 0.0)
        r10 = c10.get("recall", 0.0)
        m10 = c10.get("mAP50", 0.0)

        p20 = c20["precision"]
        r20 = c20["recall"]
        m20 = c20["mAP50"]

        comparison_table.append({
            "class_name": cname,
            "epoch10": {"precision": p10, "recall": r10, "mAP50": m10},
            "epoch20": {"precision": p20, "recall": r20, "mAP50": m20},
            "delta": {
                "precision": round(p20 - p10, 4),
                "recall": round(r20 - r10, 4),
                "mAP50": round(m20 - m10, 4)
            }
        })

    summary_payload = {
        "overall_epoch20": {
            "mAP50": round(float(box_metrics.map50), 4),
            "mAP50_95": round(float(box_metrics.map), 4),
            "mean_precision": round(float(box_metrics.mp), 4),
            "mean_recall": round(float(box_metrics.mr), 4)
        },
        "per_class_epoch20": per_class_metrics_ep20,
        "comparison_epoch10_vs_epoch20": comparison_table,
        "loss_curves_stage2": loss_curves,
        "speed": test_metrics.speed
    }

    with open(OUT_EVAL_JSON, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)
    print(f"\nSaved Epoch 20 evaluation & comparison to {OUT_EVAL_JSON}")

    # Print Formatted Report
    print("\n" + "=" * 90)
    print("COMPARISON REPORT: EPOCH 10 vs EPOCH 20 (UNSEEN TEST SPLIT)")
    print("=" * 90)
    print(f"{'Class Name':<22} | {'Metric':<10} | {'Epoch 10':<10} | {'Epoch 20':<10} | {'Change (Delta)':<15}")
    print("-" * 90)
    for comp in comparison_table:
        cname = comp["class_name"]
        e10 = comp["epoch10"]
        e20 = comp["epoch20"]
        d = comp["delta"]
        
        r_sign = "+" if d["recall"] >= 0 else ""
        m_sign = "+" if d["mAP50"] >= 0 else ""
        p_sign = "+" if d["precision"] >= 0 else ""

        print(f"{cname:<22} | Recall     | {e10['recall']*100:>8.1f}% | {e20['recall']*100:>8.1f}% | {r_sign}{d['recall']*100:>+7.1f}%")
        print(f"{'':<22} | Precision  | {e10['precision']*100:>8.1f}% | {e20['precision']*100:>8.1f}% | {p_sign}{d['precision']*100:>+7.1f}%")
        print(f"{'':<22} | mAP@50     | {e10['mAP50']*100:>8.1f}% | {e20['mAP50']*100:>8.1f}% | {m_sign}{d['mAP50']*100:>+7.1f}%")
        print("-" * 90)

    # Highlight Peanut_Moldy Recall
    pm = next((c for c in comparison_table if c["class_name"] == "Peanut_Moldy"), None)
    if pm:
        print(f"\n>>> PEANUT_MOLDY RECALL FOCUS:")
        print(f"    Epoch 10 Recall : {pm['epoch10']['recall']*100:.1f}%")
        print(f"    Epoch 20 Recall : {pm['epoch20']['recall']*100:.1f}%")
        delta = pm['delta']['recall'] * 100
        direction = "IMPROVED" if delta > 0 else ("UNCHANGED" if delta == 0 else "DECREASED")
        print(f"    Delta           : {delta:+.1f}% ({direction})")
    print("=" * 90)

if __name__ == "__main__":
    main()
