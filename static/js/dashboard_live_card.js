/**
 * FOOD MAN - DASHBOARD LIVE INSPECTION CARD CONTROLLER (PHASE 3)
 * Features:
 * 1. "Start Live Inspection" on a dedicated card, starting camera ONLY when clicked
 * 2. Stops stream immediately when user clicks Stop, leaves page, or closes tab
 * 3. In-card live preview with 1 FPS upload loop, 48x36 steady analyzer & 5-frame lock
 * 4. Displays latest final result: material, Good %, Defective %, Pass/Review/Reject, time
 * 5. Displays and auto-refreshes today's counters: samples checked, Pass, Review, Reject
 * 6. Non-secure LAN HTTP detection with "Open localhost version" button
 */

const DashboardLiveCard = (() => {
  // Session & Camera State
  let sessionToken = null;
  let sessionId = null;
  let videoStream = null;
  let isCameraRunning = false;
  let isUploading = false;
  let isLocking = false;
  let liveLoopTimer = null;
  let steadinessTimer = null;
  let counterRefreshTimer = null;

  // Steadiness tracking
  let prevSamplePixels = null;
  let steadyDuration = 0;
  const STEADY_REQ_MS = 2800;
  let latestItemCount = 0;

  // DOM Elements cache
  let dom = {};

  function init() {
    cacheDom();
    setupEvents();
    checkSecureContext();
    fetchTodaySummary();
    startCounterPolling();
  }

  function cacheDom() {
    dom = {
      btnToggle: document.getElementById('btnToggleDashCamera'),
      previewWrap: document.getElementById('dashLivePreviewWrap'),
      stage: document.getElementById('dashCameraStage'),
      video: document.getElementById('dashLiveVideo'),
      canvas: document.getElementById('dashOverlayCanvas'),
      hudGuidance: document.getElementById('dashHudGuidance'),
      hudGuidanceText: document.getElementById('dashHudGuidanceText'),
      steadyBar: document.getElementById('dashSteadyBar'),
      steadyBarFill: document.getElementById('dashSteadyBarFill'),
      flipToggle: document.getElementById('flipDashCameraToggle'),
      lanBanner: document.getElementById('dashLanWarningBanner'),
      btnOpenLocalhost: document.getElementById('btnDashOpenLocalhost'),

      // Counters
      countChecked: document.getElementById('dashCountChecked'),
      countPass: document.getElementById('dashCountPass'),
      countReview: document.getElementById('dashCountReview'),
      countReject: document.getElementById('dashCountReject'),

      // Latest Result Card (Rebuilt Component)
      resultBox: document.getElementById('dashLatestResultBox'),
      resultEmpty: document.getElementById('dashLatestResultEmpty'),
      cardStatusBanner: document.getElementById('dashCardStatusBanner'),
      cardStatusIcon: document.getElementById('dashCardStatusIcon'),
      cardStatusTitle: document.getElementById('dashCardStatusTitle'),
      cardStatusReason: document.getElementById('dashCardStatusReason'),
      latestMaterial: document.getElementById('dashLatestMaterial'),
      latestKernels: document.getElementById('dashLatestKernels'),
      latestDefectPct: document.getElementById('dashLatestDefectPct'),
      latestDefectNote: document.getElementById('dashLatestDefectNote'),
      latestGoodPct: document.getElementById('dashLatestGoodPct'),
      latestLot: document.getElementById('dashLatestLot'),
      latestSuggestion: document.getElementById('dashLatestSuggestion'),
      latestTime: document.getElementById('dashLatestTime'),
      latestConfBadge: document.getElementById('dashLatestConfBadge'),
      latestNextStep: document.getElementById('dashLatestNextStep'),
      latestActionButtonsRow: document.getElementById('dashLatestActionButtonsRow'),
      latestBestFramesGrid: document.getElementById('dashLatestBestFramesGrid'),
      howDecided: document.getElementById('dashHowDecided'),
      howDecidedContent: document.getElementById('dashHowDecidedContent'),
      peanutFooter: document.getElementById('dashPeanutFooter')
    };
  }

  function setupEvents() {
    if (dom.btnToggle) {
      dom.btnToggle.addEventListener('click', toggleCamera);
    }

    if (dom.flipToggle) {
      const savedFlip = localStorage.getItem('foodman_camera_flipped') === '1';
      dom.flipToggle.checked = savedFlip;
      if (dom.stage) dom.stage.classList.toggle('flipped', savedFlip);

      dom.flipToggle.addEventListener('change', () => {
        const isFlipped = dom.flipToggle.checked;
        localStorage.setItem('foodman_camera_flipped', isFlipped ? '1' : '0');
        if (dom.stage) dom.stage.classList.toggle('flipped', isFlipped);
      });
    }

    if (dom.btnOpenLocalhost) {
      dom.btnOpenLocalhost.addEventListener('click', () => {
        window.location.href = `http://localhost:5000/dashboard`;
      });
    }

    // Stop camera when leaving page or switching tabs
    window.addEventListener('beforeunload', stopCamera);
    window.addEventListener('pagehide', stopCamera);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden && isCameraRunning) {
        stopCamera();
      }
    });

    window.addEventListener('resize', resizeCanvas);
    if (dom.video) {
      dom.video.addEventListener('loadedmetadata', resizeCanvas);
    }
  }

  function checkSecureContext() {
    const isHttps = window.location.protocol === 'https:';
    const isLocalhost = window.location.hostname === 'localhost' || 
                        window.location.hostname === '127.0.0.1';

    if (!isHttps && !isLocalhost) {
      if (dom.lanBanner) dom.lanBanner.style.display = 'block';
      if (dom.btnToggle) dom.btnToggle.disabled = true;
      return false;
    }

    if (dom.lanBanner) dom.lanBanner.style.display = 'none';
    if (dom.btnToggle) dom.btnToggle.disabled = false;
    return true;
  }

  function startCounterPolling() {
    if (counterRefreshTimer) clearInterval(counterRefreshTimer);
    // Refresh counters every 4 seconds as requested in Requirement 3
    counterRefreshTimer = setInterval(fetchTodaySummary, 4000);
  }

  async function fetchTodaySummary() {
    try {
      const res = await fetch('/api/dashboard/live-inspection-summary');
      if (!res.ok) return;
      const data = await res.json();
      if (!data.success) return;

      // Update counters
      const c = data.counters || {};
      if (dom.countChecked) dom.countChecked.textContent = c.samples_checked || 0;
      if (dom.countPass) dom.countPass.textContent = c.pass || 0;
      if (dom.countReview) dom.countReview.textContent = c.review || 0;
      if (dom.countReject) dom.countReject.textContent = c.reject || 0;

      // Update latest result
      updateLatestResultDisplay(data.latest_result);

    } catch (e) {
      console.warn("Could not fetch today's inspection summary:", e);
    }
  }

  function updateLatestResultDisplay(res) {
    if (!res) {
      if (dom.resultEmpty) dom.resultEmpty.style.display = 'block';
      if (dom.resultBox) dom.resultBox.style.display = 'none';
      return;
    }

    if (dom.resultEmpty) dom.resultEmpty.style.display = 'none';
    if (dom.resultBox) dom.resultBox.style.display = 'block';

    const sanitizePlain = (str) => {
      if (!str) return '';
      return str
        .replace(/classifier consensus/gi, 'material agreement')
        .replace(/usable frames/gi, 'photos used')
        .replace(/multi-frame locked analysis/gi, 'photo analysis')
        .replace(/specimen/gi, 'sample')
        .replace(/Confirm Accept \(Approved\)/gi, 'Approved');
    };

    const fd = res.final_decision || {
      state: ((res.suggestion || "Review").toUpperCase()),
      reason: res.reason || "Inspection complete.",
      material: res.material || "Corn",
      kernels_checked: res.kernels_checked || res.items_counted || 0,
      defect_pct: res.defect_pct !== undefined ? res.defect_pct : null,
      next_step: res.next_step || "Review sample and determine lot disposition.",
      details: res.details || []
    };

    fd.reason = sanitizePlain(fd.reason || res.reason || '');
    fd.next_step = sanitizePlain(fd.next_step || res.next_step || '');

    const state = (fd.state || res.suggestion || "REVIEW").toUpperCase();
    const stateTitle = state.charAt(0) + state.slice(1).toLowerCase();

    // 1. Status Banner: ONLY coloured element (green, amber, red, grey)
    if (dom.cardStatusBanner) {
      let bg = '#FFFBEB';
      let border = '#FDE68A';
      let textCol = '#92400E';
      let iconSvg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';

      if (state === 'PASS') {
        bg = '#ECFDF5';
        border = '#A7F3D0';
        textCol = '#065F46';
        iconSvg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
      } else if (state === 'REJECT') {
        bg = '#FEF2F2';
        border = '#FECACA';
        textCol = '#991B1B';
        iconSvg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
      } else if (state === 'RETAKE') {
        bg = '#F1F5F9';
        border = '#CBD5E1';
        textCol = '#334155';
        iconSvg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>';
      }

      dom.cardStatusBanner.style.background = bg;
      dom.cardStatusBanner.style.borderColor = border;
      if (dom.cardStatusIcon) dom.cardStatusIcon.innerHTML = iconSvg;
      if (dom.cardStatusTitle) {
        dom.cardStatusTitle.style.color = textCol;
      }
      if (dom.latestSuggestion) {
        dom.latestSuggestion.textContent = stateTitle;
        dom.latestSuggestion.style.color = textCol;
      }
      if (dom.cardStatusReason) {
        dom.cardStatusReason.textContent = fd.reason || res.reason || '';
        dom.cardStatusReason.style.color = textCol;
      }
    }

    if (dom.latestLot) {
      dom.latestLot.textContent = res.lot_number ? `Lot #${res.lot_number}` : 'Unlinked';
    }
    if (dom.latestTime) {
      dom.latestTime.textContent = res.time || '--:--:--';
    }

    // 2. Three plain stats: Material, Kernels checked, Defective.
    if (dom.latestMaterial) {
      dom.latestMaterial.textContent = fd.material || res.material || 'Corn';
    }
    if (dom.latestKernels) {
      dom.latestKernels.textContent = (fd.kernels_checked !== undefined) ? fd.kernels_checked : (res.kernels_checked || 0);
    }
    if (dom.latestDefectPct) {
      if (fd.defect_pct !== null && fd.defect_pct !== undefined) {
        dom.latestDefectPct.textContent = `${fd.defect_pct}%`;
        if (dom.latestDefectNote) dom.latestDefectNote.style.display = 'none';
      } else {
        dom.latestDefectPct.textContent = 'Hidden';
        if (dom.latestDefectNote) dom.latestDefectNote.style.display = 'block';
      }
    }
    if (dom.latestGoodPct) {
      dom.latestGoodPct.textContent = (fd.defect_pct !== null && fd.defect_pct !== undefined) ? `${Math.round(100 - fd.defect_pct)}%` : '—';
    }

    // 3. "What to do next": one sentence and ONE primary button matching state
    if (dom.latestNextStep) {
      dom.latestNextStep.textContent = fd.next_step || 'Review sample and select next action.';
    }

    if (dom.latestActionButtonsRow) {
      dom.latestActionButtonsRow.innerHTML = '';
      const btnPrimaryStyle = 'background:#0F172A;color:#FFFFFF;border:1px solid #0F172A;font-weight:700;font-size:12px;padding:7px 14px;border-radius:6px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:6px;';
      const btnSecondaryStyle = 'background:#FFFFFF;color:#334155;border:1px solid #CBD5E1;font-weight:600;font-size:12px;padding:7px 14px;border-radius:6px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:6px;';

      const createLinkBtn = (label, isPrimary) => {
        const a = document.createElement('a');
        a.href = '/qc/station';
        a.style.cssText = isPrimary ? btnPrimaryStyle : btnSecondaryStyle;
        a.textContent = label;
        return a;
      };

      if (state === 'PASS') {
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Approve lot', true));
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Reject lot', false));
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Retake photo', false));
      } else if (state === 'REJECT') {
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Reject lot', true));
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Approve lot', false));
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Retake photo', false));
      } else if (state === 'RETAKE') {
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Retake photo', true));
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Approve lot', false));
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Reject lot', false));
      } else {
        // REVIEW
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Retake photo', true));
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Approve lot', false));
        dom.latestActionButtonsRow.appendChild(createLinkBtn('Reject lot', false));
      }
    }

    // 4. "Photos behind this result": three photos with flagged kernels outlined, click to enlarge, caption "n flagged of m kernels".
    if (dom.latestBestFramesGrid) {
      const frames = res.best_frames || [];
      if (frames.length > 0) {
        dom.latestBestFramesGrid.style.display = 'grid';
        dom.latestBestFramesGrid.innerHTML = frames.slice(0, 3).map((f, idx) => {
          const flagged = f.defect_count || 0;
          const total = (f.good_count || 0) + flagged;
          const imgSrc = f.annotated_path || f.image_path;
          return `
            <div style="border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;background:#F8FAFC;cursor:pointer;" onclick="window.open('${imgSrc}', '_blank')" title="Click to enlarge">
              <img src="${imgSrc}" alt="Sample photo ${idx + 1}" style="width:100%;height:95px;object-fit:cover;display:block;">
              <div style="padding:6px 8px;font-size:10.5px;font-weight:500;color:#475569;display:flex;justify-content:center;background:#FFFFFF;border-top:1px solid #E2E8F0;text-align:center;">
                <span>${flagged} flagged of ${total} kernels</span>
              </div>
            </div>
          `;
        }).join('');
      } else {
        dom.latestBestFramesGrid.style.display = 'none';
        dom.latestBestFramesGrid.innerHTML = '';
      }
    }

    // 5. Collapsed "How was this decided?" section
    if (dom.howDecided && dom.howDecidedContent) {
      dom.howDecided.open = false;
      const rawDetails = (fd.details && fd.details.length > 0) ? fd.details : [
        `Material agreement: ${res.material || 'Corn'}`,
        `Photos used: ${res.usable_frames || 5} of 5`,
        `Model confidence: ${res.confidence_percent || '95%'}`,
        `Pass limit: 5.0%, Reject limit: 8.0%`
      ];

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
        <div style="margin-bottom:3px;display:flex;align-items:flex-start;gap:6px;">
          <span style="color:#94A3B8;">•</span>
          <span>${line}</span>
        </div>
      `).join('');
    }

    // 7. Footer line on peanut results: "Camera screening only. Not a lab test."
    if (dom.peanutFooter) {
      const mat = (fd.material || res.material || '').toLowerCase();
      if (mat.includes('peanut')) {
        dom.peanutFooter.style.display = 'block';
      } else {
        dom.peanutFooter.style.display = 'none';
      }
    }
  }

  async function toggleCamera() {
    if (isCameraRunning) {
      stopCamera();
    } else {
      await startCamera();
    }
  }

  async function startCamera() {
    if (!checkSecureContext()) return;

    // Requirement 4: Camera must start only when clicked
    updateGuidance("Starting camera...", "⏳");
    if (dom.btnToggle) {
      dom.btnToggle.disabled = true;
      dom.btnToggle.textContent = 'Initializing...';
    }

    try {
      // 1. Ensure internal session exists
      if (!sessionToken) {
        const sessRes = await fetch('/api/qc/live-session/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const sessData = await sessRes.json();
        if (sessData.success && sessData.session) {
          sessionToken = sessData.session.token;
          sessionId = sessData.session.id;
        } else {
          throw new Error(sessData.error || "Could not initialize session");
        }
      }

      // 2. Build constraints with saved camera if exists
      const savedId = localStorage.getItem('foodman_camera_device_id');
      let constraints = {
        audio: false,
        video: savedId ? { deviceId: { exact: savedId }, width: { ideal: 1280 }, height: { ideal: 720 } }
                       : { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }
      };

      try {
        videoStream = await navigator.mediaDevices.getUserMedia(constraints);
      } catch (err) {
        videoStream = await navigator.mediaDevices.getUserMedia({ audio: false, video: true });
      }

      dom.video.srcObject = videoStream;
      await dom.video.play();

      isCameraRunning = true;
      if (dom.previewWrap) dom.previewWrap.style.display = 'block';

      if (dom.btnToggle) {
        dom.btnToggle.disabled = false;
        dom.btnToggle.innerHTML = '⏹ Stop Camera';
        dom.btnToggle.className = 'btn-secondary';
        dom.btnToggle.style.background = '#FEF2F2';
        dom.btnToggle.style.color = '#DC2626';
        dom.btnToggle.style.borderColor = '#FCA5A5';
      }

      resizeCanvas();
      startSteadinessDetector();
      startLiveStreamLoop();
      updateGuidance("Position specimen sample in frame", "🎯");

    } catch (err) {
      console.warn("Could not start camera:", err);
      if (dom.btnToggle) {
        dom.btnToggle.disabled = false;
        dom.btnToggle.innerHTML = '📹 Start Live Inspection';
        dom.btnToggle.className = 'btn-primary-action';
        dom.btnToggle.style.background = '#0F172A';
        dom.btnToggle.style.color = '#FFF';
      }
      alert("Camera access denied or unavailable: " + (err.message || err));
    }
  }

  function stopCamera() {
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
    isLocking = false;
    steadyDuration = 0;
    updateSteadyBar(0);

    if (dom.canvas) {
      const ctx = dom.canvas.getContext('2d');
      ctx.clearRect(0, 0, dom.canvas.width, dom.canvas.height);
    }

    if (dom.previewWrap) dom.previewWrap.style.display = 'none';

    if (dom.btnToggle) {
      dom.btnToggle.disabled = false;
      dom.btnToggle.innerHTML = '📹 Start Live Inspection';
      dom.btnToggle.className = 'btn-primary-action';
      dom.btnToggle.style.background = '#0F172A';
      dom.btnToggle.style.color = '#FFF';
      dom.btnToggle.style.borderColor = 'transparent';
    }
  }

  function resizeCanvas() {
    if (!dom.canvas || !dom.video) return;
    const rect = dom.video.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      dom.canvas.width = rect.width;
      dom.canvas.height = rect.height;
    }
  }

  function updateGuidance(text, icon = "🎯", isSteady = false, isLockingMode = false) {
    if (!dom.hudGuidance) return;
    if (dom.hudGuidanceText) dom.hudGuidanceText.textContent = text;
    dom.hudGuidance.className = 'hud-guidance' + (isLockingMode ? ' locking' : (isSteady ? ' steady' : ''));
  }

  function updateSteadyBar(percent) {
    if (!dom.steadyBar || !dom.steadyBarFill) return;
    if (percent > 0) {
      dom.steadyBar.style.display = 'block';
      dom.steadyBarFill.style.width = percent + '%';
    } else {
      dom.steadyBar.style.display = 'none';
      dom.steadyBarFill.style.width = '0%';
    }
  }

  // 48x36 Steadiness Detector
  function startSteadinessDetector() {
    if (steadinessTimer) clearInterval(steadinessTimer);

    const sampleCanvas = document.createElement('canvas');
    sampleCanvas.width = 48;
    sampleCanvas.height = 36;
    const sampleCtx = sampleCanvas.getContext('2d', { willReadFrequently: true });

    steadinessTimer = setInterval(() => {
      if (!isCameraRunning || isLocking) return;
      if (!dom.video || dom.video.readyState < 2) return;

      sampleCtx.drawImage(dom.video, 0, 0, 48, 36);
      const imgData = sampleCtx.getImageData(0, 0, 48, 36);
      const data = imgData.data;

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

      let diff = 0;
      if (prevSamplePixels) {
        for (let i = 0; i < count; i++) {
          diff += Math.abs(gray[i] - prevSamplePixels[i]);
        }
        diff = diff / count;
      }
      prevSamplePixels = gray;

      const isVeryDark = avgBrightness < 40;
      const isSteadyFrame = diff < 7.5;

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

      if (isSteadyFrame) {
        steadyDuration += 300;
        const pct = Math.min(100, Math.round((steadyDuration / STEADY_REQ_MS) * 100));
        updateSteadyBar(pct);

        if (steadyDuration >= STEADY_REQ_MS) {
          triggerLockSequence();
        } else {
          updateGuidance(`Hold steady... ${(steadyDuration / 1000).toFixed(1)}s`, "🎯", true);
        }
      } else {
        steadyDuration = Math.max(0, steadyDuration - 400);
        const pct = Math.min(100, Math.round((steadyDuration / STEADY_REQ_MS) * 100));
        updateSteadyBar(pct);
        updateGuidance("Hold steady", "✋");
      }
    }, 300);
  }

  // 1 FPS Live Streaming Loop
  function startLiveStreamLoop() {
    if (liveLoopTimer) clearInterval(liveLoopTimer);

    liveLoopTimer = setInterval(async () => {
      if (!isCameraRunning || isUploading || isLocking) return;
      if (!dom.video || dom.video.readyState < 2) return;

      await captureAndSendFrame(false);
    }, 1000);
  }

  async function captureAndSendFrame(isLockFrame = false) {
    if (isUploading && !isLockFrame) return null;
    isUploading = true;

    try {
      const vWidth = dom.video.videoWidth || 1280;
      const vHeight = dom.video.videoHeight || 720;

      const maxDim = 1280;
      const scale = Math.min(1, maxDim / Math.max(vWidth, vHeight));
      const targetW = Math.round(vWidth * scale);
      const targetH = Math.round(vHeight * scale);

      const capCanvas = document.createElement('canvas');
      capCanvas.width = targetW;
      capCanvas.height = targetH;
      const capCtx = capCanvas.getContext('2d');
      capCtx.drawImage(dom.video, 0, 0, targetW, targetH);

      const blob = await new Promise(resolve => capCanvas.toBlob(resolve, 'image/jpeg', 0.72));
      if (!blob) {
        isUploading = false;
        return null;
      }

      const formData = new FormData();
      formData.append('image', blob, 'dash_frame.jpg');
      if (isLockFrame) formData.append('lock', 'true');

      const res = await fetch(`/api/capture/${sessionToken}/frame`, {
        method: 'POST',
        body: formData
      });

      const data = await res.json();
      isUploading = false;

      if (!res.ok || !data.success) return null;

      handleFrameResponse(data);
      return data;

    } catch (err) {
      isUploading = false;
      return null;
    }
  }

  function handleFrameResponse(data) {
    const total = (data.good_count || 0) + (data.defect_count || 0);
    latestItemCount = total;

    // Draw boxes on overlay canvas
    drawBoxes(data.boxes || []);

    if (data.locked_result) {
      onLockCompleted(data.locked_result);
    }
  }

  function drawBoxes(boxes) {
    if (!dom.canvas) return;
    resizeCanvas();

    const ctx = dom.canvas.getContext('2d');
    const width = dom.canvas.width;
    const height = dom.canvas.height;

    ctx.clearRect(0, 0, width, height);

    boxes.forEach(box => {
      const bx = box.x * width;
      const by = box.y * height;
      const bw = box.w * width;
      const bh = box.h * height;

      const isDefect = box.type === 'defect';
      const color = isDefect ? '#EF4444' : '#10B981';
      const bgColor = isDefect ? 'rgba(239, 68, 68, 0.16)' : 'rgba(16, 185, 129, 0.16)';

      ctx.fillStyle = bgColor;
      ctx.fillRect(bx, by, bw, bh);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(bx, by, bw, bh);

      const label = `${box.class} (${Math.round((box.confidence || 0) * 100)}%)`;
      ctx.font = 'bold 11px Inter, -apple-system, sans-serif';
      const textWidth = ctx.measureText(label).width;
      ctx.fillStyle = color;
      ctx.fillRect(bx, Math.max(0, by - 16), textWidth + 6, 16);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillText(label, bx + 3, Math.max(12, by - 4));
    });
  }

  async function triggerLockSequence() {
    if (isLocking) return;
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
      onLockCompleted(finalLockedResult);
    } else {
      updateGuidance("Processing evaluation...", "⏳");
    }
  }

  function onLockCompleted(result) {
    updateGuidance(`Evaluation Complete: ${result.suggestion || 'Review'}!`, "✓");
    // Refresh counters and latest result from server
    fetchTodaySummary();

    // Auto reset lock after 3 seconds so user can scan another specimen
    setTimeout(async () => {
      if (sessionToken) {
        await fetch(`/api/capture/${sessionToken}/reset-lock`, { method: 'POST' });
        steadyDuration = 0;
        updateSteadyBar(0);
        updateGuidance("Position next sample in frame", "🎯");
      }
    }, 3000);
  }

  return {
    init,
    startCamera,
    stopCamera,
    fetchTodaySummary,
    updateLatestResultDisplay
  };
})();

document.addEventListener('DOMContentLoaded', DashboardLiveCard.init);
