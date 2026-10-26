# Part 1: AI Visual Quality Inspection Station

**Team Member**: Member 1 (Computer Vision & AI Lead)  
**Primary System Role**: QC Inspector (`qc@foodman.vn`)  
**Main Screens**: `/qc/camera-station`, `/capture/<token>`, `/qc/calibration`

---

## 1. One-Paragraph Summary

Part 1 provides the sensory intelligence of Food Man: a unified laptop and mobile inspection station that localizes grain defects in real time using edge computer vision. Instead of relying on vulnerable single-shot photographs, this component deploys an industrial dual-engine architecture combining an Ultralytics YOLOv8 convolutional defect detector, a YOLOv8n-cls commodity classifier, and OpenCV CIE Lab Otsu colour segmentation. When an operator holds a sample dish steady for 2.8 seconds, a client-side downsampled motion detector triggers an automated 5-frame locking burst. The server performs spatial kernel tracking and majority voting across all 5 frames, generating a robust consensus verdict (`PASS`, `REVIEW`, `REJECT`, or `RETAKE`). This prevents false alarms from lighting shadows, verifies grain identity, and feeds certified visual telemetry directly into the QC release pipeline.

---

## 2. What This Member Built

### Files & Modules
- **`templates/camera_station.html`** (1,241 lines): Unified Laptop Inspection Station with real-time video viewport, dynamic bounding box overlay canvas, camera diagnostic controls, hold-steady progress bar, and final decision card.
- **`templates/mobile_capture.html`** (1,288 lines): Smartphone companion capture web app paired via dynamic QR code.
- **`templates/qc_calibration.html`** (289 lines): Interactive laboratory calibration tool for colour screening threshold fitting.
- **`static/js/camera_station.js`** (2,230 lines): WebRTC stream management, client-side 48x36 grayscale motion analysis, asynchronous 1 FPS frame dispatch lock, 5-frame locking animation, and override modal handlers.
- **`static/js/live_inspection.js`** (668 lines) & **`static/js/qc_calibration.js`** (584 lines): Telemetry polling and calibration UI.
- **`ai/yolo_service.py`** (574 lines): Neural network runtime, model weight discovery (`models/combined_corrected_best.pt`), letterbox preprocessing, inference execution under global thread lock, and defect taxonomy mapping.
- **`ai/classical_kernel_finder.py`** (607 lines): Paper background illumination estimation in CIE Lab space, Otsu thresholding, distance-transform watershed blob separation, and per-kernel $\Delta E$ colour metrics.
- **`routes/qc.py`** (Inspection station routes, lines ~3600–4450): Token validation, 3 req/sec rate limiting, image decoding, frame retention management, 5-frame locking aggregation, majority voting, and calibration endpoints.
- **Evaluation & Synthesis Scripts**: `scripts/eval_inspection.py`, `scripts/eval_material.py`, `scripts/evaluate_material_classifier.py`, `scripts/make_synthetic_scenes.py`.

### Route Endpoints (21 Routes)
- `GET /qc/camera-station`: Renders unified inspection station interface.
- `GET /capture/<token>`: Mobile phone capture web app interface.
- `POST /api/capture/<token>/frame`: Live frame intake endpoint (rate-limited, JPEG validated, runs YOLO or CIE Lab).
- `POST /api/capture/<token>/reset-lock`: Resets mobile capture locking cycle.
- `POST /api/qc/live-session/create`: Initializes new WebRTC/streaming inspection session with UUID token.
- `GET /api/qc/live-session/active`: Fetches active inspection session for target lot.
- `GET /api/qc/live-session/<id>/latest`: Long-polling telemetry for latest frame and lock status.
- `POST /api/qc/live-session/<id>/close`: Terminates active inspection session.
- `POST /api/qc/live-session/<id>/link-lot`: Binds live session to an intake `RawMaterialLot`.
- `POST /api/qc/live-session/<id>/reset-lock`: Resets laptop inspection lock state.
- `POST /api/qc/ai-inspect`: Laboratory static image upload gateway (5-second emergency fallback).
- `GET /api/qc/ai-model-status`: Hardware & model diagnostic health check.
- `GET /api/qc/debug/latest`: Fetches debug visualization overlay.
- `GET /api/qc/frame/<id>/debug`: Fetches individual frame debug image.
- `GET /qc/calibration`: Admin calibration interface.
- `GET /api/qc/calibration/data`: Retrieves labeled calibration dataset.
- `GET /api/qc/calibration/crop/<frame_id>/<kernel_id>`: Serves individual kernel cut-out.
- `POST /api/qc/calibration/mark`: Stores user ground-truth labels (Normal vs Suspect).
- `POST /api/qc/calibration/fit`: Computes optimal threshold separation without machine learning.
- `POST /api/qc/calibration/reset`: Restores default colour screening thresholds.
- `POST /api/qc/calibration/clear-marks`: Purges user calibration marks.

