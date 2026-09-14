import os
import cv2
from pathlib import Path
from PIL import Image

base = Path(r"C:\Users\L E N O V O\Downloads")

# 1. Inspect corn_quality annotations
cq = base / "corn_quality.v1-v1-corn_quality.yolov8"
train_labels = list((cq / "train" / "labels").glob("*.txt"))
cls_counts = {0: 0, 1: 0}
img_has_cls = {0: 0, 1: 0}
for lp in train_labels:
    lines = lp.read_text().strip().splitlines()
    c_in_img = set()
    for l in lines:
        parts = l.strip().split()
        if parts:
            cid = int(parts[0])
            cls_counts[cid] = cls_counts.get(cid, 0) + 1
            c_in_img.add(cid)
    for c in c_in_img:
        img_has_cls[c] = img_has_cls.get(c, 0) + 1

print(f"corn_quality train label counts: {cls_counts}")
print(f"corn_quality images containing class: {img_has_cls}")

# 2. Check sample images for class 0 vs class 1 in corn_quality
only_0 = []
only_1 = []
for lp in train_labels:
    lines = lp.read_text().strip().splitlines()
    cids = set(int(l.split()[0]) for l in lines if l.strip())
    img_p = cq / "train" / "images" / (lp.stem + ".jpg")
    if not img_p.exists():
        img_p = cq / "train" / "images" / (lp.stem + ".png")
    if cids == {0}:
        only_0.append((img_p, len(lines)))
    elif cids == {1}:
        only_1.append((img_p, len(lines)))

print(f"corn_quality train images with ONLY class 0: {len(only_0)}")
print(f"corn_quality train images with ONLY class 1: {len(only_1)}")
if only_0:
    print(f"Sample ONLY class 0: {only_0[0][0].name} ({only_0[0][1]} boxes)")
if only_1:
    print(f"Sample ONLY class 1: {only_1[0][0].name} ({only_1[0][1]} boxes)")

# 3. Check Sunflower_Seeds image inspection
sf = base / "Sunflower_Seeds" / "Sunflower_Seeds"
for pre in ['m', 's', 'z']:
    samples = list(sf.glob(f"{pre}_*.jpg"))
    print(f"Sunflower prefix '{pre}': {len(samples)} files. Sample: {samples[0].name}")
