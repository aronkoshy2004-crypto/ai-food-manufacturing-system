import os
import sys
import json
from pathlib import Path
from ultralytics import YOLO

def main():
    project_root = Path(r"c:\Users\L E N O V O\Food man")
    model_path = project_root / "runs" / "detect" / "raw_materials_combined_resumed_epochs21_50" / "weights" / "best.pt"
    backup_model_path = project_root / "models" / "combined_epoch50_backup.pt"
    
    print(f"Loading YOLO model from: {model_path}")
    print(f"Exists: {model_path.exists()} (Size: {model_path.stat().st_size if model_path.exists() else 0} bytes)")
    print(f"Epoch 50 Backup in models/: {backup_model_path.exists()} (Size: {backup_model_path.stat().st_size if backup_model_path.exists() else 0} bytes)")
    
    model = YOLO(str(model_path))
    print(f"Model Task: {model.task}")
    print(f"Model Class Names: {model.names}")
    
    # Select test images across commodity types from unseen test set
    test_dir = project_root / "datasets" / "raw_materials_combined" / "images" / "test"
    
    selected_images = [
        ("Corn Moldy Test Sample", test_dir / "corn_20220327_0107_jpg.rf.0902cfd33ed9e744116cdf33e7b66b09.jpg"),
        ("Corn Healthy / Not Moldy Test Sample", test_dir / "corn_healthy-18_jpg.rf.9cc8d6aaefa9a4f7c6a2428f2786885e.jpg"),
        ("Peanut Dense Tray Test Sample", test_dir / "peanut_th_t8_jpg.rf.1b3ce486d9f00aa56dad9e4f957de4e6.jpg"),
        ("Peanut Augmented Single Test Sample", test_dir / "peanut_aug_IMG20240607225203_jpg.rf.23998ad5bd1d0ee66d636d6fc899ae42.jpg"),
        ("Sunflower Moldy Test Sample", test_dir / "sunflower_20250731_112859_jpg.rf.d8df887ed52efabf39ad5f4638014aa8.jpg"),
        ("Sunflower Bulk Test Sample", test_dir / "sunflower_20250803_141516_jpg.rf.57e9c50f48c60ebc00d89be7ff65a71f.jpg"),
    ]
    
    output_dir = project_root / "scratch" / "predictions_epoch50"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results_list = []
    
    for title, img_path in selected_images:
        if not img_path.exists():
            print(f"[WARN] File not found: {img_path}")
            continue
        
        # Run prediction
        res = model.predict(
            source=str(img_path),
            conf=0.25,
            iou=0.45,
            imgsz=416,
            save=True,
            project=str(output_dir),
            name="predict_run",
            exist_ok=True
        )[0]
        
        boxes = res.boxes
        detections = []
        counts = {}
        for b in boxes:
            cls_id = int(b.cls[0])
            cls_name = model.names[cls_id]
            conf = float(b.conf[0])
            xyxy = [round(float(coord), 1) for coord in b.xyxy[0]]
            detections.append({
                "class_id": cls_id,
                "class_name": cls_name,
                "confidence": round(conf, 4),
                "bbox_xyxy": xyxy
            })
            counts[cls_name] = counts.get(cls_name, 0) + 1
            
        speed = {k: round(v, 2) for k, v in res.speed.items()}
        
        info = {
            "title": title,
            "filename": img_path.name,
            "total_detections": len(detections),
            "class_counts": counts,
            "speed_ms": speed,
            "detections": detections[:10]  # top 10 for display
        }
        results_list.append(info)
        
        print("\n" + "="*70)
        print(f"IMAGE: {title} ({img_path.name})")
        print(f"Total Detections: {len(detections)}")
        print(f"Class Breakdown: {counts}")
        print(f"Inference Speed: {speed}")
        print("Sample Detections:")
        for det in detections[:5]:
            print(f"  - {det['class_name']}: conf={det['confidence']:.2f}, bbox={det['bbox_xyxy']}")
        if len(detections) > 5:
            print(f"  ... and {len(detections)-5} more detections")

    # Save detailed JSON summary
    summary_path = output_dir / "prediction_results.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results_list, f, indent=2)
    print(f"\nSaved detailed prediction summary to: {summary_path}")

if __name__ == "__main__":
    main()