### Database Tables (3 Tables)
- **`live_sessions`**: Session UUID tokens, expiration (2 hours), assigned lot ID, status (`ACTIVE`, `CLOSED`, `EXPIRED`), locked result JSON blob, and best 3 frame paths.
- **`live_frames`**: Historical inspection frames, image URLs, good/defect counts, confidence, status, and `is_locked` boolean flag.
- **`inspection_station_settings`**: Key-value settings for inspection engine (`yolo`, `colour`, `both`), sensitivity thresholds, ignore zones, and camera device IDs.

### Key Functions
- `ai.yolo_service.run_yolo_visual_inspection(image_input, conf_threshold, iou_threshold)`: Executes forward pass with Non-Maximum Suppression (NMS).
- `ai.classical_kernel_finder.find_kernels_classical(img_input, ignore_zones, suspect_threshold, material)`: OpenCV Lab thresholding & watershed kernel splitting.
- `ai.classical_kernel_finder.estimate_paper_color_lab(img_bgr, ignore_zones)`: Models lens vignetting and lighting gradients.
- `routes.qc.upload_live_frame(token)`: Validates token, rate limits (3 req/sec), enforces disk cleanup (latest frame + 5 locked), triggers lock evaluation.
- `routes.qc.evaluate_locked_frames(session, frames, db, request)`: Aggregates 5 frames, tracks kernels spatially, runs majority voting, outputs `final_decision` object.
- `routes.qc.final_decision(result)`: Enforces the 4-state state machine (`PASS`, `REVIEW`, `REJECT`, `RETAKE`).

### Automated Test Coverage (23 Tests)
- **`tests/test_colour_screening_calibration.py`** (5 tests):
  1. `test_01_kernel_color_metrics_and_scoring`: Median Lab, dark patch pct, unevenness, suspect score.
  2. `test_02_simple_threshold_fitting_no_ml`: Mathematical threshold optimization.
  3. `test_03_login_required_and_calibration_endpoints`: Access security.
  4. `test_04_labels_footer_and_no_mold_in_colour_mode`: Verifies labels strictly use "Suspect (discoloured)", never "mold".
  5. `test_05_sunflower_uses_same_engine_never_gets_pass`: Sunflower safety invariant.
- **`tests/test_final_decision_states.py`** (18 tests):
  - State machine tests covering blurry frames, kernel minimums (< 5 kernels), frame minimums (< 3 usable), agreement ratios, and override justifications.

---

## 3. How It Works (Step-by-Step Flow)

```
[Camera Sensor / Phone WebRTC]
              │ (1 frame per second)
              ▼
[Client Motion Detector (48x36 Grayscale)]
              │ (Hold steady for 2.8s -> mean diff < 7.5)
              ▼
[5-Frame Burst Dispatch (lock=true)]
              │
    ┌─────────┴─────────┐
    ▼                   ▼
[YOLOv8 Defect]   [YOLOv8n-cls / CIE Lab]
 (Fungal Mold)     (Commodity & Colour)
    └─────────┬─────────┘
              ▼
[Spatial Kernel Tracking (Euclidean BBox Matching)]
              ▼
[Majority Voting Across 5 Frames]
              ▼
[Final Decision Engine: PASS / REVIEW / REJECT / RETAKE]
```

