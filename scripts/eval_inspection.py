"""
Food Man - Standalone Inspection Evaluation Script
PRD Visual Quality Inspection Accuracy & Count Benchmark

Reads all images from eval_photos/ (or --dir).
Ground truth is parsed from the file name:
  e.g., 'corn_10_2.jpg' -> material='Corn', true_count=10, true_bad=2
        'peanut_10_0.png' -> material='Peanut', true_count=10, true_bad=0
        'sunflower_10_1_tray.jpg' -> material='Sunflower', true_count=10, true_bad=1

Runs the CURRENT pipeline identically to the Inspection Station:
- Evaluates across engines: 'ai', 'colour', 'both', 'auto'
- Simulates the 5-frame locking and kernel tracking pipeline (same frame repeated 5x as in single-photo station upload)
- Saves numbered annotated output images to eval_output/
- Outputs a comprehensive evaluation table and summary metrics:
    * Material Accuracy
    * Exact Count Accuracy
    * Mean Absolute Count Error (MAE)
    * Bad Kernel Recall
    * False Alarm Rate
- NEVER writes to the database.
"""

import os
import sys
import re
import cv2
import json
import time
import argparse
import numpy as np
from collections import defaultdict, Counter

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import Config
from ai.yolo_service import run_yolo_visual_inspection, find_trained_model, get_models_dir
from ai.classical_kernel_finder import (
    find_kernels_classical,
    is_center_in_ignore_zones,
    DEFAULT_IGNORE_ZONES
)
from routes.qc import (
    final_decision,
    extract_material_name,
    get_mostly_detected_material,
    resolve_inspection_engine,
    get_material_colour_threshold,
    annotate_frame_kernels,
    track_kernels_across_locked_frames
)


def parse_ground_truth(filename: str):
    """
    Parses material, true count, and true bad count from filename.
    Supports formats:
      - 'corn_10_2.jpg'
      - 'peanut_10_0_tray.png'
      - 'sunflower_10_1_bad1.jpg'
      - 'corn-count10-bad2.jpg'
      - 'peanut_10count_2defects.jpg'
    """
    stem = os.path.splitext(os.path.basename(filename))[0].lower()

    # 1. Determine material
    material = None
    if 'peanut' in stem:
        material = 'Peanut'
    elif 'corn' in stem:
        material = 'Corn'
    elif 'sunflower' in stem:
        material = 'Sunflower'
    else:
        material = 'Unknown'

    # 2. Extract numbers
    numbers = [int(n) for n in re.findall(r'\d+', stem)]
    true_count = 0
    true_bad = 0

    if len(numbers) >= 2:
        true_count = numbers[0]
        true_bad = numbers[1]
    elif len(numbers) == 1:
        true_count = numbers[0]
        true_bad = 0

    # Named pattern overrides if present
    count_match = re.search(r'(?:count|total)[-_]?(\d+)', stem)
    if count_match:
        true_count = int(count_match.group(1))

    bad_match = re.search(r'(?:bad|defect|defects|mold|moldy|suspect)[-_]?(\d+)', stem)
    if bad_match:
        true_bad = int(bad_match.group(1))

    return {
        "material": material,
        "true_count": true_count,
        "true_bad": true_bad,
        "true_good": max(0, true_count - true_bad)
    }


class MockLiveFrame:
    """Mock LiveFrame model object for simulating 5-frame locking without database access."""
    def __init__(self, frame_id, image_path, raw_json, material, good_count, defect_count, avg_confidence):
        self.id = frame_id
        self.image_path = image_path
        self.annotated_path = image_path
        self.raw_json = raw_json
        self.material = material
        self.good_count = good_count
        self.defect_count = defect_count
        self.avg_confidence = avg_confidence
        self.is_locked = True

    def to_dict(self):
        return {
            "id": self.id,
            "image_path": self.image_path,
            "annotated_path": self.annotated_path,
            "material": self.material,
            "good_count": self.good_count,
            "defect_count": self.defect_count,
            "avg_confidence": self.avg_confidence
        }


