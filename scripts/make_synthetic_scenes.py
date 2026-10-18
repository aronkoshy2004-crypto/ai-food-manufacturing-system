"""
Generate Synthetic Training and Validation Scenes from Extracted Kernel Crops
Phase 1: Build Training Data from Existing Datasets Only

Requirements:
- Segment each kernel with a mask (GrabCut + morphological validation, skipping poor masks).
- Paste 1 to 30 kernels per scene onto procedural plain backgrounds:
  (white, off-white, light grey, dark sheet, with slight noise, soft shadows, and vignette).
- Spread kernels apart with random rotation (0-360 deg), scale (matching typical live camera frame sizes: 50-125px),
  small color jitter, and blur.
- Exactly one material per scene.
- Generate:
  - 400 scenes per material for TRAIN (1200 total)
  - 60 scenes per material for VAL (180 total, from val crops only)
  - 60 scenes per material for TEST (180 total, from test crops only)
- Write exact YOLO labels for the healthy class of each material using IDs from datasets/raw_materials_combined/data.yaml:
  - Peanut: 1 (Peanut_Not_Moldy)
  - Corn: 3 (Corn_Not_Moldy)
  - Sunflower: 5 (Sunflower_Not_Moldy)
- Generate contact sheets (20 scenes each) in datasets_synth/review/ showing annotated bounding boxes.
"""

import os
import sys
import glob
import math
import random
import time
from collections import defaultdict, Counter
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CROPS_ROOT = os.path.join(PROJECT_ROOT, 'datasets_synth', 'crops')
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, 'datasets_synth')
REVIEW_ROOT = os.path.join(OUTPUT_ROOT, 'review')

# Healthy class IDs from datasets/raw_materials_combined/data.yaml
MATERIAL_HEALTHY_CLASS_ID = {
    'peanut': 1,     # Peanut_Not_Moldy
    'corn': 3,       # Corn_Not_Moldy
    'sunflower': 5   # Sunflower_Not_Moldy
}

CLASS_ID_NAMES = {
    0: 'Peanut_Moldy',
    1: 'Peanut_Not_Moldy',
    2: 'Corn_Moldy',
    3: 'Corn_Not_Moldy',
    4: 'Sunflower_Moldy',
    5: 'Sunflower_Not_Moldy'
}

SCENE_COUNTS = {
    'train': 400,  # per material
    'val': 60,     # per material
    'test': 60     # per material
}

CANVAS_WIDTH = 640
CANVAS_HEIGHT = 640

# Kernel scale ranges (max dimension in px) matching live camera frames
MATERIAL_SCALE_RANGES = {
    'peanut': (65, 125),
    'corn': (60, 115),
    'sunflower': (50, 105)
}

BACKGROUND_TYPES = ['white', 'off_white', 'light_grey', 'dark_sheet']


