"""
Comprehensive inspection script for the 4 newly downloaded datasets in Downloads:
1. Corn Defects.v6i.yolov8
2. Sunflower_Seeds
3. corn_quality.v1-v1-corn_quality.yolov8
4. Groundnut Dataset of Three Grades
"""
import os
import sys
import json
import hashlib
from pathlib import Path
from PIL import Image
import cv2
import yaml

DOWNLOADS = Path(r"C:\Users\L E N O V O\Downloads")
COMBINED_DATASET = Path(r"C:\Users\L E N O V O\Food man\datasets\raw_materials_combined")

NEW_DATASETS = {
    "Corn Defects.v6i.yolov8": DOWNLOADS / "Corn Defects.v6i.yolov8",
    "Sunflower_Seeds": DOWNLOADS / "Sunflower_Seeds",
    "corn_quality.v1-v1-corn_quality.yolov8": DOWNLOADS / "corn_quality.v1-v1-corn_quality.yolov8",
    "Groundnut Dataset of Three Grades": DOWNLOADS / "Groundnut Dataset of Three Grades"
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def get_md5(filepath: Path) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def inspect_all_four():
    # Precompute hashes of existing combined dataset images for cross-duplicate checking
    existing_hashes = {}
    if COMBINED_DATASET.exists():
        for img_p in COMBINED_DATASET.rglob("*"):
            if img_p.is_file() and img_p.suffix.lower() in IMAGE_EXTS:
                try:
                    h = get_md5(img_p)
                    existing_hashes[h] = str(img_p.relative_to(COMBINED_DATASET))
                except Exception:
                    pass

    reports = {}

    for d_name, d_root in NEW_DATASETS.items():
        print(f"\n========================================================")
        print(f"Inspecting: {d_name}")
        print(f"Path: {d_root}")
        print(f"========================================================")

        report = {
            "name": d_name,
            "root_path": str(d_root),
            "exists": d_root.exists(),
            "has_data_yaml": False,
            "data_yaml_raw": None,
            "data_yaml_parsed": {},
            "class_map": {},
            "num_classes": 0,
            "dataset_type": "YOLO_OBJECT_DETECTION",  # or UNLABELED_IMAGES or CLASSIFICATION_GRADING
            "splits": {},
            "missing_or_empty_splits": [],
            "total_images": 0,
            "total_labels": 0,
            "class_box_counts": {},
            "class_images_containing": {},
            "corrupt_images": [],
            "missing_label_images": [],
            "unmatched_labels": [],
            "invalid_annotations": [],
            "internal_duplicates": [],
            "cross_duplicates_with_existing": [],
            "image_resolutions": set(),
            "extra_metadata": {}
        }

        if not d_root.exists():
            reports[d_name] = report
            continue

        # 1. Check data.yaml
        yaml_candidates = list(d_root.glob("*.yaml")) + list(d_root.glob("*.yml"))
        if yaml_candidates:
            yaml_file = yaml_candidates[0]
            report["has_data_yaml"] = True
            try:
                raw_text = yaml_file.read_text(encoding="utf-8")
                report["data_yaml_raw"] = raw_text
                parsed = yaml.safe_load(raw_text) or {}
                report["data_yaml_parsed"] = parsed
                names = parsed.get("names", [])
                if isinstance(names, dict):
                    report["class_map"] = {int(k): v for k, v in names.items()}
                elif isinstance(names, list):
                    report["class_map"] = {i: v for i, v in enumerate(names)}
                report["num_classes"] = len(report["class_map"])
            except Exception as e:
                report["data_yaml_raw"] = f"Error: {e}"

        # Initialize per-class counts
        for cid, cname in report["class_map"].items():
            report["class_box_counts"][cname] = 0
            report["class_images_containing"][cname] = 0

        # Determine type
        if not report["has_data_yaml"]:
            if d_name == "Sunflower_Seeds":
                report["dataset_type"] = "UNLABELED_OR_PREFIX_IMAGES"
            elif d_name == "Groundnut Dataset of Three Grades":
                report["dataset_type"] = "IMAGE_LEVEL_GRADING"
            else:
                report["dataset_type"] = "UNKNOWN_NON_YOLO"

        # 2. Check Splits for YOLO datasets
        seen_hashes = {}

        if report["dataset_type"] == "YOLO_OBJECT_DETECTION":
            expected_splits = ["train", "valid", "val", "test"]
            found_split_names = set()
            for s in ["train", "valid", "val", "test"]:
                if (d_root / s).exists():
                    found_split_names.add(s)

            # Standardize 'val' and 'valid'
            if "valid" in found_split_names:
                eval_splits = ["train", "valid", "test"]
            else:
                eval_splits = ["train", "val", "test"]

            for exp_s in ["train", "valid" if "valid" in found_split_names else "val", "test"]:
                s_dir = d_root / exp_s
                if not s_dir.exists():
                    report["missing_or_empty_splits"].append(f"Split directory '{exp_s}' is completely MISSING on disk")
                    continue

                img_dir = s_dir / "images" if (s_dir / "images").exists() else s_dir
                lbl_dir = s_dir / "labels" if (s_dir / "labels").exists() else s_dir

                img_files = sorted([f for f in img_dir.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS])
                lbl_files = sorted([f for f in lbl_dir.iterdir() if f.is_file() and f.suffix.lower() == ".txt"])

                if len(img_files) == 0:
                    report["missing_or_empty_splits"].append(f"Split directory '{exp_s}' has 0 images (EMPTY)")

                split_info = {
                    "split_name": exp_s,
                    "img_dir": str(img_dir.relative_to(d_root)),
                    "lbl_dir": str(lbl_dir.relative_to(d_root)),
                    "num_images": len(img_files),
                    "num_labels": len(lbl_files),
                    "class_box_counts": {c: 0 for c in report["class_map"].values()},
                    "class_images_containing": {c: 0 for c in report["class_map"].values()}
                }

                lbl_map = {f.stem: f for f in lbl_files}
                img_stems = set(f.stem for f in img_files)

                # Unmatched labels (label file exists without image)
                for lstem, lpath in lbl_map.items():
                    if lstem not in img_stems:
                        report["unmatched_labels"].append(str(lpath.relative_to(d_root)))

                # Inspect images in this split
                for img_p in img_files:
                    # Hash for internal & cross duplicates
                    try:
                        h = get_md5(img_p)
                        if h in seen_hashes:
                            report["internal_duplicates"].append({
                                "original": str(seen_hashes[h].relative_to(d_root)),
                                "duplicate": str(img_p.relative_to(d_root))
                            })
                        else:
                            seen_hashes[h] = img_p

                        if h in existing_hashes:
                            report["cross_duplicates_with_existing"].append({
                                "new_image": str(img_p.relative_to(d_root)),
                                "existing_dataset_image": existing_hashes[h]
                            })
                    except Exception as e:
                        pass

                    # Integrity check
                    try:
                        with Image.open(img_p) as im:
                            im.verify()
                            w, h_px = im.size
                            report["image_resolutions"].add(f"{w}x{h_px}")
                        # OpenCV decode check
                        mat = cv2.imread(str(img_p))
                        if mat is None:
                            report["corrupt_images"].append({"file": str(img_p.relative_to(d_root)), "reason": "OpenCV decode failed (returned None)"})
                    except Exception as e:
                        report["corrupt_images"].append({"file": str(img_p.relative_to(d_root)), "reason": str(e)})

                    # Label check
                    if img_p.stem not in lbl_map:
                        report["missing_label_images"].append(str(img_p.relative_to(d_root)))
                    else:
                        lbl_file = lbl_map[img_p.stem]
                        try:
                            lines = lbl_file.read_text(encoding="utf-8").strip().splitlines()
                            classes_in_this_image = set()
                            for line_no, line in enumerate(lines, 1):
                                parts = line.strip().split()
                                if not parts:
                                    continue
                                if len(parts) < 5:
                                    report["invalid_annotations"].append({
                                        "file": str(lbl_file.relative_to(d_root)),
                                        "line": line_no,
                                        "issue": f"Malformed line (< 5 tokens): '{line}'"
                                    })
                                    continue
                                try:
                                    cid = int(parts[0])
                                except ValueError:
                                    report["invalid_annotations"].append({
                                        "file": str(lbl_file.relative_to(d_root)),
                                        "line": line_no,
                                        "issue": f"Non-integer class ID '{parts[0]}'"
                                    })
                                    continue

                                if cid not in report["class_map"]:
                                    report["invalid_annotations"].append({
                                        "file": str(lbl_file.relative_to(d_root)),
                                        "line": line_no,
                                        "issue": f"Class ID {cid} not in data.yaml names ({report['class_map']})"
                                    })
                                    cname = f"Unknown_ID_{cid}"
                                else:
                                    cname = report["class_map"][cid]

                                # Coordinates bounds check
                                try:
                                    cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                                    if bw <= 0 or bh <= 0:
                                        report["invalid_annotations"].append({
                                            "file": str(lbl_file.relative_to(d_root)),
                                            "line": line_no,
                                            "issue": f"Zero or negative box dimension (w={bw}, h={bh})"
                                        })
                                    if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
                                        report["invalid_annotations"].append({
                                            "file": str(lbl_file.relative_to(d_root)),
                                            "line": line_no,
                                            "issue": f"Center coordinate outside [0, 1] (cx={cx}, cy={cy})"
                                        })
                                    if bw > 1.05 or bh > 1.05:
                                        report["invalid_annotations"].append({
                                            "file": str(lbl_file.relative_to(d_root)),
                                            "line": line_no,
                                            "issue": f"Box dimension suspiciously > 1.0 (w={bw}, h={bh})"
                                        })
                                except Exception as e:
                                    report["invalid_annotations"].append({
                                        "file": str(lbl_file.relative_to(d_root)),
                                        "line": line_no,
                                        "issue": f"Failed to parse coordinates: {e}"
                                    })

                                # Increment counts
                                report["class_box_counts"][cname] = report["class_box_counts"].get(cname, 0) + 1
                                split_info["class_box_counts"][cname] = split_info["class_box_counts"].get(cname, 0) + 1
                                classes_in_this_image.add(cname)

                            for cname in classes_in_this_image:
                                report["class_images_containing"][cname] = report["class_images_containing"].get(cname, 0) + 1
                                split_info["class_images_containing"][cname] = split_info["class_images_containing"].get(cname, 0) + 1

                        except Exception as e:
                            report["invalid_annotations"].append({
                                "file": str(lbl_file.relative_to(d_root)),
                                "line": 0,
                                "issue": f"Failed to read file: {e}"
                            })

                report["splits"][exp_s] = split_info
                report["total_images"] += split_info["num_images"]
                report["total_labels"] += split_info["num_labels"]

        elif d_name == "Sunflower_Seeds":
            # Inspect Sunflower_Seeds
            sub_folder = d_root / "Sunflower_Seeds"
            target_folder = sub_folder if sub_folder.exists() else d_root
            all_imgs = sorted([f for f in target_folder.glob("*") if f.is_file() and f.suffix.lower() in IMAGE_EXTS])
            report["total_images"] = len(all_imgs)
            report["missing_or_empty_splits"].append("No train/valid/test splits exist (Flat unpartitioned folder)")
            report["missing_or_empty_splits"].append("No YOLO annotations or data.yaml present in dataset")

            prefix_groups = {}
            for img_p in all_imgs:
                pre = img_p.name.split("_")[0] if "_" in img_p.name else "unprefixed"
                prefix_groups[pre] = prefix_groups.get(pre, 0) + 1

                # Hash
                h = get_md5(img_p)
                if h in seen_hashes:
                    report["internal_duplicates"].append({
                        "original": str(seen_hashes[h].relative_to(d_root)),
                        "duplicate": str(img_p.relative_to(d_root))
                    })
                else:
                    seen_hashes[h] = img_p

                if h in existing_hashes:
                    report["cross_duplicates_with_existing"].append({
                        "new_image": str(img_p.relative_to(d_root)),
                        "existing_dataset_image": existing_hashes[h]
                    })

                # Integrity
                try:
                    with Image.open(img_p) as im:
                        im.verify()
                        w, h_px = im.size
                        report["image_resolutions"].add(f"{w}x{h_px}")
                    mat = cv2.imread(str(img_p))
                    if mat is None:
                        report["corrupt_images"].append({"file": str(img_p.relative_to(d_root)), "reason": "OpenCV decode failed"})
                except Exception as e:
                    report["corrupt_images"].append({"file": str(img_p.relative_to(d_root)), "reason": str(e)})

            report["extra_metadata"]["prefix_distribution"] = prefix_groups
            report["extra_metadata"]["folder_scanned"] = str(target_folder.relative_to(d_root))

        elif d_name == "Groundnut Dataset of Three Grades":
            # Inspect Groundnut grades
            report["missing_or_empty_splits"].append("No train/valid/test splits exist (Grade-based directory organization)")
            report["missing_or_empty_splits"].append("No YOLO bounding box annotations or data.yaml present in dataset")

            grade_dirs = [d for d in (d_root / "Groundnut Dataset of Three Grades").iterdir() if d.is_dir()]
            grade_summary = {}

            for gdir in sorted(grade_dirs):
                g_imgs = sorted([f for f in gdir.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS])
                g_xlsx = sorted([f for f in gdir.iterdir() if f.is_file() and f.suffix.lower() == ".xlsx"])
                report["total_images"] += len(g_imgs)

                # Check excel weight rows
                weights = []
                for x in g_xlsx:
                    import zipfile
                    import xml.etree.ElementTree as ET
                    try:
                        with zipfile.ZipFile(x, "r") as z:
                            sheet_xml = z.read("xl/worksheets/sheet1.xml")
                            stree = ET.fromstring(sheet_xml)
                            rows = stree.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")
                            for r in rows[1:]:  # skip header
                                cells = r.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c")
                                if len(cells) >= 2:
                                    v = cells[1].find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                                    if v is not None and v.text:
                                        try:
                                            weights.append(float(v.text))
                                        except Exception:
                                            pass
                    except Exception as e:
                        pass

                avg_w = round(sum(weights) / len(weights), 2) if weights else None
                min_w = round(min(weights), 2) if weights else None
                max_w = round(max(weights), 2) if weights else None

                grade_summary[gdir.name] = {
                    "image_count": len(g_imgs),
                    "excel_files": [f.name for f in g_xlsx],
                    "weight_record_count": len(weights),
                    "avg_weight_gm": avg_w,
                    "weight_range_gm": f"{min_w} - {max_w}" if min_w is not None else "N/A"
                }

                # Check images
                for img_p in g_imgs:
                    h = get_md5(img_p)
                    if h in seen_hashes:
                        report["internal_duplicates"].append({
                            "original": str(seen_hashes[h].relative_to(d_root)),
                            "duplicate": str(img_p.relative_to(d_root))
                        })
                    else:
                        seen_hashes[h] = img_p

                    if h in existing_hashes:
                        report["cross_duplicates_with_existing"].append({
                            "new_image": str(img_p.relative_to(d_root)),
                            "existing_dataset_image": existing_hashes[h]
                        })

                    try:
                        with Image.open(img_p) as im:
                            im.verify()
                            w, h_px = im.size
                            report["image_resolutions"].add(f"{w}x{h_px}")
                        mat = cv2.imread(str(img_p))
                        if mat is None:
                            report["corrupt_images"].append({"file": str(img_p.relative_to(d_root)), "reason": "OpenCV decode failed"})
                    except Exception as e:
                        report["corrupt_images"].append({"file": str(img_p.relative_to(d_root)), "reason": str(e)})

            report["extra_metadata"]["grade_analysis"] = grade_summary

        report["image_resolutions"] = sorted(list(report["image_resolutions"]))
        reports[d_name] = report
        print(f"Done inspecting {d_name}. Total Images: {report['total_images']}, Total Labels: {report['total_labels']}")

    # Save full JSON output
    out_json = Path(r"C:\Users\L E N O V O\Food man\scratch\four_new_datasets_inspection.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)
    print(f"\nSaved full inspection JSON to {out_json}")


if __name__ == "__main__":
    inspect_all_four()
