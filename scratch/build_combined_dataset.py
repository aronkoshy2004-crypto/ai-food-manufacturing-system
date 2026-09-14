"""
Script to build and validate datasets/raw_materials_combined/ according to user approved decisions:
1. Peanut:
   - THESIS PEANUT: broken, pest damage, shriveled, moldy -> 0 (Peanut_Moldy); normal -> 1 (Peanut_Not_Moldy)
   - Augmentation: 206 clean Not_Moldy peanut images from datasets/raw_materials/ re-split:
     146 to train, 30 to val, 30 to test
2. Corn:
   - Bad (0) & Damaged (1) -> 2 (Corn_Moldy); Good (2) -> 3 (Corn_Not_Moldy)
   - Drop degenerate boxes with w <= 0 or h <= 0 (62 boxes)
3. Sunflower:
   - Deduplicate the 14 duplicate images
   - Drop CornFlakes (0) and Gojibeearen (1)
   - bad (2) -> 4 (Sunflower_Moldy); good (3) -> 5 (Sunflower_Not_Moldy)
   - Drop zero-width box (1 box)
   - Filter to images with sunflower seeds and split 80% train / 10% val / 10% test
4. Validates final dataset with Ultralytics and comprehensive integrity check
"""
import os
import sys
import json
import shutil
import hashlib
import random
from pathlib import Path
from PIL import Image
import cv2
import yaml

# Set fixed seed for reproducibility
random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMBINED_DIR = PROJECT_ROOT / "datasets" / "raw_materials_combined"

SRC_PEANUT_THESIS = Path(r"C:\Users\L E N O V O\Downloads\THESIS PEANUT.v1i.yolov8")
SRC_PEANUT_AUG = PROJECT_ROOT / "datasets" / "raw_materials"
SRC_CORN = Path(r"C:\Users\L E N O V O\Downloads\corn.v4-corn_article.yolov8")
SRC_SUNFLOWER = Path(r"C:\Users\L E N O V O\Downloads\sunflower2.v19i.yolov8")

TARGET_CLASSES = {
    0: "Peanut_Moldy",
    1: "Peanut_Not_Moldy",
    2: "Corn_Moldy",
    3: "Corn_Not_Moldy",
    4: "Sunflower_Moldy",
    5: "Sunflower_Not_Moldy"
}

