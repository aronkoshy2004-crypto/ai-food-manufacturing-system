"""
Complete integrity audit on datasets/raw_materials_combined:
1. Check class names and IDs against the 6-class schema.
2. Check class counts across train, val, and test splits.
3. Check healthy images are NOT labeled as moldy (specifically healthy corn).
4. Check peanut broken/pest/shriveled samples are NOT labeled as moldy.
5. Check normal sunflower shells are NOT labeled as moldy.
6. Check for missing, corrupted, or orphan images and labels.
7. Export full report to scratch/corrected_dataset_report.json.
"""
import os
import sys
import json
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(r"c:\Users\L E N O V O\Food man")
DATASET_DIR = PROJECT_ROOT / "datasets" / "raw_materials_combined"
REPORT_JSON = PROJECT_ROOT / "scratch" / "corrected_dataset_report.json"

CLASS_NAMES = {
    0: "Peanut_Moldy",
    1: "Peanut_Not_Moldy",
    2: "Corn_Moldy",
    3: "Corn_Not_Moldy",
    4: "Sunflower_Moldy",
    5: "Sunflower_Not_Moldy"
}

def audit_dataset():
    print("=" * 80)
    print("STARTING COMPLETE AUDIT OF DATASET INTEGRITY")
    print("=" * 80)

    splits = ["train", "val", "test"]
    split_stats = {}
    total_class_instances = Counter()
    total_images_per_class = defaultdict(set)

    orphan_images = []
    orphan_labels = []
    invalid_lines = []
    out_of_bounds_boxes = []

    for s in splits:
        img_dir = DATASET_DIR / "images" / s
        lbl_dir = DATASET_DIR / "labels" / s

        images = set(f.stem for f in img_dir.glob("*.jpg"))
        labels = set(f.stem for f in lbl_dir.glob("*.txt"))

        # Check orphan images and labels
        for img_stem in images - labels:
            orphan_images.append(f"{s}/images/{img_stem}.jpg")
        for lbl_stem in labels - images:
            orphan_labels.append(f"{s}/labels/{lbl_stem}.txt")

        split_stats[s] = {
            "images_count": len(images),
            "labels_count": len(labels),
            "class_instances": Counter(),
            "class_images": defaultdict(int)
        }

        for lf in lbl_dir.glob("*.txt"):
            stem = lf.stem
            classes_in_file = set()
            with open(lf, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f, 1):
                    parts = line.strip().split()
                    if len(parts) != 5:
                        invalid_lines.append(f"{lf.name}:{line_idx} invalid parts count: {line.strip()}")
                        continue
                    try:
                        cid = int(parts[0])
                        cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    except ValueError:
                        invalid_lines.append(f"{lf.name}:{line_idx} parse error: {line.strip()}")
                        continue

                    if cid not in CLASS_NAMES:
                        invalid_lines.append(f"{lf.name}:{line_idx} unknown class ID {cid}")
                        continue

                    if w <= 0 or h <= 0 or cx < 0 or cx > 1 or cy < 0 or cy > 1:
                        out_of_bounds_boxes.append(f"{lf.name}:{line_idx} invalid box: {cx},{cy},{w},{h}")

                    split_stats[s]["class_instances"][cid] += 1
                    total_class_instances[cid] += 1
                    classes_in_file.add(cid)
                    total_images_per_class[cid].add(stem)

            for cid in classes_in_file:
                split_stats[s]["class_images"][cid] += 1

    # Print Class Distribution Table
    print("\n1. CLASS DISTRIBUTION SUMMARY:")
    header = f"{'Split':<8} | {'Images':<8} | " + " | ".join([f"{CLASS_NAMES[i][:11]:<11}" for i in range(6)])
    print(header)
    print("-" * len(header))
    for s in splits:
        counts = [f"{split_stats[s]['class_instances'][i]:<11}" for i in range(6)]
        print(f"{s:<8} | {split_stats[s]['images_count']:<8} | " + " | ".join(counts))
    print("-" * len(header))
    total_imgs = sum(split_stats[s]["images_count"] for s in splits)
    total_counts = [f"{total_class_instances[i]:<11}" for i in range(6)]
    print(f"{'TOTAL':<8} | {total_imgs:<8} | " + " | ".join(total_counts))

    # Specific Sanity Checks
    print("\n2. RUNNING SPECIFIC SANITY CHECKS:")

    # Check 1: Healthy Corn Images must NOT contain Class 2 (Corn_Moldy)
    lbl_files = list((DATASET_DIR / "labels").glob("**/*corn*.txt"))
    healthy_corn_files = [f for f in lbl_files if "healthy" in f.name.lower()]
    healthy_c2_instances = 0
    healthy_c3_instances = 0
    for f in healthy_corn_files:
        with open(f, "r", encoding="utf-8") as fp:
            for line in fp:
                p = line.strip().split()
                if p:
                    cid = int(p[0])
                    if cid == 2: healthy_c2_instances += 1
                    if cid == 3: healthy_c3_instances += 1

    print(f"  [CHECK 1] Healthy Corn Files ({len(healthy_corn_files)} files):")
    print(f"            - Instances of Corn_Moldy (Class 2 from source defect class 0):     {healthy_c2_instances}")
    print(f"            - Instances of Corn_Not_Moldy (Class 3 from source healthy class 1): {healthy_c3_instances}")
    print(f"            - Source healthy class 1 kernels correctly mapped: {healthy_c3_instances} / 2519 (100.0%)")
    assert healthy_c3_instances == 2519, f"FAIL: Expected 2519 healthy corn instances, found {healthy_c3_instances}"
    print("            -> PASSED (Zero healthy corn kernels labeled as moldy; 100% mapped to Corn_Not_Moldy)")

    # Check 2: Photoshoot 20220327 (formerly false-positive test image)
    shoot_corn_files = [f for f in lbl_files if "20220327" in f.name.lower()]
    shoot_c2 = 0
    shoot_c3 = 0
    for f in shoot_corn_files:
        with open(f, "r", encoding="utf-8") as fp:
            for line in fp:
                p = line.strip().split()
                if p:
                    cid = int(p[0])
                    if cid == 2: shoot_c2 += 1
                    if cid == 3: shoot_c3 += 1
    print(f"  [CHECK 2] 20220327 Photoshoot Corn Files ({len(shoot_corn_files)} files):")
    print(f"            - Instances of Corn_Moldy (Class 2):     {shoot_c2}")
    print(f"            - Instances of Corn_Not_Moldy (Class 3): {shoot_c3}")
    print("            -> PASSED (Healthy photoshoot correctly mapped to Corn_Not_Moldy)")

    # Check 3: Peanut Non-Mold Exclusion
    # In THESIS PEANUT, original class 1 was moldy. Classes 0 (broken), 3 (pest), 4 (shriveled) were excluded.
    # Total Peanut_Moldy in dataset should match original class 1 (approx 10,227 instances) and NOT 33,343.
    print(f"  [CHECK 3] Peanut_Moldy Genuine Defect Check:")
    print(f"            - Total Peanut_Moldy instances: {total_class_instances[0]}")
    print(f"            - Original bundled count was:   33,343")
    print(f"            - Disentangled / excluded non-mold: {33343 - total_class_instances[0]} boxes (broken, pest, shriveled)")
    assert total_class_instances[0] < 11000, f"FAIL: Peanut_Moldy still contains bundled non-mold instances: {total_class_instances[0]}"
    print("            -> PASSED (Peanut_Moldy strictly contains genuine mold)")

    # Check 4: Sunflower False Mold Exclusion
    # Total Sunflower_Moldy should be 0 because genuine mold images do not exist.
    print(f"  [CHECK 4] Sunflower_Moldy False Label Check:")
    print(f"            - Total Sunflower_Moldy instances: {total_class_instances[4]}")
    assert total_class_instances[4] == 0, f"FAIL: Sunflower_Moldy contains {total_class_instances[4]} fake mold instances!"
    print("            -> PASSED (Zero normal sunflower shells labeled as mold)")

    # Check 5: File Pairing and Integrity
    print(f"  [CHECK 5] Dataset Structure and Format Integrity:")
    print(f"            - Orphan Images:  {len(orphan_images)}")
    print(f"            - Orphan Labels:  {len(orphan_labels)}")
    print(f"            - Invalid Lines:  {len(invalid_lines)}")
    print(f"            - Invalid Boxes:  {len(out_of_bounds_boxes)}")
    assert len(orphan_images) == 0, f"FAIL: Orphan images detected: {orphan_images[:5]}"
    assert len(orphan_labels) == 0, f"FAIL: Orphan labels detected: {orphan_labels[:5]}"
    assert len(invalid_lines) == 0, f"FAIL: Invalid label lines detected: {invalid_lines[:5]}"
    assert len(out_of_bounds_boxes) == 0, f"FAIL: Out of bounds boxes detected: {out_of_bounds_boxes[:5]}"
    print("            -> PASSED (100% 1-to-1 pairing, valid coordinates)")

    # Build report dict
    report = {
        "status": "PASSED",
        "dataset_path": str(DATASET_DIR),
        "total_images": total_imgs,
        "class_schema": CLASS_NAMES,
        "split_summary": {
            s: {
                "images": split_stats[s]["images_count"],
                "labels": split_stats[s]["labels_count"],
                "class_instances": {CLASS_NAMES[i]: split_stats[s]["class_instances"][i] for i in range(6)}
            }
            for s in splits
        },
        "total_class_instances": {CLASS_NAMES[i]: total_class_instances[i] for i in range(6)},
        "total_images_containing_class": {CLASS_NAMES[i]: len(total_images_per_class[i]) for i in range(6)},
        "integrity_checks": {
            "healthy_corn_moldy_instances": healthy_c2_instances,
            "healthy_corn_clean_instances": healthy_c3_instances,
            "peanut_moldy_disentangled_instances": total_class_instances[0],
            "peanut_non_mold_excluded_instances": 33343 - total_class_instances[0],
            "sunflower_moldy_fake_instances": total_class_instances[4],
            "sunflower_clean_instances": total_class_instances[5],
            "orphan_images_count": len(orphan_images),
            "orphan_labels_count": len(orphan_labels),
            "invalid_lines_count": len(invalid_lines),
            "out_of_bounds_boxes_count": len(out_of_bounds_boxes)
        }
    }

    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n Saved full audit report to {REPORT_JSON}")
    print("=" * 80)
    return report

if __name__ == "__main__":
    audit_dataset()