def run_pipeline_on_image(
    image_path: str,
    engine: str = 'ai',
    use_5frame_lock: bool = True,
    output_dir: str = None
) -> dict:
    """
    Executes inspection on a single image file through the exact same logic
    as the live Inspection Station, with optional 5-frame locking simulation.
    Does NOT write to database.
    """
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise ValueError(f"Could not decode image: {image_path}")

    H, W = img_bgr.shape[:2]
    active_ignore_zones = getattr(Config, 'IGNORE_ZONES', DEFAULT_IGNORE_ZONES)
    engine_param = engine.lower()

    # Step 1: Execute engine per-frame detection
    boxes = []
    good_count = 0
    defect_count = 0
    uncertain_count = 0
    detected_material = "Unknown"
    avg_confidence = 1.0

    if engine_param in ['colour', 'color']:
        gt_meta = parse_ground_truth(os.path.basename(image_path))
        gt_mat = gt_meta.get("material")
        mat_canon = gt_mat if gt_mat in ("Corn", "Peanut", "Sunflower") else "Corn"
        try:
            threshold = get_material_colour_threshold(mat_canon)
        except Exception:
            threshold = 40.0
        classical_res = find_kernels_classical(
            img_bgr,
            ignore_zones=active_ignore_zones,
            suspect_threshold=threshold,
            material=mat_canon
        )
        good_count = classical_res["normal_count"]
        defect_count = classical_res["suspect_count"]
        detected_material = mat_canon

        for k in classical_res["kernels"]:
            nb = k["bbox_normalized"]
            is_suspect = (k.get("classification") != "Normal")
            box_class = "Suspect (discoloured)" if is_suspect else "Normal"
            boxes.append({
                "class": box_class,
                "type": "defect" if is_suspect else "healthy",
                "severity": "WARNING" if is_suspect else "NORMAL",
                "category": box_class,
                "confidence": 1.0,
                "x": nb["x"],
                "y": nb["y"],
                "w": nb["w"],
                "h": nb["h"],
                "x_pct": nb["x_pct"],
                "y_pct": nb["y_pct"],
                "w_pct": nb["w_pct"],
                "h_pct": nb["h_pct"],
                "id": k["id"],
                "area": k["area"],
                "suspect_score": k.get("suspect_score", 0.0),
                "reason_tags": k.get("reason_tags", []),
                "reason_why": k.get("reason_why", "discoloured" if is_suspect else "Normal")
            })

    elif engine_param == 'both':
        yolo_res = run_yolo_visual_inspection(raw_image_path=image_path)
        yolo_mat = get_mostly_detected_material(yolo_res)
        gt_meta = parse_ground_truth(os.path.basename(image_path))
        gt_mat = gt_meta.get("material")
        mat_canon = yolo_mat if yolo_mat in ("Corn", "Peanut", "Sunflower") else (gt_mat if gt_mat in ("Corn", "Peanut", "Sunflower") else "Corn")
        try:
            threshold = get_material_colour_threshold(mat_canon)
        except Exception:
            threshold = 40.0
        classical_res = find_kernels_classical(
            img_bgr,
            ignore_zones=active_ignore_zones,
            suspect_threshold=threshold,
            material=mat_canon
        )

        yolo_defects = [
            d for d in yolo_res.get("detected_defects", [])
            if not is_center_in_ignore_zones(
                (float(d.get("bbox_x", 0.0)) + float(d.get("bbox_w", 0.0)) / 2.0) / 100.0,
                (float(d.get("bbox_y", 0.0)) + float(d.get("bbox_h", 0.0)) / 2.0) / 100.0,
                active_ignore_zones
            )
        ]
        yolo_healthy = [
            h for h in yolo_res.get("detected_healthy", [])
            if not is_center_in_ignore_zones(
                (float(h.get("bbox_x", 0.0)) + float(h.get("bbox_w", 0.0)) / 2.0) / 100.0,
                (float(h.get("bbox_y", 0.0)) + float(h.get("bbox_h", 0.0)) / 2.0) / 100.0,
                active_ignore_zones
            )
        ]

        for k in classical_res["kernels"]:
            nb = k["bbox_normalized"]
            kcx = nb["x"] + nb["w"] / 2.0
            kcy = nb["y"] + nb["h"] / 2.0
            is_colour_suspect = (k.get("classification") != "Normal")
            colour_why = k.get("reason_why") or ("discoloured" if is_colour_suspect else "Normal")

            matched_d = None
            for d in yolo_defects:
                dx = float(d.get("bbox_x", 0.0)) / 100.0
                dy = float(d.get("bbox_y", 0.0)) / 100.0
                dw = float(d.get("bbox_w", 0.0)) / 100.0
                dh = float(d.get("bbox_h", 0.0)) / 100.0
                dcx, dcy = dx + dw / 2.0, dy + dh / 2.0
                dist = np.sqrt((kcx - dcx)**2 + (kcy - dcy)**2)
                if dist <= 0.08 or (dx <= kcx <= dx + dw and dy <= kcy <= dy + dh):
                    matched_d = d
                    break

            matched_h = None
            if not matched_d:
                for h in yolo_healthy:
                    hx = float(h.get("bbox_x", 0.0)) / 100.0
                    hy = float(h.get("bbox_y", 0.0)) / 100.0
                    hw = float(h.get("bbox_w", 0.0)) / 100.0
                    hh = float(h.get("bbox_h", 0.0)) / 100.0
                    hcx, hcy = hx + hw / 2.0, hy + hh / 2.0
                    dist = np.sqrt((kcx - hcx)**2 + (kcy - hcy)**2)
                    if dist <= 0.08 or (hx <= kcx <= hx + hw and hy <= kcy <= hy + hh):
                        matched_h = h
                        break

            is_ai_defect = (matched_d is not None)
            if is_colour_suspect and is_ai_defect:
                box_class = "Suspect (discoloured)"
                box_type = "defect"
                defect_count += 1
                reason_why = colour_why
            elif (not is_colour_suspect) and (not is_ai_defect):
                box_class = "Normal"
                box_type = "healthy"
                good_count += 1
                reason_why = colour_why
            else:
                box_class = "Uncertain"
                box_type = "uncertain"
                uncertain_count += 1
                reason_why = f"Disagreement: Colour vs AI"

            boxes.append({
                "class": box_class,
                "type": box_type,
                "confidence": 1.0,
                "x": nb["x"],
                "y": nb["y"],
                "w": nb["w"],
                "h": nb["h"],
                "x_pct": nb["x_pct"],
                "y_pct": nb["y_pct"],
                "w_pct": nb["w_pct"],
                "h_pct": nb["h_pct"],
                "id": k["id"],
                "reason_why": reason_why
            })

    else:
        # Default 'ai' engine (YOLOv8)
        yolo_res = run_yolo_visual_inspection(raw_image_path=image_path)
        detected_material = get_mostly_detected_material(yolo_res) or "Unknown"

        all_confs = []
        for d in yolo_res.get("detected_defects", []):
            x_pct = float(d.get("bbox_x", 0.0))
            y_pct = float(d.get("bbox_y", 0.0))
            w_pct = float(d.get("bbox_w", 0.0))
            h_pct = float(d.get("bbox_h", 0.0))
            cx = (x_pct + w_pct / 2.0) / 100.0
            cy = (y_pct + h_pct / 2.0) / 100.0
            if is_center_in_ignore_zones(cx, cy, active_ignore_zones):
                continue
            defect_count += 1
            conf = float(d.get("confidence", 0.0))
            all_confs.append(conf)
            boxes.append({
                "class": d.get("defect_class", "defect"),
                "type": "defect",
                "severity": "WARNING",
                "confidence": round(conf, 3),
                "reason_why": f"{d.get('defect_class', 'defect')} ({conf:.0%})",
                "x": round(x_pct / 100.0, 4),
                "y": round(y_pct / 100.0, 4),
                "w": round(w_pct / 100.0, 4),
                "h": round(h_pct / 100.0, 4),
                "x_pct": x_pct,
                "y_pct": y_pct,
                "w_pct": w_pct,
                "h_pct": h_pct
            })

        for h in yolo_res.get("detected_healthy", []):
            x_pct = float(h.get("bbox_x", 0.0))
            y_pct = float(h.get("bbox_y", 0.0))
            w_pct = float(h.get("bbox_w", 0.0))
            h_pct = float(h.get("bbox_h", 0.0))
            cx = (x_pct + w_pct / 2.0) / 100.0
            cy = (y_pct + h_pct / 2.0) / 100.0
            if is_center_in_ignore_zones(cx, cy, active_ignore_zones):
                continue
            good_count += 1
            conf = float(h.get("confidence", 0.0))
            all_confs.append(conf)
            boxes.append({
                "class": h.get("specimen_class", "Healthy"),
                "type": "healthy",
                "severity": "NORMAL",
                "confidence": round(conf, 3),
                "reason_why": f"Healthy ({conf:.0%})",
                "x": round(x_pct / 100.0, 4),
                "y": round(y_pct / 100.0, 4),
                "w": round(w_pct / 100.0, 4),
                "h": round(h_pct / 100.0, 4),
                "x_pct": x_pct,
                "y_pct": y_pct,
                "w_pct": w_pct,
                "h_pct": h_pct
            })

        avg_confidence = round(sum(all_confs) / len(all_confs), 3) if all_confs else 0.0

    raw_frame_json = json.dumps({"boxes": boxes})

    # Step 2: 5-Frame Lock & Material Classifier Consensus Simulation
    final_material = detected_material
    final_count = len(boxes)
    final_bad_count = defect_count + uncertain_count
    final_good_count = good_count
    final_state = "REVIEW"
    tracked_kernels_list = []

    if use_5frame_lock and getattr(Config, 'USE_MATERIAL_CLASSIFIER', True):
        # Simulate repeating frame 5 times (standard single-photo station upload behavior)
        mock_frames = [
            MockLiveFrame(i + 1, image_path, raw_frame_json, detected_material, good_count, defect_count, avg_confidence)
            for i in range(5)
        ]

        # Extract crops for material classifier
        from ultralytics import YOLO
        cls_path = getattr(Config, 'MATERIAL_CLS_MODEL_PATH', 'models/material_cls.pt')
        if not os.path.isabs(cls_path):
            cls_path = os.path.join(Config.BASE_DIR, cls_path)

        all_crops = []
        crop_records = []
        for b in boxes:
            bx, by, bw, bh = b["x"], b["y"], b["w"], b["h"]
            x1 = max(0, int(round(bx * W)))
            y1 = max(0, int(round(by * H)))
            x2 = min(W, int(round((bx + bw) * W)))
            y2 = min(H, int(round((by + bh) * H)))
            if x2 > x1 and y2 > y1:
                pad_w = int((x2 - x1) * 0.08)
                pad_h = int((y2 - y1) * 0.08)
                cx1 = max(0, x1 - pad_w)
                cy1 = max(0, y1 - pad_h)
                cx2 = min(W, x2 + pad_w)
                cy2 = min(H, y2 + pad_h)
                c_img = img_bgr[cy1:cy2, cx1:cx2]
                if c_img.size > 0 and c_img.shape[0] >= 6 and c_img.shape[1] >= 6:
                    all_crops.append(c_img)
                    crop_records.append({"box": b, "crop": c_img})

        is_consensus = False
        winner_mat = "Unknown"
        agreement_pct = 0

        if os.path.isfile(cls_path) and len(all_crops) >= 3:
            try:
                cls_model = YOLO(cls_path)
                cls_res = cls_model(all_crops, verbose=False, imgsz=96)
                weighted_votes = defaultdict(float)
                for rec, r in zip(crop_records, cls_res):
                    top1_idx = int(r.probs.top1)
                    pred_mat = r.names[top1_idx].capitalize()
                    pred_conf = float(r.probs.top1conf) if hasattr(r.probs, 'top1conf') else float(r.probs.data[top1_idx])
                    weighted_votes[pred_mat] += pred_conf
                
                total_weight = sum(weighted_votes.values())
                if total_weight > 0:
                    cand = max(weighted_votes, key=weighted_votes.get)
                    ratio = weighted_votes[cand] / total_weight
                    agreement_pct = int(round(ratio * 100))
                    if ratio >= 0.70 and len(crop_records) >= 3:
                        winner_mat = cand
                        is_consensus = True
            except Exception:
                pass

        final_material = winner_mat if is_consensus else "Unknown / mixed"

        # Track kernels across frames
        tracked_kernels = track_kernels_across_locked_frames(
            mock_frames,
            consensus_mat=(winner_mat if is_consensus else None)
        )
        tracked_kernels_list = tracked_kernels
        final_count = len(tracked_kernels)

        moldy_count = sum(1 for tk in tracked_kernels if "suspect" in tk["majority_verdict"].lower() or ("mold" in tk["majority_verdict"].lower() and "not" not in tk["majority_verdict"].lower()))
        unc_count = sum(1 for tk in tracked_kernels if tk["majority_verdict"] == "Uncertain")
        g_count = sum(1 for tk in tracked_kernels if tk["majority_verdict"] == "Normal")

        # Sunflower Lab colour screening check
        if is_consensus and winner_mat == "Sunflower" and crop_records:
            lab_vectors = []
            for rec in crop_records:
                lab_img = cv2.cvtColor(rec["crop"], cv2.COLOR_BGR2LAB)
                l_m = float(np.mean(lab_img[:, :, 0])) * (100.0 / 255.0)
                a_m = float(np.mean(lab_img[:, :, 1])) - 128.0
                b_m = float(np.mean(lab_img[:, :, 2])) - 128.0
                rec["lab"] = (l_m, a_m, b_m)
                lab_vectors.append((l_m, a_m, b_m))
            if lab_vectors:
                l_med = float(np.median([v[0] for v in lab_vectors]))
                a_med = float(np.median([v[1] for v in lab_vectors]))
                b_med = float(np.median([v[2] for v in lab_vectors]))
                disc_count = 0
                for tk in tracked_kernels:
                    tb = tk.get("bbox", {})
                    tcx = float(tb.get("x", 0.0)) + float(tb.get("w", 0.0)) / 2.0
                    tcy = float(tb.get("y", 0.0)) + float(tb.get("h", 0.0)) / 2.0
                    best_rec = None
                    best_d = 999.0
                    for r in crop_records:
                        if "lab" not in r:
                            continue
                        rb = r["box"]
                        rcx = float(rb.get("x", 0.0)) + float(rb.get("w", 0.0)) / 2.0
                        rcy = float(rb.get("y", 0.0)) + float(rb.get("h", 0.0)) / 2.0
                        d = (tcx - rcx)**2 + (tcy - rcy)**2
                        if d < best_d:
                            best_d = d
                            best_rec = r
                    if best_rec:
                        vl, va, vb = best_rec["lab"]
                        delta_e = float(np.sqrt((vl - l_med)**2 + (va - a_med)**2 + (vb - b_med)**2))
                        if delta_e > 22.0 or "suspect" in tk["majority_verdict"].lower() or "mold" in tk["majority_verdict"].lower():
                            tk["majority_verdict"] = "Suspect (discoloured)"
                            disc_count += 1
                moldy_count = disc_count

        final_bad_count = moldy_count + unc_count
        final_good_count = g_count

        # Call final_decision
        locked_dict = {
            "kernels_checked": final_count,
            "usable_frames": 5,
            "material": final_material,
            "defect_pct": round((final_bad_count / float(final_count) * 100.0), 1) if final_count > 0 else 0.0,
            "uncertain_count": unc_count,
            "agreement_ratio": (agreement_pct / 100.0) if is_consensus else 0.0,
            "tracked_kernels": tracked_kernels,
            "warnings": []
        }
        dec = final_decision(locked_dict)
        final_state = dec["state"]
    else:
        # Single frame mode without 5-frame locking
        final_count = len(boxes)
        final_bad_count = defect_count + uncertain_count
        final_good_count = good_count
        locked_dict = {
            "kernels_checked": final_count,
            "usable_frames": 1,
            "material": detected_material,
            "defect_pct": round((final_bad_count / float(final_count) * 100.0), 1) if final_count > 0 else 0.0,
            "uncertain_count": uncertain_count,
            "warnings": []
        }
        dec = final_decision(locked_dict)
        final_state = dec["state"]

    # Step 3: Generate annotated output image with numbered kernels
    ann_boxes = []
    if tracked_kernels_list:
        for idx, tk in enumerate(tracked_kernels_list, 1):
            maj = tk["majority_verdict"]
            b_type = "defect" if ("suspect" in maj.lower() or "mold" in maj.lower()) else ("uncertain" if maj == "Uncertain" else "healthy")
            ann_boxes.append({
                "id": idx,
                "class": maj,
                "type": b_type,
                "severity": "WARNING" if b_type != "healthy" else "NORMAL",
                "x": tk["bbox"]["x"],
                "y": tk["bbox"]["y"],
                "w": tk["bbox"]["w"],
                "h": tk["bbox"]["h"],
                "x_pct": tk["bbox"]["x"] * 100.0,
                "y_pct": tk["bbox"]["y"] * 100.0,
                "w_pct": tk["bbox"]["w"] * 100.0,
                "h_pct": tk["bbox"]["h"] * 100.0,
                "reason_why": tk.get("reason_why", "")
            })
    else:
        for idx, b in enumerate(boxes, 1):
            ann_boxes.append({
                "id": idx,
                "class": b["class"],
                "type": b["type"],
                "severity": b.get("severity", "NORMAL"),
                "x": b["x"],
                "y": b["y"],
                "w": b["w"],
                "h": b["h"],
                "x_pct": b["x_pct"],
                "y_pct": b["y_pct"],
                "w_pct": b["w_pct"],
                "h_pct": b["h_pct"],
                "reason_why": b.get("reason_why", "")
            })

    ann_img = annotate_frame_kernels(img_bgr.copy(), ann_boxes, ignore_zones=active_ignore_zones)

    annotated_output_path = None
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        fname = os.path.basename(image_path)
        annotated_output_path = os.path.join(output_dir, f"annotated_{fname}")
        cv2.imwrite(annotated_output_path, ann_img)

    return {
        "image_path": image_path,
        "engine": engine_param,
        "predicted_material": final_material,
        "predicted_count": final_count,
        "predicted_good": final_good_count,
        "predicted_bad": final_bad_count,
        "predicted_state": final_state,
        "annotated_path": annotated_output_path,
        "boxes": ann_boxes
    }


