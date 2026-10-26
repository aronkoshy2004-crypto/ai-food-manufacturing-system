"""
AI Scan Pipeline - Food Man Inspection Station
Provides repeatable, stable sample inspection by:
1. Capturing/receiving a burst of frames (typically 8 frames over ~2 seconds).
2. Discarding blurry frames using Variance of Laplacian and keeping the best 5.
3. Running the detector at imgsz 640 (with configurable augment/TTA, confidence floor, ignore zones).
4. Merging kernels across the 5 frames by position so each kernel gets one verdict by majority vote with averaged confidence.
5. Counting each kernel exactly once (eliminating overlay flicker).
6. Enforcing minimum kernel threshold (fewer than 3 kernels gives RETAKE).
7. Supporting product preselection with material mismatch warnings only.
"""
import os
import time
import json
import logging
from collections import Counter, defaultdict
import cv2
import numpy as np

from config import Config
from ai.yolo_service import get_cached_yolo_model, find_trained_model, HEALTHY_CLASSES, FOOD_DEFECT_TAXONOMY
from ai.classical_kernel_finder import is_center_in_ignore_zones

logger = logging.getLogger(__name__)

# Default parameters
DEFAULT_IMGSZ = 640
DEFAULT_CONF_FLOOR = 0.25
DEFAULT_MIN_KERNELS = 3
DEFAULT_DIST_THRESH = 0.08
DEFAULT_IOU_THRESH = 0.20


def compute_variance_of_laplacian(img_bgr: np.ndarray) -> float:
    """Computes focus measure / sharpness using the variance of the Laplacian."""
    if img_bgr is None or img_bgr.size == 0:
        return 0.0
    if len(img_bgr.shape) == 3:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = img_bgr
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def select_sharpest_frames(frame_items: list, keep_count: int = 5) -> list:
    """
    Given a list of frame items, computes sharpness for each,
    discards blurry frames (lowest variance of Laplacian), and returns the best 'keep_count'.
    Each item in frame_items can be:
      - str (file path)
      - np.ndarray (BGR image)
      - dict with 'image', 'path', etc.
    Returns: list of dicts: {'item': original_item, 'sharpness': float, 'img_bgr': np.ndarray, 'path': str}
    """
    evaluated = []
    for item in frame_items:
        img_bgr = None
        path = None
        if isinstance(item, str):
            path = item
            if os.path.isfile(path):
                img_bgr = cv2.imread(path)
        elif isinstance(item, np.ndarray):
            img_bgr = item
        elif isinstance(item, dict):
            img_bgr = item.get('img_bgr')
            path = item.get('path')
            if img_bgr is None and path and os.path.isfile(path):
                img_bgr = cv2.imread(path)

        if img_bgr is None:
            continue

        sharpness = compute_variance_of_laplacian(img_bgr)
        evaluated.append({
            'item': item,
            'img_bgr': img_bgr,
            'path': path,
            'sharpness': sharpness
        })

    if not evaluated:
        return []

    # Sort descending by sharpness (clearest first)
    evaluated.sort(key=lambda x: x['sharpness'], reverse=True)
    return evaluated[:keep_count]


