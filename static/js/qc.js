/**
 * FOOD MAN - QC MODULE CONTROLLER
 * Handles:
 * - QC Queue rendering (pending lots)
 * - Combined review (Lab Tests + COA + YOLO AI defect bounding boxes)
 * - SVG Canvas bounding-box rendering on inspection image
 * - Human-only QC Decision dispatch (APPROVED, HOLD, REJECTED)
 */

const QCApp = (() => {
  let activeLotId = null;
  let currentReviewData = null;
  let selectedFile = null;
  let lastInspectionId = null;
  let currentAiResult = null;
  let currentReleaseDecision = null;
  let activeView = 'queue';
  let modalLotId = null;

  function init(view) {
    activeView = view || 'queue';
    if (activeView === 'ai-inspection') {
      checkModelStatus();
      onTargetTypeChange();
    } else {
      loadQueue();
    }
  }

  // =========================================================================
  // AI VISUAL INSPECTION (YOLOv8) WORKSPACE CONTROLLER
  // =========================================================================

  async function checkModelStatus() {
    try {
      const res = await fetch('/api/qc/ai-model-status');
      if (!res.ok) return;
      const data = await res.json();

      const badge = document.getElementById('modelStatusBadge');
      const msg = document.getElementById('modelStatusMessage');
      const title = document.getElementById('modelStatusTitle');
      const banner = document.getElementById('aiModelStatusBanner');

      if (data.status === 'READY') {
        if (badge) {
          badge.textContent = `Model Ready (${data.model_file || 'best.pt'})`;
          badge.style.background = '#D1FAE5';
          badge.style.color = '#065F46';
        }
        if (msg) {
          msg.textContent = `Ultralytics YOLOv8 loaded successfully (${data.classes_count || 0} classes). Device: ${data.device || 'CPU'}. Active model: ${data.model_file}.`;
        }
        if (banner) {
          banner.style.background = '#ECFDF5';
          banner.style.borderColor = '#A7F3D0';
          banner.style.borderLeftColor = '#059669';
        }
      } else {
        if (badge) {
          badge.textContent = data.status === 'MODEL_NOT_FOUND' ? 'No Trained Model' : 'Engine Setup Required';
          badge.style.background = '#FEF3C7';
          badge.style.color = '#92400E';
        }
        if (msg) {
          msg.textContent = data.message || 'Place your trained best.pt model in models/ directory to enable live inference.';
        }
      }
    } catch (err) {
      console.warn("Could not check AI engine status:", err);
    }
  }

  let selectedFileSource = 'file';

  function openCamera() {
    const camInput = document.getElementById('aiCameraInput');
    if (camInput) camInput.click();
  }

  function openFilePicker() {
    const fileInput = document.getElementById('aiFileInput');
    if (fileInput) fileInput.click();
  }

  function onImageSelected(event, source) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    selectedFile = file;
    selectedFileSource = source || (event.target && event.target.id === 'aiCameraInput' ? 'camera' : 'file');

    const reader = new FileReader();
    reader.onload = (e) => {
      const previewImg = document.getElementById('aiPreviewImg');
      if (previewImg) previewImg.src = e.target.result;

      const rawResult = document.getElementById('aiRawResultImg');
      if (rawResult) rawResult.src = e.target.result;

      const emptyState = document.getElementById('dropzoneEmptyState');
      if (emptyState) emptyState.style.display = 'none';

      const previewState = document.getElementById('dropzonePreviewState');
      if (previewState) previewState.style.display = 'block';

      const filenameEl = document.getElementById('aiPreviewFilename');
      const sizeKB = (file.size / 1024).toFixed(1);
      const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
      const sizeStr = file.size > 1024 * 1024 ? `${sizeMB} MB` : `${sizeKB} KB`;
      const sourceBadge = selectedFileSource === 'camera' ? '📸 Rear Camera' : '📁 Uploaded File';

      if (filenameEl) {
        filenameEl.innerHTML = `<strong>${file.name || 'Captured Photo'}</strong> (${sizeStr}) <span class="badge-source">${sourceBadge}</span>`;
      }

      // Check if image is large phone camera photo (4000px+)
      const largeNotice = document.getElementById('largePhotoNotice');
      if (largeNotice) {
        const testImg = new Image();
        testImg.onload = () => {
          if (testImg.width >= 4000 || testImg.height >= 4000) {
            largeNotice.style.display = 'block';
            largeNotice.innerHTML = `⚡ <strong>High-Res Phone Photo (${testImg.width}×${testImg.height})</strong>: Pre-scaled to 1920px for fast YOLOv8 inference. Full original preserved on disk.`;
          } else {
            largeNotice.style.display = 'none';
          }
        };
        testImg.src = e.target.result;
      }
    };
    reader.readAsDataURL(file);
  }

  function clearImageSelection() {
    selectedFile = null;
    const fileInput = document.getElementById('aiFileInput');
    if (fileInput) fileInput.value = '';
    const camInput = document.getElementById('aiCameraInput');
    if (camInput) camInput.value = '';

    const emptyState = document.getElementById('dropzoneEmptyState');
    if (emptyState) emptyState.style.display = 'block';

    const previewState = document.getElementById('dropzonePreviewState');
    if (previewState) previewState.style.display = 'none';

    const largeNotice = document.getElementById('largePhotoNotice');
    if (largeNotice) largeNotice.style.display = 'none';
  }

  function onTargetTypeChange() {
    const select = document.getElementById('aiTargetTypeSelect');
    if (!select) return;
    const val = select.value;

    const lotGroup = document.getElementById('lotSelectGroup');
    const productGroup = document.getElementById('productSelectGroup');
    const batchGroup = document.getElementById('batchSelectGroup');

    if (lotGroup) lotGroup.style.display = val === 'lot' ? 'block' : 'none';
    if (productGroup) productGroup.style.display = val === 'product' ? 'block' : 'none';
    if (batchGroup) batchGroup.style.display = val === 'batch' ? 'block' : 'none';
  }

  async function runAiInspection() {
    if (!selectedFile) {
      alert("Please select or drop an inspection image first.");
      return;
    }

    const targetTypeSelect = document.getElementById('aiTargetTypeSelect');
    const targetType = targetTypeSelect ? targetTypeSelect.value : 'lot';

    let targetId = null;
    if (targetType === 'lot') {
      const el = document.getElementById('aiTargetLotSelect');
      targetId = el ? el.value : null;
    } else if (targetType === 'product') {
      const el = document.getElementById('aiTargetProductSelect');
      targetId = el ? el.value : null;
    } else if (targetType === 'batch') {
      const el = document.getElementById('aiTargetBatchSelect');
      targetId = el ? el.value : null;
    }

    const confSlider = document.getElementById('aiConfThreshold');
    const confThreshold = confSlider ? confSlider.value : 0.12;
    const maxDefectsInput = document.getElementById('aiMaxDefectsThreshold');
    const maxDefects = maxDefectsInput ? maxDefectsInput.value : '0';

    const btn = document.getElementById('btnRunAiInspection');
    const originalHtml = btn ? btn.innerHTML : '';
    const mismatchBanner = document.getElementById('aiMaterialMismatchBanner');
    if (mismatchBanner) mismatchBanner.style.display = 'none';

    // Reset previous inspection cards
    const unreliableCard = document.getElementById('aiUnreliableWarningCard');
    if (unreliableCard) unreliableCard.style.display = 'none';
    const passFailCard = document.getElementById('aiPassFailCard');
    if (passFailCard) passFailCard.style.display = 'none';
    const actionsToolbar = document.getElementById('aiActionsToolbar');
    if (actionsToolbar) actionsToolbar.style.display = 'none';
    const confirmToast = document.getElementById('aiVerdictConfirmToast');
    if (confirmToast) confirmToast.style.display = 'none';
    const fbSuccess = document.getElementById('aiFeedbackSuccessMsg');
    if (fbSuccess) fbSuccess.style.display = 'none';

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `
        <svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation: spin 1s linear infinite;"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle><path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="1"></path></svg>
        <span>Running YOLOv8 Defect Analysis...</span>
      `;
    }

    const formData = new FormData();
    formData.append('image', selectedFile);
    formData.append('target_type', targetType);
    if (targetId) formData.append('target_id', targetId);
    formData.append('confidence_threshold', confThreshold);
    formData.append('max_defects_threshold', maxDefects);

    try {
      const res = await fetch('/api/qc/ai-inspect', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'AI visual inspection failed');

      renderAiResults(data);
    } catch (err) {
      alert("AI Inspection Error: " + err.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
      }
    }
  }

  function renderAiResults(data) {
    const ai = data.ai_result || {};
    currentAiResult = ai;

    // Timestamp & Latency
    const tsEl = document.getElementById('aiResultTimestamp');
    if (tsEl) {
      tsEl.textContent = `Inspected: ${new Date(ai.timestamp || Date.now()).toLocaleTimeString()}`;
    }

    const speedEl = document.getElementById('aiInferenceSpeed');
    if (speedEl) {
      speedEl.textContent = `${ai.inference_time_ms || 0} ms`;
    }

    // Set lastInspectionId for feedback loop & PDF download
    lastInspectionId = ai.inspection_id || (data.data && data.data.inspection_id) || data.inspection_id;
    const fbCard = document.getElementById('aiFeedbackLoopCard');
    if (fbCard && lastInspectionId) {
      fbCard.style.display = 'block';
    }

    // Actions Toolbar (Download PDF report button)
    const actionsToolbar = document.getElementById('aiActionsToolbar');
    if (actionsToolbar && lastInspectionId) {
      actionsToolbar.style.display = 'flex';
    }

    // Final Decision Box in Drawer
    const fdBox = document.getElementById('drawerFinalDecisionBox');
    if (fdBox) {
      const fd = ai.final_decision;
      if (fd) {
        fdBox.style.display = 'block';
        const badge = document.getElementById('drawerDecisionStateBadge');
        const rEl = document.getElementById('drawerDecisionReason');
        const nextEl = document.getElementById('drawerDecisionNextStep');
        const detEl = document.getElementById('drawerDecisionDetails');
        if (badge) {
          badge.textContent = fd.state;
          badge.className = `status-pill status-${fd.state.toLowerCase()}`;
        }
        if (rEl) rEl.textContent = fd.reason || '';
        if (nextEl) nextEl.textContent = fd.next_step ? `👉 Next step: ${fd.next_step}` : '';
        if (detEl) detEl.innerHTML = (fd.details || []).map(d => `<div>• ${d}</div>`).join('');
      } else {
        fdBox.style.display = 'none';
      }
    }

    // Best 3 Annotated Frames Gallery in Drawer (Requirement 4: "n flagged of m kernels")
    const drawerGrid = document.getElementById('drawerBestFramesGrid');
    const drawerSec = document.getElementById('drawerBestFramesSection');
    if (drawerGrid && drawerSec) {
      const frames = ai.best_frames || [];
      if (frames.length > 0) {
        drawerSec.style.display = 'block';
        drawerGrid.innerHTML = frames.map((f, idx) => {
          const flagged = f.defect_count || 0;
          const total = (f.good_count || 0) + (f.defect_count || 0);
          return `
            <div style="border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;background:#F8FAFC;cursor:pointer;" onclick="window.open('${f.annotated_path || f.image_path}', '_blank')" title="Frame #${f.id} - Tap to view full size">
              <img src="${f.annotated_path || f.image_path}" alt="Specimen Frame ${idx + 1}" style="width:100%;height:120px;object-fit:cover;display:block;">
              <div style="padding:6px 8px;font-size:11px;font-weight:700;color:#475569;display:flex;justify-content:space-between;background:#FFF;border-top:1px solid #E2E8F0;">
                <span>Sample #${idx + 1}</span>
                <span style="color:${flagged > 0 ? '#DC2626' : '#059669'};">${flagged} flagged of ${total} kernels</span>
              </div>
            </div>
          `;
        }).join('');
      } else {
        drawerSec.style.display = 'none';
        drawerGrid.innerHTML = '';
      }
    }

    // Images
    if (ai.raw_image_url) {
      const rawImg = document.getElementById('aiRawResultImg');
      if (rawImg) rawImg.src = ai.raw_image_url;
    }
    if (ai.annotated_image_url) {
      const annImg = document.getElementById('aiAnnotatedResultImg');
      if (annImg) annImg.src = ai.annotated_image_url;
    }

    // Wrong-Material Mismatch Amber Warning Banner
    const mismatchBanner = document.getElementById('aiMaterialMismatchBanner');
    const mismatchText = document.getElementById('aiMaterialMismatchText');
    if (mismatchBanner) {
      if (ai.material_mismatch && ai.mismatch_warning) {
        if (mismatchText) mismatchText.textContent = ai.mismatch_warning;
        mismatchBanner.style.display = 'block';
      } else {
        mismatchBanner.style.display = 'none';
      }
    }

    // Requirement: When a material mismatch is flagged, or the average confidence of all detections is below 50%,
    // set the status to NEEDS_REVIEW. Hide the automatic pass/fail suggestion and show "Result unreliable: verify the sample manually or retake the photo."
    const isUnreliable = ai.is_unreliable || ai.model_status === 'NEEDS_REVIEW' || !!ai.unreliable_warning;
    const unreliableCard = document.getElementById('aiUnreliableWarningCard');
    const passFailCard = document.getElementById('aiPassFailCard');

    if (isUnreliable) {
      if (passFailCard) passFailCard.style.display = 'none';
      if (unreliableCard) {
        unreliableCard.style.display = 'block';
        const detailEl = document.getElementById('aiUnreliableDetail');
        if (detailEl) {
          if (ai.material_mismatch && ai.is_low_confidence) {
            detailEl.textContent = `Material mismatch detected and average detection confidence (${ai.avg_confidence_percent || '<50%'}) is below 50%.`;
          } else if (ai.material_mismatch) {
            detailEl.textContent = ai.mismatch_warning || 'Material mismatch detected between lot label and camera specimen.';
          } else if (ai.is_low_confidence) {
            detailEl.textContent = `Average detection confidence is ${ai.avg_confidence_percent || '<50%'}, which is below the 50% reliability threshold.`;
          } else {
            detailEl.textContent = 'Status set to NEEDS_REVIEW. Verify the sample manually or retake the photo.';
          }
        }
      }
    } else {
      if (unreliableCard) unreliableCard.style.display = 'none';
      if (passFailCard) {
        passFailCard.style.display = 'block';
        updatePassFailUI(ai);
      }
    }

    const tbody = document.getElementById('aiDefectsTableBody');
    const badgeCount = document.getElementById('aiDefectsCountBadge');
    const pillarAiStatus = document.getElementById('pillarAiStatus');
    const pillarAiBadge = document.getElementById('pillarAiBadge');

    // Case: No trained model weights available
    if (ai.model_status === 'MODEL_NOT_FOUND' || ai.model_status === 'ENGINE_UNAVAILABLE') {
      if (badgeCount) {
        badgeCount.textContent = 'Configuration Mode';
        badgeCount.className = 'status-pill-badge pill-pending';
      }
      if (tbody) {
        tbody.innerHTML = `
          <tr>
            <td colspan="4" style="padding:16px;background:#FFFBEB;color:#92400E;font-size:12.5px;">
              <div style="font-weight:700;display:flex;align-items:center;gap:6px;">
                <span>⚠️ YOLOv8 Model Configuration Required</span>
              </div>
              <div style="margin-top:6px;font-size:12px;color:#78350F;line-height:1.5;">
                ${ai.status_message || 'No trained YOLO model weights found in models/best.pt.'}
              </div>
              <div style="margin-top:8px;padding:8px 12px;background:#FEF3C7;border-radius:6px;font-family:monospace;font-size:11px;color:#92400E;">
                Training Flow: Food Images → Label defects → Train YOLOv8 → models/best.pt
              </div>
              <div style="margin-top:8px;font-size:11px;color:#B45309;">
                🛡️ <em>In strict compliance with food safety QA protocols, no synthetic/fake defects are generated.</em>
              </div>
            </td>
          </tr>
        `;
      }
      if (pillarAiStatus) {
        pillarAiStatus.textContent = 'Model in setup mode. Visual specimen requires 100% manual inspection by QC Specialist.';
      }
      if (pillarAiBadge) {
        pillarAiBadge.textContent = 'Manual Review Req';
        pillarAiBadge.className = 'status-pill status-pill-amber';
      }
      return;
    }

    // Normal detection results
    const defects = ai.defects || ai.detected_defects || [];
    if (badgeCount) {
      badgeCount.textContent = `${defects.length} Defect${defects.length === 1 ? '' : 's'}`;
      badgeCount.className = defects.length > 0 ? 'status-pill-badge pill-rejected' : 'status-pill-badge pill-approved';
    }

    if (defects.length === 0) {
      const healthyCount = ai.healthy_specimens_count || (ai.detected_healthy ? ai.detected_healthy.length : 0) || 0;
      const cleanMsg = healthyCount > 0
        ? `✓ YOLOv8 Analysis Complete: Specimen visually clean (${healthyCount} healthy raw material specimen(s) verified, 0 defects detected).`
        : `✓ YOLOv8 Analysis Complete: No visible defects detected above threshold (${Math.round((ai.confidence_threshold || 0.25) * 100)}%). Specimen visually clean.`;

      if (tbody) {
        tbody.innerHTML = `
          <tr>
            <td colspan="4" style="text-align:center;padding:16px;color:#059669;background:#ECFDF5;font-weight:600;">
              ${cleanMsg}
            </td>
          </tr>
        `;
      }
      if (pillarAiStatus) {
        pillarAiStatus.textContent = healthyCount > 0
          ? `YOLOv8 visual scan clean: ${healthyCount} healthy item(s) verified, 0 defects detected.`
          : 'YOLOv8 visual scan clean. Zero defects detected above confidence threshold.';
      }
      if (pillarAiBadge) {
        pillarAiBadge.textContent = '✓ AI Visual Clean';
        pillarAiBadge.className = 'status-pill status-pill-approved';
      }
    } else {
      if (tbody) {
        tbody.innerHTML = defects.map(d => {
          const bbox = d.bbox || { x: d.bbox_x, y: d.bbox_y, w: d.bbox_w, h: d.bbox_h };
          const bboxStr = `[${bbox.x}%, ${bbox.y}%, ${bbox.w}%, ${bbox.h}%]`;
          const confStr = d.confidence_percent || `${Math.round((d.confidence || 0) * 100)}%`;
          return `
            <tr style="border-bottom:1px solid var(--border-light);">
              <td style="padding:8px 12px;font-weight:700;color:#DC2626;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#EF4444;margin-right:6px;"></span>
                ${d.defect_class}
              </td>
              <td style="padding:8px 12px;">
                <span class="status-pill-badge pill-rejected" style="font-size:10px;">ANOMALY DETECTED</span>
              </td>
              <td style="padding:8px 12px;font-family:'JetBrains Mono',monospace;font-weight:700;color:var(--accent-navy);">
                ${confStr}
              </td>
              <td style="padding:8px 12px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-muted);">
                ${bboxStr}
              </td>
            </tr>
          `;
        }).join('');
      }
      if (pillarAiStatus) {
        pillarAiStatus.textContent = `YOLOv8 flagged ${defects.length} defect(s). Human verification mandatory before approval.`;
      }
      if (pillarAiBadge) {
        pillarAiBadge.textContent = '⚠ Defect Detected';
        pillarAiBadge.className = 'status-pill status-pill-rejected';
      }
    }

    if (isUnreliable) {
      if (pillarAiStatus) {
        pillarAiStatus.innerHTML = `<span style="color:#B45309;font-weight:700;">⚠️ ${ai.unreliable_warning || 'Result unreliable: verify the sample manually or retake the photo.'}</span>`;
      }
      if (pillarAiBadge) {
        pillarAiBadge.textContent = '⚠ Needs Review';
        pillarAiBadge.className = 'status-pill status-pill-amber';
      }
    } else if (ai.material_mismatch && ai.mismatch_warning) {
      if (pillarAiStatus) {
        pillarAiStatus.innerHTML = `<span style="color:#B45309;font-weight:700;">⚠️ ${ai.mismatch_warning}</span><br>${pillarAiStatus.textContent || ''}`;
      }
      if (pillarAiBadge && (!defects || defects.length === 0)) {
        pillarAiBadge.textContent = '⚠ Material Mismatch';
        pillarAiBadge.className = 'status-pill status-pill-amber';
      }
    }
  }

  // =========================================================================
  // PASS/FAIL CALCULATION WITH EDITABLE THRESHOLDS
  // =========================================================================

  function updatePassFailUI(ai) {
    const badge = document.getElementById('aiPassFailBadge');
    const summary = document.getElementById('aiPassFailSummary');
    const maxDefectsInput = document.getElementById('aiMaxDefectsThreshold');
    const tolerance = parseInt(maxDefectsInput ? maxDefectsInput.value : 0, 10) || 0;
    const defectList = (ai && (ai.defects || ai.detected_defects)) ? (ai.defects || ai.detected_defects) : [];
    const defectCount = defectList.length;

    const isPass = defectCount <= tolerance;
    if (badge) {
      if (isPass) {
        badge.textContent = 'SUGGESTED: PASS';
        badge.className = 'status-pill status-pill-approved';
        badge.style.background = '#ECFDF5';
        badge.style.color = '#065F46';
        badge.style.border = '1.5px solid #A7F3D0';
      } else {
        badge.textContent = 'SUGGESTED: FAIL';
        badge.className = 'status-pill status-pill-rejected';
        badge.style.background = '#FEF2F2';
        badge.style.color = '#991B1B';
        badge.style.border = '1.5px solid #FECACA';
      }
    }

    if (summary) {
      summary.textContent = `${defectCount} defect(s) detected (tolerance: max ${tolerance} defect(s)).`;
    }
  }

  function recalculatePassFail() {
    if (!currentAiResult) return;
    const isUnreliable = currentAiResult.is_unreliable || currentAiResult.model_status === 'NEEDS_REVIEW' || !!currentAiResult.unreliable_warning;
    if (isUnreliable) return;
    updatePassFailUI(currentAiResult);
  }

  // =========================================================================
  // LOT STATUS UPDATE ON CONFIRM (ACCEPT / REJECT)
  // =========================================================================

  async function confirmAiVerdict(action) {
    if (!lastInspectionId) {
      alert("No active inspection to confirm.");
      return;
    }

    const isAccept = (action === 'ACCEPT' || action === 'PASS' || action === 'APPROVED');
    let notes = '';

    const fd = currentAiResult ? currentAiResult.final_decision : null;
    const state = (fd && fd.state) ? fd.state : (currentAiResult && currentAiResult.model_status === 'NEEDS_REVIEW' ? 'REVIEW' : 'REVIEW');
    const isOverride = (isAccept && state !== 'PASS') || (!isAccept && state !== 'REJECT');

    if (isOverride) {
      const promptReason = prompt(`Analysis state is ${state}. A written override reason is mandatory to ${isAccept ? 'approve' : 'reject'} this lot:`);
      if (!promptReason || !promptReason.trim()) {
        alert("Action cancelled. A written override reason is mandatory when approving a lot that is not PASS or rejecting a lot that is not REJECT.");
        return;
      }
      notes = promptReason.trim();
    }

    const toast = document.getElementById('aiVerdictConfirmToast');
    try {
      const res = await fetch(`/api/qc/ai-inspection/${lastInspectionId}/confirm-verdict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: action,
          notes: notes,
          reason: notes
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to confirm verdict');

      if (toast) {
        toast.style.display = 'block';
        const isApproved = data.final_status === 'APPROVED';
        toast.style.background = isApproved ? '#ECFDF5' : '#FEF2F2';
        toast.style.border = `1.5px solid ${isApproved ? '#A7F3D0' : '#FECACA'}`;
        toast.style.color = isApproved ? '#065F46' : '#991B1B';
        toast.innerHTML = `✓ ${data.message}`;
      }
      if (window.showToast) {
        window.showToast("Verdict Confirmed", data.message, data.final_status === 'APPROVED' ? "success" : "danger");
      }
      if (typeof loadQueue === 'function') {
        loadQueue();
      }
    } catch (err) {
      alert("Error confirming verdict: " + err.message);
    }
  }

  // =========================================================================
  // INSPECTION REPORT PDF DOWNLOAD
  // =========================================================================

  function downloadPdfReport() {
    if (!lastInspectionId) {
      alert("No active inspection to generate PDF for.");
      return;
    }
    window.open(`/api/qc/ai-inspection/${lastInspectionId}/pdf`, '_blank');
  }

  // =========================================================================
  // INSPECTOR VERIFICATION & QUALITY AUDIT FEEDBACK (NO RETRAINING)
  // =========================================================================

  async function submitInspectorFeedback(feedbackType) {
    if (!lastInspectionId) {
      alert("No active inspection to submit feedback for.");
      return;
    }

    const notesInput = document.getElementById('aiFeedbackNotesInput');
    const notes = notesInput ? notesInput.value.trim() : '';
    const successEl = document.getElementById('aiFeedbackSuccessMsg');

    try {
      const res = await fetch('/api/qc/ai-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ai_inspection_id: lastInspectionId,
          feedback_type: feedbackType,
          notes: notes
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to submit feedback');

      if (successEl) {
        successEl.style.display = 'block';
        const label = feedbackType === 'RESULT_CORRECT' ? 'Result is correct' : 'Result is wrong';
        successEl.innerHTML = `✓ Verification logged: "<strong>${label}</strong>"${notes ? ` with notes: "${notes}"` : ''}. (Saved in inspection records; not fed into retraining automatically).`;
      }
      if (window.showToast) {
        window.showToast("Feedback Logged", "Verification saved to audit records (no automated retraining).", "success");
      }
    } catch (err) {
      alert("Error saving feedback: " + err.message);
    }
  }

  // Legacy fallback
  async function submitFeedback(feedbackType) {
    return submitInspectorFeedback(feedbackType);
  }


  // =========================================================================
  // FOUR-PILLAR FINAL QC DECISION GATE (HUMAN-ONLY SIGN-OFF)
  // Combines: Lab Tests + COA + YOLOv8 AI + Quality Specs
  // =========================================================================


  async function submitFourPillarDecision(finalStatus) {
    const targetTypeSelect = document.getElementById('aiTargetTypeSelect');
    const targetType = targetTypeSelect ? targetTypeSelect.value : 'lot';

    let targetId = null;
    if (targetType === 'lot') {
      const el = document.getElementById('aiTargetLotSelect');
      targetId = el ? el.value : null;
    } else if (targetType === 'product') {
      const el = document.getElementById('aiTargetProductSelect');
      targetId = el ? el.value : null;
    } else if (targetType === 'batch') {
      const el = document.getElementById('aiTargetBatchSelect');
      targetId = el ? el.value : null;
    }

    if (!targetId) {
      alert("Please select a target lot, product, or batch.");
      return;
    }

    const notesInput = document.getElementById('decisionNotesInput');
    const notes = notesInput ? notesInput.value.trim() : '';

    const statusLabels = {
      'APPROVED': '✅ Approved / Safe to Proceed',
      'HOLD': '🟡 Hold / Requires Further Review',
      'REJECTED': '❌ Rejected / Do Not Proceed'
    };

    const confirmMsg = `Four-Pillar Quality Gate Sign-Off:\n\nFinal Decision: ${statusLabels[finalStatus] || finalStatus}\nTarget: ${targetType.toUpperCase()} (ID: ${targetId})\n\nConfirm that you have reviewed:\n1. Lab physicochemical & microbial tests\n2. Certificate of Analysis (COA)\n3. YOLOv8 visual defect inspection\n4. Required manufacturing specifications\n\nProceed with official sign-off?`;
    if (!confirm(confirmMsg)) return;

    try {
      const res = await fetch('/api/qc/decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_type: targetType,
          target_id: parseInt(targetId, 10),
          final_status: finalStatus,
          reason: `Four-Pillar QC Sign-Off (Lab + COA + YOLOv8 + Specs): ${finalStatus}`,
          action_notes: notes || `Verified by QC Specialist on ${new Date().toLocaleString()}`
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to submit QC decision');

      alert(`DECISION RECORDED SUCCESSFULLY!\n\nTarget: ${data.decision.target_type.toUpperCase()} #${data.decision.target_id}\nFinal Status: ${data.decision.final_status}\n\n${data.message}`);
      if (notesInput) notesInput.value = '';

    } catch (err) {
      alert("Error submitting QC decision: " + err.message);
    }
  }

  // =========================================================================
  // STANDARD QC QUEUE & LOT DOSSIER DRAWER
  // =========================================================================

  // Helper to render standard Queue cards with 4-step indicator and next action (Stage C)
  function renderQueueCard(card) {
    const steps = card.steps || [];
    const s1 = steps[0] || { status: 'pending' };
    const s2 = steps[1] || { status: 'pending' };
    const s3 = steps[2] || { status: 'pending' };
    const s4 = steps[3] || { status: 'pending' };

    const outcome = card.decision_outcome || 'HOLD';
    const label = card.decision_label || (outcome === 'RELEASE' ? 'GOOD' : (outcome === 'REJECT' ? 'BAD' : 'NEEDS REVIEW'));
    const outcomePillClass = outcome === 'RELEASE' ? 'status-pill-approved' : (outcome === 'REJECT' ? 'status-pill-rejected' : 'status-pill-amber');

    const miniGridHtml = (card.miniGrid || []).map(cell => `
      <div class="grid-cell-item">
        <span class="cell-label-text">${cell.label}</span>
        <span class="cell-value-text" title="${cell.value}">${cell.value}</span>
      </div>
    `).join('');

    return `
      <div class="record-card-box" data-id="${card.id}" onclick="QCApp.openQcReviewDrawer(${card.db_id})" style="cursor:pointer;display:flex;flex-direction:column;justify-content:space-between;">
        <div>
          <!-- Header Row -->
          <div class="card-top-row">
            <div class="card-title-col">
              <div>
                <span class="card-id-badge">${card.id}</span>
                ${card.category ? `<span class="card-category-sub">${card.category}</span>` : ''}
              </div>
              <h3 class="card-main-title">${card.title}</h3>
            </div>
            <div class="card-stat-widget">
              <span class="card-stat-number">${card.headerStat}</span>
              ${card.statSub ? `<span class="card-stat-caption">${card.statSub}</span>` : ''}
            </div>
          </div>

          <!-- 2x2 Mini Grid -->
          <div class="card-mini-grid-layout">
            ${miniGridHtml}
          </div>

          <!-- 4-Step Progress Indicator (Stage C) -->
          <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:8px 10px;margin:10px 0;display:flex;align-items:center;justify-content:space-between;font-size:10.5px;">
            <span style="display:inline-flex;align-items:center;gap:4px;font-weight:${s1.status === 'done' ? '800;color:#065F46' : '600;color:#64748B'};">
              ${s1.status === 'done' ? '✓' : '○'} AI Scan
            </span>
            <span style="color:#CBD5E1;">→</span>
            <span style="display:inline-flex;align-items:center;gap:4px;font-weight:${s2.status === 'done' ? '800;color:#065F46' : '600;color:#64748B'};">
              ${s2.status === 'done' ? '✓' : '○'} Lab &amp; COA
            </span>
            <span style="color:#CBD5E1;">→</span>
            <span style="display:inline-flex;align-items:center;gap:4px;font-weight:${s3.status === 'done' ? '800;color:#065F46' : '600;color:#64748B'};">
              ${s3.status === 'done' ? '✓' : '○'} Combined
            </span>
            <span style="color:#CBD5E1;">→</span>
            <span style="display:inline-flex;align-items:center;gap:4px;font-weight:${s4.status === 'done' ? '800;color:#065F46' : '600;color:#64748B'};">
              ${s4.status === 'done' ? '✓' : '○'} Sign-Off
            </span>
          </div>
        </div>

        <!-- Card Footer: Next Action + Consistent Status Chip -->
        <div class="card-footer-slot" style="display:flex;align-items:center;justify-content:space-between;margin-top:8px;">
          <div style="font-size:11.5px;color:#475569;">
            Next action: <strong style="color:var(--accent-navy);">${card.next_action}</strong>
          </div>
          <span class="status-pill ${outcomePillClass}" style="font-size:11px;font-weight:800;padding:3px 10px;">
            ${label}
          </span>
        </div>
      </div>
    `;
  }

  // Helper to render distinct Test Results & COA cards (Stage C1)
  function renderTestResultsCard(card) {
    const m = card.lab_measures || {};
    const moistureVal = (m.moisture !== null && m.moisture !== undefined) ? `${m.moisture}%` : `<span style="color:#94A3B8;">—</span>`;
    const aflatoxinVal = (m.aflatoxin_b1 !== null && m.aflatoxin_b1 !== undefined) ? `${m.aflatoxin_b1} ppb` : `<span style="color:#94A3B8;">—</span>`;
    const ffaVal = (m.ffa !== null && m.ffa !== undefined) ? `${m.ffa}%` : `<span style="color:#94A3B8;">—</span>`;
    const purityVal = (m.purity !== null && m.purity !== undefined) ? `${m.purity}%` : `<span style="color:#94A3B8;">—</span>`;

    let coaBadge = '';
    if (card.coa_status === 'present') {
      coaBadge = `<span class="status-pill status-pill-approved" style="font-size:10.5px;font-weight:800;">✓ COA Present${card.coa_doc_number ? ` (${card.coa_doc_number})` : ''}</span>`;
    } else if (card.coa_status === 'expired') {
      coaBadge = `<span class="status-pill status-pill-rejected" style="font-size:10.5px;font-weight:800;">✕ COA Expired</span>`;
    } else {
      coaBadge = `<span class="status-pill status-pill-amber" style="font-size:10.5px;font-weight:800;">⚠️ COA Missing</span>`;
    }

    const outcome = card.decision_outcome || 'HOLD';
    const label = card.decision_label || (outcome === 'RELEASE' ? 'GOOD' : (outcome === 'REJECT' ? 'BAD' : 'NEEDS REVIEW'));
    const outcomePillClass = outcome === 'RELEASE' ? 'status-pill-approved' : (outcome === 'REJECT' ? 'status-pill-rejected' : 'status-pill-amber');

    return `
      <div class="record-card-box" data-id="${card.id}" onclick="QCApp.openQcReviewDrawer(${card.db_id})" style="cursor:pointer;display:flex;flex-direction:column;justify-content:space-between;">
        <div>
          <!-- Header Row -->
          <div class="card-top-row">
            <div class="card-title-col">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;flex-wrap:wrap;">
                <span class="card-id-badge">${card.id}</span>
                ${card.category ? `<span class="card-category-sub">${card.category}</span>` : ''}
                ${coaBadge}
              </div>
              <h3 class="card-main-title">${card.title}</h3>
            </div>
            <div class="card-stat-widget">
              <span class="status-pill ${outcomePillClass}" style="font-size:11.5px;font-weight:800;padding:4px 10px;">${label}</span>
              <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">${card.headerStat}</div>
            </div>
          </div>

          <!-- 4 Lab Parameters Grid -->
          <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:12px;margin:12px 0 14px;">
            <div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:8px;">
              Physicochemical Lab Values
            </div>
            <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:8px;text-align:center;">
              <div style="background:#FFF;padding:8px 6px;border-radius:6px;border:1px solid #E2E8F0;">
                <div style="font-size:10px;color:#64748B;font-weight:600;">Moisture</div>
                <div style="font-size:12.5px;font-weight:800;color:#0F172A;font-family:'JetBrains Mono',monospace;margin-top:2px;">${moistureVal}</div>
              </div>
              <div style="background:#FFF;padding:8px 6px;border-radius:6px;border:1px solid #E2E8F0;">
                <div style="font-size:10px;color:#64748B;font-weight:600;">Aflatoxin B1</div>
                <div style="font-size:12.5px;font-weight:800;color:#0F172A;font-family:'JetBrains Mono',monospace;margin-top:2px;">${aflatoxinVal}</div>
              </div>
              <div style="background:#FFF;padding:8px 6px;border-radius:6px;border:1px solid #E2E8F0;">
                <div style="font-size:10px;color:#64748B;font-weight:600;">FFA</div>
                <div style="font-size:12.5px;font-weight:800;color:#0F172A;font-family:'JetBrains Mono',monospace;margin-top:2px;">${ffaVal}</div>
              </div>
              <div style="background:#FFF;padding:8px 6px;border-radius:6px;border:1px solid #E2E8F0;">
                <div style="font-size:10px;color:#64748B;font-weight:600;">Purity</div>
                <div style="font-size:12.5px;font-weight:800;color:#0F172A;font-family:'JetBrains Mono',monospace;margin-top:2px;">${purityVal}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Card Footer: Next Action + Record Lab Measures Button (C1) -->
        <div class="card-footer-slot" style="display:flex;align-items:center;justify-content:space-between;margin-top:4px;flex-wrap:wrap;gap:8px;">
          <div style="font-size:11.5px;color:#475569;">
            Next action: <strong style="color:var(--accent-navy);">${card.next_action}</strong>
          </div>
          <button type="button" class="btn-primary-action" onclick="event.stopPropagation(); QCApp.openQcMeasuresModal(${card.db_id}, '${card.id}')" style="font-size:11.5px;padding:6px 12px;background:#162B4E;color:#FFF;border-radius:6px;font-weight:700;display:inline-flex;align-items:center;gap:6px;">
            <span>📝 Record / Edit Lab Measures</span>
          </button>
        </div>
      </div>
    `;
  }

  async function loadQueue() {
    const container = document.getElementById('qcCardsContainer');
    if (!container) return;
    container.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
        Loading QC data...
      </div>
    `;

    try {
      const res = await fetch('/api/qc/queue');
      if (!res.ok) throw new Error("Error loading QC queue");
      const json = await res.json();
      const cards = json.cards || [];

      const countBadge = document.getElementById('qcQueueCountBadge');
      if (countBadge) {
        if (activeView === 'tests' || activeView === 'coa') {
          countBadge.textContent = `${cards.length} lots with lab records`;
        } else {
          countBadge.textContent = `${cards.length} lots pending inspection`;
        }
      }

      const sidebarBadge = document.getElementById('sidebarQcQueueBadge');
      if (sidebarBadge) sidebarBadge.textContent = cards.length;

      if (cards.length === 0) {
        container.innerHTML = `
          <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--border-subtle);">
            <div style="font-size: 15px; font-weight: 700; color: var(--text-main);">No lots currently awaiting QC inspection</div>
            <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">All received materials have been inspected and processed.</div>
          </div>
        `;
        return;
      }

      if (activeView === 'tests' || activeView === 'coa') {
        container.innerHTML = cards.map(renderTestResultsCard).join('');
      } else {
        container.innerHTML = cards.map(renderQueueCard).join('');
      }

    } catch (err) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #DC2626;">
          Unable to load QC data: ${err.message}
        </div>
      `;
    }
  }

  async function openQcReviewDrawer(lotId) {
    activeLotId = lotId;
    try {
      const res = await fetch(`/api/qc/lot/${lotId}/review`);
      if (!res.ok) throw new Error("Unable to load lot inspection dossier");
      currentReviewData = await res.json();

      populateReviewDrawer(currentReviewData);
      const backdrop = document.getElementById('qcDrawerBackdrop');
      const drawer = document.getElementById('qcDetailDrawer');
      if (backdrop) backdrop.classList.add('show');
      if (drawer) drawer.classList.add('open');

    } catch (err) {
      alert(err.message);
    }
  }

  function populateReviewDrawer(data) {
    const lot = data.lot;
    const lotIdEl = document.getElementById('qcDrawerLotId');
    if (lotIdEl) lotIdEl.textContent = lot.lot_number;

    // Stage C2: 4-Step Stepper & Next Action in Drawer Header
    const steps = data.steps || [];
    const s1 = steps[0] || { status: 'pending' };
    const s2 = steps[1] || { status: 'pending' };
    const s3 = steps[2] || { status: 'pending' };
    const s4 = steps[3] || { status: 'pending' };

    const updateStepBadge = (elId, step, num, defaultTitle) => {
      const el = document.getElementById(elId);
      if (!el) return;
      const isDone = step.status === 'done';
      if (isDone) {
        el.style.background = '#ECFDF5';
        el.style.borderColor = '#A7F3D0';
        el.style.color = '#065F46';
        el.innerHTML = `<span>✓</span> <span>${step.name || defaultTitle}</span>`;
      } else {
        el.style.background = '#FFF';
        el.style.borderColor = '#CBD5E1';
        el.style.color = '#64748B';
        el.innerHTML = `<span class="step-num">${num}</span> <span>${step.name || defaultTitle}</span>`;
      }
    };

    updateStepBadge('drawerStep1', s1, 1, 'AI Scan');
    updateStepBadge('drawerStep2', s2, 2, 'Lab Tests & COA');

    const step3El = document.getElementById('drawerStep3');
    if (step3El) {
      const outcome = s3.outcome || (data.release_decision && data.release_decision.outcome) || 'HOLD';
      const label = s3.label || (outcome === 'RELEASE' ? 'GOOD' : (outcome === 'REJECT' ? 'BAD' : 'NEEDS REVIEW'));
      const pillClass = outcome === 'RELEASE' ? 'status-pill-approved' : (outcome === 'REJECT' ? 'status-pill-rejected' : 'status-pill-amber');
      step3El.innerHTML = `<span class="status-pill ${pillClass}" style="font-size:10px;padding:1px 6px;">${label}</span> <span>Combined Check</span>`;
      step3El.style.background = outcome === 'RELEASE' ? '#ECFDF5' : (outcome === 'REJECT' ? '#FEF2F2' : '#FEF3C7');
      step3El.style.borderColor = outcome === 'RELEASE' ? '#A7F3D0' : (outcome === 'REJECT' ? '#FECACA' : '#FDE68A');
    }

    updateStepBadge('drawerStep4', s4, 4, 'Sign-Off');

    const nextActionEl = document.getElementById('qcDrawerNextActionText');
    if (nextActionEl) {
      nextActionEl.textContent = data.next_action || (
        s1.status !== 'done' ? 'Run AI scan' :
        s2.status !== 'done' ? 'Enter lab & COA results' :
        s4.status !== 'done' ? 'Ready for sign-off' : 'Signed off'
      );
    }

    // 1. Image and Bounding Box Overlay
    const photoImg = document.getElementById('qcInspectionPhoto');
    if (photoImg && data.ai_inspection && data.ai_inspection.image_url) {
      photoImg.src = data.ai_inspection.image_url;
    }

    const inferenceLabel = document.getElementById('qcInferenceTimeLabel');
    if (inferenceLabel && data.ai_inspection) {
      inferenceLabel.textContent = `YOLO Inference: ${data.ai_inspection.inference_time_ms}ms (${data.ai_inspection.model_version})`;
    }

    // Render Bounding Box Overlays via SVG
    renderBoundingBoxes(data.ai_inspection ? data.ai_inspection.defects : []);

    // 2. Defect Confidence Badges
    const defectBadgesContainer = document.getElementById('qcDefectBadgesContainer');
    if (defectBadgesContainer) {
      if (data.ai_inspection && data.ai_inspection.defects && data.ai_inspection.defects.length > 0) {
        defectBadgesContainer.innerHTML = data.ai_inspection.defects.map(d => {
          const confNum = Math.round((d.confidence || 0.92) * 100);
          return `
          <div style="background:#FEE2E2;border:1px solid #FECACA;border-radius:6px;padding:5px 10px;display:inline-flex;align-items:center;gap:6px;">
            <span style="width:6px;height:6px;border-radius:50%;background:#EF4444;"></span>
            <span style="font-size:12px;font-weight:700;color:#991B1B;">${d.defect_class}</span>
            <span class="qc-conf-badge-val" data-target="${confNum}" style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:800;color:#DC2626;background:#FFFFFF;padding:1px 6px;border-radius:4px;">
              0%
            </span>
          </div>
        `;
        }).join('');

        // Trigger confidence badge count-up
        setTimeout(() => {
          document.querySelectorAll('.qc-conf-badge-val').forEach(el => {
            const targetVal = parseInt(el.dataset.target, 10) || 90;
            if (window.FoodManAnimations) {
              window.FoodManAnimations.countUp(el, 0, targetVal, 280, v => v + '%');
            } else {
              el.textContent = targetVal + '%';
            }
          });
        }, 80);
      } else {
        defectBadgesContainer.innerHTML = `
          <div style="background:#D1FAE5;border:1px solid #A7F3D0;border-radius:6px;padding:5px 10px;font-size:12px;font-weight:700;color:#065F46;">
            ✓ YOLO AI: No visual defects detected
          </div>
        `;
      }

      // Check material mismatch in drawer
      if (data.ai_inspection && data.ai_inspection.material_mismatch) {
        const warningHtml = `
          <div style="width:100%;background:#FEF3C7;border:1px solid #F59E0B;border-radius:6px;padding:8px 12px;color:#92400E;font-size:12px;font-weight:700;margin-bottom:8px;display:flex;align-items:center;gap:8px;">
            <span style="font-size:14px;">⚠️</span>
            <span>${data.ai_inspection.mismatch_warning || 'Possible material mismatch'}</span>
          </div>
        `;
        defectBadgesContainer.insertAdjacentHTML('afterbegin', warningHtml);
      }
    }

    // 3. Lab Test Results Table (C3: Empty state when no lab tests)
    const testsBody = document.getElementById('qcLabTestsTableBody');
    if (testsBody) {
      if (data.lab_tests && data.lab_tests.length > 0) {
        testsBody.innerHTML = data.lab_tests.map(t => `
          <tr style="border-bottom:1px solid var(--border-light);">
            <td style="padding:8px 12px;font-weight:700;color:var(--text-main);">${t.parameter_name}</td>
            <td style="padding:8px 12px;color:var(--text-muted);">${t.standard_spec}</td>
            <td style="padding:8px 12px;font-family:'JetBrains Mono',monospace;font-weight:700;color:var(--accent-navy);">${t.measured_value}</td>
            <td style="padding:8px 12px;text-align:center;">
              ${t.is_pass ? '<span class="status-pill-badge pill-approved" style="font-size:10.5px;">PASS</span>' : '<span class="status-pill-badge pill-rejected" style="font-size:10.5px;">FAIL</span>'}
            </td>
          </tr>
        `).join('');
      } else {
        testsBody.innerHTML = `
          <tr>
            <td colspan="4" style="padding:18px;text-align:center;background:#FAFBFC;">
              <div style="font-size:12px;font-weight:700;color:#64748B;margin-bottom:4px;">No QC results uploaded yet</div>
              <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">Enter certified moisture, aflatoxin B1, FFA, and purity specs.</div>
              <button type="button" class="btn-secondary" onclick="QCApp.openQcMeasuresModal(${lot.id}, '${lot.lot_number}')" style="font-size:11.5px;padding:5px 12px;background:#FFF;border-color:#CBD5E1;color:var(--accent-navy);font-weight:700;display:inline-flex;align-items:center;gap:4px;">
                <span>📝 Enter Lab Measures</span>
              </button>
            </td>
          </tr>
        `;
      }
    }

    // 4. COA Document
    if (data.coa) {
      const docEl = document.getElementById('qcCoaDocNumber');
      if (docEl) docEl.textContent = data.coa.doc_number;
      const accEl = document.getElementById('qcCoaAccreditation');
      if (accEl) accEl.textContent = `Lab Accreditation: ${data.coa.lab_accreditation}`;
    }

    // 5. Combined Release Decision (COA + AI)
    currentReleaseDecision = data.release_decision || null;
    const rel = currentReleaseDecision;
    if (rel) {
      // Paper Check (COA & Lab Measures) - C3 Empty state
      const coaChip = document.getElementById('qcReleaseCoaChip');
      const coaExplain = document.getElementById('qcReleaseCoaExplain');
      const isCoaMissing = rel.coa_state === 'MISSING' || (!data.lab_tests || data.lab_tests.length === 0);

      if (coaChip) {
        if (isCoaMissing) {
          coaChip.textContent = 'MISSING';
          coaChip.className = 'status-pill status-pill-amber';
        } else {
          coaChip.textContent = rel.coa_state || 'PASS';
          coaChip.className = 'status-pill ' + (
            rel.coa_state === 'PASS' ? 'status-pill-approved' :
            rel.coa_state === 'FAIL' ? 'status-pill-rejected' : 'status-pill-amber'
          );
        }
      }

      if (coaExplain) {
        if (isCoaMissing) {
          coaExplain.innerHTML = `
            <div style="font-size:12px;font-weight:700;color:#92400E;margin-bottom:3px;">No QC results uploaded yet</div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">COA certificate and physicochemical lab tests (moisture, aflatoxin B1, FFA, purity) have not been entered.</div>
            <button type="button" class="btn-secondary" onclick="QCApp.openQcMeasuresModal(${lot.id}, '${lot.lot_number}')" style="font-size:11px;padding:4px 10px;background:#FFF;border-color:#CBD5E1;color:var(--accent-navy);font-weight:700;display:inline-flex;align-items:center;gap:4px;">
              <span>📝 Enter Lab &amp; COA Results</span>
            </button>
          `;
        } else {
          let coaHtml = `<strong>${rel.coa_reason || 'COA document verified.'}</strong>`;
          if (rel.coa_details && rel.coa_details.length > 0) {
            coaHtml += `<div style="margin-top:4px;font-size:11px;color:var(--text-muted);">${rel.coa_details.map(d => `• ${d}`).join('<br>')}</div>`;
          }
          coaHtml += `
            <div style="margin-top:6px;">
              <button type="button" class="btn-secondary" onclick="QCApp.openQcMeasuresModal(${lot.id}, '${lot.lot_number}')" style="font-size:11px;padding:3px 8px;background:#FFF;border-color:#CBD5E1;font-weight:700;display:inline-flex;align-items:center;gap:4px;">
                <span>📝 Edit Lab Measures</span>
              </button>
            </div>
          `;
          coaExplain.innerHTML = coaHtml;
        }
      }

      // Camera Check (AI) - C3 Empty state
      const aiChip = document.getElementById('qcReleaseAiChip');
      const aiExplain = document.getElementById('qcReleaseAiExplain');
      const isAiNotRun = rel.ai_state === 'NOT_RUN' || (!data.ai_inspection || !data.ai_inspection.defects);

      if (aiChip) {
        if (isAiNotRun) {
          aiChip.textContent = 'NO SCAN';
          aiChip.className = 'status-pill status-pill-muted';
        } else {
          aiChip.textContent = rel.ai_state || 'PASS';
          aiChip.className = 'status-pill ' + (
            rel.ai_state === 'PASS' ? 'status-pill-approved' :
            rel.ai_state === 'REJECT' ? 'status-pill-rejected' : 'status-pill-amber'
          );
        }
      }

      if (aiExplain) {
        if (isAiNotRun) {
          aiExplain.innerHTML = `
            <div style="font-size:12px;font-weight:700;color:#64748B;margin-bottom:3px;">No AI scan yet. Use the Inspection Station</div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">Camera defect screening has not been run for this intake lot.</div>
            <a href="/qc/camera-station" class="btn-secondary" style="font-size:11px;padding:4px 10px;background:#FFF;border-color:#CBD5E1;color:var(--accent-navy);font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">
              <span>↗ Open Inspection Station</span>
            </a>
          `;
        } else {
          let aiHtml = `<strong>${rel.ai_reason || ''}</strong>`;
          if (rel.ai_details && rel.ai_details.length > 0) {
            aiHtml += `<div style="margin-top:4px;font-size:11px;color:var(--text-muted);">${rel.ai_details.map(d => `• ${d}`).join('<br>')}</div>`;
          }
          aiExplain.innerHTML = aiHtml;
        }
      }

      // Peanut Advisory Banner
      const peanutAdv = document.getElementById('qcReleasePeanutAdvisory');
      if (peanutAdv) {
        peanutAdv.style.display = rel.peanut_advisory ? 'block' : 'none';
      }

      // Combined Outcome Banner
      const banner = document.getElementById('qcReleaseOutcomeBanner');
      const title = document.getElementById('qcReleaseOutcomeTitle');
      const reason = document.getElementById('qcReleaseOutcomeReason');
      const badge = document.getElementById('qcReleaseOutcomeBadge');

      const outcome = rel.outcome || 'HOLD';
      const plainLabel = outcome === 'RELEASE' ? 'GOOD' : (outcome === 'REJECT' ? 'BAD' : 'NEEDS REVIEW');
      if (badge) {
        badge.textContent = plainLabel;
        badge.className = 'status-pill ' + (
          outcome === 'RELEASE' ? 'status-pill-approved' :
          outcome === 'REJECT' ? 'status-pill-rejected' : 'status-pill-amber'
        );
      }

      if (banner && title && reason) {
        if (outcome === 'RELEASE') {
          banner.style.background = '#ECFDF5';
          banner.style.borderColor = '#A7F3D0';
          title.style.color = '#065F46';
          title.textContent = 'OUTCOME: GOOD (RELEASE RECOMMENDED)';
          reason.style.color = '#047857';
        } else if (outcome === 'REJECT') {
          banner.style.background = '#FEF2F2';
          banner.style.borderColor = '#FECACA';
          title.style.color = '#991B1B';
          title.textContent = 'OUTCOME: BAD (REJECT RECOMMENDED)';
          reason.style.color = '#B91C1C';
        } else {
          banner.style.background = '#FEF3C7';
          banner.style.borderColor = '#FDE68A';
          title.style.color = '#92400E';
          title.textContent = 'OUTCOME: NEEDS REVIEW (HOLD)';
          reason.style.color = '#78350F';
        }
        reason.textContent = rel.outcome_reason || 'Evaluating combined decision...';
      }

      // Primary button matching the outcome
      const primaryBtn = document.getElementById('btnReleasePrimaryAction');
      const primaryText = document.getElementById('btnReleasePrimaryText');
      if (primaryBtn && primaryText) {
        if (outcome === 'RELEASE') {
          primaryBtn.style.background = '#059669';
          primaryText.textContent = '🚀 Accept Lot (GOOD)';
        } else if (outcome === 'REJECT') {
          primaryBtn.style.background = '#DC2626';
          primaryText.textContent = '❌ Reject Lot (BAD)';
        } else {
          primaryBtn.style.background = '#D97706';
          primaryText.textContent = '⚠️ Put on Hold (NEEDS REVIEW)';
        }
      }

      // Manual action buttons
      const approveManualBtn = document.getElementById('btnReleaseApproveManual');
      if (approveManualBtn) {
        if (outcome !== 'RELEASE') {
          approveManualBtn.style.opacity = '0.75';
          approveManualBtn.title = 'Release requires written justification (who, when, why)';
        } else {
          approveManualBtn.style.opacity = '1.0';
          approveManualBtn.title = 'Release lot (matches outcome)';
        }
      }
    }

    // 6. Read-Only Lot Info
    const lotSpecs = document.getElementById('qcLotInfoSpecs');
    if (lotSpecs) {
      lotSpecs.innerHTML = `
        <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Material Name:</span><span style="font-weight:700;">${lot.material_name} (${lot.unit_weight || 'Standard Spec'})</span></div>
        <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Supplier:</span><span style="font-weight:700;">${lot.supplier_name}</span></div>
        <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Purchase Order:</span><span style="font-weight:700;font-family:'JetBrains Mono',monospace;">${lot.po_number}</span></div>
        <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Received Quantity:</span><span style="font-weight:700;color:var(--accent-navy);">${lot.quantity} ${lot.unit}</span></div>
        <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Storage Conditions:</span><span style="font-weight:700;">${lot.storage_condition}</span></div>
        <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Received At:</span><span style="font-weight:700;">${lot.received_at}</span></div>
      `;
    }
  }

  function renderBoundingBoxes(defects) {
    const svg = document.getElementById('qcBoundingBoxSvg');
    if (!svg) return;
    svg.innerHTML = '';

    if (!defects || defects.length === 0) return;

    svg.innerHTML = defects.map((d, index) => {
      const bbox = d.bbox || { x: d.bbox_x, y: d.bbox_y, w: d.bbox_w, h: d.bbox_h };
      const color = index === 0 ? '#EF4444' : '#F59E0B';

      return `
        <g>
          <!-- Bounding Box Rectangle with animated stroke draw -->
          <rect class="qc-bbox-rect" x="${bbox.x}%" y="${bbox.y}%" width="${bbox.w}%" height="${bbox.h}%"
                fill="${color}" fill-opacity="0.18"
                stroke="${color}" stroke-width="2.5" rx="4" />

          <!-- Defect Tag with Confidence with fade-in -->
          <g class="qc-bbox-tag">
            <rect x="${bbox.x}%" y="${Math.max(bbox.y - 8, 2)}%" width="${Math.min(bbox.w + 10, 45)}%" height="7%"
                  fill="${color}" rx="3" />
            <text x="${bbox.x + 1}%" y="${Math.max(bbox.y - 3, 6)}%" fill="#FFFFFF" font-size="11" font-weight="700" font-family="'Plus Jakarta Sans', sans-serif">
              ${d.defect_class} [${d.confidence_percent || (Math.round(d.confidence * 100) + '%')}]
            </text>
          </g>
        </g>
      `;
    }).join('');
  }

  function handleReleasePrimaryAction() {
    const rel = currentReleaseDecision;
    const outcome = rel ? rel.outcome : 'HOLD';
    if (outcome === 'RELEASE') {
      submitDecision('APPROVED');
    } else if (outcome === 'REJECT') {
      submitDecision('REJECTED');
    } else {
      submitDecision('HOLD');
    }
  }

  function handleManualDecision(finalStatus) {
    const rel = currentReleaseDecision;
    const outcome = rel ? rel.outcome : 'HOLD';

    const isOverrideRelease = (finalStatus === 'APPROVED' && outcome !== 'RELEASE');
    const isOverrideReject = (finalStatus === 'REJECTED' && outcome === 'RELEASE');

    if (isOverrideRelease || isOverrideReject) {
      openOverrideModal(finalStatus, outcome);
      return;
    }

    submitDecision(finalStatus);
  }

  let pendingOverrideStatus = null;

  function openOverrideModal(targetStatus, currentOutcome) {
    pendingOverrideStatus = targetStatus;
    const modal = document.getElementById('qcOverrideReasonModal');
    const title = document.getElementById('qcOverrideModalTitle');
    const subtitle = document.getElementById('qcOverrideModalSubtitle');
    const input = document.getElementById('qcOverrideReasonInput');

    if (input) input.value = '';

    if (title && subtitle) {
      if (targetStatus === 'APPROVED') {
        title.textContent = `Written Reason Required: Override ${currentOutcome} → RELEASE`;
        subtitle.textContent = `The combined release check recommends ${currentOutcome}. Releasing this lot against the recommendation requires an audit-documented written justification (who, when, why).`;
      } else {
        title.textContent = `Written Reason Required: Override RELEASE → REJECT`;
        subtitle.textContent = `The combined release check recommends RELEASE. Rejecting this lot requires an audit-documented written justification (who, when, why).`;
      }
    }

    if (modal) modal.style.display = 'flex';
    if (input) setTimeout(() => input.focus(), 100);
  }

  function closeOverrideModal() {
    const modal = document.getElementById('qcOverrideReasonModal');
    if (modal) modal.style.display = 'none';
    pendingOverrideStatus = null;
  }

  async function confirmOverrideDecision() {
    const input = document.getElementById('qcOverrideReasonInput');
    const reasonText = input ? input.value.trim() : '';
    if (!reasonText || reasonText.length < 5) {
      alert("A specific written reason (who, when, why) is mandatory to override the release decision.");
      return;
    }

    const statusToSubmit = pendingOverrideStatus;
    closeOverrideModal();
    if (statusToSubmit) {
      await doSubmitDecisionWithReason(statusToSubmit, reasonText);
    }
  }

  async function doSubmitDecisionWithReason(finalStatus, notes) {
    if (!activeLotId) return;

    try {
      const res = await fetch(`/api/qc/lot/${activeLotId}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          final_status: finalStatus,
          reason: `Inspector Override: ${finalStatus}`,
          action_notes: notes
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to submit decision");

      closeDrawer();
      if (window.showToast) {
        window.showToast("QC Decision Confirmed", `Lot marked as ${finalStatus} (Override logged)`, "success");
      } else {
        alert(`SUCCESS!\n${data.message}`);
      }
      loadQueue();
    } catch (err) {
      alert("Error submitting decision: " + err.message);
    }
  }

  async function submitDecision(finalStatus, clickedBtn = null) {
    if (!activeLotId) return;

    // Check if override is required
    const rel = currentReleaseDecision;
    const outcome = rel ? rel.outcome : 'HOLD';
    const isOverrideRelease = (finalStatus === 'APPROVED' && outcome !== 'RELEASE');
    const isOverrideReject = (finalStatus === 'REJECTED' && outcome === 'RELEASE');

    if (isOverrideRelease || isOverrideReject) {
      openOverrideModal(finalStatus, outcome);
      return;
    }

    const actionText = finalStatus === 'APPROVED' ? 'APPROVED' : (finalStatus === 'HOLD' ? 'HOLD / QUARANTINE' : 'REJECT / RETURN');
    if (!confirm(`Are you sure you want to confirm "${actionText}" for this lot?`)) {
      return;
    }

    const runCall = async () => {
      const res = await fetch(`/api/qc/lot/${activeLotId}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          final_status: finalStatus,
          reason: `QC Specialist verification complete - Decision: ${finalStatus}`,
          action_notes: `Recorded at ${new Date().toLocaleString()}`
        })
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || "Failed to submit QC decision");
      }
      return await res.json();
    };

    const targetBtn = clickedBtn || (typeof event !== 'undefined' && event && event.currentTarget ? event.currentTarget : null) || document.querySelector('#qcDetailDrawer .btn-primary-action');

    if (targetBtn && window.FoodManAnimations && !window.FoodManAnimations.isReducedMotion()) {
      try {
        await window.FoodManAnimations.buttonAction(targetBtn, async () => {
          const result = await runCall();
          if (window.showToast) {
            window.showToast("QC Decision Confirmed", `Lot marked as ${finalStatus}`, "success");
          }
        }, {
          successText: 'Confirmed ✓',
          holdMs: 260,
          onComplete: () => {
            closeDrawer();
            loadQueue();
          }
        });
      } catch (err) {
        if (window.showToast) window.showToast("QC Submission Error", err.message, "danger");
        else alert(`Error: ${err.message}`);
      }
    } else {
      try {
        const result = await runCall();
        closeDrawer();
        if (window.showToast) window.showToast("QC Decision Confirmed", result.message, "success");
        else alert(`SUCCESS!\n${result.message}`);
        loadQueue();
      } catch (err) {
        alert(`Error: ${err.message}`);
      }
    }
  }

  function closeDrawer() {
    const backdrop = document.getElementById('qcDrawerBackdrop');
    const drawer = document.getElementById('qcDetailDrawer');
    if (backdrop) backdrop.classList.remove('show');
    if (drawer) drawer.classList.remove('open');
    activeLotId = null;
    currentReleaseDecision = null;
  }

  // QC Lab Measures Modal handlers (Stage C1)
  async function openQcMeasuresModal(lotId, lotNumber) {
    modalLotId = lotId;
    const badge = document.getElementById('qcMeasuresTargetLotBadge');
    if (badge) badge.textContent = lotNumber ? `${lotNumber} (#${lotId})` : `Lot #${lotId}`;

    const banner = document.getElementById('qcMeasuresStatusBanner');
    if (banner) banner.style.display = 'none';

    // Clear previous form inputs
    const docInput = document.getElementById('qcMeasuresDocNumber');
    const accInput = document.getElementById('qcMeasuresAccreditation');
    const mInput = document.getElementById('qcMeasuresMoisture');
    const aInput = document.getElementById('qcMeasuresAflatoxin');
    const fInput = document.getElementById('qcMeasuresFfa');
    const pInput = document.getElementById('qcMeasuresPurity');

    if (docInput) docInput.value = '';
    if (accInput) accInput.value = 'ISO 17025 Certified';
    if (mInput) mInput.value = '';
    if (aInput) aInput.value = '';
    if (fInput) fInput.value = '';
    if (pInput) pInput.value = '';

    // Fetch existing values via existing endpoint
    if (lotId) {
      try {
        const res = await fetch(`/api/qc/lot/${lotId}/qc-measures`);
        const data = await res.json();
        if (data.success) {
          if (docInput) docInput.value = (data.coa && data.coa.doc_number) || `COA-${(data.lot && data.lot.lot_number) || lotId}`;
          if (accInput && data.coa && data.coa.lab_accreditation) accInput.value = data.coa.lab_accreditation;
          if (mInput && data.measures && data.measures.moisture !== undefined && data.measures.moisture !== null) mInput.value = data.measures.moisture;
          if (aInput && data.measures && data.measures.aflatoxin_b1 !== undefined && data.measures.aflatoxin_b1 !== null) aInput.value = data.measures.aflatoxin_b1;
          if (fInput && data.measures && data.measures.ffa !== undefined && data.measures.ffa !== null) fInput.value = data.measures.ffa;
          if (pInput && data.measures && data.measures.purity !== undefined && data.measures.purity !== null) pInput.value = data.measures.purity;
        }
      } catch (err) {
        console.warn("Could not pre-fill QC measures:", err);
      }
    }

    const modal = document.getElementById('qcMeasuresModal');
    if (modal) modal.style.display = 'flex';
  }

  function closeQcMeasuresModal() {
    const modal = document.getElementById('qcMeasuresModal');
    if (modal) modal.style.display = 'none';
  }

  async function submitQcMeasures(e) {
    if (e) e.preventDefault();
    if (!modalLotId) {
      alert("No lot selected for recording QC measures.");
      return;
    }

    const docInput = document.getElementById('qcMeasuresDocNumber');
    const accInput = document.getElementById('qcMeasuresAccreditation');
    const mInput = document.getElementById('qcMeasuresMoisture');
    const aInput = document.getElementById('qcMeasuresAflatoxin');
    const fInput = document.getElementById('qcMeasuresFfa');
    const pInput = document.getElementById('qcMeasuresPurity');

    const payload = {
      doc_number: docInput ? docInput.value.trim() : '',
      lab_accreditation: accInput ? accInput.value.trim() : '',
      moisture: mInput && mInput.value !== '' ? parseFloat(mInput.value) : null,
      aflatoxin_b1: aInput && aInput.value !== '' ? parseFloat(aInput.value) : null,
      ffa: fInput && fInput.value !== '' ? parseFloat(fInput.value) : null,
      purity: pInput && pInput.value !== '' ? parseFloat(pInput.value) : null
    };

    const banner = document.getElementById('qcMeasuresStatusBanner');

    try {
      const res = await fetch(`/api/qc/lot/${modalLotId}/qc-measures`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (banner) {
        banner.style.display = 'block';
        if (data.success) {
          banner.style.background = '#ECFDF5';
          banner.style.color = '#065F46';
          banner.style.border = '1px solid #A7F3D0';
          banner.textContent = `✓ Saved! Combined outcome: ${data.merged_label}. COA State: ${(data.release_decision && data.release_decision.coa_state) || 'PASS'}.`;
          setTimeout(() => {
            closeQcMeasuresModal();
            loadQueue();
            if (activeLotId === modalLotId) {
              openQcReviewDrawer(activeLotId);
            }
          }, 1200);
        } else {
          banner.style.background = '#FEF2F2';
          banner.style.color = '#991B1B';
          banner.style.border = '1px solid #FECACA';
          banner.textContent = `Error: ${data.error || 'Failed to save'}`;
        }
      }
    } catch (err) {
      alert("Network error saving QC measures: " + err.message);
    }
  }

  return {
    init,
    openQcReviewDrawer,
    submitDecision,
    handleReleasePrimaryAction,
    handleManualDecision,
    openOverrideModal,
    closeOverrideModal,
    confirmOverrideDecision,
    closeDrawer,
    // Lab Measures Modal methods (Stage C1)
    openQcMeasuresModal,
    closeQcMeasuresModal,
    submitQcMeasures,
    // AI Inspection methods
    checkModelStatus,
    openCamera,
    openFilePicker,
    onImageSelected,
    clearImageSelection,
    onTargetTypeChange,
    runAiInspection,
    renderAiResults,
    submitFeedback,
    submitInspectorFeedback,
    confirmAiVerdict,
    downloadPdfReport,
    recalculatePassFail,
    submitFourPillarDecision
  };
})();


// Global window helpers
window.QCApp = QCApp;
window.closeQcDrawer = () => QCApp.closeDrawer();
window.submitDecisionDirect = (status) => QCApp.handleManualDecision(status);
window.openQcMeasuresModal = (lotId, lotNumber) => QCApp.openQcMeasuresModal(lotId, lotNumber);
window.closeQcMeasuresModal = () => QCApp.closeQcMeasuresModal();