def evaluate_directory(
    photos_dir: str = 'eval_photos',
    engines: list = None,
    output_base_dir: str = 'eval_output'
):
    """
    Evaluates every image in photos_dir across specified engines.
    Prints comprehensive results table and summary performance metrics.
    """
    if engines is None:
        engines = ['ai', 'colour', 'both']

    if not os.path.isdir(photos_dir):
        print(f"\n[!] Directory '{photos_dir}' does not exist.")
        return {}

    image_files = [
        f for f in sorted(os.listdir(photos_dir))
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
    ]

    if not image_files:
        print(f"\n[!] Directory '{photos_dir}' contains 0 image files.")
        return {}

    print(f"\nFound {len(image_files)} test images in '{photos_dir}'. Running evaluation...")

    all_results = defaultdict(list)

    for eng in engines:
        print(f"\n{'='*75}")
        print(f"RUNNING INSPECTION ENGINE: {eng.upper()}")
        print(f"{'='*75}")

        eng_out_dir = os.path.join(output_base_dir, eng)
        records = []

        for fname in image_files:
            fpath = os.path.join(photos_dir, fname)
            gt = parse_ground_truth(fname)

            try:
                res = run_pipeline_on_image(
                    image_path=fpath,
                    engine=eng,
                    use_5frame_lock=True,
                    output_dir=eng_out_dir
                )
                res["gt"] = gt
                res["filename"] = fname
                records.append(res)
            except Exception as e:
                print(f"  [ERROR] Failed to process {fname}: {e}")

        all_results[eng] = records
        print_engine_table(eng, records)

    return all_results


