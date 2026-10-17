# One-Page Live Demo Script: QC AI Camera Inspection

**Total Presentation Time**: 2–3 minutes  
**Goal**: Demonstrate real-time YOLOv8 food defect detection running on a laptop inspection station with a smartphone webcam, including a seamless 5-second fallback if physical hardware fails.

---

## 1. Quick Setup (Pre-Demo Checklist — 60 Seconds)

1. **Start System**: Double-click the **Food Man** desktop icon (or run `python wsgi.py`).  
   Open [http://localhost:5000](http://localhost:5000) in Chrome or Edge.
2. **Phone as Webcam** (Recommended):
   - Launch **Iriun Webcam** (or DroidCam) on your phone and laptop.
   - Connect via **USB cable** (or ensure both are on the same Wi-Fi / phone hotspot).
3. **Specimen Ready**: Place a small sample tray with 5–20 kernels of Corn or Peanuts on the desk.

---

## 2. Live Demo Script (Step-by-Step)

### Step 1: Open Inspection Station (30 Seconds)
1. Sign in as **QC Inspector** (`qc@foodman.vn` / `password123`) or **Admin** (`admin@foodman.vn`).
2. Click **QC & AI Inspection** -> **Inspection Station** in the sidebar (or navigate directly to `http://localhost:5000/qc/camera-station`).
3. Point out the interface to the audience:
   - *"This is our unified laptop inspection station with real-time AI bounding boxes, multi-camera switching, and an automated multi-frame hold-steady lock."*

### Step 2: Camera Setup & Diagnostics Verification (20 Seconds)
1. Click **⚙️ Camera Setup** on the toolbar.
2. In the setup panel, click **📹 Test Camera**:
   - Show the detected camera list (e.g. `Iriun Webcam (Phone)` and `Integrated Webcam`).
   - Highlight the resolution telemetry: **`1280 × 720 (16:9 HD)`** and green **`✓ Camera Ready`** diagnostic.
3. Close the panel.

### Step 3: Real-Time Scanning & Hold-Steady Lock (45 Seconds)
1. Position the phone camera **15–25 cm above the specimen tray**.
2. Point out the live telemetry on screen:
   - Green bounding boxes tracking healthy kernels in real time at **1 FPS**.
   - Material automatically recognized as **Corn** (or Peanuts).
   - Live **Good %** and **Defective %** meters.
3. Hold the camera steady for **~2.8 seconds**:
   - The HUD changes to: *"🎯 Hold steady..."*
   - Green progress bar fills along the bottom: `20%` -> `50%` -> `100%`.
   - Sequence triggers: *"🔒 Locking sample... Frame 1 of 5 ... 5 of 5"*.

### Step 4: Final Verdict & Official Sign-Off (30 Seconds)
1. The **Final Result Card** appears:
   - Metrics: **Good: 100%**, **Defective: 0%**, Verdict: **✓ PASS**.
   - Review the **Best 3 Annotated Specimen Frames**.
2. Click **"✓ Confirm Accept (Approved)"**.
   - Status updates: *"Verdict Confirmed! Lot status updated in database."*
3. Click **"📄 Download PDF Report"** -> Opens official Certificate of Analysis / AI Inspection Dossier in a new tab.
4. Click **"Scan Next Sample"** to reset the viewport for the next batch.

### Step 5: Dashboard Executive Visibility (15 Seconds)
1. Navigate to **Executive Dashboard** (`http://localhost:5000/dashboard`).
2. Scroll to the **Live Camera QC Inspection** card:
   - Show **Today's Inspection Counters** automatically incremented (*Samples Checked*, *Pass*).
   - Point to the **Latest Final Result** strip showing the specimen, time, and verdict.

---

## 3. Emergency Presentation Fallback (If Hardware Camera Fails)

> [!TIP]
> If the phone app disconnects, the Wi-Fi drops, or the browser shows a black preview / permission error during the live presentation, **do not debug in front of the audience**. Pivot instantly with this script:

### The Scripted Pivot (5 Seconds):
> *"While our camera station runs in real time, Food Man also provides an instant laboratory upload gateway for intake samples taken in the field."*

1. Click **QC & AI Inspection** -> **YOLO AI Inspection** (`/qc?view=ai-inspection`).
2. Select any target lot from the dropdown.
3. In the upload box, pick any pre-loaded raw sample:
   - `static/uploads/raw/20260910_065827_corn_cluster.jpg`
4. Click **Run AI Inspection**:
   - Neural network runs instant inference.
   - Bounding boxes, defect breakdown, and Pass recommendation render in **< 1 second**.
   - Click **Save QC Result** to complete the demonstration flawlessly.

---

*One-Page Demo Script — Food Man Quality Control AI Vision System*
