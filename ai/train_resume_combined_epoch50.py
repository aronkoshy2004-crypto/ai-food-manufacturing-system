"""
YOLOv8 Resumed Training Pipeline (Stage 3: Epochs 21-50)
Resumes training from models/combined_best.pt (Epoch 20) on datasets/raw_materials_combined/data.yaml
for 30 additional epochs (bringing cumulative total to 50 epochs).

Settings:
  - Batch size: 8
  - Resolution: 416
  - Device: CPU (torch threads: 8)
  - Base weights: models/combined_best.pt (Epoch 20)
  - Protected: models/best.pt is strictly untouched and verified via MD5
  - Checkpoint backup: models/combined_epoch50_backup.pt
  - Updated production weights: models/combined_best.pt

Logging:
  - Every 5 epochs (epochs 25, 30, 35, 40, 45, 50): Full per-class precision/recall/mAP50/mAP50-95
  - Specific tracking of Peanut_Moldy to monitor improvement vs plateauing

Post-Training Analysis:
  - Full per-class evaluation on unseen test split
  - Comparison table: Epoch 20 vs Epoch 50 for all 6 classes
  - 50-Epoch loss curve trend analysis (plateau vs continuing decline)
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

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_YAML = PROJECT_ROOT / "datasets" / "raw_materials_combined" / "data.yaml"
MODELS_DIR = PROJECT_ROOT / "models"
COMBINED_BEST_MODEL = MODELS_DIR / "combined_best.pt"
EPOCH20_BACKUP_MODEL = MODELS_DIR / "combined_epoch20_backup.pt"
EPOCH50_BACKUP_MODEL = MODELS_DIR / "combined_epoch50_backup.pt"
EXISTING_BEST_MODEL = MODELS_DIR / "best.pt"

# Previous runs and evaluations
STAGE1_CSV = PROJECT_ROOT / "runs" / "detect" / "raw_materials_combined_yolov8" / "results.csv"
STAGE2_CSV = PROJECT_ROOT / "runs" / "detect" / "raw_materials_combined_resumed_epochs11_20" / "results.csv"
EPOCH20_EVAL_JSON = PROJECT_ROOT / "scratch" / "resumed_training_evaluation.json"

# Outputs
RUN_NAME = "raw_materials_combined_resumed_epochs21_50"
RUN_DIR = PROJECT_ROOT / "runs" / "detect" / RUN_NAME
PROGRESS_LOG = PROJECT_ROOT / "scratch" / "training_epochs21_50_progress.log"
PROGRESS_JSON = PROJECT_ROOT / "scratch" / "training_epochs21_50_progress.json"
FINAL_EVAL_JSON = PROJECT_ROOT / "scratch" / "combined_epoch50_evaluation.json"


def get_file_md5(filepath: Path) -> str:
    """Computes MD5 hash of file to verify integrity."""
    if not filepath.exists():
        return "NOT_EXISTS"
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def append_progress_log(text: str):
    """Appends message to scratch/training_epochs21_50_progress.log."""
    try:
        PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        print(f"[WARN] Error writing to progress log: {e}", flush=True)


def update_progress_json(entry: dict):
    """Appends entry to scratch/training_epochs21_50_progress.json."""
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


def create_progress_callback():
    """Factory to create on_fit_epoch_end callback with clean state."""
    last_logged_epoch = [-1]

    def on_fit_epoch_end(trainer):
        try:
            current_stage3_epoch = trainer.epoch + 1  # 1 to 30
            cumulative_epoch = 20 + current_stage3_epoch  # 21 to 50

            # Log heartbeat for every completed epoch
            append_progress_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Completed Epoch {current_stage3_epoch}/30 (Cumulative {cumulative_epoch}/50)")

            # Trigger every 5 epochs or on the very last epoch
            if (current_stage3_epoch % 5 == 0 or current_stage3_epoch == trainer.epochs) and current_stage3_epoch != last_logged_epoch[0]:
                last_logged_epoch[0] = current_stage3_epoch

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
                lines.append("\n" + "=" * 96)
                lines.append(f"  [CHECKPOINT PROGRESS] STAGE 3 EPOCH {current_stage3_epoch}/{trainer.epochs} | CUMULATIVE EPOCH {cumulative_epoch}/50")
                lines.append(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("=" * 96)
                lines.append(f"{'Class ID':<8} | {'Class Name':<22} | {'Precision':<11} | {'Recall':<11} | {'mAP@50':<11} | {'mAP@50-95':<11}")
                lines.append("-" * 96)

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

                lines.append("-" * 96)
                # Peanut_Moldy focus
                pm = classes_data.get("Peanut_Moldy")
                if pm:
                    # Baseline at epoch 20 was: Precision 60.69%, Recall 49.33%, mAP50 45.25%
                    delta_rec = (pm['recall'] - 0.4933) * 100
                    delta_map = (pm['mAP50'] - 0.4525) * 100
                    rec_status = "IMPROVING" if delta_rec > 1.0 else ("PLATEAUED" if abs(delta_rec) <= 1.0 else "DECREASED")
                    lines.append(f">>> PEANUT_MOLDY STATUS (Cumulative Epoch {cumulative_epoch}):")
                    lines.append(f"    Recall: {pm['recall']*100:.2f}% (Epoch 20 Baseline: 49.33%, Delta: {delta_rec:+.2f}% -> {rec_status})")
                    lines.append(f"    Precision: {pm['precision']*100:.2f}% | mAP@50: {pm['mAP50']*100:.2f}% (Delta: {delta_map:+.2f}%)")
                lines.append("=" * 96)

                msg = "\n".join(lines)
                print(msg, flush=True)
                append_progress_log(msg)

                # Store JSON record
                record = {
                    "stage3_epoch": current_stage3_epoch,
                    "cumulative_epoch": cumulative_epoch,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "classes": classes_data
                }
                update_progress_json(record)

        except Exception as e:
            print(f"[WARN in on_fit_epoch_end callback]: {e}", flush=True)
        finally:
            gc.collect()

    return on_fit_epoch_end


def analyze_loss_curves_all50(stage1_csv: Path, stage2_csv: Path, stage3_csv: Path):
    """
    Parses and stitches together loss curves across all 50 epochs:
      - Epochs 1-10: stage1_csv
      - Epochs 11-20: stage2_csv
      - Epochs 21-50: stage3_csv
    Analyzes trends and determines if losses have plateaued or are still decreasing.
    """
    all_epochs = []

    def read_csv(path: Path, epoch_offset: int):
        if not path.exists():
            print(f"[WARN] Missing loss CSV: {path}")
            return []
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            field_map = {k: k.strip() for k in reader.fieldnames}
            for r in reader:
                cleaned = {field_map[k]: v.strip() for k, v in r.items()}
                ep = int(cleaned.get("epoch", 0)) + epoch_offset
                rows.append({
                    "epoch": ep,
                    "train_box_loss": float(cleaned.get("train/box_loss", 0.0)),
                    "train_cls_loss": float(cleaned.get("train/cls_loss", 0.0)),
                    "train_dfl_loss": float(cleaned.get("train/dfl_loss", 0.0)),
                    "val_box_loss": float(cleaned.get("val/box_loss", 0.0)),
                    "val_cls_loss": float(cleaned.get("val/cls_loss", 0.0)),
                    "val_dfl_loss": float(cleaned.get("val/dfl_loss", 0.0)),
                    "mAP50": float(cleaned.get("metrics/mAP50(B)", 0.0)),
                    "mAP50_95": float(cleaned.get("metrics/mAP50-95(B)", 0.0)),
                })
        return rows

    rows1 = read_csv(stage1_csv, 0)   # 1-10
    rows2 = read_csv(stage2_csv, 10)  # 11-20
    rows3 = read_csv(stage3_csv, 20)  # 21-50

    all_epochs = rows1 + rows2 + rows3
    all_epochs.sort(key=lambda x: x["epoch"])

    # Trend Analysis for epochs 41-50
    final_window = [e for e in all_epochs if e["epoch"] >= 41]
    prev_window = [e for e in all_epochs if 31 <= e["epoch"] <= 40]

    analysis = {
        "total_epochs": len(all_epochs),
        "history": all_epochs,
        "diagnostics": {}
    }

    if len(final_window) >= 5 and len(prev_window) >= 5:
        # Calculate averages for window comparison
        avg_train_cls_prev = sum(e["train_cls_loss"] for e in prev_window) / len(prev_window)
        avg_train_cls_final = sum(e["train_cls_loss"] for e in final_window) / len(final_window)
        train_cls_rate = ((avg_train_cls_final - avg_train_cls_prev) / avg_train_cls_prev) * 100

        avg_val_cls_prev = sum(e["val_cls_loss"] for e in prev_window) / len(prev_window)
        avg_val_cls_final = sum(e["val_cls_loss"] for e in final_window) / len(final_window)
        val_cls_rate = ((avg_val_cls_final - avg_val_cls_prev) / avg_val_cls_prev) * 100

        avg_val_box_prev = sum(e["val_box_loss"] for e in prev_window) / len(prev_window)
        avg_val_box_final = sum(e["val_box_loss"] for e in final_window) / len(final_window)
        val_box_rate = ((avg_val_box_final - avg_val_box_prev) / avg_val_box_prev) * 100

        avg_map50_prev = sum(e["mAP50"] for e in prev_window) / len(prev_window)
        avg_map50_final = sum(e["mAP50"] for e in final_window) / len(final_window)
        map50_rate = ((avg_map50_final - avg_map50_prev) / avg_map50_prev) * 100

        # Plateau determination
        # If val loss change is within +/- 2% or rising, validation loss has plateaued
        val_plateaued = abs(val_cls_rate) < 2.5 or val_cls_rate > 0
        train_plateaued = abs(train_cls_rate) < 3.0

        if val_plateaued and map50_rate <= 1.0:
            conclusion = "PLATEAUED_NEAR_CEILING"
            explanation = (
                "Validation loss and mAP50 have flattened out in the final 10 epochs (epochs 41-50). "
                f"Val Cls Loss change is {val_cls_rate:+.2f}%, and mAP50 delta is {map50_rate:+.2f}%. "
                "The model is close to the empirical ceiling for this dataset, architecture (YOLOv8n), and resolution (416). "
                "Further training on the exact same resolution is unlikely to yield substantial gains and may risk slight overfitting."
            )
        elif val_cls_rate < -2.5:
            conclusion = "STILL_DECREASING"
            explanation = (
                f"Validation classification loss is still decreasing at a rate of {val_cls_rate:.2f}% "
                f"between epochs 31-40 and 41-50, with mAP50 continuing upward (+{map50_rate:.2f}%). "
                "The model has not yet plateaued, and additional training epochs would likely improve accuracy further."
            )
        else:
            conclusion = "SLIGHT_CONVERGENCE"
            explanation = (
                f"Losses are exhibiting asymptotic convergence. Train loss is at {avg_train_cls_final:.4f} "
                f"and Val loss is at {avg_val_cls_final:.4f}. Progress is diminishing per epoch."
            )

        analysis["diagnostics"] = {
            "avg_train_cls_epochs31_40": round(avg_train_cls_prev, 4),
            "avg_train_cls_epochs41_50": round(avg_train_cls_final, 4),
            "train_cls_change_pct": round(train_cls_rate, 2),
            "avg_val_cls_epochs31_40": round(avg_val_cls_prev, 4),
            "avg_val_cls_epochs41_50": round(avg_val_cls_final, 4),
            "val_cls_change_pct": round(val_cls_rate, 2),
            "avg_val_box_epochs31_40": round(avg_val_box_prev, 4),
            "avg_val_box_epochs41_50": round(avg_val_box_final, 4),
            "val_box_change_pct": round(val_box_rate, 2),
            "avg_map50_epochs31_40": round(avg_map50_prev, 4),
            "avg_map50_epochs41_50": round(avg_map50_final, 4),
            "map50_change_pct": round(map50_rate, 2),
            "conclusion": conclusion,
            "explanation": explanation
        }

    return analysis


def main():
    print("=" * 96, flush=True)
    print("YOLOV8 RESUMED TRAINING PIPELINE (STAGE 3: EPOCHS 21-50)", flush=True)
    print("=" * 96, flush=True)

    # 1. Baseline MD5 checks & integrity verification
    if not COMBINED_BEST_MODEL.exists():
        print(f"ERROR: Starting weights not found at {COMBINED_BEST_MODEL}", flush=True)
        sys.exit(1)

    pre_train_best_md5 = get_file_md5(EXISTING_BEST_MODEL)
    pre_train_combined_md5 = get_file_md5(COMBINED_BEST_MODEL)
    print(f"Pre-training models/best.pt MD5          : {pre_train_best_md5}", flush=True)
    print(f"Pre-training models/combined_best.pt MD5 : {pre_train_combined_md5}", flush=True)

    # 2. Preserve Epoch 20 backup
    if not EPOCH20_BACKUP_MODEL.exists():
        shutil.copy2(COMBINED_BEST_MODEL, EPOCH20_BACKUP_MODEL)
        print(f"Preserved Epoch 20 weights to: {EPOCH20_BACKUP_MODEL}", flush=True)
    else:
        print(f"Epoch 20 backup already present at: {EPOCH20_BACKUP_MODEL}", flush=True)

    # Reset progress logs
    if PROGRESS_LOG.exists():
        try:
            PROGRESS_LOG.unlink()
        except Exception:
            pass
    if PROGRESS_JSON.exists():
        try:
            PROGRESS_JSON.unlink()
        except Exception:
            pass

    append_progress_log(f"Starting Training Stage 3: Epochs 21-50 at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    from ultralytics import YOLO
    import gc
    import torch

    torch.set_num_threads(8)
    gc.collect()

    epochs = 30  # 30 additional epochs (bringing cumulative total to 50)
    batch = 8
    imgsz = 416

    print(f"\n[STARTING RESUMED TRAINING]", flush=True)
    print(f"  - Starting Weights : {COMBINED_BEST_MODEL} (Epoch 20)", flush=True)
    print(f"  - Dataset          : {DATA_YAML}", flush=True)
    print(f"  - Additional Epochs: {epochs} (Cumulative Epochs 21-50)", flush=True)
    print(f"  - Batch size       : {batch}", flush=True)
    print(f"  - Image size       : {imgsz}", flush=True)
    print(f"  - Device           : cpu (torch threads: 8)", flush=True)
    print(f"  - Output Dir       : {RUN_DIR}", flush=True)
    print(f"  - Protected Model  : {EXISTING_BEST_MODEL} (strictly untouched)", flush=True)

    if RUN_DIR.exists():
        print(f"Cleaning previous run dir: {RUN_DIR}", flush=True)
        shutil.rmtree(RUN_DIR, ignore_errors=True)

    # Load starting weights from combined_best.pt (Epoch 20)
    model = YOLO(str(COMBINED_BEST_MODEL))

    # Register callback for 5-epoch per-class progress reporting
    progress_callback = create_progress_callback()
    model.add_callback("on_fit_epoch_end", progress_callback)
    print("Registered per-class progress logging callback (fires every 5 epochs).", flush=True)

    # Execute training
    start_time = time.time()
    train_results = model.train(
        data=str(DATA_YAML),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device="cpu",
        name=RUN_NAME,
        exist_ok=True,
        workers=0,
        plots=True,
        verbose=True
    )
    total_train_sec = time.time() - start_time

    save_dir = Path(train_results.save_dir) if hasattr(train_results, "save_dir") else RUN_DIR
    new_best_weights = save_dir / "weights" / "best.pt"

    print("\n" + "=" * 96, flush=True)
    print(f"TRAINING COMPLETED IN {total_train_sec/3600:.2f} HOURS — UPDATING COMBINED WEIGHTS", flush=True)
    print("=" * 96, flush=True)

    if not new_best_weights.exists():
        print(f"ERROR: Could not locate new best weights at {new_best_weights}", flush=True)
        sys.exit(1)

    # 3. Checkpoint Backups & Production Weights Update
    # Preserve backup checkpoint at models/combined_epoch50_backup.pt
    shutil.copy2(new_best_weights, EPOCH50_BACKUP_MODEL)
    print(f"[CHECKPOINT] Preserved backup checkpoint at: {EPOCH50_BACKUP_MODEL}", flush=True)

    # Update models/combined_best.pt with new best weights
    shutil.copy2(new_best_weights, COMBINED_BEST_MODEL)
    print(f"[CHECKPOINT] Updated models/combined_best.pt with new best weights (Epoch 50)!", flush=True)

    # 4. Strict MD5 integrity verification on models/best.pt
    post_train_best_md5 = get_file_md5(EXISTING_BEST_MODEL)
    print(f"Post-training models/best.pt MD5: {post_train_best_md5}", flush=True)
    assert pre_train_best_md5 == post_train_best_md5, "CRITICAL ALERT: models/best.pt was modified!"
    print("[VERIFIED] models/best.pt is 100% UNTOUCHED and PRESERVED.", flush=True)

    # 5. Full Evaluation on Unseen Test Split
    print("\n" + "=" * 96, flush=True)
    print("EVALUATING UPDATED MODEL (EPOCH 50) ON UNSEEN TEST SPLIT", flush=True)
    print("=" * 96, flush=True)

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
    class_indices = getattr(box_metrics, "ap_class_index", list(range(len(names))))

    per_class_metrics_ep50 = []
    for idx_pos, cid in enumerate(class_indices):
        cid_int = int(cid)
        cname = names.get(cid_int, f"Class_{cid_int}")
        p = round(float(p_array[idx_pos]), 4) if idx_pos < len(p_array) else 0.0
        r = round(float(r_array[idx_pos]), 4) if idx_pos < len(r_array) else 0.0
        ap50 = round(float(map50_array[idx_pos]), 4) if idx_pos < len(map50_array) else 0.0
        ap = round(float(map_array[idx_pos]), 4) if idx_pos < len(map_array) else 0.0
        per_class_metrics_ep50.append({
            "class_id": cid_int,
            "class_name": cname,
            "precision": p,
            "recall": r,
            "mAP50": ap50,
            "mAP50_95": ap
        })

    # 6. Load Epoch 20 evaluation for side-by-side comparison
    ep20_data = {}
    if EPOCH20_EVAL_JSON.exists():
        try:
            with open(EPOCH20_EVAL_JSON, "r", encoding="utf-8") as f:
                ep20_data = json.load(f)
        except Exception as e:
            print(f"Warning reading Epoch 20 data: {e}", flush=True)

    ep20_by_class = {c["class_name"]: c for c in ep20_data.get("per_class_epoch20", [])}

    comparison_table = []
    for c50 in per_class_metrics_ep50:
        cname = c50["class_name"]
        c20 = ep20_by_class.get(cname, {})

        p20 = c20.get("precision", 0.0)
        r20 = c20.get("recall", 0.0)
        m20 = c20.get("mAP50", 0.0)
        m95_20 = c20.get("mAP50_95", 0.0)

        p50 = c50["precision"]
        r50 = c50["recall"]
        m50 = c50["mAP50"]
        m95_50 = c50["mAP50_95"]

        comparison_table.append({
            "class_name": cname,
            "epoch20": {"precision": p20, "recall": r20, "mAP50": m20, "mAP50_95": m95_20},
            "epoch50": {"precision": p50, "recall": r50, "mAP50": m50, "mAP50_95": m95_50},
            "delta": {
                "precision": round(p50 - p20, 4),
                "recall": round(r50 - r20, 4),
                "mAP50": round(m50 - m20, 4),
                "mAP50_95": round(m95_50 - m95_20, 4)
            }
        })

    # 7. Analyze 50-epoch loss curves
    stage3_csv = save_dir / "results.csv"
    loss_analysis = analyze_loss_curves_all50(STAGE1_CSV, STAGE2_CSV, stage3_csv)

    # 8. Compile Comprehensive Payload
    summary_payload = {
        "overall_epoch50": {
            "mAP50": round(float(box_metrics.map50), 4),
            "mAP50_95": round(float(box_metrics.map), 4),
            "mean_precision": round(float(box_metrics.mp), 4),
            "mean_recall": round(float(box_metrics.mr), 4)
        },
        "per_class_epoch50": per_class_metrics_ep50,
        "comparison_epoch20_vs_epoch50": comparison_table,
        "loss_curve_analysis_all50": loss_analysis,
        "training_time_seconds": round(total_train_sec, 2),
        "speed": test_metrics.speed
    }

    with open(FINAL_EVAL_JSON, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)
    print(f"\nSaved Epoch 50 full evaluation to {FINAL_EVAL_JSON}", flush=True)

    # 9. Print Formatted Comparison Report
    print("\n" + "=" * 96, flush=True)
    print("FULL PER-CLASS COMPARISON REPORT: EPOCH 20 vs EPOCH 50 (UNSEEN TEST SPLIT)", flush=True)
    print("=" * 96, flush=True)
    print(f"{'Class Name':<22} | {'Metric':<10} | {'Epoch 20':<10} | {'Epoch 50':<10} | {'Change (Delta)':<15}")
    print("-" * 96, flush=True)
    for comp in comparison_table:
        cname = comp["class_name"]
        e20 = comp["epoch20"]
        e50 = comp["epoch50"]
        d = comp["delta"]

        r_sign = "+" if d["recall"] >= 0 else ""
        p_sign = "+" if d["precision"] >= 0 else ""
        m_sign = "+" if d["mAP50"] >= 0 else ""
        m95_sign = "+" if d["mAP50_95"] >= 0 else ""

        print(f"{cname:<22} | Recall     | {e20['recall']*100:>8.2f}% | {e50['recall']*100:>8.2f}% | {r_sign}{d['recall']*100:>+7.2f}%", flush=True)
        print(f"{'':<22} | Precision  | {e20['precision']*100:>8.2f}% | {e50['precision']*100:>8.2f}% | {p_sign}{d['precision']*100:>+7.2f}%", flush=True)
        print(f"{'':<22} | mAP@50     | {e20['mAP50']*100:>8.2f}% | {e50['mAP50']*100:>8.2f}% | {m_sign}{d['mAP50']*100:>+7.2f}%", flush=True)
        print(f"{'':<22} | mAP@50-95  | {e20['mAP50_95']*100:>8.2f}% | {e50['mAP50_95']*100:>8.2f}% | {m95_sign}{d['mAP50_95']*100:>+7.2f}%", flush=True)
        print("-" * 96, flush=True)

    # Highlight Peanut_Moldy
    pm = next((c for c in comparison_table if c["class_name"] == "Peanut_Moldy"), None)
    if pm:
        print("\n>>> PEANUT_MOLDY FINAL FOCUS:", flush=True)
        print(f"    Epoch 20 Recall    : {pm['epoch20']['recall']*100:.2f}%", flush=True)
        print(f"    Epoch 50 Recall    : {pm['epoch50']['recall']*100:.2f}%", flush=True)
        delta_r = pm['delta']['recall'] * 100
        direction = "IMPROVED" if delta_r > 0 else ("UNCHANGED" if delta_r == 0 else "DECREASED")
        print(f"    Recall Delta       : {delta_r:+.2f}% ({direction})", flush=True)
        print(f"    Epoch 20 mAP@50    : {pm['epoch20']['mAP50']*100:.2f}%", flush=True)
        print(f"    Epoch 50 mAP@50    : {pm['epoch50']['mAP50']*100:.2f}%", flush=True)
        delta_m = pm['delta']['mAP50'] * 100
        print(f"    mAP@50 Delta       : {delta_m:+.2f}%", flush=True)

    # Loss Curve Diagnostics
    diag = loss_analysis.get("diagnostics", {})
    if diag:
        print("\n" + "=" * 96, flush=True)
        print("LOSS CURVE TREND ANALYSIS ACROSS ALL 50 EPOCHS", flush=True)
        print("=" * 96, flush=True)
        print(f"  * Conclusion             : {diag.get('conclusion')}", flush=True)
        print(f"  * Train Cls Loss Trend   : Epochs 31-40 avg = {diag.get('avg_train_cls_epochs31_40')} -> Epochs 41-50 avg = {diag.get('avg_train_cls_epochs41_50')} ({diag.get('train_cls_change_pct'):+.2f}%)", flush=True)
        print(f"  * Val Cls Loss Trend     : Epochs 31-40 avg = {diag.get('avg_val_cls_epochs31_40')} -> Epochs 41-50 avg = {diag.get('avg_val_cls_epochs41_50')} ({diag.get('val_cls_change_pct'):+.2f}%)", flush=True)
        print(f"  * Val Box Loss Trend     : Epochs 31-40 avg = {diag.get('avg_val_box_epochs31_40')} -> Epochs 41-50 avg = {diag.get('avg_val_box_epochs41_50')} ({diag.get('val_box_change_pct'):+.2f}%)", flush=True)
        print(f"  * mAP@50 Trend           : Epochs 31-40 avg = {diag.get('avg_map50_epochs31_40')*100:.2f}% -> Epochs 41-50 avg = {diag.get('avg_map50_epochs41_50')*100:.2f}% ({diag.get('map50_change_pct'):+.2f}%)", flush=True)
        print(f"  * Assessment Detail      :\n    {diag.get('explanation')}", flush=True)
        print("=" * 96, flush=True)


if __name__ == "__main__":
    main()
