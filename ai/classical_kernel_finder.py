"""
Classical Kernel Finder (OpenCV, No AI)
PRD Visual Quality Inspection - Colour Screening Engine

Estimates paper background colour in CIE Lab space, thresholds by colour distance (Otsu),
cleans with morphology, splits touching kernels via distance-transform watershed,
filters by area range, solidity, aspect ratio, and drops blobs in configured ignore zones.
"""
import os
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional


DEFAULT_IGNORE_ZONES = [
    {"x": 0.0, "y": 0.82, "w": 0.22, "h": 0.18} # Bottom-left 22% wide by 18% high (watermark / logo)
]


def is_center_in_ignore_zones(cx: float, cy: float, ignore_zones: List[Dict]) -> bool:
    """
    Checks if a normalized point (cx, cy) in [0, 1] falls inside any ignore zone.
    zone format: {"x": 0.0, "y": 0.82, "w": 0.22, "h": 0.18}
    """
    if not ignore_zones:
        return False
    for z in ignore_zones:
        zx = float(z.get("x", 0.0))
        zy = float(z.get("y", 0.0))
        zw = float(z.get("w", 0.0))
        zh = float(z.get("h", 0.0))
        if zx <= cx <= (zx + zw) and zy <= cy <= (zy + zh):
            return True
    return False


def estimate_paper_color_lab(img_bgr: np.ndarray, ignore_zones: List[Dict] = None):
    """
    Estimates the paper background illumination surface and chromaticity in Lab colour space.
    Switches to local background estimation via morphological closing (to remove dark kernels)
    and smooth Gaussian blurring to model lens vignetting and lighting gradients across the frame.
    Returns:
        bg_L: 2D float32 array of local lightness field
        paper_ab: 1D float32 array [a_med, b_med] representing paper chromaticity
        bg_a: 2D float32 array of local a-chromaticity field
        bg_b: 2D float32 array of local b-chromaticity field
    """
    H, W = img_bgr.shape[:2]
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

    # Structuring element for local background estimation (larger than individual kernels)
    ksize = max(31, int(min(H, W) * 0.08)) | 1
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))

    # Background L: kernels are darker than paper. Morphological closing (dilation + erosion) removes dark kernels
    # and recovers local paper lightness even under strong vignetting (dark edges).
    bg_L = cv2.morphologyEx(lab[:, :, 0], cv2.MORPH_CLOSE, se)
    bg_L = cv2.GaussianBlur(bg_L, (0, 0), sigmaX=ksize / 2.0, sigmaY=ksize / 2.0)

    # Background chromaticity: local estimation
    bg_a = cv2.morphologyEx(lab[:, :, 1], cv2.MORPH_CLOSE, se)
    bg_a = cv2.GaussianBlur(bg_a, (0, 0), sigmaX=ksize / 2.0, sigmaY=ksize / 2.0)
    bg_b = cv2.morphologyEx(lab[:, :, 2], cv2.MORPH_CLOSE, se)
    bg_b = cv2.GaussianBlur(bg_b, (0, 0), sigmaX=ksize / 2.0, sigmaY=ksize / 2.0)

    # Mask out ignore zones during background sampling to avoid watermark bias
    sample_mask = np.ones((H, W), dtype=bool)
    if ignore_zones:
        for z in ignore_zones:
            x1 = max(0, int(round(float(z.get("x", 0.0)) * W)))
            y1 = max(0, int(round(float(z.get("y", 0.0)) * H)))
            x2 = min(W, int(round((float(z.get("x", 0.0)) + float(z.get("w", 0.0))) * W)))
            y2 = min(H, int(round((float(z.get("y", 0.0)) + float(z.get("h", 0.0))) * H)))
            sample_mask[y1:y2, x1:x2] = False

    # Representative median chromaticity in clean paper region
    valid_a = bg_a[sample_mask]
    valid_b = bg_b[sample_mask]
    a_med = float(np.median(valid_a)) if valid_a.size > 0 else 128.0
    b_med = float(np.median(valid_b)) if valid_b.size > 0 else 128.0
    paper_ab = np.array([a_med, b_med], dtype=np.float32)

    return bg_L, paper_ab, bg_a, bg_b


