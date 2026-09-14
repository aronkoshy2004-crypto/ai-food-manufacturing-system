"""
YOLOv8 AI-Assisted Visual Quality Inspection Service
PRD AI Inspection Engine — Ultralytics YOLOv8 Integration
"""
import os
import time
import datetime
import logging

logger = logging.getLogger(__name__)

# Model search paths in priority order inside models/ directory
MODEL_SEARCH_NAMES = [
    "combined_corrected_best.pt",
    "combined_best.pt",
    "best.pt",
    "food_defect_yolov8.pt",
    "yolov8n.pt",
    "yolov8s.pt"
]

# Standard food manufacturing defect taxonomy
FOOD_DEFECT_TAXONOMY = {
    "moldy": {"category": "Contamination", "severity": "CRITICAL", "description": "Fungal or mold growth on raw material"},
    "peanut_moldy": {"category": "Contamination", "severity": "CRITICAL", "description": "Fungal or mold growth on peanut kernel"},
    "corn_moldy": {"category": "Contamination", "severity": "CRITICAL", "description": "Fungal or mold growth on corn kernel"},
    "sunflower_moldy": {"category": "Contamination", "severity": "CRITICAL", "description": "Fungal or mold growth on sunflower seed"},
    "mold_spot": {"category": "Contamination", "severity": "CRITICAL", "description": "Fungal or mold growth spot on seed/kernel"},
    "pest_damage": {"category": "Infestation", "severity": "CRITICAL", "description": "Insect bore holes, chewing, or frass"},
    "insect_damage": {"category": "Infestation", "severity": "CRITICAL", "description": "Bore holes, insect frass, or pest chewing marks"},
    "broken": {"category": "Physical Damage", "severity": "WARNING", "description": "Mechanically cracked or split kernel"},
    "broken_kernel": {"category": "Physical Damage", "severity": "WARNING", "description": "Mechanically cracked, split, or crushed seed"},
    "shriveled": {"category": "Quality Degradation", "severity": "WARNING", "description": "Dehydrated, stunted, or shriveled kernel"},
    "discoloration": {"category": "Quality Degradation", "severity": "WARNING", "description": "Abnormal surface pigmentation or oxidation"},
    "foreign_matter": {"category": "Foreign Material", "severity": "CRITICAL", "description": "Stone, stalk, soil, or synthetic particle"},
    "bad": {"category": "Defect", "severity": "CRITICAL", "description": "Spoiled or contaminated raw material"},
    "packaging_tear": {"category": "Packaging Integrity", "severity": "CRITICAL", "description": "Rupture, puncture, or split in primary container"},
    "seal_breach": {"category": "Packaging Integrity", "severity": "CRITICAL", "description": "Broken, misaligned, or unsealed safety closure"}
}

# Classes that represent normal, healthy specimens (NOT defects)
HEALTHY_CLASSES = {
    "not_moldy",
    "peanut_not_moldy",
    "corn_not_moldy",
    "sunflower_not_moldy",
    "normal",
    "good"
}


