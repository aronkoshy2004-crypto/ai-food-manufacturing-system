/**
 * FOOD MAN - QC LAPTOP INSPECTION STATION CONTROLLER (PHASE 2)
 * Features:
 * 1. Automatic/manual internal live session behind the scenes (zero token/QR exposure)
 * 2. Hardware camera selector using enumerateDevices, localStorage persistence, deviceId exact
 * 3. LAN HTTP insecure mode detection with "Open localhost version" button
 * 4. "Flip image" container transform ensuring overlay canvas boxes stay 100% aligned
 * 5. 1 FPS live stream at 960-1280px, strictly one request at a time
 * 6. 48x36 steady analyzer & 5-frame lock evaluation
 * 7. Complete final result card with Accept/Reject sign-off, PDF download, and "Scan next sample"
 */

const CameraStationApp = (() => {
  // Config & Session State (injected by template)
  let sessionToken = null;
  let sessionId = null;
  let currentLotId = null;

  // Stream & Camera state
  // Stream & Camera state
  let videoStream = null;
  let isCameraRunning = false;
  let isUploading = false;
  let isLocking = false;
  let isLockedResultShowing = false;
  let lastLockedResult = null;
  let liveLoopTimer = null;
  let steadinessTimer = null;

  // Stabilized Burst Scan & Station Mode State (Default: 'scan')
  let stationMode = 'scan';
  let isBurstScanning = false;

  // Phase 4: Test Camera State
  let testStream = null;
  let isTestingCamera = false;
  let testBlackCheckTimer = null;

  // Steadiness tracking
  let prevSamplePixels = null;
  let steadyDuration = 0;
  const STEADY_REQ_MS = 2800; // ~3 seconds of steady holding
  let latestItemCount = 0;

  // DOM Elements cache
  let dom = {};

  // Session URLs for pairing
  let sessionUrls = null;
  let selectedUploadFiles = [];

  function init(config) {
    sessionToken = config.token;
    sessionId = config.sessionId;
    currentLotId = config.lotId;
    sessionUrls = config.sessionUrls || null;

    cacheDomElements();
    setupEventListeners();
    updateScanModeFromSelectedLot();
    setStationMode(localStorage.getItem('foodman_station_ui_mode') || 'scan');
    checkSecureContext();
  }

  function cacheDomElements() {
    dom = {
      stageContainer: document.getElementById('cameraStageContainer'),
      videoElem: document.getElementById('liveVideo'),
      overlayCanvas: document.getElementById('overlayCanvas'),
      lotSelect: document.getElementById('stationLotSelect'),
      cameraSelect: document.getElementById('stationCameraSelect'),
      cameraSelectContainer: document.getElementById('cameraSelectContainer'),
      flipToggle: document.getElementById('flipCameraToggle'),
      btnStartCamera: document.getElementById('btnStartCamera'),
      btnOpenLocalhost: document.getElementById('btnOpenLocalhost'),
      lanHttpBanner: document.getElementById('lanHttpWarningBanner'),
      alertBanner: document.getElementById('stationAlertBanner'),
      alertBannerText: document.getElementById('stationAlertBannerText'),

      // Auto-save badge
      stationLotSavedBadge: document.getElementById('stationLotSavedBadge'),
      stationLotSavedBadgeText: document.getElementById('stationLotSavedBadgeText'),

      // Modals & Toolbar Buttons
      pairPhoneModal: document.getElementById('pairPhoneModal'),
      btnTogglePairPhoneModal: document.getElementById('btnTogglePairPhoneModal'),
      btnClosePairPhoneModal: document.getElementById('btnClosePairPhoneModal'),
      stationQrImg: document.getElementById('stationQrImg'),
      stationCaptureUrl: document.getElementById('stationCaptureUrl'),
      btnCopyStationLink: document.getElementById('btnCopyStationLink'),
      btnStationModeTunnel: document.getElementById('btnStationModeTunnel'),
      btnStationModeLan: document.getElementById('btnStationModeLan'),

      photoUploadModal: document.getElementById('photoUploadModal'),
      btnTogglePhotoUploadModal: document.getElementById('btnTogglePhotoUploadModal'),
      btnClosePhotoUploadModal: document.getElementById('btnClosePhotoUploadModal'),
      photoDropzone: document.getElementById('photoDropzone'),
      photoFileInput: document.getElementById('photoFileInput'),
      photoFilesPreview: document.getElementById('photoFilesPreview'),
      photoFilesCount: document.getElementById('photoFilesCount'),
      photoFilesList: document.getElementById('photoFilesList'),
      btnExecutePhotoUpload: document.getElementById('btnExecutePhotoUpload'),
      btnCancelPhotoUpload: document.getElementById('btnCancelPhotoUpload'),
      photoUploadStatus: document.getElementById('photoUploadStatus'),

      qcMeasuresModal: document.getElementById('stationQcMeasuresModal'),
      btnToggleQcMeasuresModal: document.getElementById('btnToggleQcMeasuresModal'),
      btnCloseQcMeasuresModal: document.getElementById('btnCloseQcMeasuresModal'),
      formStationQcMeasures: document.getElementById('formStationQcMeasures'),
      qcMeasuresTargetLotBadge: document.getElementById('qcMeasuresTargetLotBadge'),
      qcModalLotSubtitle: document.getElementById('qcModalLotSubtitle'),
      qcMeasuresDocNumber: document.getElementById('qcMeasuresDocNumber'),
      qcMeasuresAccreditation: document.getElementById('qcMeasuresAccreditation'),
      qcMeasuresMoisture: document.getElementById('qcMeasuresMoisture'),
      qcMeasuresAflatoxin: document.getElementById('qcMeasuresAflatoxin'),
      qcMeasuresFfa: document.getElementById('qcMeasuresFfa'),
      qcMeasuresPurity: document.getElementById('qcMeasuresPurity'),
      qcMeasuresStatusBanner: document.getElementById('qcMeasuresStatusBanner'),
      btnCancelQcMeasures: document.getElementById('btnCancelQcMeasures'),

      // Phase 4: Camera Setup & Diagnostics Elements
      setupPanel: document.getElementById('cameraSetupPanel'),
      btnToggleSetup: document.getElementById('btnToggleCameraSetup'),
      btnCloseSetup: document.getElementById('btnCloseCameraSetup'),
      detectedCamerasCount: document.getElementById('detectedCamerasCount'),
      detectedCamerasList: document.getElementById('detectedCamerasList'),
      btnRefreshDeviceList: document.getElementById('btnRefreshDeviceList'),
      scanModeSelect: document.getElementById('stationScanModeSelect'),
      btnTestCamera: document.getElementById('btnTestCamera'),
      btnStopTestCamera: document.getElementById('btnStopTestCamera'),
      testResolutionBadge: document.getElementById('testResolutionBadge'),
      testVideo: document.getElementById('testVideo'),
      testVideoPlaceholder: document.getElementById('testVideoPlaceholder'),
      testVideoOverlayBadge: document.getElementById('testVideoOverlayBadge'),
      testCameraActiveLabel: document.getElementById('testCameraActiveLabel'),
      cameraDiagnosticBox: document.getElementById('cameraDiagnosticBox'),

      // HUD Elements
      hudMaterial: document.getElementById('hudMaterial'),
      hudGoodPct: document.getElementById('hudGoodPct'),
      hudDefectPct: document.getElementById('hudDefectPct'),
      hudTotalCount: document.getElementById('hudTotalCount'),
      hudGuidance: document.getElementById('hudGuidance'),
      hudGuidanceIcon: document.getElementById('hudGuidanceIcon'),
      hudGuidanceText: document.getElementById('hudGuidanceText'),
      steadyBarContainer: document.getElementById('steadyBarContainer'),
      steadyBarFill: document.getElementById('steadyBarFill'),

      // View sections
      liveSection: document.getElementById('stationLiveSection'),
      resultCard: document.getElementById('stationResultCard'),

      // Result Card Elements (Rebuilt Component)
      cardStatusBanner: document.getElementById('cardStatusBanner'),
      cardStatusIcon: document.getElementById('cardStatusIcon'),
      cardStatusTitle: document.getElementById('cardStatusTitle'),
      cardStatusReason: document.getElementById('cardStatusReason'),
      cardStatMaterial: document.getElementById('cardStatMaterial'),
      cardStatKernels: document.getElementById('cardStatKernels'),
      cardStatKernelsSub: document.getElementById('cardStatKernelsSub'),
      cardSummaryRow: document.getElementById('cardSummaryRow'),
      cardSummaryHeadline: document.getElementById('cardSummaryHeadline'),
      cardSummaryBadges: document.getElementById('cardSummaryBadges'),
      cardStatDefectVal: document.getElementById('cardStatDefectVal'),
      cardStatDefectNote: document.getElementById('cardStatDefectNote'),
      cardNextStepText: document.getElementById('cardNextStepText'),
      cardOverrideReasonBox: document.getElementById('cardOverrideReasonBox'),
      cardOverrideReasonLabel: document.getElementById('cardOverrideReasonLabel'),
      cardOverrideReasonInput: document.getElementById('cardOverrideReasonInput'),
      cardActionButtonsRow: document.getElementById('cardActionButtonsRow'),
      resBestFramesGrid: document.getElementById('stationBestFramesGrid'),
      howDecided: document.getElementById('stationHowDecided'),
      howDecidedContent: document.getElementById('stationHowDecidedContent'),
      peanutFooter: document.getElementById('stationPeanutFooter'),
      verdictNotice: document.getElementById('stationVerdictConfirmedNotice'),
      verdictNoticeText: document.getElementById('stationVerdictNoticeText'),
      pdfReportLink: document.getElementById('stationPdfReportLink'),

      // Engine, Ignore Zones & Validation Settings
      engineSelect: document.getElementById('stationEngineSelect'),
      ignoreZonesToggle: document.getElementById('stationIgnoreZonesToggle'),
      minKernelsInput: document.getElementById('stationMinKernelsInput'),
      btnToggleDebugView: document.getElementById('btnToggleDebugView'),

      // Classical Kernel Finder Debug View Modal Elements
      debugModal: document.getElementById('debugViewModal'),
      btnCloseDebugModal: document.getElementById('btnCloseDebugModal'),
      btnRefreshDebugModal: document.getElementById('btnRefreshDebugModal'),
      debugModalLoading: document.getElementById('debugModalLoading'),
      debugModalContent: document.getElementById('debugModalContent'),
      debugModalImage: document.getElementById('debugModalImage'),
      debugStatKernels: document.getElementById('debugStatKernels'),
      debugStatIgnored: document.getElementById('debugStatIgnored'),
      debugStatPaperLab: document.getElementById('debugStatPaperLab'),
      debugStatOtsu: document.getElementById('debugStatOtsu'),

      // Per-Kernel Breakdown & Kernel Inspector Modal Elements (Requirement 2 & 4)
      perKernelContainer: document.getElementById('stationPerKernelContainer'),
      perKernelCountBadge: document.getElementById('stationPerKernelCountBadge'),
      perKernelTableBody: document.getElementById('stationPerKernelTableBody'),
      kernelInspectorModal: document.getElementById('kernelInspectorModal'),
      btnCloseKernelInspector: document.getElementById('btnCloseKernelInspector'),
      kernelInspectorImage: document.getElementById('kernelInspectorImage'),
      kernelHotspotsLayer: document.getElementById('kernelHotspotsLayer'),
      kernelDetailCard: document.getElementById('kernelDetailCard'),
      kernelDetailTitle: document.getElementById('kernelDetailTitle'),
      kernelDetailBadge: document.getElementById('kernelDetailBadge'),
      kernelDetailWhy: document.getElementById('kernelDetailWhy'),
      kernelDetailOpinion: document.getElementById('kernelDetailOpinion'),

      // Stabilized Scan & Framing Guide Elements (Requirements 1, 4, 5)
      btnModeScan: document.getElementById('btnModeScan'),
      btnModeLive: document.getElementById('btnModeLive'),
      scanTipsBar: document.getElementById('scanTipsBar'),
      scanFramingGuide: document.getElementById('scanFramingGuide'),
      scanActionControlBar: document.getElementById('scanActionControlBar'),
      btnTriggerScan: document.getElementById('btnTriggerScan'),
      scanProgressOverlay: document.getElementById('scanProgressOverlay'),
      scanProgressTitle: document.getElementById('scanProgressTitle'),
      scanProgressSubtitle: document.getElementById('scanProgressSubtitle'),
      scanProgressBar: document.getElementById('scanProgressBar')
    };
  }

  // Preselect product mode from selected Lot's data-material (Auto if none)
  function updateScanModeFromSelectedLot() {
    if (!dom.lotSelect || !dom.scanModeSelect) return;
    const selectedOpt = dom.lotSelect.options[dom.lotSelect.selectedIndex];
    if (!selectedOpt) return;

    const matAttr = (selectedOpt.getAttribute('data-material') || '').trim();
    if (!matAttr) {
      dom.scanModeSelect.value = 'Auto';
      return;
    }

    let matched = false;
    for (let i = 0; i < dom.scanModeSelect.options.length; i++) {
      const optVal = dom.scanModeSelect.options[i].value;
      if (optVal.toLowerCase() === matAttr.toLowerCase() ||
          matAttr.toLowerCase().includes(optVal.toLowerCase())) {
        dom.scanModeSelect.selectedIndex = i;
        matched = true;
        break;
      }
    }
    if (!matched) {
      dom.scanModeSelect.value = 'Auto';
    }
  }

  // Station Mode Switcher: 'scan' (default) vs 'live' (experimental live preview)
  function setStationMode(mode) {
    stationMode = mode || 'scan';
    localStorage.setItem('foodman_station_ui_mode', stationMode);

    if (stationMode === 'scan') {
      // 1. Scan mode: plain live preview with framing guide & tips, no overlay boxes
      if (dom.btnModeScan) {
        dom.btnModeScan.style.background = '#4F46E5';
        dom.btnModeScan.style.color = '#FFFFFF';
      }
      if (dom.btnModeLive) {
        dom.btnModeLive.style.background = 'transparent';
        dom.btnModeLive.style.color = '#475569';
      }

      if (dom.scanFramingGuide) dom.scanFramingGuide.style.display = 'flex';
      if (dom.scanTipsBar) dom.scanTipsBar.style.display = 'flex';
      if (dom.scanActionControlBar) dom.scanActionControlBar.style.display = 'flex';
      if (dom.hudGuidance) dom.hudGuidance.style.display = 'none';
      if (dom.steadyBarContainer) dom.steadyBarContainer.style.display = 'none';

      // Stop 1 FPS live loop & steadiness tracker to prevent overlay boxes & background load
      if (liveLoopTimer) {
        clearInterval(liveLoopTimer);
        liveLoopTimer = null;
      }
      if (steadinessTimer) {
        clearInterval(steadinessTimer);
        steadinessTimer = null;
      }

      // Clear any remaining overlay boxes
      if (dom.overlayCanvas) {
        const ctx = dom.overlayCanvas.getContext('2d');
        ctx.clearRect(0, 0, dom.overlayCanvas.width, dom.overlayCanvas.height);
      }

      if (dom.hudMaterial) dom.hudMaterial.textContent = "Plain Preview";
      if (dom.hudTotalCount) dom.hudTotalCount.textContent = "Ready to scan";
      if (dom.hudGoodPct) dom.hudGoodPct.textContent = "--%";
      if (dom.hudDefectPct) dom.hudDefectPct.textContent = "--%";

    } else {
      // 2. Experimental Live Mode: 1 FPS live loop + hold-steady analyzer + live bounding boxes
      if (dom.btnModeLive) {
        dom.btnModeLive.style.background = '#EF4444';
        dom.btnModeLive.style.color = '#FFFFFF';
      }
      if (dom.btnModeScan) {
        dom.btnModeScan.style.background = 'transparent';
        dom.btnModeScan.style.color = '#475569';
      }

      if (dom.scanFramingGuide) dom.scanFramingGuide.style.display = 'none';
      if (dom.scanTipsBar) dom.scanTipsBar.style.display = 'none';
      if (dom.scanActionControlBar) dom.scanActionControlBar.style.display = 'none';

      if (isCameraRunning && !isLockedResultShowing) {
        startSteadinessDetector();
        startLiveStreamLoop();
        updateGuidance("Position specimen sample in view", "🎯");
      }
    }
  }

  // Execute Stabilized 8-Frame Burst Scan at Full Resolution
  async function executeBurstScan() {
    if (!isCameraRunning || !dom.videoElem || dom.videoElem.readyState < 2) {
      alert("Please ensure the camera is running before scanning.");
      return;
    }
    if (isBurstScanning) return;
    isBurstScanning = true;

    if (dom.btnTriggerScan) {
      dom.btnTriggerScan.disabled = true;
      dom.btnTriggerScan.style.opacity = '0.6';
    }

    if (dom.scanProgressOverlay) {
      dom.scanProgressOverlay.style.display = 'flex';
      if (dom.scanProgressBar) dom.scanProgressBar.style.width = '10%';
      if (dom.scanProgressTitle) dom.scanProgressTitle.textContent = 'Capturing Burst...';
      if (dom.scanProgressSubtitle) dom.scanProgressSubtitle.textContent = 'Capturing 8 frames over ~2 seconds at full camera resolution';
    }

    try {
      const vWidth = dom.videoElem.videoWidth || 1280;
      const vHeight = dom.videoElem.videoHeight || 720;

      const burstCanvas = document.createElement('canvas');
      burstCanvas.width = vWidth;
      burstCanvas.height = vHeight;
      const burstCtx = burstCanvas.getContext('2d');

      const burstBlobs = [];
      const totalFrames = 8;
      const intervalMs = 250; // 8 frames * 250ms = 2.0s burst duration

      for (let i = 0; i < totalFrames; i++) {
        burstCtx.drawImage(dom.videoElem, 0, 0, vWidth, vHeight);
        const blob = await new Promise(resolve => burstCanvas.toBlob(resolve, 'image/jpeg', 0.95));
        if (blob) {
          burstBlobs.push(blob);
        }

        const pct = Math.round(10 + ((i + 1) / totalFrames) * 35);
        if (dom.scanProgressBar) dom.scanProgressBar.style.width = `${pct}%`;
        if (dom.scanProgressTitle) dom.scanProgressTitle.textContent = `Capturing Frame ${i + 1} of ${totalFrames}...`;

        if (i < totalFrames - 1) {
          await new Promise(r => setTimeout(r, intervalMs));
        }
      }

      if (burstBlobs.length === 0) {
        throw new Error("Failed to capture any frames from camera.");
      }

      if (dom.scanProgressTitle) dom.scanProgressTitle.textContent = 'Analyzing Frames with AI Detector...';
      if (dom.scanProgressSubtitle) dom.scanProgressSubtitle.textContent = 'Selecting 5 sharpest frames (Laplacian variance) & merging kernels (imgsz 640)...';
      if (dom.scanProgressBar) dom.scanProgressBar.style.width = '60%';

      const formData = new FormData();
      burstBlobs.forEach((blob, idx) => {
        formData.append('images', blob, `frame_${idx}.jpg`);
      });

      const activeScanMode = dom.scanModeSelect ? dom.scanModeSelect.value : (localStorage.getItem('foodman_scan_mode') || 'Auto');
      formData.append('scan_mode', activeScanMode);
      formData.append('imgsz', '640');
      formData.append('confidence_floor', '0.25');

      const minKernels = getMinScanKernels();
      formData.append('min_scan_kernels', minKernels);

      if (isIgnoreZoneActive()) {
        formData.append('ignore_zones', JSON.stringify([getIgnoreZone()]));
      }

      // Smooth progress animation ticker
      let animProgress = 62;
      const progressTimer = setInterval(() => {
        if (animProgress < 92) {
          animProgress += 3;
          if (dom.scanProgressBar) dom.scanProgressBar.style.width = `${animProgress}%`;
        }
      }, 200);

      const res = await fetch(`/api/capture/${sessionToken}/burst-scan`, {
        method: 'POST',
        body: formData
      });

      clearInterval(progressTimer);
      if (dom.scanProgressBar) dom.scanProgressBar.style.width = '100%';

      const data = await res.json();

      if (!res.ok || !data.success) {
        alert("Scan analysis error: " + (data.error || "Failed to process scan."));
        if (dom.scanProgressOverlay) dom.scanProgressOverlay.style.display = 'none';
        isBurstScanning = false;
        if (dom.btnTriggerScan) {
          dom.btnTriggerScan.disabled = false;
          dom.btnTriggerScan.style.opacity = '1';
        }
        return;
      }

      // Small pause to show completion
      await new Promise(r => setTimeout(r, 220));
      if (dom.scanProgressOverlay) dom.scanProgressOverlay.style.display = 'none';

      if (data.locked_result) {
        displayFinalResultCard(data.locked_result);
      }

    } catch (err) {
      console.error("Burst scan error:", err);
      alert("Error executing scan: " + err.message);
      if (dom.scanProgressOverlay) dom.scanProgressOverlay.style.display = 'none';
    } finally {
      isBurstScanning = false;
      if (dom.btnTriggerScan) {
        dom.btnTriggerScan.disabled = false;
        dom.btnTriggerScan.style.opacity = '1';
      }
    }
  }

  function getIgnoreZone() {
    return { x: 0.0, y: 0.82, w: 0.22, h: 0.18 };
  }

  function isIgnoreZoneActive() {
    if (dom.ignoreZonesToggle) return dom.ignoreZonesToggle.checked;
    return localStorage.getItem('foodman_ignore_zones_enabled') !== '0';
  }

  function getMinScanKernels() {
    if (dom.minKernelsInput) {
      const v = parseInt(dom.minKernelsInput.value, 10);
      if (!isNaN(v) && v > 0) return v;
    }
    const saved = parseInt(localStorage.getItem('foodman_min_scan_kernels') || '3', 10);
    return isNaN(saved) || saved <= 0 ? 3 : saved;
  }

  async function openDebugModal() {
    if (!dom.debugModal) return;
    dom.debugModal.style.display = 'flex';
    if (dom.debugModalLoading) {
      dom.debugModalLoading.style.display = 'block';
      dom.debugModalLoading.innerHTML = '<div style="font-size:24px;margin-bottom:8px;">⏳</div><div>Loading classical kernel segmentation debug view...</div>';
    }
    if (dom.debugModalContent) dom.debugModalContent.style.display = 'none';

    try {
      const res = await fetch('/api/qc/debug/latest');
      const data = await res.json();
      if (data.success && data.debug_image_url) {
        if (dom.debugModalImage) {
          dom.debugModalImage.src = `${data.debug_image_url}?t=${Date.now()}`;
        }
        if (dom.debugStatKernels) dom.debugStatKernels.textContent = data.total_kernels;
        if (dom.debugStatIgnored) dom.debugStatIgnored.textContent = data.ignored_count;
        if (dom.debugStatPaperLab) {
          const lab = data.paper_lab || [0, 0, 0];
          dom.debugStatPaperLab.textContent = `L:${lab[0]} a:${lab[1]} b:${lab[2]}`;
        }
        if (dom.debugStatOtsu) dom.debugStatOtsu.textContent = data.otsu_threshold;

        if (dom.debugModalLoading) dom.debugModalLoading.style.display = 'none';
        if (dom.debugModalContent) dom.debugModalContent.style.display = 'flex';
      } else {
        if (dom.debugModalLoading) {
          dom.debugModalLoading.innerHTML = `<div style="color:#EF4444;">⚠️ ${data.error || 'Failed to load debug view.'}</div>`;
        }
      }
    } catch (e) {
      if (dom.debugModalLoading) {
        dom.debugModalLoading.innerHTML = '<div style="color:#EF4444;">⚠️ Network error fetching classical debug view.</div>';
      }
    }
  }

  function closeDebugModal() {
    if (dom.debugModal) dom.debugModal.style.display = 'none';
  }

  function setupEventListeners() {
    // 1. Flip toggle
    if (dom.flipToggle) {
      const savedFlip = localStorage.getItem('foodman_camera_flipped') === '1';
      dom.flipToggle.checked = savedFlip;
      if (dom.stageContainer) {
        dom.stageContainer.classList.toggle('flipped', savedFlip);
      }
      dom.flipToggle.addEventListener('change', () => {
        const isFlipped = dom.flipToggle.checked;
        localStorage.setItem('foodman_camera_flipped', isFlipped ? '1' : '0');
        if (dom.stageContainer) {
          dom.stageContainer.classList.toggle('flipped', isFlipped);
        }
      });
    }

    // 2. Camera selector dropdown
    if (dom.cameraSelect) {
      dom.cameraSelect.addEventListener('change', async () => {
        const selectedId = dom.cameraSelect.value;
        if (selectedId) {
          localStorage.setItem('foodman_camera_device_id', selectedId);
        }
        await restartCameraStream();
      });
    }

    // 3. Lot selector dropdown
    if (dom.lotSelect) {
      dom.lotSelect.addEventListener('change', async () => {
        const newLotId = dom.lotSelect.value;
        currentLotId = newLotId ? parseInt(newLotId, 10) : null;
        updateScanModeFromSelectedLot();
        await linkSessionLot(currentLotId);
      });
    }

    // 3b. Scan mode dropdown (Phase 3 Requirement 4)
    if (dom.scanModeSelect) {
      const savedMode = localStorage.getItem('foodman_scan_mode') || 'Auto';
      dom.scanModeSelect.value = savedMode;
      dom.scanModeSelect.addEventListener('change', () => {
        const mode = dom.scanModeSelect.value || 'Auto';
        localStorage.setItem('foodman_scan_mode', mode);
      });
    }

    // 3c. Engine dropdown (Setting ENGINE: ai | auto | colour | both)
    if (dom.engineSelect) {
      const savedEngine = localStorage.getItem('foodman_inspection_engine') || 'ai';
      dom.engineSelect.value = savedEngine;
      dom.engineSelect.addEventListener('change', () => {
        const eng = dom.engineSelect.value || 'ai';
        localStorage.setItem('foodman_inspection_engine', eng);
      });
    }

    // 3d. Ignore zones toggle
    if (dom.ignoreZonesToggle) {
      const savedIz = localStorage.getItem('foodman_ignore_zones_enabled');
      dom.ignoreZonesToggle.checked = savedIz !== '0';
      dom.ignoreZonesToggle.addEventListener('change', () => {
        localStorage.setItem('foodman_ignore_zones_enabled', dom.ignoreZonesToggle.checked ? '1' : '0');
        drawBoxesOnCanvas([]);
      });
    }

    // 3e. Minimum scan kernels setting
    if (dom.minKernelsInput) {
      const savedMin = localStorage.getItem('foodman_min_scan_kernels') || '3';
      dom.minKernelsInput.value = savedMin;
      dom.minKernelsInput.addEventListener('change', () => {
        localStorage.setItem('foodman_min_scan_kernels', dom.minKernelsInput.value || '3');
      });
    }

    // 3f. Debug View Modal listeners
    if (dom.btnToggleDebugView) {
      dom.btnToggleDebugView.addEventListener('click', openDebugModal);
    }
    if (dom.btnCloseDebugModal) {
      dom.btnCloseDebugModal.addEventListener('click', closeDebugModal);
    }
    if (dom.btnRefreshDebugModal) {
      dom.btnRefreshDebugModal.addEventListener('click', openDebugModal);
    }
    if (dom.debugModal) {
      dom.debugModal.addEventListener('click', (e) => {
        if (e.target === dom.debugModal) closeDebugModal();
      });
    }

    // 3g. Kernel Inspector Modal listeners (Requirement 4)
    if (dom.btnCloseKernelInspector) {
      dom.btnCloseKernelInspector.addEventListener('click', closeKernelInspector);
    }
    if (dom.kernelInspectorModal) {
      dom.kernelInspectorModal.addEventListener('click', (e) => {
        if (e.target === dom.kernelInspectorModal) closeKernelInspector();
      });
    }

    // 4. Start camera manual button
    if (dom.btnStartCamera) {
      dom.btnStartCamera.addEventListener('click', () => {
        initLiveCamera();
      });
    }

    // 5. Open localhost button for LAN HTTP mode
    if (dom.btnOpenLocalhost) {
      dom.btnOpenLocalhost.addEventListener('click', () => {
        const targetUrl = `http://localhost:5000/qc/camera-station`;
        window.location.href = targetUrl;
      });
    }

    // 6. Resize handler for overlay canvas
    window.addEventListener('resize', resizeCanvasToVideo);
    if (dom.videoElem) {
      dom.videoElem.addEventListener('loadedmetadata', resizeCanvasToVideo);
    }

    // 6b. Stabilized Scan Mode & Trigger Listeners (Requirements 1, 4)
    if (dom.btnModeScan) {
      dom.btnModeScan.addEventListener('click', () => setStationMode('scan'));
    }
    if (dom.btnModeLive) {
      dom.btnModeLive.addEventListener('click', () => setStationMode('live'));
    }
    if (dom.btnTriggerScan) {
      dom.btnTriggerScan.addEventListener('click', executeBurstScan);
    }

    // 7. Phase 4: Toggle Camera Setup Panel
    if (dom.btnToggleSetup) {
      dom.btnToggleSetup.addEventListener('click', () => {
        const isVisible = dom.setupPanel && dom.setupPanel.style.display !== 'none';
        toggleCameraSetupPanel(!isVisible);
      });
    }

    if (dom.btnCloseSetup) {
      dom.btnCloseSetup.addEventListener('click', () => {
        toggleCameraSetupPanel(false);
      });
    }

    if (dom.btnRefreshDeviceList) {
      dom.btnRefreshDeviceList.addEventListener('click', () => {
        enumerateCameraDevices();
      });
    }

    if (dom.btnTestCamera) {
      dom.btnTestCamera.addEventListener('click', () => {
        startCameraTest();
      });
    }

    if (dom.btnStopTestCamera) {
      dom.btnStopTestCamera.addEventListener('click', () => {
        stopCameraTest();
      });
    }

    // 8. Phone QR Modal Listeners
    if (dom.btnTogglePairPhoneModal) {
      dom.btnTogglePairPhoneModal.addEventListener('click', openPairPhoneModal);
    }
    if (dom.btnClosePairPhoneModal) {
      dom.btnClosePairPhoneModal.addEventListener('click', closePairPhoneModal);
    }
    if (dom.pairPhoneModal) {
      dom.pairPhoneModal.addEventListener('click', (e) => {
        if (e.target === dom.pairPhoneModal) closePairPhoneModal();
      });
    }
    if (dom.btnCopyStationLink) {
      dom.btnCopyStationLink.addEventListener('click', copyStationCaptureLink);
    }
    if (dom.btnStationModeTunnel) {
      dom.btnStationModeTunnel.addEventListener('click', () => setStationQrMode('tunnel'));
    }
    if (dom.btnStationModeLan) {
      dom.btnStationModeLan.addEventListener('click', () => setStationQrMode('lan'));
    }

    // 9. Photo Upload Fallback Modal Listeners
    if (dom.btnTogglePhotoUploadModal) {
      dom.btnTogglePhotoUploadModal.addEventListener('click', openPhotoUploadModal);
    }
    if (dom.btnClosePhotoUploadModal) {
      dom.btnClosePhotoUploadModal.addEventListener('click', closePhotoUploadModal);
    }
    if (dom.btnCancelPhotoUpload) {
      dom.btnCancelPhotoUpload.addEventListener('click', closePhotoUploadModal);
    }
    if (dom.photoUploadModal) {
      dom.photoUploadModal.addEventListener('click', (e) => {
        if (e.target === dom.photoUploadModal) closePhotoUploadModal();
      });
    }
    if (dom.photoDropzone && dom.photoFileInput) {
      dom.photoDropzone.addEventListener('click', () => dom.photoFileInput.click());
      dom.photoFileInput.addEventListener('change', (e) => handlePhotoFilesSelected(e.target.files));

      dom.photoDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dom.photoDropzone.style.borderColor = '#4F46E5';
        dom.photoDropzone.style.background = '#EEF2FF';
      });
      dom.photoDropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dom.photoDropzone.style.borderColor = '#94A3B8';
        dom.photoDropzone.style.background = '#F8FAFC';
      });
      dom.photoDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dom.photoDropzone.style.borderColor = '#94A3B8';
        dom.photoDropzone.style.background = '#F8FAFC';
        if (e.dataTransfer && e.dataTransfer.files) {
          handlePhotoFilesSelected(e.dataTransfer.files);
        }
      });
    }
    if (dom.btnExecutePhotoUpload) {
      dom.btnExecutePhotoUpload.addEventListener('click', executePhotoUpload);
    }

    // 10. QC Measures Modal Listeners
    if (dom.btnToggleQcMeasuresModal) {
      dom.btnToggleQcMeasuresModal.addEventListener('click', openQcMeasuresModal);
    }
    if (dom.btnCloseQcMeasuresModal) {
      dom.btnCloseQcMeasuresModal.addEventListener('click', closeQcMeasuresModal);
    }
    if (dom.btnCancelQcMeasures) {
      dom.btnCancelQcMeasures.addEventListener('click', closeQcMeasuresModal);
    }
    if (dom.qcMeasuresModal) {
      dom.qcMeasuresModal.addEventListener('click', (e) => {
        if (e.target === dom.qcMeasuresModal) closeQcMeasuresModal();
      });
    }
    if (dom.formStationQcMeasures) {
      dom.formStationQcMeasures.addEventListener('submit', submitQcMeasures);
    }
  }

  // Phone Pairing Modal handlers
  function openPairPhoneModal() {
    if (dom.pairPhoneModal) dom.pairPhoneModal.style.display = 'flex';
  }
  function closePairPhoneModal() {
    if (dom.pairPhoneModal) dom.pairPhoneModal.style.display = 'none';
  }
  function setStationQrMode(mode) {
    if (!sessionUrls) return;
    if (mode === 'tunnel' && sessionUrls.tunnel_url) {
      if (dom.stationQrImg && sessionUrls.tunnel_qr_data_url) dom.stationQrImg.src = sessionUrls.tunnel_qr_data_url;
      if (dom.stationCaptureUrl) dom.stationCaptureUrl.value = sessionUrls.tunnel_url;
      if (dom.btnStationModeTunnel) {
        dom.btnStationModeTunnel.style.background = '#4F46E5';
        dom.btnStationModeTunnel.style.color = '#FFFFFF';
      }
      if (dom.btnStationModeLan) {
        dom.btnStationModeLan.style.background = 'transparent';
        dom.btnStationModeLan.style.color = '#475569';
      }
    } else if (sessionUrls.lan_url) {
      if (dom.stationQrImg && sessionUrls.lan_qr_data_url) dom.stationQrImg.src = sessionUrls.lan_qr_data_url;
      if (dom.stationCaptureUrl) dom.stationCaptureUrl.value = sessionUrls.lan_url;
      if (dom.btnStationModeLan) {
        dom.btnStationModeLan.style.background = '#4F46E5';
        dom.btnStationModeLan.style.color = '#FFFFFF';
      }
      if (dom.btnStationModeTunnel) {
        dom.btnStationModeTunnel.style.background = 'transparent';
        dom.btnStationModeTunnel.style.color = '#475569';
      }
    }
  }
  function copyStationCaptureLink() {
    if (!dom.stationCaptureUrl) return;
    navigator.clipboard.writeText(dom.stationCaptureUrl.value).then(() => {
      if (dom.btnCopyStationLink) {
        dom.btnCopyStationLink.textContent = "✓ Copied!";
        setTimeout(() => { dom.btnCopyStationLink.textContent = "📋 Copy"; }, 2000);
      }
    }).catch(() => {
      dom.stationCaptureUrl.select();
      document.execCommand('copy');
    });
  }

  // Photo Upload Fallback handlers
  function openPhotoUploadModal() {
    selectedUploadFiles = [];
    if (dom.photoFilesList) dom.photoFilesList.innerHTML = '';
    if (dom.photoFilesPreview) dom.photoFilesPreview.style.display = 'none';
    if (dom.photoUploadStatus) dom.photoUploadStatus.style.display = 'none';
    if (dom.photoUploadModal) dom.photoUploadModal.style.display = 'flex';
  }
  function closePhotoUploadModal() {
    if (dom.photoUploadModal) dom.photoUploadModal.style.display = 'none';
  }
  function handlePhotoFilesSelected(fileList) {
    if (!fileList || fileList.length === 0) return;
    selectedUploadFiles = Array.from(fileList).slice(0, 5);
    if (dom.photoFilesCount) dom.photoFilesCount.textContent = selectedUploadFiles.length;
    if (dom.photoFilesList) {
      dom.photoFilesList.innerHTML = selectedUploadFiles.map(f => `
        <div style="background:#FFFFFF;border:1px solid #CBD5E1;border-radius:6px;padding:4px 8px;font-size:11px;font-weight:600;color:#334155;display:inline-flex;align-items:center;gap:4px;">
          <span>📷 ${f.name} (${Math.round(f.size / 1024)} KB)</span>
        </div>
      `).join('');
    }
    if (dom.photoFilesPreview) dom.photoFilesPreview.style.display = 'block';
  }
  async function executePhotoUpload() {
    if (selectedUploadFiles.length === 0) {
      alert("Please select or drop at least one sample photo first.");
      return;
    }
    if (dom.photoUploadStatus) {
      dom.photoUploadStatus.style.display = 'block';
      dom.photoUploadStatus.textContent = `Analyzing ${selectedUploadFiles.length} photo(s) through AI visual inspection...`;
    }

    try {
      const activeScanMode = dom.scanModeSelect ? dom.scanModeSelect.value : (localStorage.getItem('foodman_scan_mode') || 'Auto');
      const activeEngine = dom.engineSelect ? dom.engineSelect.value : (localStorage.getItem('foodman_inspection_engine') || 'ai');
      const minKernels = getMinScanKernels();

      let lastData = null;
      // If only 1 file is selected, repeat 5 times to satisfy 5-frame locking
      const framesToSend = selectedUploadFiles.length === 1
        ? [selectedUploadFiles[0], selectedUploadFiles[0], selectedUploadFiles[0], selectedUploadFiles[0], selectedUploadFiles[0]]
        : selectedUploadFiles;

      for (let i = 0; i < framesToSend.length; i++) {
        const file = framesToSend[i];
        const formData = new FormData();
        formData.append('image', file, `upload_frame_${i + 1}.jpg`);
        formData.append('lock', 'true');
        if (activeScanMode) formData.append('scan_mode', activeScanMode);
        formData.append('engine', activeEngine);
        formData.append('min_scan_kernels', minKernels);
        if (isIgnoreZoneActive()) {
          formData.append('ignore_zones', JSON.stringify([getIgnoreZone()]));
        }

        const res = await fetch(`/api/capture/${sessionToken}/frame`, {
          method: 'POST',
          body: formData
        });
        lastData = await res.json();
        if (dom.photoUploadStatus) {
          dom.photoUploadStatus.textContent = `Processed frame ${i + 1} of ${framesToSend.length}...`;
        }
      }

      if (lastData && lastData.locked_result) {
        closePhotoUploadModal();
        displayFinalResultCard(lastData.locked_result);
      } else if (lastData && lastData.success) {
        closePhotoUploadModal();
        handleFrameResponse(lastData);
      } else {
        if (dom.photoUploadStatus) {
          dom.photoUploadStatus.textContent = `Error: ${lastData ? lastData.error : 'Inspection failed'}`;
        }
      }
    } catch (err) {
      if (dom.photoUploadStatus) {
        dom.photoUploadStatus.textContent = `Upload error: ${err.message}`;
      }
    }
  }

  // QC Lab Measures Modal handlers
  async function openQcMeasuresModal() {
    const selectedLotText = (dom.lotSelect && dom.lotSelect.options[dom.lotSelect.selectedIndex])
      ? dom.lotSelect.options[dom.lotSelect.selectedIndex].text
      : '';
    if (dom.qcMeasuresTargetLotBadge) {
      dom.qcMeasuresTargetLotBadge.textContent = selectedLotText || (currentLotId ? `Lot #${currentLotId}` : 'No Lot Selected');
    }
    if (dom.qcMeasuresStatusBanner) dom.qcMeasuresStatusBanner.style.display = 'none';

    if (currentLotId) {
      try {
        const res = await fetch(`/api/qc/lot/${currentLotId}/qc-measures`);
        const data = await res.json();
        if (data.success) {
          if (dom.qcMeasuresDocNumber) dom.qcMeasuresDocNumber.value = data.coa.doc_number || `COA-${data.lot.lot_number}`;
          if (dom.qcMeasuresAccreditation) dom.qcMeasuresAccreditation.value = data.coa.lab_accreditation || 'ISO 17025 Certified';
          if (dom.qcMeasuresMoisture && data.measures.moisture !== undefined) dom.qcMeasuresMoisture.value = data.measures.moisture;
          if (dom.qcMeasuresAflatoxin && data.measures.aflatoxin_b1 !== undefined) dom.qcMeasuresAflatoxin.value = data.measures.aflatoxin_b1;
          if (dom.qcMeasuresFfa && data.measures.ffa !== undefined) dom.qcMeasuresFfa.value = data.measures.ffa;
          if (dom.qcMeasuresPurity && data.measures.purity !== undefined) dom.qcMeasuresPurity.value = data.measures.purity;
        }
      } catch (err) {
        console.warn("Could not pre-fill QC measures:", err);
      }
    }

    if (dom.qcMeasuresModal) dom.qcMeasuresModal.style.display = 'flex';
  }
  function closeQcMeasuresModal() {
    if (dom.qcMeasuresModal) dom.qcMeasuresModal.style.display = 'none';
  }
  async function submitQcMeasures(e) {
    if (e) e.preventDefault();
    if (!currentLotId) {
      alert("Please select a Target Lot first from the dropdown.");
      return;
    }

    const payload = {
      doc_number: dom.qcMeasuresDocNumber ? dom.qcMeasuresDocNumber.value : '',
      lab_accreditation: dom.qcMeasuresAccreditation ? dom.qcMeasuresAccreditation.value : '',
      moisture: dom.qcMeasuresMoisture && dom.qcMeasuresMoisture.value !== '' ? parseFloat(dom.qcMeasuresMoisture.value) : null,
      aflatoxin_b1: dom.qcMeasuresAflatoxin && dom.qcMeasuresAflatoxin.value !== '' ? parseFloat(dom.qcMeasuresAflatoxin.value) : null,
      ffa: dom.qcMeasuresFfa && dom.qcMeasuresFfa.value !== '' ? parseFloat(dom.qcMeasuresFfa.value) : null,
      purity: dom.qcMeasuresPurity && dom.qcMeasuresPurity.value !== '' ? parseFloat(dom.qcMeasuresPurity.value) : null
    };

    try {
      const res = await fetch(`/api/qc/lot/${currentLotId}/qc-measures`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (dom.qcMeasuresStatusBanner) {
        dom.qcMeasuresStatusBanner.style.display = 'block';
        if (data.success) {
          dom.qcMeasuresStatusBanner.style.background = '#ECFDF5';
          dom.qcMeasuresStatusBanner.style.color = '#065F46';
          dom.qcMeasuresStatusBanner.style.border = '1px solid #A7F3D0';
          dom.qcMeasuresStatusBanner.textContent = `✓ Saved! Combined outcome: ${data.merged_label}. COA State: ${data.release_decision.coa_state}.`;
          setTimeout(() => { closeQcMeasuresModal(); }, 1800);
        } else {
          dom.qcMeasuresStatusBanner.style.background = '#FEF2F2';
          dom.qcMeasuresStatusBanner.style.color = '#991B1B';
          dom.qcMeasuresStatusBanner.style.border = '1px solid #FECACA';
          dom.qcMeasuresStatusBanner.textContent = `Error: ${data.error || 'Failed to save'}`;
        }
      }
    } catch (err) {
      alert("Network error saving QC measures: " + err.message);
    }
  }

  // Check Secure Context (HTTPS or localhost)
  function checkSecureContext() {
    const isHttps = window.location.protocol === 'https:';
    const isLocalhost = window.location.hostname === 'localhost' || 
                        window.location.hostname === '127.0.0.1';

    if (!isHttps && !isLocalhost) {
      // Insecure LAN HTTP mode
      if (dom.lanHttpBanner) dom.lanHttpBanner.style.display = 'block';
      if (dom.btnStartCamera) dom.btnStartCamera.style.display = 'none';
      updateGuidance("Webcam blocked on insecure LAN HTTP. Please open localhost.", "⚠️");
      return false;
    }

    if (dom.lanHttpBanner) dom.lanHttpBanner.style.display = 'none';
    // Automatically initialize camera when loaded in secure context
    initLiveCamera();
    return true;
  }

  // Phase 4: Toggle Setup Panel
  function toggleCameraSetupPanel(show) {
    if (!dom.setupPanel) return;
    if (show) {
      dom.setupPanel.style.display = 'block';
      if (dom.btnToggleSetup) {
        dom.btnToggleSetup.style.background = '#0F172A';
        dom.btnToggleSetup.style.color = '#FFFFFF';
      }
      enumerateCameraDevices();
    } else {
      dom.setupPanel.style.display = 'none';
      if (dom.btnToggleSetup) {
        dom.btnToggleSetup.style.background = '#F8FAFC';
        dom.btnToggleSetup.style.color = '#334155';
      }
      stopCameraTest();
    }
  }

  // Phase 4: Plain-Language Camera Error Mapper
  function getPlainLanguageCameraError(err) {
    const errName = typeof err === 'string' ? err : (err ? (err.name || '') : '');
    const errMsg = typeof err === 'string' ? err.toLowerCase() : (err ? (err.message || '').toLowerCase() : '');

    if (errName === 'NotAllowedError' || errName === 'PermissionDeniedError' || errName === 'permission_denied' || errMsg.includes('permission') || errMsg.includes('denied')) {
      return {
        type: 'permission_denied',
        badgeColor: '#EF4444',
        title: '🚫 Camera Permission Denied',
        message: 'Camera permission was denied. Please click the camera icon 🔒 or 🎥 in your browser address bar, select "Always allow", and reload the page.'
      };
    }

    if (errName === 'NotReadableError' || errName === 'TrackStartError' || errName === 'in_use' || errMsg.includes('concurrent') || errMsg.includes('in use') || errMsg.includes('could not start')) {
      return {
        type: 'in_use',
        badgeColor: '#F59E0B',
        title: '⚠️ Camera Used by Another App',
        message: 'Camera is currently locked or in use by another application. Please close Zoom, Microsoft Teams, Skype, Google Meet, or other browser tabs that may be using the webcam, then click "Test Camera" again.'
      };
    }

    if (errName === 'NotFoundError' || errName === 'DevicesNotFoundError' || errName === 'not_found' || errMsg.includes('not found') || errMsg.includes('no device')) {
      return {
        type: 'not_found',
        badgeColor: '#64748B',
        title: '🔍 No Camera Found',
        message: 'No camera hardware was detected on this computer. Please connect a USB webcam, or follow the 3-step checklist above to use your phone as a wireless/USB webcam.'
      };
    }

    if (errName === 'black_preview' || errMsg.includes('black preview')) {
      return {
        type: 'black_preview',
        badgeColor: '#F59E0B',
        title: '⬛ Black Preview Detected',
        message: 'Black preview detected: The phone-camera app (such as Iriun, DroidCam, or Camo) or its Windows program is not running, or your phone is not connected. Open the companion app on both your phone and laptop and verify the USB / Wi-Fi connection.'
      };
    }

    if (errName === 'OverconstrainedError' || errMsg.includes('constraint')) {
      return {
        type: 'overconstrained',
        badgeColor: '#3B82F6',
        title: 'ℹ️ Resolution Not Supported',
        message: 'The selected camera does not support 1280x720 HD resolution. Falling back to default camera resolution.'
      };
    }

    return {
      type: 'general',
      badgeColor: '#EF4444',
      title: '⚠️ Camera Initialization Error',
      message: (err && err.message) || 'Unable to access video stream. Please check camera connections and permissions.'
    };
  }

  // Phase 4: Diagnostic Message Banner Renderer
  function showDiagnosticMessage(type, info) {
    if (!dom.cameraDiagnosticBox) return;

    let bg = '#FEF2F2';
    let border = '#FECACA';
    let textColor = '#991B1B';

    if (type === 'success') {
      bg = '#F0FDF4';
      border = '#BBF7D0';
      textColor = '#166534';
    } else if (type === 'in_use' || type === 'black_preview') {
      bg = '#FFFBEB';
      border = '#FDE68A';
      textColor = '#92400E';
    } else if (type === 'overconstrained') {
      bg = '#EFF6FF';
      border = '#BFDBFE';
      textColor = '#1E40AF';
    }

    dom.cameraDiagnosticBox.style.display = 'block';
    dom.cameraDiagnosticBox.style.background = bg;
    dom.cameraDiagnosticBox.style.border = `1px solid ${border}`;
    dom.cameraDiagnosticBox.style.color = textColor;

    dom.cameraDiagnosticBox.innerHTML = `
      <div style="font-weight:800;font-size:13px;margin-bottom:4px;display:flex;align-items:center;gap:6px;">
        <span>${info.title || 'Diagnostic Notice'}</span>
      </div>
      <div>${info.message}</div>
    `;
  }

  // Phase 4: Start Standalone Camera Test
  async function startCameraTest(deviceId = null) {
    stopCameraTest();

    if (dom.cameraDiagnosticBox) dom.cameraDiagnosticBox.style.display = 'none';
    if (dom.testResolutionBadge) {
      dom.testResolutionBadge.textContent = 'Resolution: Connecting...';
      dom.testResolutionBadge.style.background = '#E2E8F0';
      dom.testResolutionBadge.style.color = '#475569';
    }
    if (dom.testVideoPlaceholder) dom.testVideoPlaceholder.style.display = 'none';
    if (dom.btnTestCamera) dom.btnTestCamera.style.display = 'none';
    if (dom.btnStopTestCamera) dom.btnStopTestCamera.style.display = 'inline-flex';

    const chosenId = deviceId || (dom.cameraSelect && dom.cameraSelect.value) || localStorage.getItem('foodman_camera_device_id');
    const constraints = {
      audio: false,
      video: chosenId ? { deviceId: { exact: chosenId }, width: { ideal: 1280 }, height: { ideal: 720 } }
                      : { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }
    };

    try {
      try {
        testStream = await navigator.mediaDevices.getUserMedia(constraints);
      } catch (errFallback) {
        testStream = await navigator.mediaDevices.getUserMedia({ audio: false, video: true });
      }

      dom.testVideo.srcObject = testStream;
      await dom.testVideo.play();
      isTestingCamera = true;

      // Update resolution badge once metadata is loaded
      const updateRes = () => {
        const w = dom.testVideo.videoWidth || 0;
        const h = dom.testVideo.videoHeight || 0;
        if (w > 0 && h > 0) {
          const ratio = (w / h).toFixed(2);
          const aspectName = ratio === '1.78' ? '16:9 HD' : (ratio === '1.33' ? '4:3' : `${ratio}:1`);
          dom.testResolutionBadge.textContent = `Resolution: ${w} × ${h} (${aspectName})`;
          dom.testResolutionBadge.style.background = '#ECFDF5';
          dom.testResolutionBadge.style.color = '#065F46';
        }
      };

      if (dom.testVideo.videoWidth) {
        updateRes();
      } else {
        dom.testVideo.onloadedmetadata = updateRes;
      }

      if (dom.testVideoOverlayBadge) dom.testVideoOverlayBadge.style.display = 'flex';
      if (dom.testCameraActiveLabel) {
        const track = testStream.getVideoTracks()[0];
        dom.testCameraActiveLabel.textContent = track ? (track.label || 'Camera Active') : 'Camera Active';
      }

      // Re-enumerate devices so active badge shows up
      await enumerateCameraDevices();

      // Requirement 2: Black preview check (detects unlinked phone app or inactive virtual driver)
      if (testBlackCheckTimer) clearTimeout(testBlackCheckTimer);
      testBlackCheckTimer = setTimeout(() => {
        if (!isTestingCamera || !dom.testVideo) return;
        try {
          const chkCanvas = document.createElement('canvas');
          chkCanvas.width = 24;
          chkCanvas.height = 18;
          const chkCtx = chkCanvas.getContext('2d', { willReadFrequently: true });
          chkCtx.drawImage(dom.testVideo, 0, 0, 24, 18);
          const imgD = chkCtx.getImageData(0, 0, 24, 18).data;
          let totalLuma = 0;
          for (let i = 0; i < imgD.length; i += 4) {
            totalLuma += (imgD[i] * 299 + imgD[i + 1] * 587 + imgD[i + 2] * 114) / 1000;
          }
          const avgLuma = totalLuma / (24 * 18);
          if (avgLuma < 1.5) {
            const blackErr = getPlainLanguageCameraError('black_preview');
            showDiagnosticMessage(blackErr.type, blackErr);
          } else {
            showDiagnosticMessage('success', {
              title: '✓ Camera Test Passed',
              message: `Camera is active and streaming clearly at ${dom.testVideo.videoWidth} × ${dom.testVideo.videoHeight}. Feed is verified and ready for AI inspection.`
            });
          }
        } catch (e) {
          console.warn("Black frame check error:", e);
        }
      }, 1500);

    } catch (err) {
      console.warn("Camera test failed:", err);
      stopCameraTest();
      const plainErr = getPlainLanguageCameraError(err);
      showDiagnosticMessage(plainErr.type, plainErr);
      if (dom.testResolutionBadge) {
        dom.testResolutionBadge.textContent = 'Resolution: Error';
        dom.testResolutionBadge.style.background = '#FEF2F2';
        dom.testResolutionBadge.style.color = '#991B1B';
      }
    }
  }

  // Phase 4: Stop Standalone Camera Test
  function stopCameraTest() {
    if (testBlackCheckTimer) {
      clearTimeout(testBlackCheckTimer);
      testBlackCheckTimer = null;
    }
    if (testStream) {
      testStream.getTracks().forEach(t => t.stop());
      testStream = null;
    }
    isTestingCamera = false;

    if (dom.testVideo) {
      dom.testVideo.srcObject = null;
    }
    if (dom.testVideoPlaceholder) dom.testVideoPlaceholder.style.display = 'flex';
    if (dom.testVideoOverlayBadge) dom.testVideoOverlayBadge.style.display = 'none';
    if (dom.btnTestCamera) dom.btnTestCamera.style.display = 'inline-flex';
    if (dom.btnStopTestCamera) dom.btnStopTestCamera.style.display = 'none';
    if (dom.testResolutionBadge) {
      dom.testResolutionBadge.textContent = 'Resolution: -- × --';
      dom.testResolutionBadge.style.background = '#E2E8F0';
      dom.testResolutionBadge.style.color = '#475569';
    }
  }

  // Phase 4: Select and Test a specific camera from the list
  async function selectAndTestDevice(deviceId) {
    if (deviceId) {
      localStorage.setItem('foodman_camera_device_id', deviceId);
      if (dom.cameraSelect) dom.cameraSelect.value = deviceId;
      await restartCameraStream();
      await startCameraTest(deviceId);
    }
  }

  // Camera Selector & Device Enumeration (Requirement 1 & Phase 4)
  async function enumerateCameraDevices() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;

    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoInputs = devices.filter(d => d.kind === 'videoinput');

      // Update Phase 4 detected cameras count
      if (dom.detectedCamerasCount) {
        dom.detectedCamerasCount.textContent = videoInputs.length;
      }

      // Update Phase 4 detected cameras list in Setup Panel
      if (dom.detectedCamerasList) {
        dom.detectedCamerasList.innerHTML = '';
        if (videoInputs.length === 0) {
          dom.detectedCamerasList.innerHTML = `
            <div style="font-size:12px;color:#94A3B8;text-align:center;padding:24px 0;">
              No cameras detected. Please plug in a webcam or start your phone camera app.
            </div>
          `;
        } else {
          const savedId = localStorage.getItem('foodman_camera_device_id');
          videoInputs.forEach((device, index) => {
            const devLabel = device.label || `Camera ${index + 1}`;
            const isSelected = (savedId === device.deviceId) || (!savedId && index === 0);

            const item = document.createElement('div');
            item.style.cssText = `display:flex;align-items:center;justify-content:space-between;padding:8px 10px;background:#FFF;border:1px solid ${isSelected ? '#818CF8' : '#E2E8F0'};border-radius:6px;gap:8px;`;

            item.innerHTML = `
              <div style="display:flex;align-items:center;gap:8px;overflow:hidden;">
                <span style="font-size:14px;">📹</span>
                <div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                  <strong style="font-size:12px;color:#0F172A;">${devLabel}</strong>
                  <div style="font-size:10.5px;color:#64748B;">ID: ${device.deviceId ? device.deviceId.slice(0, 16) + '...' : 'Default'}</div>
                </div>
              </div>
              <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
                ${isSelected ? '<span style="font-size:10px;font-weight:700;color:#4F46E5;background:#EEF2FF;padding:2px 6px;border-radius:4px;">In Use</span>' : ''}
                <button type="button" class="btn-secondary" style="font-size:11px;padding:3px 8px;cursor:pointer;" onclick="CameraStationApp.selectAndTestDevice('${device.deviceId}')">
                  Select & Test
                </button>
              </div>
            `;
            dom.detectedCamerasList.appendChild(item);
          });
        }
      }

      if (!dom.cameraSelect) return;

      // Requirement 1: Show dropdown only if more than one camera exists
      if (videoInputs.length > 1) {
        if (dom.cameraSelectContainer) dom.cameraSelectContainer.style.display = 'inline-flex';
        dom.cameraSelect.style.display = 'inline-block';

        const savedDeviceId = localStorage.getItem('foodman_camera_device_id');
        dom.cameraSelect.innerHTML = '';

        videoInputs.forEach((device, index) => {
          const opt = document.createElement('option');
          opt.value = device.deviceId;
          opt.textContent = device.label || `Camera ${index + 1}`;
          if (savedDeviceId && device.deviceId === savedDeviceId) {
            opt.selected = true;
          }
          dom.cameraSelect.appendChild(opt);
        });
      } else {
        if (dom.cameraSelectContainer) dom.cameraSelectContainer.style.display = 'none';
        dom.cameraSelect.style.display = 'none';
      }
    } catch (err) {
      console.warn("Could not enumerate camera devices:", err);
    }
  }

  // Build constraints according to Requirement 1
  function buildCameraConstraints() {
    const savedDeviceId = localStorage.getItem('foodman_camera_device_id');
    const selectedDeviceId = (dom.cameraSelect && dom.cameraSelect.value) || savedDeviceId;

    if (selectedDeviceId) {
      // When device is chosen: use deviceId exact and drop facingMode; ideal 1280x720
      return {
        audio: false,
        video: {
          deviceId: { exact: selectedDeviceId },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      };
    } else {
      // Otherwise keep current behavior with 1280x720 ideal
      return {
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      };
    }
  }

  // Start Camera Stream
  async function initLiveCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showAlert("Camera API (getUserMedia) not supported in this browser. Please use Chrome, Edge or Firefox.");
      return;
    }

    hideAlert();
    try {
      const constraints = buildCameraConstraints();
      videoStream = await navigator.mediaDevices.getUserMedia(constraints);
      dom.videoElem.srcObject = videoStream;
      await dom.videoElem.play();

      isCameraRunning = true;
      if (dom.btnStartCamera) dom.btnStartCamera.style.display = 'none';

      // After permission granted, enumerate devices to populate camera selector
      await enumerateCameraDevices();

      // Start steadiness detector & 1 FPS capture loop ONLY in live mode; scan mode uses plain preview
      if (stationMode === 'live') {
        startSteadinessDetector();
        startLiveStreamLoop();
        updateGuidance("Position specimen sample in view", "🎯");
      } else {
        setStationMode('scan');
      }

      resizeCanvasToVideo();

    } catch (err) {
      console.warn("Camera init with ideal constraints failed:", err);
      // Fallback constraints without facingMode or exact deviceId if restricted
      try {
        videoStream = await navigator.mediaDevices.getUserMedia({ audio: false, video: true });
        dom.videoElem.srcObject = videoStream;
        await dom.videoElem.play();

        isCameraRunning = true;
        if (dom.btnStartCamera) dom.btnStartCamera.style.display = 'none';

        await enumerateCameraDevices();
        if (stationMode === 'live') {
          startSteadinessDetector();
          startLiveStreamLoop();
          updateGuidance("Position specimen sample in view", "🎯");
        } else {
          setStationMode('scan');
        }
        resizeCanvasToVideo();

      } catch (err2) {
        const plainErr = getPlainLanguageCameraError(err2);
        showAlert(`${plainErr.title}: ${plainErr.message}`);
        showDiagnosticMessage(plainErr.type, plainErr);
        if (dom.btnStartCamera) dom.btnStartCamera.style.display = 'inline-flex';
        updateGuidance(plainErr.title, "⚠️");
      }
    }
  }

  async function restartCameraStream() {
    stopCameraStream();
    await initLiveCamera();
  }

  function stopCameraStream() {
    if (steadinessTimer) {
      clearInterval(steadinessTimer);
      steadinessTimer = null;
    }
    if (liveLoopTimer) {
      clearInterval(liveLoopTimer);
      liveLoopTimer = null;
    }
    if (videoStream) {
      videoStream.getTracks().forEach(t => t.stop());
      videoStream = null;
    }
    isCameraRunning = false;
  }

  function resizeCanvasToVideo() {
    if (!dom.overlayCanvas || !dom.videoElem) return;
    const rect = dom.videoElem.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      dom.overlayCanvas.width = rect.width;
      dom.overlayCanvas.height = rect.height;
    }
  }

  function updateGuidance(text, icon = "🎯", isSteady = false, isLockingMode = false) {
    if (!dom.hudGuidance) return;
    if (dom.hudGuidanceText) dom.hudGuidanceText.textContent = text;
    if (dom.hudGuidanceIcon) dom.hudGuidanceIcon.textContent = icon;
    dom.hudGuidance.className = 'hud-guidance' + (isLockingMode ? ' locking' : (isSteady ? ' steady' : ''));
  }

  function updateSteadyBar(percent) {
    if (!dom.steadyBarContainer || !dom.steadyBarFill) return;
    if (percent > 0) {
      dom.steadyBarContainer.style.display = 'block';
      dom.steadyBarFill.style.width = percent + '%';
    } else {
      dom.steadyBarContainer.style.display = 'none';
      dom.steadyBarFill.style.width = '0%';
    }
  }

  function showAlert(msg) {
    if (dom.alertBanner && dom.alertBannerText) {
      dom.alertBannerText.textContent = msg;
      dom.alertBanner.style.display = 'flex';
    }
  }

  function hideAlert() {
    if (dom.alertBanner) dom.alertBanner.style.display = 'none';
  }

  // Steadiness & Quality Analyzer (Requirement 2 & 6)
  function startSteadinessDetector() {
    if (steadinessTimer) clearInterval(steadinessTimer);

    const sampleCanvas = document.createElement('canvas');
    sampleCanvas.width = 48;
    sampleCanvas.height = 36;
    const sampleCtx = sampleCanvas.getContext('2d', { willReadFrequently: true });

    steadinessTimer = setInterval(() => {
      if (!isCameraRunning || isLocking || isLockedResultShowing) return;
      if (!dom.videoElem || dom.videoElem.readyState < 2) return;

      sampleCtx.drawImage(dom.videoElem, 0, 0, 48, 36);
      const imgData = sampleCtx.getImageData(0, 0, 48, 36);
      const data = imgData.data;

      // 1. Calculate average brightness (Luma)
      let totalLuma = 0;
      const count = 48 * 36;
      const gray = new Uint8Array(count);
      for (let i = 0; i < count; i++) {
        const r = data[i * 4];
        const g = data[i * 4 + 1];
        const b = data[i * 4 + 2];
        const luma = (r * 299 + g * 587 + b * 114) / 1000;
        gray[i] = luma;
        totalLuma += luma;
      }
      const avgBrightness = totalLuma / count;

      // 2. Calculate frame difference against previous sample
      let diff = 0;
      if (prevSamplePixels) {
        for (let i = 0; i < count; i++) {
          diff += Math.abs(gray[i] - prevSamplePixels[i]);
        }
        diff = diff / count;
      }
      prevSamplePixels = gray;

      // Quality checks
      const isBlackScreen = avgBrightness < 1.5;
      const isVeryDark = avgBrightness < 40;
      const isSteadyFrame = diff < 7.5; // low motion

      if (isBlackScreen) {
        updateGuidance("Black preview: Open phone app & Windows companion", "⬛");
        steadyDuration = 0;
        updateSteadyBar(0);
        return;
      }

      if (isVeryDark) {
        updateGuidance("More light needed", "💡");
        steadyDuration = 0;
        updateSteadyBar(0);
        return;
      }

      if (latestItemCount === 0) {
        updateGuidance("Move closer to specimen", "🔍");
        steadyDuration = 0;
        updateSteadyBar(0);
        return;
      }

      const minReq = getMinScanKernels();
      if (latestItemCount < minReq) {
        updateGuidance(`Include ≥ ${minReq} items in frame`, "📐");
        steadyDuration = 0;
        updateSteadyBar(0);
        return;
      }

      // Valid specimen count and lighting
      if (isSteadyFrame) {
        steadyDuration += 300;
        const pct = Math.min(100, Math.round((steadyDuration / STEADY_REQ_MS) * 100));
        updateSteadyBar(pct);

        if (steadyDuration >= STEADY_REQ_MS) {
          // Trigger 5-frame multi-frame lock sequence!
          triggerLockSequence();
        } else {
          updateGuidance(`Hold steady... ${(steadyDuration / 1000).toFixed(1)}s`, "🎯", true);
        }
      } else {
        // Motion detected
        steadyDuration = Math.max(0, steadyDuration - 400);
        const pct = Math.min(100, Math.round((steadyDuration / STEADY_REQ_MS) * 100));
        updateSteadyBar(pct);
        updateGuidance("Hold steady", "✋");
      }
    }, 300);
  }

  // Requirement 5: Send about one frame per second at 960-1280 px, one request at a time
  function startLiveStreamLoop() {
    if (liveLoopTimer) clearInterval(liveLoopTimer);

    liveLoopTimer = setInterval(async () => {
      if (!isCameraRunning || isUploading || isLocking || isLockedResultShowing) return;
      if (!dom.videoElem || dom.videoElem.readyState < 2) return;

      await captureAndSendFrame(false);
    }, 1000); // 1 FPS
  }

  // Frame Capture and Upload
  async function captureAndSendFrame(isLockFrame = false) {
    if (isUploading && !isLockFrame) return null;
    isUploading = true;

    try {
      const vWidth = dom.videoElem.videoWidth || 1280;
      const vHeight = dom.videoElem.videoHeight || 720;

      // Scale to roughly 960 - 1280 px max dimension
      const maxDim = 1280;
      const scale = Math.min(1, maxDim / Math.max(vWidth, vHeight));
      const targetW = Math.round(vWidth * scale);
      const targetH = Math.round(vHeight * scale);

      const capCanvas = document.createElement('canvas');
      capCanvas.width = targetW;
      capCanvas.height = targetH;
      const capCtx = capCanvas.getContext('2d');
      capCtx.drawImage(dom.videoElem, 0, 0, targetW, targetH);

      const blob = await new Promise(resolve => capCanvas.toBlob(resolve, 'image/jpeg', 0.72));
      if (!blob) {
        isUploading = false;
        return null;
      }

      const formData = new FormData();
      formData.append('image', blob, 'station_frame.jpg');
      if (isLockFrame) {
        formData.append('lock', 'true');
      }

      const activeScanMode = dom.scanModeSelect ? dom.scanModeSelect.value : (localStorage.getItem('foodman_scan_mode') || 'Auto');
      if (activeScanMode) {
        formData.append('scan_mode', activeScanMode);
      }

      // Setting ENGINE: ai | colour | both
      const activeEngine = dom.engineSelect ? dom.engineSelect.value : (localStorage.getItem('foodman_inspection_engine') || 'ai');
      formData.append('engine', activeEngine);

      // Min scan kernels (default 3)
      const minKernels = getMinScanKernels();
      formData.append('min_scan_kernels', minKernels);

      // Ignore zones: default bottom-left 22% wide by 18% high
      if (isIgnoreZoneActive()) {
        formData.append('ignore_zones', JSON.stringify([getIgnoreZone()]));
      }

      const res = await fetch(`/api/capture/${sessionToken}/frame`, {
        method: 'POST',
        body: formData
      });

      const data = await res.json();
      isUploading = false;

      if (!res.ok || !data.success) {
        if (res.status === 410) {
          showAlert("Inspection session closed or expired.");
        }
        return null;
      }

      handleFrameResponse(data);
      return data;

    } catch (err) {
      isUploading = false;
      console.warn("Upload frame error:", err);
      return null;
    }
  }

  function handleFrameResponse(data) {
    // 1. Update Status Bar
    const material = data.material || "Raw Specimen";
    const good = data.good_count || 0;
    const defect = data.defect_count || 0;
    const total = good + defect;
    latestItemCount = total;

    if (dom.hudMaterial) dom.hudMaterial.textContent = material;
    if (dom.hudTotalCount) dom.hudTotalCount.textContent = `${total} items`;

    if (total > 0) {
      const goodPct = Math.round((good / total) * 100);
      const defectPct = Math.round((defect / total) * 100);
      if (dom.hudGoodPct) dom.hudGoodPct.textContent = `${goodPct}%`;
      if (dom.hudDefectPct) dom.hudDefectPct.textContent = `${defectPct}%`;
    } else {
      if (dom.hudGoodPct) dom.hudGoodPct.textContent = "--%";
      if (dom.hudDefectPct) dom.hudDefectPct.textContent = "--%";
    }

    // 2. Draw Bounding Boxes on Overlay Canvas
    drawBoxesOnCanvas(data.boxes || []);

    // 3. Check if locked_result is returned
    if (data.locked_result) {
      displayFinalResultCard(data.locked_result);
    }
  }

  function drawBoxesOnCanvas(boxes) {
    if (!dom.overlayCanvas) return;
    resizeCanvasToVideo();

    const ctx = dom.overlayCanvas.getContext('2d');
    const width = dom.overlayCanvas.width;
    const height = dom.overlayCanvas.height;

    ctx.clearRect(0, 0, width, height);

    if (stationMode === 'scan') {
      // Plain live preview in scan mode: no boxes drawn on preview
      return;
    }

    // Requirement 1: Ignore Zones preview with outlines
    const iz = getIgnoreZone();
    const ignoreActive = isIgnoreZoneActive();

    if (ignoreActive) {
      const zx = iz.x * width;
      const zy = iz.y * height;
      const zw = iz.w * width;
      const zh = iz.h * height;

      ctx.save();
      ctx.fillStyle = 'rgba(245, 158, 11, 0.14)';
      ctx.fillRect(zx, zy, zw, zh);

      ctx.strokeStyle = '#F59E0B';
      ctx.lineWidth = 2.0;
      ctx.setLineDash([6, 4]);
      ctx.strokeRect(zx, zy, zw, zh);
      ctx.setLineDash([]);

      ctx.fillStyle = '#F59E0B';
      ctx.fillRect(zx, Math.max(0, zy - 18), 160, 18);
      ctx.fillStyle = '#FFFFFF';
      ctx.font = 'bold 10px Inter, -apple-system, sans-serif';
      ctx.fillText('⊘ IGNORE ZONE (22%×18%)', zx + 6, Math.max(13, zy - 5));
      ctx.restore();
    }

    // Filter boxes: drop any whose center falls inside the ignore zone
    const displayBoxes = (boxes || []).filter(box => {
      if (!ignoreActive) return true;
      const cx = (box.x || 0) + (box.w || 0) / 2.0;
      const cy = (box.y || 0) + (box.h || 0) / 2.0;
      return !(cx >= iz.x && cx <= (iz.x + iz.w) && cy >= iz.y && cy <= (iz.y + iz.h));
    });

    displayBoxes.forEach(box => {
      const bx = box.x * width;
      const by = box.y * height;
      const bw = box.w * width;
      const bh = box.h * height;

      const bType = (box.type || '').toLowerCase();
      const bClass = (box.class || '').toLowerCase();
      const isUncertain = bType === 'uncertain' || bClass.includes('uncertain');
      const isDefect = !isUncertain && (bType === 'defect' || bClass.includes('suspect') || (bClass.includes('mold') && !bClass.includes('not')));

      let color = '#10B981'; // Green (Normal)
      let bgColor = 'rgba(16, 185, 129, 0.16)';
      if (isUncertain) {
        color = '#F59E0B'; // Amber (Uncertain)
        bgColor = 'rgba(245, 158, 11, 0.20)';
      } else if (isDefect) {
        color = '#EF4444'; // Red (Suspect)
        bgColor = 'rgba(239, 68, 68, 0.20)';
      }

      // Box fill and stroke (Big readable outlines: lineWidth 3.5)
      ctx.fillStyle = bgColor;
      ctx.fillRect(bx, by, bw, bh);
      ctx.strokeStyle = color;
      ctx.lineWidth = 3.5;
      ctx.strokeRect(bx, by, bw, bh);

      // Label background & text
      const baseLabel = box.reason_why ? `${box.class} • ${box.reason_why}` : box.class;
      const label = (box.confidence !== undefined && box.confidence > 0 && box.confidence < 1.0)
        ? `${baseLabel} (${Math.round(box.confidence * 100)}%)`
        : baseLabel;
      ctx.font = 'bold 11px Inter, -apple-system, sans-serif';
      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = color;
      ctx.fillRect(bx, Math.max(0, by - 18), textWidth + 8, 18);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillText(label, bx + 4, Math.max(13, by - 5));
    });
  }

  // 5-Frame Lock Sequence
  async function triggerLockSequence() {
    if (isLocking || isLockedResultShowing) return;
    isLocking = true;
    updateSteadyBar(100);

    let finalLockedResult = null;

    for (let i = 1; i <= 5; i++) {
      updateGuidance(`Locking sample... Frame ${i} of 5`, "🔒", true, true);
      const resData = await captureAndSendFrame(true);
      if (resData && resData.locked_result) {
        finalLockedResult = resData.locked_result;
      }
      if (i < 5) {
        await new Promise(r => setTimeout(r, 550));
      }
    }

    isLocking = false;
    updateSteadyBar(0);

    if (finalLockedResult) {
      displayFinalResultCard(finalLockedResult);
    } else {
      updateGuidance("Evaluating 5-frame sequence...", "⏳");
    }
  }

  // Pending Override State
  let pendingOverrideAction = null;

  // Final Result Card (Rebuilt Component)
  function displayFinalResultCard(result) {
    isLockedResultShowing = true;
    lastLockedResult = result;

    // Clear overlay boxes
    if (dom.overlayCanvas) {
      const ctx = dom.overlayCanvas.getContext('2d');
      ctx.clearRect(0, 0, dom.overlayCanvas.width, dom.overlayCanvas.height);
    }

    // Switch view: hide live stage, show result card
    if (dom.liveSection) dom.liveSection.style.display = 'none';
    if (dom.resultCard) dom.resultCard.style.display = 'block';

    const sanitizePlain = (str) => {
      if (!str) return '';
      return str
        .replace(/classifier consensus/gi, 'material agreement')
        .replace(/usable frames/gi, 'photos used')
        .replace(/multi-frame locked analysis/gi, 'photo analysis')
        .replace(/specimen/gi, 'sample')
        .replace(/Confirm Accept \(Approved\)/gi, 'Approved');
    };

    const fd = result.final_decision || {
      state: ((result.suggestion || "Review").toUpperCase()),
      reason: result.reason || "Inspection complete.",
      material: result.material || "Corn",
      kernels_checked: result.kernels_checked || result.items_counted || 0,
      defect_pct: result.defect_pct !== undefined ? result.defect_pct : null,
      next_step: result.next_step || "Review sample and determine lot disposition.",
      details: result.details || []
    };

    fd.reason = sanitizePlain(fd.reason || result.reason || '');
    fd.next_step = sanitizePlain(fd.next_step || result.next_step || '');

    const state = (fd.state || "REVIEW").toUpperCase();
    const stateTitle = state.charAt(0) + state.slice(1).toLowerCase();

    // Auto-save Result Confirmation Banner
    const selectedLotText = (dom.lotSelect && dom.lotSelect.options[dom.lotSelect.selectedIndex])
      ? dom.lotSelect.options[dom.lotSelect.selectedIndex].text
      : '';
    if (dom.stationLotSavedBadge) {
      dom.stationLotSavedBadge.style.display = 'flex';
      if (dom.stationLotSavedBadgeText) {
        if (currentLotId && selectedLotText && !selectedLotText.includes('-- Standalone')) {
          const lotLabel = selectedLotText.split('—')[0].trim();
          dom.stationLotSavedBadgeText.textContent = `Result saved to ${lotLabel} (${fd.material || 'Material'})`;
        } else {
          dom.stationLotSavedBadgeText.textContent = `Inspection completed for specimen sample. Select Target Lot above to link.`;
        }
      }
    }

    if (currentLotId && sessionId) {
      linkSessionLot(currentLotId);
    }

    // 1. Status Banner: icon, one big word (Pass, Review, Reject or Retake) and the one-sentence reason.
    // This is the ONLY coloured element (green, amber, red, grey). The rest of the card uses neutral greys.
    if (dom.cardStatusBanner) {
      let bg = '#FFFBEB';
      let border = '#FDE68A';
      let textCol = '#92400E';
      let iconSvg = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';

      if (state === 'PASS') {
        bg = '#ECFDF5';
        border = '#A7F3D0';
        textCol = '#065F46';
        iconSvg = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
      } else if (state === 'REJECT') {
        bg = '#FEF2F2';
        border = '#FECACA';
        textCol = '#991B1B';
        iconSvg = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
      } else if (state === 'RETAKE') {
        bg = '#F1F5F9';
        border = '#CBD5E1';
        textCol = '#334155';
        iconSvg = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>';
      }

      dom.cardStatusBanner.style.background = bg;
      dom.cardStatusBanner.style.borderColor = border;
      if (dom.cardStatusIcon) dom.cardStatusIcon.innerHTML = iconSvg;
      if (dom.cardStatusTitle) {
        dom.cardStatusTitle.textContent = stateTitle;
        dom.cardStatusTitle.style.color = textCol;
      }
      if (dom.cardStatusReason) {
        dom.cardStatusReason.textContent = fd.reason || '';
        dom.cardStatusReason.style.color = textCol;
      }
    }

    // 2. Three plain stats: Material, Kernels checked, Defective.
    // Show "Hidden" with note "Shown once the material is clear" when defect_pct is null.
    if (dom.cardStatMaterial) {
      dom.cardStatMaterial.textContent = fd.material || 'Unknown';
    }
    if (dom.cardStatKernels) {
      dom.cardStatKernels.textContent = (fd.kernels_checked !== undefined) ? fd.kernels_checked : 0;
    }

    const totalKernels = fd.total_kernels_counted || fd.kernels_checked || result.total_items_counted || 0;
    const goodKernels = (fd.good_kernels_count !== undefined) ? fd.good_kernels_count : ((result.good_count !== undefined) ? result.good_count : Math.max(0, totalKernels - (result.moldy_count || 0) - (result.uncertain_count || 0)));
    const suspectKernels = (fd.suspect_kernels_count !== undefined) ? fd.suspect_kernels_count : (result.moldy_count || 0);
    const uncertainKernels = (fd.uncertain_kernels_count !== undefined) ? fd.uncertain_kernels_count : (result.uncertain_count || 0);
    const matName = fd.material_name || fd.material || result.winner_material || 'Sample';
    const summaryHeadline = fd.summary_headline || result.summary_headline || `${matName}, ${totalKernels} kernels, ${goodKernels} good, ${suspectKernels} suspect, ${uncertainKernels} uncertain`;

    if (dom.cardStatKernelsSub && totalKernels > 0) {
      dom.cardStatKernelsSub.textContent = `${goodKernels} Good · ${suspectKernels} Suspect${uncertainKernels ? ` · ${uncertainKernels} Uncertain` : ''}`;
    }

    if (dom.cardSummaryHeadline) {
      dom.cardSummaryHeadline.textContent = summaryHeadline;
    }

    if (dom.cardSummaryBadges) {
      dom.cardSummaryBadges.innerHTML = `
        <span style="display:inline-flex;align-items:center;background:#DCFCE7;color:#15803D;font-weight:700;font-size:12px;padding:3px 9px;border-radius:12px;border:1px solid #86EFAC;">
          ✓ ${goodKernels} Good
        </span>
        <span style="display:inline-flex;align-items:center;background:${suspectKernels > 0 ? '#FEE2E2' : '#F1F5F9'};color:${suspectKernels > 0 ? '#DC2626' : '#64748B'};font-weight:700;font-size:12px;padding:3px 9px;border-radius:12px;border:1px solid ${suspectKernels > 0 ? '#FCA5A5' : '#CBD5E1'};">
          ${suspectKernels > 0 ? '⚠️' : '•'} ${suspectKernels} Suspect
        </span>
        ${uncertainKernels > 0 ? `
          <span style="display:inline-flex;align-items:center;background:#FEF3C7;color:#B45309;font-weight:700;font-size:12px;padding:3px 9px;border-radius:12px;border:1px solid #FCD34D;">
            ❓ ${uncertainKernels} Uncertain
          </span>
        ` : ''}
      `;
    }

    if (dom.cardStatDefectVal) {
      if (fd.defect_pct !== null && fd.defect_pct !== undefined) {
        dom.cardStatDefectVal.textContent = `${fd.defect_pct}%`;
        if (dom.cardStatDefectNote) dom.cardStatDefectNote.style.display = 'none';
      } else {
        dom.cardStatDefectVal.textContent = 'Hidden';
        if (dom.cardStatDefectNote) dom.cardStatDefectNote.style.display = 'block';
      }
    }

    // 3. "What to do next": one sentence and ONE primary button that matches the state.
    // Secondary buttons for other actions.
    if (dom.cardNextStepText) {
      dom.cardNextStepText.textContent = fd.next_step || 'Review sample and select next action.';
    }

    // Reset inline override reason box and verdict notice
    pendingOverrideAction = null;
    if (dom.cardOverrideReasonBox) dom.cardOverrideReasonBox.style.display = 'none';
    if (dom.verdictNotice) dom.verdictNotice.style.display = 'none';

    if (dom.cardActionButtonsRow) {
      dom.cardActionButtonsRow.style.display = 'flex';
      dom.cardActionButtonsRow.innerHTML = '';

      const btnPrimaryStyle = 'background:#0F172A;color:#FFFFFF;border:1px solid #0F172A;font-weight:700;font-size:13px;padding:9px 18px;border-radius:6px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;';
      const btnSecondaryStyle = 'background:#FFFFFF;color:#334155;border:1px solid #CBD5E1;font-weight:600;font-size:13px;padding:9px 16px;border-radius:6px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;';

      const createBtn = (id, label, action, isPrimary) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.id = id;
        btn.style.cssText = isPrimary ? btnPrimaryStyle : btnSecondaryStyle;
        btn.textContent = label;
        btn.onclick = () => CameraStationApp.handleAction(action);
        return btn;
      };

      if (state === 'PASS') {
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionApprove', 'Approve lot', 'APPROVE', true));
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionReject', 'Reject lot', 'REJECT', false));
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionScanAgain', 'Scan again', 'RETAKE', false));
      } else if (state === 'REJECT') {
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionReject', 'Reject lot', 'REJECT', true));
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionApprove', 'Approve lot', 'APPROVE', false));
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionScanAgain', 'Scan again', 'RETAKE', false));
      } else if (state === 'RETAKE') {
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionScanAgain', 'Scan again', 'RETAKE', true));
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionApprove', 'Approve lot', 'APPROVE', false));
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionReject', 'Reject lot', 'REJECT', false));
      } else {
        // REVIEW
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionScanAgain', 'Scan again', 'RETAKE', true));
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionApprove', 'Approve lot', 'APPROVE', false));
        dom.cardActionButtonsRow.appendChild(createBtn('btnActionReject', 'Reject lot', 'REJECT', false));
      }
    }

    // 4. "Photos behind this result": three photos with flagged kernels outlined, click to enlarge, caption "n flagged of m kernels".
    if (dom.resBestFramesGrid) {
      const frames = result.best_frames || [];
      if (frames.length > 0) {
        dom.resBestFramesGrid.innerHTML = frames.slice(0, 3).map((f, idx) => {
          const flagged = f.defect_count || 0;
          const total = (f.good_count || 0) + flagged;
          const imgSrc = f.annotated_path || f.image_path;
          return `
            <div style="border:1px solid #CBD5E1;border-radius:8px;overflow:hidden;background:#F8FAFC;cursor:pointer;transition:transform 0.15s, box-shadow 0.15s;" 
                 onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)';this.style.transform='translateY(-2px)'"
                 onmouseout="this.style.boxShadow='none';this.style.transform='none'"
                 onclick="CameraStationApp.openKernelInspector(${idx})" title="Click to inspect kernels and reasons why">
              <img src="${imgSrc}" alt="Sample photo ${idx + 1}" style="width:100%;height:130px;object-fit:cover;display:block;">
              <div style="padding:8px 10px;font-size:11.5px;font-weight:600;color:#334155;background:#FFFFFF;border-top:1px solid #E2E8F0;display:flex;align-items:center;justify-content:space-between;">
                <span>${flagged} flagged of ${total} kernels</span>
                <span style="font-size:10.5px;color:#0284C7;font-weight:700;">🔎 Inspect</span>
              </div>
            </div>
          `;
        }).join('');
      } else {
        dom.resBestFramesGrid.innerHTML = `
          <div style="grid-column:1/-1;background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:8px;padding:16px;text-align:center;font-size:12px;color:#64748B;">
            No photos recorded for this result.
          </div>
        `;
      }
    }

    // 4b. Per-Kernel Breakdown Table (Requirement 2, 4, 5)
    renderPerKernelBreakdownTable(result.tracked_kernels);

    // 5. Collapsed "How was this decided?" section holding technical lines:
    // material agreement, photos used, model confidence, the pass and reject limits.
    if (dom.howDecided && dom.howDecidedContent) {
      dom.howDecided.open = false; // Always collapsed by default
      const rawDetails = (fd.details && fd.details.length > 0) ? fd.details : [
        `Material agreement: ${Math.round((result.winner_ratio || 1.0) * 100)}% (${fd.material})`,
        `Photos used: ${result.usable_frames || 5} of 5`,
        `Model confidence: ${result.confidence_percent || Math.round((result.avg_confidence || 0.95) * 100) + '%'}`,
        `Pass limit: ${result.pass_limit !== undefined ? result.pass_limit : 5.0}%, Reject limit: ${result.reject_limit !== undefined ? result.reject_limit : 8.0}%`
      ];

      // Remove jargon and sanitize wording
      const cleanDetails = rawDetails.map(d => {
        return d
          .replace(/across \d+ usable frames/gi, 'across photos used')
          .replace(/usable frames/gi, 'photos used')
          .replace(/classifier consensus/gi, 'material agreement')
          .replace(/multi-frame locked analysis/gi, 'photo analysis')
          .replace(/specimen/gi, 'sample')
          .replace(/(?:Material\s+)?Agreement:/gi, 'Material agreement:');
      });

      dom.howDecidedContent.innerHTML = cleanDetails.map(line => `
        <div style="margin-bottom:4px;display:flex;align-items:flex-start;gap:6px;">
          <span style="color:#94A3B8;">•</span>
          <span>${line}</span>
        </div>
      `).join('');
    }

    // 7. Footer line on peanut results: "Camera screening only. Not a lab test."
    if (dom.peanutFooter) {
      const mat = (fd.material || '').toLowerCase();
      if (mat.includes('peanut')) {
        dom.peanutFooter.style.display = 'block';
      } else {
        dom.peanutFooter.style.display = 'none';
      }
    }
  }

  // Requirement 2 & 5: Render Per-Kernel Breakdown Table
  function renderPerKernelBreakdownTable(trackedKernels) {
    if (!dom.perKernelTableBody) return;
    const kernels = trackedKernels || [];
    if (dom.perKernelCountBadge) {
      dom.perKernelCountBadge.textContent = `${kernels.length} kernel${kernels.length !== 1 ? 's' : ''}`;
    }

    if (kernels.length === 0) {
      dom.perKernelTableBody.innerHTML = `
        <tr>
          <td colspan="5" style="padding:14px;text-align:center;color:#64748B;font-style:italic;">
            No tracked kernels recorded for this scan.
          </td>
        </tr>
      `;
      return;
    }

    dom.perKernelTableBody.innerHTML = kernels.map(tk => {
      const kid = tk.id;
      const verdict = tk.majority_verdict || 'Normal';
      const vLower = verdict.toLowerCase();
      const isUncertain = verdict === 'Uncertain' || vLower.includes('uncertain');
      const isSuspect = !isUncertain && (vLower.includes('suspect') || (vLower.includes('mold') && !vLower.includes('not')));

      let badgeStyle = 'background:#DCFCE7;color:#166534;border:1px solid #BBF7D0;';
      let badgeLabel = '✓ Normal';
      if (isUncertain) {
        badgeStyle = 'background:#FEF3C7;color:#92400E;border:1px solid #FDE68A;';
        badgeLabel = '⚠ Uncertain';
      } else if (isSuspect) {
        badgeStyle = 'background:#FEE2E2;color:#991B1B;border:1px solid #FECACA;';
        badgeLabel = '✕ Suspect';
      }

      const votes = tk.vote_counts || {};
      const consensusText = votes.total
        ? `${votes.normal || 0}N / ${votes.suspect || 0}S / ${votes.uncertain || 0}U (${votes.total} frames)`
        : '5 frames';

      const why = tk.reason_why || (isSuspect ? 'Discoloured patch' : `Normal (score ${tk.representative_score || 0})`);
      const aiOp = tk.ai_opinion || (isSuspect ? 'AI: Defect' : 'AI: Healthy');

      return `
        <tr style="border-bottom:1px solid #F1F5F9;cursor:pointer;transition:background 0.15s;"
            onmouseover="this.style.background='#F8FAFC'"
            onmouseout="this.style.background='transparent'"
            onclick="CameraStationApp.openKernelInspector(0, ${kid})"
            title="Click to view Kernel #${kid} on sample photo">
          <td style="padding:9px 10px;font-weight:700;color:#0F172A;">#${kid}</td>
          <td style="padding:9px 10px;">
            <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;${badgeStyle}">
              ${badgeLabel}
            </span>
          </td>
          <td style="padding:9px 10px;color:#1E293B;font-weight:500;">
            ${why}
          </td>
          <td style="padding:9px 10px;color:#475569;font-size:11.5px;">
            ${consensusText}
          </td>
          <td style="padding:9px 10px;color:#64748B;font-size:11.5px;">
            ${aiOp}
          </td>
        </tr>
      `;
    }).join('');
  }

  // Requirement 4: Interactive Kernel Photo Inspector Modal
  let activeInspectorResult = null;
  let activeInspectorFrameIdx = 0;

  function openKernelInspector(frameIdx = 0, focusKernelId = null) {
    if (!lastLockedResult || !dom.kernelInspectorModal) return;
    activeInspectorResult = lastLockedResult;
    activeInspectorFrameIdx = frameIdx;

    const frames = lastLockedResult.best_frames || [];
    const frame = frames[frameIdx] || frames[0];
    if (!frame) return;

    const imgSrc = frame.annotated_path || frame.image_path;
    if (dom.kernelInspectorImage) {
      dom.kernelInspectorImage.src = imgSrc;
    }
    if (dom.kernelInspectorTitle) {
      dom.kernelInspectorTitle.textContent = `Sample Photo ${frameIdx + 1} of ${frames.length} — Click any kernel to inspect`;
    }

    if (dom.kernelHotspotsLayer) {
      dom.kernelHotspotsLayer.innerHTML = '';
      const tracked = lastLockedResult.tracked_kernels || [];

      tracked.forEach(tk => {
        const obs = (tk.observations || []).find(o => o.frame_id === frame.id);
        const b = obs ? obs.bbox : tk.bbox;
        if (!b) return;

        const verdict = tk.majority_verdict || 'Normal';
        const vLower = verdict.toLowerCase();
        const isUncertain = verdict === 'Uncertain' || vLower.includes('uncertain');
        const isSuspect = !isUncertain && (vLower.includes('suspect') || (vLower.includes('mold') && !vLower.includes('not')));

        let color = '#10B981';
        let badgeBg = '#10B981';
        if (isUncertain) {
          color = '#F59E0B';
          badgeBg = '#F59E0B';
        } else if (isSuspect) {
          color = '#EF4444';
          badgeBg = '#EF4444';
        }

        const hotspot = document.createElement('div');
        hotspot.style.position = 'absolute';
        hotspot.style.left = `${b.x * 100}%`;
        hotspot.style.top = `${b.y * 100}%`;
        hotspot.style.width = `${b.w * 100}%`;
        hotspot.style.height = `${b.h * 100}%`;
        hotspot.style.border = `3px solid ${color}`;
        hotspot.style.borderRadius = '3px';
        hotspot.style.cursor = 'pointer';
        hotspot.style.boxSizing = 'border-box';
        hotspot.style.pointerEvents = 'auto';
        hotspot.style.transition = 'background 0.15s';
        hotspot.dataset.kernelId = tk.id;

        const badge = document.createElement('div');
        badge.textContent = `#${tk.id}`;
        badge.style.position = 'absolute';
        badge.style.top = '-16px';
        badge.style.left = '-1px';
        badge.style.background = badgeBg;
        badge.style.color = '#FFFFFF';
        badge.style.fontSize = '10px';
        badge.style.fontWeight = '800';
        badge.style.padding = '0 4px';
        badge.style.borderRadius = '2px';
        badge.style.lineHeight = '14px';
        hotspot.appendChild(badge);

        hotspot.addEventListener('mouseenter', () => {
          hotspot.style.backgroundColor = isUncertain ? 'rgba(245, 158, 11, 0.25)' : (isSuspect ? 'rgba(239, 68, 68, 0.25)' : 'rgba(16, 185, 129, 0.25)');
        });
        hotspot.addEventListener('mouseleave', () => {
          if (hotspot.dataset.selected !== 'true') {
            hotspot.style.backgroundColor = 'transparent';
          }
        });

        hotspot.addEventListener('click', (e) => {
          e.stopPropagation();
          selectKernelInInspector(tk);
        });

        dom.kernelHotspotsLayer.appendChild(hotspot);

        if (focusKernelId && tk.id === focusKernelId) {
          selectKernelInInspector(tk);
        }
      });

      if (!focusKernelId && tracked.length > 0) {
        const firstSuspect = tracked.find(t => t.majority_verdict !== 'Normal') || tracked[0];
        selectKernelInInspector(firstSuspect);
      }
    }

    dom.kernelInspectorModal.style.display = 'flex';
  }

  function selectKernelInInspector(tk) {
    if (!tk || !dom.kernelDetailCard) return;
    const verdict = tk.majority_verdict || 'Normal';
    const vLower = verdict.toLowerCase();
    const isUncertain = verdict === 'Uncertain' || vLower.includes('uncertain');
    const isSuspect = !isUncertain && (vLower.includes('suspect') || (vLower.includes('mold') && !vLower.includes('not')));

    let badgeStyle = 'background:#DCFCE7;color:#166534;border:1px solid #BBF7D0;';
    let badgeText = '✓ Normal';
    if (isUncertain) {
      badgeStyle = 'background:#FEF3C7;color:#92400E;border:1px solid #FDE68A;';
      badgeText = '⚠ Uncertain';
    } else if (isSuspect) {
      badgeStyle = 'background:#FEE2E2;color:#991B1B;border:1px solid #FECACA;';
      badgeText = '✕ Suspect';
    }

    if (dom.kernelDetailTitle) {
      dom.kernelDetailTitle.textContent = `Kernel #${tk.id} • ${verdict}`;
    }
    if (dom.kernelDetailBadge) {
      dom.kernelDetailBadge.style.display = 'inline-block';
      dom.kernelDetailBadge.style.cssText += badgeStyle;
      dom.kernelDetailBadge.textContent = badgeText;
    }

    const why = tk.reason_why || (isSuspect ? 'Discoloured patch' : `Normal appearance`);
    if (dom.kernelDetailWhy) {
      dom.kernelDetailWhy.innerHTML = `<strong>Reason why:</strong> ${why}`;
    }

    const votes = tk.vote_counts || {};
    const consensusText = votes.total ? `${votes.normal || 0} Normal, ${votes.suspect || 0} Suspect, ${votes.uncertain || 0} Uncertain (${votes.total} frames)` : '5 frames locked';
    const aiOp = tk.ai_opinion || 'AI: Evaluated';
    if (dom.kernelDetailOpinion) {
      dom.kernelDetailOpinion.innerHTML = `<strong>5-Frame Consensus:</strong> ${consensusText} &nbsp;|&nbsp; <strong>AI Opinion:</strong> ${aiOp}`;
    }
    dom.kernelDetailCard.style.display = 'block';

    // Highlight selected hotspot in layer
    if (dom.kernelHotspotsLayer) {
      Array.from(dom.kernelHotspotsLayer.children).forEach(el => {
        if (parseInt(el.dataset.kernelId, 10) === tk.id) {
          el.dataset.selected = 'true';
          el.style.backgroundColor = isUncertain ? 'rgba(245, 158, 11, 0.35)' : (isSuspect ? 'rgba(239, 68, 68, 0.35)' : 'rgba(16, 185, 129, 0.35)');
          el.style.boxShadow = '0 0 10px rgba(255,255,255,0.7)';
        } else {
          el.dataset.selected = 'false';
          el.style.backgroundColor = 'transparent';
          el.style.boxShadow = 'none';
        }
      });
    }
  }

  function closeKernelInspector() {
    if (dom.kernelInspectorModal) {
      dom.kernelInspectorModal.style.display = 'none';
    }
  }

  // Handle Action (Approve, Reject, Retake)
  function handleAction(action) {
    if (action === 'RETAKE') {
      resetForNextSample();
      return;
    }

    const state = (lastLockedResult && lastLockedResult.final_decision && lastLockedResult.final_decision.state)
      ? lastLockedResult.final_decision.state.toUpperCase()
      : (lastLockedResult && lastLockedResult.suggestion ? lastLockedResult.suggestion.toUpperCase() : 'REVIEW');
    const stateTitle = state.charAt(0) + state.slice(1).toLowerCase();

    if (action === 'APPROVE') {
      if (state === 'PASS') {
        // Matches suggestion, no reason needed
        confirmVerdict('ACCEPT', '');
      } else {
        // Approving against suggestion requires reason
        pendingOverrideAction = 'ACCEPT';
        if (dom.cardOverrideReasonLabel) {
          dom.cardOverrideReasonLabel.textContent = `Reason required to approve lot (${stateTitle}):`;
        }
        if (dom.cardOverrideReasonInput) {
          dom.cardOverrideReasonInput.value = '';
        }
        if (dom.cardOverrideReasonBox) {
          dom.cardOverrideReasonBox.style.display = 'block';
          if (dom.cardOverrideReasonInput) dom.cardOverrideReasonInput.focus();
        }
      }
    } else if (action === 'REJECT') {
      if (state === 'REJECT') {
        // Matches suggestion, no reason needed
        confirmVerdict('REJECT', '');
      } else {
        // Rejecting against suggestion requires reason
        pendingOverrideAction = 'REJECT';
        if (dom.cardOverrideReasonLabel) {
          dom.cardOverrideReasonLabel.textContent = `Reason required to reject lot (${stateTitle}):`;
        }
        if (dom.cardOverrideReasonInput) {
          dom.cardOverrideReasonInput.value = '';
        }
        if (dom.cardOverrideReasonBox) {
          dom.cardOverrideReasonBox.style.display = 'block';
          if (dom.cardOverrideReasonInput) dom.cardOverrideReasonInput.focus();
        }
      }
    }
  }

  // Submit Override Reason
  function submitOverrideReason() {
    const reason = dom.cardOverrideReasonInput ? dom.cardOverrideReasonInput.value.trim() : '';
    if (!reason) {
      alert('A written reason is required when deciding against the suggestion.');
      return;
    }
    const act = pendingOverrideAction || 'ACCEPT';
    confirmVerdict(act, reason);
    if (dom.cardOverrideReasonBox) dom.cardOverrideReasonBox.style.display = 'none';
  }

  // Cancel Override Reason
  function cancelOverrideReason() {
    pendingOverrideAction = null;
    if (dom.cardOverrideReasonBox) dom.cardOverrideReasonBox.style.display = 'none';
  }

  // Inspector Confirmation Sign-Off (Accept / Reject)
  async function confirmVerdict(verdict, overrideNotes) {
    if (!sessionId) {
      alert("No active session ID.");
      return;
    }

    const notes = overrideNotes || '';
    const state = (lastLockedResult && lastLockedResult.final_decision && lastLockedResult.final_decision.state)
                  ? lastLockedResult.final_decision.state
                  : (lastLockedResult && lastLockedResult.suggestion ? lastLockedResult.suggestion.toUpperCase() : 'REVIEW');

    try {
      const res = await fetch(`/api/qc/live-session/${sessionId}/confirm-verdict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          verdict: verdict,
          notes: notes
        })
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        alert("Verdict submission error: " + (data.error || "Server error"));
        return;
      }

      // Hide buttons & reason box; show confirmation notice
      if (dom.cardActionButtonsRow) dom.cardActionButtonsRow.style.display = 'none';
      if (dom.cardOverrideReasonBox) dom.cardOverrideReasonBox.style.display = 'none';
      if (dom.verdictNotice) {
        dom.verdictNotice.style.display = 'block';
        if (dom.verdictNoticeText) {
          dom.verdictNoticeText.textContent = `Decision saved: Lot ${verdict === 'ACCEPT' ? 'approved' : 'rejected'}.`;
        }
      }

      if (dom.pdfReportLink && data.pdf_url) {
        dom.pdfReportLink.href = data.pdf_url;
        dom.pdfReportLink.style.display = 'inline-flex';
      }

    } catch (err) {
      alert("Network error: " + err.message);
    }
  }

  // Scan Next Sample
  async function resetForNextSample() {
    try {
      const res = await fetch(`/api/capture/${sessionToken}/reset-lock`, {
        method: 'POST'
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        alert("Could not reset sample: " + (data.error || "Server error"));
        return;
      }

      // Reset local state
      isLockedResultShowing = false;
      isLocking = false;
      steadyDuration = 0;
      pendingOverrideAction = null;
      updateSteadyBar(0);

      if (dom.cardOverrideReasonInput) dom.cardOverrideReasonInput.value = '';
      if (dom.cardOverrideReasonBox) dom.cardOverrideReasonBox.style.display = 'none';
      if (dom.resultCard) dom.resultCard.style.display = 'none';
      if (dom.liveSection) dom.liveSection.style.display = 'block';

      // Restore active station mode layout (framing guide, tips, etc.)
      setStationMode(stationMode);
      resizeCanvasToVideo();

    } catch (err) {
      alert("Network error resetting sample: " + err.message);
    }
  }

  // Lot Linking
  async function linkSessionLot(lotId) {
    if (!sessionId) return;
    try {
      const res = await fetch(`/api/qc/live-session/${sessionId}/link-lot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lot_id: lotId })
      });
      const data = await res.json();
      if (data.success) {
        console.log(`[Station] Lot linked: ${data.lot_number}`);
      }
    } catch (err) {
      console.warn("Could not link lot:", err);
    }
  }

  return {
    init,
    confirmVerdict,
    handleAction,
    submitOverrideReason,
    cancelOverrideReason,
    displayFinalResultCard,
    resetForNextSample,
    toggleCameraSetupPanel,
    startCameraTest,
    stopCameraTest,
    selectAndTestDevice,
    getPlainLanguageCameraError,
    openKernelInspector,
    closeKernelInspector,
    selectKernelInInspector,
    setStationMode,
    executeBurstScan,
    updateScanModeFromSelectedLot
  };
})();
