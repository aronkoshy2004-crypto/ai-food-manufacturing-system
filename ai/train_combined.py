"""
YOLOv8 Combined Multi-Commodity Raw Material Training Pipeline
Food Manufacturing System — AI Quality Control Module

Trains on datasets/raw_materials_combined/data.yaml (6 classes):
0: Peanut_Moldy
1: Peanut_Not_Moldy
2: Corn_Moldy
3: Corn_Not_Moldy
4: Sunflower_Moldy
5: Sunflower_Not_Moldy

Saves best weights to models/combined_best.pt (strictly preserving models/best.pt).
Evaluates test split with per-class precision, recall, mAP, confusion matrix,
loss curves summary, and sample predictions.
Supports resuming from checkpoint (runs/detect/raw_materials_combined_yolov8/weights/last.pt).
"""
import os
import sys
import csv
import shutil
import hashlib
import json
from pathlib import Path
import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_YAML = PROJECT_ROOT / "datasets" / "raw_materials_combined" / "data.yaml"
MODELS_DIR = PROJECT_ROOT / "models"
SAVED_COMBINED_MODEL = MODELS_DIR / "combined_best.pt"
EXISTING_BEST_MODEL = MODELS_DIR / "best.pt"

TARGET_CLASSES = {
    0: "Peanut_Moldy",
    1: "Peanut_Not_Moldy",
    2: "Corn_Moldy",
    3: "Corn_Not_Moldy",
    4: "Sunflower_Moldy",
    5: "Sunflower_Not_Moldy"
}

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
    print("YOLOV8 COMBINED RAW MATERIALS TRAINING PIPELINE")
    print("=" * 80)
    
    # Baseline md5 of existing best.pt
    pre_train_best_md5 = get_file_md5(EXISTING_BEST_MODEL)
    print(f"Pre-training models/best.pt MD5: {pre_train_best_md5}")

    from ultralytics import YOLO

    epochs = 10
    batch = 8
    imgsz = 416
    run_name = "raw_materials_combined_yolov8"
    run_dir = PROJECT_ROOT / "runs" / "detect" / run_name
    checkpoint_last = run_dir / "weights" / "last.pt"

    # Check for resumable checkpoint
    if checkpoint_last.exists():
        print(f"\n[RESUME DETECTED] Found checkpoint at: {checkpoint_last}")
        print("Resuming training from checkpoint with resume=True...")
        model = YOLO(str(checkpoint_last))
        train_results = model.train(resume=True)
    else:
        print(f"\n[CLEAN START] No previous checkpoint found at {checkpoint_last}.")
        print("Starting 10-epoch training run from scratch using yolov8n.pt...")
        print(f"  - Dataset   : {DATA_YAML}")
        print(f"  - Model     : yolov8n.pt")
        print(f"  - Epochs    : {epochs}")
        print(f"  - Batch size: {batch}")
        print(f"  - Image size: {imgsz}")
        print(f"  - Device    : cpu")
        print(f"  - Output    : {run_dir}")
        print(f"  - Target    : {SAVED_COMBINED_MODEL}")

        model = YOLO("yolov8n.pt")
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
    print("TRAINING COMPLETED — DEPLOYING MODEL WEIGHTS")
    print("=" * 80)

    if not best_weights.exists():
        print(f"ERROR: Could not locate best weights at {best_weights}")
        sys.exit(1)

    # Save exclusively to models/combined_best.pt
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_weights, SAVED_COMBINED_MODEL)
    print(f"Exported combined model weights to: {SAVED_COMBINED_MODEL}")

    # Verify existing models/best.pt integrity
    post_train_best_md5 = get_file_md5(EXISTING_BEST_MODEL)
    print(f"Post-training models/best.pt MD5: {post_train_best_md5}")
    if pre_train_best_md5 != "NOT_EXISTS":
        assert pre_train_best_md5 == post_train_best_md5, "ALERT: models/best.pt was modified! Revert immediately!"
        print("[VERIFIED] models/best.pt is completely untouched and preserved.")

    # Parse results.csv using built-in csv module
    results_csv = save_dir / "results.csv"
    loss_curves = []
    if results_csv.exists():
        try:
            with open(results_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                # Clean headers
                field_map = {col: col.strip() for col in reader.fieldnames}
                for row in reader:
                    cleaned_row = {field_map[k]: v.strip() for k, v in row.items()}
                    epoch_num = int(cleaned_row.get("epoch", 0)) + 1
                    loss_curves.append({
                        "epoch": epoch_num,
                        "train_box_loss": round(float(cleaned_row.get("train/box_loss", 0)), 4),
                        "train_cls_loss": round(float(cleaned_row.get("train/cls_loss", 0)), 4),
                        "train_dfl_loss": round(float(cleaned_row.get("train/dfl_loss", 0)), 4),
                        "val_box_loss": round(float(cleaned_row.get("val/box_loss", 0)), 4),
                        "val_cls_loss": round(float(cleaned_row.get("val/cls_loss", 0)), 4),
                        "val_dfl_loss": round(float(cleaned_row.get("val/dfl_loss", 0)), 4),
                        "mAP50": round(float(cleaned_row.get("metrics/mAP50(B)", 0)), 4),
                        "mAP50_95": round(float(cleaned_row.get("metrics/mAP50-95(B)", 0)), 4)
                    })
        except Exception as e:
            print(f"Warning reading results.csv: {e}")

    # Evaluate on test split
    print("\n" + "=" * 80)
    print("EVALUATING COMBINED MODEL ON TEST SPLIT")
    print("=" * 80)
    eval_model = YOLO(str(SAVED_COMBINED_MODEL))
    test_metrics = eval_model.val(
        data=str(DATA_YAML),
        split="test",
        device="cpu",
        plots=True,
        save_json=True
    )

    # Per-class metrics
    per_class_metrics = []
    box_metrics = test_metrics.box
    names = test_metrics.names
    p_array = box_metrics.p
    r_array = box_metrics.r
    map50_array = box_metrics.ap50
    map_array = box_metrics.ap

    for cid in range(len(names)):
        cname = names.get(cid, f"Class_{cid}")
        p = round(float(p_array[cid]), 4) if cid < len(p_array) else 0.0
        r = round(float(r_array[cid]), 4) if cid < len(r_array) else 0.0
        ap50 = round(float(map50_array[cid]), 4) if cid < len(map50_array) else 0.0
        ap = round(float(map_array[cid]), 4) if cid < len(map_array) else 0.0
        
        per_class_metrics.append({
            "class_id": cid,
            "class_name": cname,
            "precision": p,
            "recall": r,
            "mAP50": ap50,
            "mAP50_95": ap
        })

    overall_summary = {
        "mAP50": round(float(box_metrics.map50), 4),
        "mAP50_95": round(float(box_metrics.map), 4),
        "mean_precision": round(float(box_metrics.mp), 4),
        "mean_recall": round(float(box_metrics.mr), 4),
        "per_class": per_class_metrics,
        "loss_curves": loss_curves,
        "speed": test_metrics.speed
    }

    # Generate sample test predictions and save annotated images
    annotated_output_dir = PROJECT_ROOT / "static" / "uploads" / "annotated_combined"
    annotated_output_dir.mkdir(parents=True, exist_ok=True)

    test_imgs_dir = PROJECT_ROOT / "datasets" / "raw_materials_combined" / "images" / "test"
    sample_images = []
    for prefix in ["peanut_", "corn_", "sunflower_"]:
        matches = list(test_imgs_dir.glob(f"{prefix}*.jpg"))
        if matches:
            sample_images.extend(matches[:3])

    sample_predictions = []
    for img_p in sample_images:
        res = eval_model.predict(source=str(img_p), conf=0.12, imgsz=imgsz, device="cpu", save=False)[0]
        plot_img = res.plot()
        out_name = f"annotated_{img_p.name}"
        out_path = annotated_output_dir / out_name
        cv2.imwrite(str(out_path), plot_img)

        dets = []
        if res.boxes is not None and len(res.boxes) > 0:
            for b in res.boxes:
                cid = int(b.cls[0].item())
                conf = float(b.conf[0].item())
                dets.append({
                    "class_name": names.get(cid, f"Class_{cid}"),
                    "confidence": round(conf, 3)
                })

        sample_predictions.append({
            "image": img_p.name,
            "detections_count": len(dets),
            "detections": dets[:5],
            "annotated_url": f"/static/uploads/annotated_combined/{out_name}"
        })

    overall_summary["sample_predictions"] = sample_predictions

    # Save evaluation summary to scratch/
    out_json = PROJECT_ROOT / "scratch" / "combined_training_evaluation.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(overall_summary, f, indent=2)
    print(f"\nSaved evaluation results to {out_json}")

    print("\n" + "=" * 80)
    print("FINAL EVALUATION METRICS REPORT (TEST SPLIT)")
    print("=" * 80)
    print(f"Overall mAP50    : {overall_summary['mAP50'] * 100:.2f}%")
    print(f"Overall mAP50-95 : {overall_summary['mAP50_95'] * 100:.2f}%")
    print(f"Mean Precision   : {overall_summary['mean_precision'] * 100:.2f}%")
    print(f"Mean Recall      : {overall_summary['mean_recall'] * 100:.2f}%")
    print("-" * 80)
    print(f"{'Class ID':<9} | {'Class Name':<22} | {'Precision':<10} | {'Recall':<10} | {'mAP50':<10} | {'mAP50-95':<10}")
    print("-" * 80)
    for c in per_class_metrics:
        print(f"{c['class_id']:<9} | {c['class_name']:<22} | {c['precision']*100:<9.1f}% | {c['recall']*100:<9.1f}% | {c['mAP50']*100:<9.1f}% | {c['mAP50_95']*100:<9.1f}%")
    print("=" * 80)

if __name__ == "__main__":
    main()
