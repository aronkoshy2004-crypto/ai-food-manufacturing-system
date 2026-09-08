/**
 * Food Man - Phase 3 Production Client Controller
 * Recommendations, Batches Card Grid, Stage Timeline Stepper, Packaging & Wizard
 */
const ProductionApp = (function() {

  let currentBatches = [];
  let currentRecommendations = [];
  let activeView = 'batches';
  let selectedBatch = null;

  function init() {
    const urlParams = new URLSearchParams(window.location.search);
    activeView = urlParams.get('view') || 'batches';

    if (activeView === 'recommendations') {
      loadRecommendations();
    } else if (activeView === 'recipes') {
      loadRecommendations(); // shares product BOM view
    } else {
      loadBatches();
    }
  }

  // ---------------------------------------------------------------------------
  // 1. Recommendations & Produceability Rule Check
  // ---------------------------------------------------------------------------
  async function loadRecommendations() {
    try {
      const resp = await fetch('/api/production/recommendations');
      const data = await resp.json();
      if (data.success) {
        currentRecommendations = data.data;
        renderRecommendations(data.data);
      }
    } catch (e) {
      console.error("Failed loading recommendations", e);
    }
  }

  function renderRecommendations(items) {
    const container = document.getElementById('productionCardGrid');
    const countEl = document.getElementById('totalRecordsCount');
    if (!container) return;

    if (countEl) countEl.innerText = `${items.length} Thành phẩm được đánh giá BOM vs Lô QC`;
    container.innerHTML = '';

    items.forEach(prod => {
      const isProduceable = prod.readiness === 'PRODUCEABLE';
      const pillClass = isProduceable ? 'pill-green' : 'pill-red';
      const pillLabel = isProduceable ? '✓ Sẵn sàng sản xuất' : '⚠ Thiếu nguyên liệu QC';

      let missingHtml = '';
      if (!isProduceable && prod.missing_materials.length > 0) {
        missingHtml = `
          <div style="margin-top:10px;padding:8px 10px;background:#FEF2F2;border-radius:6px;font-size:11.5px;color:#991B1B;">
            <strong>Nguyên liệu chưa đủ chuẩn:</strong>
            ${prod.missing_materials.map(m => `<div>• ${m.material_name}: thiếu ${m.shortage} ${m.unit}</div>`).join('')}
          </div>
        `;
      }

      const card = document.createElement('div');
      card.className = 'record-card';
      card.innerHTML = `
        <div class="card-header-row">
          <div>
            <span class="card-id-badge" style="background:#EEF3FA;color:var(--accent-navy);">${prod.product_code}</span>
            <span class="card-title-text" style="display:block;margin-top:4px;font-weight:700;font-size:14px;">${prod.product_name}</span>
          </div>
          <span class="card-secondary-stat">Định mức: ${prod.standard_yield.toLocaleString()} ${prod.yield_unit}</span>
        </div>

        <div class="card-minigrid" style="margin-top:10px;">
          <div class="minigrid-cell">
            <span class="minigrid-label">Chủng loại</span>
            <span class="minigrid-val">${prod.category}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Công thức (BOM)</span>
            <span class="minigrid-val">${prod.recipe_code}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Khả năng sản xuất</span>
            <span class="minigrid-val" style="font-weight:700;color:${isProduceable ? '#059669' : '#DC2626'}">
              ${prod.max_batches_possible} Mẻ tiêu chuẩn
            </span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Nguyên liệu BOM</span>
            <span class="minigrid-val">${prod.bom_items.length} Thành phần</span>
          </div>
        </div>

        ${missingHtml}

        <div class="card-footer-row" style="margin-top:14px;">
          <button class="btn-primary-action" style="padding:6px 14px;font-size:12px;" onclick="ProductionApp.openWizardForProduct(${prod.product_id})">
            + Khởi tạo mẻ
          </button>
          <span class="readiness-pill ${pillClass}">
            ${pillLabel}
          </span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  // ---------------------------------------------------------------------------
  // 2. Batches Card Grid (Mirrors reference vehicle cards)
  // ---------------------------------------------------------------------------
  async function loadBatches() {
    try {
      const resp = await fetch('/api/production/batches');
      const data = await resp.json();
      if (data.success) {
        currentBatches = data.data;
        renderBatches(data.data);
      }
    } catch (e) {
      console.error("Failed loading batches", e);
    }
  }

  function renderBatches(batches) {
    const container = document.getElementById('productionCardGrid');
    const countEl = document.getElementById('totalRecordsCount');
    if (!container) return;

    if (countEl) countEl.innerText = `${batches.length} Lô sản xuất trên dây chuyền`;
    container.innerHTML = '';

    batches.forEach(b => {
      const isComplete = b.status === 'COMPLETE';
      const statusPillClass = isComplete ? 'status-pill-approved' : 'status-pill-pending';
      const statusDotClass = isComplete ? 'dot-approved' : 'dot-pending';
      const statusLabel = isComplete ? 'Hoàn tất (COMPLETE)' : 'Đang sản xuất (IN_PROGRESS)';

      const card = document.createElement('div');
      card.className = 'record-card';
      card.onclick = () => selectBatch(b.id);

      card.innerHTML = `
        <div class="card-header-row">
          <div>
            <span class="card-id-badge">${b.batch_code}</span>
            <span class="card-title-text" style="display:block;margin-top:4px;font-weight:700;font-size:14px;">${b.product_name}</span>
          </div>
          <span class="card-secondary-stat">${b.actual_quantity.toLocaleString()} / ${b.target_quantity.toLocaleString()} ${b.unit}</span>
        </div>

        <div class="card-progress-bar" style="margin: 12px 0 6px 0;">
          <div class="card-progress-fill" style="width: ${b.progress || 20}%; background: ${isComplete ? '#10B981' : 'var(--accent-navy)'};"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted);margin-bottom:10px;">
          <span>Tiến độ công đoạn: ${b.current_stage}</span>
          <span>${b.progress}%</span>
        </div>

        <div class="card-minigrid">
          <div class="minigrid-cell">
            <span class="minigrid-label">Dây chuyền</span>
            <span class="minigrid-val">${b.line_name}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Thông số nhiệt</span>
            <span class="minigrid-val">${b.temperature_spec}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Ngày sản xuất</span>
            <span class="minigrid-val">${b.mfg_date || 'Hôm nay'}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Hạn sử dụng</span>
            <span class="minigrid-val">${b.expiry_date || '180 ngày'}</span>
          </div>
        </div>

        <div class="card-footer-row">
          <div class="avatar-stack">
            <div class="avatar-stack-item">TM</div>
            <div class="avatar-stack-item" style="background:#059669;">K1</div>
            <div class="avatar-stack-item" style="background:#D97706;">K2</div>
          </div>
          <span class="status-pill ${statusPillClass}">
            <span class="status-indicator-dot ${statusDotClass}"></span>
            ${statusLabel}
          </span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  // ---------------------------------------------------------------------------
  // 3. Batch Detail Drawer with Stage Timeline / Stepper
  // ---------------------------------------------------------------------------
  async function selectBatch(batchId) {
    try {
      const resp = await fetch(`/api/production/batches/${batchId}`);
      const data = await resp.json();
      if (!data.success) return;

      selectedBatch = data.data;
      openBatchDrawer(data.data);
    } catch (e) {
      console.error("Error fetching batch details", e);
    }
  }

  function openBatchDrawer(batch) {
    const drawer = document.getElementById('detailDrawerRoot');
    const backdrop = document.getElementById('drawerBackdrop');
    if (!drawer) return;

    document.getElementById('drawerRecordId').innerText = batch.batch_code;

    // Slot 1: Visual Slot
    const visualSlot = document.getElementById('drawerVisualSlot');
    visualSlot.innerHTML = `
      <div style="background:var(--accent-navy);color:#FFF;padding:16px;border-radius:var(--radius-md);margin-bottom:12px;">
        <div style="font-size:12px;opacity:0.8;">LÔ SẢN XUẤT NHÀ MÁY</div>
        <div style="font-size:16px;font-weight:800;margin-top:2px;">${batch.product_name}</div>
        <div style="font-size:12.5px;margin-top:8px;display:flex;justify-content:space-between;">
          <span>Sản lượng: <strong>${batch.actual_quantity.toLocaleString()} / ${batch.target_quantity.toLocaleString()} ${batch.unit}</strong></span>
          <span>Dây chuyền: <strong>${batch.line_name}</strong></span>
        </div>
      </div>
    `;

    // Slot 2: Field Slot -> Stage Timeline Stepper & Packaging Form
    const fieldSlot = document.getElementById('drawerFieldSlot');
    const stages = batch.process_stages || [];

    let stepperHtml = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
        <span style="font-size:12px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;">
          TIẾN TRÌNH CÔNG ĐOẠN (TIMELINE STEPPER)
        </span>
        ${batch.status !== 'COMPLETE' ? `
          <button class="btn-primary-action" style="padding:4px 10px;font-size:11px;" onclick="ProductionApp.advanceCurrentStage(${batch.id})">
            Hoàn tất công đoạn ▶
          </button>
        ` : `<span style="font-size:11.5px;font-weight:700;color:#059669;">✓ Đã hoàn tất 5 công đoạn</span>`}
      </div>
      <div class="stage-stepper-container">
    `;

    stages.forEach(s => {
      const isDone = s.status === 'COMPLETED';
      const isActive = s.status === 'IN_PROGRESS';
      const itemClass = isDone ? 'is-completed' : (isActive ? 'is-active' : '');
      const timeStr = isDone 
        ? `${s.started_at || ''} → ${s.ended_at || ''} (${s.duration_minutes || 0} phút)`
        : (isActive ? `Bắt đầu: ${s.started_at || 'Vừa bắt đầu'} • Đang thực hiện` : 'Chờ thực hiện');

      stepperHtml += `
        <div class="stage-step-item ${itemClass}">
          <div class="stage-step-circle">${isDone ? '✓' : s.stage_order}</div>
          <div class="stage-step-content">
            <div class="stage-step-title">
              <span>${s.stage_name}</span>
              <span style="font-size:11px;font-weight:600;color:${isDone ? '#059669' : (isActive ? '#D97706' : '#9CA3AF')}">
                ${isDone ? 'ĐẠT' : (isActive ? 'ĐANG CHẠY' : 'CHỜ')}
              </span>
            </div>
            <div class="stage-step-time">${timeStr}</div>
            ${s.parameters_log ? `<div class="stage-step-param">${s.parameters_log}</div>` : ''}
          </div>
        </div>
      `;
    });
    stepperHtml += `</div>`;

    // Packaging section
    const pkg = batch.packaging || {};
    let packagingHtml = `
      <div style="margin-top:14px;padding:12px;background:#FFF;border:1px solid var(--border-subtle);border-radius:var(--radius-md);">
        <span style="font-size:12px;font-weight:700;color:var(--text-secondary);display:block;margin-bottom:8px;">
          GHI NHẬN ĐÓNG GÓI & HOÀN THIỆN
        </span>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div>
            <label style="font-size:11px;color:var(--text-muted);">Số thùng đã đóng</label>
            <input type="number" id="drawerCartonsUsed" value="${pkg.packages_completed || batch.target_quantity}" style="width:100%;padding:6px;border:1px solid var(--border-subtle);border-radius:4px;font-weight:700;">
          </div>
          <div>
            <label style="font-size:11px;color:var(--text-muted);">Cuộn màng seal</label>
            <input type="number" step="0.1" id="drawerSealRolls" value="${pkg.packaging_seal_rolls_used || 2.5}" style="width:100%;padding:6px;border:1px solid var(--border-subtle);border-radius:4px;">
          </div>
          <div>
            <label style="font-size:11px;color:var(--text-muted);">Phế phẩm hao hụt</label>
            <input type="number" id="drawerWasteCount" value="${pkg.waste_count || 12}" style="width:100%;padding:6px;border:1px solid var(--border-subtle);border-radius:4px;">
          </div>
          <div>
            <label style="font-size:11px;color:var(--text-muted);">Người kiểm tra</label>
            <input type="text" readonly value="${pkg.inspected_by || 'Tổ trưởng Đóng gói'}" style="width:100%;padding:6px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;">
          </div>
        </div>
      </div>
    `;

    fieldSlot.innerHTML = stepperHtml + packagingHtml;

    // Slot 3: Info List Slot (Consumed lots from Member 2)
    const infoSlot = document.getElementById('drawerInfoListSlot');
    const consumed = batch.consumed_materials || [];
    let consumedHtml = `
      <div class="infolist-container" style="margin-top:12px;">
        <div class="infolist-row-item" style="background:var(--bg-subtle);font-weight:700;">
          <span>Lô nguyên liệu tiêu hao (QC Approved)</span>
          <span>Số lượng đã trừ</span>
        </div>
        ${consumed.map(c => `
          <div class="infolist-row-item">
            <span><strong>${c.lot_number}</strong> (${c.material_name})</span>
            <span style="font-weight:700;color:var(--accent-navy);">${c.quantity_consumed} ${c.unit}</span>
          </div>
        `).join('') || '<div class="infolist-row-item"><span>Chưa ghi nhận lô tiêu hao</span></div>'}
        <div class="infolist-row-item">
          <span>Quản đốc phụ trách ca</span>
          <span>${batch.shift_manager}</span>
        </div>
        <div class="infolist-row-item">
          <span>Hạn sử dụng ghi trên bao bì</span>
          <span>${batch.expiry_date || 'N/A'}</span>
        </div>
      </div>
    `;
    infoSlot.innerHTML = consumedHtml;

    // Drawer footer button hook
    drawer.__controller = {
      save: () => submitPackagingRecord(batch.id)
    };

    drawer.classList.add('is-open');
    if (backdrop) backdrop.classList.add('is-visible');
  }

  async function advanceCurrentStage(batchId) {
    try {
      const resp = await fetch(`/api/production/batches/${batchId}/advance-stage`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
      });
      const data = await resp.json();
      if (data.success) {
        selectBatch(batchId);
        loadBatches();
      }
    } catch (e) {
      console.error("Failed to advance stage", e);
    }
  }

  async function submitPackagingRecord(batchId) {
    const cartons = document.getElementById('drawerCartonsUsed')?.value || 5000;
    const rolls = document.getElementById('drawerSealRolls')?.value || 2.5;
    const waste = document.getElementById('drawerWasteCount')?.value || 10;

    try {
      const resp = await fetch(`/api/production/batches/${batchId}/packaging`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          packages_completed: parseInt(cartons),
          carton_boxes_used: parseInt(cartons),
          packaging_seal_rolls_used: parseFloat(rolls),
          waste_count: parseInt(waste)
        })
      });
      const data = await resp.json();
      if (data.success) {
        FoodManApp.clearCardSelection();
        loadBatches();
        alert(data.message);
      }
    } catch (e) {
      console.error("Failed saving packaging record", e);
    }
  }

  // ---------------------------------------------------------------------------
  // 4. Batch Creation Wizard Controller
  // ---------------------------------------------------------------------------
  async function openWizard() {
    const panel = document.getElementById('batchWizardPanel');
    const backdrop = document.getElementById('wizardBackdrop');
    if (!panel) return;

    // Load produceable products into select
    try {
      const resp = await fetch('/api/production/recommendations');
      const data = await resp.json();
      if (data.success) {
        currentRecommendations = data.data;
        const select = document.getElementById('wizardProductSelect');
        select.innerHTML = '<option value="">-- Chọn thành phẩm cần sản xuất --</option>';
        data.data.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.product_id;
          opt.innerText = `${p.product_code} - ${p.product_name} (${p.readiness === 'PRODUCEABLE' ? 'ĐỦ NGUYÊN LIỆU' : 'THIẾU'})`;
          select.appendChild(opt);
        });
      }
    } catch (e) {
      console.error("Failed loading wizard products", e);
    }

    panel.classList.add('is-open');
    if (backdrop) backdrop.classList.add('is-visible');
  }

  function openWizardForProduct(productId) {
    openWizard();
    setTimeout(() => {
      const select = document.getElementById('wizardProductSelect');
      if (select) {
        select.value = productId;
        onWizardProductChange();
      }
    }, 200);
  }

  function closeWizard() {
    const panel = document.getElementById('batchWizardPanel');
    const backdrop = document.getElementById('wizardBackdrop');
    if (panel) panel.classList.remove('is-open');
    if (backdrop) backdrop.classList.remove('is-visible');
  }

  function onWizardProductChange() {
    const prodId = document.getElementById('wizardProductSelect')?.value;
    const container = document.getElementById('wizardBomAllocationList');
    if (!prodId || !container) return;

    const prod = currentRecommendations.find(p => p.product_id == prodId);
    if (!prod) return;

    let html = `
      <div style="font-size:12px;font-weight:700;margin-bottom:8px;color:var(--accent-navy);">
        Công thức: ${prod.recipe_code} (Định mức mẻ: ${prod.standard_yield.toLocaleString()} ${prod.yield_unit})
      </div>
    `;

    prod.bom_items.forEach(item => {
      const isPass = item.status === 'SUFFICIENT';
      html += `
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #E2E8F0;font-size:12px;">
          <span>• <strong>${item.material_name}</strong> (Cần: ${item.required_quantity} ${item.unit})</span>
          <span style="font-weight:700;color:${isPass ? '#059669' : '#DC2626'}">
            ${isPass ? `✓ Có sẵn ${item.available_approved_quantity} ${item.unit}` : `⚠ Thiếu (Có ${item.available_approved_quantity} ${item.unit})`}
          </span>
        </div>
      `;
    });

    container.innerHTML = html;
  }

  async function submitBatchCreation() {
    const prodId = document.getElementById('wizardProductSelect')?.value;
    const targetQty = document.getElementById('wizardTargetQty')?.value;
    const lineName = document.getElementById('wizardLineSelect')?.value;
    const notes = document.getElementById('wizardNotes')?.value;

    if (!prodId) {
      alert("Vui lòng chọn sản phẩm!");
      return;
    }

    try {
      const resp = await fetch('/api/production/batches', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          product_id: parseInt(prodId),
          target_quantity: parseFloat(targetQty),
          line_name: lineName,
          notes: notes
        })
      });
      const data = await resp.json();
      if (data.success) {
        closeWizard();
        loadBatches();
        alert(data.message);
      } else {
        alert("Lỗi khởi tạo: " + data.error);
      }
    } catch (e) {
      console.error("Failed creating batch", e);
    }
  }

  return {
    init,
    loadBatches,
    loadRecommendations,
    selectBatch,
    advanceCurrentStage,
    openWizard,
    openWizardForProduct,
    closeWizard,
    onWizardProductChange,
    submitBatchCreation
  };

})();

document.addEventListener('DOMContentLoaded', ProductionApp.init);
