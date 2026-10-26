"""
Prepare Classification Dataset for Material Classifier (YOLOv8n-cls)
Phase 2 - Step 1: Combining Real Kernel Crops with Synthetic Scene Kernel Crops

Dataset Structure:
datasets_synth/cls_dataset/
  train/
    peanut/
    corn/
    sunflower/
  val/
    peanut/
    corn/
    sunflower/
"""

import os
import glob
import shutil
import random
from collections import Counter
import cv2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CROPS_ROOT = os.path.join(PROJECT_ROOT, 'datasets_synth', 'crops')
SYNTH_IMAGES_ROOT = os.path.join(PROJECT_ROOT, 'datasets_synth', 'images')
SYNTH_LABELS_ROOT = os.path.join(PROJECT_ROOT, 'datasets_synth', 'labels')
CLS_DATASET_ROOT = os.path.join(PROJECT_ROOT, 'datasets_synth', 'cls_dataset')

MATERIALS = ['peanut', 'corn', 'sunflower']
TARGET_SYNTH_CROPS_PER_MATERIAL = 3000
MARGIN_PERCENT = 0.05


def extract_crops_from_scenes(split: str, material: str, max_crops: int = 3000):
    """
    Extracts kernel crops from the synthetic scenes for the given split and material.
    """
    img_dir = os.path.join(SYNTH_IMAGES_ROOT, split)
    lbl_dir = os.path.join(SYNTH_LABELS_ROOT, split)

    pattern = os.path.join(img_dir, f"synth_{material}_{split}_*.jpg")
    scene_files = sorted(glob.glob(pattern))

    extracted_crops = []
    for s_path in scene_files:
        if len(extracted_crops) >= max_crops:
            break
        base = os.path.splitext(os.path.basename(s_path))[0]
        lbl_path = os.path.join(lbl_dir, f"{base}.txt")
        if not os.path.exists(lbl_path):
            continue

        img = cv2.imread(s_path)
        if img is None:
            continue
        H, W = img.shape[:2]

        with open(lbl_path, 'r', encoding='utf-8') as lf:
            for k_idx, line in enumerate(lf):
                if len(extracted_crops) >= max_crops:
                    break
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                xc, yc, bw, bh = [float(v) for v in parts[1:5]]

                # Convert to pixel coords with small margin
                x1 = int(round((xc - bw / 2.0) * W))
                y1 = int(round((yc - bh / 2.0) * H))
                x2 = int(round((xc + bw / 2.0) * W))
                y2 = int(round((yc + bh / 2.0) * H))

                mx = int(round((x2 - x1) * MARGIN_PERCENT))
                my = int(round((y2 - y1) * MARGIN_PERCENT))

                x1_m = max(0, x1 - mx)
                y1_m = max(0, y1 - my)
                x2_m = min(W, x2 + mx)
                y2_m = min(H, y2 + my)

                crop = img[y1_m:y2_m, x1_m:x2_m]
                if crop.size > 0 and crop.shape[0] >= 16 and crop.shape[1] >= 16:
                    crop_name = f"synth_{base}_k{k_idx}.jpg"
                    extracted_crops.append((crop_name, crop))

    return extracted_crops


def build_classification_dataset():
    print("=" * 70)
    print("PHASE 2 - STEP 1: PREPARING CLASSIFICATION DATASET FOR YOLOv8n-cls")
    print(f"Destination: {CLS_DATASET_ROOT}")
    print("=" * 70)

    random.seed(42)

    # Clean destination if previously created
    if os.path.exists(CLS_DATASET_ROOT):
        shutil.rmtree(CLS_DATASET_ROOT)

    summary_counts = {'train': Counter(), 'val': Counter()}

    for split in ['train', 'val']:
        print(f"\n>>> Processing Split: [{split.upper()}]")
        for material in MATERIALS:
            mat_out_dir = os.path.join(CLS_DATASET_ROOT, split, material)
            os.makedirs(mat_out_dir, exist_ok=True)

            # 1. Copy real crops from datasets_synth/crops/{split}/{material}/
            real_crops_dir = os.path.join(CROPS_ROOT, split, material)
            real_files = glob.glob(os.path.join(real_crops_dir, '*.png')) if os.path.exists(real_crops_dir) else []
            random.shuffle(real_files)

            # For corn in val, sample up to 500 so peanut isn't overwhelmed
            if split == 'val' and material == 'corn' and len(real_files) > 500:
                real_files = real_files[:500]

            for rf in real_files:
                fname = os.path.basename(rf)
                dst = os.path.join(mat_out_dir, f"real_{fname}")
                shutil.copy2(rf, dst)
                summary_counts[split][material] += 1

            real_count = summary_counts[split][material]
            print(f"  [{material.upper()}] Copied {real_count} real kernel crops.")

            # 2. Extract crops cut from synthetic scenes
            synth_target = TARGET_SYNTH_CROPS_PER_MATERIAL if split == 'train' else 1000
            synth_crops = extract_crops_from_scenes(split, material, max_crops=synth_target)

            for crop_name, crop_img in synth_crops:
                dst = os.path.join(mat_out_dir, crop_name)
                cv2.imwrite(dst, crop_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                summary_counts[split][material] += 1

            synth_count = len(synth_crops)
            print(f"  [{material.upper()}] Cut {synth_count} synthetic scene kernel crops.")
            print(f"  [{material.upper()} Total {split}]: {summary_counts[split][material]} images.")

    print("\n" + "=" * 70)
    print("CLASSIFICATION DATASET SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Split':<10} | {'Peanut':<12} | {'Corn':<12} | {'Sunflower':<12} | {'Total':<12}")
    print("-" * 10 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12)

    grand_total = 0
    for split in ['train', 'val']:
        p = summary_counts[split]['peanut']
        c = summary_counts[split]['corn']
        s = summary_counts[split]['sunflower']
        tot = p + c + s
        grand_total += tot
        print(f"{split:<10} | {p:<12} | {c:<12} | {s:<12} | {tot:<12}")

    print("-" * 10 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12)
    print(f"{'TOTAL':<10} | {'':<12} | {'':<12} | {'':<12} | {grand_total:<12}")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    build_classification_dataset()