1. **Input**: A video stream from an integrated laptop webcam or smartphone paired via Wi-Fi/USB. The specimen dish contains 5–25 kernels of corn, peanuts, or sunflower seeds.
2. **Streaming & Motion Gating**:
   - The browser captures video frames onto a hidden HTML5 canvas.
   - A client-side motion analyzer downsamples the image to a low-resolution 48×36 grayscale grid. It measures the mean pixel intensity difference between successive frames.
   - If movement is high (`difference >= 7.5`), the system stays in preview mode.
   - Once the camera is held steady for ~2.8 seconds with adequate lighting (`luma >= 40`) and item count ($\ge 3$), the progress bar reaches 100% and triggers the **5-Frame Lock Sequence**.
3. **5-Frame Acquisition & Dual-Engine Processing**:
   - The client dispatches 5 rapid sequential frames with HTTP parameter `lock=true`.
   - On the server, `ai/yolo_service.py` executes YOLOv8 object detection under a global thread lock.
   - Concurrently, `ai/classical_kernel_finder.py` estimates paper background chromaticity in CIE Lab space, subtracts lighting vignetting, separates contiguous kernels using watershed distance transforms, and measures colour variance.
   - If enabled (`USE_MATERIAL_CLASSIFIER=1`), `models/material_cls.pt` confirms commodity identity.
4. **Majority Voting & Decision Synthesis**:
   - The server matches kernel bounding boxes across all 5 locked frames using spatial Euclidean centroid tracking.
   - Each kernel's classification across the 5 frames is evaluated by majority vote: if a kernel is labeled defective in at least 3 of 5 frames, it is counted as defective; otherwise, single-frame shadow glares are discarded as transient noise.
   - The `final_decision()` engine checks limits:
     - **RETAKE**: Fewer than 5 kernels detected, fewer than 3 usable frames, or severe blur.
     - **REVIEW**: Material agreement below 70%, commodity mismatch with order metadata, average confidence below threshold, or Sunflower seeds.
     - **REJECT**: Defect percentage exceeds the reject threshold ($\ge 8\%$).
     - **PASS**: Material verified, defect percentage below pass threshold ($\le 5\%$), zero critical mold.
5. **Output**: Normalized bounding box coordinates, Best 3 annotated frame crops, defect percentage, and an immutable JSON verdict saved into `live_sessions.locked_result_json`.

---

## 4. Live Demo Click Path (Step-by-Step)

1. **Role Login**: Sign in as QC Inspector (`qc@foodman.vn` via `/demo-login/qc`).
2. **Open Station**: Navigate to **QC & AI Inspection** -> **Inspection Station** (`http://localhost:5000/qc/camera-station`).
3. **Verify Camera Diagnostics**:
   - Click **⚙️ Camera Setup** in the toolbar.
   - Click **📹 Test Camera**: show camera device resolution (`1280 x 720 HD`) and green `✓ Camera Ready` indicator. Close panel.
4. **Select Target Lot**:
   - In the "Select Target Lot" dropdown, pick **`DEMO-LOT-REL-01 (Corn)`**.
5. **Demonstrate Live Scanning**:
   - Place camera 15–20 cm above the corn sample dish.
   - Point out live green bounding boxes tracking corn kernels at **1 FPS**.
   - Show live HUD telemetry: Material = **Corn**, Good % = **100%**, Defective % = **0%**.
6. **Trigger 5-Frame Lock**:
   - Hold the camera steady for 2.8 seconds.
   - Point out the locking animation: HUD displays *"🎯 Hold steady..."*, progress bar increments to 100%, and sequence reads *"🔒 Locking sample... Frame 1 of 5 ... 5 of 5"*.
7. **Review Final Result Card**:
   - Final verdict renders on screen: Quality State = **✓ PASS**.
   - Show the **Best 3 Specimen Frames** with overlay annotations.
8. **Emergency Fallback (If Physical Camera Fails)**:
   - Navigate to `/qc?view=ai-inspection`.
   - Select lot `DEMO-LOT-REL-01`.
   - Upload `static/uploads/raw/20261017_035528_test_corn.jpg` and click **Run AI Inspection**.
   - Bounding boxes and defect metrics appear in < 1 second.