def detect_frame_kernels(img_bgr: np.ndarray,
                         model=None,
                         imgsz: int = DEFAULT_IMGSZ,
                         conf_floor: float = DEFAULT_CONF_FLOOR,
                         ignore_zones: list = None,
                         augment: bool = False,
                         product_filter: str = None) -> list:
    """
    Runs YOLO detector on a single frame at specified imgsz and confidence floor.
    Filters out detections within ignore_zones or below conf_floor.
    Returns list of normalized bounding box dicts.
    """
    if img_bgr is None or img_bgr.size == 0:
        return []

    if model is None:
        model_path, _ = find_trained_model()
        if not model_path:
            return []
        model = get_cached_yolo_model(model_path)

    H, W = img_bgr.shape[:2]
    active_iz = ignore_zones or getattr(Config, 'IGNORE_ZONES', [{"x": 0.0, "y": 0.82, "w": 0.22, "h": 0.18}])

    # Run inference with Ultralytics YOLO
    results = model.predict(
        source=img_bgr,
        conf=conf_floor,
        iou=0.35,
        imgsz=imgsz,
        augment=augment,
        verbose=False
    )

    if not results or len(results) == 0:
        return []

    first_res = results[0]
    boxes = first_res.boxes
    names = first_res.names or {}

    frame_detections = []
    if boxes is None or len(boxes) == 0:
        return []

    for box in boxes:
        conf = float(box.conf[0].cpu().item()) if hasattr(box.conf, 'cpu') else float(box.conf[0])
        if conf < conf_floor:
            continue

        cls_id = int(box.cls[0].cpu().item()) if hasattr(box.cls, 'cpu') else int(box.cls[0])
        cls_name = names.get(cls_id, f"class_{cls_id}")
        cls_lower = cls_name.lower()

        xyxy = box.xyxy[0].cpu().numpy() if hasattr(box.xyxy, 'cpu') else box.xyxy[0]
        x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

        # Normalized coordinates (0.0 to 1.0)
        bx = max(0.0, min(1.0, x1 / W))
        by = max(0.0, min(1.0, y1 / H))
        bw = max(0.0, min(1.0, (x2 - x1) / W))
        bh = max(0.0, min(1.0, (y2 - y1) / H))

        cx = bx + bw / 2.0
        cy = by + bh / 2.0

        # Filter by ignore zones
        if is_center_in_ignore_zones(cx, cy, active_iz):
            continue

        # Determine if defect or healthy
        is_healthy = any(h in cls_lower for h in HEALTHY_CLASSES) or ("not" in cls_lower and "mold" in cls_lower) or ("clean" in cls_lower)
        is_defect = not is_healthy and ("mold" in cls_lower or "defect" in cls_lower or "suspect" in cls_lower or cls_lower in FOOD_DEFECT_TAXONOMY)

        box_type = "defect" if is_defect else "healthy"

        # Apply product filter if specified (e.g. Peanut, Corn, Sunflower)
        if product_filter and product_filter.lower() not in ('auto', 'all', 'none', ''):
            pf = product_filter.lower()
            # If the class name explicitly contains a different commodity name, flag as cross-material
            other_commodities = [c for c in ['peanut', 'corn', 'sunflower'] if c != pf]
            if any(oc in cls_lower for oc in other_commodities):
                box_type = "uncertain"

        frame_detections.append({
            "class": cls_name,
            "type": box_type,
            "confidence": round(conf, 4),
            "x": round(bx, 4),
            "y": round(by, 4),
            "w": round(bw, 4),
            "h": round(bh, 4),
            "cx": round(cx, 4),
            "cy": round(cy, 4),
            "x_pct": round(bx * 100.0, 2),
            "y_pct": round(by * 100.0, 2),
            "w_pct": round(bw * 100.0, 2),
            "h_pct": round(bh * 100.0, 2)
        })

    return frame_detections


