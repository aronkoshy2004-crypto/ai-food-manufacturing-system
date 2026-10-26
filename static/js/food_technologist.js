/**
 * Food Technologist Audit Command Center Client Logic
 * PRD Step 4: 7-Stage Full Farm-to-Fork Lifecycle Journey
 */

(function() {
  'use strict';

  // DOM Handles
  const searchInput = document.getElementById('ftSearchInput');
  const materialSelect = document.getElementById('ftMaterialSelect');
  const supplierSelect = document.getElementById('ftSupplierSelect');
  const outcomeSelect = document.getElementById('ftOutcomeSelect');
  const stageSelect = document.getElementById('ftStageSelect');
  const resetBtn = document.getElementById('ftResetFiltersBtn');
  const tableBody = document.getElementById('ftLotTableBody');
  const lotCountBadge = document.getElementById('ftLotCountBadge');

  // Drawer Handles
  const drawer = document.getElementById('journeyDrawer');
  const drawerOverlay = document.getElementById('drawerOverlay');
  const drawerCloseBtn = document.getElementById('drawerCloseBtn');
  const drawerPdfBtn = document.getElementById('drawerPdfBtn');

  let debounceTimer = null;

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    loadLots();

    // Event listeners
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(loadLots, 300);
      });
    }

    if (materialSelect) materialSelect.addEventListener('change', loadLots);
    if (supplierSelect) supplierSelect.addEventListener('change', loadLots);
    if (outcomeSelect) outcomeSelect.addEventListener('change', loadLots);
    if (stageSelect) stageSelect.addEventListener('change', loadLots);

    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (searchInput) searchInput.value = '';
        if (materialSelect) materialSelect.value = 'all';
        if (supplierSelect) supplierSelect.value = 'all';
        if (outcomeSelect) outcomeSelect.value = 'ALL';
        if (stageSelect) stageSelect.value = 'all';
        loadLots();
      });
    }

    if (drawerCloseBtn) drawerCloseBtn.addEventListener('click', closeDrawer);
    if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeDrawer();
    });
  });

  // Fetch and display lots
  async function loadLots() {
    if (!tableBody) return;

    tableBody.innerHTML = `
      <tr>
        <td colspan="11" style="text-align:center;padding:36px;color:#64748B;">
          <div style="display:inline-block;animation:spin 1s linear infinite;width:20px;height:20px;border:2px solid #CBD5E1;border-top-color:#4F46E5;border-radius:50%;margin-bottom:8px;"></div>
          <div>Loading lots...</div>
        </td>
      </tr>
    `;

    const params = new URLSearchParams();
    if (searchInput && searchInput.value.trim()) params.append('search', searchInput.value.trim());
    if (materialSelect && materialSelect.value !== 'all') params.append('material', materialSelect.value);
    if (supplierSelect && supplierSelect.value !== 'all') params.append('supplier', supplierSelect.value);
    if (outcomeSelect && outcomeSelect.value !== 'ALL') params.append('outcome', outcomeSelect.value);
    if (stageSelect && stageSelect.value !== 'all') params.append('stage', stageSelect.value);

    try {
      const res = await fetch(`/api/food-technologist/lots?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();

      if (lotCountBadge) {
        lotCountBadge.textContent = `${data.count} lots listed`;
      }

      renderLotsTable(data.lots || []);
    } catch (err) {
      console.error('Error loading lots:', err);
      tableBody.innerHTML = `
        <tr>
          <td colspan="11" style="text-align:center;padding:28px;color:#EF4444;">
            Failed to load audit lots. Please refresh or check connection.
          </td>
        </tr>
      `;
    }
  }

  function renderLotsTable(lots) {
    if (!lots || lots.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="11" style="text-align:center;padding:36px;color:#64748B;">
            <div style="font-size:14px;font-weight:600;margin-bottom:4px;">No matching lots found</div>
            <div style="font-size:12px;">Try adjusting search keywords or resetting filters.</div>
          </td>
        </tr>
      `;
      return;
    }

    const rows = lots.map(lot => {
      // Outcome Badge
      const outcome = lot.outcome ? lot.outcome.plain_label : 'NEEDS REVIEW';
      let outcomeBadgeClass = 'badge-review';
      if (outcome === 'GOOD') outcomeBadgeClass = 'badge-good';
      else if (outcome === 'BAD') outcomeBadgeClass = 'badge-bad';

      // AI Result
      const ai = lot.ai_result || {};
      let aiDisplay = '—';
      if (ai.has_run) {
        if (ai.defects_count === 0) {
          aiDisplay = `<span style="color:#166534;font-weight:600;">✓ 0 defects</span> <span style="color:#64748B;font-size:11px;">(${Math.round(ai.confidence * 100)}%)</span>`;
        } else {
          aiDisplay = `<span style="color:#991B1B;font-weight:600;">⚠ ${ai.defects_count} defects</span> <span style="color:#64748B;font-size:11px;">(${Math.round(ai.confidence * 100)}%)</span>`;
        }
      }

      // QC Measures
      const qc = lot.qc_measures || {};
      const moisture = qc.moisture || '—';
      const aflatoxin = qc.aflatoxin_b1 || '—';
      const ffa = qc.ffa || '—';
      const purity = qc.purity || '—';

      // QC Sign-off
      const signoff = lot.qc_signoff || {};
      let signoffDisplay = `<span style="color:#64748B;">Pending</span>`;
      if (signoff.has_decision) {
        const sColor = signoff.status === 'APPROVED' ? '#166534' : (signoff.status === 'REJECTED' ? '#991B1B' : '#92400E');
        signoffDisplay = `<div><b style="color:${sColor};">${signoff.status}</b></div><div style="font-size:11px;color:#64748B;">${signoff.inspector || 'QC'}</div>`;
      }

      // Stage
      const stage = lot.stage || { number: 2, name: 'Arrived (GRN)' };
      const stageClass = stage.number >= 6 ? 'stage-completed' : (stage.number >= 3 ? 'stage-active' : '');

      return `
        <tr>
          <td>
            <a href="javascript:void(0)" onclick="window.ftOpenDrawer(${lot.id})" style="font-weight:700;color:#4F46E5;text-decoration:none;">
              ${lot.lot_number}
            </a>
            <div style="font-size:11px;color:#64748B;">${lot.material_name} (${lot.category})</div>
          </td>
          <td>
            <div style="font-weight:600;color:#0F172A;">${lot.supplier_name || 'Supplier'}</div>
            <div style="font-size:11px;color:#64748B;">${lot.quantity} ${lot.unit}</div>
          </td>
          <td>
            <div style="font-size:12px;">${lot.received_at ? lot.received_at.split(' ')[0] : '—'}</div>
          </td>
          <td>
            <div>${aiDisplay}</div>
          </td>
          <td>
            <div class="lab-preview-grid">
              <div class="lab-preview-item"><span class="lab-preview-lbl">M:</span> <b>${moisture}</b></div>
              <div class="lab-preview-item"><span class="lab-preview-lbl">Afla:</span> <b>${aflatoxin}</b></div>
              <div class="lab-preview-item"><span class="lab-preview-lbl">FFA:</span> <b>${ffa}</b></div>
              <div class="lab-preview-item"><span class="lab-preview-lbl">Pur:</span> <b>${purity}</b></div>
            </div>
          </td>
          <td>
            <span class="badge-outcome ${outcomeBadgeClass}">
              ${outcome}
            </span>
          </td>
          <td>
            ${signoffDisplay}
          </td>
          <td>
            <span class="badge-stage ${stageClass}">
              S${stage.number}: ${stage.name}
            </span>
          </td>
          <td>
            <span style="font-family:monospace;font-size:11px;color:${lot.production_batch !== '—' ? '#0F172A' : '#94A3B8'};">
              ${lot.production_batch}
            </span>
          </td>
          <td>
            <span style="font-family:monospace;font-size:11px;color:${lot.dispatch_code !== '—' ? '#0F172A' : '#94A3B8'};">
              ${lot.dispatch_code}
            </span>
          </td>
          <td style="text-align:right;white-space:nowrap;">
            <button onclick="window.ftOpenDrawer(${lot.id})" class="ft-action-btn" title="View Full 7-Stage Farm-to-Fork Journey">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              Journey
            </button>
            <a href="/api/food-technologist/lot/${lot.id}/pdf" target="_blank" class="ft-action-btn" title="Download Official Quality Dossier (PDF)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
              PDF
            </a>
          </td>
        </tr>
      `;
    }).join('');

    tableBody.innerHTML = rows;
  }

  // Open Full Journey Drawer
  window.ftOpenDrawer = async function(lotId) {
    if (!drawer || !drawerOverlay) return;

    drawer.classList.add('active');
    drawerOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';

    if (drawerPdfBtn) {
      drawerPdfBtn.href = `/api/food-technologist/lot/${lotId}/pdf`;
    }

    try {
      const res = await fetch(`/api/food-technologist/lot/${lotId}`);
      if (!res.ok) throw new Error('Lot not found');
      const data = await res.json();
      populateDrawer(data.journey);
    } catch (err) {
      console.error('Error fetching lot journey:', err);
    }
  };

  function closeDrawer() {
    if (!drawer || !drawerOverlay) return;
    drawer.classList.remove('active');
    drawerOverlay.classList.remove('active');
    document.body.style.overflow = '';
  }

  function populateDrawer(journey) {
    if (!journey) return;

    const lot = journey.lot || {};
    const stageInfo = journey.stage_info || {};
    const s1 = journey.stage_1_supplier_po || {};
    const s2 = journey.stage_2_arrival_grn || {};
    const s3 = journey.stage_3_inspection_station || {};
    const s4 = journey.stage_4_qc_measures || {};
    const s5 = journey.stage_5_qc_signoff || {};
    const s6 = journey.stage_6_production || {};
    const s7 = journey.stage_7_warehouse_dispatch || {};

    // Header info
    const lotNumEl = document.getElementById('drawerLotNumber');
    const lotSubEl = document.getElementById('drawerLotSubtitle');
    const outcomeBadgeEl = document.getElementById('drawerOutcomeBadge');

    if (lotNumEl) lotNumEl.textContent = lot.lot_number || 'LOT';
    if (lotSubEl) lotSubEl.textContent = `${lot.material_name} (${lot.category}) • ${lot.supplier_name}`;

    const rec = s5.merged_recommendation || {};
    const plainOutcome = rec.plain_label || 'GOOD';
    if (outcomeBadgeEl) {
      outcomeBadgeEl.textContent = plainOutcome;
      outcomeBadgeEl.className = 'badge-outcome ' + (plainOutcome === 'GOOD' ? 'badge-good' : (plainOutcome === 'BAD' ? 'badge-bad' : 'badge-review'));
    }

    // Update 7-Stage Stepper Nodes
    const curStage = stageInfo.current_stage || 2;
    for (let i = 1; i <= 7; i++) {
      const node = document.getElementById(`stepNode${i}`);
      if (node) {
        node.className = 'step-node';
        if (i < curStage) {
          node.classList.add('completed');
        } else if (i === curStage) {
          node.classList.add('active');
        }
      }
    }

    // Stage 1: Supplier & PO
    const sup = s1.supplier || {};
    const po = s1.po || {};
    setText('stage1SupplierName', `${sup.name} (${sup.code || 'SUP'}) - Rating: ${sup.rating || 4.8}★`);
    setText('stage1PoNumber', po.po_number || 'PO-DIRECT');
    setText('stage1OrderedQty', po.items && po.items.length > 0 ? `${po.items[0].quantity_ordered} ${po.items[0].unit}` : `${lot.quantity} ${lot.unit}`);
    setText('stage1OrderDate', po.order_date || '—');

    // Stage 2: Arrival & Intake
    setText('stage2GrnNumber', s2.grn_number || 'GRN-INBOUND');
    setText('stage2ArrivalDate', s2.received_date || lot.received_at || '—');
    setText('stage2RecvQty', `${s2.quantity_received || lot.quantity} ${s2.unit || lot.unit}`);
    setText('stage2Carrier', `${s2.truck_plate || '29C-438.12'} (${s2.delivery_note_ref || 'DN-2026'})`);
    setText('stage2Storage', s2.storage_condition || lot.storage_condition || 'Cool storage 4-6°C');
    setText('stage2Receiver', s2.receiver || 'Receiving Custodian');

    // Stage 3: Inspection Station
    const ai = s3.ai_inspection;
    if (ai) {
      setText('stage3ModelVersion', `${ai.model_version} (${ai.model_status})`);
      setText('stage3DefectCount', `${ai.total_defects_count} defects`);
      setText('stage3Confidence', `${Math.round(ai.avg_confidence * 100)}% avg confidence`);
      setText('stage3Latency', `${ai.inference_time_ms} ms`);
      setText('stage3SummaryText', ai.summary || 'Visual scan completed');

      const imgWrap = document.getElementById('stage3ImageWrap');
      const imgEl = document.getElementById('stage3Image');
      if (ai.annotated_image_url && imgWrap && imgEl) {
        imgEl.src = ai.annotated_image_url;
        imgWrap.style.display = 'block';
      } else if (imgWrap) {
        imgWrap.style.display = 'none';
      }
    } else {
      setText('stage3ModelVersion', 'Not yet evaluated');
      setText('stage3DefectCount', '—');
      setText('stage3Confidence', '—');
      setText('stage3Latency', '—');
      setText('stage3SummaryText', 'Pending Inspection Station run');
      const imgWrap = document.getElementById('stage3ImageWrap');
      if (imgWrap) imgWrap.style.display = 'none';
    }

    // Stage 4: QC Measures & COA
    const coa = s4.coa || {};
    setText('stage4CoaDoc', `${coa.doc_number || 'COA-PENDING'} ${coa.is_verified ? '(Verified ✓)' : ''}`);
    setText('stage4LabAccreditation', coa.lab_accreditation || 'VILAS 102 / ISO 17025');

    const testsBody = document.getElementById('stage4TestsBody');
    const params = s4.parameters || [];
    if (testsBody) {
      if (params.length > 0) {
        testsBody.innerHTML = params.map(p => `
          <tr>
            <td><b>${p.name}</b></td>
            <td>${p.spec}</td>
            <td><b>${p.value} ${p.unit}</b></td>
            <td>
              <span class="badge-outcome ${p.is_pass ? 'badge-good' : 'badge-bad'}" style="font-size:10.5px;padding:2px 6px;">
                ${p.is_pass ? 'PASS' : 'FAIL'}
              </span>
            </td>
          </tr>
        `).join('');
      } else {
        testsBody.innerHTML = `
          <tr><td colspan="4" style="text-align:center;color:#64748B;">Standard parameters pending test recording</td></tr>
        `;
      }
    }

    // Stage 5: QC Sign-Off
    const dec = s5.decision || {};
    setText('stage5FinalStatus', dec.final_status || 'PENDING_QC');
    setText('stage5Inspector', dec.inspector_name || 'QC Inspector');
    setText('stage5Timestamp', dec.decided_at || 'Awaiting sign-off');
    setText('stage5Reason', dec.reason || 'Standard quality verification');
    setText('stage5MergedOutcome', rec.plain_label || 'GOOD');
    setText('stage5MergedReason', rec.reason || 'Decision calculated from AI detection and laboratory specs');

    // Stage 6: Production
    const batches = s6.batches || [];
    const stage6Content = document.getElementById('stage6Content');
    if (stage6Content) {
      if (batches.length > 0) {
        const b = batches[0];
        setText('stage6BatchCode', b.batch_code);
        setText('stage6ProductName', b.product_name);
        setText('stage6LineName', b.line_name);
        setText('stage6Progress', `${b.progress}% (${b.status})`);
      } else {
        stage6Content.innerHTML = `
          <div style="font-size:12.5px;color:#64748B;padding:6px 0;">
            Lot is not yet consumed by a manufacturing batch (ready in warehouse storage once released).
          </div>
        `;
      }
    }

    // Stage 7: Warehouse & Dispatch
    const dispatches = s7.dispatches || [];
    const inv = s7.inventory || [];
    const stage7Content = document.getElementById('stage7Content');
    if (stage7Content) {
      if (dispatches.length > 0) {
        const d = dispatches[0];
        setText('stage7Location', inv.length > 0 ? inv[0].storage_bin : 'Cold Storage Zone A');
        setText('stage7Temp', `${d.temp_sensor_celsius}°C (Cold Chain Spec: ${d.temp_spec_range})`);
        setText('stage7DispatchCode', d.dispatch_code);
        setText('stage7Customer', `${d.customer_name} (${d.status})`);
      } else if (inv.length > 0) {
        setText('stage7Location', inv[0].storage_bin);
        setText('stage7Temp', inv[0].storage_temperature);
        setText('stage7DispatchCode', 'In Warehouse Stock');
        setText('stage7Customer', `${inv[0].available_quantity} ${inv[0].unit} available for dispatch`);
      } else {
        stage7Content.innerHTML = `
          <div style="font-size:12.5px;color:#64748B;padding:6px 0;">
            No outbound cold-chain dispatches allocated yet.
          </div>
        `;
      }
    }
  }

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

})();
