"""
Side-by-Side Model Comparator: Epoch 10 vs Epoch 20
Compares detection counts, confidence scores, and visual bounding boxes
between models/combined_epoch10_backup.pt and models/combined_best.pt.
"""
import os
import sys
from pathlib import Path
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_EP10 = PROJECT_ROOT / "models" / "combined_epoch10_backup.pt"
MODEL_EP20 = PROJECT_ROOT / "models" / "combined_best.pt"
OUT_DIR = PROJECT_ROOT / "scratch" / "side_by_side_comparisons"

SAMPLE_IMAGES = {
    "peanut_cluster": PROJECT_ROOT / "datasets" / "raw_materials_combined" / "images" / "test" / "peanut_th_t8_jpg.rf.1b3ce486d9f00aa56dad9e4f957de4e6.jpg",
    "peanut_single": PROJECT_ROOT / "datasets" / "raw_materials_combined" / "images" / "test" / "peanut_aug_IMG20240607225203_jpg.rf.23998ad5bd1d0ee66d636d6fc899ae42.jpg",
    "corn_cluster": PROJECT_ROOT / "datasets" / "raw_materials_combined" / "images" / "test" / "corn_20220327_0107_jpg.rf.0902cfd33ed9e744116cdf33e7b66b09.jpg",
    "sunflower_cluster": PROJECT_ROOT / "datasets" / "raw_materials_combined" / "images" / "test" / "sunflower_20250731_112859_jpg.rf.d8df887ed52efabf39ad5f4638014aa8.jpg"
}

def compare_image(img_key: str, img_path: Path, m10, m20, conf: float = 0.12):
    if not img_path.exists():
        print(f"[SKIP] File not found: {img_path}")
        return None

    res10 = m10.predict(str(img_path), conf=conf, verbose=False)[0]
    res20 = m20.predict(str(img_path), conf=conf, verbose=False)[0]

    b10 = res10.boxes
    b20 = res20.boxes

    conf10 = [float(c) for c in b10.conf] if len(b10) else [0]
    conf20 = [float(c) for c in b20.conf] if len(b20) else [0]

    plot10 = res10.plot()
    plot20 = res20.plot()

    # Add header banners
    h, w, _ = plot10.shape
    banner_h = 45
    header10 = np.full((banner_h, w, 3), (40, 40, 40), dtype=np.uint8)
    header20 = np.full((banner_h, w, 3), (20, 80, 20), dtype=np.uint8)

    txt10 = f"Epoch 10 | Boxes: {len(b10)} | Mean Conf: {np.mean(conf10)*100:.1f}%"
    txt20 = f"Epoch 20 (NEW) | Boxes: {len(b20)} | Mean Conf: {np.mean(conf20)*100:.1f}%"

    cv2.putText(header10, txt10, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(header20, txt20, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    img10_labeled = np.vstack([header10, plot10])
    img20_labeled = np.vstack([header20, plot20])

    # Side by side canvas
    side_by_side = np.hstack([img10_labeled, img20_labeled])
    out_file = OUT_DIR / f"compare_{img_key}.jpg"
    cv2.imwrite(str(out_file), side_by_side)

    # Class breakdown
    names = res20.names
    def count_classes(boxes):
        counts = {}
        for b in boxes:
            cid = int(b.cls[0])
            cname = names.get(cid, str(cid))
            counts[cname] = counts.get(cname, 0) + 1
        return counts

    cls10 = count_classes(b10)
    cls20 = count_classes(b20)

    return {
        "key": img_key,
        "out_file": out_file,
        "ep10": {"count": len(b10), "mean_conf": float(np.mean(conf10)), "classes": cls10},
        "ep20": {"count": len(b20), "mean_conf": float(np.mean(conf20)), "classes": cls20}
    }

def main():
    print("=" * 80)
    print("SIDE-BY-SIDE MODEL COMPARISON TOOL: EPOCH 10 vs EPOCH 20")
    print("=" * 80)

    if not MODEL_EP10.exists() or not MODEL_EP20.exists():
        print(f"Error: Model weights missing. Check {MODEL_EP10} and {MODEL_EP20}")
        sys.exit(1)

    from ultralytics import YOLO
    print("Loading models into memory...")
    m10 = YOLO(str(MODEL_EP10))
    m20 = YOLO(str(MODEL_EP20))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for key, path in SAMPLE_IMAGES.items():
        print(f"\nRunning comparison on: {key} ({path.name})")
        res = compare_image(key, path, m10, m20)
        if res:
            e10 = res["ep10"]
            e20 = res["ep20"]
            print(f"  * Epoch 10: {e10['count']} detections, Avg Conf: {e10['mean_conf']*100:.1f}%, Classes: {e10['classes']}")
            print(f"  * Epoch 20: {e20['count']} detections, Avg Conf: {e20['mean_conf']*100:.1f}%, Classes: {e20['classes']}")
            print(f"  * Side-by-side visualization saved: {res['out_file']}")

    print("\n" + "=" * 80)
    print(f"All side-by-side comparison images saved to: {OUT_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()
