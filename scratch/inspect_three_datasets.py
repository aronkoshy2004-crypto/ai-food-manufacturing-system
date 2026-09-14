"""
Comprehensive inspection script for the three raw material YOLO datasets:
1. THESIS PEANUT.v1i.yolov8
2. sunflower2.v19i.yolov8
3. corn.v4-corn_article.yolov8
"""
import os
import sys
import hashlib
import json
from pathlib import Path
from PIL import Image
import cv2
import yaml

DATASET_PATHS = {
    "Peanut": Path(r"C:\Users\L E N O V O\Downloads\THESIS PEANUT.v1i.yolov8"),
    "Sunflower": Path(r"C:\Users\L E N O V O\Downloads\sunflower2.v19i.yolov8"),
    "Corn": Path(r"C:\Users\L E N O V O\Downloads\corn.v4-corn_article.yolov8")
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

def compute_file_hash(filepath: Path) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def inspect_single_dataset(name: str, root_dir: Path) -> dict:
    report = {
        "name": name,
        "root_path": str(root_dir),
        "exists": root_dir.exists(),
        "folder_structure": [],
        "data_yaml_raw": "",
        "data_yaml_parsed": {},
        "splits": {},
        "total_images": 0,
        "total_labels": 0,
        "class_instance_counts": {},
        "corrupt_images": [],
        "missing_label_images": [],
        "unmatched_labels": [],
        "invalid_annotations": [],
        "duplicate_images_internal": [],
        "image_resolutions": set()
    }
    
    if not root_dir.exists():
        return report

    # 1. Folder structure
    for item in sorted(root_dir.rglob("*")):
        if item.is_dir():
            rel = item.relative_to(root_dir)
            if len(rel.parts) <= 3:
                report["folder_structure"].append(str(rel))

    # 2. data.yaml
    yaml_candidates = list(root_dir.glob("*.yaml")) + list(root_dir.glob("*.yml"))
    if yaml_candidates:
        yaml_file = yaml_candidates[0]
        try:
            raw_text = yaml_file.read_text(encoding="utf-8")
            report["data_yaml_raw"] = raw_text
            report["data_yaml_parsed"] = yaml.safe_load(raw_text) or {}
        except Exception as e:
            report["data_yaml_raw"] = f"Error reading yaml: {e}"

    classes = report["data_yaml_parsed"].get("names", [])
    if isinstance(classes, dict):
        class_map = classes
    elif isinstance(classes, list):
        class_map = {i: c for i, c in enumerate(classes)}
    else:
        class_map = {}
    
    report["class_map"] = class_map
    for cid in class_map:
        report["class_instance_counts"][class_map[cid]] = 0

    # 3. Splits & Files
    seen_hashes = {}
    
    # Identify splits present
    possible_splits = ["train", "valid", "val", "test"]
    found_splits = set()
    for s in possible_splits:
        if (root_dir / s).exists():
            found_splits.add(s)

    for split in sorted(found_splits):
        split_dir = root_dir / split
        # Check standard YOLO structure: split/images and split/labels or images/split and labels/split
        img_dir = split_dir / "images"
        if not img_dir.exists():
            img_dir = split_dir
        
        lbl_dir = split_dir / "labels"
        if not lbl_dir.exists():
            lbl_dir = split_dir

        img_files = [f for f in img_dir.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS] if img_dir.exists() else []
        lbl_files = [f for f in lbl_dir.iterdir() if f.is_file() and f.suffix.lower() == ".txt"] if lbl_dir.exists() else []

        split_info = {
            "img_dir": str(img_dir.relative_to(root_dir)),
            "lbl_dir": str(lbl_dir.relative_to(root_dir)),
            "num_images": len(img_files),
            "num_labels": len(lbl_files),
            "classes_in_split": {}
        }

        # Check images
        for img_p in img_files:
            # Hash check for duplicates
            h = compute_file_hash(img_p)
            if h in seen_hashes:
                report["duplicate_images_internal"].append({
                    "original": str(seen_hashes[h].relative_to(root_dir)),
                    "duplicate": str(img_p.relative_to(root_dir))
                })
            else:
                seen_hashes[h] = img_p

            # Corrupt image check
            try:
                with Image.open(img_p) as im:
                    im.verify()
                    w, h_px = im.size
                    report["image_resolutions"].add(f"{w}x{h_px}")
                # check opencv load
                mat = cv2.imread(str(img_p))
                if mat is None:
                    report["corrupt_images"].append((str(img_p.name), "OpenCV could not decode image"))
            except Exception as e:
                report["corrupt_images"].append((str(img_p.name), str(e)))

            # Corresponding label check
            expected_lbl = lbl_dir / (img_p.stem + ".txt")
            if not expected_lbl.exists():
                report["missing_label_images"].append(str(img_p.relative_to(root_dir)))
            else:
                # Validate YOLO annotation format
                try:
                    lines = expected_lbl.read_text(encoding="utf-8").strip().splitlines()
                    for line_idx, line in enumerate(lines, 1):
                        parts = line.strip().split()
                        if not parts:
                            continue
                        if len(parts) < 5:
                            report["invalid_annotations"].append({
                                "file": str(expected_lbl.relative_to(root_dir)),
                                "line": line_idx,
                                "issue": f"Expected >= 5 tokens, got {len(parts)}: '{line}'"
                            })
                            continue
                        cls_id_str = parts[0]
                        try:
                            cls_id = int(cls_id_str)
                        except ValueError:
                            report["invalid_annotations"].append({
                                "file": str(expected_lbl.relative_to(root_dir)),
                                "line": line_idx,
                                "issue": f"Invalid class id '{cls_id_str}'"
                            })
                            continue

                        if cls_id not in class_map:
                            report["invalid_annotations"].append({
                                "file": str(expected_lbl.relative_to(root_dir)),
                                "line": line_idx,
                                "issue": f"Class ID {cls_id} not defined in data.yaml names {list(class_map.keys())}"
                            })
                        else:
                            cname = class_map[cls_id]
                            report["class_instance_counts"][cname] = report["class_instance_counts"].get(cname, 0) + 1
                            split_info["classes_in_split"][cname] = split_info["classes_in_split"].get(cname, 0) + 1

                        # Check bounding box bounds [0, 1]
                        coords = [float(x) for x in parts[1:5]]
                        cx, cy, bw, bh = coords[0], coords[1], coords[2], coords[3]
                        if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
                            report["invalid_annotations"].append({
                                "file": str(expected_lbl.relative_to(root_dir)),
                                "line": line_idx,
                                "issue": f"Center ({cx}, {cy}) outside [0, 1]"
                            })
                        if bw <= 0 or bh <= 0 or bw > 1.05 or bh > 1.05:
                            report["invalid_annotations"].append({
                                "file": str(expected_lbl.relative_to(root_dir)),
                                "line": line_idx,
                                "issue": f"Invalid box dimensions (w={bw}, h={bh})"
                            })
                except Exception as e:
                    report["invalid_annotations"].append({
                        "file": str(expected_lbl.relative_to(root_dir)),
                        "line": 0,
                        "issue": f"Could not read/parse label file: {e}"
                    })

        report["splits"][split] = split_info
        report["total_images"] += split_info["num_images"]
        report["total_labels"] += split_info["num_labels"]

    # Convert sets to list for JSON serialization
    report["image_resolutions"] = sorted(list(report["image_resolutions"]))
    return report

def main():
    all_reports = {}
    for name, path in DATASET_PATHS.items():
        print(f"Inspecting {name} at {path}...")
        report = inspect_single_dataset(name, path)
        all_reports[name] = report

    # Cross-dataset duplicate check
    cross_duplicates = []
    hashes_by_dataset = {}
    for dname, r in all_reports.items():
        hashes_by_dataset[dname] = {}
        rpath = Path(r["root_path"])
        if rpath.exists():
            for f in rpath.rglob("*"):
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                    h = compute_file_hash(f)
                    hashes_by_dataset[dname][h] = str(f.relative_to(rpath))

    dnames = list(all_reports.keys())
    for i in range(len(dnames)):
        for j in range(i + 1, len(dnames)):
            d1, d2 = dnames[i], dnames[j]
            common = set(hashes_by_dataset[d1].keys()) & set(hashes_by_dataset[d2].keys())
            if common:
                cross_duplicates.append({
                    "datasets": (d1, d2),
                    "count": len(common),
                    "samples": [(hashes_by_dataset[d1][h], hashes_by_dataset[d2][h]) for h in list(common)[:3]]
                })

    summary = {
        "datasets": all_reports,
        "cross_dataset_duplicates": cross_duplicates
    }

    out_path = Path("scratch/datasets_inspection_report.json")
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Inspection complete! Saved to scratch/datasets_inspection_report.json")

if __name__ == "__main__":
    main()
