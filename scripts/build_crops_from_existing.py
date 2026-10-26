"""
Build Kernel Crops from Existing Labeled Datasets
Part of Phase 1: Training Data Generation (No New Photos)

Rules:
- Cut every labeled kernel out of existing train, val, and test images (10% margin).
- Map classes 0-1 -> peanut, 2-3 -> corn, 4-5 -> sunflower.
- Skip crops under 24 px or with extreme aspect ratios (> 3.5).
- Keep existing splits strictly separated (no data leakage).
- Balance to up to 3000 train crops per material.
- Save to datasets_synth/crops/{train,val,test}/<material>/.
"""
import os
import sys
import random
import cv2
from collections import defaultdict, Counter

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATASET_ROOT = os.path.join(PROJECT_ROOT, 'datasets', 'raw_materials_combined')
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, 'datasets_synth', 'crops')

# Class ID to canonical material mapping
# 0: Peanut_Moldy, 1: Peanut_Not_Moldy
# 2: Corn_Moldy, 3: Corn_Not_Moldy
# 4: Sunflower_Moldy, 5: Sunflower_Not_Moldy
CLASS_TO_MATERIAL = {
    0: 'peanut',
    1: 'peanut',
    2: 'corn',
    3: 'corn',
    4: 'sunflower',
    5: 'sunflower'
}

MAX_TRAIN_CROPS_PER_MATERIAL = 3000
MIN_CROP_DIMENSION = 24
MAX_ASPECT_RATIO = 3.5
MARGIN_PERCENT = 0.10


def collect_box_metadata(split: str):
    """
    Scans labels for the given split and collects bounding box metadata.
    Returns: dict(material -> list of dicts: file, img_path, box_idx, cls_id, bbox_norm, approx_size)
    """
    img_dir = os.path.join(DATASET_ROOT, 'images', split)
    lbl_dir = os.path.join(DATASET_ROOT, 'labels', split)

    boxes_by_mat = defaultdict(list)
    skipped_reasons = Counter()

    if not os.path.exists(lbl_dir):
        print(f"Warning: Label directory not found: {lbl_dir}")
        return boxes_by_mat, skipped_reasons

    # Cache image filenames for fast lookup
    img_files = {os.path.splitext(f)[0]: f for f in os.listdir(img_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))}

    for lbl_file in sorted(os.listdir(lbl_dir)):
        if not lbl_file.endswith('.txt'):
            continue
        base_name = os.path.splitext(lbl_file)[0]
        if base_name not in img_files:
            continue

        img_file = img_files[base_name]
        img_path = os.path.join(img_dir, img_file)
        lbl_path = os.path.join(lbl_dir, lbl_file)

        with open(lbl_path, 'r', encoding='utf-8') as f:
            for box_idx, line in enumerate(f):
                parts = line.strip().split()
                if not parts:
                    continue
                try:
                    cls_id = int(parts[0])
                    if cls_id not in CLASS_TO_MATERIAL:
                        continue
                    mat = CLASS_TO_MATERIAL[cls_id]
                    xc, yc, w, h = [float(v) for v in parts[1:5]]

                    # Basic sanity check on normalized coords
                    if w <= 0 or h <= 0 or xc < 0 or yc < 0:
                        continue

                    # Filter extreme aspect ratios at normalized level
                    ar = max(w, h) / max(1e-6, min(w, h))
                    if ar > MAX_ASPECT_RATIO:
                        skipped_reasons['extreme_ar_pre'] += 1
                        continue

                    boxes_by_mat[mat].append({
                        'base_name': base_name,
                        'img_path': img_path,
                        'box_idx': box_idx,
                        'cls_id': cls_id,
                        'bbox_norm': (xc, yc, w, h),
                        'ar': ar
                    })
                except (ValueError, IndexError):
                    continue

    return boxes_by_mat, skipped_reasons


