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
  let videoStream = null;
  let isCameraRunning = false;
  let isUploading = false;
  let isLocking = false;
  let isLockedResultShowing = false;
  let liveLoopTimer = null;
  let steadinessTimer = null;

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

  function init(config) {
    sessionToken = config.token;
    sessionId = config.sessionId;
    currentLotId = config.lotId;

    cacheDomElements();
    setupEventListeners();
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

      // Result Card Elements
      resMaterial: document.getElementById('stationResultMaterial'),
      resConfBadge: document.getElementById('stationResultConfBadge'),
      resSuggestionBadge: document.getElementById('stationSuggestionBadge'),
      resItemsCount: document.getElementById('stationResultItemsCount'),
      resGoodPct: document.getElementById('stationResultGoodPct'),
      resDefectPct: document.getElementById('stationResultDefectPct'),
      resUsableFrames: document.getElementById('stationResultUsableFrames'),
      resWarnings: document.getElementById('stationResultWarnings'),
      resBestFramesGrid: document.getElementById('stationBestFramesGrid'),
      inspectorNotes: document.getElementById('stationInspectorNotes'),
      decisionActionsRow: document.getElementById('stationDecisionActionsRow'),
      verdictNotice: document.getElementById('stationVerdictConfirmedNotice'),
      verdictNoticeText: document.getElementById('stationVerdictNoticeText'),
      pdfReportLink: document.getElementById('stationPdfReportLink')
    };
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

      // Start steadiness detector & 1 FPS capture loop
      startSteadinessDetector();
      startLiveStreamLoop();

      updateGuidance("Position specimen sample in view", "🎯");
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
        startSteadinessDetector();
        startLiveStreamLoop();
        updateGuidance("Position specimen sample in view", "🎯");
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

      if (latestItemCount < 3) {
        updateGuidance("Include ≥ 3 items in frame", "📐");
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

    boxes.forEach(box => {
      const bx = box.x * width;
      const by = box.y * height;
      const bw = box.w * width;
      const bh = box.h * height;

      const isDefect = box.type === 'defect';
      const color = isDefect ? '#EF4444' : '#10B981';
      const bgColor = isDefect ? 'rgba(239, 68, 68, 0.16)' : 'rgba(16, 185, 129, 0.16)';

      // Box fill and stroke
      ctx.fillStyle = bgColor;
      ctx.fillRect(bx, by, bw, bh);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      ctx.strokeRect(bx, by, bw, bh);

      // Label background & text
      const label = `${box.class} (${Math.round((box.confidence || 0) * 100)}%)`;
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

  // Final Result Card (Requirement 2)
  function displayFinalResultCard(result) {
    isLockedResultShowing = true;

    // Clear overlay boxes
    if (dom.overlayCanvas) {
      const ctx = dom.overlayCanvas.getContext('2d');
      ctx.clearRect(0, 0, dom.overlayCanvas.width, dom.overlayCanvas.height);
    }

    // Switch view
    if (dom.liveSection) dom.liveSection.style.display = 'none';
    if (dom.resultCard) dom.resultCard.style.display = 'block';

    // Populate Material & Confidence (Phase 3 Requirement 5: "Material: Peanut (classifier 97%)")
    const rawMat = result.material || "Specimen Scan";
    const displayMat = rawMat.startsWith("Material:") ? rawMat : `Material: ${rawMat}`;
    if (dom.resMaterial) dom.resMaterial.textContent = displayMat;
    if (dom.resConfBadge) dom.resConfBadge.textContent = `${result.confidence_percent || '--%'} Confidence`;

    // Populate Suggestion Badge
    if (dom.resSuggestionBadge) {
      const sugg = result.suggestion || "Manual Review";
      dom.resSuggestionBadge.textContent = sugg;
      if (sugg === 'Pass') {
        dom.resSuggestionBadge.className = 'status-pill status-pass';
        dom.resSuggestionBadge.textContent = '✓ PASS (High Quality)';
      } else if (sugg === 'Reject') {
        dom.resSuggestionBadge.className = 'status-pill status-reject';
        dom.resSuggestionBadge.textContent = '✕ REJECT (Defective)';
      } else if (sugg === 'Retake') {
        dom.resSuggestionBadge.className = 'status-pill status-retake';
        dom.resSuggestionBadge.textContent = '🔄 RETAKE REQUIRED';
      } else {
        dom.resSuggestionBadge.className = 'status-pill status-review';
        dom.resSuggestionBadge.textContent = '⚠ MANUAL REVIEW REQUIRED';
      }
    }

    // Populate 4-box metrics grid
    if (dom.resItemsCount) dom.resItemsCount.textContent = result.items_counted || result.total_items_counted || 0;
    if (dom.resGoodPct) dom.resGoodPct.textContent = `${(result.good_pct !== undefined ? result.good_pct : 0)}%`;
    if (dom.resDefectPct) dom.resDefectPct.textContent = `${(result.defect_pct !== undefined ? result.defect_pct : 0)}%`;
    if (dom.resUsableFrames) dom.resUsableFrames.textContent = `${result.usable_frames || 5}/5`;

    // Populate Warnings & Scan Mode Mismatch Alert
    if (dom.resWarnings) {
      let warnings = [...(result.warnings || [])];
      if (result.scan_mode_warning && !warnings.includes(result.scan_mode_warning)) {
        warnings.unshift(result.scan_mode_warning);
      }
      if (warnings.length > 0) {
        dom.resWarnings.innerHTML = warnings.map(w => `
          <div style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:6px;padding:8px 12px;font-size:12px;color:#92400E;display:flex;align-items:center;gap:8px;">
            <span>⚠️</span>
            <span>${w}</span>
          </div>
        `).join('');
        dom.resWarnings.style.display = 'flex';
      } else {
        dom.resWarnings.style.display = 'none';
        dom.resWarnings.innerHTML = '';
      }
    }

    // Populate Best 3 Frames Gallery
    if (dom.resBestFramesGrid) {
      const frames = result.best_frames || [];
      dom.resBestFramesGrid.innerHTML = frames.map((f, idx) => `
        <div style="border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;background:#F8FAFC;cursor:pointer;" onclick="window.open('${f.annotated_path || f.image_path}', '_blank')" title="Frame #${f.id} - Click to enlarge">
          <img src="${f.annotated_path || f.image_path}" alt="Specimen Frame ${idx + 1}" style="width:100%;height:130px;object-fit:cover;display:block;">
          <div style="padding:6px 8px;font-size:11px;font-weight:700;color:#475569;display:flex;justify-content:space-between;background:#FFF;border-top:1px solid #E2E8F0;">
            <span>Sample #${idx + 1}</span>
            <span style="color:#059669;">Good: ${f.good_count || 0}</span>
          </div>
        </div>
      `).join('');
    }

    // Reset Decision Actions
    if (dom.decisionActionsRow) dom.decisionActionsRow.style.display = 'flex';
    if (dom.verdictNotice) dom.verdictNotice.style.display = 'none';
  }

  // Inspector Confirmation Sign-Off (Accept / Reject)
  async function confirmVerdict(verdict) {
    if (!sessionId) {
      alert("No active session ID.");
      return;
    }

    const notes = dom.inspectorNotes ? dom.inspectorNotes.value.trim() : '';
    const btnAccept = document.getElementById('btnConfirmAccept');
    const btnReject = document.getElementById('btnConfirmReject');
    if (btnAccept) btnAccept.disabled = true;
    if (btnReject) btnReject.disabled = true;

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
      if (btnAccept) btnAccept.disabled = false;
      if (btnReject) btnReject.disabled = false;

      if (!res.ok || !data.success) {
        alert("Verdict submission error: " + (data.error || "Server error"));
        return;
      }

      // Hide action buttons and display verdict notice
      if (dom.decisionActionsRow) dom.decisionActionsRow.style.display = 'none';
      if (dom.verdictNotice) {
        dom.verdictNotice.style.display = 'block';
        if (dom.verdictNoticeText) {
          dom.verdictNoticeText.textContent = `Verdict Confirmed: ${verdict === 'ACCEPT' ? 'ACCEPTED (Approved)' : 'REJECTED'}`;
        }
      }

      if (dom.pdfReportLink && data.pdf_url) {
        dom.pdfReportLink.href = data.pdf_url;
        dom.pdfReportLink.style.display = 'inline-flex';
      }

    } catch (err) {
      if (btnAccept) btnAccept.disabled = false;
      if (btnReject) btnReject.disabled = false;
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
      updateSteadyBar(0);

      if (dom.inspectorNotes) dom.inspectorNotes.value = '';
      if (dom.resultCard) dom.resultCard.style.display = 'none';
      if (dom.liveSection) dom.liveSection.style.display = 'block';

      updateGuidance("Position new specimen in frame", "🎯");
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
    resetForNextSample,
    toggleCameraSetupPanel,
    startCameraTest,
    stopCameraTest,
    selectAndTestDevice,
    getPlainLanguageCameraError
  };
})();
