"""
YOLOv8 Stage 4 Fine-Tuning on Expanded Dataset (105,241 instances)
Resumes training from models/combined_best.pt (Epoch 50) for 20 additional epochs
on the newly expanded datasets/raw_materials_combined/data.yaml.

Settings:
  - Batch size: 8
  - Resolution: 416
  - Device: CPU (torch threads: 8, workers: 0)
  - Starting weights: models/combined_best.pt (Epoch 50)
  - Protected models:
      models/best.pt (strictly untouched, verified via MD5)
      models/combined_epoch20_backup.pt (untouched)
      models/combined_epoch50_backup.pt (untouched)
  - New Backup checkpoint: models/combined_epoch50_expanded20_backup.pt
  - Updated production weights: models/combined_best.pt

Logging:
  - Every 5 epochs (epochs 5, 10, 15, 20): Full per-class precision/recall/mAP50/mAP50-95
  - Tracking Corn_Moldy & Corn_Not_Moldy gains, plus monitoring Peanut & Sunflower stability

Post-Training Analysis:
  - Full per-class evaluation on unseen test split (all 6 classes)
  - Comparison table: Pre-expansion Epoch 50 vs Post-expansion 20 Epochs
  - Loss curve trend analysis across the fine-tuning run
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
NEW_BACKUP_MODEL = MODELS_DIR / "combined_epoch50_expanded20_backup.pt"
EXISTING_BEST_MODEL = MODELS_DIR / "best.pt"

# Baseline Epoch 50 evaluation
PRE_EXPANSION_EVAL_JSON = PROJECT_ROOT / "scratch" / "combined_epoch50_evaluation.json"

# Output dirs and log files
RUN_NAME = "raw_materials_expanded_stage4"
RUN_DIR = PROJECT_ROOT / "runs" / "detect" / RUN_NAME
PROGRESS_LOG = PROJECT_ROOT / "scratch" / "training_stage4_expanded_progress.log"
PROGRESS_JSON = PROJECT_ROOT / "scratch" / "training_stage4_expanded_progress.json"
FINAL_EVAL_JSON = PROJECT_ROOT / "scratch" / "expanded_stage4_evaluation.json"


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


def create_progress_callback():
    last_logged_epoch = [-1]

    def on_fit_epoch_end(trainer):
        try:
            current_epoch = trainer.epoch + 1  # 1 to 20
            cumulative_epoch = 50 + current_epoch  # 51 to 70

            # Single-line log for every epoch
            append_progress_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Completed Stage 4 Epoch {current_epoch}/{trainer.epochs} (Cumulative {cumulative_epoch}/70)")

            # Checkpoint every 5 epochs or on the very last epoch
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
                lines.append("\n" + "=" * 96)
                lines.append(f"  [STAGE 4 PROGRESS] EPOCH {current_epoch}/{trainer.epochs} | CUMULATIVE EPOCH {cumulative_epoch}/70 (EXPANDED DATASET)")
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
                # Corn focus
                cm = classes_data.get("Corn_Moldy", {})
                cn = classes_data.get("Corn_Not_Moldy", {})
                pm = classes_data.get("Peanut_Moldy", {})
                sm = classes_data.get("Sunflower_Moldy", {})

                lines.append(f">>> CORN EXPANSION TRACKING:")
                lines.append(f"    Corn_Moldy     -> Recall: {cm.get('recall',0)*100:.2f}%, Precision: {cm.get('precision',0)*100:.2f}%, mAP@50: {cm.get('mAP50',0)*100:.2f}%")
                lines.append(f"    Corn_Not_Moldy -> Recall: {cn.get('recall',0)*100:.2f}%, Precision: {cn.get('precision',0)*100:.2f}%, mAP@50: {cn.get('mAP50',0)*100:.2f}%")
                lines.append(f">>> PEANUT & SUNFLOWER STABILITY TRACKING:")
                lines.append(f"    Peanut_Moldy    -> Recall: {pm.get('recall',0)*100:.2f}%, Precision: {pm.get('precision',0)*100:.2f}%, mAP@50: {pm.get('mAP50',0)*100:.2f}%")
                lines.append(f"    Sunflower_Moldy -> Recall: {sm.get('recall',0)*100:.2f}%, Precision: {sm.get('precision',0)*100:.2f}%, mAP@50: {sm.get('mAP50',0)*100:.2f}%")
                lines.append("=" * 96)

                msg = "\n".join(lines)
                print(msg, flush=True)
                append_progress_log(msg)

                record = {
                    "stage4_epoch": current_epoch,
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


def analyze_stage4_loss(results_csv: Path):
    if not results_csv.exists():
        return {"error": "results.csv not found"}

    rows = []
    with open(results_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        field_map = {k: k.strip() for k in reader.fieldnames}
        for r in reader:
            cleaned = {field_map[k]: v.strip() for k, v in r.items()}
            rows.append({
                "epoch": int(cleaned.get("epoch", 0)),
                "train_box_loss": float(cleaned.get("train/box_loss", 0.0)),
                "train_cls_loss": float(cleaned.get("train/cls_loss", 0.0)),
                "train_dfl_loss": float(cleaned.get("train/dfl_loss", 0.0)),
                "val_box_loss": float(cleaned.get("val/box_loss", 0.0)),
                "val_cls_loss": float(cleaned.get("val/cls_loss", 0.0)),
                "val_dfl_loss": float(cleaned.get("val/dfl_loss", 0.0)),
                "mAP50": float(cleaned.get("metrics/mAP50(B)", 0.0)),
                "mAP50_95": float(cleaned.get("metrics/mAP50-95(B)", 0.0)),
            })

    if len(rows) < 4:
        return {"history": rows, "conclusion": "INSUFFICIENT_EPOCHS"}

    first_half = rows[:len(rows)//2]
    second_half = rows[len(rows)//2:]

    avg_train_cls_1 = sum(r["train_cls_loss"] for r in first_half) / len(first_half)
    avg_train_cls_2 = sum(r["train_cls_loss"] for r in second_half) / len(second_half)
    train_cls_rate = ((avg_train_cls_2 - avg_train_cls_1) / avg_train_cls_1) * 100

    avg_val_cls_1 = sum(r["val_cls_loss"] for r in first_half) / len(first_half)
    avg_val_cls_2 = sum(r["val_cls_loss"] for r in second_half) / len(second_half)
    val_cls_rate = ((avg_val_cls_2 - avg_val_cls_1) / avg_val_cls_1) * 100

    avg_map50_1 = sum(r["mAP50"] for r in first_half) / len(first_half)
    avg_map50_2 = sum(r["mAP50"] for r in second_half) / len(second_half)
    map50_rate = ((avg_map50_2 - avg_map50_1) / avg_map50_1) * 100

    if val_cls_rate < -2.0 and map50_rate > 0.5:
        conclusion = "STILL_IMPROVING"
        explanation = (
            f"Validation classification loss decreased by {val_cls_rate:.2f}% between the first half "
            f"and second half of fine-tuning, while validation mAP@50 improved by +{map50_rate:.2f}%. "
            "The model continues to extract discriminative features from the expanded dataset without overfitting."
        )
    elif abs(val_cls_rate) <= 2.5:
        conclusion = "PLATEAUED_NEAR_OPTIMAL"
        explanation = (
            f"Validation loss change has flattened ({val_cls_rate:+.2f}%) with mAP@50 stabilizing "
            f"({avg_map50_2*100:.2f}%). The fine-tuning has converged on the expanded data."
        )
    else:
        conclusion = "CONVERGING"
        explanation = f"Losses are leveling off. Train cls loss delta: {train_cls_rate:+.2f}%, Val cls loss delta: {val_cls_rate:+.2f}%."

    return {
        "total_epochs": len(rows),
        "history": rows,
        "diagnostics": {
            "avg_train_cls_first_half": round(avg_train_cls_1, 4),
            "avg_train_cls_second_half": round(avg_train_cls_2, 4),
            "train_cls_change_pct": round(train_cls_rate, 2),
            "avg_val_cls_first_half": round(avg_val_cls_1, 4),
            "avg_val_cls_second_half": round(avg_val_cls_2, 4),
            "val_cls_change_pct": round(val_cls_rate, 2),
            "avg_map50_first_half": round(avg_map50_1, 4),
            "avg_map50_second_half": round(avg_map50_2, 4),
            "map50_change_pct": round(map50_rate, 2),
            "conclusion": conclusion,
            "explanation": explanation
        }
    }


def main():
    print("=" * 96, flush=True)
    print("STAGE 4 YOLOv8 FINE-TUNING ON EXPANDED DATASET (20 EPOCHS)", flush=True)
    print("=" * 96, flush=True)

    # 1. Baseline integrity checks
    if not COMBINED_BEST_MODEL.exists():
        print(f"ERROR: Base weights not found at {COMBINED_BEST_MODEL}", flush=True)
        sys.exit(1)

    pre_train_best_md5 = get_file_md5(EXISTING_BEST_MODEL)
    pre_train_ep20_md5 = get_file_md5(EPOCH20_BACKUP_MODEL)
    pre_train_ep50_md5 = get_file_md5(EPOCH50_BACKUP_MODEL)
    pre_train_combined_md5 = get_file_md5(COMBINED_BEST_MODEL)

    print(f"Pre-training models/best.pt MD5               : {pre_train_best_md5} (PROTECTED)", flush=True)
    print(f"Pre-training models/combined_epoch20_backup.pt: {pre_train_ep20_md5} (PROTECTED)", flush=True)
    print(f"Pre-training models/combined_epoch50_backup.pt: {pre_train_ep50_md5} (PROTECTED)", flush=True)
    print(f"Starting weights models/combined_best.pt MD5   : {pre_train_combined_md5} (Epoch 50 Base)", flush=True)

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

    append_progress_log(f"Starting Stage 4 Fine-Tuning: 20 Epochs on Expanded Dataset at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    from ultralytics import YOLO

    torch.set_num_threads(8)
    gc.collect()

    epochs = 20
    batch = 8
    imgsz = 416

    print(f"\n[STARTING FINE-TUNING CONFIGURATION]", flush=True)
    print(f"  - Starting Weights : {COMBINED_BEST_MODEL} (Cumulative Epoch 50)", flush=True)
    print(f"  - Dataset          : {DATA_YAML} (Expanded: 4,697 images, 105,241 instances)", flush=True)
    print(f"  - Additional Epochs: {epochs} (Cumulative Epochs 51-70)", flush=True)
    print(f"  - Batch size       : {batch}", flush=True)
    print(f"  - Image size       : {imgsz}", flush=True)
    print(f"  - Device           : cpu (torch threads: 8, workers: 0)", flush=True)
    print(f"  - Output Dir       : {RUN_DIR}", flush=True)
    print(f"  - Protected Model  : {EXISTING_BEST_MODEL} (strictly untouched)", flush=True)

    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR, ignore_errors=True)

    model = YOLO(str(COMBINED_BEST_MODEL))

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
    print(f"STAGE 4 TRAINING COMPLETED IN {total_train_sec/3600:.2f} HOURS", flush=True)
    print("=" * 96, flush=True)

    if not new_best_weights.exists():
        print(f"ERROR: Could not locate new best weights at {new_best_weights}", flush=True)
        sys.exit(1)

    # 3. Checkpoint Backups & Production Weights Update
    shutil.copy2(new_best_weights, NEW_BACKUP_MODEL)
    print(f"[CHECKPOINT] Preserved new backup at: {NEW_BACKUP_MODEL}", flush=True)

    shutil.copy2(new_best_weights, COMBINED_BEST_MODEL)
    print(f"[CHECKPOINT] Updated models/combined_best.pt with new best fine-tuned weights!", flush=True)

    # 4. Strict MD5 integrity verification on protected models
    post_train_best_md5 = get_file_md5(EXISTING_BEST_MODEL)
    post_train_ep20_md5 = get_file_md5(EPOCH20_BACKUP_MODEL)
    post_train_ep50_md5 = get_file_md5(EPOCH50_BACKUP_MODEL)

    assert pre_train_best_md5 == post_train_best_md5, "CRITICAL: models/best.pt was modified!"
    assert pre_train_ep20_md5 == post_train_ep20_md5, "CRITICAL: models/combined_epoch20_backup.pt was modified!"
    assert pre_train_ep50_md5 == post_train_ep50_md5, "CRITICAL: models/combined_epoch50_backup.pt was modified!"
    print("[VERIFIED] All protected checkpoints (best.pt, epoch20_backup.pt, epoch50_backup.pt) are 100% UNTOUCHED.", flush=True)

    # 5. Full Evaluation on Unseen Test Split
    print("\n" + "=" * 96, flush=True)
    print("EVALUATING UPDATED MODEL (STAGE 4 EXPANDED) ON UNSEEN TEST SPLIT", flush=True)
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

    per_class_metrics_post = []
    for idx_pos, cid in enumerate(class_indices):
        cid_int = int(cid)
        cname = names.get(cid_int, f"Class_{cid_int}")
        p = round(float(p_array[idx_pos]), 4) if idx_pos < len(p_array) else 0.0
        r = round(float(r_array[idx_pos]), 4) if idx_pos < len(r_array) else 0.0
        ap50 = round(float(map50_array[idx_pos]), 4) if idx_pos < len(map50_array) else 0.0
        ap = round(float(map_array[idx_pos]), 4) if idx_pos < len(map_array) else 0.0
        per_class_metrics_post.append({
            "class_id": cid_int,
            "class_name": cname,
            "precision": p,
            "recall": r,
            "mAP50": ap50,
            "mAP50_95": ap
        })

    # 6. Load Pre-Expansion Epoch 50 evaluation for side-by-side comparison
    ep50_data = {}
    if PRE_EXPANSION_EVAL_JSON.exists():
        try:
            with open(PRE_EXPANSION_EVAL_JSON, "r", encoding="utf-8") as f:
                ep50_data = json.load(f)
        except Exception as e:
            print(f"Warning reading Epoch 50 data: {e}", flush=True)

    ep50_by_class = {c["class_name"]: c for c in ep50_data.get("per_class_epoch50", [])}

    comparison_table = []
    for c_post in per_class_metrics_post:
        cname = c_post["class_name"]
        c50 = ep50_by_class.get(cname, {})

        p50 = c50.get("precision", 0.0)
        r50 = c50.get("recall", 0.0)
        m50 = c50.get("mAP50", 0.0)
        m95_50 = c50.get("mAP50_95", 0.0)

        p_new = c_post["precision"]
        r_new = c_post["recall"]
        m_new = c_post["mAP50"]
        m95_new = c_post["mAP50_95"]

        comparison_table.append({
            "class_name": cname,
            "pre_expansion_epoch50": {"precision": p50, "recall": r50, "mAP50": m50, "mAP50_95": m95_50},
            "post_expansion_epoch20": {"precision": p_new, "recall": r_new, "mAP50": m_new, "mAP50_95": m95_new},
            "delta": {
                "precision": round(p_new - p50, 4),
                "recall": round(r_new - r50, 4),
                "mAP50": round(m_new - m50, 4),
                "mAP50_95": round(m95_new - m95_50, 4)
            }
        })

    # 7. Analyze Stage 4 loss curves
    stage4_csv = save_dir / "results.csv"
    loss_analysis = analyze_stage4_loss(stage4_csv)

    # 8. Compile Comprehensive Payload
    summary_payload = {
        "overall_stage4_expanded": {
            "mAP50": round(float(box_metrics.map50), 4),
            "mAP50_95": round(float(box_metrics.map), 4),
            "mean_precision": round(float(box_metrics.mp), 4),
            "mean_recall": round(float(box_metrics.mr), 4)
        },
        "per_class_stage4_expanded": per_class_metrics_post,
        "comparison_pre_expansion_ep50_vs_post_expansion": comparison_table,
        "loss_curve_analysis_stage4": loss_analysis,
        "training_time_seconds": round(total_train_sec, 2),
        "speed": test_metrics.speed
    }

    with open(FINAL_EVAL_JSON, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)
    print(f"\nSaved Stage 4 full evaluation to {FINAL_EVAL_JSON}", flush=True)

    # 9. Print Formatted Comparison Report
    print("\n" + "=" * 96, flush=True)
    print("COMPARISON REPORT: PRE-EXPANSION EPOCH 50 vs POST-EXPANSION (UNSEEN TEST SPLIT)", flush=True)
    print("=" * 96, flush=True)
    print(f"{'Class Name':<22} | {'Metric':<10} | {'Pre-Exp Ep50':<12} | {'Post-Exp Ep20':<13} | {'Change (Delta)':<15}")
    print("-" * 96, flush=True)
    for comp in comparison_table:
        cname = comp["class_name"]
        e50 = comp["pre_expansion_epoch50"]
        enew = comp["post_expansion_epoch20"]
        d = comp["delta"]

        r_sign = "+" if d["recall"] >= 0 else ""
        p_sign = "+" if d["precision"] >= 0 else ""
        m_sign = "+" if d["mAP50"] >= 0 else ""
        m95_sign = "+" if d["mAP50_95"] >= 0 else ""

        print(f"{cname:<22} | Recall     | {e50['recall']*100:>10.2f}% | {enew['recall']*100:>11.2f}% | {r_sign}{d['recall']*100:>+7.2f}%", flush=True)
        print(f"{'':<22} | Precision  | {e50['precision']*100:>10.2f}% | {enew['precision']*100:>11.2f}% | {p_sign}{d['precision']*100:>+7.2f}%", flush=True)
        print(f"{'':<22} | mAP@50     | {e50['mAP50']*100:>10.2f}% | {enew['mAP50']*100:>11.2f}% | {m_sign}{d['mAP50']*100:>+7.2f}%", flush=True)
        print(f"{'':<22} | mAP@50-95  | {e50['mAP50_95']*100:>10.2f}% | {enew['mAP50_95']*100:>11.2f}% | {m95_sign}{d['mAP50_95']*100:>+7.2f}%", flush=True)
        print("-" * 96, flush=True)

    # 10. Specific Highlight Analysis
    cm = next((c for c in comparison_table if c["class_name"] == "Corn_Moldy"), None)
    cn = next((c for c in comparison_table if c["class_name"] == "Corn_Not_Moldy"), None)
    pm = next((c for c in comparison_table if c["class_name"] == "Peanut_Moldy"), None)
    sm = next((c for c in comparison_table if c["class_name"] == "Sunflower_Moldy"), None)

    print("\n>>> CORN SPECIFIC IMPACT (ADDED DATA EFFECT):", flush=True)
    if cm:
        print(f"    Corn_Moldy Recall      : {cm['pre_expansion_epoch50']['recall']*100:.2f}% -> {cm['post_expansion_epoch20']['recall']*100:.2f}% (Delta: {cm['delta']['recall']*100:+.2f}%)", flush=True)
        print(f"    Corn_Moldy mAP@50      : {cm['pre_expansion_epoch50']['mAP50']*100:.2f}% -> {cm['post_expansion_epoch20']['mAP50']*100:.2f}% (Delta: {cm['delta']['mAP50']*100:+.2f}%)", flush=True)
    if cn:
        print(f"    Corn_Not_Moldy Recall  : {cn['pre_expansion_epoch50']['recall']*100:.2f}% -> {cn['post_expansion_epoch20']['recall']*100:.2f}% (Delta: {cn['delta']['recall']*100:+.2f}%)", flush=True)
        print(f"    Corn_Not_Moldy mAP@50  : {cn['pre_expansion_epoch50']['mAP50']*100:.2f}% -> {cn['post_expansion_epoch20']['mAP50']*100:.2f}% (Delta: {cn['delta']['mAP50']*100:+.2f}%)", flush=True)

    print("\n>>> STABILITY & NON-REGRESSION CHECK (PEANUT & SUNFLOWER):", flush=True)
    if pm:
        print(f"    Peanut_Moldy Recall    : {pm['pre_expansion_epoch50']['recall']*100:.2f}% -> {pm['post_expansion_epoch20']['recall']*100:.2f}% (Delta: {pm['delta']['recall']*100:+.2f}%)", flush=True)
        print(f"    Peanut_Moldy mAP@50    : {pm['pre_expansion_epoch50']['mAP50']*100:.2f}% -> {pm['post_expansion_epoch20']['mAP50']*100:.2f}% (Delta: {pm['delta']['mAP50']*100:+.2f}%)", flush=True)
    if sm:
        print(f"    Sunflower_Moldy Recall : {sm['pre_expansion_epoch50']['recall']*100:.2f}% -> {sm['post_expansion_epoch20']['recall']*100:.2f}% (Delta: {sm['delta']['recall']*100:+.2f}%)", flush=True)
        print(f"    Sunflower_Moldy mAP@50 : {sm['pre_expansion_epoch50']['mAP50']*100:.2f}% -> {sm['post_expansion_epoch20']['mAP50']*100:.2f}% (Delta: {sm['delta']['mAP50']*100:+.2f}%)", flush=True)

    diag = loss_analysis.get("diagnostics", {})
    if diag:
        print("\n" + "=" * 96, flush=True)
        print("STAGE 4 LOSS CURVE TREND ANALYSIS", flush=True)
        print("=" * 96, flush=True)
        print(f"  * Conclusion             : {diag.get('conclusion')}", flush=True)
        print(f"  * Train Cls Loss Trend   : First half avg = {diag.get('avg_train_cls_first_half')} -> Second half avg = {diag.get('avg_train_cls_second_half')} ({diag.get('train_cls_change_pct'):+.2f}%)", flush=True)
        print(f"  * Val Cls Loss Trend     : First half avg = {diag.get('avg_val_cls_first_half')} -> Second half avg = {diag.get('avg_val_cls_second_half')} ({diag.get('val_cls_change_pct'):+.2f}%)", flush=True)
        print(f"  * mAP@50 Trend           : First half avg = {diag.get('avg_map50_first_half')*100:.2f}% -> Second half avg = {diag.get('avg_map50_second_half')*100:.2f}% ({diag.get('map50_change_pct'):+.2f}%)", flush=True)
        print(f"  * Assessment Detail      :\n    {diag.get('explanation')}", flush=True)
        print("=" * 96, flush=True)


if __name__ == "__main__":
    main()
