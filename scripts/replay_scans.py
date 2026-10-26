"""
Food Man QC - Replay Scans Benchmark Script
Requirement 6:
Replay all saved live frames and sample photos grouped by scan,
run the new pipeline 5 times each, and report:
- kernels found
- verdict per kernel
- consistency % across runs
- old live mode on the same frames for comparison
- comparison of settings (imgsz, confidence, TTA)
"""
import os
import sys
import glob
import re
import time
import json
from collections import defaultdict, Counter
import cv2
import numpy as np

# Ensure project root in sys.path
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from config import Config
from ai.scan_pipeline import (
    run_burst_scan_pipeline,
    select_sharpest_frames,
    detect_frame_kernels,
    DEFAULT_IMGSZ,
    DEFAULT_CONF_FLOOR
)
from ai.yolo_service import get_cached_yolo_model, find_trained_model


def find_scan_groups(max_scans=15):
    """
    Finds saved live frame sessions and sample evaluation photos grouped by scan.
    """
    groups = defaultdict(list)

    # 1. Group static/uploads/live_frames/raw by session ID
    live_raw_dir = os.path.join(PROJECT_DIR, 'static', 'uploads', 'live_frames', 'raw')
    if os.path.isdir(live_raw_dir):
        files = glob.glob(os.path.join(live_raw_dir, 'live_*.jpg'))
        for fpath in files:
            fname = os.path.basename(fpath)
            m = re.match(r'live_(\d+)_', fname)
            if m:
                sid = f"Session_{m.group(1)}"
                groups[sid].append(fpath)

    # 2. Add eval_photos as demo sample groups
    eval_dir = os.path.join(PROJECT_DIR, 'eval_photos')
    if os.path.isdir(eval_dir):
        eval_files = glob.glob(os.path.join(eval_dir, '*.jpg'))
        # Group eval photos by commodity/sample prefix
        for ef in eval_files:
            bname = os.path.basename(ef)
            parts = bname.split('_')
            prefix = parts[0] if len(parts) > 0 else 'sample'
            group_key = f"Eval_{prefix}"
            groups[group_key].append(ef)

    # Filter to groups with at least 3 frames (or at least 1 frame for eval photos)
    valid_groups = {}
    for k, flist in sorted(groups.items()):
        # Sort files by timestamp or name
        flist.sort()
        if len(flist) >= 3:
            valid_groups[k] = flist
        elif k.startswith("Eval_") and len(flist) >= 1:
            valid_groups[k] = flist

    # Return selected subset of diverse scan groups
    selected = {}
    # Include up to max_scans
    for k, v in list(valid_groups.items())[:max_scans]:
        selected[k] = v

    return selected


def simulate_old_live_mode(frames, model, imgsz=640, conf_floor=0.25):
    """
    Simulates the old live mode:
    Evaluates frames sequentially frame-by-frame with single-frame YOLO overlay.
    Reports kernel counts per frame, variation (flicker), and verdicts.
    """
    frame_counts = []
    frame_defect_counts = []
    frame_verdicts = []

    for fpath in frames:
        img = cv2.imread(fpath)
        if img is None:
            continue
        dets = detect_frame_kernels(
            img_bgr=img,
            model=model,
            imgsz=imgsz,
            conf_floor=conf_floor,
            augment=False
        )
        n_total = len(dets)
        n_defects = sum(1 for d in dets if d['type'] == 'defect')
        verdict = "Reject" if n_defects > 0 else ("Pass" if n_total >= 3 else "Retake")

        frame_counts.append(n_total)
        frame_defect_counts.append(n_defects)
        frame_verdicts.append(verdict)

    if not frame_counts:
        return {
            "mean_count": 0,
            "min_count": 0,
            "max_count": 0,
            "count_std": 0.0,
            "verdict_agreement_pct": 0.0,
            "dominant_verdict": "None",
            "frame_counts": []
        }

    mean_c = float(np.mean(frame_counts))
    min_c = min(frame_counts)
    max_c = max(frame_counts)
    std_c = float(np.std(frame_counts))

    # Agreement % of the single-frame verdict across frames
    v_counts = Counter(frame_verdicts)
    dom_verdict, dom_count = v_counts.most_common(1)[0]
    verdict_agreement = round((dom_count / float(len(frame_verdicts))) * 100.0, 1)

    return {
        "mean_count": round(mean_c, 1),
        "min_count": min_c,
        "max_count": max_c,
        "count_std": round(std_c, 2),
        "verdict_agreement_pct": verdict_agreement,
        "dominant_verdict": dom_verdict,
        "frame_counts": frame_counts
    }


