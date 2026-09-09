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
      loadRecipes();
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

    if (countEl) countEl.innerText = `${items.length} Products evaluated against BOM vs QC Lots`;
    container.innerHTML = '';

    items.forEach(prod => {
      const isProduceable = prod.readiness === 'PRODUCEABLE';
      const pillClass = isProduceable ? 'pill-green' : 'pill-red';
      const pillLabel = isProduceable ? '✓ Ready to produce' : '⚠ Insufficient QC materials';

      let missingHtml = '';
      if (!isProduceable && prod.missing_materials.length > 0) {
        missingHtml = `
          <div style="margin-top:10px;padding:8px 10px;background:#FEF2F2;border-radius:6px;font-size:11.5px;color:#991B1B;">
            <strong>Materials below required QC threshold:</strong>
            ${prod.missing_materials.map(m => `<div>• ${m.material_name}: shortage ${m.shortage} ${m.unit}</div>`).join('')}
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
          <span class="card-secondary-stat">Standard Yield: ${prod.standard_yield.toLocaleString()} ${prod.yield_unit}</span>
        </div>

        <div class="card-minigrid" style="margin-top:10px;">
          <div class="minigrid-cell">
            <span class="minigrid-label">Category</span>
            <span class="minigrid-val">${prod.category}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Recipe (BOM)</span>
            <span class="minigrid-val">${prod.recipe_code}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Produceable Batches</span>
            <span class="minigrid-val" style="font-weight:700;color:${isProduceable ? '#059669' : '#DC2626'}">
              ${prod.max_batches_possible} Standard batches
            </span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">BOM Materials</span>
            <span class="minigrid-val">${prod.bom_items.length} Components</span>
          </div>
        </div>

        ${missingHtml}

        <div class="card-footer-row" style="margin-top:14px;">
          <button class="btn-primary-action" style="padding:6px 14px;font-size:12px;" onclick="ProductionApp.openWizardForProduct(${prod.product_id})">
            + Create Batch
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

    if (countEl) countEl.innerText = `${batches.length} Production batches active on lines`;
    container.innerHTML = '';

    batches.forEach(b => {
      const isComplete = b.status === 'COMPLETE';
      const statusPillClass = isComplete ? 'status-pill-approved' : 'status-pill-pending';
      const statusDotClass = isComplete ? 'dot-approved' : 'dot-pending';
      const statusLabel = isComplete ? 'Complete (COMPLETE)' : 'In Progress (IN_PROGRESS)';

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
          <span>Stage progress: ${b.current_stage}</span>
          <span>${b.progress}%</span>
        </div>

        <div class="card-minigrid">
          <div class="minigrid-cell">
            <span class="minigrid-label">Production Line</span>
            <span class="minigrid-val">${b.line_name}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Temperature Spec</span>
            <span class="minigrid-val">${b.temperature_spec}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Production Date</span>
            <span class="minigrid-val">${b.mfg_date || 'Today'}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Shelf Life / Expiry</span>
            <span class="minigrid-val">${b.expiry_date || '180 days'}</span>
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

    // Check if newly created batch was flagged
    if (sessionStorage.getItem('foodman_new_batch_created') === 'true') {
      sessionStorage.removeItem('foodman_new_batch_created');
      const firstCard = container.querySelector('.record-card');
      if (firstCard && window.FoodManAnimations) {
        window.FoodManAnimations.animateNewRecord(firstCard);
      }
    }
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
        <div style="font-size:12px;opacity:0.8;">PLANT PRODUCTION BATCH</div>
        <div style="font-size:16px;font-weight:800;margin-top:2px;">${batch.product_name}</div>
        <div style="font-size:12.5px;margin-top:8px;display:flex;justify-content:space-between;">
          <span>Quantity: <strong>${batch.actual_quantity.toLocaleString()} / ${batch.target_quantity.toLocaleString()} ${batch.unit}</strong></span>
          <span>Line: <strong>${batch.line_name}</strong></span>
        </div>
      </div>
    `;

    // Slot 2: Field Slot -> Stage Timeline Stepper & Packaging Form
    const fieldSlot = document.getElementById('drawerFieldSlot');
    const stages = batch.process_stages || [];

    let stepperHtml = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
        <span style="font-size:12px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;">
          PROCESS STAGES (TIMELINE STEPPER)
        </span>
        ${batch.status !== 'COMPLETE' ? `
          <button class="btn-primary-action" style="padding:4px 10px;font-size:11px;" onclick="ProductionApp.advanceCurrentStage(${batch.id})">
            Complete Stage ▶
          </button>
        ` : `<span style="font-size:11.5px;font-weight:700;color:#059669;">✓ All 5 stages completed</span>`}
      </div>
      <div class="stage-stepper-container">
    `;

    stages.forEach(s => {
      const isDone = s.status === 'COMPLETED';
      const isActive = s.status === 'IN_PROGRESS';
      const itemClass = isDone ? 'is-completed' : (isActive ? 'is-active' : '');
      const timeStr = isDone 
        ? `${s.started_at || ''} → ${s.ended_at || ''} (${s.duration_minutes || 0} mins)`
        : (isActive ? `Started: ${s.started_at || 'Just started'} • In Progress` : 'Pending');

      stepperHtml += `
        <div class="stage-step-item ${itemClass}">
          <div class="stage-step-circle">${isDone ? '✓' : s.stage_order}</div>
          <div class="stage-step-content">
            <div class="stage-step-title">
              <span>${s.stage_name}</span>
              <span style="font-size:11px;font-weight:600;color:${isDone ? '#059669' : (isActive ? '#D97706' : '#9CA3AF')}">
                ${isDone ? 'PASS' : (isActive ? 'RUNNING' : 'PENDING')}
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
          PACKAGING & FINISHING RECORD
        </span>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div>
            <label style="font-size:11px;color:var(--text-muted);">Cartons Packaged</label>
            <input type="number" id="drawerCartonsUsed" value="${pkg.packages_completed || batch.target_quantity}" style="width:100%;padding:6px;border:1px solid var(--border-subtle);border-radius:4px;font-weight:700;">
          </div>
          <div>
            <label style="font-size:11px;color:var(--text-muted);">Seal Film Rolls</label>
            <input type="number" step="0.1" id="drawerSealRolls" value="${pkg.packaging_seal_rolls_used || 2.5}" style="width:100%;padding:6px;border:1px solid var(--border-subtle);border-radius:4px;">
          </div>
          <div>
            <label style="font-size:11px;color:var(--text-muted);">Packaging Waste</label>
            <input type="number" id="drawerWasteCount" value="${pkg.waste_count || 12}" style="width:100%;padding:6px;border:1px solid var(--border-subtle);border-radius:4px;">
          </div>
          <div>
            <label style="font-size:11px;color:var(--text-muted);">Inspector</label>
            <input type="text" readonly value="${pkg.inspected_by || 'Packaging Lead'}" style="width:100%;padding:6px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;">
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
          <span>Consumed Material Lots (QC Approved)</span>
          <span>Quantity Deducted</span>
        </div>
        ${consumed.map(c => `
          <div class="infolist-row-item">
            <span><strong>${c.lot_number}</strong> (${c.material_name})</span>
            <span style="font-weight:700;color:var(--accent-navy);">${c.quantity_consumed} ${c.unit}</span>
          </div>
        `).join('') || '<div class="infolist-row-item"><span>No consumed lots recorded</span></div>'}
        <div class="infolist-row-item">
          <span>Shift Manager</span>
          <span>${batch.shift_manager}</span>
        </div>
        <div class="infolist-row-item">
          <span>Packaging Expiry Date</span>
          <span>${batch.expiry_date || 'N/A'}</span>
        </div>
      </div>

      <!-- Stage 5 AI Quality Control Gate Banner -->
      <div style="margin-top:14px;padding:12px;background:#EEF2FF;border:1px solid #C7D2FE;border-radius:8px;display:flex;align-items:center;justify-content:space-between;">
        <div>
          <div style="font-size:12px;font-weight:700;color:#4338CA;">STAGE 5: QUALITY CONTROL (AI INSPECTION)</div>
          <div style="font-size:11px;color:#6366F1;margin-top:2px;">YOLOv8 visual defect screening before warehouse release</div>
        </div>
        <a href="/qc?view=ai-inspection" class="btn-primary-action" style="font-size:11.5px;padding:6px 12px;background:#4F46E5;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">
          <span>Launch AI QC ➔</span>
        </a>
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
        select.innerHTML = '<option value="">-- Select finished product to produce --</option>';
        data.data.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.product_id;
          opt.innerText = `${p.product_code} - ${p.product_name} (${p.readiness === 'PRODUCEABLE' ? 'SUFFICIENT MATERIALS' : 'SHORTAGE'})`;
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
        Recipe: ${prod.recipe_code} (Standard yield: ${prod.standard_yield.toLocaleString()} ${prod.yield_unit})
      </div>
    `;

    prod.bom_items.forEach(item => {
      const isPass = item.status === 'SUFFICIENT';
      html += `
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #E2E8F0;font-size:12px;">
          <span>• <strong>${item.material_name}</strong> (Required: ${item.required_quantity} ${item.unit})</span>
          <span style="font-weight:700;color:${isPass ? '#059669' : '#DC2626'}">
            ${isPass ? `✓ Available ${item.available_approved_quantity} ${item.unit}` : `⚠ Shortage (Available ${item.available_approved_quantity} ${item.unit})`}
          </span>
        </div>
      `;
    });

    container.innerHTML = html;
  }

  async function submitBatchCreation() {
    const prodSelect = document.getElementById('wizardProductSelect');
    const prodId = prodSelect ? prodSelect.value : '';
    const targetQty = document.getElementById('wizardTargetQty')?.value;
    const lineName = document.getElementById('wizardLineSelect')?.value;
    const notes = document.getElementById('wizardNotes')?.value;

    if (!prodId) {
      if (window.FoodManAnimations) window.FoodManAnimations.shakeField(prodSelect);
      if (window.showToast) window.showToast("Validation Error", "Please select a product!", "danger");
      else alert("Please select a product!");
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
        sessionStorage.setItem('foodman_new_batch_created', 'true');
        if (window.showToast) window.showToast("Batch Created", data.message, "success");
        loadBatches();
      } else {
        if (window.showToast) window.showToast("Creation Error", data.error, "danger");
        else alert("Creation error: " + data.error);
      }
    } catch (e) {
      console.error("Failed creating batch", e);
    }
  }

  // ---------------------------------------------------------------------------
  // Recipe & BOM Management (Phase 3 Extensible CRUD)
  // ---------------------------------------------------------------------------
  let cachedRawMaterials = [];

  async function loadRecipes() {
    try {
      const resp = await fetch('/api/production/recipes');
      const data = await resp.json();
      if (data.success) {
        renderRecipes(data.data);
      }
    } catch (e) {
      console.error("Failed loading recipes", e);
    }
  }

  function renderRecipes(recipes) {
    const container = document.getElementById('productionCardGrid');
    const countEl = document.getElementById('totalRecordsCount');
    if (!container) return;

    if (countEl) countEl.innerText = `${recipes.length} Standard Recipes & Bill of Materials`;
    container.innerHTML = '';

    recipes.forEach(r => {
      const card = document.createElement('div');
      card.className = 'record-card';

      let bomRows = '';
      if (r.bom_items && r.bom_items.length > 0) {
        bomRows = r.bom_items.map(b => `
          <tr style="border-bottom:1px solid var(--border-subtle);">
            <td style="padding:6px 8px;font-weight:600;color:var(--text-main);">${b.raw_material_name}</td>
            <td style="padding:6px 8px;color:var(--text-secondary);">${b.raw_material_code}</td>
            <td style="padding:6px 8px;font-weight:700;color:var(--accent-navy);">${b.required_quantity} ${b.unit}</td>
            <td style="padding:6px 8px;color:var(--text-muted);">&plusmn;${b.tolerance_percent}%</td>
          </tr>
        `).join('');
      } else {
        bomRows = `<tr><td colspan="4" style="padding:10px;text-align:center;color:var(--text-muted);">No BOM ingredients registered yet.</td></tr>`;
      }

      card.innerHTML = `
        <div class="card-header-row">
          <div>
            <span class="card-id-badge" style="background:#EEF3FA;color:var(--accent-navy);">${r.recipe_code}</span>
            <span class="card-title-text" style="display:block;margin-top:4px;font-weight:700;font-size:14px;">${r.product_name}</span>
          </div>
          <span class="card-secondary-stat">Standard Yield: ${r.standard_batch_yield.toLocaleString()} ${r.yield_unit}</span>
        </div>

        <div style="margin-top:10px;font-size:12px;color:var(--text-secondary);">
          <strong>BOM Components (${r.bom_items.length}):</strong>
          <table style="width:100%;border-collapse:collapse;margin-top:6px;font-size:11.5px;">
            <thead>
              <tr style="background:#F8FAFC;border-bottom:1px solid var(--border-subtle);text-align:left;">
                <th style="padding:4px 8px;">Material</th>
                <th style="padding:4px 8px;">Code</th>
                <th style="padding:4px 8px;">Required Qty</th>
                <th style="padding:4px 8px;">Tolerance</th>
              </tr>
            </thead>
            <tbody>
              ${bomRows}
            </tbody>
          </table>
        </div>

        <div class="card-footer-row" style="margin-top:14px;">
          <button class="btn-primary-action" style="padding:6px 12px;font-size:11.5px;" onclick="ProductionApp.openIngredientModal(${r.id}, '${r.recipe_code} - ${r.product_name}')">
            + Add Ingredient
          </button>
        </div>
      `;
      container.appendChild(card);
    });
  }

  async function openIngredientModal(recipeId, recipeName) {
    document.getElementById('ingRecipeId').value = recipeId;
    document.getElementById('ingRecipeNameDisplay').value = recipeName;

    const select = document.getElementById('ingMaterialSelect');
    try {
      const resp = await fetch('/api/procurement/raw-materials');
      const data = await resp.json();
      cachedRawMaterials = data.data || [];
      select.innerHTML = cachedRawMaterials.map(m => `
        <option value="${m.id}" data-unit="${m.standard_unit || 'kg'}">${m.name} (${m.code}) - [${m.category}]</option>
      `).join('');
      onIngMaterialChange();
    } catch (e) {
      console.error("Failed loading raw materials", e);
    }

    document.getElementById('ingredientModalBackdrop')?.classList.add('show');
    document.getElementById('ingredientModalPanel')?.classList.add('open');
  }

  function closeIngredientModal() {
    document.getElementById('ingredientModalBackdrop')?.classList.remove('show');
    document.getElementById('ingredientModalPanel')?.classList.remove('open');
  }

  function onIngMaterialChange() {
    const select = document.getElementById('ingMaterialSelect');
    const selectedOpt = select.options[select.selectedIndex];
    const unit = selectedOpt ? selectedOpt.getAttribute('data-unit') || 'kg' : 'kg';
    document.getElementById('ingUnitDisplay').value = unit;
  }

  async function submitAddIngredient() {
    const recipeId = document.getElementById('ingRecipeId').value;
    const rawMaterialId = document.getElementById('ingMaterialSelect').value;
    const requiredQty = document.getElementById('ingRequiredQty').value;
    const unit = document.getElementById('ingUnitDisplay').value;
    const tolerance = document.getElementById('ingTolerance').value;

    if (!rawMaterialId || !requiredQty) {
      alert("Please fill in required fields!");
      return;
    }

    try {
      const resp = await fetch(`/api/production/recipes/${recipeId}/ingredients`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          raw_material_id: parseInt(rawMaterialId),
          required_quantity: parseFloat(requiredQty),
          unit: unit,
          tolerance_percent: parseFloat(tolerance)
        })
      });
      const data = await resp.json();
      if (data.success) {
        closeIngredientModal();
        loadRecipes();
        alert(data.message);
      } else {
        alert("Error: " + data.error);
      }
    } catch (e) {
      console.error("Failed adding ingredient", e);
    }
  }

  async function openRecipeModal() {
    const select = document.getElementById('newRecipeProductSelect');
    try {
      const resp = await fetch('/api/production/recommendations');
      const data = await resp.json();
      const prods = data.data || [];
      select.innerHTML = prods.map(p => `
        <option value="${p.product_id}">${p.product_name} (${p.product_code})</option>
      `).join('');
    } catch (e) {
      console.error("Failed loading products", e);
    }
    document.getElementById('recipeModalBackdrop')?.classList.add('show');
    document.getElementById('recipeModalPanel')?.classList.add('open');
  }

  function closeRecipeModal() {
    document.getElementById('recipeModalBackdrop')?.classList.remove('show');
    document.getElementById('recipeModalPanel')?.classList.remove('open');
  }

  async function submitCreateRecipe() {
    const productId = document.getElementById('newRecipeProductSelect').value;
    const code = document.getElementById('newRecipeCode').value.trim();
    const version = document.getElementById('newRecipeVersion').value.trim();
    const yieldQty = document.getElementById('newRecipeYield').value;
    const yieldUnit = document.getElementById('newRecipeYieldUnit').value;
    const notes = document.getElementById('newRecipeNotes').value;

    if (!productId) {
      alert("Please select a product!");
      return;
    }

    try {
      const resp = await fetch('/api/production/recipes', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          product_id: parseInt(productId),
          recipe_code: code || undefined,
          version: version,
          standard_batch_yield: parseFloat(yieldQty) || 1000,
          yield_unit: yieldUnit,
          notes: notes
        })
      });
      const data = await resp.json();
      if (data.success) {
        closeRecipeModal();
        loadRecipes();
        alert(data.message);
      } else {
        alert("Error: " + data.error);
      }
    } catch (e) {
      console.error("Failed creating recipe", e);
    }
  }

  return {
    init,
    loadBatches,
    loadRecommendations,
    loadRecipes,
    selectBatch,
    advanceCurrentStage,
    openWizard,
    openWizardForProduct,
    closeWizard,
    onWizardProductChange,
    submitBatchCreation,
    openIngredientModal,
    closeIngredientModal,
    onIngMaterialChange,
    submitAddIngredient,
    openRecipeModal,
    closeRecipeModal,
    submitCreateRecipe
  };

})();

document.addEventListener('DOMContentLoaded', ProductionApp.init);
