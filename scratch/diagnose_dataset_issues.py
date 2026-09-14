import os
import sys
import glob
import json
from collections import defaultdict, Counter
from pathlib import Path

PROJECT_ROOT = Path(r"c:\Users\L E N O V O\Food man")
DATASET_DIR = PROJECT_ROOT / "datasets" / "raw_materials_combined"

CLASS_NAMES = {
    0: "Peanut_Moldy",
    1: "Peanut_Not_Moldy",
    2: "Corn_Moldy",
    3: "Corn_Not_Moldy",
    4: "Sunflower_Moldy",
    5: "Sunflower_Not_Moldy"
}

def analyze_dataset_splits():
    print("=" * 80)
    print("1. DATASET SPLIT & CLASS BALANCE ANALYSIS (datasets/raw_materials_combined)")
    print("=" * 80)
    
    splits = ["train", "val", "test"]
    stats = {
        s: {
            "image_count": 0,
            "label_count": 0,
            "class_instances": Counter(),
            "images_per_class": defaultdict(set)
        }
        for s in splits
    }
    
    total_class_instances = Counter()
    total_images_per_class = defaultdict(set)
    
    for s in splits:
        img_dir = DATASET_DIR / "images" / s
        lbl_dir = DATASET_DIR / "labels" / s
        
        images = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png"))
        stats[s]["image_count"] = len(images)
        
        for lf in lbl_dir.glob("*.txt"):
            stats[s]["label_count"] += 1
            img_stem = lf.stem
            with open(lf, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts and parts[0].isdigit():
                        cid = int(parts[0])
                        stats[s]["class_instances"][cid] += 1
                        stats[s]["images_per_class"][cid].add(img_stem)
                        total_class_instances[cid] += 1
                        total_images_per_class[cid].add(img_stem)

    print(f"{'Split':<8} | {'Images':<8} | {'Labels':<8} | " + " | ".join([f"{CLASS_NAMES[i][:11]:<11}" for i in range(6)]))
    print("-" * 95)
    for s in splits:
        counts = [f"{stats[s]['class_instances'][i]:<11}" for i in range(6)]
        print(f"{s:<8} | {stats[s]['image_count']:<8} | {stats[s]['label_count']:<8} | " + " | ".join(counts))
    print("-" * 95)
    total_counts = [f"{total_class_instances[i]:<11}" for i in range(6)]
    total_images = sum(stats[s]["image_count"] for s in splits)
    print(f"{'TOTAL':<8} | {total_images:<8} | {'-':<8} | " + " | ".join(total_counts))
    
    print("\nTotal Unique Images Containing Each Class:")
    for cid in range(6):
        print(f"  Class {cid} ({CLASS_NAMES[cid]}): {len(total_images_per_class[cid])} images, {total_class_instances[cid]} bounding boxes")

    print("\nPairwise Class Balance (Moldy vs Not_Moldy):")
    p_ratio = total_class_instances[0] / max(1, total_class_instances[1])
    c_ratio = total_class_instances[2] / max(1, total_class_instances[3])
    s_ratio = total_class_instances[4] / max(1, total_class_instances[5])
    print(f"  Peanut:    Moldy={total_class_instances[0]:<6} vs Not_Moldy={total_class_instances[1]:<6} (Ratio: {p_ratio:.2f}:1)")
    print(f"  Corn:      Moldy={total_class_instances[2]:<6} vs Not_Moldy={total_class_instances[3]:<6} (Ratio: {c_ratio:.2f}:1)")
    print(f"  Sunflower: Moldy={total_class_instances[4]:<6} vs Not_Moldy={total_class_instances[5]:<6} (Ratio: {s_ratio:.2f}:1)")
    
    return stats, total_class_instances

def analyze_corn_healthy_anomaly():
    print("\n" + "=" * 80)
    print("2. DEEP DIVE: WHY HEALTHY CORN WAS LABELED / DETECTED AS CORN_MOLDY")
    print("=" * 80)
    
    lbl_dir = DATASET_DIR / "labels"
    all_corn_files = list(lbl_dir.glob("**/*corn*.txt"))
    
    healthy_files = [f for f in all_corn_files if "healthy" in f.name.lower()]
    fusarium_files = [f for f in all_corn_files if "fusarium" in f.name.lower()]
    cq_files = [f for f in all_corn_files if "corn_cq_" in f.name.lower()]
    orig_corn_files = [f for f in all_corn_files if "corn_cq_" not in f.name.lower()]

    print(f"Total Corn Label Files: {len(all_corn_files)}")
    print(f"  - Files containing 'healthy':  {len(healthy_files)}")
    print(f"  - Files containing 'fusarium': {len(fusarium_files)}")
    print(f"  - Files with 'corn_cq_' (new corn quality dataset): {len(cq_files)}")
    print(f"  - Files from original corn.v4 dataset: {len(orig_corn_files)}")
    
    def count_classes_in_files(file_list):
        c = Counter()
        for f in file_list:
            with open(f, "r", encoding="utf-8") as fp:
                for line in fp:
                    p = line.strip().split()
                    if p and p[0].isdigit():
                        c[int(p[0])] += 1
        return c

    healthy_classes = count_classes_in_files(healthy_files)
    fusarium_classes = count_classes_in_files(fusarium_files)
    cq_classes = count_classes_in_files(cq_files)
    
    print("\nClass distribution in filenames containing 'healthy':")
    for cid in range(6):
        if healthy_classes[cid] > 0:
            print(f"  Class {cid} ({CLASS_NAMES[cid]}): {healthy_classes[cid]} instances")
            
    print("\nClass distribution in filenames containing 'fusarium' (fungal disease):")
    for cid in range(6):
        if fusarium_classes[cid] > 0:
            print(f"  Class {cid} ({CLASS_NAMES[cid]}): {fusarium_classes[cid]} instances")
            
    print("\nClass distribution in 'corn_cq_' (corn_quality dataset):")
    for cid in range(6):
        if cq_classes[cid] > 0:
            print(f"  Class {cid} ({CLASS_NAMES[cid]}): {cq_classes[cid]} instances")

def analyze_peanut_and_sunflower():
    print("\n" + "=" * 80)
    print("3. ANALYSIS OF PEANUT AND SUNFLOWER CLASSES FOR SIMILAR ISSUES")
    print("=" * 80)
    
    lbl_dir = DATASET_DIR / "labels"
    all_peanut = list(lbl_dir.glob("**/*peanut*.txt"))
    all_sunflower = list(lbl_dir.glob("**/*sunflower*.txt"))
    
    # Peanut Thesis vs Peanut Augmented
    p_thesis = [f for f in all_peanut if "peanut_th_" in f.name]
    p_aug = [f for f in all_peanut if "peanut_aug_" in f.name]
    
    def count_c(file_list):
        c = Counter()
        for f in file_list:
            with open(f, "r", encoding="utf-8") as fp:
                for line in fp:
                    p = line.strip().split()
                    if p and p[0].isdigit():
                        c[int(p[0])] += 1
        return c

    pt_counts = count_c(p_thesis)
    pa_counts = count_c(p_aug)
    sf_counts = count_c(all_sunflower)
    
    print(f"Peanut Files: {len(all_peanut)} total ({len(p_thesis)} thesis, {len(p_aug)} augmented)")
    print("  Peanut Thesis instances:    " + ", ".join([f"{CLASS_NAMES[k]}: {v}" for k, v in pt_counts.items()]))
    print("  Peanut Augmented instances: " + ", ".join([f"{CLASS_NAMES[k]}: {v}" for k, v in pa_counts.items()]))
    print(f"\nSunflower Files: {len(all_sunflower)} total")
    print("  Sunflower instances:        " + ", ".join([f"{CLASS_NAMES[k]}: {v}" for k, v in sf_counts.items()]))

def analyze_confusion_matrix_data():
    print("\n" + "=" * 80)
    print("4. CONFUSION MATRIX & VALIDATION PERFORMANCE DATA")
    print("=" * 80)
    eval_json = PROJECT_ROOT / "scratch" / "combined_epoch50_evaluation.json"
    if eval_json.exists():
        with open(eval_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        print("Test Evaluation Summary (293 images):")
        for cls_item in data.get("per_class_epoch50", []):
            print(f"  {cls_item['class_name']:<20}: P={cls_item['precision']*100:5.2f}% | R={cls_item['recall']*100:5.2f}% | mAP50={cls_item['mAP50']*100:5.2f}% | mAP50-95={cls_item['mAP50_95']*100:5.2f}%")

if __name__ == "__main__":
    analyze_dataset_splits()
    analyze_corn_healthy_anomaly()
    analyze_peanut_and_sunflower()
    analyze_confusion_matrix_data()
