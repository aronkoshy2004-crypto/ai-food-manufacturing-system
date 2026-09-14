"""
Fresh YOLOv8 Training Pipeline on Corrected 5-Source Dataset (20 Epochs)
- Starting weights: yolov8n.pt (clean pre-trained backbone, NOT resuming from combined_best.pt)
- Target data: datasets/raw_materials_combined/data.yaml (3,487 images, 61,377 instances)
- Settings: batch=8, imgsz=416, device=cpu (threads=8, workers=0)
- Epochs: 20
- Protected files: models/best.pt and models/combined_best.pt strictly untouched
- Output weights: models/combined_corrected_best.pt
- Logging: per-class metrics every 5 epochs (epochs 5, 10, 15, 20)
- Post-training validation & specific verification on corn_20220327_0107_jpg
"""
import os
import sys
import gc
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
BASE_MODEL = PROJECT_ROOT / "yolov8n.pt"

CORRECTED_BEST_MODEL = MODELS_DIR / "combined_corrected_best.pt"
PROTECTED_BEST_MODEL = MODELS_DIR / "best.pt"
PROTECTED_COMBINED_BEST = MODELS_DIR / "combined_best.pt"

RUN_NAME = "raw_materials_corrected_fresh20"
RUN_DIR = PROJECT_ROOT / "runs" / "detect" / RUN_NAME
PROGRESS_LOG = PROJECT_ROOT / "scratch" / "training_corrected_progress.log"
PROGRESS_JSON = PROJECT_ROOT / "scratch" / "training_corrected_progress.json"
FINAL_EVAL_JSON = PROJECT_ROOT / "scratch" / "corrected_model_evaluation.json"

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


def create_progress_callback():
    last_logged_epoch = [-1]

    def on_fit_epoch_end(trainer):
        try:
            current_epoch = trainer.epoch + 1  # 1 to 20
            append_progress_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Completed Epoch {current_epoch}/{trainer.epochs}")

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
                lines.append(f"  [CHECKPOINT PROGRESS] FRESH TRAINING EPOCH {current_epoch}/{trainer.epochs}")
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
                # Corn metrics tracking
                cm = classes_data.get("Corn_Moldy")
                cnm = classes_data.get("Corn_Not_Moldy")
                if cm and cnm:
                    lines.append(f">>> CORN STATUS (Epoch {current_epoch}):")
                    lines.append(f"    Corn_Moldy     -> Recall: {cm['recall']*100:.2f}%, Precision: {cm['precision']*100:.2f}%, mAP50: {cm['mAP50']*100:.2f}%")
                    lines.append(f"    Corn_Not_Moldy -> Recall: {cnm['recall']*100:.2f}%, Precision: {cnm['precision']*100:.2f}%, mAP50: {cnm['mAP50']*100:.2f}%")
                lines.append("=" * 96)

                msg = "\n".join(lines)
                print(msg, flush=True)
                append_progress_log(msg)

                record = {
                    "epoch": current_epoch,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "classes": classes_data
                }
                update_progress_json(record)

        except Exception as e:
            print(f"[WARN] Error in on_fit_epoch_end callback: {e}", flush=True)

    return on_fit_epoch_end


def test_corn_false_positive_resolution(model_path: Path):
    """Evaluates the model specifically on the problem test image corn_20220327_0107_jpg."""
    print("\n" + "=" * 96)
    print("SPECIFIC VERIFICATION: HEALTHY CORN TEST IMAGE (corn_20220327_0107_jpg)")
    print("=" * 96)

    if not TEST_CORN_IMAGE.exists():
        print(f"[WARN] Test image {TEST_CORN_IMAGE} does not exist!")
        return {"status": "IMAGE_NOT_FOUND"}

    model = YOLO(str(model_path))
    res = model.predict(str(TEST_CORN_IMAGE), conf=0.25, verbose=False)[0]

    detected_classes = [int(b.cls[0].item()) for b in res.boxes]
    confs = [float(b.conf[0].item()) for b in res.boxes]

    moldy_count = detected_classes.count(2)  # 2 is Corn_Moldy
    clean_count = detected_classes.count(3)  # 3 is Corn_Not_Moldy

    print(f"Total detections at conf >= 0.25: {len(detected_classes)}")
    print(f"  - Detected Corn_Not_Moldy (Healthy): {clean_count}")
    print(f"  - Detected Corn_Moldy (False Positives): {moldy_count}")

    is_resolved = (moldy_count == 0)
    verdict = "RESOLVED" if is_resolved else f"PARTIAL ({moldy_count} false positives remaining)"
    print(f"\n>>> VERDICT: False-Positive Issue is {verdict}!")
    print("=" * 96)

    return {
        "test_image": str(TEST_CORN_IMAGE.name),
        "total_detections": len(detected_classes),
        "corn_not_moldy_count": clean_count,
        "corn_moldy_count": moldy_count,
        "is_resolved": is_resolved,
        "verdict": verdict
    }