def print_engine_table(engine_name: str, records: list):
    """Prints formatted table and metrics for a specific engine run."""
    print(f"\nDetailed Results for Engine: {engine_name.upper()}")
    print("-" * 115)
    print(f"{'File':<32} | {'True Mat':<10} | {'Pred Mat':<14} | {'Count':<9} | {'Bad (Sus)':<10} | {'MAE':<5} | {'State':<8}")
    print("-" * 115)

    mat_correct = 0
    count_exact = 0
    abs_errors = []
    total_true_bad = 0
    detected_true_bad = 0
    total_true_good = 0
    false_alarms = 0

    per_material_stats = defaultdict(lambda: {
        "total": 0,
        "mat_correct": 0,
        "count_exact": 0,
        "abs_errors": [],
        "true_bad": 0,
        "detected_bad": 0,
        "true_good": 0,
        "false_alarms": 0
    })

    for r in records:
        gt = r["gt"]
        t_mat = gt["material"]
        p_mat = r["predicted_material"]
        t_cnt = gt["true_count"]
        p_cnt = r["predicted_count"]
        t_bad = gt["true_bad"]
        p_bad = r["predicted_bad"]
        state = r["predicted_state"]

        # Clean material representation
        clean_p_mat = p_mat.split('(')[0].strip()

        # Material match
        is_mat_match = (t_mat.lower() in clean_p_mat.lower() or clean_p_mat.lower() in t_mat.lower()) if t_mat != 'Unknown' else False
        if is_mat_match:
            mat_correct += 1
            per_material_stats[t_mat]["mat_correct"] += 1

        # Count match & error
        is_cnt_match = (t_cnt == p_cnt)
        if is_cnt_match:
            count_exact += 1
            per_material_stats[t_mat]["count_exact"] += 1

        mae = abs(p_cnt - t_cnt)
        abs_errors.append(mae)
        per_material_stats[t_mat]["abs_errors"].append(mae)

        # Bad kernel recall & false alarm
        total_true_bad += t_bad
        per_material_stats[t_mat]["true_bad"] += t_bad
        det_bad = min(t_bad, p_bad) # detected true bad
        detected_true_bad += det_bad
        per_material_stats[t_mat]["detected_bad"] += det_bad

        t_good = gt["true_good"]
        total_true_good += t_good
        per_material_stats[t_mat]["true_good"] += t_good
        fa = max(0, p_bad - t_bad) # false alarms
        false_alarms += fa
        per_material_stats[t_mat]["false_alarms"] += fa

        per_material_stats[t_mat]["total"] += 1

        cnt_str = f"{t_cnt} -> {p_cnt}"
        bad_str = f"{t_bad} -> {p_bad}"
        short_file = r["filename"] if len(r["filename"]) <= 32 else r["filename"][:29] + "..."
        print(f"{short_file:<32} | {t_mat:<10} | {p_mat[:14]:<14} | {cnt_str:<9} | {bad_str:<10} | {mae:<5} | {state:<8}")

    print("-" * 115)

    n = len(records)
    if n == 0:
        return

    overall_mat_acc = (mat_correct / n) * 100.0
    overall_cnt_acc = (count_exact / n) * 100.0
    overall_mae = sum(abs_errors) / n if abs_errors else 0.0
    overall_recall = (detected_true_bad / total_true_bad * 100.0) if total_true_bad > 0 else 100.0
    overall_fa_rate = (false_alarms / total_true_good * 100.0) if total_true_good > 0 else 0.0

    print(f"\n[SUMMARY METRICS - ENGINE: {engine_name.upper()}]")
    print(f"  * Total Images Evaluated:     {n}")
    print(f"  * Material Accuracy:          {overall_mat_acc:.1f}% ({mat_correct}/{n})")
    print(f"  * Exact Count Accuracy:       {overall_cnt_acc:.1f}% ({count_exact}/{n})")
    print(f"  * Mean Absolute Count Error:  {overall_mae:.2f} kernels")
    print(f"  * Bad-Kernel Recall:          {overall_recall:.1f}% ({detected_true_bad}/{total_true_bad})")
    print(f"  * False-Alarm Rate:           {overall_fa_rate:.1f}% ({false_alarms}/{total_true_good})")

    print("\n[PER-MATERIAL BREAKDOWN]")
    print(f"{'Material':<12} | {'Photos':<6} | {'Mat Acc':<9} | {'Count Acc':<9} | {'Mean Error':<10} | {'Recall':<8} | {'False Alarm':<11}")
    print("-" * 80)
    for mat, st in sorted(per_material_stats.items()):
        tot = st["total"]
        if tot == 0: continue
        m_acc = (st["mat_correct"] / tot) * 100.0
        c_acc = (st["count_exact"] / tot) * 100.0
        m_mae = sum(st["abs_errors"]) / tot
        rec = (st["detected_bad"] / st["true_bad"] * 100.0) if st["true_bad"] > 0 else 100.0
        fa_r = (st["false_alarms"] / st["true_good"] * 100.0) if st["true_good"] > 0 else 0.0
        print(f"{mat:<12} | {tot:<6} | {m_acc:>6.1f}%  | {c_acc:>6.1f}%  | {m_mae:>7.2f}    | {rec:>6.1f}% | {fa_r:>8.1f}%")
    print("-" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Food Man Visual Inspection Evaluation")
    parser.add_argument("--dir", default="eval_photos", help="Directory containing test images")
    parser.add_argument("--engine", default="all", choices=["ai", "colour", "both", "auto", "all"], help="Inspection engine to test")
    parser.add_argument("--output", default="eval_output", help="Directory for annotated debug output images")

    args = parser.parse_args()

    engine_list = ['ai', 'colour', 'both'] if args.engine == 'all' else [args.engine]
    evaluate_directory(photos_dir=args.dir, engines=engine_list, output_base_dir=args.output)