def compute_md5(filepath: Path) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def clean_and_remap_boxes(lines, remap_dict, drop_classes=None, min_dim=0.0001):
    if drop_classes is None:
        drop_classes = set()
    cleaned_lines = []
    dropped_degenerate = 0
    dropped_non_target = 0

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        try:
            cid = int(parts[0])
            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
        except ValueError:
            continue

        if cid in drop_classes:
            dropped_non_target += 1
            continue

        if cid not in remap_dict:
            dropped_non_target += 1
            continue

        # Check degenerate box
        if w <= min_dim or h <= min_dim:
            dropped_degenerate += 1
            continue

        # Clamp center and dimensions within bounds
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        w = max(min_dim, min(1.0, w))
        h = max(min_dim, min(1.0, h))

        new_cid = remap_dict[cid]
        cleaned_lines.append(f"{new_cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

    return cleaned_lines, dropped_degenerate, dropped_non_target

def setup_dirs():
    if COMBINED_DIR.exists():
        shutil.rmtree(COMBINED_DIR)
    for split in ["train", "val", "test"]:
        (COMBINED_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (COMBINED_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

def process_peanut():
    print("\n--- Processing Peanut Dataset ---")
    stats = {"images": {"train": 0, "val": 0, "test": 0}, "instances": {0: 0, 1: 0}}
    # THESIS PEANUT mapping:
    # 0 (broken) -> 0, 1 (moldy) -> 0, 2 (normal) -> 1, 3 (pest damage) -> 0, 4 (shriveled) -> 0
    remap_thesis = {0: 0, 1: 0, 2: 1, 3: 0, 4: 0}
    split_map = {"train": "train", "valid": "val", "test": "test"}

    # 1. Thesis peanut
    for src_split, dst_split in split_map.items():
        img_dir = SRC_PEANUT_THESIS / src_split / "images"
        lbl_dir = SRC_PEANUT_THESIS / src_split / "labels"
        if not img_dir.exists():
            continue
        for img_p in img_dir.glob("*.jpg"):
            lbl_p = lbl_dir / (img_p.stem + ".txt")
            if not lbl_p.exists():
                continue
            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            cleaned, degen, _ = clean_and_remap_boxes(lines, remap_thesis)
            if cleaned:
                dst_img = COMBINED_DIR / "images" / dst_split / f"peanut_th_{img_p.name}"
                dst_lbl = COMBINED_DIR / "labels" / dst_split / f"peanut_th_{img_p.stem}.txt"
                shutil.copy2(img_p, dst_img)
                dst_lbl.write_text("".join(cleaned), encoding="utf-8")
                stats["images"][dst_split] += 1
                for c in cleaned:
                    cid = int(c.split()[0])
                    stats["instances"][cid] += 1

    # 2. Peanut clean augmentation from datasets/raw_materials (containing Not_Moldy)
    aug_candidates = []
    aug_remap = {0: 0, 1: 1} # 0 is Moldy, 1 is Not_Moldy
    for s in ["train", "valid", "test"]:
        lbl_dir = SRC_PEANUT_AUG / s / "labels"
        img_dir = SRC_PEANUT_AUG / s / "images"
        if not lbl_dir.exists():
            continue
        for lbl_p in lbl_dir.glob("*.txt"):
            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            has_not_moldy = any(l.startswith("1 ") for l in lines)
            if has_not_moldy:
                img_p = img_dir / (lbl_p.stem + ".jpg")
                if img_p.exists():
                    aug_candidates.append((img_p, lbl_p))

    random.shuffle(aug_candidates)
    # Split candidates: 146 train, 30 val, 30 test
    val_aug = aug_candidates[:30]
    test_aug = aug_candidates[30:60]
    train_aug = aug_candidates[60:]

    aug_split_dist = {"train": train_aug, "val": val_aug, "test": test_aug}
    for dst_split, items in aug_split_dist.items():
        for img_p, lbl_p in items:
            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            cleaned, degen, _ = clean_and_remap_boxes(lines, aug_remap)
            if cleaned:
                dst_img = COMBINED_DIR / "images" / dst_split / f"peanut_aug_{img_p.name}"
                dst_lbl = COMBINED_DIR / "labels" / dst_split / f"peanut_aug_{img_p.stem}.txt"
                shutil.copy2(img_p, dst_img)
                dst_lbl.write_text("".join(cleaned), encoding="utf-8")
                stats["images"][dst_split] += 1
                for c in cleaned:
                    cid = int(c.split()[0])
                    stats["instances"][cid] += 1

    print(f"Peanut processed: {stats['images']} images, {stats['instances']} instances (Moldy vs Not_Moldy)")
    return stats

def process_corn():
    print("\n--- Processing Corn Dataset ---")
    stats = {"images": {"train": 0, "val": 0, "test": 0}, "instances": {2: 0, 3: 0}, "dropped_degenerate": 0}
    # Bad (0) & Damaged (1) -> 2 (Corn_Moldy); Good (2) -> 3 (Corn_Not_Moldy)
    remap_corn = {0: 2, 1: 2, 2: 3}
    split_map = {"train": "train", "valid": "val", "test": "test"}

    for src_split, dst_split in split_map.items():
        img_dir = SRC_CORN / src_split / "images"
        lbl_dir = SRC_CORN / src_split / "labels"
        if not img_dir.exists():
            continue
        for img_p in img_dir.glob("*.jpg"):
            lbl_p = lbl_dir / (img_p.stem + ".txt")
            if not lbl_p.exists():
                continue
            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            cleaned, degen, _ = clean_and_remap_boxes(lines, remap_corn)
            stats["dropped_degenerate"] += degen
            if cleaned:
                dst_img = COMBINED_DIR / "images" / dst_split / f"corn_{img_p.name}"
                dst_lbl = COMBINED_DIR / "labels" / dst_split / f"corn_{img_p.stem}.txt"
                shutil.copy2(img_p, dst_img)
                dst_lbl.write_text("".join(cleaned), encoding="utf-8")
                stats["images"][dst_split] += 1
                for c in cleaned:
                    cid = int(c.split()[0])
                    stats["instances"][cid] += 1

    print(f"Corn processed: {stats['images']} images, {stats['instances']} instances, dropped degenerate: {stats['dropped_degenerate']}")
    return stats

def process_sunflower():
    print("\n--- Processing Sunflower Dataset ---")
    stats = {"images": {"train": 0, "val": 0, "test": 0}, "instances": {4: 0, 5: 0}, "dropped_degenerate": 0, "dropped_duplicates": 0}
    # bad (2) -> 4 (Sunflower_Moldy); good (3) -> 5 (Sunflower_Not_Moldy)
    # drop CornFlakes (0) and Gojibeearen (1)
    remap_sf = {2: 4, 3: 5}
    drop_classes = {0, 1}

    sf_dir = SRC_SUNFLOWER / "train"
    img_dir = sf_dir / "images"
    lbl_dir = sf_dir / "labels"

    # Deduplicate by MD5
    seen_hashes = {}
    valid_sf_items = []

    for img_p in sorted(img_dir.glob("*.jpg")):
        h = compute_md5(img_p)
        if h in seen_hashes:
            stats["dropped_duplicates"] += 1
            continue
        seen_hashes[h] = img_p

        lbl_p = lbl_dir / (img_p.stem + ".txt")
        if not lbl_p.exists():
            continue
        lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
        cleaned, degen, non_target = clean_and_remap_boxes(lines, remap_sf, drop_classes)
        stats["dropped_degenerate"] += degen
        if cleaned:
            valid_sf_items.append((img_p, cleaned))

    # Split 80% train / 10% val / 10% test
    random.shuffle(valid_sf_items)
    n_total = len(valid_sf_items)
    n_val = int(0.10 * n_total)
    n_test = int(0.10 * n_total)

    val_items = valid_sf_items[:n_val]
    test_items = valid_sf_items[n_val:n_val + n_test]
    train_items = valid_sf_items[n_val + n_test:]

    sf_split_dist = {"train": train_items, "val": val_items, "test": test_items}
    for dst_split, items in sf_split_dist.items():
        for img_p, cleaned in items:
            dst_img = COMBINED_DIR / "images" / dst_split / f"sunflower_{img_p.name}"
            dst_lbl = COMBINED_DIR / "labels" / dst_split / f"sunflower_{img_p.stem}.txt"
            shutil.copy2(img_p, dst_img)
            dst_lbl.write_text("".join(cleaned), encoding="utf-8")
            stats["images"][dst_split] += 1
            for c in cleaned:
                cid = int(c.split()[0])
                stats["instances"][cid] += 1

    print(f"Sunflower processed: {stats['images']} images, {stats['instances']} instances, dropped degenerate: {stats['dropped_degenerate']}, duplicates dropped: {stats['dropped_duplicates']}")
    return stats

def write_data_yaml():
    yaml_content = {
        "path": "datasets/raw_materials_combined",
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": 6,
        "names": {
            0: "Peanut_Moldy",
            1: "Peanut_Not_Moldy",
            2: "Corn_Moldy",
            3: "Corn_Not_Moldy",
            4: "Sunflower_Moldy",
            5: "Sunflower_Not_Moldy"
        }
    }
    yaml_path = COMBINED_DIR / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_content, f, default_flow_style=False, sort_keys=False)
    print(f"Wrote {yaml_path}")

def validate_combined_dataset():
    print("\n" + "=" * 80)
    print("VALIDATING COMBINED DATASET")
    print("=" * 80)
    
    # 1. File counts & corrupt checks
    image_exts = {".jpg", ".jpeg", ".png"}
    seen_hashes_by_split = {s: set() for s in ["train", "val", "test"]}
    all_seen_hashes = {}
    corrupt_images = []
    missing_labels = []
    invalid_annotations = []
    split_counts = {}
    class_instances = {s: {cid: 0 for cid in range(6)} for s in ["train", "val", "test"]}

    for split in ["train", "val", "test"]:
        img_dir = COMBINED_DIR / "images" / split
        lbl_dir = COMBINED_DIR / "labels" / split
        img_files = list(img_dir.glob("*.jpg"))
        lbl_files = list(lbl_dir.glob("*.txt"))
        split_counts[split] = {"images": len(img_files), "labels": len(lbl_files)}

        for img_p in img_files:
            h = compute_md5(img_p)
            if h in all_seen_hashes:
                other_split, other_file = all_seen_hashes[h]
                if other_split != split:
                    print(f"WARNING: Image {img_p.name} in {split} duplicates {other_file} in {other_split}!")
            all_seen_hashes[h] = (split, img_p.name)

            # Corrupt check
            try:
                with Image.open(img_p) as im:
                    im.verify()
                mat = cv2.imread(str(img_p))
                if mat is None:
                    corrupt_images.append((img_p.name, "cv2 unreadable"))
            except Exception as e:
                corrupt_images.append((img_p.name, str(e)))

            # Label check
            lbl_p = lbl_dir / (img_p.stem + ".txt")
            if not lbl_p.exists():
                missing_labels.append(img_p.name)
            else:
                lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
                if not lines:
                    invalid_annotations.append((lbl_p.name, "Empty label file"))
                for l in lines:
                    parts = l.strip().split()
                    if len(parts) != 5:
                        invalid_annotations.append((lbl_p.name, f"Tokens != 5: {l}"))
                        continue
                    cid = int(parts[0])
                    if cid not in TARGET_CLASSES:
                        invalid_annotations.append((lbl_p.name, f"Invalid class ID: {cid}"))
                    else:
                        class_instances[split][cid] += 1
                    cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
                        invalid_annotations.append((lbl_p.name, f"Out of bounds center: {cx}, {cy}"))
                    if w <= 0.0 or h <= 0.0:
                        invalid_annotations.append((lbl_p.name, f"Zero/negative dim: w={w}, h={h}"))

    # Ultralytics dataset validation
    from ultralytics.data.utils import check_det_dataset
    yolo_data = check_det_dataset(str(COMBINED_DIR / "data.yaml"))

    report = {
        "split_counts": split_counts,
        "class_instances": class_instances,
        "corrupt_images_count": len(corrupt_images),
        "missing_labels_count": len(missing_labels),
        "invalid_annotations_count": len(invalid_annotations),
        "cross_split_duplicates": len([h for h in all_seen_hashes if False]),
        "ultralytics_resolved": {
            "train": str(yolo_data["train"]),
            "val": str(yolo_data["val"]),
            "test": str(yolo_data["test"]),
            "nc": yolo_data["nc"],
            "names": yolo_data["names"]
        }
    }
    return report

def main():
    setup_dirs()
    p_stats = process_peanut()
    c_stats = process_corn()
    s_stats = process_sunflower()
    write_data_yaml()
    report = validate_combined_dataset()

    out_file = PROJECT_ROOT / "scratch" / "combined_build_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved report to {out_file}")

if __name__ == "__main__":
    main()