---

## 5. Spoken Script (2 Minutes)

> *"Good morning committee. I am Member 1, and I developed the Computer Vision and AI Quality Inspection Station for Food Man.*
>
> *In industrial receiving docks, inspecting food grain with a single snapshot is notoriously unreliable. Lighting flickers, conveyor vibrations, and hand tremors create false positives and shadow artifacts. To solve this, we engineered a dual-engine vision system with automated multi-frame locking.*
>
> *Our architecture combines an Ultralytics YOLOv8 defect detector fine-tuned on raw grain, a secondary YOLOv8n-cls material classifier, and OpenCV CIE Lab colour segmentation. The camera feed streams directly into a client-side motion analyzer that downsamples frames to 48x36 grayscale.*
>
> *As you can see on screen, when I position the camera over our intake corn sample, the model identifies each kernel and recognizes the commodity as Corn. To eliminate operator bias, our software monitors camera stability. When I hold the sensor steady for 2.8 seconds, the system automatically captures a rapid 5-frame burst.*
>
> *In the backend, our server tracks each kernel's physical coordinates across all five frames and calculates a majority vote. If a shadow flickers across a kernel for one frame, it is discarded. Only persistent, verified defects are counted. For this sample, the 5-frame consensus confirms zero fungal mycelium and 100% healthy grain, generating a certified quality state of PASS.*
>
> *We also built an interactive calibration tool that models background paper chromaticity in CIE Lab space to catch non-mold discolourations. However, in food safety, visual appearance cannot detect invisible chemical toxins. I now hand over to Member 2 to demonstrate how our release decision engine validates laboratory chemical certificates alongside our vision scores."*

---

## 6. Honest Limitations & Future Work

### Verified Code Limitations (from `docs/AI_MODEL_LIMITATIONS.md`)
1. **Peanut Mold Recall Plateau (~42%–57%)**:
   - `Peanut_Moldy` recall plateaus between 42% and 57% (evaluated at 44.30% at Epoch 50) due to training dataset size (10,227 moldy peanut instances vs over 45,000 for corn). Nascent fungal mycelium can be missed visually.
2. **Zero Sunflower Mold Training Data**:
   - Zero genuine fungal sunflower training instances exist in source datasets. The system **never suggests automatic PASS for sunflower seeds** and routes them to `NEEDS_REVIEW` using CIE Lab colour screening only.
3. **Dense Peanut Pile Misclassification**:
   - Piled or clustered peanuts can be misclassified as corn because the training dataset contained 25,041 clustered corn kernels but only 213 clean peanuts (all photographed as isolated single seeds on white paper).
4. **Optical Estimate Only**:
   - Computer vision scans surface grain coats only; it cannot penetrate seed hulls or detect chemical toxins like Aflatoxin B1 or heavy metals. AI results are strictly advisory.
5. **CPU Inference Latency**:
   - Running full neural network inference on CPU requires ~800ms–1100ms per frame, capped client-side at 1 FPS to prevent thread starvation.

### One Sentence on Future Work
> *"Future work will focus on acquiring 300+ ground-truth industrial dock tray images of bulk clustered peanuts and fungal-inoculated sunflower seeds to retrain the YOLOv8 backbone and break through the peanut mold recall ceiling."*

---

## 7. 10 Likely Questions & Correct Answers

1. **Q: Why does the live video preview run at 1 frame per second instead of 30 FPS?**  
   *A: YOLOv8 neural network inference runs directly on host CPU cores without requiring dedicated GPUs. A full forward pass, non-maximum suppression (NMS), and annotated canvas rendering take ~800–1,000ms. Throttling client transmission to 1 FPS prevents server thread starvation while providing smooth operational telemetry.*
2. **Q: How does the 5-frame locking mechanism prevent false defect detections?**  
   *A: Spatial tracking matches kernel centroids across 5 consecutive frames and computes a majority vote. A kernel is only classified as defective if it is flagged in at least 3 out of 5 frames, filtering out transient lighting shadows and motion glares.*