def merge_kernels_across_frames(frames_detections: list,
                                dist_thresh: float = DEFAULT_DIST_THRESH,
                                iou_thresh: float = DEFAULT_IOU_THRESH) -> list:
    """
    Tracks and merges kernels across multiple frames by position.
    Each kernel gets:
    - Exactly one consolidated identity (counted once)
    - One majority vote verdict ("Normal", "Defect", or "Uncertain")
    - Averaged confidence across all its observations
    - Consolidated bounding box
    """
    tracked_kernels = []

    for f_idx, detections in enumerate(frames_detections):
        for det in detections:
            cx, cy = det["cx"], det["cy"]
            bx, by, bw, bh = det["x"], det["y"], det["w"], det["h"]
            conf = det["confidence"]
            b_type = det["type"]

            obs = {
                "frame_idx": f_idx,
                "class": det["class"],
                "type": b_type,
                "confidence": conf,
                "bbox": {"x": bx, "y": by, "w": bw, "h": bh},
                "centroid": (cx, cy)
            }

            best_tk = None
            min_dist = float('inf')

            for tk in tracked_kernels:
                # Avoid matching two detections from the same frame to the same tracked kernel
                if any(o["frame_idx"] == f_idx for o in tk["observations"]):
                    continue

                tcx, tcy = tk["centroid"]
                dist = np.sqrt((cx - tcx)**2 + (cy - tcy)**2)

                # IoU calculation
                tx, ty, tw, th = tk["bbox"]["x"], tk["bbox"]["y"], tk["bbox"]["w"], tk["bbox"]["h"]
                ix1 = max(bx, tx)
                iy1 = max(by, ty)
                ix2 = min(bx + bw, tx + tw)
                iy2 = min(by + bh, ty + th)
                iou = 0.0
                if ix2 > ix1 and iy2 > iy1:
                    ia = (ix2 - ix1) * (iy2 - iy1)
                    ua = bw * bh + tw * th - ia
                    iou = ia / ua if ua > 0 else 0.0

                if (dist <= dist_thresh or iou >= iou_thresh) and dist < min_dist:
                    min_dist = dist
                    best_tk = tk

            if best_tk is not None:
                best_tk["observations"].append(obs)
                n_obs = len(best_tk["observations"])
                # Update running centroid
                best_tk["centroid"] = (
                    round((best_tk["centroid"][0] * (n_obs - 1) + cx) / n_obs, 4),
                    round((best_tk["centroid"][1] * (n_obs - 1) + cy) / n_obs, 4)
                )
                # Keep bounding box of the highest-confidence observation
                if conf > best_tk.get("max_conf", 0.0):
                    best_tk["max_conf"] = conf
                    best_tk["bbox"] = {"x": bx, "y": by, "w": bw, "h": bh}
            else:
                tracked_kernels.append({
                    "id": len(tracked_kernels) + 1,
                    "centroid": (cx, cy),
                    "bbox": {"x": bx, "y": by, "w": bw, "h": bh},
                    "max_conf": conf,
                    "observations": [obs]
                })

    # Compute consolidated verdict & averaged confidence for each kernel
    for tk in tracked_kernels:
        obs = tk["observations"]
        total_obs = len(obs)

        # Average confidence
        confs = [o["confidence"] for o in obs]
        tk["avg_confidence"] = round(float(np.mean(confs)), 4) if confs else 0.0

        # Majority vote for verdict
        types = [o["type"] for o in obs]
        type_counts = Counter(types)
        defect_votes = type_counts.get("defect", 0)
        healthy_votes = type_counts.get("healthy", 0)
        uncertain_votes = type_counts.get("uncertain", 0)

        if uncertain_votes > 0 and (uncertain_votes >= max(defect_votes, healthy_votes) or (uncertain_votes / float(total_obs)) >= 0.40):
            tk["verdict"] = "Uncertain"
            tk["class"] = "Uncertain"
        elif defect_votes > healthy_votes:
            tk["verdict"] = "Defect"
            # Use most frequent defect class name
            defect_classes = [o["class"] for o in obs if o["type"] == "defect"]
            tk["class"] = Counter(defect_classes).most_common(1)[0][0] if defect_classes else "Defect"
        else:
            tk["verdict"] = "Normal"
            healthy_classes = [o["class"] for o in obs if o["type"] == "healthy"]
            tk["class"] = Counter(healthy_classes).most_common(1)[0][0] if healthy_classes else "Healthy"

        tk["vote_summary"] = {
            "defect": defect_votes,
            "healthy": healthy_votes,
            "uncertain": uncertain_votes,
            "total_frames_observed": total_obs
        }

    return tracked_kernels