def split_touching_watershed(blob_mask: np.ndarray, img_bgr: np.ndarray, peak_ratio: float = 0.40) -> List[np.ndarray]:
    """
    Detects if a connected blob consists of touching kernels using distance transform
    local maxima. If multiple peaks are found, executes watershed to split them.
    Returns list of binary uint8 masks (one per separated kernel).
    """
    dist = cv2.distanceTransform(blob_mask, cv2.DIST_L2, 5)
    max_d = float(dist.max())
    if max_d == 0:
        return [blob_mask]

    # Find distinct distance peaks separated by at least minimum kernel radius
    r = max(6, int(max_d * 0.45))
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    dilated = cv2.dilate(dist, se)
    peaks = (dist == dilated) & (dist > peak_ratio * max_d) & (blob_mask > 0)
    
    num_peaks, markers = cv2.connectedComponents(peaks.astype(np.uint8))
    
    # 0 is background, so <= 2 components means at most 1 distinct peak -> single kernel
    if num_peaks <= 2:
        return [blob_mask]

    # Multiple peaks detected -> touching kernels! Run watershed
    markers = markers + 1
    sure_bg = cv2.dilate(blob_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    markers[sure_bg == 0] = 1
    markers[blob_mask == 0] = 1

    ws_markers = cv2.watershed(img_bgr, markers)
    split_masks = []
    for lbl in range(2, num_peaks + 1):
        m = (ws_markers == lbl).astype(np.uint8) * 255
        if cv2.countNonZero(m) > 100:
            split_masks.append(m)

    return split_masks if split_masks else [blob_mask]


def compute_kernel_color_metrics(
    img_bgr: np.ndarray,
    mask: np.ndarray,
    suspect_threshold: float = 40.0,
    material: Optional[str] = None
) -> Dict:
    """
    Computes per-kernel colour screening metrics in CIE Lab space:
    1. Median Lab colour: (L_med, a_med, b_med)
    2. Fraction of pixels much darker than the kernel's own median lightness (L < L_med - 18)
    3. Fraction of grey, green, or bluish-white discoloured patches
    4. Colour unevenness (variance/standard deviation across Lab channels)
    5. Suspect score (0-100) and human-readable reason tags ("dark patch 18%", "grey-green patch", "uneven colour")
    6. Classification: "Normal" or "Suspect (discoloured)" (never uses the word 'mold')
    """
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    pts = lab[mask > 0]
    if pts.shape[0] == 0:
        return {
            "median_lab": (128.0, 128.0, 128.0),
            "dark_patch_pct": 0.0,
            "patch_pct": 0.0,
            "unevenness": 0.0,
            "suspect_score": 0.0,
            "reason_tags": [],
            "classification": "Normal"
        }

    L_channel = pts[:, 0].astype(np.float32)
    a_channel = pts[:, 1].astype(np.float32)
    b_channel = pts[:, 2].astype(np.float32)

    # 1. Median Lab colour
    med_L = float(np.median(L_channel))
    med_a = float(np.median(a_channel))
    med_b = float(np.median(b_channel))

    # 2. Fraction of pixels much darker than kernel's own median
    dark_mask = L_channel < (med_L - 18.0)
    dark_frac = float(np.mean(dark_mask))

    # 3. Fraction of grey, green or bluish-white patches
    chroma = np.sqrt((a_channel - 128.0) ** 2 + (b_channel - 128.0) ** 2)
    # Grey patch: washed out / low chroma (dist < 9.5 and not bright specular white)
    is_grey = (chroma < 9.5) & (L_channel < 210.0)
    # Green patch: negative a-shift (a < 124 in uint8 Lab)
    is_green = a_channel < 124.0
    # Bluish-white / pale powdery patch: higher lightness with cool/blue shift
    is_blue_white = (L_channel > 165.0) & (b_channel < 126.0)

    patch_mask = is_grey | is_green | is_blue_white
    patch_frac = float(np.mean(patch_mask))

    # 4. Colour unevenness: total dispersion across L, a, b channels
    var_L = float(np.var(L_channel))
    var_a = float(np.var(a_channel))
    var_b = float(np.var(b_channel))
    unevenness = float(np.sqrt(var_L + var_a + var_b))

    # 5. Suspect score (0 - 100)
    dark_score = min(45.0, dark_frac * 200.0)
    patch_score = min(40.0, patch_frac * 220.0)
    uneven_score = min(30.0, max(0.0, (unevenness - 12.0) * 2.5))
    total_score = min(100.0, round(dark_score + patch_score + uneven_score, 1))

    # Reason tags
    tags = []
    if dark_frac >= 0.05:
        tags.append(f"dark patch {round(dark_frac * 100)}%")
    if patch_frac >= 0.04:
        if float(np.mean(is_green)) >= 0.03:
            tags.append("grey-green patch")
        elif float(np.mean(is_blue_white)) >= 0.03:
            tags.append("bluish-white patch")
        else:
            tags.append("grey-green patch")
    if unevenness >= 16.0:
        tags.append("uneven colour")

    # Reason why (Requirement 4: e.g. "dark patch 18% of area")
    if dark_frac >= 0.05:
        reason_why = f"dark patch {round(dark_frac * 100)}% of area"
    elif patch_frac >= 0.04:
        if float(np.mean(is_green)) >= 0.03:
            reason_why = f"grey-green patch {round(patch_frac * 100)}% of area"
        elif float(np.mean(is_blue_white)) >= 0.03:
            reason_why = f"bluish-white patch {round(patch_frac * 100)}% of area"
        else:
            reason_why = f"grey-green patch {round(patch_frac * 100)}% of area"
    elif unevenness >= 16.0:
        reason_why = f"uneven colour dispersion ({unevenness:.1f})"
    elif total_score >= suspect_threshold:
        reason_why = f"discoloured (suspect score {total_score:.0f})"
    else:
        reason_why = f"Normal (score {total_score:.0f})"

    # Classification: "Normal" or "Suspect (discoloured)"
    classification = "Suspect (discoloured)" if total_score >= suspect_threshold else "Normal"

    return {
        "median_lab": (round(med_L, 1), round(med_a, 1), round(med_b, 1)),
        "dark_patch_pct": round(dark_frac * 100.0, 1),
        "patch_pct": round(patch_frac * 100.0, 1),
        "unevenness": round(unevenness, 1),
        "suspect_score": total_score,
        "reason_tags": tags,
        "reason_why": reason_why,
        "classification": classification
    }


def crop_kernel_image(img_bgr: np.ndarray, bbox: Tuple[int, int, int, int], padding: int = 8) -> np.ndarray:
    """Crops a kernel image with boundary safety and padding."""
    H, W = img_bgr.shape[:2]
    x, y, w, h = bbox
    y1 = max(0, y - padding)
    y2 = min(H, y + h + padding)
    x1 = max(0, x - padding)
    x2 = min(W, x + w + padding)
    return img_bgr[y1:y2, x1:x2].copy()


def find_kernels_classical(
    img_input,
    ignore_zones: Optional[List[Dict]] = None,
    min_area_pct: float = 0.08,
    max_area_pct: float = 6.0,
    min_solidity: float = 0.70,
    max_aspect_ratio: float = 3.6,
    watershed_peak_ratio: float = 0.40,
    suspect_threshold: float = 40.0,
    material: Optional[str] = None
) -> Dict:
    """
    Classical kernel finder (OpenCV, no AI):
    1. Estimate paper colour from the frame in Lab space
    2. Threshold by colour distance in Lab using Otsu
    3. Clean with morphological opening & closing
    4. Split touching kernels with distance-transform watershed
    5. Filter blobs by area range (relative to frame), solidity, aspect ratio, and ignore zones
    6. Compute per-kernel colour screening metrics, suspect score, and reason tags
    
    Returns:
        dict containing:
            - kernels: list of dicts with mask, bbox, area, metrics, suspect_score, classification, reason_tags
            - total_kernels: integer count
            - normal_count: count of Normal kernels
            - suspect_count: count of Suspect (discoloured) kernels
            - ignored_count: count of candidate blobs dropped inside ignore zones
            - paper_color: estimated (L_mean, a, b)
            - otsu_threshold: float
            - debug_image: annotated image with outlines and ID numbers
    """
    if ignore_zones is None:
        ignore_zones = DEFAULT_IGNORE_ZONES

    # Profile parameter tuning gated behind INSPECTION_PROFILE=improved
    try:
        from config import Config
        if Config.is_improved_inspection():
            mat_key = str(material or "default").lower()
            if "corn" in mat_key or "maize" in mat_key:
                mat_key = "corn"
            elif "peanut" in mat_key or "groundnut" in mat_key:
                mat_key = "peanut"
            elif "sunflower" in mat_key:
                mat_key = "sunflower"
            else:
                mat_key = "default"
            profile = Config.INSPECTION_PROFILES.get("improved", {}).get(mat_key, Config.INSPECTION_PROFILES["improved"]["default"])
            min_area_pct = profile.get("min_area_pct", min_area_pct)
            max_area_pct = profile.get("max_area_pct", max_area_pct)
            watershed_peak_ratio = profile.get("watershed_peak_ratio", watershed_peak_ratio)
            suspect_threshold = profile.get("colour_threshold", suspect_threshold)
    except Exception:
        pass

    if isinstance(img_input, str):
        img = cv2.imread(img_input)
        if img is None:
            raise FileNotFoundError(f"Could not load image from: {img_input}")
    else:
        img = img_input.copy()

    H, W = img.shape[:2]
    frame_area = float(H * W)

    # 1. Estimate paper colour from frame in Lab using local background estimation
    res_bg = estimate_paper_color_lab(img, ignore_zones)
    if len(res_bg) == 4:
        bg_L, paper_ab, bg_a, bg_b = res_bg
    else:
        bg_L, paper_ab = res_bg[:2]
        bg_a, bg_b = paper_ab[0], paper_ab[1]

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)

    # 2. Subtract local background before thresholding (neutralizes vignetting and lighting gradients)
    d_L = np.maximum(0.0, bg_L - lab[:, :, 0])
    d_a = np.abs(lab[:, :, 1] - bg_a)
    d_b = np.abs(lab[:, :, 2] - bg_b)

    # Contrast distance: lightness darkening and chromatic delta from local background
    color_dist = np.sqrt(d_L ** 2 + d_a ** 2 + d_b ** 2)
    max_dist = float(color_dist.max())
    if max_dist >= 8.0:
        dist_8u = np.uint8(np.clip(color_dist * (255.0 / max_dist), 0, 255))
        otsu_val, thresh = cv2.threshold(dist_8u, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        dist_8u = np.zeros((H, W), dtype=np.uint8)
        otsu_val, thresh = 0.0, np.zeros((H, W), dtype=np.uint8)

    # 3. Clean with morphology
    k_size = max(3, int(min(H, W) * 0.005))
    k_size = k_size if k_size % 2 == 1 else k_size + 1
    morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
    
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, morph_kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, morph_kernel)

    # 4. Extract connected components and apply watershed to split touching kernels
    cnts, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    candidate_masks = []
    ignored_count = 0

    for c in cnts:
        raw_area = cv2.contourArea(c)
        if raw_area < 150: # filter micro noise
            continue

        rx, ry, rw, rh = cv2.boundingRect(c)
        rcx = (rx + rw / 2.0) / float(W)
        rcy = (ry + rh / 2.0) / float(H)

        # Check ignore zone: if center is inside, drop immediately
        if is_center_in_ignore_zones(rcx, rcy, ignore_zones):
            ignored_count += 1
            continue

        blob_mask = np.zeros((H, W), dtype=np.uint8)
        cv2.drawContours(blob_mask, [c], -1, 255, -1)

        # Split touching kernels with watershed
        split_masks = split_touching_watershed(blob_mask, img, peak_ratio=watershed_peak_ratio)
        candidate_masks.extend(split_masks)

    # 5. Filter blobs by area range, solidity, aspect ratio
    kernels = []

    for mask in candidate_masks:
        sub_cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not sub_cnts:
            continue

        cnt = max(sub_cnts, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        if area <= 0:
            continue

        area_pct = (area / frame_area) * 100.0

        # Bounding box & normalized coordinates
        x, y, w, h = cv2.boundingRect(cnt)
        cx = (x + w / 2.0) / float(W)
        cy = (y + h / 2.0) / float(H)

        # Area range check (relative to frame)
        if area_pct < min_area_pct or area_pct > max_area_pct:
            continue

        # In improved profile: ignore border slivers and diffuse shadows
        try:
            from config import Config
            if Config.is_improved_inspection():
                if cx < 0.015 or cx > 0.985 or cy < 0.015 or cy > 0.985:
                    continue
                blob_dist = color_dist[mask > 0]
                if blob_dist.size > 0 and float(np.mean(blob_dist)) < 15.0:
                    continue
        except Exception:
            pass

        # Solidity: contour area / convex hull area
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity = float(area / hull_area) if hull_area > 0 else 0.0
        if solidity < min_solidity:
            continue

        # Aspect ratio: max(w, h) / min(w, h)
        ar = float(max(w, h)) / max(1.0, float(min(w, h)))
        if ar > max_aspect_ratio:
            continue

        kernels.append({
            "id": len(kernels) + 1,
            "mask": mask,
            "bbox": (x, y, w, h),
            "bbox_normalized": {
                "x": round(x / float(W), 4),
                "y": round(y / float(H), 4),
                "w": round(w / float(W), 4),
                "h": round(h / float(H), 4),
                "x_pct": round((x / float(W)) * 100.0, 2),
                "y_pct": round((y / float(H)) * 100.0, 2),
                "w_pct": round((w / float(W)) * 100.0, 2),
                "h_pct": round((h / float(H)) * 100.0, 2),
            },
            "centroid": (int(round(cx * W)), int(round(cy * H))),
            "centroid_normalized": (round(cx, 4), round(cy, 4)),
            "area": int(round(area)),
            "area_pct": round(area_pct, 3),
            "solidity": round(solidity, 3),
            "aspect_ratio": round(ar, 3),
            "contour": cnt
        })

    # Sort kernels spatially (top-to-bottom, left-to-right) and index 1..N
    kernels.sort(key=lambda k: (k["bbox"][1] // 60, k["bbox"][0]))
    for idx, k in enumerate(kernels, 1):
        k["id"] = idx
        # Compute per-kernel colour screening metrics, suspect score, and reason tags
        metrics = compute_kernel_color_metrics(
            img, k["mask"], suspect_threshold=suspect_threshold, material=material
        )
        k["metrics"] = metrics
        k["classification"] = metrics["classification"]
        k["suspect_score"] = metrics["suspect_score"]
        k["reason_tags"] = metrics["reason_tags"]
        k["reason_why"] = metrics.get("reason_why", "")
        k["median_lab"] = metrics["median_lab"]

    normal_count = sum(1 for k in kernels if k["classification"] == "Normal")
    suspect_count = sum(1 for k in kernels if k["classification"] != "Normal")

    # 6. Generate Debug View image
    debug_img = generate_debug_view(
        img, kernels, ignore_zones,
        (float(np.mean(bg_L)), float(paper_ab[0]), float(paper_ab[1])),
        otsu_val
    )

    return {
        "kernels": kernels,
        "total_kernels": len(kernels),
        "normal_count": normal_count,
        "suspect_count": suspect_count,
        "ignored_count": ignored_count,
        "paper_lab": (round(float(np.mean(bg_L)), 1), round(float(paper_ab[0]), 1), round(float(paper_ab[1]), 1)),
        "otsu_threshold": round(float(otsu_val), 1),
        "debug_image": debug_img
    }


def generate_debug_view(
    img_bgr: np.ndarray,
    kernels: List[Dict],
    ignore_zones: List[Dict],
    paper_lab: Tuple[float, float, float],
    otsu_val: float
) -> np.ndarray:
    """
    Renders an informative debug image showing:
    - Kernel outlines with color coding:
        Normal -> Green
        Suspect (discoloured) -> Red
        Uncertain -> Amber
    - Big readable outlines (thickness 3)
    - Distinct ID numbers (#1, #2, #3, ...) with label and reason tags
    - Bounding boxes and centroid crosshairs
    - Ignore zone(s) outlined in red/amber with hatched label
    - Top HUD diagnostics bar
    - Bottom footer notice: "Colour screening only. Not a mold or lab test."
    """
    debug = img_bgr.copy()
    H, W = debug.shape[:2]

    # Draw Ignore Zones (Outlined with dashed / highlighted border)
    if ignore_zones:
        for z in ignore_zones:
            zx1 = max(0, int(round(float(z.get("x", 0.0)) * W)))
            zy1 = max(0, int(round(float(z.get("y", 0.0)) * H)))
            zx2 = min(W, int(round((float(z.get("x", 0.0)) + float(z.get("w", 0.0))) * W)))
            zy2 = min(H, int(round((float(z.get("y", 0.0)) + float(z.get("h", 0.0))) * H)))

            # Semi-transparent red overlay in ignore zone
            overlay = debug.copy()
            cv2.rectangle(overlay, (zx1, zy1), (zx2, zy2), (40, 40, 200), -1)
            cv2.addWeighted(overlay, 0.22, debug, 0.78, 0, debug)

            # Highlighted amber border
            cv2.rectangle(debug, (zx1, zy1), (zx2, zy2), (30, 165, 245), 2, cv2.LINE_AA)
            cv2.putText(
                debug, "IGNORE ZONE (Logo / Watermark)",
                (zx1 + 8, zy1 + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA
            )

    # Draw Kernels (Requirement 4: Outlines green=normal, red=suspect, amber=uncertain, big readable outlines)
    for k in kernels:
        cnt = k.get("contour")
        kid = k["id"]
        x, y, w, h = k["bbox"]
        cx, cy = k["centroid"]
        
        is_uncertain = (k.get("classification") == "Uncertain" or k.get("type") == "uncertain")
        is_suspect = (k.get("classification") != "Normal" and not is_uncertain)
        score = k.get("suspect_score", 0.0)
        tags = k.get("reason_tags", [])

        # Color coding: Green for Normal, Red for Suspect, Amber for Uncertain (in BGR)
        if is_uncertain:
            contour_color = (0, 165, 255)   # Amber
            box_color = (0, 165, 255)
            badge_border = (0, 165, 255)
            class_str = "Uncertain"
        elif is_suspect:
            contour_color = (30, 30, 235)   # Red
            box_color = (40, 40, 220)
            badge_border = (30, 30, 235)
            class_str = "Suspect"
        else:
            contour_color = (40, 205, 50)   # Green
            box_color = (40, 190, 50)
            badge_border = (40, 205, 50)
            class_str = "Normal"

        # Big readable outline: thickness=3 for contour, thickness=2 for box
        if cnt is not None:
            cv2.drawContours(debug, [cnt], -1, contour_color, 3, cv2.LINE_AA)
        cv2.rectangle(debug, (x, y), (x + w, y + h), box_color, 2, cv2.LINE_AA)
        cv2.circle(debug, (cx, cy), 3, (0, 0, 255), -1, cv2.LINE_AA)

        # ID Badge
        tag_str = f" [{tags[0]}]" if (is_suspect and tags) else ""
        if is_uncertain:
            id_label = f"#{kid} Uncertain"
        elif is_suspect:
            id_label = f"#{kid} Suspect ({score:.0f}){tag_str}"
        else:
            id_label = f"#{kid} Normal ({score:.0f})"

        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.44
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(id_label, font, scale, thickness)
        
        # Position label above bounding box (or inside if near top)
        bx = max(2, x)
        by = max(th + 6, y - 6)
        
        # Badge background
        cv2.rectangle(debug, (bx - 2, by - th - 4), (bx + tw + 6, by + baseline + 2), (15, 23, 42), -1)
        cv2.rectangle(debug, (bx - 2, by - th - 4), (bx + tw + 6, by + baseline + 2), badge_border, 1, cv2.LINE_AA)
        cv2.putText(debug, id_label, (bx + 2, by), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    # Top HUD Banner
    hud_h = 36
    hud = np.zeros((hud_h, W, 3), dtype=np.uint8)
    cv2.rectangle(hud, (0, 0), (W, hud_h), (15, 23, 42), -1)

    normal_cnt = sum(1 for k in kernels if k.get("classification") == "Normal")
    suspect_cnt = sum(1 for k in kernels if k.get("classification") != "Normal")

    hud_text = f"COLOUR SCREENING | {normal_cnt} Normal, {suspect_cnt} Suspect (discoloured) | Paper Lab: ({paper_lab[0]:.0f}, {paper_lab[1]:.0f}, {paper_lab[2]:.0f}) | Otsu: {otsu_val:.0f}"
    cv2.putText(hud, hud_text, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (241, 245, 249), 1, cv2.LINE_AA)
    
    # Mode indicator
    cv2.circle(hud, (W - 130, 18), 5, (0, 220, 100), -1, cv2.LINE_AA)
    cv2.putText(hud, "NO AI / LAB OTSU", (W - 118, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 220, 180), 1, cv2.LINE_AA)

    # Bottom Footer Banner (Requirement 3: "Colour screening only. Not a mold or lab test.")
    footer_h = 28
    footer = np.zeros((footer_h, W, 3), dtype=np.uint8)
    cv2.rectangle(footer, (0, 0), (W, footer_h), (10, 15, 30), -1)
    footer_text = "Colour screening only. Not a mold or lab test."
    (ftw, fth), _ = cv2.getTextSize(footer_text, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
    fx = max(10, (W - ftw) // 2)
    cv2.putText(footer, footer_text, (fx, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (148, 163, 184), 1, cv2.LINE_AA)

    return np.vstack([hud, debug, footer])
