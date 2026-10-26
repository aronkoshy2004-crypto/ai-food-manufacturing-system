/**
 * FOOD MAN - QC LIVE INSPECTION CONTROLLER
 * Phase 1: Real-time QR pairing, 1-second polling, live view updates,
 * counts/status metrics, and session lifecycle management.
 * Phase 2: Live camera mode with "hold steady, then lock", multi-frame
 * evaluation, Final Result Card on laptop, inspector Accept/Reject
 * lot status confirmation, PDF generation, and "Scan next sample" reset.
 */

const LiveInspectionApp = (() => {
  let activeSessionId = null;
  let pollInterval = null;
  let lastKnownFrameId = null;
  let isViewingHistory = false;
  let cachedLatestFrame = null;
  let isShowingLockedResult = false;
  let lastLockedResult = null;
  let currentSessionUrls = null;
  let currentQrMode = 'tunnel'; // 'tunnel' or 'lan'


  function init(initialSession) {
    if (initialSession && initialSession.session && initialSession.session.is_active) {
      activeSessionId = initialSession.session.id;
      renderSessionActive(initialSession);
      startPolling();
    } else {
      renderSessionInactive();
    }
  }

  function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    // Initial immediate poll
    pollLatest();
    // Poll every 1000ms (1 second) as specified in Requirement E
    pollInterval = setInterval(pollLatest, 1000);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  async function pollLatest() {
    if (!activeSessionId) return;

    try {
      const res = await fetch(`/api/qc/live-session/${activeSessionId}/latest`);
      if (!res.ok) {
        if (res.status === 404 || res.status === 410) {
          stopPolling();
          onSessionEnded('Session has ended or expired.');
        }
        return;
      }

      const data = await res.json();
      if (!data.success) return;

      // Check if session status has changed
      if (data.session.status !== 'ACTIVE') {
        stopPolling();
        onSessionEnded(`Session ${data.session.status.toLowerCase()}.`);
        return;
      }

      // Phase 3 Requirement 4: Automatically pick up new public link from .public_url for QR
      if (data.capture_url) {
        currentSessionUrls = data;
        applyQrDisplay();
      }

      // Phase 2: Check for Multi-Frame Locked Result
      if (data.session.locked_result) {
        renderLaptopFinalResult(data.session.locked_result, data.session);
        return;
      } else if (isShowingLockedResult) {
        // If locked result was cleared (e.g. "Scan next sample" clicked from phone)
        isShowingLockedResult = false;
        const liveCard = document.getElementById('liveMonitorWorkspaceCard');
        const resCard = document.getElementById('laptopFinalResultCard');
        if (liveCard) liveCard.style.display = 'block';
        if (resCard) resCard.style.display = 'none';
      }

      // Update frame counts badge
      const totalCountElem = document.getElementById('liveTotalFramesBadge');
      if (totalCountElem) {
        totalCountElem.textContent = `${data.total_frames || 0} frame(s)`;
      }

      // Check for newest frame
      if (data.latest_frame) {
        cachedLatestFrame = data.latest_frame;
        if (data.latest_frame.id !== lastKnownFrameId) {
          lastKnownFrameId = data.latest_frame.id;
          if (!isViewingHistory) {
            displayFrame(data.latest_frame, true);
          }
        }
      }

      // Update thumbnail history strip
      if (data.history && data.history.length > 0) {
        renderThumbnails(data.history);
      }

    } catch (err) {
      console.warn('[LiveInspection] Polling error:', err);
    }
  }

  function displayFrame(frame, isNewArrival = false) {
    const imgElem = document.getElementById('liveLatestImage');
    const waitingElem = document.getElementById('liveWaitingState');
    const statusBadge = document.getElementById('liveStatusBadge');
    const goodBadge = document.getElementById('liveGoodCountBadge');
    const defectBadge = document.getElementById('liveDefectCountBadge');
    const materialBadge = document.getElementById('liveMaterialBadge');
    const confBadge = document.getElementById('liveConfidenceBadge');
    const frameTimeElem = document.getElementById('liveFrameTime');

    if (waitingElem) waitingElem.style.display = 'none';
    if (imgElem) {
      imgElem.src = frame.annotated_path || frame.image_path;
      imgElem.style.display = 'block';
      if (isNewArrival) {
        imgElem.style.animation = 'none';
        void imgElem.offsetWidth; // trigger reflow
        imgElem.style.animation = 'flashHighlight 0.6s ease';
      }
    }

    const defects = frame.defect_count || 0;
    const goods = frame.good_count || 0;
    const material = frame.material || 'Specimen';
    const conf = Math.round((frame.avg_confidence || 0) * 100);

    if (statusBadge) {
      if (defects > 0) {
        statusBadge.textContent = `⚠ ${defects} Defect(s) Detected`;
        statusBadge.className = 'status-pill status-pill-rejected';
      } else if (goods > 0) {
        statusBadge.textContent = `✓ Clean (${goods} Healthy)`;
        statusBadge.className = 'status-pill status-pill-approved';
      } else {
        statusBadge.textContent = '✓ Inspected (No Defects)';
        statusBadge.className = 'status-pill status-pill-approved';
      }
    }

    if (goodBadge) goodBadge.textContent = goods;
    if (defectBadge) defectBadge.textContent = defects;
    if (materialBadge) materialBadge.textContent = material;
    if (confBadge) confBadge.textContent = `${conf}%`;
    if (frameTimeElem) frameTimeElem.textContent = frame.created_at || '';
  }

  function renderThumbnails(historyList) {
    const container = document.getElementById('liveThumbnailStrip');
    const countElem = document.getElementById('thumbCount');
    if (!container) return;

    if (countElem) countElem.textContent = historyList.length;

    container.innerHTML = historyList.map((f, idx) => {
      const isDefect = (f.defect_count || 0) > 0;
      const isSelected = lastKnownFrameId === f.id && !isViewingHistory;
      return `
        <div class="live-thumb-card ${isSelected ? 'active-thumb' : ''}" 
             onclick="LiveInspectionApp.selectHistoricalFrame(${JSON.stringify(f).replace(/"/g, '&quot;')})"
             title="Frame #${f.id} at ${f.created_at}">
          <div class="thumb-img-wrapper">
            <img src="${f.annotated_path || f.image_path}" class="thumb-img" alt="Frame ${f.id}">
            <span class="thumb-badge ${isDefect ? 'badge-defect' : 'badge-clean'}">
              ${isDefect ? `${f.defect_count} Defect` : 'Clean'}
            </span>
          </div>
          <div class="thumb-meta">
            <span class="thumb-time">${f.created_at}</span>
            <span class="thumb-id">#${f.id}</span>
          </div>
        </div>
      `;
    }).join('');
  }

  function selectHistoricalFrame(frame) {
    isViewingHistory = true;
    displayFrame(frame, false);

    const banner = document.getElementById('historyNoticeBanner');
    if (banner) {
      banner.style.display = 'flex';
      const text = document.getElementById('historyNoticeText');
      if (text) text.textContent = `Viewing Historical Frame #${frame.id} (${frame.created_at}).`;
    }
  }

  function returnToLive() {
    isViewingHistory = false;
    const banner = document.getElementById('historyNoticeBanner');
    if (banner) banner.style.display = 'none';

    if (cachedLatestFrame) {
      displayFrame(cachedLatestFrame, false);
    }
  }

  // =========================================================================
  // PHASE 2: LAPTOP FINAL RESULT CARD & INSPECTOR VERDICT CONFIRMATION
  // =========================================================================
  function renderLaptopFinalResult(result, session) {
    isShowingLockedResult = true;

    const liveCard = document.getElementById('liveMonitorWorkspaceCard');
    const resCard = document.getElementById('laptopFinalResultCard');
    if (liveCard) liveCard.style.display = 'none';
    if (resCard) resCard.style.display = 'block';

    // Material and Confidence
    const matElem = document.getElementById('laptopResultMaterial');
    const confBadge = document.getElementById('laptopResultConfBadge');
    if (matElem) matElem.textContent = result.material || "Specimen";
    if (confBadge) confBadge.textContent = `${result.confidence_percent || '--%'} Confidence`;

    lastLockedResult = result;
    const fd = result.final_decision;
    const state = (fd && fd.state) ? fd.state : (result.suggestion || "Review").toUpperCase();

    // Suggestion Badge
    const suggBadge = document.getElementById('laptopSuggestionBadge');
    if (suggBadge) {
      if (state === 'PASS') {
        suggBadge.className = 'status-pill status-pill-approved';
        suggBadge.textContent = '✓ PASS (Recommended Approval)';
      } else if (state === 'REJECT') {
        suggBadge.className = 'status-pill status-pill-rejected';
        suggBadge.textContent = '✕ REJECT (Defects Exceed Tolerance)';
      } else if (state === 'RETAKE') {
        suggBadge.className = 'status-pill status-pill-hold';
        suggBadge.textContent = '🔄 RETAKE REQUIRED';
      } else {
        suggBadge.className = 'status-pill status-pill-hold';
        suggBadge.textContent = '⚠ MANUAL REVIEW REQUIRED';
      }
    }

    // Metrics Grid
    const itemsElem = document.getElementById('laptopResultItemsCount');
    const goodElem = document.getElementById('laptopResultGoodPct');
    const defectElem = document.getElementById('laptopResultDefectPct');
    const usableElem = document.getElementById('laptopResultUsableFrames');
    if (itemsElem) itemsElem.textContent = (fd && fd.kernels_checked !== undefined) ? `${fd.kernels_checked}/frame` : (result.items_counted ? `${result.items_counted}/frame` : '0');
    
    // Hide percentages if defect_pct is null (Requirement 3)
    const showPct = (fd && fd.defect_pct !== null && fd.defect_pct !== undefined) || (!fd && result.defect_pct !== null && result.defect_pct !== undefined && state !== 'RETAKE');
    if (goodElem) goodElem.textContent = showPct ? `${(result.good_pct !== undefined ? result.good_pct : Math.round(100 - (fd ? fd.defect_pct : result.defect_pct)))}%` : '—';
    if (defectElem) defectElem.textContent = showPct ? `${(fd ? fd.defect_pct : result.defect_pct)}%` : '—';
    if (usableElem) usableElem.textContent = `${result.usable_frames_count || 0}/${result.total_frames_count || 5}`;

    // Final Decision Box
    const fdBox = document.getElementById('laptopFinalDecisionBox');
    if (fdBox && fd) {
      fdBox.style.display = 'block';
      const badge = document.getElementById('laptopDecisionStateBadge');
      const rEl = document.getElementById('laptopDecisionReason');
      const nextEl = document.getElementById('laptopDecisionNextStep');
      const detEl = document.getElementById('laptopDecisionDetails');
      if (badge) {
        badge.textContent = fd.state;
        badge.className = `status-pill status-${fd.state.toLowerCase()}`;
      }
      if (rEl) rEl.textContent = fd.reason || '';
      if (nextEl) nextEl.textContent = fd.next_step ? `👉 Next step: ${fd.next_step}` : '';
      if (detEl) detEl.innerHTML = (fd.details || []).map(d => `<div>• ${d}</div>`).join('');
    }

    // Warnings
    const warnContainer = document.getElementById('laptopResultWarnings');
    if (warnContainer) {
      const warnings = result.warnings || [];
      if (warnings.length > 0) {
        warnContainer.innerHTML = warnings.map(w => `
          <div style="background:#FFFBEB;border:1px solid #FDE68A;border-left:4px solid #D97706;padding:8px 12px;border-radius:6px;font-size:12px;color:#92400E;display:flex;align-items:center;gap:8px;">
            <span style="font-size:14px;">⚠️</span>
            <span>${w}</span>
          </div>
        `).join('');
        warnContainer.style.display = 'flex';
      } else {
        warnContainer.style.display = 'none';
        warnContainer.innerHTML = '';
      }
    }

    // Best 3 Annotated Frames Gallery (Requirement 4: "n flagged of m kernels")
    const gridElem = document.getElementById('laptopBestFramesGrid');
    if (gridElem) {
      const frames = result.best_frames || [];
      gridElem.innerHTML = frames.map((f, idx) => {
        const flagged = f.defect_count || 0;
        const total = (f.good_count || 0) + (f.defect_count || 0);
        return `
        <div style="border-radius:8px;overflow:hidden;border:1px solid #CBD5E1;background:#0F172A;position:relative;cursor:pointer;" 
             onclick="window.open('${f.annotated_path || f.image_path}', '_blank')" 
             title="Frame #${f.id} - Tap to view full size">
          <img src="${f.annotated_path || f.image_path}" style="width:100%;height:130px;object-fit:cover;display:block;" alt="Locked Frame ${idx+1}">
          <div style="position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,0.75);padding:4px 8px;font-size:10px;color:#FFF;display:flex;justify-content:space-between;">
            <span>Frame #${idx+1} (${f.material || 'Specimen'})</span>
            <span style="color:${flagged > 0 ? '#F87171' : '#34D399'};">${flagged} flagged of ${total} kernels</span>
          </div>
        </div>
      `;
      }).join('');
    }

    // Check if session is already linked to ai_inspection_id
    if (session && session.ai_inspection_id) {
      showVerdictConfirmed(session.ai_inspection_id, session.status || 'APPROVED');
    }
  }

  // Requirement D & Requirement 5: Inspector Confirms Accept or Reject
  async function confirmVerdict(verdict) {
    if (!activeSessionId) return;

    const notesElem = document.getElementById('laptopInspectorNotes');
    let notes = notesElem ? notesElem.value.trim() : '';

    const state = (lastLockedResult && lastLockedResult.final_decision && lastLockedResult.final_decision.state)
                  ? lastLockedResult.final_decision.state
                  : (lastLockedResult && lastLockedResult.suggestion ? lastLockedResult.suggestion.toUpperCase() : 'REVIEW');

    const isAccept = (verdict === 'ACCEPT' || verdict === 'PASS' || verdict === 'APPROVED');
    const isOverride = (isAccept && state !== 'PASS') || (!isAccept && state !== 'REJECT');

    if (isOverride && !notes) {
      const promptReason = prompt(`Analysis state is ${state}. A written override reason is mandatory to ${isAccept ? 'approve' : 'reject'} this lot:`);
      if (!promptReason || !promptReason.trim()) {
        alert(`Action cancelled. A written reason is required when approving a lot that is not PASS or rejecting a lot that is not REJECT.`);
        return;
      }
      notes = promptReason.trim();
      if (notesElem) notesElem.value = notes;
    }

    const confirmed = confirm(`Are you sure you want to confirm '${verdict}' for this sample inspection?\n\nThis will update the linked raw material lot status and log an official QC Decision.`);
    if (!confirmed) return;

    try {
      const res = await fetch(`/api/qc/live-session/${activeSessionId}/confirm-verdict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          verdict: verdict,
          notes: notes
        })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        alert('Could not record verdict: ' + (data.error || 'Server error'));
        return;
      }

      showVerdictConfirmed(data.inspection_id, data.final_status, data.pdf_url);

    } catch (err) {
      alert('Network error while recording verdict: ' + err.message);
    }
  }

  function showVerdictConfirmed(inspectionId, status, pdfUrl = null) {
    const actionsRow = document.getElementById('laptopDecisionActionsRow');
    const noticeBox = document.getElementById('laptopVerdictConfirmedNotice');
    const noticeText = document.getElementById('laptopVerdictNoticeText');
    const pdfLink = document.getElementById('laptopPdfReportLink');

    if (actionsRow) actionsRow.style.display = 'none';
    if (noticeBox) noticeBox.style.display = 'block';

    if (noticeText) {
      noticeText.textContent = `✓ QC Officer Verdict Confirmed: [${status}]`;
      noticeText.style.color = status === 'APPROVED' ? '#065F46' : '#991B1B';
    }

    if (pdfLink) {
      pdfLink.href = pdfUrl || `/api/qc/ai-inspection/${inspectionId}/pdf`;
    }
  }

  // Scan Next Sample Reset
  async function resetLockForNextSample() {
    if (!activeSessionId) return;

    try {
      const res = await fetch(`/api/qc/live-session/${activeSessionId}/reset-lock`, {
        method: 'POST'
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        alert('Could not reset session for next sample: ' + (data.error || 'Server error'));
        return;
      }

      isShowingLockedResult = false;
      const liveCard = document.getElementById('liveMonitorWorkspaceCard');
      const resCard = document.getElementById('laptopFinalResultCard');
      const actionsRow = document.getElementById('laptopDecisionActionsRow');
      const noticeBox = document.getElementById('laptopVerdictConfirmedNotice');

      if (liveCard) liveCard.style.display = 'block';
      if (resCard) resCard.style.display = 'none';
      if (actionsRow) actionsRow.style.display = 'flex';
      if (noticeBox) noticeBox.style.display = 'none';

      const notesElem = document.getElementById('laptopInspectorNotes');
      if (notesElem) notesElem.value = '';

    } catch (err) {
      alert('Network error: ' + err.message);
    }
  }

  async function startNewSession() {
    const lotSelect = document.getElementById('liveLotSelect');
    const lotId = lotSelect ? lotSelect.value : null;

    const btnStart = document.getElementById('btnStartLiveSession');
    if (btnStart) {
      btnStart.disabled = true;
      btnStart.textContent = 'Starting...';
    }

    try {
      const res = await fetch('/api/qc/live-session/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lot_id: lotId || null })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        alert('Could not start live session: ' + (data.error || 'Server error'));
        if (btnStart) {
          btnStart.disabled = false;
          btnStart.textContent = '🚀 Start Session';
        }
        return;
      }

      activeSessionId = data.session.id;
      lastKnownFrameId = null;
      isViewingHistory = false;
      cachedLatestFrame = null;
      isShowingLockedResult = false;

      renderSessionActive(data);
      startPolling();

    } catch (err) {
      alert('Error connecting to server: ' + err.message);
      if (btnStart) {
        btnStart.disabled = false;
        btnStart.textContent = '🚀 Start Session';
      }
    }
  }

  async function closeSession() {
    if (!activeSessionId) return;

    const confirmed = confirm(
      'Are you sure you want to close this live inspection session?\n\n' +
      '• The session token will be permanently invalidated.\n' +
      '• Temporary non-final frame image files will be cleaned from disk.\n' +
      '• The final captured frame will be preserved for the inspection record.'
    );
    if (!confirmed) return;

    stopPolling();

    const btnClose = document.getElementById('btnCloseLiveSession');
    if (btnClose) {
      btnClose.disabled = true;
      btnClose.textContent = 'Closing...';
    }

    try {
      const res = await fetch(`/api/qc/live-session/${activeSessionId}/close`, {
        method: 'POST'
      });
      const data = await res.json();

      if (data.success) {
        alert(`Session Closed!\n${data.message}`);
        window.location.reload();
      } else {
        alert('Error closing session: ' + (data.error || 'Unknown error'));
        if (btnClose) {
          btnClose.disabled = false;
          btnClose.textContent = '🛑 Close Session';
        }
      }
    } catch (err) {
      alert('Network error while closing session: ' + err.message);
      if (btnClose) {
        btnClose.disabled = false;
        btnClose.textContent = '🛑 Close Session';
      }
    }
  }

  function setQrMode(mode) {
    currentQrMode = mode;
    applyQrDisplay();
  }

  function applyQrDisplay() {
    if (!currentSessionUrls) return;

    const qrImg = document.getElementById('sessionQrImg');
    const linkInput = document.getElementById('sessionCaptureUrl');
    const urlLabel = document.getElementById('sessionCaptureUrlLabel');
    const btnTunnel = document.getElementById('btnModeTunnel');
    const btnLan = document.getElementById('btnModeLan');
    const warningBox = document.getElementById('liveHttpsWarningBox');
    const tipText = document.getElementById('qrNetworkGuidanceText');

    const hasTunnel = currentSessionUrls.has_public_tunnel;

    if (currentQrMode === 'lan' || !hasTunnel) {
      // Show LAN URL
      const lanUrl = currentSessionUrls.lan_capture_url || currentSessionUrls.capture_url;
      const lanQr = currentSessionUrls.lan_qr_data_url || currentSessionUrls.qr_data_url;

      if (qrImg && lanQr) qrImg.src = lanQr;
      if (linkInput && lanUrl) linkInput.value = lanUrl;
      if (urlLabel) urlLabel.textContent = "Phone Capture Link (Local Wi-Fi LAN)";

      if (btnLan) {
        btnLan.style.background = '#4F46E5';
        btnLan.style.color = '#FFFFFF';
      }
      if (btnTunnel) {
        btnTunnel.style.background = 'transparent';
        btnTunnel.style.color = '#475569';
      }

      if (warningBox) {
        warningBox.style.display = 'flex';
      }
      if (tipText) {
        tipText.innerHTML = "<strong>Local Wi-Fi Mode Active:</strong> Direct router connection (no internet required). Use the <strong>'Take Photo'</strong> button on your phone to inspect food specimens!";
      }
    } else {
      // Show Tunnel HTTPS URL
      const tunnelUrl = currentSessionUrls.public_capture_url || currentSessionUrls.capture_url;
      const tunnelQr = currentSessionUrls.public_qr_data_url || currentSessionUrls.qr_data_url;

      if (qrImg && tunnelQr) qrImg.src = tunnelQr;
      if (linkInput && tunnelUrl) linkInput.value = tunnelUrl;
      if (urlLabel) urlLabel.textContent = "Phone Capture Link (HTTPS Tunnel)";

      if (btnTunnel) {
        btnTunnel.style.background = '#4F46E5';
        btnTunnel.style.color = '#FFFFFF';
      }
      if (btnLan) {
        btnLan.style.background = 'transparent';
        btnLan.style.color = '#475569';
      }

      if (warningBox) {
        warningBox.style.display = 'none';
      }
      if (tipText) {
        tipText.innerHTML = "<strong>Network Tip:</strong> If your mobile network blocks <em>trycloudflare.com</em> (showing 'This site can't be reached'), tap <strong>Local Wi-Fi</strong> above to connect directly over Wi-Fi!";
      }
    }
  }

  function renderSessionActive(sessionData) {
    const inactiveCard = document.getElementById('liveInactiveCard');
    const activeCard = document.getElementById('liveActiveCard');
    const liveMonitor = document.getElementById('liveMonitorWorkspaceCard');

    if (inactiveCard) inactiveCard.style.display = 'none';
    if (activeCard) activeCard.style.display = 'block';
    if (liveMonitor) liveMonitor.style.display = 'block';

    currentSessionUrls = sessionData;
    applyQrDisplay();

    // Session Meta Labels
    const sessIdElem = document.getElementById('liveSessionIdText');
    if (sessIdElem) sessIdElem.textContent = `#${sessionData.session.id}`;

    const tokenElem = document.getElementById('liveTokenSnippet');
    if (tokenElem && sessionData.session.token) {
      tokenElem.textContent = sessionData.session.token.substring(0, 16) + '...';
    }

    const lotBadge = document.getElementById('liveLotLinkedBadge');
    if (lotBadge) {
      if (sessionData.session.lot_number) {
        lotBadge.textContent = `Lot: ${sessionData.session.lot_number} (${sessionData.session.lot_material || 'Material'})`;
        lotBadge.style.display = 'inline-block';
      } else {
        lotBadge.textContent = 'General Specimen Scan (No Lot Linked)';
        lotBadge.style.display = 'inline-block';
      }
    }
  }

  function renderSessionInactive() {
    const inactiveCard = document.getElementById('liveInactiveCard');
    const activeCard = document.getElementById('liveActiveCard');
    const liveMonitor = document.getElementById('liveMonitorWorkspaceCard');
    const resultCard = document.getElementById('laptopFinalResultCard');

    if (inactiveCard) inactiveCard.style.display = 'block';
    if (activeCard) activeCard.style.display = 'none';
    if (liveMonitor) liveMonitor.style.display = 'none';
    if (resultCard) resultCard.style.display = 'none';
  }

  function onSessionEnded(reason) {
    const statusBadge = document.getElementById('liveStatusBadge');
    if (statusBadge) {
      statusBadge.textContent = `Session Inactive (${reason})`;
      statusBadge.className = 'status-pill status-pill-hold';
    }
  }

  function copySessionLink() {
    const linkInput = document.getElementById('sessionCaptureUrl');
    if (!linkInput) return;
    linkInput.select();
    linkInput.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(linkInput.value).then(() => {
      const btn = document.getElementById('btnCopyLink');
      if (btn) {
        const origText = btn.textContent;
        btn.textContent = '✓ Copied!';
        setTimeout(() => { btn.textContent = origText; }, 2000);
      }
    }).catch(() => {
      alert('Link: ' + linkInput.value);
    });
  }

  return {
    init,
    startNewSession,
    closeSession,
    copySessionLink,
    selectHistoricalFrame,
    returnToLive,
    confirmVerdict,
    resetLockForNextSample,
    setQrMode
  };
})();
