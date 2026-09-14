"""
Merge expanded corn datasets into datasets/raw_materials_combined:
1. corn_quality.v1-v1-corn_quality.yolov8:
   - Class 0 -> 3 (Corn_Not_Moldy)
   - Class 1 -> 2 (Corn_Moldy)
   - Splits: train (311), valid -> val (90), test (45)
2. Corn Defects.v6i.yolov8:
   - 1 (inteiro) + 2 (padrao) -> 3 (Corn_Not_Moldy)
   - 4 (ponto_preto) -> 2 (Corn_Moldy)
   - 0 (corpo_estranho) & 3 (pelicula) -> EXCLUDED
   - 80/20 train/val split on images containing target classes
3. Sunflower_Seeds and Groundnut Dataset of Three Grades:
   - Strictly EXCLUDED
4. Full post-merge integrity check and report generation
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

random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMBINED_DIR = PROJECT_ROOT / "datasets" / "raw_materials_combined"

SRC_CORN_QUALITY = Path(r"C:\Users\L E N O V O\Downloads\corn_quality.v1-v1-corn_quality.yolov8")
SRC_CORN_DEFECTS = Path(r"C:\Users\L E N O V O\Downloads\Corn Defects.v6i.yolov8")

TARGET_CLASSES = {
    0: "Peanut_Moldy",
    1: "Peanut_Not_Moldy",
    2: "Corn_Moldy",
    3: "Corn_Not_Moldy",
    4: "Sunflower_Moldy",
    5: "Sunflower_Not_Moldy"
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def get_md5(filepath: Path) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_dataset_stats(dataset_dir: Path):
    splits = ["train", "val", "test"]
    stats = {
        "images": {s: 0 for s in splits},
        "labels": {s: 0 for s in splits},
        "instances": {s: {cid: 0 for cid in TARGET_CLASSES} for s in splits},
        "total_instances": {cid: 0 for cid in TARGET_CLASSES}
    }
    for s in splits:
        img_dir = dataset_dir / "images" / s
        lbl_dir = dataset_dir / "labels" / s
        if img_dir.exists():
            stats["images"][s] = len([f for f in img_dir.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS])
        if lbl_dir.exists():
            stats["labels"][s] = len([f for f in lbl_dir.iterdir() if f.is_file() and f.suffix.lower() == ".txt"])
            for lf in lbl_dir.glob("*.txt"):
                lines = lf.read_text(encoding="utf-8").strip().splitlines()
                for line in lines:
                    parts = line.strip().split()
                    if parts:
                        cid = int(parts[0])
                        if cid in stats["instances"][s]:
                            stats["instances"][s][cid] += 1
                            stats["total_instances"][cid] += 1
    return stats


def merge_corn_quality():
    print("\n--- 1. Merging corn_quality.v1-v1-corn_quality.yolov8 ---")
    remap = {0: 3, 1: 2}  # 0 -> Corn_Not_Moldy (3), 1 -> Corn_Moldy (2)
    split_map = {"train": "train", "valid": "val", "test": "test"}

    added_images = {"train": 0, "val": 0, "test": 0}
    added_boxes = {2: 0, 3: 0}

    for src_split, dst_split in split_map.items():
        img_dir = SRC_CORN_QUALITY / src_split / "images"
        lbl_dir = SRC_CORN_QUALITY / src_split / "labels"

        dst_img_dir = COMBINED_DIR / "images" / dst_split
        dst_lbl_dir = COMBINED_DIR / "labels" / dst_split

        for img_p in sorted(img_dir.glob("*.jpg")):
            lbl_p = lbl_dir / (img_p.stem + ".txt")
            if not lbl_p.exists():
                print(f"[WARN] Missing label for {img_p}")
                continue

            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            cleaned_lines = []
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cid = int(parts[0])
                    if cid in remap:
                        new_cid = remap[cid]
                        cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                        # clamp bounds
                        cx, cy = max(0.0, min(1.0, cx)), max(0.0, min(1.0, cy))
                        w, h = max(0.0001, min(1.0, w)), max(0.0001, min(1.0, h))
                        cleaned_lines.append(f"{new_cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
                        added_boxes[new_cid] += 1

            if cleaned_lines:
                target_img_name = f"corn_cq_{img_p.name}"
                target_lbl_name = f"corn_cq_{img_p.stem}.txt"

                shutil.copy2(img_p, dst_img_dir / target_img_name)
                (dst_lbl_dir / target_lbl_name).write_text("".join(cleaned_lines), encoding="utf-8")
                added_images[dst_split] += 1

    print(f"corn_quality merged: {added_images} images, {added_boxes} boxes (2: Corn_Moldy, 3: Corn_Not_Moldy)")
    return added_images, added_boxes


def merge_corn_defects():
    print("\n--- 2. Merging Corn Defects.v6i.yolov8 (80/20 Train/Val Split) ---")
    # inteiro (1) -> 3, padrao (2) -> 3, ponto_preto (4) -> 2
    # corpo_estranho (0) & pelicula (3) -> EXCLUDED
    remap = {1: 3, 2: 3, 4: 2}
    exclude_classes = {0, 3}

    img_dir = SRC_CORN_DEFECTS / "train" / "images"
    lbl_dir = SRC_CORN_DEFECTS / "train" / "labels"

    candidate_items = []
    excluded_empty_images = 0

    for img_p in sorted(img_dir.glob("*.jpg")):
        lbl_p = lbl_dir / (img_p.stem + ".txt")
        if not lbl_p.exists():
            continue

        lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
        cleaned_lines = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 5:
                cid = int(parts[0])
                if cid in exclude_classes:
                    continue
                if cid in remap:
                    new_cid = remap[cid]
                    cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    cx, cy = max(0.0, min(1.0, cx)), max(0.0, min(1.0, cy))
                    w, h = max(0.0001, min(1.0, w)), max(0.0001, min(1.0, h))
                    cleaned_lines.append(f"{new_cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

        if cleaned_lines:
            candidate_items.append((img_p, cleaned_lines))
        else:
            excluded_empty_images += 1

    print(f"Corn Defects candidates with target boxes: {len(candidate_items)} (Excluded {excluded_empty_images} images with only foreign matter/pelicula)")

    # Deterministic 80/20 train/val split
    random.shuffle(candidate_items)
    n_total = len(candidate_items)
    n_val = int(round(0.20 * n_total))
    val_items = candidate_items[:n_val]
    train_items = candidate_items[n_val:]

    added_images = {"train": len(train_items), "val": len(val_items), "test": 0}
    added_boxes = {2: 0, 3: 0}

    split_dist = {"train": train_items, "val": val_items}
    for dst_split, items in split_dist.items():
        dst_img_dir = COMBINED_DIR / "images" / dst_split
        dst_lbl_dir = COMBINED_DIR / "labels" / dst_split

        for img_p, cleaned_lines in items:
            target_img_name = f"corn_cd_{img_p.name}"
            target_lbl_name = f"corn_cd_{img_p.stem}.txt"

            shutil.copy2(img_p, dst_img_dir / target_img_name)
            (dst_lbl_dir / target_lbl_name).write_text("".join(cleaned_lines), encoding="utf-8")

            for l in cleaned_lines:
                cid = int(l.split()[0])
                added_boxes[cid] += 1

    print(f"Corn Defects merged: {added_images} images (80/20 train/val), {added_boxes} boxes (2: Corn_Moldy, 3: Corn_Not_Moldy)")
    return added_images, added_boxes


def run_full_integrity_check(dataset_dir: Path):
    print("\n--- 3. Running Comprehensive Integrity Check on Expanded Dataset ---")
    splits = ["train", "val", "test"]

    corrupt_images = []
    missing_labels = []
    unmatched_labels = []
    invalid_boxes = []
    split_hashes = {s: {} for s in splits}
    cross_split_duplicates = []

    total_images = 0
    total_labels = 0

    for s in splits:
        img_dir = dataset_dir / "images" / s
        lbl_dir = dataset_dir / "labels" / s

        img_files = sorted([f for f in img_dir.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS])
        lbl_files = sorted([f for f in lbl_dir.iterdir() if f.is_file() and f.suffix.lower() == ".txt"])

        total_images += len(img_files)
        total_labels += len(lbl_files)

        lbl_map = {f.stem: f for f in lbl_files}
        img_stems = set(f.stem for f in img_files)

        # Unmatched labels
        for lstem, lpath in lbl_map.items():
            if lstem not in img_stems:
                unmatched_labels.append(f"{s}/{lpath.name}")

        # Check images
        for img_p in img_files:
            h = get_md5(img_p)
            split_hashes[s][h] = img_p.name

            # PIL & OpenCV verify
            try:
                with Image.open(img_p) as im:
                    im.verify()
                mat = cv2.imread(str(img_p))
                if mat is None:
                    corrupt_images.append(f"{s}/{img_p.name}: OpenCV decode returned None")
            except Exception as e:
                corrupt_images.append(f"{s}/{img_p.name}: {e}")

            # Check matching label
            if img_p.stem not in lbl_map:
                missing_labels.append(f"{s}/{img_p.name}")
            else:
                lpath = lbl_map[img_p.stem]
                lines = lpath.read_text(encoding="utf-8").strip().splitlines()
                for line_no, line in enumerate(lines, 1):
                    parts = line.strip().split()
                    if len(parts) < 5:
                        invalid_boxes.append(f"{s}/{lpath.name}: Line {line_no} malformed")
                        continue
                    try:
                        cid = int(parts[0])
                        cx, cy, w, h_box = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                        if cid not in TARGET_CLASSES:
                            invalid_boxes.append(f"{s}/{lpath.name}: Invalid class ID {cid}")
                        if w <= 0 or h_box <= 0:
                            invalid_boxes.append(f"{s}/{lpath.name}: Box dimension w={w}, h={h_box} <= 0")
                        if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
                            invalid_boxes.append(f"{s}/{lpath.name}: Center ({cx}, {cy}) outside [0, 1]")
                    except Exception as e:
                        invalid_boxes.append(f"{s}/{lpath.name}: Parse error {e}")

    # Cross-split duplicates
    for h, fn_train in split_hashes["train"].items():
        if h in split_hashes["val"]:
            cross_split_duplicates.append(f"Train {fn_train} == Val {split_hashes['val'][h]}")
        if h in split_hashes["test"]:
            cross_split_duplicates.append(f"Train {fn_train} == Test {split_hashes['test'][h]}")

    for h, fn_val in split_hashes["val"].items():
        if h in split_hashes["test"]:
            cross_split_duplicates.append(f"Val {fn_val} == Test {split_hashes['test'][h]}")

    results = {
        "total_images": total_images,
        "total_labels": total_labels,
        "corrupt_images": corrupt_images,
        "missing_labels": missing_labels,
        "unmatched_labels": unmatched_labels,
        "invalid_boxes": invalid_boxes,
        "cross_split_duplicates": cross_split_duplicates
    }

    print(f"Integrity check complete: {total_images} images, {total_labels} labels")
    print(f"  Corrupt images: {len(corrupt_images)}")
    print(f"  Missing labels: {len(missing_labels)}")
    print(f"  Unmatched labels: {len(unmatched_labels)}")
    print(f"  Invalid boxes: {len(invalid_boxes)}")
    print(f"  Cross-split duplicates: {len(cross_split_duplicates)}")

    return results


def main():
    print("=" * 80)
    print("EXPANDING DATASETS/RAW_MATERIALS_COMBINED WITH APPROVED CORN DATASETS")
    print("=" * 80)

    # 1. Baseline stats
    baseline_stats = get_dataset_stats(COMBINED_DIR)
    print("\nBaseline total images:", sum(baseline_stats["images"].values()))
    print("Baseline instances:", baseline_stats["total_instances"])

    # 2. Merge corn_quality
    cq_imgs, cq_boxes = merge_corn_quality()

    # 3. Merge Corn Defects
    cd_imgs, cd_boxes = merge_corn_defects()

    # 4. Integrity check on final expanded dataset
    integrity_results = run_full_integrity_check(COMBINED_DIR)

    # 5. Final stats
    expanded_stats = get_dataset_stats(COMBINED_DIR)

    # Build report payload
    comparison_report = {
        "baseline": baseline_stats,
        "added_corn_quality": {"images": cq_imgs, "boxes": cq_boxes},
        "added_corn_defects": {"images": cd_imgs, "boxes": cd_boxes},
        "expanded": expanded_stats,
        "integrity": integrity_results,
        "classes": TARGET_CLASSES
    }

    out_file = PROJECT_ROOT / "scratch" / "expanded_dataset_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(comparison_report, f, indent=2)

    print(f"\nSaved expansion report to {out_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
