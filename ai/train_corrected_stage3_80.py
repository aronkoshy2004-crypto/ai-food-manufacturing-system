"""
YOLOv8 Continued Training Pipeline (Stage 3: 30 Additional Epochs -> Cumulative 80 Epochs)
- Resumes fine-tuning from: models/combined_corrected_best.pt (Cumulative Epoch 50)
- Target data: datasets/raw_materials_combined/data.yaml (3,487 images, 61,377 instances)
- Settings: batch=8, imgsz=416, device=cpu (threads=8, workers=0)
- Epochs: 30 (cumulative total: 80 epochs on corrected labels)
- Output weights: models/combined_corrected_best.pt
- Backup weights: models/combined_corrected_epoch80_backup.pt
- Protected files: models/best.pt, models/combined_best.pt, models/combined_corrected_epoch50_backup.pt strictly untouched
- Logging: per-class metrics every 5 epochs with special focus on Peanut_Moldy trajectory (peaked 57%, currently 44.30%)
- Post-training: unseen test split evaluation, Epoch 50 vs 80 comparison table, loss curve plateau/trend analysis, and corn verification
"""
import os
import sys
import gc
import csv
import json
import time
import shutil
import hashlib
from pathlib import Path
import torch
from ultralytics import YOLO

# CPU threading optimization
torch.set_num_threads(8)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_YAML = PROJECT_ROOT / "datasets" / "raw_materials_combined" / "data.yaml"
MODELS_DIR = PROJECT_ROOT / "models"

SOURCE_MODEL = MODELS_DIR / "combined_corrected_best.pt"
TARGET_BEST_MODEL = MODELS_DIR / "combined_corrected_best.pt"
BACKUP_EPOCH80_MODEL = MODELS_DIR / "combined_corrected_epoch80_backup.pt"

PROTECTED_BEST_MODEL = MODELS_DIR / "best.pt"
PROTECTED_COMBINED_BEST = MODELS_DIR / "combined_best.pt"
PROTECTED_EPOCH50_BACKUP = MODELS_DIR / "combined_corrected_epoch50_backup.pt"

RUN_NAME = "raw_materials_corrected_resumed_epochs51_80"
RUN_DIR = PROJECT_ROOT / "runs" / "detect" / RUN_NAME
PROGRESS_LOG = PROJECT_ROOT / "scratch" / "training_corrected_stage3_progress.log"
PROGRESS_JSON = PROJECT_ROOT / "scratch" / "training_corrected_stage3_progress.json"
EPOCH50_EVAL_JSON = PROJECT_ROOT / "scratch" / "corrected_epoch50_evaluation.json"
EPOCH80_EVAL_JSON = PROJECT_ROOT / "scratch" / "corrected_epoch80_evaluation.json"

TEST_CORN_IMAGE = PROJECT_ROOT / "datasets" / "raw_materials_combined" / "images" / "test" / "corn_20220327_0107_jpg.rf.0902cfd33ed9e744116cdf33e7b66b09.jpg"


def get_file_md5(filepath: Path) -> str:
    if not filepath.exists():
        return "NOT_EXISTS"
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def append_progress_log(text: str):
    try:
        PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        print(f"[WARN] Error writing to progress log: {e}", flush=True)