def replay_scan_group(group_name, frame_paths, num_runs=5, imgsz=640, conf_floor=0.25, augment=False, model=None):
    """
    Runs the new pipeline 5 times on the same scan group,
    recording kernels found, verdict per kernel, and consistency % across runs.
    Also compares against the old live mode.
    """
    runs_results = []

    for r_idx in range(num_runs):
        res = run_burst_scan_pipeline(
            frames=frame_paths,
            imgsz=imgsz,
            conf_floor=conf_floor,
            augment=augment,
            min_kernels=3
        )
        runs_results.append(res)

    # 1. Kernel Count Consistency
    kernel_counts = [r["total_kernels"] for r in runs_results]
    is_count_identical = len(set(kernel_counts)) == 1
    count_consistency_pct = 100.0 if is_count_identical else round((min(kernel_counts) / float(max(kernel_counts) or 1)) * 100.0, 1)

    # 2. Verdict per Kernel Consistency
    # Map kernels across runs by centroid
    first_run = runs_results[0]
    base_kernels = first_run.get("tracked_kernels", [])

    kernel_verdict_agreements = []
    for k in base_kernels:
        k_id = k["id"]
        k_verdict = k["verdict"]
        # In subsequent runs, check if a matching kernel has the same verdict
        agreed_runs = 1
        for other_res in runs_results[1:]:
            other_kernels = other_res.get("tracked_kernels", [])
            # Find closest kernel by centroid
            best_match = None
            min_d = float('inf')
            for ok in other_kernels:
                d = np.sqrt((k["centroid"][0] - ok["centroid"][0])**2 + (k["centroid"][1] - ok["centroid"][1])**2)
                if d < min_d and d < 0.08:
                    min_d = d
                    best_match = ok
            if best_match and best_match["verdict"] == k_verdict:
                agreed_runs += 1
            elif not best_match and k_verdict == "Normal":
                pass
        kernel_verdict_agreements.append((agreed_runs / float(num_runs)) * 100.0)

    avg_kernel_verdict_consistency = round(float(np.mean(kernel_verdict_agreements)), 1) if kernel_verdict_agreements else 100.0

    # 3. Overall Decision State Consistency
    run_decisions = [r["suggestion"] for r in runs_results]
    decision_counts = Counter(run_decisions)
    dom_decision, dom_count = decision_counts.most_common(1)[0]
    run_decision_consistency = round((dom_count / float(num_runs)) * 100.0, 1)

    # 4. Old Live Mode Comparison on the same frames
    old_live = simulate_old_live_mode(frame_paths, model=model, imgsz=imgsz, conf_floor=conf_floor)

    return {
        "group_name": group_name,
        "frames_count": len(frame_paths),
        "kernels_found": kernel_counts[0] if kernel_counts else 0,
        "kernel_counts_across_runs": kernel_counts,
        "new_count_consistency_pct": count_consistency_pct,
        "kernel_verdict_consistency_pct": avg_kernel_verdict_consistency,
        "new_decision": dom_decision,
        "new_decision_consistency_pct": run_decision_consistency,
        "tracked_kernels_sample": [
            {"id": k["id"], "verdict": k["verdict"], "avg_conf": round(k["avg_confidence"], 3)}
            for k in base_kernels[:8]
        ],
        "old_live_mean_count": old_live["mean_count"],
        "old_live_count_std": old_live["count_std"],
        "old_live_frame_counts": old_live["frame_counts"],
        "old_live_verdict_agreement_pct": old_live["verdict_agreement_pct"],
        "old_live_dominant_verdict": old_live["dominant_verdict"]
    }


def evaluate_parameter_settings(scan_groups, model):
    """
    Evaluates different parameter combinations (imgsz, confidence, TTA)
    to find the optimal configuration for demo sample repeatability.
    """
    settings_candidates = [
        {"imgsz": 640, "conf_floor": 0.25, "augment": False, "name": "imgsz 640, conf 0.25, TTA off"},
        {"imgsz": 640, "conf_floor": 0.25, "augment": True,  "name": "imgsz 640, conf 0.25, TTA on"},
        {"imgsz": 640, "conf_floor": 0.20, "augment": False, "name": "imgsz 640, conf 0.20, TTA off"},
        {"imgsz": 640, "conf_floor": 0.30, "augment": False, "name": "imgsz 640, conf 0.30, TTA off"},
        {"imgsz": 480, "conf_floor": 0.25, "augment": False, "name": "imgsz 480, conf 0.25, TTA off"},
    ]

    print("\n" + "=" * 90)
    print("PARAMETRIC SWEEP: COMPARING IMGSZ, CONFIDENCE FLOOR & TTA SETTINGS")
    print("=" * 90)

    sweep_results = []
    # Test on a representative subset of scan groups
    eval_subset = dict(list(scan_groups.items())[:6])

    for setting in settings_candidates:
        s_name = setting["name"]
        print(f"Testing {s_name}...")
        consistencies = []
        verdict_consistencies = []
        times = []

        for gname, flist in eval_subset.items():
            t0 = time.time()
            res = replay_scan_group(
                gname, flist, num_runs=3,
                imgsz=setting["imgsz"],
                conf_floor=setting["conf_floor"],
                augment=setting["augment"],
                model=model
            )
            elapsed = time.time() - t0
            consistencies.append(res["new_count_consistency_pct"])
            verdict_consistencies.append(res["kernel_verdict_consistency_pct"])
            times.append(elapsed / 3.0)

        avg_count_cons = round(float(np.mean(consistencies)), 1)
        avg_v_cons = round(float(np.mean(verdict_consistencies)), 1)
        avg_time_sec = round(float(np.mean(times)), 2)

        sweep_results.append({
            "setting": s_name,
            "imgsz": setting["imgsz"],
            "conf_floor": setting["conf_floor"],
            "augment": setting["augment"],
            "count_consistency_pct": avg_count_cons,
            "verdict_consistency_pct": avg_v_cons,
            "avg_latency_sec": avg_time_sec
        })

    return sweep_results


