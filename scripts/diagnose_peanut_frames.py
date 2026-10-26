import os
import sys
import json
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.yolo_service import run_yolo_visual_inspection
from ai.classical_kernel_finder import find_kernels_classical, estimate_paper_color_lab, is_center_in_ignore_zones
from config import Config

def diagnose_frames():
    debug_dir = os.path.join(PROJECT_ROOT, 'static', 'uploads', 'live_frames', 'debug')
    os.makedirs(debug_dir, exist_ok=True)

    # 1. Select the last 10 saved peanut frames
    # Real camera peanut specimens
    real_frames = [
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'raw', '20261017_064108_test_peanut.jpg'),
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'raw', '20261017_055631_test_peanut.jpg'),
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'raw', '20261017_035810_test_peanut.jpg'),
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'raw', '20261017_032908_peanut_test.jpg'),
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'raw', '20260910_073039_healthy_peanut_specimen.jpg'),
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'raw', '20260910_073039_bulk_peanut_cluster_o2.jpg'),
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'raw', '20260910_065924_isolated_single_peanut.jpg'),
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'raw', '20260910_065924_bulk_peanut_tray.jpg'),
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'live_frames', 'raw', 'sim_294_f0_peanut.jpg'),
        os.path.join(PROJECT_ROOT, 'static', 'uploads', 'live_frames', 'raw', 'sim_294_f1_peanut.jpg')
    ]

    ignore_zones = [{"x": 0.0, "y": 0.82, "w": 0.22, "h": 0.18}]

    print("=" * 90)
    print("DIAGNOSIS ON LAST 10 SAVED PEANUT FRAMES")
    print("=" * 90)

    results = []

    for idx, fpath in enumerate(real_frames):
        bname = os.path.basename(fpath)
        print(f"\n[{idx+1}/10] Frame: {bname}")
        img = cv2.imread(fpath)
        if img is None:
            print("  [ERROR] Could not load image file!")
            continue

        H, W = img.shape[:2]

        # a) AI detector with Product=Auto, ENGINE=ai
        y_auto = run_yolo_visual_inspection(fpath)
        all_def = y_auto.get("detected_defects", [])
        all_hlth = y_auto.get("detected_healthy", [])
        auto_boxes = all_def + all_hlth
        # Filter ignore zone
        auto_valid = [
            b for b in auto_boxes
            if not is_center_in_ignore_zones(
                (float(b.get("bbox_x", 0.0)) + float(b.get("bbox_w", 0.0)) / 2.0) / 100.0,
                (float(b.get("bbox_y", 0.0)) + float(b.get("bbox_h", 0.0)) / 2.0) / 100.0,
                ignore_zones
            )
        ]

        # b) AI detector with Product=Peanut (classes restricted)
        peanut_valid = [
            b for b in auto_valid
            if "peanut" in (b.get("specimen_class") or b.get("defect_class") or "").lower()
        ]

        # c) ENGINE=colour: Classical kernel finder
        c_res = find_kernels_classical(fpath, ignore_zones=ignore_zones, material="Peanut")
        c_kernels = c_res.get("kernels", [])
        c_count = len(c_kernels)

        # Diagnose reasons for any drop in colour engine
        # Let's inspect raw contours before filtering
        bg_L, paper_ab, bg_a, bg_b = estimate_paper_color_lab(img, ignore_zones)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        d_L = np.maximum(0.0, bg_L - lab[:, :, 0])
        d_a = np.abs(lab[:, :, 1] - bg_a)
        d_b = np.abs(lab[:, :, 2] - bg_b)
        color_dist = np.sqrt(d_L ** 2 + d_a ** 2 + d_b ** 2)
        m = color_dist.max()
        dist_8u = np.uint8(np.clip(color_dist * (255.0 / max(1.0, m)), 0, 255))
        otsu_val, thresh = cv2.threshold(dist_8u, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        k_size = max(3, int(min(H, W) * 0.005)) | 1
        morph_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, morph_k)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, morph_k)
        raw_cnts, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        dropped_ignore_zone = 0
        dropped_area_small = 0
        dropped_area_large = 0
        dropped_solidity = 0
        dropped_aspect = 0

        for c in raw_cnts:
            ca = cv2.contourArea(c)
            if ca < 150:
                dropped_area_small += 1
                continue
            rx, ry, rw, rh = cv2.boundingRect(c)
            rcx = (rx + rw / 2.0) / float(W)
            rcy = (ry + rh / 2.0) / float(H)
            if is_center_in_ignore_zones(rcx, rcy, ignore_zones):
                dropped_ignore_zone += 1
                continue
            apct = (ca / float(H * W)) * 100.0
            if apct < 0.08:
                dropped_area_small += 1
            elif apct > 6.0:
                dropped_area_large += 1
            hull = cv2.convexHull(c)
            ha = cv2.contourArea(hull)
            sol = float(ca / ha) if ha > 0 else 0.0
            if sol < 0.70:
                dropped_solidity += 1
            ar = float(max(rw, rh)) / max(1.0, float(min(rw, rh)))
            if ar > 3.6:
                dropped_aspect += 1

        # Save debug image if colour finds nothing
        debug_img_saved = None
        if c_count == 0:
            debug_fname = f"debug_empty_{bname}"
            debug_path = os.path.join(debug_dir, debug_fname)
            # Create side-by-side debug visualization: [Original BGR | Distance Map | Threshold Mask]
            dist_vis = cv2.cvtColor(dist_8u, cv2.COLOR_GRAY2BGR)
            thresh_vis = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
            debug_vis = np.hstack([cv2.resize(img, (400, 400)), cv2.resize(dist_vis, (400, 400)), cv2.resize(thresh_vis, (400, 400))])
            cv2.imwrite(debug_path, debug_vis)
            debug_img_saved = f"/static/uploads/live_frames/debug/{debug_fname}"

        # d) ENGINE=both:
        # Colour as primary, AI as second opinion
        both_count = c_count
        both_uncertain = 0
        if c_count == 0 and len(peanut_valid) > 0:
            both_status = "0 kernels from colour (AI found " + str(len(peanut_valid)) + ")"
        else:
            both_status = f"{c_count} colour kernels"

        print(f"  a) AI (Product=Auto, Engine=ai):      {len(auto_valid)} detections ({len(all_hlth)} healthy, {len(all_def)} defect)")
        print(f"  b) AI (Product=Peanut, Engine=ai):    {len(peanut_valid)} peanut detections")
        print(f"  c) Colour (Engine=colour):            {c_count} kernels found")
        print(f"     [Drop Reasons] Raw contours={len(raw_cnts)} | DropLargeArea(>6%)={dropped_area_large} | DropSmallArea(<0.08%)={dropped_area_small} | DropIgnoreZone={dropped_ignore_zone} | DropSolidity={dropped_solidity} | DropAspect={dropped_aspect}")
        print(f"  d) Both (Engine=both):                {both_status}")
        if debug_img_saved:
            print(f"     [DEBUG IMAGE SAVED]: {debug_img_saved}")

        results.append({
            "filename": bname,
            "ai_auto_count": len(auto_valid),
            "ai_peanut_count": len(peanut_valid),
            "colour_count": c_count,
            "raw_contours": len(raw_cnts),
            "drop_large_area": dropped_area_large,
            "drop_small_area": dropped_area_small,
            "drop_ignore_zone": dropped_ignore_zone,
            "drop_solidity": dropped_solidity,
            "drop_aspect": dropped_aspect,
            "both_status": both_status,
            "debug_image": debug_img_saved
        })

    return results

if __name__ == '__main__':
    diagnose_frames()
