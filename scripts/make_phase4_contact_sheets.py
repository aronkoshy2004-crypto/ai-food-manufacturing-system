"""
Phase 4 Verification: Re-run Material Classifier on Phase 0 Live Frames
Generates comparison contact sheets showing Old vs New predicted material per frame.
"""
import os
import sys
import time
import shutil
from collections import defaultdict, Counter
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.yolo_service import run_yolo_visual_inspection, find_trained_model
from routes.qc import extract_material_name, get_mostly_detected_material
from scripts.eval_material import collect_from_saved_live_frames
from ultralytics import YOLO


ARTIFACT_DIR = r"C:\Users\L E N O V O\.gemini\antigravity-ide\brain\07a95aab-ec1c-4721-acec-0e1f33f6e3b6"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "datasets_synth", "live_review")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def classify_frame_with_cls(img: np.ndarray, yolo_res: dict, cls_model: YOLO) -> tuple:
    """
    Classifies a frame using the Phase 3 material classifier on all detected kernel crops.
    Returns (predicted_material, agreement_pct, kernel_count)
    """
    H, W = img.shape[:2]
    boxes = []

    for d in yolo_res.get("detected_defects", []):
        boxes.append(d)
    for h in yolo_res.get("detected_healthy", []):
        boxes.append(h)

    crops = []
    for b in boxes:
        bx = float(b.get("x_pct", 0.0)) / 100.0
        by = float(b.get("y_pct", 0.0)) / 100.0
        bw = float(b.get("w_pct", 0.0)) / 100.0
        bh = float(b.get("h_pct", 0.0)) / 100.0

        x1 = max(0, int(round(bx * W)))
        y1 = max(0, int(round(by * H)))
        x2 = min(W, int(round((bx + bw) * W)))
        y2 = min(H, int(round((by + bh) * H)))

        if x2 <= x1 or y2 <= y1:
            continue

        pad_w = int((x2 - x1) * 0.08)
        pad_h = int((y2 - y1) * 0.08)
        cx1 = max(0, x1 - pad_w)
        cy1 = max(0, y1 - pad_h)
        cx2 = min(W, x2 + pad_w)
        cy2 = min(H, y2 + pad_h)

        crop = img[cy1:cy2, cx1:cx2]
        if crop.size > 0 and crop.shape[0] >= 6 and crop.shape[1] >= 6:
            crops.append(crop)

    # If YOLO didn't detect kernel boxes (e.g. dense clusters where detector failed),
    # take sample center/grid crops across the frame to evaluate
    if not crops:
        ch, cw = int(H * 0.35), int(W * 0.35)
        crops = [
            img[int(H*0.1):int(H*0.1)+ch, int(W*0.1):int(W*0.1)+cw],
            img[int(H*0.1):int(H*0.1)+ch, int(W*0.5):int(W*0.5)+cw],
            img[int(H*0.5):int(H*0.5)+ch, int(W*0.1):int(W*0.1)+cw],
            img[int(H*0.5):int(H*0.5)+ch, int(W*0.5):int(W*0.5)+cw],
            img[int(H*0.3):int(H*0.3)+ch, int(W*0.3):int(W*0.3)+cw],
        ]

    weighted_votes = defaultdict(float)
    total_weight = 0.0

    cls_names = cls_model.names
    for crop in crops:
        rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        res = cls_model(rgb_crop, verbose=False)[0]
        top1_idx = int(res.probs.top1)
        top1_conf = float(res.probs.top1conf)
        raw_name = cls_names.get(top1_idx, "")
        mat_name = extract_material_name(raw_name) or raw_name.capitalize()
        weighted_votes[mat_name] += top1_conf
        total_weight += top1_conf

    if total_weight > 0:
        winner = max(weighted_votes, key=weighted_votes.get)
        agreement = int(round((weighted_votes[winner] / total_weight) * 100))
        return winner, agreement, len(crops)

    return "Unknown", 0, 0


