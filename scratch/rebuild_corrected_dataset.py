"""
Unified Rebuilder for datasets/raw_materials_combined incorporating all 5 source datasets:
1. corn.v4-corn_article.yolov8:
   - 0 (Fusarium rot) -> 2 (Corn_Moldy)
   - 1 (Healthy intact corn) -> 3 (Corn_Not_Moldy)
   - 2 (Broken / fragments) -> EXCLUDED
2. corn_quality.v1-v1-corn_quality.yolov8:
   - 0 (Standard intact corn) -> 3 (Corn_Not_Moldy)
   - 1 (Moldy / rot / black-spot) -> 2 (Corn_Moldy)
   - Splits: train (311), valid -> val (90), test (45)
3. Corn Defects.v6i.yolov8:
   - 1 (inteiro) + 2 (padrao) -> 3 (Corn_Not_Moldy)
   - 4 (ponto_preto) -> 2 (Corn_Moldy)
   - 0 (corpo_estranho) & 3 (pelicula) -> EXCLUDED
   - Splits: 80% train / 20% val
4. THESIS PEANUT.v1i.yolov8:
   - 1 (moldy) -> 0 (Peanut_Moldy)
   - 2 (normal) -> 1 (Peanut_Not_Moldy)
   - 0 (broken), 3 (pest damage), 4 (shriveled) -> EXCLUDED
   - Clean peanut augmentation (datasets/raw_materials):
     1 (Not_Moldy) -> 1 (Peanut_Not_Moldy)
5. sunflower2.v19i.yolov8:
   - 3 (good / dehusked pale seeds) -> 5 (Sunflower_Not_Moldy)
   - 2 (bad / in-shell striped seeds & cracked shells) -> EXCLUDED (do NOT label as mold!)
   - 0 (CornFlakes) & 1 (Gojibeearen) -> EXCLUDED
   - 4 (Sunflower_Moldy) -> 0 instances (genuine mold unavailable)
"""
import os
import sys
import shutil
import hashlib
import random
from pathlib import Path
import yaml

random.seed(42)

PROJECT_ROOT = Path(r"c:\Users\L E N O V O\Food man")
COMBINED_DIR = PROJECT_ROOT / "datasets" / "raw_materials_combined"

SRC_CORN = Path(r"C:\Users\L E N O V O\Downloads\corn.v4-corn_article.yolov8")
SRC_CORN_QUALITY = Path(r"C:\Users\L E N O V O\Downloads\corn_quality.v1-v1-corn_quality.yolov8")
SRC_CORN_DEFECTS = Path(r"C:\Users\L E N O V O\Downloads\Corn Defects.v6i.yolov8")

SRC_PEANUT_THESIS = Path(r"C:\Users\L E N O V O\Downloads\THESIS PEANUT.v1i.yolov8")
SRC_PEANUT_AUG = PROJECT_ROOT / "datasets" / "raw_materials"
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

