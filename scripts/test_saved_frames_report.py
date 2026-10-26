import os
import sys
import json
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ['USE_MATERIAL_CLASSIFIER'] = '1'

from config import Config
Config.USE_MATERIAL_CLASSIFIER = True

from wsgi import app
from models import get_db
from models.qc import LiveSession, LiveFrame
from routes.qc import evaluate_locked_frames, get_default_engine_for_material, resolve_inspection_engine, final_decision
from ai.classical_kernel_finder import find_kernels_classical

def test_saved_frames():
    with app.app_context():
        db = get_db()

        frame_sets = [
            {
                "name": "Peanut Saved Frames",
                "material": "Peanut",
                "expected_default_engine": "colour",
                "files": [os.path.join(PROJECT_ROOT, "static", "uploads", "live_frames", "raw", f"sim_179_f{i}_peanut.jpg") for i in range(5)]
            },
            {
                "name": "Corn Saved Frames",
                "material": "Corn",
                "expected_default_engine": "ai",
                "files": [os.path.join(PROJECT_ROOT, "static", "uploads", "live_frames", "raw", f"sim_181_f{i}_corn.jpg") for i in range(5)]
            },
            {
                "name": "Sunflower Saved Frames",
                "material": "Sunflower",
                "expected_default_engine": "colour",
                "files": [os.path.join(PROJECT_ROOT, "static", "uploads", "live_frames", "raw", f"sim_184_f{i}_sunflower.jpg") for i in range(5)]
            },
            {
                "name": "Mixed Material Frames",
                "material": "Mixed",
                "expected_default_engine": "colour",
                "files": [os.path.join(PROJECT_ROOT, "static", "uploads", "live_frames", "raw", f"sim_mixed_189_{i}.jpg") for i in range(5)]
            },
            {
                "name": "Uncertain Kernel Frames",
                "material": "Uncertain",
                "expected_default_engine": "colour",
                "files": [os.path.join(PROJECT_ROOT, "static", "uploads", "live_frames", "raw", f"sim_uncert_190_{i}.jpg") for i in range(5)]
            }
        ]

        print("=" * 80)
        print("VERIFYING REQUIREMENT 1: DEFAULT ENGINE RULES & 'BOTH' MODE")
        print("=" * 80)
        assert get_default_engine_for_material("Peanut") == "colour", "Peanut must default to colour"
        assert get_default_engine_for_material("Sunflower") == "colour", "Sunflower must default to colour"
        assert get_default_engine_for_material("Corn") == "ai", "Corn must default to ai"
        assert resolve_inspection_engine("auto", "Peanut") == "colour"
        assert resolve_inspection_engine("auto", "Corn") == "ai"
        assert resolve_inspection_engine("auto", "Sunflower") == "colour"
        assert resolve_inspection_engine("both", "Peanut") == "both"
        print("[PASS] Engine Resolution: Peanut -> colour, Sunflower -> colour, Corn -> ai, both -> both.")

        tables_output = []

        for fset in frame_sets:
            print("\n" + "=" * 80)
            print(f"RUNNING 5-FRAME EVALUATION: {fset['name']}")
            print("=" * 80)

            # Check files exist
            existing_files = [f for f in fset["files"] if os.path.isfile(f)]
            print(f"Loaded {len(existing_files)}/5 frame files.")
            assert len(existing_files) == 5, f"Missing frame files for {fset['name']}"

            import uuid
            import datetime
            sess = LiveSession(
                token=f"sim_sess_{uuid.uuid4().hex[:8]}",
                status="ACTIVE",
                expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
            )
            db.add(sess)
            db.commit()

            # Create LiveFrames copying detector/colour boxes from original recorded frames
            batch_frames = []
            for idx, fpath in enumerate(fset["files"]):
                rel_path = "/static/uploads/live_frames/raw/" + os.path.basename(fpath)
                orig_lf = db.query(LiveFrame).filter_by(image_path=rel_path).first()
                if orig_lf:
                    lf = LiveFrame(
                        session_id=sess.id,
                        image_path=rel_path,
                        annotated_path=orig_lf.annotated_path or rel_path,
                        material=orig_lf.material,
                        good_count=orig_lf.good_count,
                        defect_count=orig_lf.defect_count,
                        avg_confidence=orig_lf.avg_confidence,
                        status=orig_lf.status,
                        is_locked=True,
                        raw_json=orig_lf.raw_json
                    )
                else:
                    # Classical colour screening fallback
                    c_res = find_kernels_classical(fpath, material_type=fset["material"])
                    k_list = c_res.get("kernels", [])
                    boxes = []
                    for k in k_list:
                        nb = k["bbox_normalized"]
                        is_suspect = (k.get("classification") != "Normal")
                        boxes.append({
                            "id": k["id"],
                            "class": "Suspect (discoloured)" if is_suspect else "Normal",
                            "type": "defect" if is_suspect else "healthy",
                            "x": nb["x"], "y": nb["y"], "w": nb["w"], "h": nb["h"],
                            "suspect_score": k.get("suspect_score", 0.0),
                            "reason_why": k.get("reason_why", "discoloured" if is_suspect else "Normal")
                        })
                    n_sus = sum(1 for b in boxes if b["type"] == "defect")
                    n_norm = len(boxes) - n_sus
                    lf = LiveFrame(
                        session_id=sess.id,
                        image_path=rel_path,
                        annotated_path=rel_path,
                        material=fset["material"],
                        good_count=n_norm,
                        defect_count=n_sus,
                        avg_confidence=0.85,
                        status="DEFECTS_DETECTED" if n_sus > 0 else "NO_DEFECTS",
                        is_locked=True,
                        raw_json=json.dumps({"boxes": boxes})
                    )
                db.add(lf)
                batch_frames.append(lf)
            db.commit()

            # Run 5-frame locked evaluation
            res = evaluate_locked_frames(sess, batch_frames, db)

            total_items = res.get("total_items_counted", 0)
            good_items = res.get("good_items_counted", 0)
            defect_items = res.get("defect_items_counted", 0)
            uncertain_items = res.get("uncertain_items_counted", 0)
            sugg = res.get("operator_suggestion")
            final_dec = res.get("final_decision", {})
            material = res.get("material")
            tracked_kernels = res.get("tracked_kernels", [])

            print(f"Detected Material:   {material}")
            print(f"Final Decision:      State={final_dec.get('state')} | Sugg={sugg}")
            print(f"Decision Reason:     {final_dec.get('reason')}")
            print(f"Deduplicated Count:  Total={total_items} (Good={good_items}, Defect={defect_items}, Uncertain={uncertain_items})")
            print(f"Tracked Kernels:     {len(tracked_kernels)} kernels tracked across frames without duplication")

            assert len(tracked_kernels) == total_items, f"Tracked kernels {len(tracked_kernels)} != total {total_items}"

            # Verify best photos exist
            best_photos = res.get("best_photo_urls", [])
            for bpu in best_photos:
                disk_path = os.path.join(PROJECT_ROOT, bpu.lstrip('/'))
                assert os.path.isfile(disk_path), f"Best photo missing: {disk_path}"

            # Build markdown per-kernel table
            table_lines = []
            table_lines.append(f"### Per-Kernel Breakdown: {fset['name']} ({material})")
            table_lines.append(f"**Final Decision State**: `{final_dec.get('state')}` | **Suggestion**: {sugg} | **Deduplicated Total**: {total_items} kernels")
            table_lines.append("")
            table_lines.append("| Kernel # | Centroid (x, y) | BBox (w × h) | Observations | Normal Votes | Suspect Votes | Uncertain Votes | Majority Verdict | Reason Why / Details |")
            table_lines.append("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|")

            for tk in tracked_kernels:
                kid = tk["id"]
                cx, cy = tk["centroid"]
                bw = tk["bbox"]["w"]
                bh = tk["bbox"]["h"]
                n_obs = len(tk["observations"])
                vc = tk.get("vote_counts", {})
                maj = tk.get("majority_verdict", "Normal")
                rwhy = tk.get("reason_why", "Normal")
                ai_op = tk.get("ai_opinion", "")
                if ai_op:
                    rwhy += f" [AI: {ai_op}]"

                # Color indicator
                if "suspect" in maj.lower():
                    maj_str = f"🔴 **{maj}**"
                elif "uncertain" in maj.lower():
                    maj_str = f"🟠 **{maj}**"
                else:
                    maj_str = f"🟢 {maj}"

                table_lines.append(
                    f"| #{kid} | ({cx:.2f}, {cy:.2f}) | {bw:.2f} × {bh:.2f} | {n_obs}/5 frames | {vc.get('normal', 0)} | {vc.get('suspect', 0)} | {vc.get('uncertain', 0)} | {maj_str} | {rwhy} |"
                )

            table_md = "\n".join(table_lines)
            tables_output.append(table_md)
            print("\n" + table_md + "\n")

        # Verify "both" mode test with disagreement to REVIEW
        print("=" * 80)
        print("TESTING BOTH MODE (COLOUR MAIN + AI SECOND OPINION)")
        print("=" * 80)
        mock_both_pass = {
            "defect_pct": 0.0,
            "total_items_counted": 4,
            "good_items_counted": 4,
            "defect_items_counted": 0,
            "uncertain_items_counted": 0,
            "material": "Peanut",
            "station_engine": "both",
            "tracked_kernels": [
                {"id": 1, "majority_verdict": "Normal", "reason_why": "Normal (score 12)", "vote_counts": {"normal": 5, "suspect": 0, "uncertain": 0, "total": 5}}
            ]
        }
        dec_pass = final_decision(mock_both_pass)
        print(f"Both Mode Agreement -> Decision: {dec_pass['state']} ({dec_pass['reason']})")
        assert dec_pass["state"] == "PASS"

        mock_both_disagree = {
            "defect_pct": 5.0,
            "total_items_counted": 4,
            "good_items_counted": 3,
            "defect_items_counted": 0,
            "uncertain_items_counted": 1,
            "material": "Peanut",
            "station_engine": "both",
            "tracked_kernels": [
                {"id": 1, "majority_verdict": "Uncertain", "reason_why": "AI/Colour disagreement: colour=Normal, AI=Suspect", "ai_opinion": "Suspect (mold 84%)", "vote_counts": {"normal": 2, "suspect": 1, "uncertain": 2, "total": 5}}
            ]
        }
        dec_disagree = final_decision(mock_both_disagree)
        print(f"Both Mode Disagreement -> Decision: {dec_disagree['state']} ({dec_disagree['reason']})")
        assert dec_disagree["state"] == "REVIEW", f"Expected REVIEW on disagreement, got {dec_disagree['state']}"

        # Write generated tables to file for reference
        out_path = os.path.join(PROJECT_ROOT, "scratch", "saved_frames_report_tables.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n\n---\n\n".join(tables_output))
        print(f"\nTables written to {out_path}")

        return tables_output

if __name__ == "__main__":
    tables = test_saved_frames()
    print("\n" + "=" * 80)
    print("ALL TESTS AND PER-KERNEL TABLES GENERATED SUCCESSFULLY!")
    print("=" * 80)