def update_progress_json(entry: dict):
    try:
        PROGRESS_JSON.parent.mkdir(parents=True, exist_ok=True)
        records = []
        if PROGRESS_JSON.exists():
            try:
                with open(PROGRESS_JSON, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []
        records.append(entry)
        with open(PROGRESS_JSON, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    except Exception as e:
        print(f"[WARN] Error updating progress json: {e}", flush=True)


def create_progress_callback(baseline_ep50_pm_test_recall: float = 44.30, baseline_ep50_pm_val_recall: float = 47.32):
    last_logged_epoch = [-1]

    def on_fit_epoch_end(trainer):
        try:
            current_epoch = trainer.epoch + 1  # 1 to 30
            cumulative_epoch = current_epoch + 50  # 51 to 80
            append_progress_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Completed Stage 3 Epoch {current_epoch}/{trainer.epochs} (Cumulative Epoch {cumulative_epoch}/80)")

            if (current_epoch % 5 == 0 or current_epoch == trainer.epochs) and current_epoch != last_logged_epoch[0]:
                last_logged_epoch[0] = current_epoch

                validator = getattr(trainer, "validator", None)
                if not validator or not hasattr(validator, "metrics") or validator.metrics is None:
                    return

                metrics = validator.metrics
                names = getattr(validator, "names", {})
                box = getattr(metrics, "box", None)
                if box is None:
                    return

                p_arr = box.p
                r_arr = box.r
                ap50_arr = box.ap50
                ap_arr = box.ap
                class_indices = getattr(metrics, "ap_class_index", list(range(len(names))))

                lines = []
                lines.append("\n" + "=" * 100)
                lines.append(f"  [CHECKPOINT PROGRESS] STAGE 3 EPOCH {current_epoch}/{trainer.epochs} (CUMULATIVE {cumulative_epoch}/80)")
                lines.append(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("=" * 100)
                lines.append(f"{'Class ID':<8} | {'Class Name':<22} | {'Precision':<11} | {'Recall':<11} | {'mAP@50':<11} | {'mAP@50-95':<11}")
                lines.append("-" * 100)

                classes_data = {}
                for idx_pos, cid in enumerate(class_indices):
                    cid_int = int(cid)
                    cname = names.get(cid_int, f"Class_{cid_int}")
                    p = float(p_arr[idx_pos]) if idx_pos < len(p_arr) else 0.0
                    r = float(r_arr[idx_pos]) if idx_pos < len(r_arr) else 0.0
                    ap50 = float(ap50_arr[idx_pos]) if idx_pos < len(ap50_arr) else 0.0
                    ap = float(ap_arr[idx_pos]) if idx_pos < len(ap_arr) else 0.0

                    classes_data[cname] = {
                        "class_id": cid_int,
                        "precision": round(p, 4),
                        "recall": round(r, 4),
                        "mAP50": round(ap50, 4),
                        "mAP50_95": round(ap, 4)
                    }
                    lines.append(f"{cid_int:<8} | {cname:<22} | {p*100:>9.2f}% | {r*100:>9.2f}% | {ap50*100:>9.2f}% | {ap*100:>9.2f}%")

                lines.append("-" * 100)

                # Peanut_Moldy Focus
                pm = classes_data.get("Peanut_Moldy")
                if pm:
                    pm_r = pm["recall"] * 100
                    pm_p = pm["precision"] * 100
                    pm_map50 = pm["mAP50"] * 100
                    val_diff = pm_r - baseline_ep50_pm_val_recall
                    status_str = "CLIMBING" if val_diff > 3.0 else ("PLATEAUED/STABLE" if abs(val_diff) <= 3.0 else "DIPPING")
                    lines.append(f">>> [KEY METRIC FOCUS] PEANUT_MOLDY TRAJECTORY (Cumulative Epoch {cumulative_epoch}/80):")
                    lines.append(f"    Current Val Recall    : {pm_r:.2f}% (Baseline Ep50 Val: {baseline_ep50_pm_val_recall:.2f}%, Test: {baseline_ep50_pm_test_recall:.2f}%)")
                    lines.append(f"    Current Val Precision : {pm_p:.2f}%")
                    lines.append(f"    Current Val mAP@50    : {pm_map50:.2f}%")
                    lines.append(f"    Val Recall Delta vs Ep50: {val_diff:+.2f}% ({status_str})")

                # Corn Status Tracking
                cm = classes_data.get("Corn_Moldy")
                cnm = classes_data.get("Corn_Not_Moldy")
                if cm and cnm:
                    lines.append(f">>> CORN STATUS (Cumulative Epoch {cumulative_epoch}/80):")
                    lines.append(f"    Corn_Moldy     -> Recall: {cm['recall']*100:.2f}%, Precision: {cm['precision']*100:.2f}%, mAP50: {cm['mAP50']*100:.2f}%")
                    lines.append(f"    Corn_Not_Moldy -> Recall: {cnm['recall']*100:.2f}%, Precision: {cnm['precision']*100:.2f}%, mAP50: {cnm['mAP50']*100:.2f}%")
                lines.append("=" * 100)

                msg = "\n".join(lines)
                print(msg, flush=True)
                append_progress_log(msg)

                record = {
                    "stage3_epoch": current_epoch,
                    "cumulative_epoch": cumulative_epoch,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "classes": classes_data
                }
                update_progress_json(record)

        except Exception as e:
            print(f"[WARN] Error in on_fit_epoch_end callback: {e}", flush=True)

    return on_fit_epoch_end


def test_corn_false_positive_resolution(model_path: Path):
    """Evaluates the model specifically on the problem test image corn_20220327_0107_jpg."""
    print("\n" + "=" * 100)
    print("SPECIFIC VERIFICATION: HEALTHY CORN TEST IMAGE (corn_20220327_0107_jpg)")
    print("=" * 100)

    if not TEST_CORN_IMAGE.exists():
        print(f"[WARN] Test image {TEST_CORN_IMAGE} does not exist!")
        return {"status": "IMAGE_NOT_FOUND"}

    model = YOLO(str(model_path))
    res = model.predict(str(TEST_CORN_IMAGE), conf=0.25, verbose=False)[0]

    detected_classes = [int(b.cls[0].item()) for b in res.boxes]

    moldy_count = detected_classes.count(2)  # 2 is Corn_Moldy
    clean_count = detected_classes.count(3)  # 3 is Corn_Not_Moldy

    print(f"Total detections at conf >= 0.25: {len(detected_classes)}")
    print(f"  - Detected Corn_Not_Moldy (Healthy): {clean_count}")
    print(f"  - Detected Corn_Moldy (False Positives): {moldy_count}")

    is_resolved = (moldy_count == 0)
    verdict = "RESOLVED (0 False Positives)" if is_resolved else f"FAILED ({moldy_count} false positives remaining)"
    print(f"\n>>> VERDICT: Healthy Corn False-Positive Fix at Epoch 80 is {verdict}!")
    print("=" * 100)

    return {
        "test_image": str(TEST_CORN_IMAGE.name),
        "total_detections": len(detected_classes),
        "corn_not_moldy_count": clean_count,
        "corn_moldy_count": moldy_count,
        "is_resolved": is_resolved,
        "verdict": verdict
    }


def parse_loss_curves(results_csv_path: Path):
    """Extracts loss and metric curves across all epochs from results.csv."""
    curves = []
    if not results_csv_path.exists():
        return curves

    try:
        with open(results_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            field_map = {col: col.strip() for col in reader.fieldnames}
            for row in reader:
                cleaned = {field_map[k]: v.strip() for k, v in row.items()}
                stage3_ep = int(cleaned.get("epoch", 0)) + 1
                cumulative_ep = stage3_ep + 50
                curves.append({
                    "stage3_epoch": stage3_ep,
                    "cumulative_epoch": cumulative_ep,
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
        print(f"[WARN] Error reading results.csv: {e}")

    return curves


def analyze_loss_trend(curves: list) -> dict:
    """Provides a concise loss curve trajectory analysis: plateaued vs still improving."""
    if not curves:
        return {"summary": "No loss curves available"}

    first = curves[0]
    last = curves[-1]

    train_cls_drop = first["train_cls_loss"] - last["train_cls_loss"]
    val_cls_drop = first["val_cls_loss"] - last["val_cls_loss"]
    train_box_drop = first["train_box_loss"] - last["train_box_loss"]
    val_box_drop = first["val_box_loss"] - last["val_box_loss"]
    map50_gain = last["mAP50"] - first["mAP50"]

    # Trend assessment
    cls_abs_change = abs(val_cls_drop)
    if cls_abs_change < 0.05 and abs(map50_gain) < 0.02:
        trend_state = "PLATEAUED"
        assessment = "Loss curves and validation mAP@50 have largely plateaued, showing mature convergence with minimal marginal gains."
    elif val_cls_drop > 0.05 or map50_gain > 0.02:
        trend_state = "STILL IMPROVING"
        assessment = "Model is still steadily improving with continued reduction in classification and box losses."
    else:
        trend_state = "OSCILLATING / STABLE"
        assessment = "Model metrics show slight natural epoch-to-epoch oscillation around an optimal plateau."

    overfitting = False
    if last["val_cls_loss"] > first["val_cls_loss"] * 1.25 and last["train_cls_loss"] < first["train_cls_loss"] * 0.7:
        overfitting = True

    return {
        "trend_state": trend_state,
        "start_cumulative_epoch": first["cumulative_epoch"],
        "end_cumulative_epoch": last["cumulative_epoch"],
        "train_cls_loss_initial": first["train_cls_loss"],
        "train_cls_loss_final": last["train_cls_loss"],
        "train_cls_loss_reduction": round(train_cls_drop, 4),
        "val_cls_loss_initial": first["val_cls_loss"],
        "val_cls_loss_final": last["val_cls_loss"],
        "val_cls_loss_reduction": round(val_cls_drop, 4),
        "train_box_loss_initial": first["train_box_loss"],
        "train_box_loss_final": last["train_box_loss"],
        "val_box_loss_initial": first["val_box_loss"],
        "val_box_loss_final": last["val_box_loss"],
        "mAP50_initial": first["mAP50"],
        "mAP50_final": last["mAP50"],
        "mAP50_gain": round(map50_gain, 4),
        "is_overfitting_detected": overfitting,
        "trend_summary": (
            f"Stage 3 (Epochs 51-80): Classification loss moved from {first['train_cls_loss']} to {last['train_cls_loss']} (train) "
            f"and {first['val_cls_loss']} to {last['val_cls_loss']} (val). Validation mAP@50 evolved from {first['mAP50']*100:.2f}% to {last['mAP50']*100:.2f}%. "
            f"Trend status: [{trend_state}]. {assessment}"
        )
    }


def main():
    print("=" * 100)
    print("STARTING CONTINUED YOLOV8 TRAINING (STAGE 3: 30 EPOCHS -> CUMULATIVE 80 EPOCHS)")
    print("CORRECTED 5-SOURCE DATASET PIPELINE")
    print("=" * 100)
    print(f"  Source weights (Ep 50):       {SOURCE_MODEL}")
    print(f"  Target data YAML:             {DATA_YAML}")
    print(f"  Output weights:               {TARGET_BEST_MODEL}")
    print(f"  Epoch 80 backup weights:      {BACKUP_EPOCH80_MODEL}")
    print(f"  Protected Epoch 50 backup:    {PROTECTED_EPOCH50_BACKUP}")
    print(f"  Protected best:               {PROTECTED_BEST_MODEL}")
    print(f"  Protected combined:           {PROTECTED_COMBINED_BEST}")
    print("=" * 100)

    # 1. Integrity check on source model
    if not SOURCE_MODEL.exists():
        print(f"[FATAL] Source model does not exist at {SOURCE_MODEL}!")
        sys.exit(1)

    # 2. Record initial MD5 of protected models
    initial_best_md5 = get_file_md5(PROTECTED_BEST_MODEL)
    initial_combined_md5 = get_file_md5(PROTECTED_COMBINED_BEST)
    initial_ep50_md5 = get_file_md5(PROTECTED_EPOCH50_BACKUP)
    print(f"Protected models/best.pt MD5                       : {initial_best_md5}")
    print(f"Protected models/combined_best.pt MD5              : {initial_combined_md5}")
    print(f"Protected models/combined_corrected_epoch50_backup : {initial_ep50_md5}")

    # 3. Reset progress log for stage 3
    if PROGRESS_LOG.exists():
        PROGRESS_LOG.unlink()
    if PROGRESS_JSON.exists():
        PROGRESS_JSON.unlink()
    append_progress_log(f"Starting Stage 3 Training: 30 Epochs (Cumulative 51-80) at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 4. Load Epoch 50 baseline evaluation for comparison
    ep50_data = {}
    if EPOCH50_EVAL_JSON.exists():
        try:
            with open(EPOCH50_EVAL_JSON, "r", encoding="utf-8") as f:
                ep50_data = json.load(f)
        except Exception as e:
            print(f"[WARN] Error reading Epoch 50 evaluation json: {e}")

    ep50_by_class = {c["class_name"]: c for c in ep50_data.get("per_class_test_epoch50", [])}
    baseline_pm_test_recall = ep50_by_class.get("Peanut_Moldy", {}).get("recall", 0.4430) * 100

    # 5. Initialize YOLO model from combined_corrected_best.pt (Epoch 50 weights)
    model = YOLO(str(SOURCE_MODEL))
    callback = create_progress_callback(baseline_ep50_pm_test_recall=baseline_pm_test_recall, baseline_ep50_pm_val_recall=47.32)
    model.add_callback("on_fit_epoch_end", callback)

    # Clean existing run dir if present
    if RUN_DIR.exists():
        print(f"Cleaning previous run directory: {RUN_DIR}")
        shutil.rmtree(RUN_DIR, ignore_errors=True)

    start_train_time = time.time()

    # 6. Execute 30-epoch training (bringing cumulative total to 80)
    train_results = model.train(
        data=str(DATA_YAML),
        epochs=30,
        batch=8,
        imgsz=416,
        device="cpu",
        workers=0,
        name=RUN_NAME,
        project=str(PROJECT_ROOT / "runs" / "detect"),
        exist_ok=True,
        save=True,
        plots=True,
        verbose=True
    )

    train_duration = time.time() - start_train_time
    print(f"\n Training completed in {train_duration/60:.2f} minutes ({train_duration/3600:.2f} hours).")

    # 7. Locate best weights from this run
    save_dir = Path(train_results.save_dir) if hasattr(train_results, "save_dir") else RUN_DIR
    run_best_weights = save_dir / "weights" / "best.pt"
    if not run_best_weights.exists():
        run_best_weights = save_dir / "weights" / "last.pt"

    print(f"Trained run best weights located at: {run_best_weights}")

    # 8. Save to combined_corrected_best.pt AND backup to combined_corrected_epoch80_backup.pt
    shutil.copy2(run_best_weights, TARGET_BEST_MODEL)
    print(f" Saved updated weights to: {TARGET_BEST_MODEL}")
    shutil.copy2(run_best_weights, BACKUP_EPOCH80_MODEL)
    print(f" Saved Epoch 80 backup weights to: {BACKUP_EPOCH80_MODEL}")

    # Verify protected models integrity
    post_best_md5 = get_file_md5(PROTECTED_BEST_MODEL)
    post_combined_md5 = get_file_md5(PROTECTED_COMBINED_BEST)
    post_ep50_md5 = get_file_md5(PROTECTED_EPOCH50_BACKUP)
    assert initial_best_md5 == post_best_md5, "CRITICAL ERROR: Protected models/best.pt was modified!"
    assert initial_combined_md5 == post_combined_md5, "CRITICAL ERROR: Protected models/combined_best.pt was modified!"
    assert initial_ep50_md5 == post_ep50_md5, "CRITICAL ERROR: Protected models/combined_corrected_epoch50_backup.pt was modified!"
    print(" VERIFIED: Protected models/best.pt, models/combined_best.pt, and models/combined_corrected_epoch50_backup.pt remain completely untouched.")

    # 9. Evaluate on unseen test split
    print("\n" + "=" * 100)
    print("EVALUATING UPDATED MODEL (CUMULATIVE EPOCH 80) ON UNSEEN TEST SPLIT")
    print("=" * 100)

    test_model = YOLO(str(TARGET_BEST_MODEL))
    test_metrics = test_model.val(
        data=str(DATA_YAML),
        split="test",
        batch=8,
        imgsz=416,
        device="cpu",
        workers=0
    )

    box_metrics = test_metrics.box
    names = test_metrics.names
    class_indices = getattr(test_metrics, "ap_class_index", list(range(len(names))))

    p_array = box_metrics.p
    r_array = box_metrics.r
    map50_array = box_metrics.ap50
    map_array = box_metrics.ap

    per_class_test_ep80 = []
    for idx_pos, cid in enumerate(class_indices):
        cid_int = int(cid)
        cname = names.get(cid_int, f"Class_{cid_int}")
        p = round(float(p_array[idx_pos]), 4) if idx_pos < len(p_array) else 0.0
        r = round(float(r_array[idx_pos]), 4) if idx_pos < len(r_array) else 0.0
        ap50 = round(float(map50_array[idx_pos]), 4) if idx_pos < len(map50_array) else 0.0
        ap = round(float(map_array[idx_pos]), 4) if idx_pos < len(map_array) else 0.0
        per_class_test_ep80.append({
            "class_id": cid_int,
            "class_name": cname,
            "precision": p,
            "recall": r,
            "mAP50": ap50,
            "mAP50_95": ap
        })

    # 10. Side-by-side comparison (Epoch 50 vs Epoch 80)
    comparison_table = []
    for c80 in per_class_test_ep80:
        cname = c80["class_name"]
        c50 = ep50_by_class.get(cname, {})

        p50 = c50.get("precision", 0.0)
        r50 = c50.get("recall", 0.0)
        m50 = c50.get("mAP50", 0.0)
        m95_50 = c50.get("mAP50_95", 0.0)

        p80 = c80["precision"]
        r80 = c80["recall"]
        m80 = c80["mAP50"]
        m95_80 = c80["mAP50_95"]

        comparison_table.append({
            "class_name": cname,
            "class_id": c80["class_id"],
            "epoch50": {"precision": p50, "recall": r50, "mAP50": m50, "mAP50_95": m95_50},
            "epoch80": {"precision": p80, "recall": r80, "mAP50": m80, "mAP50_95": m95_80},
            "delta": {
                "precision": round(p80 - p50, 4),
                "recall": round(r80 - r50, 4),
                "mAP50": round(m80 - m50, 4),
                "mAP50_95": round(m95_80 - m95_50, 4)
            }
        })

    # 11. Parse loss curves from results.csv
    results_csv = save_dir / "results.csv"
    loss_curves = parse_loss_curves(results_csv)
    loss_analysis = analyze_loss_trend(loss_curves)

    # 12. Re-verify healthy corn false-positive resolution
    corn_fp_test = test_corn_false_positive_resolution(TARGET_BEST_MODEL)

    # 13. Compile final payload
    eval_payload = {
        "model_path": str(TARGET_BEST_MODEL),
        "backup_path": str(BACKUP_EPOCH80_MODEL),
        "cumulative_epochs": 80,
        "stage3_epochs": 30,
        "training_duration_seconds": round(train_duration, 2),
        "overall_test_epoch80": {
            "mAP50": round(float(box_metrics.map50), 4),
            "mAP50_95": round(float(box_metrics.map), 4),
            "mean_precision": round(float(box_metrics.mp), 4),
            "mean_recall": round(float(box_metrics.mr), 4)
        },
        "per_class_test_epoch80": per_class_test_ep80,
        "comparison_epoch50_vs_epoch80": comparison_table,
        "loss_curves_stage3": loss_curves,
        "loss_curve_trend": loss_analysis,
        "corn_false_positive_test": corn_fp_test
    }

    with open(EPOCH80_EVAL_JSON, "w", encoding="utf-8") as f:
        json.dump(eval_payload, f, indent=2)
    print(f"\nSaved full Epoch 80 evaluation to {EPOCH80_EVAL_JSON}")

    # 14. Print Formatted Comparison Report
    print("\n" + "=" * 100)
    print("COMPARISON REPORT: EPOCH 50 vs EPOCH 80 (UNSEEN TEST SPLIT)")
    print("=" * 100)
    print(f"{'Class Name':<22} | {'Metric':<10} | {'Epoch 50':<10} | {'Epoch 80':<10} | {'Change (Delta)':<15}")
    print("-" * 100)
    for comp in comparison_table:
        cname = comp["class_name"]
        e50 = comp["epoch50"]
        e80 = comp["epoch80"]
        d = comp["delta"]

        r_sign = "+" if d["recall"] >= 0 else ""
        m_sign = "+" if d["mAP50"] >= 0 else ""
        p_sign = "+" if d["precision"] >= 0 else ""

        print(f"{cname:<22} | Recall     | {e50['recall']*100:>8.2f}% | {e80['recall']*100:>8.2f}% | {r_sign}{d['recall']*100:>+7.2f}%")
        print(f"{'':<22} | Precision  | {e50['precision']*100:>8.2f}% | {e80['precision']*100:>8.2f}% | {p_sign}{d['precision']*100:>+7.2f}%")
        print(f"{'':<22} | mAP@50     | {e50['mAP50']*100:>8.2f}% | {e80['mAP50']*100:>8.2f}% | {m_sign}{d['mAP50']*100:>+7.2f}%")
        print("-" * 100)

    # Dedicated Spotlight on Peanut_Moldy
    pm_comp = next((c for c in comparison_table if c["class_name"] == "Peanut_Moldy"), None)
    if pm_comp:
        print("\n" + "=" * 100)
        print(">>> KEY METRIC SPOTLIGHT: PEANUT_MOLDY PROGRESSION (EPOCH 50 -> 80)")
        print("=" * 100)
        e50 = pm_comp["epoch50"]
        e80 = pm_comp["epoch80"]
        d = pm_comp["delta"]
        print(f"  Recall     : {e50['recall']*100:.2f}%  ->  {e80['recall']*100:.2f}%  ({d['recall']*100:+.2f}%)")
        print(f"  Precision  : {e50['precision']*100:.2f}%  ->  {e80['precision']*100:.2f}%  ({d['precision']*100:+.2f}%)")
        print(f"  mAP@50     : {e50['mAP50']*100:.2f}%  ->  {e80['mAP50']*100:.2f}%  ({d['mAP50']*100:+.2f}%)")
        print("=" * 100)

    print("\n" + "=" * 100)
    print("LOSS CURVE TREND ANALYSIS:")
    print("=" * 100)
    print(f"  State:   [{loss_analysis['trend_state']}]")
    print(f"  Summary: {loss_analysis['trend_summary']}")
    print("=" * 100)


if __name__ == "__main__":
    main()