def clean_and_remap_boxes(lines, remap_dict, min_dim=0.0001):
    cleaned_lines = []
    dropped_excluded = 0
    dropped_degenerate = 0

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        try:
            cid = int(parts[0])
            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
        except ValueError:
            continue

        if cid not in remap_dict:
            dropped_excluded += 1
            continue

        if w <= min_dim or h <= min_dim:
            dropped_degenerate += 1
            continue

        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        w = max(min_dim, min(1.0, w))
        h = max(min_dim, min(1.0, h))

        new_cid = remap_dict[cid]
        cleaned_lines.append(f"{new_cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

    return cleaned_lines, dropped_degenerate, dropped_excluded

def setup_dirs():
    print("[1/7] Setting up target dataset directory structure...")
    if COMBINED_DIR.exists():
        shutil.rmtree(COMBINED_DIR)
    for split in ["train", "val", "test"]:
        (COMBINED_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (COMBINED_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)
    print("  -> Directory structure initialized at", COMBINED_DIR)

def process_corn_v4():
    print("\n[2/7] Processing corn.v4-corn_article.yolov8 (Corrected)...")
    remap_corn = {0: 2, 1: 3}
    split_map = {"train": "train", "valid": "val", "test": "test"}

    stats = {
        "images": {"train": 0, "val": 0, "test": 0},
        "instances": {"train": {2: 0, 3: 0}, "val": {2: 0, 3: 0}, "test": {2: 0, 3: 0}},
        "dropped_degenerate": 0,
        "dropped_excluded": 0
    }

    for src_split, dst_split in split_map.items():
        img_dir = SRC_CORN / src_split / "images"
        lbl_dir = SRC_CORN / src_split / "labels"
        if not img_dir.exists():
            continue
        for img_p in sorted(img_dir.glob("*.jpg")):
            lbl_p = lbl_dir / (img_p.stem + ".txt")
            if not lbl_p.exists():
                continue
            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            cleaned, degen, excl = clean_and_remap_boxes(lines, remap_corn)
            stats["dropped_degenerate"] += degen
            stats["dropped_excluded"] += excl
            if cleaned:
                dst_img = COMBINED_DIR / "images" / dst_split / f"corn_{img_p.name}"
                dst_lbl = COMBINED_DIR / "labels" / dst_split / f"corn_{img_p.stem}.txt"
                shutil.copy2(img_p, dst_img)
                dst_lbl.write_text("".join(cleaned), encoding="utf-8")
                stats["images"][dst_split] += 1
                for c in cleaned:
                    cid = int(c.split()[0])
                    stats["instances"][dst_split][cid] += 1

    total_m = sum(stats["instances"][s][2] for s in split_map.values())
    total_h = sum(stats["instances"][s][3] for s in split_map.values())
    print(f"  -> corn.v4 processed: {stats['images']} images | Moldy={total_m} | Clean={total_h} | Excluded broken={stats['dropped_excluded']}")
    return stats

def process_corn_quality():
    print("\n[3/7] Processing corn_quality.v1-v1-corn_quality.yolov8 (Corrected)...")
    # In corn_quality: 0 is clean intact (-> 3), 1 is mold/rot/black spot (-> 2)
    remap = {0: 3, 1: 2}
    split_map = {"train": "train", "valid": "val", "test": "test"}

    stats = {
        "images": {"train": 0, "val": 0, "test": 0},
        "instances": {"train": {2: 0, 3: 0}, "val": {2: 0, 3: 0}, "test": {2: 0, 3: 0}},
        "dropped_degenerate": 0,
        "dropped_excluded": 0
    }

    for src_split, dst_split in split_map.items():
        img_dir = SRC_CORN_QUALITY / src_split / "images"
        lbl_dir = SRC_CORN_QUALITY / src_split / "labels"
        if not img_dir.exists():
            continue
        for img_p in sorted(img_dir.glob("*.jpg")):
            lbl_p = lbl_dir / (img_p.stem + ".txt")
            if not lbl_p.exists():
                continue
            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            cleaned, degen, excl = clean_and_remap_boxes(lines, remap)
            stats["dropped_degenerate"] += degen
            stats["dropped_excluded"] += excl
            if cleaned:
                dst_img = COMBINED_DIR / "images" / dst_split / f"corn_cq_{img_p.name}"
                dst_lbl = COMBINED_DIR / "labels" / dst_split / f"corn_cq_{img_p.stem}.txt"
                shutil.copy2(img_p, dst_img)
                dst_lbl.write_text("".join(cleaned), encoding="utf-8")
                stats["images"][dst_split] += 1
                for c in cleaned:
                    cid = int(c.split()[0])
                    stats["instances"][dst_split][cid] += 1

    total_m = sum(stats["instances"][s][2] for s in split_map.values())
    total_h = sum(stats["instances"][s][3] for s in split_map.values())
    print(f"  -> corn_quality processed: {stats['images']} images | Moldy={total_m} | Clean={total_h}")
    return stats

def process_corn_defects():
    print("\n[4/7] Processing Corn Defects.v6i.yolov8 (Corrected)...")
    # inteiro (1) -> 3, padrao (2) -> 3, ponto_preto (4) -> 2
    # corpo_estranho (0) & pelicula (3) -> EXCLUDED
    remap = {1: 3, 2: 3, 4: 2}

    img_dir = SRC_CORN_DEFECTS / "train" / "images"
    lbl_dir = SRC_CORN_DEFECTS / "train" / "labels"

    candidate_items = []
    stats = {
        "images": {"train": 0, "val": 0, "test": 0},
        "instances": {"train": {2: 0, 3: 0}, "val": {2: 0, 3: 0}, "test": {2: 0, 3: 0}},
        "dropped_degenerate": 0,
        "dropped_excluded": 0
    }

    for img_p in sorted(img_dir.glob("*.jpg")):
        lbl_p = lbl_dir / (img_p.stem + ".txt")
        if not lbl_p.exists():
            continue
        lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
        cleaned, degen, excl = clean_and_remap_boxes(lines, remap)
        stats["dropped_degenerate"] += degen
        stats["dropped_excluded"] += excl
        if cleaned:
            candidate_items.append((img_p, cleaned))

    # 80/20 train/val split
    random.shuffle(candidate_items)
    n_val = int(round(0.20 * len(candidate_items)))
    val_items = candidate_items[:n_val]
    train_items = candidate_items[n_val:]

    split_dist = {"train": train_items, "val": val_items}
    for dst_split, items in split_dist.items():
        for img_p, cleaned in items:
            dst_img = COMBINED_DIR / "images" / dst_split / f"corn_cd_{img_p.name}"
            dst_lbl = COMBINED_DIR / "labels" / dst_split / f"corn_cd_{img_p.stem}.txt"
            shutil.copy2(img_p, dst_img)
            dst_lbl.write_text("".join(cleaned), encoding="utf-8")
            stats["images"][dst_split] += 1
            for c in cleaned:
                cid = int(c.split()[0])
                stats["instances"][dst_split][cid] += 1

    total_m = sum(stats["instances"][s][2] for s in ["train", "val"])
    total_h = sum(stats["instances"][s][3] for s in ["train", "val"])
    print(f"  -> Corn Defects processed: {stats['images']} images (80/20 train/val) | Moldy={total_m} | Clean={total_h} | Excluded={stats['dropped_excluded']}")
    return stats

def process_peanut():
    print("\n[5/7] Processing Peanut Dataset with Disentangled Taxonomy...")
    # Class 1 (moldy) -> 0 (Peanut_Moldy)
    # Class 2 (normal) -> 1 (Peanut_Not_Moldy)
    # Classes 0 (broken), 3 (pest damage), 4 (shriveled) -> EXCLUDED
    remap_thesis = {1: 0, 2: 1}
    split_map = {"train": "train", "valid": "val", "test": "test"}

    stats = {
        "images": {"train": 0, "val": 0, "test": 0},
        "instances": {"train": {0: 0, 1: 0}, "val": {0: 0, 1: 0}, "test": {0: 0, 1: 0}},
        "dropped_excluded": 0,
        "dropped_degenerate": 0
    }

    # 1. Thesis peanut
    for src_split, dst_split in split_map.items():
        img_dir = SRC_PEANUT_THESIS / src_split / "images"
        lbl_dir = SRC_PEANUT_THESIS / src_split / "labels"
        if not img_dir.exists():
            continue
        for img_p in sorted(img_dir.glob("*.jpg")):
            lbl_p = lbl_dir / (img_p.stem + ".txt")
            if not lbl_p.exists():
                continue
            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            cleaned, degen, excl = clean_and_remap_boxes(lines, remap_thesis)
            stats["dropped_degenerate"] += degen
            stats["dropped_excluded"] += excl
            if cleaned:
                dst_img = COMBINED_DIR / "images" / dst_split / f"peanut_th_{img_p.name}"
                dst_lbl = COMBINED_DIR / "labels" / dst_split / f"peanut_th_{img_p.stem}.txt"
                shutil.copy2(img_p, dst_img)
                dst_lbl.write_text("".join(cleaned), encoding="utf-8")
                stats["images"][dst_split] += 1
                for c in cleaned:
                    cid = int(c.split()[0])
                    stats["instances"][dst_split][cid] += 1

    # 2. Peanut clean augmentation
    aug_candidates = []
    aug_remap = {1: 1}
    for s in ["train", "valid", "test"]:
        lbl_dir = SRC_PEANUT_AUG / s / "labels"
        img_dir = SRC_PEANUT_AUG / s / "images"
        if not lbl_dir.exists():
            continue
        for lbl_p in sorted(lbl_dir.glob("*.txt")):
            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            has_not_moldy = any(l.startswith("1 ") for l in lines)
            if has_not_moldy:
                img_p = img_dir / (lbl_p.stem + ".jpg")
                if img_p.exists():
                    aug_candidates.append((img_p, lbl_p))

    random.shuffle(aug_candidates)
    val_aug = aug_candidates[:30]
    test_aug = aug_candidates[30:60]
    train_aug = aug_candidates[60:]

    aug_split_dist = {"train": train_aug, "val": val_aug, "test": test_aug}
    for dst_split, items in aug_split_dist.items():
        for img_p, lbl_p in items:
            lines = lbl_p.read_text(encoding="utf-8").strip().splitlines()
            cleaned, degen, excl = clean_and_remap_boxes(lines, aug_remap)
            if cleaned:
                dst_img = COMBINED_DIR / "images" / dst_split / f"peanut_aug_{img_p.name}"
                dst_lbl = COMBINED_DIR / "labels" / dst_split / f"peanut_aug_{img_p.stem}.txt"
                shutil.copy2(img_p, dst_img)
                dst_lbl.write_text("".join(cleaned), encoding="utf-8")
                stats["images"][dst_split] += 1
                for c in cleaned:
                    cid = int(c.split()[0])
                    stats["instances"][dst_split][cid] += 1

    total_m = sum(stats["instances"][s][0] for s in split_map.values())
    total_h = sum(stats["instances"][s][1] for s in split_map.values())
    print(f"  -> Peanut processed: {stats['images']} images | Moldy={total_m} | Clean={total_h} | Excluded non-mold={stats['dropped_excluded']}")
    return stats

def process_sunflower():
    print("\n[6/7] Processing Sunflower Dataset (Purging Fake Mold)...")
    # 3 (good / hulled pale seeds) -> 5 (Sunflower_Not_Moldy)
    # 2 (bad / in-shell seeds & shells) -> EXCLUDED (NOT mold)
    remap_sf = {3: 5}

    sf_dir = SRC_SUNFLOWER / "train"
    img_dir = sf_dir / "images"
    lbl_dir = sf_dir / "labels"

    seen_hashes = {}
    valid_sf_items = []
    stats = {
        "images": {"train": 0, "val": 0, "test": 0},
        "instances": {"train": {4: 0, 5: 0}, "val": {4: 0, 5: 0}, "test": {4: 0, 5: 0}},
        "dropped_excluded": 0,
        "dropped_duplicates": 0,
        "dropped_degenerate": 0
    }

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
        cleaned, degen, excl = clean_and_remap_boxes(lines, remap_sf)
        stats["dropped_degenerate"] += degen
        stats["dropped_excluded"] += excl
        if cleaned:
            valid_sf_items.append((img_p, cleaned))

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
                stats["instances"][dst_split][cid] += 1

    total_m = sum(stats["instances"][s][4] for s in ["train", "val", "test"])
    total_h = sum(stats["instances"][s][5] for s in ["train", "val", "test"])
    print(f"  -> Sunflower processed: {stats['images']} images | Sunflower_Moldy={total_m} | Sunflower_Not_Moldy={total_h} | Excluded={stats['dropped_excluded']}")
    return stats

def write_data_yaml():
    print("\n[7/7] Writing updated data.yaml...")
    yaml_content = {
        "path": str(COMBINED_DIR),
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
        yaml.dump(yaml_content, f, sort_keys=False)
    print("  -> Wrote data.yaml to", yaml_path)

if __name__ == "__main__":
    setup_dirs()
    process_corn_v4()
    process_corn_quality()
    process_corn_defects()
    process_peanut()
    process_sunflower()
    write_data_yaml()
    print("\n Full 5-source rebuild complete.")