def annotate_kernels_on_frame(img_bgr: np.ndarray,
                              tracked_kernels: list,
                              ignore_zones: list = None,
                              title_hud: str = None) -> np.ndarray:
    """
    Renders clean, non-flickering bounding boxes and HUD on the best frame.
    Green = Normal (Healthy), Red = Defect (Moldy), Amber = Uncertain.
    """
    canvas = img_bgr.copy()
    H, W = canvas.shape[:2]
    active_iz = ignore_zones or getattr(Config, 'IGNORE_ZONES', [{"x": 0.0, "y": 0.82, "w": 0.22, "h": 0.18}])

    # Draw Ignore Zones outline
    if active_iz:
        for z in active_iz:
            zx = int(z.get("x", 0.0) * W)
            zy = int(z.get("y", 0.0) * H)
            zw = int(z.get("w", 0.0) * W)
            zh = int(z.get("h", 0.0) * H)
            sub = canvas[zy:zy+zh, zx:zx+zw]
            if sub.size > 0:
                color_rect = np.full_like(sub, (11, 158, 245))  # Amber
                cv2.addWeighted(color_rect, 0.15, sub, 0.85, 0, sub)
                canvas[zy:zy+zh, zx:zx+zw] = sub
            cv2.rectangle(canvas, (zx, zy), (zx+zw, zy+zh), (11, 158, 245), 2)
            cv2.putText(canvas, "IGNORE ZONE", (zx + 6, max(18, zy - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (11, 158, 245), 1, cv2.LINE_AA)

    # Draw each merged kernel
    for tk in tracked_kernels:
        bb = tk["bbox"]
        x1 = max(0, int(round(bb["x"] * W)))
        y1 = max(0, int(round(bb["y"] * H)))
        x2 = min(W, int(round((bb["x"] + bb["w"]) * W)))
        y2 = min(H, int(round((bb["y"] + bb["h"]) * H)))

        verdict = tk.get("verdict", "Normal")
        avg_conf = tk.get("avg_confidence", 1.0)
        k_id = tk.get("id", 1)

        if verdict == "Defect":
            box_color = (68, 68, 239)      # Red in BGR
            bg_color = (50, 50, 200)
            label = f"#{k_id} {tk.get('class', 'Defect')} ({avg_conf:.0%})"
        elif verdict == "Uncertain":
            box_color = (11, 158, 245)     # Amber in BGR
            bg_color = (10, 140, 220)
            label = f"#{k_id} Uncertain ({avg_conf:.0%})"
        else:
            box_color = (129, 185, 16)     # Green in BGR
            bg_color = (100, 160, 10)
            label = f"#{k_id} Normal ({avg_conf:.0%})"

        # Draw kernel bounding box
        cv2.rectangle(canvas, (x1, y1), (x2, y2), box_color, 3)

        # Draw label banner
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.50
        thickness = 1
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
        label_y1 = max(0, y1 - th - 8)
        label_y2 = y1
        cv2.rectangle(canvas, (x1, label_y1), (x1 + tw + 10, label_y2), box_color, -1)
        cv2.putText(canvas, label, (x1 + 5, label_y2 - 4), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    if title_hud:
        cv2.putText(canvas, title_hud, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)

    return canvas


def run_burst_scan_pipeline(frames: list,
                            product: str = None,
                            imgsz: int = DEFAULT_IMGSZ,
                            conf_floor: float = DEFAULT_CONF_FLOOR,
                            ignore_zones: list = None,
                            augment: bool = False,
                            min_kernels: int = DEFAULT_MIN_KERNELS) -> dict:
    """
    Executes the full end-to-end 5-frame stabilized scan pipeline:
    1. Selects the 5 sharpest frames via variance of Laplacian (discarding blurry burst frames).
    2. Runs detector at imgsz 640 with confidence floor & ignore zones.
    3. Merges kernels across the 5 frames by position (deduplicating).
    4. Evaluates kernel count, verdicts, and pass/fail state.
    5. Returns structured verdict dictionary with annotated best frame.
    """
    t_start = time.time()

    # 1. Select the 5 sharpest frames (discarding blurry ones)
    sharp_frames = select_sharpest_frames(frames, keep_count=5)
    if not sharp_frames:
        return {
            "success": False,
            "status": "NEEDS_RETAKE",
            "suggestion": "Retake",
            "error": "No valid frames could be decoded.",
            "kernels_found": 0,
            "total_kernels": 0,
            "tracked_kernels": [],
            "warnings": ["No readable frames captured. Please ensure camera is connected."]
        }

    best_frame_record = sharp_frames[0]  # The sharpest frame
    best_img_bgr = best_frame_record['img_bgr']

    # Load YOLO model
    model_path, model_name = find_trained_model()
    if not model_path:
        return {
            "success": False,
            "status": "ERROR",
            "suggestion": "Review",
            "error": "No trained YOLO detector weights found in models/",
            "kernels_found": 0,
            "total_kernels": 0,
            "tracked_kernels": []
        }
    model = get_cached_yolo_model(model_path)

    # 2. Run detector on each of the sharpest frames
    frames_detections = []
    for sf in sharp_frames:
        dets = detect_frame_kernels(
            img_bgr=sf['img_bgr'],
            model=model,
            imgsz=imgsz,
            conf_floor=conf_floor,
            ignore_zones=ignore_zones,
            augment=augment,
            product_filter=product
        )
        frames_detections.append(dets)

    # 3. Merge kernels across frames by position
    tracked_kernels = merge_kernels_across_frames(frames_detections)
    total_kernels = len(tracked_kernels)

    defect_kernels = [tk for tk in tracked_kernels if tk["verdict"] == "Defect"]
    healthy_kernels = [tk for tk in tracked_kernels if tk["verdict"] == "Normal"]
    uncertain_kernels = [tk for tk in tracked_kernels if tk["verdict"] == "Uncertain"]

    defect_count = len(defect_kernels)
    good_count = len(healthy_kernels)
    uncertain_count = len(uncertain_kernels)

    defect_pct = round((defect_count / float(total_kernels) * 100.0), 1) if total_kernels > 0 else 0.0
    good_pct = round(100.0 - defect_pct, 1) if total_kernels > 0 else 0.0

    # Calculate overall average confidence
    all_confs = [tk["avg_confidence"] for tk in tracked_kernels]
    overall_conf = round(float(np.mean(all_confs)), 4) if all_confs else 0.0
    conf_pct_str = f"{round(overall_conf * 100.0, 1)}%"

    warnings = []

    # 4. Check Minimum Kernels Threshold (Requirement 4: fewer than 3 kernels gives RETAKE)
    if total_kernels < min_kernels:
        suggestion = "Retake"
        status = "NEEDS_RETAKE"
        reason = f"Fewer than {min_kernels} kernels detected ({total_kernels} found). Sample must fill frame with at least {min_kernels} distinct kernels."
        next_step = "Place at least 3 kernels in the framing guide on a plain background, lamp on, and press Scan again."
        warnings.append(reason)
    elif defect_count > 0 or defect_pct > 5.0:
        suggestion = "Reject"
        status = "REJECTED"
        reason = f"{defect_count} defective/moldy kernel(s) detected ({defect_pct}% defect rate exceeds 5% tolerance)."
        next_step = "Sample exceeds critical defect limit. Quarantine and reject lot or arrange second sampling."
    elif uncertain_count > 0:
        suggestion = "Review"
        status = "NEEDS_REVIEW"
        reason = f"{uncertain_count} kernel(s) have uncertain classifications. Manual visual verification required."
        next_step = "Inspect highlighted kernels under magnification or confirm verdict manually."
    else:
        suggestion = "Pass"
        status = "APPROVED"
        reason = f"All {total_kernels} kernels verified clean and normal (0.0% defects)."
        next_step = "Sample meets all visual quality standards. Confirm approval."

    # 5. Annotate the best sharp frame
    annotated_bgr = annotate_kernels_on_frame(
        best_img_bgr,
        tracked_kernels,
        ignore_zones=ignore_zones,
        title_hud=f"AI Stabilized Scan | {total_kernels} Kernels | {suggestion.upper()}"
    )

    elapsed_ms = round((time.time() - t_start) * 1000, 1)

    return {
        "success": True,
        "status": status,
        "suggestion": suggestion,
        "decision_state": suggestion.upper(),
        "decision_reason": reason,
        "next_step": next_step,
        "kernels_found": total_kernels,
        "total_kernels": total_kernels,
        "good_count": good_count,
        "defect_count": defect_count,
        "uncertain_count": uncertain_count,
        "good_pct": good_pct,
        "defect_pct": defect_pct,
        "avg_confidence": overall_conf,
        "confidence_percent": conf_pct_str,
        "frames_evaluated_count": len(sharp_frames),
        "total_burst_frames": len(frames),
        "sharpness_scores": [round(sf['sharpness'], 1) for sf in sharp_frames],
        "best_frame_sharpness": round(best_frame_record['sharpness'], 1),
        "best_frame_bgr": best_img_bgr,
        "annotated_bgr": annotated_bgr,
        "tracked_kernels": tracked_kernels,
        "warnings": warnings,
        "pipeline_settings": {
            "imgsz": imgsz,
            "conf_floor": conf_floor,
            "augment_tta": augment,
            "min_kernels": min_kernels
        },
        "elapsed_time_ms": elapsed_ms
    }
