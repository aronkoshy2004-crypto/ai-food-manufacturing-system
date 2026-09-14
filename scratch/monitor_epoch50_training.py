"""
Live Progress Monitor for Stage 3 Training (Epochs 21-50)
Usage: python scratch/monitor_epoch50_training.py
"""
import sys
import json
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROGRESS_LOG = PROJECT_ROOT / "scratch" / "training_epochs21_50_progress.log"
PROGRESS_JSON = PROJECT_ROOT / "scratch" / "training_epochs21_50_progress.json"
RESULTS_CSV = PROJECT_ROOT / "runs" / "detect" / "raw_materials_combined_resumed_epochs21_50" / "results.csv"
FINAL_EVAL_JSON = PROJECT_ROOT / "scratch" / "combined_epoch50_evaluation.json"


def main():
    print("=" * 80)
    print("STAGE 3 RESUMED TRAINING LIVE MONITOR (EPOCHS 21-50)")
    print("=" * 80)

    # 1. Check if complete
    if FINAL_EVAL_JSON.exists():
        print("[STATUS] Training and Evaluation COMPLETE!")
        try:
            with open(FINAL_EVAL_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            overall = data.get("overall_epoch50", {})
            print(f"Final Overall mAP@50: {overall.get('mAP50', 0)*100:.2f}% | mAP@50-95: {overall.get('mAP50_95', 0)*100:.2f}%")
            print(f"Full report available in: {FINAL_EVAL_JSON}")
        except Exception as e:
            print(f"Error reading final eval: {e}")
        return

    # 2. Check current epoch from results.csv
    current_stage3_epoch = 0
    if RESULTS_CSV.exists():
        try:
            with open(RESULTS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    last_row = rows[-1]
                    field_map = {k: k.strip() for k in reader.fieldnames}
                    cleaned = {field_map[k]: v.strip() for k, v in last_row.items()}
                    current_stage3_epoch = int(cleaned.get("epoch", 0))
                    cum_epoch = 20 + current_stage3_epoch
                    print(f"Current Completed Epoch : {current_stage3_epoch}/30 in Stage 3 (Cumulative Epoch {cum_epoch}/50)")
                    print(f"Last Train Box Loss     : {cleaned.get('train/box_loss', 'N/A')}")
                    print(f"Last Train Cls Loss     : {cleaned.get('train/cls_loss', 'N/A')}")
                    print(f"Last Val Box Loss       : {cleaned.get('val/box_loss', 'N/A')}")
                    print(f"Last Val Cls Loss       : {cleaned.get('val/cls_loss', 'N/A')}")
                    print(f"Last Validation mAP@50  : {float(cleaned.get('metrics/mAP50(B)', 0))*100:.2f}%")
        except Exception as e:
            print(f"[WARN] Reading results.csv: {e}")
    else:
        print("[STATUS] Training initializing or running first epoch...")

    # 3. Check 5-Epoch Checkpoint History
    if PROGRESS_JSON.exists():
        try:
            with open(PROGRESS_JSON, "r", encoding="utf-8") as f:
                checkpoints = json.load(f)
            print(f"\nRecorded Checkpoints ({len(checkpoints)}):")
            for cp in checkpoints:
                cum_ep = cp.get("cumulative_epoch")
                pm = cp.get("classes", {}).get("Peanut_Moldy", {})
                rec = pm.get("recall", 0) * 100
                prec = pm.get("precision", 0) * 100
                m50 = pm.get("mAP50", 0) * 100
                print(f"  * Cumulative Epoch {cum_ep}: Peanut_Moldy -> Recall: {rec:.2f}%, Precision: {prec:.2f}%, mAP@50: {m50:.2f}%")
        except Exception as e:
            print(f"[WARN] Reading progress json: {e}")

    # 4. Show last section of progress log
    if PROGRESS_LOG.exists():
        try:
            with open(PROGRESS_LOG, "r", encoding="utf-8") as f:
                lines = f.readlines()
            print("\n--- Latest Log Output ---")
            print("".join(lines[-25:]))
        except Exception as e:
            print(f"[WARN] Reading progress log: {e}")

    print("=" * 80)


if __name__ == "__main__":
    main()
