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

  function init(view) {

    if (view === 'ai-inspection') {
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

  function onImageSelected(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    selectedFile = file;

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
      if (filenameEl) filenameEl.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    };
    reader.readAsDataURL(file);
  }

  function clearImageSelection() {
    selectedFile = null;
    const input = document.getElementById('aiFileInput');
    if (input) input.value = '';

    const emptyState = document.getElementById('dropzoneEmptyState');
    if (emptyState) emptyState.style.display = 'block';

    const previewState = document.getElementById('dropzonePreviewState');
    if (previewState) previewState.style.display = 'none';
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

    const btn = document.getElementById('btnRunAiInspection');
    const originalHtml = btn ? btn.innerHTML : '';
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

    // Timestamp & Latency
    const tsEl = document.getElementById('aiResultTimestamp');
    if (tsEl) {
      tsEl.textContent = `Inspected: ${new Date(ai.timestamp || Date.now()).toLocaleTimeString()}`;
    }

    const speedEl = document.getElementById('aiInferenceSpeed');
    if (speedEl) {
      speedEl.textContent = `${ai.inference_time_ms || 0} ms`;
    }

    // Set lastInspectionId for feedback loop
    lastInspectionId = ai.inspection_id || (data.data && data.data.inspection_id) || data.inspection_id;
    const fbCard = document.getElementById('aiFeedbackLoopCard');
    if (fbCard && lastInspectionId) {
      fbCard.style.display = 'block';
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
    const defects = ai.defects || [];
    if (badgeCount) {
      badgeCount.textContent = `${defects.length} Defect${defects.length === 1 ? '' : 's'}`;
      badgeCount.className = defects.length > 0 ? 'status-pill-badge pill-rejected' : 'status-pill-badge pill-approved';
    }

    if (defects.length === 0) {
      const healthyCount = ai.healthy_specimens_count || 0;
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
  }

  // =========================================================================
  // CONTINUOUS IMPROVEMENT FEEDBACK LOOP
  // =========================================================================

  async function submitFeedback(feedbackType) {
    if (!lastInspectionId) {
      alert("No active inspection to submit feedback for.");
      return;
    }

    try {
      const res = await fetch('/api/qc/ai-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ai_inspection_id: lastInspectionId,
          feedback_type: feedbackType,
          notes: `Inspector ground-truth validation: ${feedbackType}`
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to submit feedback');

      alert("FEEDBACK RECORDED!\n\nThank you for validating this detection. Your ground-truth input has been logged into the continuous model retraining pipeline.");
      const card = document.getElementById('aiFeedbackLoopCard');
      if (card) {
        card.innerHTML = `
          <div style="font-size:12px;font-weight:700;color:#065F46;display:flex;align-items:center;gap:6px;">
            <span>✓ Inspector feedback recorded for model retraining dataset (${feedbackType}).</span>
          </div>
        `;
      }
    } catch (err) {
      alert("Error logging feedback: " + err.message);
    }
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

  async function loadQueue() {
    const container = document.getElementById('qcCardsContainer');
    if (!container) return;
    container.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
        Loading QC inspection queue...
      </div>
    `;

    try {
      const res = await fetch('/api/qc/queue');
      if (!res.ok) throw new Error("Error loading QC queue");
      const json = await res.json();
      const cards = json.cards || [];

      const countBadge = document.getElementById('qcQueueCountBadge');
      if (countBadge) countBadge.textContent = `${cards.length} lots pending inspection`;

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

      container.innerHTML = cards.map(card => FoodManComponents.RecordCard({
        ...card,
        onClick: () => openQcReviewDrawer(card.db_id)
      })).join('');

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
    }

    // 3. Lab Test Results Table
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
        testsBody.innerHTML = '<tr><td colspan="4" style="padding:12px;text-align:center;color:var(--text-muted);">Performing sample laboratory analysis...</td></tr>';
      }
    }

    // 4. COA Document
    if (data.coa) {
      const docEl = document.getElementById('qcCoaDocNumber');
      if (docEl) docEl.textContent = data.coa.doc_number;
      const accEl = document.getElementById('qcCoaAccreditation');
      if (accEl) accEl.textContent = `Lab Accreditation: ${data.coa.lab_accreditation}`;
    }

    // 5. Read-Only Lot Info
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

  async function submitDecision(finalStatus, clickedBtn = null) {
    if (!activeLotId) return;

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

      if (!res.ok) throw new Error("Failed to submit QC decision");
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
  }

  return {
    init,
    openQcReviewDrawer,
    submitDecision,
    closeDrawer,
    // AI Inspection methods
    checkModelStatus,
    onImageSelected,
    clearImageSelection,
    onTargetTypeChange,
    runAiInspection,
    renderAiResults,
    submitFeedback,
    submitFourPillarDecision
  };
})();


// Global window helpers
window.closeQcDrawer = () => QCApp.closeDrawer();
window.submitDecisionDirect = (status) => QCApp.submitDecision(status);

