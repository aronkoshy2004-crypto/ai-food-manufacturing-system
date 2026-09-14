import os
import cv2
import numpy as np
from ultralytics import YOLO

def render_readable_annotations(image_path, model_path, output_path, conf_thresh=0.12, iou_thresh=0.50):
    model = YOLO(model_path)
    res = model.predict(source=image_path, conf=conf_thresh, iou=iou_thresh, verbose=False)[0]
    
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image {image_path}")
    h, w = img.shape[:2]
    
    # Scale up smaller images for crisp text rendering
    scale = 1.0
    if max(h, w) < 800:
        scale = 800.0 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)
        h, w = img.shape[:2]
    
    boxes = res.boxes
    names = res.names
    
    detections = []
    for box in boxes:
        cls_id = int(box.cls[0].item())
        cls_name = names.get(cls_id, f'Class_{cls_id}')
        conf = float(box.conf[0].item())
        xyxy = box.xyxy[0].tolist()
        is_healthy = 'not_moldy' in cls_name.lower() or 'clean' in cls_name.lower() or 'good' in cls_name.lower()
        detections.append({
            'cls_id': cls_id,
            'cls_name': cls_name,
            'conf': conf,
            'xyxy': [c * scale for c in xyxy],
            'is_healthy': is_healthy
        })
    # Sort descending by confidence so higher confidence gets priority placement
    detections.sort(key=lambda d: d['conf'], reverse=True)
    
    COLOR_DEFECT = (45, 45, 230)    # Crimson Red in BGR
    COLOR_HEALTHY = (45, 185, 75)   # Emerald Green in BGR
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.36
    font_thickness = 1
    
    occupied_labels = []
    
    def overlaps(rect1, rect_list):
        x1, y1, x2, y2 = rect1
        for ox1, oy1, ox2, oy2 in rect_list:
            if not (x2 < ox1 or x1 > ox2 or y2 < oy1 or y1 > oy2):
                return True
        return False
    
    defect_count = sum(1 for d in detections if not d['is_healthy'])
    healthy_count = sum(1 for d in detections if d['is_healthy'])
    
    # 1. Draw thin bounding boxes (1px for dense clusters, 2px for sparse)
    box_thickness = 1 if len(detections) > 25 else 2
    for d in detections:
        x1, y1, x2, y2 = [int(v) for v in d['xyxy']]
        color = COLOR_HEALTHY if d['is_healthy'] else COLOR_DEFECT
        cv2.rectangle(img, (x1, y1), (x2, y2), color, box_thickness, cv2.LINE_AA)
        
    # 2. Draw smart compact labels
    for d in detections:
        x1, y1, x2, y2 = [int(v) for v in d['xyxy']]
        color = COLOR_HEALTHY if d['is_healthy'] else COLOR_DEFECT
        
        # Abbreviate label: 'Corn_Moldy' -> 'Mold 72%', 'Corn_Not_Moldy' -> 'Clean 88%'
        prefix = d['cls_name'].split('_')[0] if '_' in d['cls_name'] else ''
        state = 'Clean' if d['is_healthy'] else 'Mold'
        label_text = f"{state} {int(round(d['conf'] * 100))}%"
        
        (tw, th), baseline = cv2.getTextSize(label_text, font, font_scale, font_thickness)
        pad_x = 3
        pad_y = 2
        
        bw = tw + pad_x * 2
        bh = th + pad_y * 2 + baseline
        
        candidates = [
            (x1, y1 - bh, x1 + bw, y1),                    # Top
            (x1, y1, x1 + bw, y1 + bh),                    # Inside Top
            (x1, y2, x1 + bw, y2 + bh),                    # Below
            (x2 - bw, y1 - bh, x2, y1),                    # Top right
        ]
        
        chosen = None
        for cand in candidates:
            cx1, cy1, cx2, cy2 = cand
            if cx1 >= 0 and cy1 >= 0 and cx2 < w and cy2 < h:
                if not overlaps(cand, occupied_labels):
                    chosen = cand
                    break
        
        if chosen is not None:
            cx1, cy1, cx2, cy2 = chosen
            occupied_labels.append(chosen)
            # Dark background pill
            cv2.rectangle(img, (cx1, cy1), (cx2, cy2), (20, 20, 20), -1)
            cv2.rectangle(img, (cx1, cy1), (cx2, cy2), color, 1, cv2.LINE_AA)
            cv2.putText(img, label_text, (cx1 + pad_x, cy1 + th + pad_y), font, font_scale, (255, 255, 255), font_thickness, cv2.LINE_AA)
        else:
            # Draw micro dot inside top-left corner
            cv2.circle(img, (x1 + 3, y1 + 3), 2, color, -1, cv2.LINE_AA)
            
    # 3. Top HUD status banner
    hud_h = 32
    hud_bg = np.zeros((hud_h, w, 3), dtype=np.uint8)
    cv2.rectangle(hud_bg, (0, 0), (w, hud_h), (24, 24, 28), -1)
    
    cv2.circle(hud_bg, (15, 16), 5, COLOR_DEFECT, -1, cv2.LINE_AA)
    cv2.putText(hud_bg, f"Defects: {defect_count}", (26, 20), font, 0.42, (230, 230, 230), 1, cv2.LINE_AA)
    
    cv2.circle(hud_bg, (150, 16), 5, COLOR_HEALTHY, -1, cv2.LINE_AA)
    cv2.putText(hud_bg, f"Healthy: {healthy_count}", (161, 20), font, 0.42, (230, 230, 230), 1, cv2.LINE_AA)
    
    meta_text = f"Total: {len(detections)} | IoU: {iou_thresh} | Conf >= {int(conf_thresh*100)}%"
    cv2.putText(hud_bg, meta_text, (w - 330, 20), font, 0.40, (180, 180, 180), 1, cv2.LINE_AA)
    
    final_img = np.vstack([hud_bg, img])
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cv2.imwrite(output_path, final_img)
    print(f"Successfully generated: {output_path} (Defects={defect_count}, Healthy={healthy_count})")

if __name__ == '__main__':
    render_readable_annotations(
        'static/uploads/raw/20260910_072004_Screenshot_2026-09-09_221944.png',
        'models/combined_best.pt',
        'scratch/readable_corn_inspection_62.jpg',
        conf_thresh=0.12,
        iou_thresh=0.50
    )
    render_readable_annotations(
        'static/uploads/raw/20260910_073039_bulk_peanut_cluster_o2.jpg',
        'models/combined_best.pt',
        'scratch/readable_peanut_th_o2.jpg',
        conf_thresh=0.12,
        iou_thresh=0.50
    )