3. **Q: How does the system recognize which grain commodity is being scanned?**  
   *A: Via a secondary YOLOv8n-cls classification model (`models/material_cls.pt`) trained to identify Peanut, Corn, and Sunflower. If classifier agreement is below 70%, the system flags `REVIEW: Material unclear`.*
4. **Q: What is the purpose of the OpenCV CIE Lab colour screening engine?**  
   *A: It measures Euclidean colour distance ($\Delta E$) from local paper background chromaticity to detect non-mold surface discolouration and scorch marks, providing screening for commodities like sunflower seeds that lack mold training data.*
5. **Q: Can the camera station detect Aflatoxin contamination on peanuts?**  
   *A: Absolutely not. Aflatoxins are microscopic chemical mycotoxins that produce no visible surface alteration at statutory contamination levels (e.g. 2.0 ppb). Aflatoxin certification requires laboratory HPLC or ELISA testing.*
6. **Q: What happens if an operator points the camera at an empty table?**  
   *A: The system detects item count $< 3$, keeps the state as `NO_SPECIMENS`, and refuses to initiate the hold-steady locking sequence.*
7. **Q: Why does Sunflower inspection never output a PASS verdict?**  
   *A: Because zero genuine fungal sunflower images exist in our training datasets. To maintain HACCP compliance and prevent false safety certification, sunflower lots are programmatically forced to `REVIEW` requiring human sign-off.*
8. **Q: What is the purpose of the ignore zone configuration?**  
   *A: In `ai/classical_kernel_finder.py`, ignore zones (defaulting to the bottom-left 22% x 18%) prevent UI watermarks, scale rulers, or dock tray logos from being misidentified as grain kernels.*
9. **Q: What happens if the browser video preview shows a black rectangle?**  
   *A: The station includes an automated black-screen detector that samples frame luminance. If luminance $< 1.5$ for 1.5 seconds, it alerts the user that the phone companion app or virtual webcam driver is disconnected.*
10. **Q: Can the smartphone capture interface authorize the final lot release?**  
    *A: No. Under `routes/qc.py:confirm_live_session_verdict()`, confirming a verdict requires authentication with `RoleEnum.QC` or `RoleEnum.ADMIN`. The unauthenticated mobile interface can only stream capture frames.*

---

## 8. Key Terms to Know

- **YOLOv8 (You Only Look Once v8)**: State-of-the-art single-stage convolutional neural network architecture for real-time object detection and bounding box localization.
- **CIE $L^*a^*b^*$ Colour Space**: Device-independent colour space modeling Lightness ($L^*$), green-red chromaticity ($a^*$), and blue-yellow chromaticity ($b^*$), matching human visual perception.
- **Watershed Algorithm**: Mathematical morphological segmentation technique using distance transform topography to cleanly separate touching or clustered seed kernels.
- **NMS (Non-Maximum Suppression)**: Post-processing algorithm that eliminates redundant, overlapping bounding boxes by filtering candidate regions exceeding an IoU (Intersection-over-Union) threshold.
- **Majority Voting Consensus**: Multi-frame temporal aggregation rule requiring $\ge 3$ out of 5 frames to confirm a defect before flagging the kernel.

---

## 9. What NOT to Claim or Click During Demo

- **DO NOT claim 30 FPS or GPU real-time video processing**: The model runs on CPU at 1 FPS (~1 frame per second).
- **DO NOT claim the camera can detect Aflatoxin, salmonella, or chemical toxins**: It is an optical surface scanner only.
- **DO NOT claim 99% accuracy on moldy peanuts**: Peanut mold recall plateaus at ~42%–57% due to source dataset limitations.
- **DO NOT click `/qc/calibration` during the main live demo**: The calibration tool is an advanced administrative utility and takes time to explain. Keep to `/qc/camera-station`.
- **DO NOT attempt to scan dense, piled mounds of peanuts on camera**: Dense peanut piles will trigger corn misclassification. Keep peanuts in a single-layer flat arrangement.