def extract_kernel_mask(crop, max_dim=120):
    """
    Extracts a clean foreground kernel mask using GrabCut with 1 iteration
    on downscaled crop, followed by morphological closing and contour validation.
    Returns: (tight_crop, tight_mask) or (None, None) if mask is invalid.
    """
    h, w = crop.shape[:2]
    if h < 16 or w < 16:
        return None, None

    scale = min(1.0, max_dim / max(h, w))
    sw, sh = max(16, int(w * scale)), max(16, int(h * scale))
    small = cv2.resize(crop, (sw, sh), interpolation=cv2.INTER_AREA)

    mask = np.full((sh, sw), cv2.GC_PR_BGD, dtype=np.uint8)

    # 10% margin was added during crop extraction, so borders are background
    bx = max(1, int(sw * 0.08))
    by = max(1, int(sh * 0.08))
    mask[by:sh - by, bx:sw - bx] = cv2.GC_PR_FGD

    # Center core is definite foreground
    cx1, cy1 = int(sw * 0.25), int(sh * 0.25)
    cx2, cy2 = int(sw * 0.75), int(sh * 0.75)
    mask[cy1:cy2, cx1:cx2] = cv2.GC_FGD

    # Outer border edges are definite background
    obx = max(1, bx // 2)
    oby = max(1, by // 2)
    mask[0:oby, :] = cv2.GC_BGD
    mask[-oby:, :] = cv2.GC_BGD
    mask[:, 0:obx] = cv2.GC_BGD
    mask[:, -obx:] = cv2.GC_BGD

    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(small, mask, None, bgd, fgd, 1, cv2.GC_INIT_WITH_MASK)
        bin_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

        # Upscale mask back to original crop resolution
        full_mask = cv2.resize(bin_mask, (w, h), interpolation=cv2.INTER_NEAREST)

        # Morphological closing to seal internal cavities
        ksize = max(3, int(min(h, w) * 0.04))
        if ksize % 2 == 0:
            ksize += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
        full_mask = cv2.morphologyEx(full_mask, cv2.MORPH_CLOSE, kernel)

        # Find external contours
        cnts, _ = cv2.findContours(full_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None, None

        c = max(cnts, key=cv2.contourArea)
        area = cv2.contourArea(c)
        crop_area = h * w
        ratio = area / max(1, crop_area)

        # Skip crops where mask looks bad (under-segmented or over-segmented)
        if ratio < 0.16 or ratio > 0.88:
            return None, None

        final_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(final_mask, [c], -1, 255, thickness=cv2.FILLED)

        # Crop tightly around contour bounding rect
        rx, ry, rw, rh = cv2.boundingRect(c)
        if rw < 12 or rh < 12:
            return None, None

        tight_crop = crop[ry:ry + rh, rx:rx + rw].copy()
        tight_mask = final_mask[ry:ry + rh, rx:rx + rw].copy()
        return tight_crop, tight_mask
    except Exception:
        return None, None


def build_masked_kernel_pool(split: str, material: str, max_pool_size: int = 800):
    """
    Loads crops for (split, material) and extracts validated masked kernels.
    """
    mat_crops_dir = os.path.join(CROPS_ROOT, split, material)
    if not os.path.exists(mat_crops_dir):
        print(f"Warning: directory not found: {mat_crops_dir}")
        return []

    files = glob.glob(os.path.join(mat_crops_dir, '*.png'))
    random.shuffle(files)

    pool = []
    skipped = 0
    t0 = time.time()

    for f in files:
        if len(pool) >= max_pool_size:
            break
        img = cv2.imread(f)
        if img is None:
            continue
        tc, tm = extract_kernel_mask(img)
        if tc is not None:
            pool.append((tc, tm))
        else:
            skipped += 1

    dt = time.time() - t0
    print(f"  [{split.upper()}] Material '{material}': Built pool of {len(pool)} validated masked kernels (skipped {skipped} poor masks) in {dt:.1f}s.")
    return pool


def generate_procedural_background(width=640, height=640, bg_type='light_grey'):
    """
    Generates procedural plain background (white, off-white, light grey, dark sheet)
    with subtle lighting gradient, Gaussian noise, and radial vignette.
    """
    if bg_type == 'white':
        # Bright white paper / light tray
        val = np.random.randint(246, 255)
        base_color = np.array([val, val, val], dtype=np.float32)
    elif bg_type == 'off_white':
        # Warm ivory or slight cream tint
        b = np.random.randint(232, 246)
        g = np.random.randint(238, 250)
        r = np.random.randint(236, 248)
        base_color = np.array([b, g, r], dtype=np.float32)
    elif bg_type == 'light_grey':
        # Stainless steel / matte grey inspection table
        val = np.random.randint(180, 218)
        base_color = np.array([
            val + np.random.randint(-3, 4),
            val + np.random.randint(-3, 4),
            val + np.random.randint(-3, 4)
        ], dtype=np.float32)
    else:  # 'dark_sheet'
        # Dark grey / black rubber mat
        val = np.random.randint(35, 62)
        base_color = np.array([
            val + np.random.randint(-2, 3),
            val + np.random.randint(-2, 3),
            val + np.random.randint(-2, 3)
        ], dtype=np.float32)

    bg = np.full((height, width, 3), base_color, dtype=np.float32)

    # Subtle directional lighting gradient
    grad_x = np.linspace(np.random.uniform(-4, 0), np.random.uniform(0, 4), width).reshape(1, width, 1)
    grad_y = np.linspace(np.random.uniform(-4, 0), np.random.uniform(0, 4), height).reshape(height, 1, 1)
    bg += grad_x + grad_y

    # Subtle surface noise
    noise = np.random.normal(0, np.random.uniform(1.8, 3.2), (height, width, 3))
    bg += noise

    # Soft radial vignette
    X = np.linspace(-1, 1, width)
    Y = np.linspace(-1, 1, height)
    XX, YY = np.meshgrid(X, Y)
    dist = np.sqrt(XX**2 + YY**2)
    vignette_depth = np.random.uniform(0.08, 0.16)
    vignette = 1.0 - vignette_depth * np.clip(dist / np.sqrt(2), 0, 1)
    bg *= vignette[:, :, np.newaxis]

    return np.clip(bg, 0, 255).astype(np.uint8)


def transform_kernel(tight_crop, tight_mask, target_dim):
    """
    Applies random scale, rotation (0-360 deg), slight color jitter, and blur.
    Returns: (rot_crop, rot_mask, width, height)
    """
    h, w = tight_crop.shape[:2]
    scale = target_dim / max(h, w)
    nw = max(10, int(round(w * scale)))
    nh = max(10, int(round(h * scale)))

    resized_crop = cv2.resize(tight_crop, (nw, nh), interpolation=cv2.INTER_LINEAR)
    resized_mask = cv2.resize(tight_mask, (nw, nh), interpolation=cv2.INTER_LINEAR)

    # Rotation: pad canvas to prevent clipping corners
    diag = int(math.ceil(math.sqrt(nw**2 + nh**2)))
    pad_x = (diag - nw) // 2 + 8
    pad_y = (diag - nh) // 2 + 8

    padded_crop = cv2.copyMakeBorder(resized_crop, pad_y, pad_y, pad_x, pad_x, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    padded_mask = cv2.copyMakeBorder(resized_mask, pad_y, pad_y, pad_x, pad_x, cv2.BORDER_CONSTANT, value=0)

    angle = random.uniform(0, 360)
    cp = (padded_crop.shape[1] // 2, padded_crop.shape[0] // 2)
    M = cv2.getRotationMatrix2D(cp, angle, 1.0)
    rot_crop = cv2.warpAffine(padded_crop, M, (padded_crop.shape[1], padded_crop.shape[0]), flags=cv2.INTER_LINEAR)
    rot_mask = cv2.warpAffine(padded_mask, M, (padded_mask.shape[1], padded_mask.shape[0]), flags=cv2.INTER_LINEAR)

    cnts, _ = cv2.findContours(rot_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None, None, 0, 0

    c = max(cnts, key=cv2.contourArea)
    rx, ry, rw, rh = cv2.boundingRect(c)
    if rw < 8 or rh < 8:
        return None, None, 0, 0

    k_crop = rot_crop[ry:ry + rh, rx:rx + rw].copy()
    k_mask = rot_mask[ry:ry + rh, rx:rx + rw].copy()

    # Small color jitter: brightness and contrast
    brightness = random.uniform(0.92, 1.08)
    contrast = random.uniform(0.93, 1.07)
    k_crop = np.clip(k_crop.astype(np.float32) * contrast + (brightness - 1.0) * 128.0, 0, 255).astype(np.uint8)

    # Small camera blur (Gaussian or bilateral)
    if random.random() < 0.55:
        sigma = random.uniform(0.35, 0.75)
        k_crop = cv2.GaussianBlur(k_crop, (3, 3), sigma)

    return k_crop, k_mask, rw, rh


def paste_kernel_with_shadow(canvas, k_crop, k_mask, top_left):
    """
    Pastes transformed kernel onto canvas with realistic soft drop shadow and alpha blending.
    top_left: (x1, y1)
    """
    x1, y1 = top_left
    kh, kw = k_crop.shape[:2]
    H, W = canvas.shape[:2]
    x2, y2 = x1 + kw, y1 + kh

    # Cast soft drop shadow (simulating overhead oblique inspection lighting)
    sx_offset = random.randint(2, 5)
    sy_offset = random.randint(2, 5)
    sx1 = x1 + sx_offset
    sy1 = y1 + sy_offset
    sx2 = sx1 + kw
    sy2 = sy1 + kh

    if 0 <= sx1 and sx2 <= W and 0 <= sy1 and sy2 <= H:
        # Blurred shadow mask
        shadow_ksize = random.choice([11, 13, 15])
        shadow_mask = cv2.GaussianBlur(k_mask, (shadow_ksize, shadow_ksize), 3.2).astype(np.float32) / 255.0
        shadow_strength = random.uniform(0.32, 0.45)
        canvas_shadow_roi = canvas[sy1:sy2, sx1:sx2].astype(np.float32)
        canvas_shadow_roi = canvas_shadow_roi * (1.0 - shadow_strength * shadow_mask[:, :, np.newaxis])
        canvas[sy1:sy2, sx1:sx2] = np.clip(canvas_shadow_roi, 0, 255).astype(np.uint8)

    # Alpha blend kernel with feathering
    alpha = cv2.GaussianBlur(k_mask, (3, 3), 0.5).astype(np.float32) / 255.0
    alpha = alpha[:, :, np.newaxis]

    canvas_roi = canvas[y1:y2, x1:x2].astype(np.float32)
    blended = k_crop.astype(np.float32) * alpha + canvas_roi * (1.0 - alpha)
    canvas[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)


def check_overlap(box, placed_boxes, max_iou=0.08, min_center_dist_factor=0.72):
    """
    Checks if candidate box (x1, y1, x2, y2) overlaps excessively with placed boxes.
    Keeps kernels spread apart.
    """
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    r = math.sqrt((x2 - x1)**2 + (y2 - y1)**2) / 2.0

    for px1, py1, px2, py2 in placed_boxes:
        # Center distance check
        pcx = (px1 + px2) / 2.0
        pcy = (py1 + py2) / 2.0
        pr = math.sqrt((px2 - px1)**2 + (py2 - py1)**2) / 2.0
        dist = math.hypot(cx - pcx, cy - pcy)

        if dist < (r + pr) * min_center_dist_factor:
            return True

        # Bounding box IoU check
        ix1 = max(x1, px1)
        iy1 = max(y1, py1)
        ix2 = min(x2, px2)
        iy2 = min(y2, py2)

        if ix2 > ix1 and iy2 > iy1:
            inter_area = (ix2 - ix1) * (iy2 - iy1)
            area1 = (x2 - x1) * (y2 - y1)
            area2 = (px2 - px1) * (py2 - py1)
            iou = inter_area / float(area1 + area2 - inter_area)
            if iou > max_iou:
                return True

    return False


def generate_single_scene(material: str, pool: list, bg_type: str, min_kernels=1, max_kernels=30):
    """
    Generates a single 640x640 synthetic scene of the given material.
    Returns: (canvas, list_of_yolo_labels)
    """
    canvas = generate_procedural_background(CANVAS_WIDTH, CANVAS_HEIGHT, bg_type)
    cls_id = MATERIAL_HEALTHY_CLASS_ID[material]
    scale_min, scale_max = MATERIAL_SCALE_RANGES[material]

    target_num_kernels = random.randint(min_kernels, max_kernels)
    placed_boxes = []
    yolo_labels = []

    # Safe canvas border margin
    margin = 40

    for _ in range(target_num_kernels):
        # Pick random masked kernel from pool
        tight_crop, tight_mask = random.choice(pool)
        target_dim = random.randint(scale_min, scale_max)

        k_crop, k_mask, kw, kh = transform_kernel(tight_crop, tight_mask, target_dim)
        if k_crop is None:
            continue

        # Try up to 35 random positions to find non-overlapping location
        placed = False
        max_x = CANVAS_WIDTH - margin - kw
        max_y = CANVAS_HEIGHT - margin - kh

        if max_x <= margin or max_y <= margin:
            continue

        for attempt in range(35):
            x1 = random.randint(margin, max_x)
            y1 = random.randint(margin, max_y)
            x2 = x1 + kw
            y2 = y1 + kh
            candidate_box = (x1, y1, x2, y2)

            # Check overlap; slightly relax tolerance if scene is getting dense
            tol_iou = 0.08 if attempt < 25 else 0.15
            tol_dist = 0.72 if attempt < 25 else 0.55
            if not check_overlap(candidate_box, placed_boxes, max_iou=tol_iou, min_center_dist_factor=tol_dist):
                paste_kernel_with_shadow(canvas, k_crop, k_mask, (x1, y1))
                placed_boxes.append(candidate_box)

                # Normalized YOLO coordinates: <class_id> <xc> <yc> <bw> <bh>
                norm_xc = (x1 + x2) / 2.0 / CANVAS_WIDTH
                norm_yc = (y1 + y2) / 2.0 / CANVAS_HEIGHT
                norm_bw = kw / float(CANVAS_WIDTH)
                norm_bh = kh / float(CANVAS_HEIGHT)

                yolo_labels.append((cls_id, norm_xc, norm_yc, norm_bw, norm_bh, (x1, y1, x2, y2)))
                placed = True
                break

    return canvas, yolo_labels


def create_contact_sheet(image_paths, output_sheet_path, title="Synthetic Scenes Review", grid_shape=(4, 5)):
    """
    Creates a contact sheet from 20 scene images with annotated bounding boxes.
    grid_shape: (rows, cols) = (4, 5) -> 20 thumbnails
    """
    rows, cols = grid_shape
    thumb_w, thumb_h = 320, 320
    header_h = 70
    sheet_w = cols * thumb_w
    sheet_h = rows * thumb_h + header_h

    sheet = np.full((sheet_h, sheet_w, 3), 24, dtype=np.uint8)

    # Draw header banner
    cv2.rectangle(sheet, (0, 0), (sheet_w, header_h), (38, 38, 42), -1)
    cv2.putText(sheet, title, (25, 45), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(sheet, f"20 Scenes | Exact YOLO Labels | Healthy Class IDs: Peanut=1, Corn=3, Sunflower=5",
                (sheet_w - 740, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)

    # Class colors for visualization
    class_colors = {
        1: (30, 200, 30),    # Peanut_Not_Moldy: Green
        3: (30, 210, 240),   # Corn_Not_Moldy: Yellow/Cyan
        5: (220, 130, 30)    # Sunflower_Not_Moldy: Blue/Orange
    }

    for idx, img_path in enumerate(image_paths[:rows * cols]):
        img = cv2.imread(img_path)
        if img is None:
            continue

        annotated = img.copy()
        # Find corresponding label file
        # img_path: datasets_synth/images/<split>/<filename>.jpg
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        split_dir = os.path.basename(os.path.dirname(img_path))
        lbl_path = os.path.join(OUTPUT_ROOT, 'labels', split_dir, f"{base_name}.txt")

        kernel_count = 0
        if os.path.exists(lbl_path):
            with open(lbl_path, 'r', encoding='utf-8') as lf:
                for line in lf:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cid = int(parts[0])
                        xc, yc, bw, bh = [float(v) for v in parts[1:5]]
                        x1 = int(round((xc - bw / 2.0) * CANVAS_WIDTH))
                        y1 = int(round((yc - bh / 2.0) * CANVAS_HEIGHT))
                        x2 = int(round((xc + bw / 2.0) * CANVAS_WIDTH))
                        y2 = int(round((yc + bh / 2.0) * CANVAS_HEIGHT))

                        color = class_colors.get(cid, (0, 255, 0))
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                        kernel_count += 1

        # Resize to thumbnail
        thumb = cv2.resize(annotated, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)

        # Thumbnail overlay info
        cv2.putText(thumb, f"#{idx+1} {base_name.split('_')[1]} ({kernel_count}k)", (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(thumb, f"#{idx+1} {base_name.split('_')[1]} ({kernel_count}k)", (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        r = idx // cols
        c = idx % cols
        sy = header_h + r * thumb_h
        sx = c * thumb_w
        sheet[sy:sy + thumb_h, sx:sx + thumb_w] = thumb

        # Thin grid border
        cv2.rectangle(sheet, (sx, sy), (sx + thumb_w, sy + thumb_h), (50, 50, 50), 1)

    os.makedirs(os.path.dirname(output_sheet_path), exist_ok=True)
    cv2.imwrite(output_sheet_path, sheet, [cv2.IMWRITE_JPEG_QUALITY, 93])
    print(f"Saved review contact sheet: {output_sheet_path}")


def write_synth_data_yaml():
    """
    Writes datasets_synth/data.yaml for YOLO training and evaluation.
    """
    yaml_path = os.path.join(OUTPUT_ROOT, 'data.yaml')
    content = f"""path: {OUTPUT_ROOT}
train: images/train
val: images/val
test: images/test

nc: 6
names:
  0: Peanut_Moldy
  1: Peanut_Not_Moldy
  2: Corn_Moldy
  3: Corn_Not_Moldy
  4: Sunflower_Moldy
  5: Sunflower_Not_Moldy
"""
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Generated dataset YAML: {yaml_path}")


def main():
    print("=" * 75)
    print("PHASE 1 - STEP 2: MAKE SYNTHETIC SCENES FROM EXTRACTED KERNEL CROPS")
    print(f"Source Crops Root: {CROPS_ROOT}")
    print(f"Output Root:       {OUTPUT_ROOT}")
    print(f"Canvas Size:       {CANVAS_WIDTH}x{CANVAS_HEIGHT}")
    print(f"Backgrounds:       {BACKGROUND_TYPES}")
    print(f"Target Scenes:     Train=400/mat, Val=60/mat, Test=60/mat")
    print("=" * 75)

    random.seed(42)
    np.random.seed(42)

    scene_counts_report = defaultdict(Counter)
    sample_images_for_review = defaultdict(list)

    # Ensure directories exist
    for split in ['train', 'val', 'test']:
        os.makedirs(os.path.join(OUTPUT_ROOT, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(OUTPUT_ROOT, 'labels', split), exist_ok=True)
    os.makedirs(REVIEW_ROOT, exist_ok=True)

    materials = ['peanut', 'corn', 'sunflower']

    # Process each split strictly with its own crops (no leakage)
    for split in ['train', 'val', 'test']:
        n_scenes = SCENE_COUNTS[split]
        print(f"\n=======================================================")
        print(f">>> GENERATING SYNTHETIC SCENES FOR SPLIT: [{split.upper()}]")
        print(f">>> Target: {n_scenes} scenes per material ({n_scenes * 3} total)")
        print(f"=======================================================")

        for material in materials:
            print(f"\n--- Material: {material.upper()} ({split.upper()}) ---")
            # Build masked kernel pool from this split's crops
            pool_cap = 800 if split == 'train' else 500
            pool = build_masked_kernel_pool(split, material, max_pool_size=pool_cap)

            if not pool:
                print(f"ERROR: No valid masked kernels for {material} in {split}!")
                continue

            img_out_dir = os.path.join(OUTPUT_ROOT, 'images', split)
            lbl_out_dir = os.path.join(OUTPUT_ROOT, 'labels', split)

            t0 = time.time()
            total_kernels_material = 0

            for i in range(n_scenes):
                # Cycle through background types evenly
                bg_type = BACKGROUND_TYPES[i % len(BACKGROUND_TYPES)]
                scene_img, labels = generate_single_scene(
                    material=material,
                    pool=pool,
                    bg_type=bg_type,
                    min_kernels=1,
                    max_kernels=30
                )

                scene_name = f"synth_{material}_{split}_{i+1:04d}"
                img_path = os.path.join(img_out_dir, f"{scene_name}.jpg")
                lbl_path = os.path.join(lbl_out_dir, f"{scene_name}.txt")

                # Save image (.jpg, 95 quality)
                cv2.imwrite(img_path, scene_img, [cv2.IMWRITE_JPEG_QUALITY, 95])

                # Save exact YOLO labels
                with open(lbl_path, 'w', encoding='utf-8') as lf:
                    for l in labels:
                        cid, xc, yc, bw, bh, _ = l
                        lf.write(f"{cid} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n")

                scene_counts_report[split][material] += 1
                total_kernels_material += len(labels)

                # Keep references for contact sheets
                if len(sample_images_for_review[f"{split}_{material}"]) < 20:
                    sample_images_for_review[f"{split}_{material}"].append(img_path)
                if len(sample_images_for_review[split]) < 20:
                    sample_images_for_review[split].append(img_path)

            dt = time.time() - t0
            avg_k = total_kernels_material / max(1, n_scenes)
            print(f"  Generated {n_scenes} {material} scenes ({total_kernels_material} kernels, avg {avg_k:.1f}/scene) in {dt:.1f}s.")

    # Write data.yaml
    write_synth_data_yaml()

    # Create contact sheets (20 scenes each)
    print("\n" + "=" * 75)
    print("PHASE 1 - STEP 3: GENERATING REVIEW CONTACT SHEETS (20 SCENES EACH)")
    print("=" * 75)

    contact_sheets = [
        ('train_peanut', 'review_train_peanut.jpg', 'Train Peanut Synthetic Scenes (20 Reviews)'),
        ('train_corn', 'review_train_corn.jpg', 'Train Corn Synthetic Scenes (20 Reviews)'),
        ('train_sunflower', 'review_train_sunflower.jpg', 'Train Sunflower Synthetic Scenes (20 Reviews)'),
        ('val', 'review_val_samples.jpg', 'Validation Synthetic Scenes (20 Reviews - Multi-Material)'),
        ('test', 'review_test_samples.jpg', 'Test Synthetic Scenes (20 Reviews - Multi-Material)')
    ]

    for key, sheet_fname, sheet_title in contact_sheets:
        paths = sample_images_for_review.get(key, [])
        if paths:
            out_sheet_path = os.path.join(REVIEW_ROOT, sheet_fname)
            create_contact_sheet(paths, out_sheet_path, title=sheet_title, grid_shape=(4, 5))

    # Grand Scene Summary Table
    print("\n" + "=" * 75)
    print("PHASE 1 GATE: SYNTHETIC SCENES GENERATION SUMMARY")
    print("=" * 75)
    print(f"{'Split':<10} | {'Peanut':<12} | {'Corn':<12} | {'Sunflower':<12} | {'Total Scenes':<14}")
    print("-" * 10 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 14)

    grand_total_scenes = 0
    for split in ['train', 'val', 'test']:
        p = scene_counts_report[split].get('peanut', 0)
        c = scene_counts_report[split].get('corn', 0)
        s = scene_counts_report[split].get('sunflower', 0)
        tot = p + c + s
        grand_total_scenes += tot
        print(f"{split:<10} | {p:<12} | {c:<12} | {s:<12} | {tot:<14}")

    print("-" * 10 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 14)
    print(f"{'TOTAL':<10} | {'':<12} | {'':<12} | {'':<12} | {grand_total_scenes:<14}")
    print("=" * 75 + "\n")


if __name__ == '__main__':
    main()
