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
    "best.pt",
    "food_defect_yolov8.pt",
    "yolov8n.pt",
    "yolov8s.pt"
]

# Standard food manufacturing defect taxonomy
FOOD_DEFECT_TAXONOMY = {
    "mold_spot": {"category": "Contamination", "severity": "CRITICAL", "description": "Fungal or mold growth spot on seed/kernel"},
    "broken_kernel": {"category": "Physical Damage", "severity": "WARNING", "description": "Mechanically cracked, split, or crushed seed"},
    "foreign_matter": {"category": "Foreign Material", "severity": "CRITICAL", "description": "Stone, stalk, soil, or synthetic particle"},
    "discoloration": {"category": "Quality Degradation", "severity": "WARNING", "description": "Abnormal surface pigmentation or oxidation"},
    "insect_damage": {"category": "Infestation", "severity": "CRITICAL", "description": "Bore holes, insect frass, or pest chewing marks"},
    "packaging_tear": {"category": "Packaging Integrity", "severity": "CRITICAL", "description": "Rupture, puncture, or split in primary container"},
    "seal_breach": {"category": "Packaging Integrity", "severity": "CRITICAL", "description": "Broken, misaligned, or unsealed safety closure"}
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
        "model_path": model_path,
        "ultralytics_installed": True,
        "torch_installed": True,
        "message": f"YOLOv8 visual inspection engine is active using '{model_name}'.",
        "training_workflow": []
    }


def run_yolo_visual_inspection(raw_image_path: str, output_annotated_dir: str = None, conf_threshold: float = 0.25) -> dict:
    """
    Executes YOLOv8 defect detection on an uploaded inspection image.
    
    If no trained model is found in models/:
    - Strictly avoids generating fake inspection results.
    - Returns structured status MODEL_NOT_FOUND with configuration instructions.
    
    If a trained model is found:
    - Runs inference with Ultralytics YOLO.
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
        results = model.predict(source=raw_image_path, conf=conf_threshold, save=False)
        inference_time_ms = round((time.time() - start_time) * 1000, 1)

        first_res = results[0]
        boxes = first_res.boxes
        names = first_res.names

        detected_defects = []
        orig_w = first_res.orig_shape[1] if hasattr(first_res, 'orig_shape') else 1000
        orig_h = first_res.orig_shape[0] if hasattr(first_res, 'orig_shape') else 1000

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

                taxonomy_info = FOOD_DEFECT_TAXONOMY.get(
                    raw_cls_name.lower().replace(" ", "_"),
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

        # Use Ultralytics plot() to draw bounding boxes and labels
        annotated_plot = first_res.plot()
        cv2.imwrite(annotated_full_path, annotated_plot)

        total_count = len(detected_defects)
        summary = (
            f"Detected {total_count} visual defect(s) requiring QC review"
            if total_count > 0 else
            "No visual defects detected. Specimen intact within visual confidence threshold."
        )

        return {
            "success": True,
            "model_status": "DEFECTS_DETECTED" if total_count > 0 else "NO_DEFECTS",
            "model_version": f"YOLOv8 ({engine_status['model_name']})",
            "inference_time_ms": inference_time_ms,
            "total_defects_count": total_count,
            "detected_defects": detected_defects,
            "summary": summary,
            "status_message": f"Inference complete on {len(boxes)} candidate region(s).",
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