def extract_and_save_crops(split: str, selected_boxes: list, out_dir_base: str):
    """
    Loads images and extracts crops with 10% margin, validating pixel size and aspect ratio.
    """
    # Group boxes by image to avoid reloading image multiple times
    boxes_by_img = defaultdict(list)
    for b in selected_boxes:
        boxes_by_img[b['img_path']].append(b)

    saved_counts = Counter()
    skipped_reasons = Counter()

    for img_path, box_list in boxes_by_img.items():
        img = cv2.imread(img_path)
        if img is None:
            skipped_reasons['unreadable_img'] += len(box_list)
            continue

        H, W = img.shape[:2]

        for b in box_list:
            mat = CLASS_TO_MATERIAL[b['cls_id']]
            xc, yc, w, h = b['bbox_norm']

            # Un-normalize
            x1 = (xc - w / 2.0) * W
            y1 = (yc - h / 2.0) * H
            x2 = (xc + w / 2.0) * W
            y2 = (yc + h / 2.0) * H

            bw = x2 - x1
            bh = y2 - y1

            # 10% margin
            mx = bw * MARGIN_PERCENT
            my = bh * MARGIN_PERCENT

            x1_m = max(0, int(round(x1 - mx)))
            y1_m = max(0, int(round(y1 - my)))
            x2_m = min(W, int(round(x2 + mx)))
            y2_m = min(H, int(round(y2 + my)))

            cw = x2_m - x1_m
            ch = y2_m - y1_m

            # Dimension checks
            if cw < MIN_CROP_DIMENSION or ch < MIN_CROP_DIMENSION:
                skipped_reasons['under_24px'] += 1
                continue

            ar = max(cw, ch) / max(1, min(cw, ch))
            if ar > MAX_ASPECT_RATIO:
                skipped_reasons['extreme_ar_post'] += 1
                continue

            crop = img[y1_m:y2_m, x1_m:x2_m]
            if crop.size == 0:
                skipped_reasons['empty_crop'] += 1
                continue

            # Save to datasets_synth/crops/{split}/{material}/
            mat_dir = os.path.join(out_dir_base, split, mat)
            os.makedirs(mat_dir, exist_ok=True)

            crop_filename = f"{mat}_{b['base_name']}_box{b['box_idx']}.png"
            crop_path = os.path.join(mat_dir, crop_filename)

            # Save as PNG for exact lossless color representation
            success = cv2.imwrite(crop_path, crop)
            if success:
                saved_counts[mat] += 1
            else:
                skipped_reasons['write_failed'] += 1

    return saved_counts, skipped_reasons


def main():
    print("=" * 70)
    print("PHASE 1 - STEP 1: EXTRACTING KERNEL CROPS FROM EXISTING DATASETS")
    print(f"Source Dataset: {DATASET_ROOT}")
    print(f"Output Root:    {OUTPUT_ROOT}")
    print(f"Min Dimension:  {MIN_CROP_DIMENSION}px")
    print(f"Max Aspect Ratio: {MAX_ASPECT_RATIO}")
    print(f"Margin:         {int(MARGIN_PERCENT * 100)}%")
    print("=" * 70)

    # Use deterministic seed for reproducibility
    random.seed(42)

    total_extracted_by_split = {}

    for split in ['train', 'val', 'test']:
        print(f"\n>>> Processing Split: [{split.upper()}]")
        boxes_by_mat, skipped_meta = collect_box_metadata(split)

        selected_boxes = []
        for mat in ['peanut', 'corn', 'sunflower']:
            cand_list = boxes_by_mat.get(mat, [])
            total_cand = len(cand_list)
            print(f"  Material '{mat}': {total_cand} candidate boxes found.")

            if split == 'train':
                # Shuffle candidates so we get diverse crops across images
                shuffled = list(cand_list)
                random.shuffle(shuffled)
                # Keep all candidates to pass to extraction; extraction will stop or we will trim
                selected_boxes.extend(shuffled)
            else:
                # val and test: keep all candidate crops without leakage
                print(f"    -> Keeping all {total_cand} candidate boxes for {split} split.")
                selected_boxes.extend(cand_list)

        print(f"  Extracting and saving pixel crops for {len(selected_boxes)} selected boxes...")
        saved_counts, skipped_reasons = extract_and_save_crops(split, selected_boxes, OUTPUT_ROOT)

        # If train exceeded 3000, trim down to exactly 3000
        if split == 'train':
            for mat in ['peanut', 'corn', 'sunflower']:
                mat_dir = os.path.join(OUTPUT_ROOT, split, mat)
                files = sorted(os.listdir(mat_dir)) if os.path.exists(mat_dir) else []
                if len(files) > MAX_TRAIN_CROPS_PER_MATERIAL:
                    random.shuffle(files)
                    to_remove = files[MAX_TRAIN_CROPS_PER_MATERIAL:]
                    for f in to_remove:
                        try:
                            os.remove(os.path.join(mat_dir, f))
                        except OSError:
                            pass
                    saved_counts[mat] = MAX_TRAIN_CROPS_PER_MATERIAL
                else:
                    saved_counts[mat] = len(files)

        total_extracted_by_split[split] = saved_counts
        print(f"  [{split.upper()} Complete] Crops Saved: {dict(saved_counts)}")
        print(f"  Filtered out: {dict(skipped_reasons)}")

    # Print final grand summary table
    print("\n" + "=" * 70)
    print("PHASE 1 - STEP 1 CROP EXTRACTION SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Split':<10} | {'Peanut':<12} | {'Corn':<12} | {'Sunflower':<12} | {'Total':<12}")
    print("-" * 10 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12)

    grand_total = 0
    for split in ['train', 'val', 'test']:
        counts = total_extracted_by_split.get(split, {})
        p = counts.get('peanut', 0)
        c = counts.get('corn', 0)
        s = counts.get('sunflower', 0)
        tot = p + c + s
        grand_total += tot
        print(f"{split:<10} | {p:<12} | {c:<12} | {s:<12} | {tot:<12}")

    print("-" * 10 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12)
    print(f"{'TOTAL':<10} | {'':<12} | {'':<12} | {'':<12} | {grand_total:<12}")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