def create_frame_tile(img_path: str, true_mat: str, old_pred: str, new_pred: str, new_conf: int, tile_size: int = 300) -> np.ndarray:
    """Renders a single labeled comparison tile."""
    img = cv2.imread(img_path)
    if img is None:
        img = np.zeros((tile_size, tile_size, 3), dtype=np.uint8)
    else:
        h, w = img.shape[:2]
        scale = min((tile_size - 70) / float(h), tile_size / float(w))
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
        
        canvas = np.zeros((tile_size, tile_size, 3), dtype=np.uint8)
        y_off = (tile_size - 70 - nh) // 2
        x_off = (tile_size - nw) // 2
        canvas[y_off:y_off+nh, x_off:x_off+nw] = resized
        img = canvas

    banner_y1 = tile_size - 70
    img[banner_y1:, :] = (25, 25, 25)

    cv2.line(img, (0, banner_y1), (tile_size, banner_y1), (60, 60, 60), 1)

    COLOR_GREEN = (60, 200, 60)
    COLOR_RED = (60, 60, 230)
    COLOR_WHITE = (240, 240, 240)

    old_ok = (old_pred.lower() == true_mat.lower())
    new_ok = (new_pred.lower() == true_mat.lower())

    old_color = COLOR_GREEN if old_ok else COLOR_RED
    new_color = COLOR_GREEN if new_ok else COLOR_RED

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.40
    thick = 1

    cv2.putText(img, f"True: {true_mat}", (8, banner_y1 + 18), font, font_scale, COLOR_WHITE, thick, cv2.LINE_AA)

    cv2.putText(img, f"Old: {old_pred[:14]}", (8, banner_y1 + 38), font, font_scale, old_color, thick, cv2.LINE_AA)
    cv2.putText(img, "[PASS]" if old_ok else "[FAIL]", (tile_size - 52, banner_y1 + 38), font, 0.35, old_color, thick, cv2.LINE_AA)

    cv2.putText(img, f"New: {new_pred[:10]} ({new_conf}%)", (8, banner_y1 + 58), font, font_scale, new_color, thick, cv2.LINE_AA)
    cv2.putText(img, "[PASS]" if new_ok else "[FAIL]", (tile_size - 52, banner_y1 + 58), font, 0.35, new_color, thick, cv2.LINE_AA)

    border_color = (0, 160, 0) if new_ok else (0, 0, 180)
    cv2.rectangle(img, (0, 0), (tile_size - 1, tile_size - 1), border_color, 2)

    return img


def build_contact_sheet(tiles: list, sheet_title: str, cols: int = 5) -> np.ndarray:
    """Builds a contact sheet grid with a title header."""
    if not tiles:
        return None

    tile_h, tile_w = tiles[0].shape[:2]
    n_tiles = len(tiles)
    rows = (n_tiles + cols - 1) // cols

    header_h = 60
    sheet_w = cols * tile_w
    sheet_h = header_h + rows * tile_h

    sheet = np.full((sheet_h, sheet_w, 3), (20, 20, 20), dtype=np.uint8)

    cv2.putText(sheet, sheet_title, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)

    for idx, tile in enumerate(tiles):
        r = idx // cols
        c = idx % cols
        y1 = header_h + r * tile_h
        y2 = y1 + tile_h
        x1 = c * tile_w
        x2 = x1 + tile_w
        sheet[y1:y2, x1:x2] = tile

    return sheet


