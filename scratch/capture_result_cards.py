import asyncio
import json
import base64
import os
import subprocess
import time
import urllib.request
import websockets

ARTIFACT_DIR = r"C:\Users\L E N O V O\.gemini\antigravity-ide\brain\07a95aab-ec1c-4721-acec-0e1f33f6e3b6"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

_mid = 0

async def send_recv(ws, method, params=None, timeout=12):
    global _mid
    _mid += 1
    req = {"id": _mid, "method": method}
    if params:
        req["params"] = params
    await ws.send(json.dumps(req))
    start = time.time()
    while time.time() - start < timeout:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(raw)
            if data.get("id") == _mid:
                return data.get("result", {})
        except asyncio.TimeoutError:
            continue
    print(f"Warning: timeout waiting for {method}", flush=True)
    return {}

async def eval_js(ws, expr):
    return await send_recv(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True})

async def capture_screen(ws, filename):
    res = await send_recv(ws, "Page.captureScreenshot", {"format": "png"})
    out_path = os.path.join(ARTIFACT_DIR, filename)
    if "data" in res:
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(res["data"]))
        print(f"Saved screenshot: {out_path} ({os.path.getsize(out_path)} bytes)", flush=True)
    else:
        print(f"Failed to capture: {filename}", flush=True)

async def run():
    print("Launching Edge headless...", flush=True)
    proc = subprocess.Popen([
        EDGE_PATH,
        "--remote-debugging-port=9227",
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1400,980",
        "about:blank"
    ])

    try:
        await asyncio.sleep(2.5)
        with urllib.request.urlopen("http://127.0.0.1:9227/json/list") as resp:
            targets = json.loads(resp.read().decode())
        page_targets = [t for t in targets if t.get("type") == "page"]
        page_target = page_targets[0] if page_targets else targets[0]
        ws_url = page_target["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=100*1024*1024) as ws:
            await send_recv(ws, "Page.enable")
            await send_recv(ws, "Runtime.enable")
            await send_recv(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1400,
                "height": 980,
                "deviceScaleFactor": 1,
                "mobile": False
            })

            # 1. Login via /demo-login/Admin
            print("Logging in...", flush=True)
            await send_recv(ws, "Page.navigate", {"url": "http://127.0.0.1:5000/demo-login/Admin"})
            await asyncio.sleep(2.5)

            # 2. Navigate to Inspection Station
            print("Navigating to Inspection Station...", flush=True)
            await send_recv(ws, "Page.navigate", {"url": "http://127.0.0.1:5000/qc/station"})
            await asyncio.sleep(2.5)

            # Capture initial station before result
            await capture_screen(ws, "station_01_initial_before.png")

            # 3. Simulate PASS State
            print("Simulating State 1: PASS...", flush=True)
            pass_js = """
            CameraStationApp.displayFinalResultCard({
              material: "Corn",
              confidence_percent: "98%",
              best_frames: [
                { id: 1, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242319891_5348331a.jpg", good_count: 15, defect_count: 0 },
                { id: 2, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242320114_c1b2ca33.jpg", good_count: 15, defect_count: 0 },
                { id: 3, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242320341_4034c41c.jpg", good_count: 15, defect_count: 0 }
              ],
              final_decision: {
                state: "PASS",
                reason: "Material verified as Corn with 0.0% defects, within the 5.0% pass limit.",
                material: "Corn",
                kernels_checked: 15,
                defect_pct: 0.0,
                next_step: "Lot meets visual inspection standards; proceed with standard sign-off.",
                details: [
                  "Material: Corn (Agreement: 100%)",
                  "Kernels checked: 15 across 5 photos used",
                  "Defect rate: 0.0% (Pass limit: 5.0%, Reject limit: 8.0%)",
                  "Average detection confidence: 98%"
                ]
              }
            });
            """
            await eval_js(ws, pass_js)
            await asyncio.sleep(1.0)
            await capture_screen(ws, "station_state_1_pass.png")

            # 4. Simulate REVIEW State (material unclear -> defect_pct is null / Hidden)
            print("Simulating State 2: REVIEW...", flush=True)
            review_js = """
            CameraStationApp.displayFinalResultCard({
              material: "Unknown / mixed",
              confidence_percent: "85%",
              best_frames: [
                { id: 1, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242319891_5348331a.jpg", good_count: 10, defect_count: 2 },
                { id: 2, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242320114_c1b2ca33.jpg", good_count: 10, defect_count: 2 },
                { id: 3, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242320341_4034c41c.jpg", good_count: 10, defect_count: 2 }
              ],
              final_decision: {
                state: "REVIEW",
                reason: "Material identification is unclear (60% agreement, minimum 70% required).",
                material: "Unknown / mixed",
                kernels_checked: 12,
                defect_pct: null,
                next_step: "Inspect tray manually to confirm material type or rescan with clean separation.",
                details: [
                  "Material: Unknown / mixed (Material agreement: 60%)",
                  "Kernels checked: 12 across 5 photos used",
                  "Defect rate: Unverified (hidden from card due to review state)",
                  "Average detection confidence: 85%"
                ]
              }
            });
            """
            await eval_js(ws, review_js)
            await asyncio.sleep(1.0)
            await capture_screen(ws, "station_state_2_review.png")

            # Trigger inline override reason box (clicking Approve lot on REVIEW)
            print("Triggering inline override reason prompt box...", flush=True)
            trigger_reason_js = """
            CameraStationApp.handleAction('APPROVE');
            """
            await eval_js(ws, trigger_reason_js)
            await asyncio.sleep(0.8)
            await capture_screen(ws, "station_state_2_review_override_reason.png")

            # 5. Simulate REJECT State (defect % > reject limit)
            print("Simulating State 3: REJECT...", flush=True)
            reject_js = """
            CameraStationApp.displayFinalResultCard({
              material: "Corn",
              confidence_percent: "96%",
              best_frames: [
                { id: 1, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242319891_5348331a.jpg", good_count: 17, defect_count: 3 },
                { id: 2, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242320114_c1b2ca33.jpg", good_count: 17, defect_count: 3 },
                { id: 3, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242320341_4034c41c.jpg", good_count: 17, defect_count: 3 }
              ],
              final_decision: {
                state: "REJECT",
                reason: "Defect percentage of 15.0% exceeds the allowable reject limit of 8.0%.",
                material: "Corn",
                kernels_checked: 20,
                defect_pct: 15.0,
                next_step: "Quarantine lot immediately and initiate supplier non-conformance workflow.",
                details: [
                  "Material: Corn (Material agreement: 100%)",
                  "Kernels checked: 20 across 5 photos used",
                  "Defect rate: 15.0% (Pass limit: 5.0%, Reject limit: 8.0%)",
                  "Average detection confidence: 96%"
                ]
              }
            });
            """
            await eval_js(ws, reject_js)
            await asyncio.sleep(1.0)
            await capture_screen(ws, "station_state_3_reject.png")

            # 6. Simulate RETAKE State (fewer than 5 kernels)
            print("Simulating State 4: RETAKE...", flush=True)
            retake_js = """
            CameraStationApp.displayFinalResultCard({
              material: "Corn",
              confidence_percent: "92%",
              best_frames: [
                { id: 1, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242319891_5348331a.jpg", good_count: 3, defect_count: 0 }
              ],
              final_decision: {
                state: "RETAKE",
                reason: "Scan has only 3 kernels; at least 5 kernels are required for valid analysis.",
                material: "Corn",
                kernels_checked: 3,
                defect_pct: null,
                next_step: "Hold camera steady with good lighting and rescan with at least 5 kernels in the tray.",
                details: [
                  "Material: Corn (Material agreement: 100%)",
                  "Kernels checked: 3 across 5 photos used",
                  "Defect rate: Unverified (hidden from card due to retake state)",
                  "Average detection confidence: 92%"
                ]
              }
            });
            """
            await eval_js(ws, retake_js)
            await asyncio.sleep(1.0)
            await capture_screen(ws, "station_state_4_retake.png")

            # 7. Simulate Peanut Result (verifying footer line and expanded details)
            print("Simulating Peanut Result with screening footer...", flush=True)
            peanut_js = """
            CameraStationApp.displayFinalResultCard({
              material: "Peanut",
              confidence_percent: "97%",
              best_frames: [
                { id: 1, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242319891_5348331a.jpg", good_count: 24, defect_count: 1 },
                { id: 2, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242320114_c1b2ca33.jpg", good_count: 24, defect_count: 1 },
                { id: 3, annotated_path: "/static/uploads/live_frames/annotated/annotated_live_100_1792242320341_4034c41c.jpg", good_count: 24, defect_count: 1 }
              ],
              final_decision: {
                state: "PASS",
                reason: "Material verified as Peanut with 4.0% defects, within the 5.0% pass limit.",
                material: "Peanut",
                kernels_checked: 25,
                defect_pct: 4.0,
                next_step: "Lot meets visual inspection standards; proceed with standard sign-off.",
                details: [
                  "Material: Peanut (Material agreement: 97%)",
                  "Kernels checked: 25 across 5 photos used",
                  "Defect rate: 4.0% (Pass limit: 5.0%, Reject limit: 8.0%)",
                  "Average detection confidence: 97%",
                  "Camera screening only. Peanut lots need lab testing before release."
                ]
              }
            });
            """
            await eval_js(ws, peanut_js)
            await asyncio.sleep(0.5)

            # Scroll card into view to capture photos, details, and peanut footer
            scroll_card_js = """
            const card = document.getElementById('stationResultCard');
            if (card) card.scrollIntoView({ behavior: 'instant', block: 'center' });
            """
            await eval_js(ws, scroll_card_js)
            await asyncio.sleep(0.5)
            await capture_screen(ws, "station_state_peanut_footer.png")

            # Open "How was this decided?" details section
            open_details_js = """
            const d = document.getElementById('stationHowDecided');
            if (d) d.open = true;
            """
            await eval_js(ws, open_details_js)
            await asyncio.sleep(0.5)
            await capture_screen(ws, "station_how_decided_expanded.png")

            # 8. Navigate to Dashboard and capture rebuilt live card
            print("Navigating to Dashboard...", flush=True)
            await send_recv(ws, "Page.navigate", {"url": "http://127.0.0.1:5000/dashboard"})
            await asyncio.sleep(2.5)

            # Scroll into view of the live card
            scroll_js = """
            const el = document.getElementById('dashLatestResultBox');
            if (el) el.scrollIntoView({ behavior: 'instant', block: 'center' });
            """
            await eval_js(ws, scroll_js)
            await asyncio.sleep(1.0)
            await capture_screen(ws, "dashboard_live_card_rebuilt.png")

            print("All screenshots successfully captured!", flush=True)

    finally:
        proc.terminate()
        print("Headless Edge terminated.", flush=True)

if __name__ == "__main__":
    asyncio.run(run())
