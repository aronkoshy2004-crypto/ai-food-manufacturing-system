import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path

def draw_readable_annotations(img_bgr, boxes, names, is_dense=False):
    canvas = img_bgr.copy()
    h, w = canvas.shape[:2]
    
    # Line width: 1px for dense clusters, 2px for sparse
    box_lw = 1 if (is_dense or len(boxes) > 20) else max(2, int(min(w, h) / 300))
    font_scale = 0.30 if is_dense else 0.45
    font_thickness = 1
    
    # Sort boxes by confidence descending so highest confidence badges are placed first
    sorted_boxes = sorted(boxes, key=lambda b: float(b.conf[0]), reverse=True) if len(boxes) else []
    
    placed_badge_rects = []
    
    def rects_overlap(r1, r2):
        # r = (x1, y1, x2, y2)
        return not (r1[2] < r2[0] or r1[0] > r2[2] or r1[3] < r2[1] or r1[1] > r2[3])

    for b in sorted_boxes:
        cid = int(b.cls[0])
        cname = names[cid]
        conf = float(b.conf[0])
        x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
        
        # Clamp coordinates
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        
        is_defect = "moldy" in cname.lower() and "not_moldy" not in cname.lower()
        
        # Crimson Red for defect, Emerald Green for healthy
        color = (40, 40, 230) if is_defect else (40, 195, 45) # BGR
        
        # Draw clean crisp bounding box
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, box_lw)
        
        # Compact readable label text
        short_name = cname.replace("Peanut_", "").replace("Corn_", "").replace("Sunflower_", "")
        if is_dense:
            badge_text = f"{short_name} {int(conf * 100)}%"
        else:
            badge_text = f"{cname} {conf * 100:.1f}%"
            
        (tw, th), baseline = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
        
        # Candidate badge locations:
        # 1. Above box
        # 2. Below box
        # 3. Inside box top
        candidate_rects = [
            (x1, max(0, y1 - th - 4), min(w, x1 + tw + 4), y1),
            (x1, y2, min(w, x1 + tw + 4), min(h, y2 + th + 4)),
            (x1, y1, min(w, x1 + tw + 4), min(h, y1 + th + 4))
        ]
        
        best_rect = None
        for cand in candidate_rects:
            overlaps = any(rects_overlap(cand, placed) for placed in placed_badge_rects)
            if not overlaps:
                best_rect = cand
                break
                
        # If dense and all positions overlap, only draw badge if confidence is high (> 0.40)
        # Otherwise suppress the badge text to keep kernels visible!
        if best_rect is None and conf >= 0.40:
            best_rect = candidate_rects[0] # Allow minor overlap for high-confidence detections
            
        if best_rect is not None:
            rx1, ry1, rx2, ry2 = best_rect
            # Background pill with slight transparency or solid
            cv2.rectangle(canvas, (rx1, ry1), (rx2, ry2), color, -1)
            # Text
            cv2.putText(
                canvas,
                badge_text,
                (rx1 + 2, ry2 - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                font_thickness,
                cv2.LINE_AA
            )
            placed_badge_rects.append(best_rect)

    return canvas

def main():
    m = YOLO("models/combined_best.pt")
    
    # 1. Test peanut_th_o2 (Inspection #63 image)
    img1_path = "datasets/raw_materials_combined/images/test/peanut_th_o2_jpg.rf.1f4aecb860ea5b664f926758694a8991.jpg"
    img1 = cv2.imread(img1_path)
    res1 = m.predict(img1_path, conf=0.12, iou=0.50, verbose=False)[0]
    out1 = draw_readable_annotations(img1, res1.boxes, res1.names, is_dense=True)
    cv2.imwrite("scratch/readable_peanut_th_o2.jpg", out1)
    print(f"Peanut tray: {len(res1.boxes)} boxes rendered cleanly into scratch/readable_peanut_th_o2.jpg")

    # 2. Test Screenshot_2026-09-09_221944.png (Inspection #62 image)
    img2_path = "static/uploads/raw/20260910_072004_Screenshot_2026-09-09_221944.png"
    img2 = cv2.imread(img2_path)
    res2 = m.predict(img2_path, conf=0.12, iou=0.50, verbose=False)[0]
    out2 = draw_readable_annotations(img2, res2.boxes, res2.names, is_dense=True)
    cv2.imwrite("scratch/readable_corn_inspection_62.jpg", out2)
    print(f"Inspection #62: {len(res2.boxes)} boxes rendered cleanly into scratch/readable_corn_inspection_62.jpg")

if __name__ == "__main__":
    main()