def main():
    print("=" * 90)
    print("FOOD MAN QC: REPLAY SCANS & AI INSPECTION STABILITY BENCHMARK")
    print("=" * 90)

    model_path, model_name = find_trained_model()
    print(f"Loaded Detection Model: {model_name} ({model_path})")
    model = get_cached_yolo_model(model_path)

    # 1. Discover scan groups
    scan_groups = find_scan_groups(max_scans=12)
    print(f"Discovered {len(scan_groups)} eligible scan groups across live sessions & demo photos.\n")

    if not scan_groups:
        print("ERROR: No scan groups found in static/uploads/live_frames/raw or eval_photos.")
        return

    # 2. Benchmark each scan group with the new pipeline (5 runs) vs old live mode
    print(f"{'Scan / Group':<16} | {'Frames':<6} | {'Kernels':<8} | {'New Verdict':<12} | {'New Consistency':<15} | {'Old Live Counts':<18} | {'Old Agreement':<13}")
    print("-" * 98)

    benchmark_rows = []
    for gname, flist in scan_groups.items():
        row = replay_scan_group(
            gname, flist, num_runs=5,
            imgsz=DEFAULT_IMGSZ,
            conf_floor=DEFAULT_CONF_FLOOR,
            augment=False,
            model=model
        )
        benchmark_rows.append(row)

        counts_str = f"μ={row['old_live_mean_count']} (σ={row['old_live_count_std']})"
        old_agree_str = f"{row['old_live_verdict_agreement_pct']}%"
        new_consist_str = f"{row['new_count_consistency_pct']}% (v:{row['kernel_verdict_consistency_pct']}%)"

        print(f"{row['group_name']:<16} | {row['frames_count']:<6} | {row['kernels_found']:<8} | {row['new_decision']:<12} | {new_consist_str:<15} | {counts_str:<18} | {old_agree_str:<13}")

    # Summary Statistics
    avg_new_count_cons = np.mean([r['new_count_consistency_pct'] for r in benchmark_rows])
    avg_new_verdict_cons = np.mean([r['kernel_verdict_consistency_pct'] for r in benchmark_rows])
    avg_old_verdict_agree = np.mean([r['old_live_verdict_agreement_pct'] for r in benchmark_rows])
    avg_old_std = np.mean([r['old_live_count_std'] for r in benchmark_rows])

    print("-" * 98)
    print(f"AVERAGES: New Count Consistency: {avg_new_count_cons:.1f}% | New Verdict Consistency: {avg_new_verdict_cons:.1f}%")
    print(f"          Old Live Frame Agreement: {avg_old_verdict_agree:.1f}% | Old Count Jitter (StdDev): ±{avg_old_std:.2f} kernels")
    print("=" * 98)

    # 3. Parameter sweep
    sweep_results = evaluate_parameter_settings(scan_groups, model)

    print("\n" + "=" * 90)
    print(f"{'Setting Configuration':<36} | {'Count Cons.':<12} | {'Verdict Cons.':<14} | {'Avg Latency':<12}")
    print("-" * 90)
    for sr in sweep_results:
        print(f"{sr['setting']:<36} | {sr['count_consistency_pct']}%{'':<6} | {sr['verdict_consistency_pct']}%{'':<7} | {sr['avg_latency_sec']}s")
    print("=" * 90)

    # Save benchmark report to scratch/replay_scans_summary.json
    scratch_dir = os.path.join(PROJECT_DIR, 'scratch')
    os.makedirs(scratch_dir, exist_ok=True)
    report_file = os.path.join(scratch_dir, 'replay_scans_summary.json')

    serializable_rows = []
    for r in benchmark_rows:
        cp = dict(r)
        serializable_rows.append(cp)

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "benchmark_rows": serializable_rows,
            "sweep_results": sweep_results,
            "overall_averages": {
                "new_count_consistency_pct": round(float(avg_new_count_cons), 1),
                "new_verdict_consistency_pct": round(float(avg_new_verdict_cons), 1),
                "old_live_verdict_agreement_pct": round(float(avg_old_verdict_agree), 1),
                "old_live_jitter_std": round(float(avg_old_std), 2)
            }
        }, f, indent=2)

    print(f"\n✓ Benchmark results written to {report_file}")


if __name__ == '__main__':
    main()
