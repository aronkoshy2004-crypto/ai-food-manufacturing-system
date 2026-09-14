"""
Live Progress Monitor for Stage 4 Expanded Fine-Tuning (20 Epochs)
Usage: python scratch/monitor_stage4_training.py
"""
import sys
import json
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROGRESS_LOG = PROJECT_ROOT / "scratch" / "training_stage4_expanded_progress.log"
PROGRESS_JSON = PROJECT_ROOT / "scratch" / "training_stage4_expanded_progress.json"
RESULTS_CSV = PROJECT_ROOT / "runs" / "detect" / "raw_materials_expanded_stage4" / "results.csv"
FINAL_EVAL_JSON = PROJECT_ROOT / "scratch" / "expanded_stage4_evaluation.json"


def main():
    print("=" * 80)
    print("STAGE 4 FINE-TUNING LIVE MONITOR (EXPANDED DATASET: 20 EPOCHS)")
    print("=" * 80)

    # 1. Check if complete
    if FINAL_EVAL_JSON.exists():
        print("[STATUS] Stage 4 Fine-Tuning and Evaluation COMPLETE!")
        try:
            with open(FINAL_EVAL_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            overall = data.get("overall_stage4_expanded", {})
            print(f"Final Overall mAP@50: {overall.get('mAP50', 0)*100:.2f}% | mAP@50-95: {overall.get('mAP50_95', 0)*100:.2f}%")
            print(f"Full report available in: {FINAL_EVAL_JSON}")
        except Exception as e:
            print(f"Error reading final eval: {e}")
        return

    # 2. Check current epoch from results.csv
    if RESULTS_CSV.exists():
        try:
            with open(RESULTS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    last_row = rows[-1]
                    field_map = {k: k.strip() for k in reader.fieldnames}
                    cleaned = {field_map[k]: v.strip() for k, v in last_row.items()}
                    ep = int(cleaned.get("epoch", 0))
                    cum_ep = 50 + ep
                    print(f"Current Completed Epoch : {ep}/20 in Stage 4 (Cumulative Epoch {cum_ep}/70)")
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
                ep = cp.get("stage4_epoch")
                cum_ep = cp.get("cumulative_epoch")
                cm = cp.get("classes", {}).get("Corn_Moldy", {})
                cn = cp.get("classes", {}).get("Corn_Not_Moldy", {})
                pm = cp.get("classes", {}).get("Peanut_Moldy", {})
                sm = cp.get("classes", {}).get("Sunflower_Moldy", {})
                print(f"\n  * Stage 4 Epoch {ep}/20 (Cumulative Epoch {cum_ep}/70):")
                print(f"    - Corn_Moldy     -> Recall: {cm.get('recall',0)*100:.2f}%, Precision: {cm.get('precision',0)*100:.2f}%, mAP@50: {cm.get('mAP50',0)*100:.2f}%")
                print(f"    - Corn_Not_Moldy -> Recall: {cn.get('recall',0)*100:.2f}%, Precision: {cn.get('precision',0)*100:.2f}%, mAP@50: {cn.get('mAP50',0)*100:.2f}%")
                print(f"    - Peanut_Moldy   -> Recall: {pm.get('recall',0)*100:.2f}%, Precision: {pm.get('precision',0)*100:.2f}%, mAP@50: {pm.get('mAP50',0)*100:.2f}%")
                print(f"    - Sunflower_Moldy-> Recall: {sm.get('recall',0)*100:.2f}%, Precision: {sm.get('precision',0)*100:.2f}%, mAP@50: {sm.get('mAP50',0)*100:.2f}%")
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
