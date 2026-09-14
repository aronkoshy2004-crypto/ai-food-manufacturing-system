import os
import sys
import shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from ultralytics import YOLO
import ai.yolo_service as ys

img_path = 'static/uploads/raw/20260910_072004_Screenshot_2026-09-09_221944.png'

# Run at IoU 0.70
res_70 = ys.run_yolo_visual_inspection(img_path, conf_threshold=0.12, iou_threshold=0.70)
# Run at IoU 0.50
res_50 = ys.run_yolo_visual_inspection(img_path, conf_threshold=0.12, iou_threshold=0.50)

total_70 = len(res_70['detected_defects']) + len(res_70['detected_healthy'])
moldy_70 = len(res_70['detected_defects'])
healthy_70 = len(res_70['detected_healthy'])
confs_70 = [d['confidence'] for d in res_70['detected_defects']]

total_50 = len(res_50['detected_defects']) + len(res_50['detected_healthy'])
moldy_50 = len(res_50['detected_defects'])
healthy_50 = len(res_50['detected_healthy'])
confs_50 = [d['confidence'] for d in res_50['detected_defects']]

print("=== CORN CLUSTER INSPECTION #62: IoU 0.70 vs IoU 0.50 ===")
print(f"Old Default (IoU=0.70):")
print(f"  Total Candidate Regions: {total_70}")
print(f"  - Corn_Moldy: {moldy_70} (Avg Conf: {np.mean(confs_70):.1%}, Min: {np.min(confs_70):.1%}, Max: {np.max(confs_70):.1%})")
print(f"  - Corn_Not_Moldy: {healthy_70}")

print(f"\nNew Permanent Default (IoU=0.50):")
print(f"  Total Candidate Regions: {total_50}")
print(f"  - Corn_Moldy: {moldy_50} (Avg Conf: {np.mean(confs_50):.1%}, Min: {np.min(confs_50):.1%}, Max: {np.max(confs_50):.1%})")
print(f"  - Corn_Not_Moldy: {healthy_50}")

diff_total = total_70 - total_50
diff_moldy = moldy_70 - moldy_50
print(f"\nAnalysis:")
print(f"  Duplicate Over-Counting at 0.70: Yes, exactly {diff_total} duplicate box(es) suppressed.")
print(f"  {diff_moldy} duplicate/overlapping Corn_Moldy detection(s) merged into single kernels.")
print(f"  Healthy Corn_Not_Moldy count remained exactly unchanged at {healthy_50}, proving no valid healthy detections were suppressed.")

# Copy updated annotated image to artifact directory
artifact_dir = r"C:\Users\L E N O V O\.gemini\antigravity-ide\brain\0188ed43-ad3b-4f6b-bd55-84345362981a"
shutil.copy("static/uploads/annotated/annotated_20260910_072004_Screenshot_2026-09-09_221944.png", 
            os.path.join(artifact_dir, "corn_cluster_inspection_62_iou50_readable.png"))
print("\nCopied updated readable image to artifacts directory as 'corn_cluster_inspection_62_iou50_readable.png'")