def run_phase4_verification():
    print("=" * 70)
    print("PHASE 4: LIVE REVIEW FRAMES RE-EVALUATION & CONTACT SHEETS")
    print("=" * 70)

    model_path, model_name = find_trained_model()
    print(f"Base Detector Model:   {model_name} ({model_path})")

    cls_model_path = os.path.join(PROJECT_ROOT, "models", "material_cls.pt")
    if not os.path.isfile(cls_model_path):
        raise FileNotFoundError(f"Material classifier not found at {cls_model_path}")
    print(f"Material Classifier:   {cls_model_path}")
    cls_model = YOLO(cls_model_path)

    items = collect_from_saved_live_frames()
    print(f"\nCollected {len(items)} saved live review frames from Phase 0.")

    eval_records = []
    start_time = time.time()

    old_correct_by_mat = Counter()
    new_correct_by_mat = Counter()
    total_by_mat = Counter()

    for idx, item in enumerate(items, 1):
        img_path = item["path"]
        true_mat = item["true_material"]
        total_by_mat[true_mat] += 1

        img = cv2.imread(img_path)
        if img is None:
            continue

        # 1. Old Phase 0 Pipeline (Detector voting)
        yolo_res = run_yolo_visual_inspection(img_path)
        old_pred = get_mostly_detected_material(yolo_res) or "None / Undetected"
        if old_pred.lower() == true_mat.lower():
            old_correct_by_mat[true_mat] += 1

        # 2. New Phase 3/4 Pipeline (Material Classifier on kernel crops)
        new_pred, new_conf, kernel_cnt = classify_frame_with_cls(img, yolo_res, cls_model)
        if new_pred.lower() == true_mat.lower():
            new_correct_by_mat[true_mat] += 1

        eval_records.append({
            "idx": idx,
            "path": img_path,
            "filename": os.path.basename(img_path),
            "true_material": true_mat,
            "old_pred": old_pred,
            "old_ok": (old_pred.lower() == true_mat.lower()),
            "new_pred": new_pred,
            "new_conf": new_conf,
            "kernel_cnt": kernel_cnt,
            "new_ok": (new_pred.lower() == true_mat.lower())
        })

        if idx % 50 == 0 or idx == len(items):
            print(f"  Processed {idx}/{len(items)} live frames ({time.time() - start_time:.1f}s)...")

    by_mat = defaultdict(list)
    for rec in eval_records:
        by_mat[rec["true_material"]].append(rec)

    sheet_paths = []
    print("\nGenerating contact sheets...")

    chunk_size = 20
    for mat in ["Peanut", "Corn", "Sunflower"]:
        recs = by_mat.get(mat, [])
        if not recs:
            continue

        for chunk_i in range(0, len(recs), chunk_size):
            chunk = recs[chunk_i:chunk_i + chunk_size]
            tiles = []
            for r in chunk:
                tile = create_frame_tile(r["path"], r["true_material"], r["old_pred"], r["new_pred"], r["new_conf"])
                tiles.append(tile)

            part_num = (chunk_i // chunk_size) + 1
            title = f"Phase 4 Live Review: {mat} (Part {part_num}) - Old vs New Classifier"
            sheet = build_contact_sheet(tiles, title, cols=5)

            sheet_fname = f"live_review_contact_{mat.lower()}_p{part_num}.jpg"
            disk_save_path = os.path.join(OUTPUT_DIR, sheet_fname)
            cv2.imwrite(disk_save_path, sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])

            art_save_path = os.path.join(ARTIFACT_DIR, sheet_fname)
            shutil.copyfile(disk_save_path, art_save_path)

            sheet_paths.append((sheet_fname, disk_save_path, art_save_path))
            print(f"  Saved contact sheet: {disk_save_path} ({len(chunk)} frames)")

    print("\n" + "=" * 70)
    print("LIVE FRAMES COMPARISON: OLD (PHASE 0) VS NEW (PHASE 4 CLASSIFIER)")
    print("=" * 70)
    print(f"{'Material':<14} | {'Total':<6} | {'Old Correct':<12} | {'Old Acc':<10} | {'New Correct':<12} | {'New Acc':<10} | {'Gain':<8}")
    print("-" * 70)

    total_all = len(eval_records)
    total_old = sum(old_correct_by_mat.values())
    total_new = sum(new_correct_by_mat.values())

    for mat in sorted(total_by_mat.keys()):
        tot = total_by_mat[mat]
        oc = old_correct_by_mat[mat]
        nc = new_correct_by_mat[mat]
        o_acc = (oc / tot * 100.0) if tot > 0 else 0.0
        n_acc = (nc / tot * 100.0) if tot > 0 else 0.0
        gain = n_acc - o_acc
        print(f"{mat:<14} | {tot:<6} | {oc:<12} | {o_acc:>8.2f}% | {nc:<12} | {n_acc:>8.2f}% | {gain:>+7.2f}%")

    print("-" * 70)
    overall_o_acc = (total_old / total_all * 100.0) if total_all > 0 else 0.0
    overall_n_acc = (total_new / total_all * 100.0) if total_all > 0 else 0.0
    overall_gain = overall_n_acc - overall_o_acc
    print(f"{'OVERALL':<14} | {total_all:<6} | {total_old:<12} | {overall_o_acc:>8.2f}% | {total_new:<12} | {overall_n_acc:>8.2f}% | {overall_gain:>+7.2f}%")
    print("=" * 70)

    return eval_records, sheet_paths


if __name__ == "__main__":
    run_phase4_verification()
