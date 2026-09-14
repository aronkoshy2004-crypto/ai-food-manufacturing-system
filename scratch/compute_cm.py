import json
import os
from pathlib import Path
from collections import defaultdict
import numpy as np

PROJECT_ROOT = Path(r"c:\Users\L E N O V O\Food man")
TEST_LBL_DIR = PROJECT_ROOT / "datasets" / "raw_materials_combined" / "labels" / "test"
PRED_JSON = PROJECT_ROOT / "runs" / "detect" / "val-8" / "predictions.json"

CLASS_NAMES = [
    "Peanut_Moldy",
    "Peanut_Not_Moldy",
    "Corn_Moldy",
    "Corn_Not_Moldy",
    "Sunflower_Moldy",
    "Sunflower_Not_Moldy"
]

def compute_confusion_matrix(conf_thresh=0.25, iou_thresh=0.45):
    matrix = np.zeros((7, 7), dtype=int)
    
    with open(PRED_JSON, "r") as f:
        all_preds = json.load(f)
        
    preds_by_img = defaultdict(list)
    for p in all_preds:
        if p["score"] >= conf_thresh:
            stem = Path(p["file_name"]).stem
            x, y, w, h = p["bbox"]
            box = [x, y, x + w, y + h]
            # category_id in COCO json is 1-indexed (1..6) -> map to 0..5
            cls_0indexed = p["category_id"] - 1
            preds_by_img[stem].append({
                "cls": cls_0indexed,
                "score": p["score"],
                "box": box
            })
            
    gt_by_img = defaultdict(list)
    for lf in TEST_LBL_DIR.glob("*.txt"):
        stem = lf.stem
        with open(lf, "r") as f:
            for line in f:
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    cid = int(parts[0])
                    # normalized cx, cy, w, h -> 640 coords
                    cx, cy, w, h = float(parts[1])*640, float(parts[2])*640, float(parts[3])*640, float(parts[4])*640
                    box = [cx - w/2, cy - h/2, cx + w/2, cy + h/2]
                    gt_by_img[stem].append({
                        "cls": cid,
                        "box": box
                    })

    all_stems = set(gt_by_img.keys()).union(preds_by_img.keys())

    for stem in all_stems:
        gts = gt_by_img.get(stem, [])
        preds = sorted(preds_by_img.get(stem, []), key=lambda x: x["score"], reverse=True)
        
        matched_gt = set()
        matched_pred = set()
        
        for p_idx, p in enumerate(preds):
            best_iou = 0
            best_g_idx = -1
            for g_idx, g in enumerate(gts):
                if g_idx in matched_gt:
                    continue
                xA = max(p["box"][0], g["box"][0])
                yA = max(p["box"][1], g["box"][1])
                xB = min(p["box"][2], g["box"][2])
                yB = min(p["box"][3], g["box"][3])
                inter = max(0, xB - xA) * max(0, yB - yA)
                areaA = (p["box"][2] - p["box"][0]) * (p["box"][3] - p["box"][1])
                areaB = (g["box"][2] - g["box"][0]) * (g["box"][3] - g["box"][1])
                iou = inter / float(areaA + areaB - inter + 1e-6)
                if iou > best_iou:
                    best_iou = iou
                    best_g_idx = g_idx
                    
            if best_iou >= iou_thresh:
                matched_gt.add(best_g_idx)
                matched_pred.add(p_idx)
                gt_cls = gts[best_g_idx]["cls"]
                pred_cls = p["cls"]
                matrix[gt_cls, pred_cls] += 1
            else:
                matrix[6, p["cls"]] += 1
                
        for g_idx, g in enumerate(gts):
            if g_idx not in matched_gt:
                matrix[g["cls"], 6] += 1

    print("=" * 85)
    print(f"CONFUSION MATRIX (IoU={iou_thresh}, Conf={conf_thresh})")
    print("=" * 85)
    header_names = [CLASS_NAMES[i][:9] for i in range(6)] + ["Backgrd"]
    print(f"{'GT \\ Pred':<12} | " + " | ".join([f"{h:<9}" for h in header_names]))
    print("-" * 88)
    for i in range(7):
        row_name = CLASS_NAMES[i][:11] if i < 6 else "Background"
        row_vals = " | ".join([f"{matrix[i, j]:<9}" for j in range(7)])
        print(f"{row_name:<12} | {row_vals}")
    print("-" * 88)
    
    print("\n" + "=" * 85)
    print("NORMALIZED CONFUSION MATRIX (Row-wise Recall %)")
    print("=" * 85)
    print(f"{'GT \\ Pred':<12} | " + " | ".join([f"{h:<9}" for h in header_names]))
    print("-" * 88)
    for i in range(6):
        row_sum = np.sum(matrix[i, :])
        row_name = CLASS_NAMES[i][:11]
        row_pcts = [f"{(matrix[i, j] / max(1, row_sum))*100:6.1f}%   " for j in range(7)]
        print(f"{row_name:<12} | " + " | ".join(row_pcts))

if __name__ == "__main__":
    compute_confusion_matrix()