def get_models_dir() -> str:
    """Returns absolute path to models/ directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    return os.path.join(project_root, "models")


def find_trained_model() -> tuple:
    """
    Searches models/ for a valid trained YOLOv8 model weight file (.pt).
    Returns (model_path, model_filename) or (None, None).
    """
    models_dir = get_models_dir()
    for fname in MODEL_SEARCH_NAMES:
        path = os.path.join(models_dir, fname)
        if os.path.isfile(path):
            return path, fname
    return None, None


def check_ai_engine_status() -> dict:
    """
    Checks environment capabilities and model file availability.
    Returns diagnostic dictionary without throwing exceptions.
    """
    model_path, model_name = find_trained_model()
    
    ultralytics_installed = False
    torch_installed = False
    try:
        import ultralytics
        ultralytics_installed = True
    except ImportError:
        pass

    try:
        import torch
        torch_installed = True
    except ImportError:
        pass

    if not ultralytics_installed or not torch_installed:
        return {
            "ready": False,
            "status": "DEPENDENCY_MISSING",
            "model_name": model_name or "None",
            "model_path": model_path,
            "ultralytics_installed": ultralytics_installed,
            "torch_installed": torch_installed,
            "message": (
                "Ultralytics YOLOv8 library or PyTorch is not yet installed in the current Python environment. "
                "Run 'pip install ultralytics' once disk space permits to enable PyTorch tensor operations."
            ),
            "training_workflow": [
                "1. Collect domain food inspection photos (peanuts, corn, sunflower seeds)",
                "2. Label bounding boxes and defect classes using Roboflow or CVAT",
                "3. Train YOLOv8: yolo detect train data=food.yaml model=yolov8n.pt epochs=50",
                "4. Place exported 'best.pt' into the models/ directory"
            ]
        }

    if not model_path:
        return {
            "ready": False,
            "status": "MODEL_NOT_FOUND",
            "model_name": None,
            "model_path": None,
            "ultralytics_installed": True,
            "torch_installed": True,
            "message": (
                "No trained model found at models/best.pt. "
                "Installing YOLOv8 does not automatically detect defects in raw materials (peanuts, corn, sunflower seeds). "
                "You must train YOLOv8 on your labeled food defect dataset and save the resulting weights as 'models/best.pt'."
            ),
            "training_workflow": [
                "1. Food Images: Capture dock/line photos of raw materials and products",
                "2. Label Defects: Annotate classes (mold, cracked seed, foreign matter, tear)",
                "3. Train YOLOv8: yolo detect train data=food_defects.yaml model=yolov8n.pt",
                "4. Integrate: Save trained weights as models/best.pt"
            ]
        }

    return {
        "ready": True,
        "status": "READY",
        "model_name": model_name,
        "model_file": model_name,
        "model_path": model_path,
        "classes_count": 6 if "combined" in model_name else 2,
        "device": "CPU",
        "ultralytics_installed": True,
        "torch_installed": True,
        "message": f"YOLOv8 visual inspection engine is active using '{model_name}'.",
        "training_workflow": []
    }


def draw_readable_annotations(raw_image_path: str, boxes, names, conf_threshold: float = 0.12, iou_threshold: float = 0.50, defect_conf_min: float = 0.12):
    """
    Renders clean, high-readability annotations for dense cluster images.
    Features:
    - Slim bounding boxes (1px for dense clusters, 2px for sparse).
    - Compact status badges ('Mold 85%', 'Clean 92%') with dark contrast backgrounds.
    - Multi-candidate label placement with overlap collision avoidance.
    - Filters defect noise below defect_conf_min (recalibrated to >= 0.35 in dense clusters).
    - Top HUD summary banner with counts and inspection metadata.
    """
    import cv2
    import numpy as np

    img = cv2.imread(raw_image_path)
    if img is None:
        return None

    h, w = img.shape[:2]
    scale = 1.0
    if max(h, w) < 800:
        scale = 800.0 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)
        h, w = img.shape[:2]

    detections = []
    if boxes is not None and len(boxes) > 0:
        for box in boxes:
            cls_id = int(box.cls[0].item())
            cls_name = names.get(cls_id, f"Class_{cls_id}")
            conf = float(box.conf[0].item())
            xyxy = box.xyxy[0].tolist()
            cls_key = cls_name.lower().replace(" ", "_")
            is_healthy = cls_key in HEALTHY_CLASSES

            # Filter low-confidence defect false positives (e.g. shadow/crevice noise in dense clusters)
            if not is_healthy and conf < defect_conf_min:
                continue

            detections.append({
                "cls_id": cls_id,
                "cls_name": cls_name,
                "conf": conf,
                "xyxy": [c * scale for c in xyxy],
                "is_healthy": is_healthy
            })

    # Sort descending by confidence so higher confidence items get priority placement
    detections.sort(key=lambda d: d["conf"], reverse=True)

    COLOR_DEFECT = (45, 45, 230)    # Crimson Red in BGR
    COLOR_HEALTHY = (45, 185, 75)   # Emerald Green in BGR

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.36
    font_thickness = 1

    occupied_labels = []

    def overlaps(r1, r_list):
        x1, y1, x2, y2 = r1
        for ox1, oy1, ox2, oy2 in r_list:
            if not (x2 < ox1 or x1 > ox2 or y2 < oy1 or y1 > oy2):
                return True
        return False

    defect_count = sum(1 for d in detections if not d["is_healthy"])
    healthy_count = sum(1 for d in detections if d["is_healthy"])

    # 1. Draw bounding boxes (1px for dense clusters > 25 boxes, 2px otherwise)
    box_thickness = 1 if len(detections) > 25 else 2
    for d in detections:
        x1, y1, x2, y2 = [int(v) for v in d["xyxy"]]
        color = COLOR_HEALTHY if d["is_healthy"] else COLOR_DEFECT
        cv2.rectangle(img, (x1, y1), (x2, y2), color, box_thickness, cv2.LINE_AA)

    # 2. Draw smart collision-avoiding badges
    for d in detections:
        x1, y1, x2, y2 = [int(v) for v in d["xyxy"]]
        color = COLOR_HEALTHY if d["is_healthy"] else COLOR_DEFECT

        state = "Clean" if d["is_healthy"] else "Mold"
        label_text = f"{state} {int(round(d['conf'] * 100))}%"

        (tw, th), baseline = cv2.getTextSize(label_text, font, font_scale, font_thickness)
        pad_x, pad_y = 3, 2
        bw = tw + pad_x * 2
        bh = th + pad_y * 2 + baseline

        candidates = [
            (x1, y1 - bh, x1 + bw, y1),
            (x1, y1, x1 + bw, y1 + bh),
            (x1, y2, x1 + bw, y2 + bh),
            (x2 - bw, y1 - bh, x2, y1),
        ]

        chosen = None
        for cand in candidates:
            cx1, cy1, cx2, cy2 = cand
            if cx1 >= 0 and cy1 >= 0 and cx2 < w and cy2 < h:
                if not overlaps(cand, occupied_labels):
                    chosen = cand
                    break

        if chosen is not None:
            occupied_labels.append(chosen)
            cx1, cy1, cx2, cy2 = chosen
            cv2.rectangle(img, (cx1, cy1), (cx2, cy2), (20, 20, 20), -1)
            cv2.rectangle(img, (cx1, cy1), (cx2, cy2), color, 1, cv2.LINE_AA)
            cv2.putText(img, label_text, (cx1 + pad_x, cy1 + th + pad_y), font, font_scale, (255, 255, 255), font_thickness, cv2.LINE_AA)
        else:
            # Draw micro dot indicator at corner so detection is marked without obscuring kernel
            cv2.circle(img, (x1 + 3, y1 + 3), 2, color, -1, cv2.LINE_AA)

    # 3. Top HUD status banner
    hud_h = 32
    hud_bg = np.zeros((hud_h, w, 3), dtype=np.uint8)
    cv2.rectangle(hud_bg, (0, 0), (w, hud_h), (24, 24, 28), -1)

    cv2.circle(hud_bg, (15, 16), 5, COLOR_DEFECT, -1, cv2.LINE_AA)
    cv2.putText(hud_bg, f"Defects: {defect_count}", (26, 20), font, 0.42, (230, 230, 230), 1, cv2.LINE_AA)

    cv2.circle(hud_bg, (150, 16), 5, COLOR_HEALTHY, -1, cv2.LINE_AA)
    cv2.putText(hud_bg, f"Healthy: {healthy_count}", (161, 20), font, 0.42, (230, 230, 230), 1, cv2.LINE_AA)

    if defect_conf_min > conf_threshold:
        meta_text = f"Total: {len(detections)} | IoU: {iou_threshold} | Defect Conf >= {int(round(defect_conf_min*100))}% (Dense Calibrated)"
    else:
        meta_text = f"Total: {len(detections)} | IoU: {iou_threshold} | Conf >= {int(round(conf_threshold*100))}%"
    cv2.putText(hud_bg, meta_text, (max(280, w - 440), 20), font, 0.38, (180, 180, 180), 1, cv2.LINE_AA)

    return np.vstack([hud_bg, img])


def run_yolo_visual_inspection(raw_image_path: str, output_annotated_dir: str = None, conf_threshold: float = 0.12, iou_threshold: float = 0.50) -> dict:
    """
    Executes YOLOv8 defect detection on an uploaded inspection image.
    
    If no trained model is found in models/:
    - Strictly avoids generating fake inspection results.
    - Returns structured status MODEL_NOT_FOUND with configuration instructions.
    
    If a trained model is found:
    - Runs inference with Ultralytics YOLO with permanent default iou_threshold=0.50 (suppressing duplicates in dense clusters)
      and conf_threshold=0.12.
    - Saves an annotated image with bounding boxes to static/uploads/annotated/.
    - Returns classified defects, confidence scores, and coordinates.
    """
    timestamp_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    engine_status = check_ai_engine_status()

    # Case 1: Model or dependencies missing -> Return honest configuration diagnostic
    if not engine_status["ready"]:
        return {
            "success": False,
            "model_status": engine_status["status"],
            "model_version": engine_status.get("model_name") or "YOLOv8-Unconfigured",
            "inference_time_ms": 0.0,
            "total_defects_count": 0,
            "detected_defects": [],
            "summary": "Model Configuration Required",
            "status_message": engine_status["message"],
            "training_workflow": engine_status.get("training_workflow", []),
            "annotated_image_url": None,
            "inspection_timestamp": timestamp_str
        }

    # Case 2: Model is available -> Run Ultralytics YOLOv8 inference
    model_path = engine_status["model_path"]
    start_time = time.time()

    try:
        from ultralytics import YOLO
        import cv2

        model = YOLO(model_path)
        results = model.predict(source=raw_image_path, conf=conf_threshold, iou=iou_threshold, save=False)
        inference_time_ms = round((time.time() - start_time) * 1000, 1)

        if not results or len(results) == 0:
            return {
                "success": False,
                "model_status": "IMAGE_UNREADABLE",
                "model_version": f"YOLOv8 ({engine_status['model_name']})",
                "inference_time_ms": inference_time_ms,
                "total_defects_count": 0,
                "detected_defects": [],
                "healthy_specimens_count": 0,
                "detected_healthy": [],
                "summary": "Could not decode or process image file.",
                "status_message": "Image format unreadable or corrupt.",
                "annotated_image_url": None,
                "inspection_timestamp": timestamp_str
            }

        first_res = results[0]
        boxes = first_res.boxes
        names = first_res.names

        detected_defects = []
        detected_healthy = []
        orig_w = first_res.orig_shape[1] if hasattr(first_res, 'orig_shape') else 1000
        orig_h = first_res.orig_shape[0] if hasattr(first_res, 'orig_shape') else 1000

        total_raw_boxes = len(boxes) if boxes is not None else 0
        is_dense_cluster = total_raw_boxes >= 20
        # Defect confidence threshold recalibration: in dense clusters, raise defect threshold to >= 0.35
        # to filter ambient shadows, crevices, and skin wrinkles while catching genuine mold (60-80%+)
        defect_conf_min = 0.35 if is_dense_cluster else conf_threshold

        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                cls_id = int(box.cls[0].item())
                raw_cls_name = names.get(cls_id, f"Class_{cls_id}")
                conf = float(box.conf[0].item())
                
                # Bounding box xyxy in pixels
                xyxy = box.xyxy[0].tolist()
                x1, y1, x2, y2 = xyxy[0], xyxy[1], xyxy[2], xyxy[3]

                # Normalized percentages (0 - 100%)
                norm_x = round((x1 / orig_w) * 100.0, 1)
                norm_y = round((y1 / orig_h) * 100.0, 1)
                norm_w = round(((x2 - x1) / orig_w) * 100.0, 1)
                norm_h = round(((y2 - y1) / orig_h) * 100.0, 1)

                cls_key = raw_cls_name.lower().replace(" ", "_")

                # Check if this detection is a normal/healthy item rather than a defect
                if cls_key in HEALTHY_CLASSES:
                    detected_healthy.append({
                        "specimen_class": raw_cls_name,
                        "status": "HEALTHY",
                        "confidence": round(conf, 3),
                        "confidence_percent": f"{conf * 100:.1f}%",
                        "bbox_x": norm_x,
                        "bbox_y": norm_y,
                        "bbox_w": norm_w,
                        "bbox_h": norm_h
                    })
                    continue

                # Recalibration: filter out low-confidence defect false positives in dense clusters
                if conf < defect_conf_min:
                    continue

                taxonomy_info = FOOD_DEFECT_TAXONOMY.get(
                    cls_key,
                    {"category": "Visual Anomaly", "severity": "WARNING", "description": raw_cls_name}
                )

                detected_defects.append({
                    "defect_class": raw_cls_name,
                    "category": taxonomy_info["category"],
                    "severity": taxonomy_info["severity"],
                    "confidence": round(conf, 3),
                    "confidence_percent": f"{conf * 100:.1f}%",
                    "bbox_x": norm_x,
                    "bbox_y": norm_y,
                    "bbox_w": norm_w,
                    "bbox_h": norm_h
                })

        # Generate annotated image with bounding boxes
        annotated_filename = "annotated_" + os.path.basename(raw_image_path)
        if not output_annotated_dir:
            output_annotated_dir = os.path.join(os.path.dirname(raw_image_path), "..", "annotated")
        
        os.makedirs(output_annotated_dir, exist_ok=True)
        annotated_full_path = os.path.join(output_annotated_dir, annotated_filename)

        # Render high-readability annotated image with collision avoidance and compact badges
        rendered_image = draw_readable_annotations(
            raw_image_path=raw_image_path,
            boxes=boxes,
            names=names,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            defect_conf_min=defect_conf_min
        )
        if rendered_image is not None:
            cv2.imwrite(annotated_full_path, rendered_image)
        else:
            annotated_plot = first_res.plot()
            cv2.imwrite(annotated_full_path, annotated_plot)

        total_count = len(detected_defects)
        healthy_count = len(detected_healthy)

        if total_count > 0:
            defect_types = ", ".join(sorted(list(set(d["defect_class"] for d in detected_defects))))
            summary = f"Detected {total_count} visual defect(s) ({defect_types}) requiring QC review"
            model_status = "DEFECTS_DETECTED"
        elif healthy_count > 0:
            summary = f"YOLOv8 Analysis Complete: Specimen visually clean ({healthy_count} healthy item(s) verified, 0 defects)."
            model_status = "NO_DEFECTS"
        else:
            summary = "No visual defects detected. Specimen intact within visual confidence threshold."
            model_status = "NO_DEFECTS"

        status_msg = f"Inference complete on {len(boxes)} candidate region(s)."
        if is_dense_cluster:
            status_msg = f"Inference complete on {len(boxes)} candidate region(s) (dense cluster calibrated: defect conf >= {int(round(defect_conf_min*100))}%)."

        return {
            "success": True,
            "model_status": model_status,
            "model_version": f"YOLOv8 ({engine_status['model_name']})",
            "inference_time_ms": inference_time_ms,
            "total_defects_count": total_count,
            "detected_defects": detected_defects,
            "healthy_specimens_count": healthy_count,
            "detected_healthy": detected_healthy,
            "summary": summary,
            "status_message": status_msg,
            "annotated_image_url": f"/static/uploads/annotated/{annotated_filename}",
            "inspection_timestamp": timestamp_str
        }

    except Exception as e:
        logger.exception("Error executing YOLOv8 model inference")
        return {
            "success": False,
            "model_status": "INFERENCE_ERROR",
            "model_version": "YOLOv8",
            "inference_time_ms": 0.0,
            "total_defects_count": 0,
            "detected_defects": [],
            "summary": "Inference Execution Error",
            "status_message": f"An error occurred while running YOLOv8 forward pass: {str(e)}",
            "annotated_image_url": None,
            "inspection_timestamp": timestamp_str
        }