def main():
    print("=" * 96)
    print("STARTING FRESH YOLOV8 TRAINING (20 EPOCHS) ON CORRECTED 5-SOURCE DATASET")
    print("=" * 96)
    print(f"  Base weights:        {BASE_MODEL}")
    print(f"  Data YAML:           {DATA_YAML}")
    print(f"  Output weights:      {CORRECTED_BEST_MODEL}")
    print(f"  Protected best:      {PROTECTED_BEST_MODEL}")
    print(f"  Protected combined:  {PROTECTED_COMBINED_BEST}")
    print("=" * 96)

    # 1. Record initial MD5 of protected models
    initial_best_md5 = get_file_md5(PROTECTED_BEST_MODEL)
    initial_combined_md5 = get_file_md5(PROTECTED_COMBINED_BEST)

    # 2. Reset progress log
    if PROGRESS_LOG.exists():
        PROGRESS_LOG.unlink()
    if PROGRESS_JSON.exists():
        PROGRESS_JSON.unlink()
    append_progress_log(f"Starting Fresh Training: 20 Epochs on Corrected Dataset at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 3. Initialize fresh YOLO model from yolov8n.pt
    model = YOLO(str(BASE_MODEL))
    callback = create_progress_callback()
    model.add_callback("on_fit_epoch_end", callback)

    start_train_time = time.time()

    # 4. Execute training
    train_results = model.train(
        data=str(DATA_YAML),
        epochs=20,
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
    print(f"\n Training completed in {train_duration/60:.2f} minutes.")

    # 5. Locate best.pt from this run
    save_dir = Path(train_results.save_dir) if hasattr(train_results, "save_dir") else RUN_DIR
    run_best_weights = save_dir / "weights" / "best.pt"
    if not run_best_weights.exists():
        run_best_weights = save_dir / "weights" / "last.pt"

    print(f"Trained run best weights located at: {run_best_weights}")

    # 6. Save strictly to combined_corrected_best.pt (do NOT overwrite combined_best.pt or best.pt)
    shutil.copy2(run_best_weights, CORRECTED_BEST_MODEL)
    print(f" Saved new weights to: {CORRECTED_BEST_MODEL}")

    # Verify protected models integrity
    post_best_md5 = get_file_md5(PROTECTED_BEST_MODEL)
    post_combined_md5 = get_file_md5(PROTECTED_COMBINED_BEST)
    assert initial_best_md5 == post_best_md5, "FAIL: Protected models/best.pt was modified!"
    assert initial_combined_md5 == post_combined_md5, "FAIL: Protected models/combined_best.pt was modified!"
    print(" Protected models models/best.pt and models/combined_best.pt remain completely untouched.")

    # 7. Evaluate on unseen test split
    print("\n--- Evaluating Corrected Model on Test Split ---")
    test_metrics = model.val(
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

    per_class_test = []
    for idx_pos, cid in enumerate(class_indices):
        cid_int = int(cid)
        cname = names.get(cid_int, f"Class_{cid_int}")
        p = round(float(p_array[idx_pos]), 4) if idx_pos < len(p_array) else 0.0
        r = round(float(r_array[idx_pos]), 4) if idx_pos < len(r_array) else 0.0
        ap50 = round(float(map50_array[idx_pos]), 4) if idx_pos < len(map50_array) else 0.0
        ap = round(float(map_array[idx_pos]), 4) if idx_pos < len(map_array) else 0.0
        per_class_test.append({
            "class_id": cid_int,
            "class_name": cname,
            "precision": p,
            "recall": r,
            "mAP50": ap50,
            "mAP50_95": ap
        })

    # 8. Test specifically on corn_20220327_0107_jpg
    corn_fp_test = test_corn_false_positive_resolution(CORRECTED_BEST_MODEL)

    # 9. Save final evaluation json
    eval_payload = {
        "model_path": str(CORRECTED_BEST_MODEL),
        "epochs": 20,
        "training_duration_seconds": round(train_duration, 2),
        "overall_test": {
            "mAP50": round(float(box_metrics.map50), 4),
            "mAP50_95": round(float(box_metrics.map), 4),
            "mean_precision": round(float(box_metrics.mp), 4),
            "mean_recall": round(float(box_metrics.mr), 4)
        },
        "per_class_test": per_class_test,
        "corn_false_positive_test": corn_fp_test
    }

    with open(FINAL_EVAL_JSON, "w", encoding="utf-8") as f:
        json.dump(eval_payload, f, indent=2)
    print(f"\nSaved full evaluation to {FINAL_EVAL_JSON}")

    # Print summary table
    print("\n" + "=" * 96)
    print("FINAL EVALUATION BREAKDOWN: UNSEEN TEST SPLIT")
    print("=" * 96)
    print(f"{'Class ID':<8} | {'Class Name':<22} | {'Precision':<11} | {'Recall':<11} | {'mAP@50':<11} | {'mAP@50-95':<11}")
    print("-" * 96)
    for c in per_class_test:
        print(f"{c['class_id']:<8} | {c['class_name']:<22} | {c['precision']*100:>9.2f}% | {c['recall']*100:>9.2f}% | {c['mAP50']*100:>9.2f}% | {c['mAP50_95']*100:>9.2f}%")
    print("=" * 96)


if __name__ == "__main__":
    main()
