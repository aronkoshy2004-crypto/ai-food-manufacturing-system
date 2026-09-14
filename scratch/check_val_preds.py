import json
import os
from pathlib import Path
from collections import defaultdict
import numpy as np

PROJECT_ROOT = Path(r"c:\Users\L E N O V O\Food man")
VAL_LBL_DIR = PROJECT_ROOT / "datasets" / "raw_materials_combined" / "labels" / "val"
PRED_JSON = PROJECT_ROOT / "runs" / "detect" / "val-8" / "predictions.json"

CLASS_NAMES = [
    "Peanut_Moldy",
    "Peanut_Not_Moldy",
    "Corn_Moldy",
    "Corn_Not_Moldy",
    "Sunflower_Moldy",
    "Sunflower_Not_Moldy"
]

def bb_intersection_over_union(boxA, boxB):
    # box format: [x1, y1, x2, y2]
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
    return iou

def load_ground_truth():
    gt = defaultdict(list)
    # image resolution in test/val is 640x640 or 416x416. YOLO predictions.json bboxes are in pixels
    # In YOLO predictions.json, bbox is [x, y, w, h] or [x1, y1, w, h] or [x1, y1, x2, y2].
    # Let's check format: 'bbox': [220.883, 283.639, 419.117, 356.361]
    # For a 640x640 image, x1=220, y1=283, w=419, h=356 or x2=419?
    # Notice x2=419.117 > 220.883, y2=356.361 > 283.639.
    return gt

def inspect_pred_bbox():
    with open(PRED_JSON, "r") as f:
        preds = json.load(f)
    print(f"Loaded {len(preds)} predictions")
    for p in preds[:5]:
        print(p["file_name"], "cat:", p["category_id"], "score:", p["score"], "bbox:", p["bbox"])

if __name__ == "__main__":
    inspect_pred_bbox()
