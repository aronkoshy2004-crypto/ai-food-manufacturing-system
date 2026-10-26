/**
 * FOOD MAN - PROCUREMENT MODULE CONTROLLER
 * Handles:
 * - Raw Material Lots, Suppliers, Raw Materials, Purchase Orders, Goods Receipts
 * - Multi-line PO builder modal
 * - GRN intake modal -> triggers auto-lot generation with qc_status = PENDING_QC
 * - Master-detail drawer interactions
 * - Live sidebar badge update
 */

const ProcurementModule = (() => {
  let activeView = 'lots';
  let currentItems = [];
  let suppliersList = [];
  let materialsList = [];
  let posList = [];
  let poItemRowCount = 0;
  let drawer = null;
  let showInactive = false;
  let currentStatusFilter = 'ALL';
  let currentSearchKeyword = '';

  function init(view) {
    activeView = view || 'lots';
    drawer = new FoodManComponents.DetailDrawerController('detailDrawerRoot', 'drawerBackdrop');
    
    // Register card handler with FoodManApp so clicking any card routes properly
    if (typeof FoodManApp !== 'undefined' && typeof FoodManApp.registerCardHandler === 'function') {
      FoodManApp.registerCardHandler((cardId) => {
        return selectCard(cardId);
      });
    }

    setupFilterTabs();
    setupSearch();
    loadAuxiliaryData();
    loadViewData(activeView);
    updatePendingQcBadge();
  }

  function toggleShowInactive(show) {
    showInactive = !!show;
    filterAndRenderCards(currentStatusFilter, currentSearchKeyword);
  }

  function setupFilterTabs() {
    document.querySelectorAll('.tab-pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentStatusFilter = btn.dataset.status;
        filterAndRenderCards(currentStatusFilter, currentSearchKeyword);
      });
    });
  }

  function setupSearch() {
    const searchInput = document.getElementById('globalSearchInput') || document.getElementById('topbarSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        currentSearchKeyword = e.target.value.toLowerCase().trim();
        filterAndRenderCards(currentStatusFilter, currentSearchKeyword);
      });
    }
  }

  async function loadAuxiliaryData() {
    try {
      const [supRes, matRes, poRes] = await Promise.all([
        fetch('/api/procurement/suppliers?active_only=true'),
        fetch('/api/procurement/raw-materials?active_only=true'),
        fetch('/api/procurement/purchase-orders')
      ]);
      suppliersList = (await supRes.json()).data || [];
      materialsList = (await matRes.json()).data || [];
      posList = (await poRes.json()).data || [];
    } catch (e) {
      console.warn("Could not load auxiliary procurement data", e);
    }
  }

  async function updatePendingQcBadge() {
    try {
      const res = await fetch('/api/procurement/stats');
      if (res.ok) {
        const stats = await res.json();
        const badge = document.getElementById('sidebarPendingQcBadge');
        if (badge) badge.textContent = stats.pending_qc_lots || 0;
      }
    } catch (e) {}
  }

  async function loadViewData(view) {
    const container = document.getElementById('procurementCardsContainer');
    container.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
        Loading ${view} data...
      </div>
    `;

    try {
      let url = '/api/procurement/lots';
      if (view === 'suppliers') url = '/api/procurement/suppliers';
      else if (view === 'raw-materials') url = '/api/procurement/raw-materials';
      else if (view === 'po') url = '/api/procurement/purchase-orders';
      else if (view === 'grn') url = '/api/procurement/grn';

      const res = await fetch(url);
      if (!res.ok) throw new Error("Error loading data");
      const json = await res.json();

      if (view === 'lots') {
        currentItems = json.cards || [];
        if (typeof FoodManApp !== 'undefined' && typeof FoodManApp.setCards === 'function') {
          FoodManApp.setCards(currentItems);
        }
      } else {
        currentItems = json.data || [];
      }

      const countBadge = document.getElementById('procurementCountBadge');
      if (countBadge) countBadge.textContent = `${currentItems.length} records`;

      filterAndRenderCards('ALL');

      // Direct drawer opening from Global Search
      const urlParams = new URLSearchParams(window.location.search);
      const openParam = urlParams.get('open');
      if (openParam) {
        setTimeout(() => {
          if (view === 'po') {
            const p = currentItems.find(item => String(item.id) === String(openParam) || item.po_number === openParam);
            if (p) selectPo(p.id);
          } else if (view === 'grn') {
            const g = currentItems.find(item => String(item.id) === String(openParam) || item.grn_number === openParam);
            if (g) selectGrn(g.id);
          } else {
            selectCard(openParam);
          }
        }, 150);
      }
    } catch (err) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #DC2626;">
          Failed to load data: ${err.message}
        </div>
      `;
    }
  }

  function filterAndRenderCards(statusFilter, searchKeyword) {
    const container = document.getElementById('procurementCardsContainer');
    if (!container) return;

    if (statusFilter !== undefined && statusFilter !== null) currentStatusFilter = statusFilter;
    if (searchKeyword !== undefined && searchKeyword !== null) currentSearchKeyword = searchKeyword;

    let filtered = [...currentItems];

    // Status filter
    if (currentStatusFilter && currentStatusFilter !== 'ALL') {
      filtered = filtered.filter(item => (item.qc_status || item.status) === currentStatusFilter);
    }

    // Keyword filter
    if (currentSearchKeyword) {
      filtered = filtered.filter(item => {
        const str = `${item.id || ''} ${item.code || ''} ${item.name || ''} ${item.title || ''} ${item.po_number || ''} ${item.grn_number || ''}`.toLowerCase();
        return str.includes(currentSearchKeyword);
      });
    }

    // Inactive filter for suppliers and raw-materials
    if ((activeView === 'suppliers' || activeView === 'raw-materials') && !showInactive) {
      filtered = filtered.filter(item => item.is_active !== false);
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--border-subtle);">
          <div style="font-size: 15px; font-weight: 700; color: var(--text-main);">No matching records found</div>
          <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">Please create a new entry or adjust your search filters.</div>
        </div>
      `;
      return;
    }

    if (activeView === 'lots') {
      if (typeof FoodManApp !== 'undefined' && typeof FoodManApp.setCards === 'function') {
        FoodManApp.setCards(filtered);
      }
      container.innerHTML = filtered.map(card => FoodManComponents.RecordCard({
        ...card,
        onclick: `ProcurementModule.selectLot('${card.id}')`
      })).join('');
    } else if (activeView === 'suppliers') {
      container.innerHTML = filtered.map(s => renderSupplierCard(s)).join('');
    } else if (activeView === 'raw-materials') {
      container.innerHTML = filtered.map(m => renderRawMaterialCard(m)).join('');
    } else if (activeView === 'po') {
      container.innerHTML = filtered.map(p => renderPurchaseOrderCard(p)).join('');
    } else if (activeView === 'grn') {
      container.innerHTML = filtered.map(g => renderGrnCard(g)).join('');
    }

    // Trigger subtle entrance animation for newly created record if flagged
    if (sessionStorage.getItem('foodman_highlight_first_card') === 'true') {
      sessionStorage.removeItem('foodman_highlight_first_card');
      const firstCard = container.querySelector('.record-card-box');
      if (firstCard && window.FoodManAnimations) {
        window.FoodManAnimations.animateNewRecord(firstCard);
      }
    }
  }

  // Card renderers for procurement views
  function renderSupplierCard(s) {
    const isInactive = s.is_active === false;
    return `
      <div class="record-card-box ${isInactive ? 'card-inactive' : ''}" style="${isInactive ? 'opacity:0.85;border:1px dashed #94A3B8;' : ''}" onclick="ProcurementModule.selectSupplier(${s.id})">
        <div class="card-top-row">
          <div class="card-title-col">
            <div>
              <span class="card-id-badge">${s.code}</span>
              <span class="card-category-sub">Supplier</span>
              ${isInactive ? '<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#EF4444;color:#FFF;font-weight:700;margin-left:6px;">INACTIVE</span>' : ''}
            </div>
            <h3 class="card-main-title">${s.name}</h3>
          </div>
          <div class="card-stat-widget">
            <span class="card-stat-number">${s.rating} ★</span>
            <span class="card-stat-caption">Rating</span>
          </div>
        </div>
        <div class="card-mini-grid-layout">
          <div class="grid-cell-item"><span class="cell-label-text">Contact Person</span><span class="cell-value-text">${s.contact_name || 'N/A'}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Phone</span><span class="cell-value-text">${s.phone || 'N/A'}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Email</span><span class="cell-value-text">${s.email || 'N/A'}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Address</span><span class="cell-value-text">${s.address || 'N/A'}</span></div>
        </div>
        <div class="card-footer-slot">
          <div class="avatar-stack-slot"><div class="avatar-stack-disc" style="background:#162B4E;">SUP</div></div>
          ${isInactive 
            ? FoodManComponents.StatusPill("HOLD", "Deactivated")
            : FoodManComponents.StatusPill("APPROVED", "Verified Partner")}
        </div>
      </div>
    `;
  }

  function renderRawMaterialCard(m) {
    const isInactive = m.is_active === false;
    return `
      <div class="record-card-box ${isInactive ? 'card-inactive' : ''}" style="${isInactive ? 'opacity:0.85;border:1px dashed #94A3B8;' : ''}" onclick="ProcurementModule.selectRawMaterial(${m.id})">
        <div class="card-top-row">
          <div class="card-title-col">
            <div>
              <span class="card-id-badge">${m.code}</span>
              <span class="card-category-sub">${m.category}</span>
              ${isInactive ? '<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#EF4444;color:#FFF;font-weight:700;margin-left:6px;">INACTIVE</span>' : ''}
            </div>
            <h3 class="card-main-title">${m.name}</h3>
          </div>
          <div class="card-stat-widget">
            <span class="card-stat-number">${m.standard_unit}</span>
            <span class="card-stat-caption">Standard Unit</span>
          </div>
        </div>
        <div class="card-mini-grid-layout">
          <div class="grid-cell-item"><span class="cell-label-text">Packaging Spec</span><span class="cell-value-text">${m.unit_weight || 'Standard'}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Storage Condition</span><span class="cell-value-text">${m.storage_temp || 'Ambient'}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Shelf Life</span><span class="cell-value-text">${m.shelf_life_days} days</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Min Stock Level</span><span class="cell-value-text">${m.min_stock_level} ${m.standard_unit}</span></div>
        </div>
        <div class="card-footer-slot">
          <div class="avatar-stack-slot"><div class="avatar-stack-disc" style="background:#0D9488;">RM</div></div>
          ${isInactive 
            ? FoodManComponents.StatusPill("HOLD", "Deactivated")
            : FoodManComponents.StatusPill("APPROVED", "Active")}
        </div>
      </div>
    `;
  }

  function renderPurchaseOrderCard(p) {
    const itemsPreview = (p.items || []).map(i => `${i.material_name}: ${i.quantity_ordered} ${i.unit}`).join(', ');
    const isCancelled = p.status === 'CANCELLED';
    return `
      <div class="record-card-box ${isCancelled ? 'card-inactive' : ''}" style="${isCancelled ? 'opacity:0.75;' : ''}" onclick="ProcurementModule.selectPo(${p.id})">
        <div class="card-top-row">
          <div class="card-title-col">
            <div>
              <span class="card-id-badge">${p.po_number}</span>
              <span class="card-category-sub">Purchase Order</span>
              ${isCancelled ? '<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:#EF4444;color:#FFF;font-weight:700;margin-left:6px;">VOIDED</span>' : ''}
            </div>
            <h3 class="card-main-title">${p.supplier_name}</h3>
          </div>
          <div class="card-stat-widget">
            <span class="card-stat-number">${(p.total_amount || 0).toLocaleString()} VND</span>
            <span class="card-stat-caption">${p.items_count || (p.items ? p.items.length : 0)} items</span>
          </div>
        </div>
        <div class="card-mini-grid-layout">
          <div class="grid-cell-item"><span class="cell-label-text">Order Date</span><span class="cell-value-text">${p.order_date}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Expected Delivery</span><span class="cell-value-text">${p.expected_delivery_date}</span></div>
          <div class="grid-cell-item" style="grid-column:1/-1;"><span class="cell-label-text">Line Items Detail</span><span class="cell-value-text">${itemsPreview || 'No line items'}</span></div>
        </div>
        <div class="card-footer-slot">
          <div class="avatar-stack-slot"><div class="avatar-stack-disc" style="background:#2563EB;">PO</div></div>
          ${FoodManComponents.StatusPill(
            p.status === 'COMPLETED' ? 'APPROVED' : (isCancelled ? 'REJECTED' : 'PENDING'), 
            p.status === 'COMPLETED' ? 'Fully Received' : (isCancelled ? 'Voided' : 'In Progress')
          )}
        </div>
      </div>
    `;
  }

  function renderGrnCard(g) {
    return `
      <div class="record-card-box" onclick="ProcurementModule.selectGrn(${g.id})">
        <div class="card-top-row">
          <div class="card-title-col">
            <div><span class="card-id-badge">${g.grn_number}</span><span class="card-category-sub">Goods Receipt Note</span></div>
            <h3 class="card-main-title">${g.supplier_name}</h3>
          </div>
          <div class="card-stat-widget">
            <span class="card-stat-number">${g.items_count} items</span>
            <span class="card-stat-caption">Received Items</span>
          </div>
        </div>
        <div class="card-mini-grid-layout">
          <div class="grid-cell-item"><span class="cell-label-text">Purchase Order</span><span class="cell-value-text">${g.po_number}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Receipt Timestamp</span><span class="cell-value-text">${g.received_date}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Truck Plate</span><span class="cell-value-text">${g.truck_plate}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Waybill / Delivery Note</span><span class="cell-value-text">${g.delivery_note_ref}</span></div>
        </div>
        <div class="card-footer-slot">
          <div class="avatar-stack-slot"><div class="avatar-stack-disc" style="background:#059669;">GRN</div></div>
          ${FoodManComponents.StatusPill("APPROVED", "QC Lots Generated")}
        </div>
      </div>
    `;
  }

  // Generalized selectCard delegator
  function selectCard(cardId) {
    if (activeView === 'lots') {
      selectLot(cardId);
      return true;
    }
    return false;
  }

  // Detail Drawer: Lot Selection
  function selectLot(cardOrId) {
    let card = null;
    if (typeof cardOrId === 'object' && cardOrId !== null) {
      card = cardOrId;
    } else {
      card = currentItems.find(item => item.id === cardOrId || item.db_id === parseInt(cardOrId));
    }
    if (!card) return;

    const customActions = [];
    if (card.qc_status === 'PENDING_QC') {
      customActions.push({
        label: "Open Inspection Lab →",
        class: "btn-primary",
        style: "background:#0D9488;color:#FFF;",
        onClick: () => {
          window.location.href = `/qc?view=queue`;
        }
      });
    }

    const poRef = card.readonlySpecs && card.readonlySpecs[0] ? card.readonlySpecs[0].value : 'Direct Intake';
    const grnRef = card.readonlySpecs && card.readonlySpecs[1] ? card.readonlySpecs[1].value : 'Standard GRN';
    const supName = card.supplier_name || (card.miniGrid && card.miniGrid[1] ? card.miniGrid[1].value : 'Approved Supplier');

    drawer.open({
      id: card.id,
      db_id: card.db_id,
      title: card.title,
      category: "RAW MATERIAL LOT",
      headerStat: card.headerStat,
      statSub: card.statSub || "Intake Quantity",
      status: card.status,
      statusLabel: card.statusLabel,
      statusPill: card.statusPill,
      editableFields: card.editableFields || [
        { label: "Material Name", key: "material_name", type: "text", value: card.title },
        { label: "Unit of Measure", key: "unit", type: "text", value: "Tons" },
        { label: "Storage Condition", key: "storage_condition", type: "text", value: "Cold Storage 4-6°C" }
      ],
      readonlySpecs: [
        { label: "Lot Number", value: card.id, mono: true },
        { label: "Raw Material", value: card.title },
        { label: "Supplier", value: supName },
        { label: "Quantity", value: card.headerStat },
        { label: "QC Status", value: card.qc_status },
        { label: "Linked Purchase Order", value: poRef, mono: true },
        { label: "Linked Goods Receipt (GRN)", value: grnRef, mono: true }
      ],
      customActions: customActions
    }, async (item, newStatus) => {
      const matName = document.getElementById('drawer_input_material_name')?.value;
      const supName = document.getElementById('drawer_input_supplier_name')?.value;
      const unit = document.getElementById('drawer_input_unit')?.value;
      const storage = document.getElementById('drawer_input_storage_condition')?.value;

      try {
        const res = await fetch(`/api/procurement/lots/${card.db_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            material_name: matName,
            supplier_name: supName,
            unit: unit,
            storage_condition: storage,
            qc_status: newStatus
          })
        });
        if (!res.ok) throw new Error("Update failed");
        drawer.close();
        loadViewData('lots');
        updatePendingQcBadge();
        if (window.showToast) window.showToast("Success", `Updated lot ${card.id}`, "success");
        else alert(`Successfully updated lot ${card.id}`);
      } catch (err) {
        if (window.showToast) window.showToast("Error", err.message, "danger");
        else alert(err.message);
      }
    });
  }

  // Detail Drawer: Purchase Order Selection
  function selectPo(id) {
    const p = currentItems.find(item => item.id === id);
    if (!p) return;

    const items = p.items || [];
    const grns = p.goods_receipts || [];

    const itemsTableHtml = `
      <div style="font-size:12px;font-weight:700;margin-top:14px;margin-bottom:6px;color:var(--text-secondary);text-transform:uppercase;">
        Order Line Items (${items.length})
      </div>
      <div style="border:1px solid var(--border-subtle);border-radius:8px;overflow:hidden;background:#FFF;">
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
          <thead>
            <tr style="background:#F8FAFC;border-bottom:1px solid var(--border-subtle);color:var(--text-muted);text-align:left;">
              <th style="padding:8px 10px;">Material</th>
              <th style="padding:8px 10px;text-align:right;">Ordered</th>
              <th style="padding:8px 10px;text-align:right;">Received</th>
              <th style="padding:8px 10px;text-align:right;">Unit Price</th>
              <th style="padding:8px 10px;text-align:right;">Line Total</th>
            </tr>
          </thead>
          <tbody>
            ${items.length === 0 ? '<tr><td colspan="5" style="padding:12px;text-align:center;color:var(--text-muted);">No line items</td></tr>' : ''}
            ${items.map(it => `
              <tr style="border-bottom:1px solid var(--border-subtle);">
                <td style="padding:8px 10px;font-weight:600;color:var(--text-main);">${it.material_name}</td>
                <td style="padding:8px 10px;text-align:right;">${it.quantity_ordered} ${it.unit}</td>
                <td style="padding:8px 10px;text-align:right;color:${it.quantity_received >= it.quantity_ordered ? '#059669' : '#D97706'};font-weight:600;">${it.quantity_received} ${it.unit}</td>
                <td style="padding:8px 10px;text-align:right;font-family:'JetBrains Mono',monospace;">${(it.unit_price || 0).toLocaleString()} VND</td>
                <td style="padding:8px 10px;text-align:right;font-weight:700;font-family:'JetBrains Mono',monospace;color:var(--accent-navy);">${(it.subtotal || (it.quantity_ordered * it.unit_price) || 0).toLocaleString()} VND</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

    const grnsHtml = `
      <div style="font-size:12px;font-weight:700;margin-top:14px;margin-bottom:6px;color:var(--text-secondary);text-transform:uppercase;">
        Linked Goods Receipts (GRN)
      </div>
      <div style="border:1px solid var(--border-subtle);border-radius:8px;padding:10px;background:#F8FAFC;">
        ${grns.length === 0 
          ? '<div style="font-size:12px;color:var(--text-muted);text-align:center;padding:8px;">No Goods Receipts recorded against this PO yet.</div>'
          : grns.map(g => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px dashed var(--border-subtle);font-size:12px;">
                <div>
                  <strong style="color:var(--accent-navy);">${g.grn_number}</strong>
                  <span style="color:var(--text-muted);margin-left:6px;">${g.received_date}</span>
                </div>
                <div style="display:flex;gap:8px;align-items:center;">
                  <span style="font-size:11px;font-weight:600;">${g.items_count} items</span>
                  <span class="status-pill status-pill-approved" style="font-size:10px;padding:2px 6px;">${g.status}</span>
                </div>
              </div>
            `).join('')
        }
      </div>
    `;

    const customActions = [];

    // Role-allowed action: "Receive goods (create GRN)"
    if (p.status !== 'CANCELLED' && p.status !== 'COMPLETED') {
      customActions.push({
        label: "Receive goods (create GRN)",
        class: "btn-primary",
        style: "background:#059669;color:#FFF;",
        onClick: () => {
          drawer.close();
          window.openGrnModal(p.id);
        }
      });
    }

    // Void button for draft/pending orders
    if (p.status === 'PENDING' || p.status === 'DRAFT' || (p.status === 'APPROVED' && grns.length === 0)) {
      customActions.push({
        label: "Void Order",
        class: "btn-danger",
        style: "background:#DC2626;color:#FFF;",
        onClick: async (e) => {
          if (!confirm(`Are you sure you want to VOID Purchase Order ${p.po_number}? This action cannot be undone.`)) {
            return;
          }
          const btn = e.target;
          if (btn) { btn.disabled = true; btn.innerText = "Voiding..."; }
          try {
            const resp = await fetch(`/api/procurement/purchase-orders/${p.id}/void`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) {
              throw new Error(data.error || "Failed to void purchase order");
            }
            drawer.close();
            if (window.showToast) window.showToast("Order Voided", data.message, "success");
            else alert(data.message);
            loadViewData('po');
          } catch (err) {
            if (btn) { btn.disabled = false; btn.innerText = "Void Order"; }
            if (window.showToast) window.showToast("Error", err.message, "danger");
            else alert("Error: " + err.message);
          }
        }
      });
    }

    drawer.open({
      id: p.po_number,
      title: p.supplier_name,
      category: "PURCHASE ORDER",
      headerStat: `${(p.total_amount || 0).toLocaleString()} VND`,
      statSub: `Total Amount (${p.currency || 'VND'})`,
      status: p.status,
      statusLabel: p.status,
      statusPill: p.status === 'COMPLETED' ? 'pill-approved' : (p.status === 'CANCELLED' ? 'pill-rejected' : 'pill-pending'),
      readonlySpecs: [
        { label: "Purchase Order #", value: p.po_number, mono: true },
        { label: "Supplier", value: p.supplier_name },
        { label: "Order Date", value: p.order_date },
        { label: "Expected Delivery", value: p.expected_delivery_date },
        { label: "Fulfillment Status", value: p.status },
        { label: "Total Order Value", value: `${(p.total_amount || 0).toLocaleString()} ${p.currency || 'VND'}` }
      ],
      customContentHtml: itemsTableHtml + grnsHtml,
      customActions: customActions
    });
  }

  // Detail Drawer: Goods Receipt Selection
  function selectGrn(id) {
    const g = currentItems.find(item => item.id === id);
    if (!g) return;

    const items = g.items || [];
    const lots = g.lots || [];

    const itemsHtml = `
      <div style="font-size:12px;font-weight:700;margin-top:14px;margin-bottom:6px;color:var(--text-secondary);text-transform:uppercase;">
        Received Line Items (${items.length})
      </div>
      <div style="border:1px solid var(--border-subtle);border-radius:8px;overflow:hidden;background:#FFF;">
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
          <thead>
            <tr style="background:#F8FAFC;border-bottom:1px solid var(--border-subtle);color:var(--text-muted);text-align:left;">
              <th style="padding:8px 10px;">Raw Material</th>
              <th style="padding:8px 10px;text-align:right;">Quantity</th>
              <th style="padding:8px 10px;">Unit / Spec</th>
            </tr>
          </thead>
          <tbody>
            ${items.length === 0 ? '<tr><td colspan="3" style="padding:12px;text-align:center;color:var(--text-muted);">No items recorded</td></tr>' : ''}
            ${items.map(it => `
              <tr style="border-bottom:1px solid var(--border-subtle);">
                <td style="padding:8px 10px;font-weight:600;color:var(--text-main);">${it.material_name}</td>
                <td style="padding:8px 10px;text-align:right;font-weight:700;color:var(--accent-navy);">${it.quantity_received}</td>
                <td style="padding:8px 10px;color:var(--text-muted);">${it.unit} (${it.unit_weight || 'Standard spec'})</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

    const lotsHtml = `
      <div style="font-size:12px;font-weight:700;margin-top:14px;margin-bottom:6px;color:var(--text-secondary);text-transform:uppercase;">
        Auto-Generated QC Lots (${lots.length})
      </div>
      <div style="border:1px solid var(--border-subtle);border-radius:8px;padding:10px;background:#F8FAFC;">
        ${lots.length === 0
          ? '<div style="font-size:12px;color:var(--text-muted);text-align:center;padding:8px;">No QC lots linked to this GRN.</div>'
          : lots.map(l => {
              const isApproved = l.qc_status === 'APPROVED';
              const isPending = l.qc_status === 'PENDING_QC';
              const pillColor = isApproved ? '#059669' : (isPending ? '#D97706' : '#DC2626');
              return `
                <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px dashed var(--border-subtle);font-size:12px;">
                  <div>
                    <strong style="color:var(--accent-navy);font-family:'JetBrains Mono',monospace;">${l.lot_number}</strong>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">${l.material_name} • ${l.quantity} ${l.unit}</div>
                  </div>
                  <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;color:#FFF;background:${pillColor};">${l.qc_status}</span>
                    <a href="/qc?view=queue" style="font-size:11px;color:var(--accent-navy);font-weight:700;text-decoration:none;padding:3px 8px;background:#FFF;border:1px solid var(--border-subtle);border-radius:4px;">QC Lab →</a>
                  </div>
                </div>
              `;
            }).join('')
        }
      </div>
    `;

    const customActions = [
      {
        label: "Print GRN Dossier",
        class: "btn-secondary",
        style: "background:#1E293B;color:#FFF;",
        onClick: () => {
          window.print();
        }
      }
    ];

    drawer.open({
      id: g.grn_number,
      title: g.supplier_name,
      category: "GOODS RECEIPT NOTE",
      headerStat: `${g.items_count} items`,
      statSub: "Received Intake",
      status: g.status,
      statusLabel: "QC Lots Generated",
      statusPill: "pill-approved",
      readonlySpecs: [
        { label: "GRN Number", value: g.grn_number, mono: true },
        { label: "Purchase Order", value: g.po_number, mono: true },
        { label: "Supplier", value: g.supplier_name },
        { label: "Receipt Timestamp", value: g.received_date },
        { label: "Waybill / Delivery Ref", value: g.delivery_note_ref },
        { label: "Truck License Plate", value: g.truck_plate },
        { label: "Receiving Custodian", value: g.receiver || "Warehouse Team" }
      ],
      customContentHtml: itemsHtml + lotsHtml,
      customActions: customActions
    });
  }

  // Detail Drawer: Supplier Selection with Soft Deactivation
  function selectSupplier(id) {
    const s = currentItems.find(item => item.id === id);
    if (!s) return;

    const isInactive = s.is_active === false;
    const customActions = [];

    if (isInactive) {
      customActions.push({
        label: "Reactivate Supplier",
        class: "btn-primary",
        style: "background:#059669;color:#FFF;",
        onClick: async (e) => {
          if (!confirm(`Are you sure you want to REACTIVATE supplier '${s.name}'?`)) return;
          const btn = e.target;
          if (btn) { btn.disabled = true; btn.innerText = "Reactivating..."; }
          try {
            const resp = await fetch(`/api/procurement/suppliers/${s.id}/reactivate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) throw new Error(data.error || "Failed to reactivate supplier");
            drawer.close();
            if (window.showToast) window.showToast("Reactivated", data.message, "success");
            else alert(data.message);
            loadViewData('suppliers');
            loadAuxiliaryData();
          } catch (err) {
            if (btn) { btn.disabled = false; btn.innerText = "Reactivate Supplier"; }
            if (window.showToast) window.showToast("Error", err.message, "danger");
            else alert("Error: " + err.message);
          }
        }
      });
    } else {
      customActions.push({
        label: "Deactivate Supplier",
        class: "btn-danger",
        style: "background:#DC2626;color:#FFF;",
        onClick: async (e) => {
          if (!confirm(`Are you sure you want to DEACTIVATE supplier '${s.name}'? Inactive suppliers will not appear in new purchase orders.`)) return;
          const btn = e.target;
          if (btn) { btn.disabled = true; btn.innerText = "Deactivating..."; }
          try {
            const resp = await fetch(`/api/procurement/suppliers/${s.id}/deactivate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) throw new Error(data.error || "Failed to deactivate supplier");
            drawer.close();
            if (window.showToast) window.showToast("Deactivated", data.message, "success");
            else alert(data.message);
            loadViewData('suppliers');
            loadAuxiliaryData();
          } catch (err) {
            if (btn) { btn.disabled = false; btn.innerText = "Deactivate Supplier"; }
            if (window.showToast) window.showToast("Error", err.message, "danger");
            else alert("Error: " + err.message);
          }
        }
      });
    }

    drawer.open({
      id: s.code,
      title: s.name,
      category: isInactive ? "INACTIVE SUPPLIER" : "SUPPLIER",
      headerStat: `${s.rating} ★`,
      statSub: isInactive ? "Status: Deactivated" : "Reputation Rating",
      editableFields: [
        { label: "Supplier Name", key: "name", type: "text", value: s.name },
        { label: "Contact Person", key: "contact_name", type: "text", value: s.contact_name },
        { label: "Phone Number", key: "phone", type: "text", value: s.phone },
        { label: "Email", key: "email", type: "text", value: s.email }
      ],
      readonlySpecs: [
        { label: "Headquarters Address", value: s.address },
        { label: "Total Orders Signed", value: `${s.po_count || 0} POs` },
        { label: "Account Status", value: isInactive ? "INACTIVE (Soft Deactivated)" : "ACTIVE (Verified Partner)" },
        { label: "Quality Certification", value: "HACCP & ISO 22000 Approved" }
      ],
      customActions: customActions
    }, async (item) => {
      const name = document.getElementById('drawer_input_name')?.value;
      const contact = document.getElementById('drawer_input_contact_name')?.value;
      const phone = document.getElementById('drawer_input_phone')?.value;
      const email = document.getElementById('drawer_input_email')?.value;

      try {
        const resp = await fetch(`/api/procurement/suppliers/${s.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, contact_name: contact, phone, email })
        });
        const resData = await resp.json();
        if (!resp.ok) throw new Error(resData.error || "Update failed");
        drawer.close();
        if (window.showToast) window.showToast("Success", "Supplier updated successfully", "success");
        loadViewData('suppliers');
        loadAuxiliaryData();
      } catch (err) {
        if (window.showToast) window.showToast("Error", err.message, "danger");
        else alert("Error: " + err.message);
      }
    });
  }

  // Detail Drawer: Raw Material Selection with Soft Deactivation
  function selectRawMaterial(id) {
    const m = currentItems.find(item => item.id === id);
    if (!m) return;

    const isInactive = m.is_active === false;
    const customActions = [];

    if (isInactive) {
      customActions.push({
        label: "Reactivate Material",
        class: "btn-primary",
        style: "background:#059669;color:#FFF;",
        onClick: async (e) => {
          if (!confirm(`Are you sure you want to REACTIVATE raw material '${m.name}'?`)) return;
          const btn = e.target;
          if (btn) { btn.disabled = true; btn.innerText = "Reactivating..."; }
          try {
            const resp = await fetch(`/api/procurement/raw-materials/${m.id}/reactivate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) throw new Error(data.error || "Failed to reactivate material");
            drawer.close();
            if (window.showToast) window.showToast("Reactivated", data.message, "success");
            else alert(data.message);
            loadViewData('raw-materials');
            loadAuxiliaryData();
          } catch (err) {
            if (btn) { btn.disabled = false; btn.innerText = "Reactivate Material"; }
            if (window.showToast) window.showToast("Error", err.message, "danger");
            else alert("Error: " + err.message);
          }
        }
      });
    } else {
      customActions.push({
        label: "Deactivate Material",
        class: "btn-danger",
        style: "background:#DC2626;color:#FFF;",
        onClick: async (e) => {
          if (!confirm(`Are you sure you want to DEACTIVATE raw material '${m.name}'? Inactive materials cannot be selected for new purchase orders or lots.`)) return;
          const btn = e.target;
          if (btn) { btn.disabled = true; btn.innerText = "Deactivating..."; }
          try {
            const resp = await fetch(`/api/procurement/raw-materials/${m.id}/deactivate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) throw new Error(data.error || "Failed to deactivate material");
            drawer.close();
            if (window.showToast) window.showToast("Deactivated", data.message, "success");
            else alert(data.message);
            loadViewData('raw-materials');
            loadAuxiliaryData();
          } catch (err) {
            if (btn) { btn.disabled = false; btn.innerText = "Deactivate Material"; }
            if (window.showToast) window.showToast("Error", err.message, "danger");
            else alert("Error: " + err.message);
          }
        }
      });
    }

    drawer.open({
      id: m.code,
      title: m.name,
      category: isInactive ? "INACTIVE MATERIAL" : m.category,
      headerStat: m.standard_unit,
      statSub: isInactive ? "Status: Deactivated" : "Measurement Unit",
      editableFields: [
        { label: "Material Name", key: "name", type: "text", value: m.name },
        { label: "Category", key: "category", type: "text", value: m.category },
        { label: "Storage Temperature", key: "storage_temp", type: "text", value: m.storage_temp },
        { label: "Packaging Spec", key: "unit_weight", type: "text", value: m.unit_weight }
      ],
      readonlySpecs: [
        { label: "Shelf Life", value: `${m.shelf_life_days} days` },
        { label: "Min Safety Stock", value: `${m.min_stock_level} ${m.standard_unit}` },
        { label: "Material Status", value: isInactive ? "INACTIVE (Soft Deactivated)" : "ACTIVE (Standard Supply)" },
        { label: "Intake Standards", value: "QCVN 5-1:2010/BYT / ISO 22000" }
      ],
      customActions: customActions
    }, async (item) => {
      const name = document.getElementById('drawer_input_name')?.value;
      const category = document.getElementById('drawer_input_category')?.value;
      const storage_temp = document.getElementById('drawer_input_storage_temp')?.value;
      const unit_weight = document.getElementById('drawer_input_unit_weight')?.value;

      try {
        const resp = await fetch(`/api/procurement/raw-materials/${m.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, category, storage_temp, unit_weight })
        });
        const resData = await resp.json();
        if (!resp.ok) throw new Error(resData.error || "Update failed");
        drawer.close();
        if (window.showToast) window.showToast("Success", "Material updated successfully", "success");
        loadViewData('raw-materials');
        loadAuxiliaryData();
      } catch (err) {
        if (window.showToast) window.showToast("Error", err.message, "danger");
        else alert("Error: " + err.message);
      }
    });
  }

  // Multi-item PO builder modal methods
  function openPoBuilder() {
    const supSelect = document.getElementById('poSupplierSelect');
    if (supSelect) {
      supSelect.innerHTML = suppliersList.map(s => `<option value="${s.id}">${s.name} (${s.code})</option>`).join('');
    }
    const tbody = document.getElementById('poItemsTableBody');
    tbody.innerHTML = '';
    poItemRowCount = 0;
    addPoItemRow(); // Add first default row

    document.getElementById('poModalBackdrop').classList.add('show');
    document.getElementById('poModalPanel').classList.add('open');
  }

  function closePoBuilder() {
    document.getElementById('poModalBackdrop').classList.remove('show');
    document.getElementById('poModalPanel').classList.remove('open');
  }

  function addPoItemRow() {
    poItemRowCount++;
    const rowId = `po_row_${poItemRowCount}`;
    const tbody = document.getElementById('poItemsTableBody');

    const defaultUnit = materialsList[0] ? (materialsList[0].standard_unit || 'kg') : 'kg';
    const matOpts = materialsList.map(m => `<option value="${m.id}" data-unit="${m.standard_unit || 'kg'}">${m.name} (${m.code})</option>`).join('');

    const tr = document.createElement('tr');
    tr.id = rowId;
    tr.style.borderBottom = '1px solid var(--border-light)';
    tr.innerHTML = `
      <td style="padding:8px 4px;">
        <select class="field-slot-select" style="font-size:12px;padding:6px 8px;" onchange="ProcurementModule.handlePoMaterialChange('${rowId}', this)">
          ${matOpts}
        </select>
      </td>
      <td style="padding:8px 4px;">
        <input type="number" class="field-slot-input" style="font-size:12px;padding:6px 8px;" value="1000" min="1" step="1" onchange="ProcurementModule.recalculatePoTotal()">
      </td>
      <td style="padding:8px 4px;">
        <span class="po-row-unit" style="font-size:12px;color:var(--text-secondary);font-weight:600;">${defaultUnit}</span>
      </td>
      <td style="padding:8px 4px;">
        <input type="number" class="field-slot-input" style="font-size:12px;padding:6px 8px;" value="15000000" step="500000" onchange="ProcurementModule.recalculatePoTotal()">
      </td>
      <td style="padding:8px 4px;text-align:center;">
        <button type="button" onclick="document.getElementById('${rowId}').remove(); ProcurementModule.recalculatePoTotal();" style="color:#DC2626;padding:4px;background:transparent;">✕</button>
      </td>
    `;
    tbody.appendChild(tr);
    recalculatePoTotal();
  }

  function handlePoMaterialChange(rowId, selectEl) {
    const row = document.getElementById(rowId);
    if (!row) return;
    const selectedOpt = selectEl.options[selectEl.selectedIndex];
    const unit = selectedOpt.getAttribute('data-unit') || 'Tons';
    const unitSpan = row.querySelector('.po-row-unit');
    if (unitSpan) unitSpan.textContent = unit;
    recalculatePoTotal();
  }

  function recalculatePoTotal() {
    let total = 0;
    const rows = document.querySelectorAll('#poItemsTableBody tr');
    rows.forEach(row => {
      const inputs = row.querySelectorAll('input');
      if (inputs.length >= 2) {
        const qty = parseFloat(inputs[0].value) || 0;
        const price = parseFloat(inputs[1].value) || 0;
        total += (qty * price);
      }
    });
    const totalEl = document.getElementById('poTotalAmountDisplay');
    if (totalEl) totalEl.textContent = `${total.toLocaleString()} VND`;
  }

  async function submitPurchaseOrder() {
    const supplierId = document.getElementById('poSupplierSelect').value;
    const expectedDate = document.getElementById('poExpectedDate').value;
    const notes = document.getElementById('poNotes').value;

    const rows = document.querySelectorAll('#poItemsTableBody tr');
    if (rows.length === 0) {
      alert("Please add at least 1 line item!");
      return;
    }

    const items = [];
    rows.forEach(row => {
      const select = row.querySelector('select');
      const inputs = row.querySelectorAll('input');
      const unitSpan = row.querySelector('.po-row-unit');

      if (select && inputs.length >= 2) {
        items.push({
          raw_material_id: parseInt(select.value),
          quantity_ordered: parseFloat(inputs[0].value),
          unit_price: parseFloat(inputs[1].value),
          unit: unitSpan ? unitSpan.textContent : 'Tons'
        });
      }
    });

    try {
      const res = await fetch('/api/procurement/purchase-orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          supplier_id: parseInt(supplierId),
          expected_delivery_date: expectedDate,
          notes: notes,
          items: items
        })
      });

      if (!res.ok) throw new Error("Failed to create purchase order");
      const result = await res.json();
      closePoBuilder();
      alert(`Successfully created purchase order ${result.data.po_number}!`);
      loadAuxiliaryData();
      if (activeView === 'po') loadViewData('po');
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  }

  // GRN Receipt Modal Methods
  function openGrn() {
    const poSelect = document.getElementById('grnPoSelect');
    if (poSelect) {
      poSelect.innerHTML = `<option value="">-- Select Purchase Order to Receive --</option>` + 
        posList.map(p => `<option value="${p.id}">${p.po_number} - ${p.supplier_name} (${p.status})</option>`).join('');
    }
    document.getElementById('grnItemsContainer').innerHTML = '<div style="font-size:12px;color:var(--text-muted);">Please select a Purchase Order above.</div>';
    document.getElementById('grnModalBackdrop').classList.add('show');
    document.getElementById('grnModalPanel').classList.add('open');
  }

  function closeGrn() {
    document.getElementById('grnModalBackdrop').classList.remove('show');
    document.getElementById('grnModalPanel').classList.remove('open');
  }

  function loadGrnPoItems(poId) {
    const container = document.getElementById('grnItemsContainer');
    if (!poId) {
      container.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">Please select a Purchase Order above.</div>';
      return;
    }
    const po = posList.find(p => p.id === parseInt(poId));
    if (!po || !po.items || po.items.length === 0) {
      container.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">This purchase order has no line items.</div>';
      return;
    }

    container.innerHTML = po.items.map(item => `
      <div class="grn-line-item-box" data-po-item-id="${item.id}" data-raw-material-id="${item.raw_material_id}" style="background:#F8FAFC;border:1px solid var(--border-subtle);border-radius:8px;padding:12px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
          <strong style="color:var(--text-main);font-size:13px;">${item.material_name}</strong>
          <span style="font-size:12px;color:var(--text-muted);">Ordered: ${item.quantity_ordered} ${item.unit} (Received: ${item.quantity_received} ${item.unit})</span>
        </div>
        <div class="field-slot-grid">
          <div class="field-slot-group">
            <label class="field-slot-label">Quantity Received *</label>
            <input type="number" class="field-slot-input grn-item-qty" value="${Math.max(item.quantity_ordered - item.quantity_received, 1)}" step="0.1">
          </div>
          <div class="field-slot-group">
            <label class="field-slot-label">Unit & Specification</label>
            <input type="text" class="field-slot-input grn-item-unit" value="${item.unit}" readonly>
          </div>
        </div>
      </div>
    `).join('');
  }

  async function submitGoodsReceipt() {
    const poId = document.getElementById('grnPoSelect').value;
    if (!poId) {
      alert("Please select a Purchase Order!");
      return;
    }
    const truckPlate = document.getElementById('grnTruckPlate').value;
    const deliveryNote = document.getElementById('grnDeliveryNote').value;

    const boxes = document.querySelectorAll('.grn-line-item-box');
    if (boxes.length === 0) {
      alert("No line items available to receive!");
      return;
    }

    const items = [];
    boxes.forEach(b => {
      const poItemId = b.getAttribute('data-po-item-id');
      const rawMaterialId = b.getAttribute('data-raw-material-id');
      const qtyInput = b.querySelector('.grn-item-qty');
      const unitInput = b.querySelector('.grn-item-unit');

      if (qtyInput) {
        items.push({
          purchase_order_item_id: parseInt(poItemId),
          raw_material_id: parseInt(rawMaterialId),
          quantity_received: parseFloat(qtyInput.value) || 0,
          unit: unitInput ? unitInput.value : 'Tons'
        });
      }
    });

    try {
      const res = await fetch('/api/procurement/grn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          purchase_order_id: parseInt(poId),
          truck_plate: truckPlate,
          delivery_note_ref: deliveryNote,
          items: items
        })
      });

      if (!res.ok) throw new Error("Goods receipt intake failed");
      const result = await res.json();
      closeGrn();

      alert(`SUCCESS!\n${result.message}\nNew lots generated: ${result.generated_lots.join(', ')} with status PENDING_QC.`);

      // Update badge & refresh view
      updatePendingQcBadge();
      loadAuxiliaryData();
      if (activeView === 'lots') {
        loadViewData('lots');
      } else if (activeView === 'grn') {
        loadViewData('grn');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  }

  // Supplier & Raw Material Modals
  function openSupModal() {
    document.getElementById('supModalBackdrop').classList.add('show');
    document.getElementById('supModalPanel').classList.add('open');
  }
  function closeSupModal() {
    document.getElementById('supModalBackdrop').classList.remove('show');
    document.getElementById('supModalPanel').classList.remove('open');
  }
  async function submitSupplier() {
    const name = document.getElementById('newSupName').value.trim();
    if (!name) return alert("Please enter supplier name");
    const contact = document.getElementById('newSupContact').value;
    const phone = document.getElementById('newSupPhone').value;
    const email = document.getElementById('newSupEmail').value;
    const address = document.getElementById('newSupAddress').value;

    await fetch('/api/procurement/suppliers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, contact_name: contact, phone, email, address })
    });
    closeSupModal();
    loadAuxiliaryData();
    if (activeView === 'suppliers') loadViewData('suppliers');
  }

  function openMatModal() {
    document.getElementById('matModalBackdrop').classList.add('show');
    document.getElementById('matModalPanel').classList.add('open');
  }
  function closeMatModal() {
    document.getElementById('matModalBackdrop').classList.remove('show');
    document.getElementById('matModalPanel').classList.remove('open');
  }
  async function submitRawMaterial() {
    const name = document.getElementById('newMatName').value.trim();
    if (!name) return alert("Please enter raw material name");
    const category = document.getElementById('newMatCategory').value;
    const standard_unit = document.getElementById('newMatUnit').value;
    const storage_temp = document.getElementById('newMatTemp').value;
    const shelf_life_days = document.getElementById('newMatShelfLife').value;

    await fetch('/api/procurement/raw-materials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, category, standard_unit, storage_temp, shelf_life_days })
    });
    closeMatModal();
    loadAuxiliaryData();
    if (activeView === 'raw-materials') loadViewData('raw-materials');
  }

  return {
    init,
    selectCard,
    selectLot,
    selectSupplier,
    selectRawMaterial,
    selectPo,
    selectGrn,
    toggleShowInactive,
    handlePoMaterialChange,
    recalculatePoTotal,
    addPoItemRow,
    openPoBuilder,
    closePoBuilder,
    submitPurchaseOrder,
    openGrn,
    closeGrn,
    loadGrnPoItems,
    submitGoodsReceipt,
    openSupModal,
    closeSupModal,
    submitSupplier,
    openMatModal,
    closeMatModal,
    submitRawMaterial
  };
})();

// Global helpers for inline HTML event handlers
window.openPoBuilderModal = () => ProcurementModule.openPoBuilder ? ProcurementModule.openPoBuilder() : document.getElementById('poModalPanel')?.classList.add('open') || document.getElementById('poModalBackdrop')?.classList.add('show');
window.closePoBuilderModal = () => { document.getElementById('poModalPanel')?.classList.remove('open'); document.getElementById('poModalBackdrop')?.classList.remove('show'); };
window.addPoItemRow = () => ProcurementModule.addPoItemRow();

window.openGrnModal = (selectedPoId) => {
  const poSelect = document.getElementById('grnPoSelect');
  fetch('/api/procurement/purchase-orders').then(r => r.json()).then(data => {
    if (poSelect) {
      poSelect.innerHTML = `<option value="">-- Select Purchase Order to Receive --</option>` + 
        (data.data || []).filter(p => p.status !== 'CANCELLED').map(p => `
          <option value="${p.id}" ${selectedPoId && parseInt(p.id) === parseInt(selectedPoId) ? 'selected' : ''}>
            ${p.po_number} - ${p.supplier_name} (${p.status})
          </option>
        `).join('');
      if (selectedPoId) {
        window.loadGrnPoItems(selectedPoId);
      }
    }
  });
  document.getElementById('grnModalBackdrop')?.classList.add('show');
  document.getElementById('grnModalPanel')?.classList.add('open');
};
window.closeGrnModal = () => { document.getElementById('grnModalBackdrop')?.classList.remove('show'); document.getElementById('grnModalPanel')?.classList.remove('open'); };

window.loadGrnPoItems = (val) => {
  if (!val) {
    const container = document.getElementById('grnItemsContainer');
    if (container) container.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">Please select a Purchase Order above.</div>';
    return;
  }
  fetch('/api/procurement/purchase-orders').then(r => r.json()).then(data => {
    const po = (data.data || []).find(p => p.id === parseInt(val));
    const container = document.getElementById('grnItemsContainer');
    if (!po || !po.items || po.items.length === 0) {
      if (container) container.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">This purchase order has no line items.</div>';
      return;
    }
    container.innerHTML = po.items.map(item => `
      <div class="grn-line-item-box" data-po-item-id="${item.id}" data-raw-material-id="${item.raw_material_id}" style="background:#F8FAFC;border:1px solid var(--border-subtle);border-radius:8px;padding:12px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
          <strong style="color:var(--text-main);font-size:13px;">${item.material_name}</strong>
          <span style="font-size:12px;color:var(--text-muted);">Ordered: ${item.quantity_ordered} ${item.unit} (Received: ${item.quantity_received} ${item.unit})</span>
        </div>
        <div class="field-slot-grid">
          <div class="field-slot-group">
            <label class="field-slot-label">Quantity Received *</label>
            <input type="number" class="field-slot-input grn-item-qty" value="${Math.max(item.quantity_ordered - item.quantity_received, 1)}" step="0.1">
          </div>
          <div class="field-slot-group">
            <label class="field-slot-label">Unit & Specification</label>
            <input type="text" class="field-slot-input grn-item-unit" value="${item.unit}" readonly>
          </div>
        </div>
      </div>
    `).join('');
  });
};

window.submitGoodsReceipt = async (e) => {
  const submitBtn = e && e.target ? e.target : document.querySelector('#grnModalPanel .btn-primary-action');
  const poSelect = document.getElementById('grnPoSelect');
  const poId = poSelect ? poSelect.value : '';
  if (!poId) {
    if (window.FoodManAnimations) window.FoodManAnimations.shakeField(poSelect);
    if (window.showToast) window.showToast("Validation Error", "Please select a Purchase Order!", "danger");
    else alert("Please select a Purchase Order!");
    return;
  }
  const truckPlate = document.getElementById('grnTruckPlate').value;
  const deliveryNote = document.getElementById('grnDeliveryNote').value;
  const boxes = document.querySelectorAll('.grn-line-item-box');
  const items = [];
  boxes.forEach(b => {
    items.push({
      purchase_order_item_id: parseInt(b.getAttribute('data-po-item-id')),
      raw_material_id: parseInt(b.getAttribute('data-raw-material-id')),
      quantity_received: parseFloat(b.querySelector('.grn-item-qty')?.value) || 0,
      unit: b.querySelector('.grn-item-unit')?.value || 'Tons'
    });
  });

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.dataset.originalText = submitBtn.innerText;
    submitBtn.innerText = "Receiving Intake...";
  }

  try {
    const res = await fetch('/api/procurement/grn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        purchase_order_id: parseInt(poId),
        truck_plate: truckPlate,
        delivery_note_ref: deliveryNote,
        items: items
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Goods receipt failed");

    window.closeGrnModal();
    sessionStorage.setItem('foodman_highlight_first_card', 'true');
    if (window.showToast) window.showToast("Goods Receipt Saved", data.message, "success");
    else alert(data.message);
    window.location.href = '/procurement?view=lots';
  } catch (err) {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = submitBtn.dataset.originalText || "Save Goods Receipt";
    }
    if (window.showToast) window.showToast("Error", err.message, "danger");
    else alert("Error: " + err.message);
  }
};

window.openSupplierModal = () => { document.getElementById('supModalBackdrop')?.classList.add('show'); document.getElementById('supModalPanel')?.classList.add('open'); };
window.closeSupplierModal = () => { document.getElementById('supModalBackdrop')?.classList.remove('show'); document.getElementById('supModalPanel')?.classList.remove('open'); };
window.submitNewSupplier = async (e) => {
  const submitBtn = e && e.target ? e.target : document.querySelector('#supModalPanel .btn-primary-action');
  const nameInput = document.getElementById('newSupName');
  const name = nameInput ? nameInput.value.trim() : '';
  if (!name) {
    if (window.FoodManAnimations) window.FoodManAnimations.shakeField(nameInput);
    if (window.showToast) window.showToast("Validation Error", "Please enter supplier name", "danger");
    else alert("Please enter supplier name");
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.dataset.originalText = submitBtn.innerText;
    submitBtn.innerText = "Saving Supplier...";
  }

  try {
    const res = await fetch('/api/procurement/suppliers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        contact_name: document.getElementById('newSupContact').value,
        phone: document.getElementById('newSupPhone').value,
        email: document.getElementById('newSupEmail').value,
        address: document.getElementById('newSupAddress').value
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to create supplier");

    window.closeSupplierModal();
    sessionStorage.setItem('foodman_highlight_first_card', 'true');
    if (window.showToast) window.showToast("Success", "Supplier registered successfully", "success");
    window.location.reload();
  } catch (err) {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = submitBtn.dataset.originalText || "Save Supplier";
    }
    if (window.showToast) window.showToast("Error", err.message, "danger");
    else alert("Error: " + err.message);
  }
};

window.openRawMaterialModal = () => { document.getElementById('matModalBackdrop')?.classList.add('show'); document.getElementById('matModalPanel')?.classList.add('open'); };
window.closeRawMaterialModal = () => { document.getElementById('matModalBackdrop')?.classList.remove('show'); document.getElementById('matModalPanel')?.classList.remove('open'); };
window.submitNewRawMaterial = async (e) => {
  const submitBtn = e && e.target ? e.target : document.querySelector('#matModalPanel .btn-primary-action');
  const nameInput = document.getElementById('newMatName');
  const name = nameInput ? nameInput.value.trim() : '';
  if (!name) {
    if (window.FoodManAnimations) window.FoodManAnimations.shakeField(nameInput);
    if (window.showToast) window.showToast("Validation Error", "Please enter raw material name", "danger");
    else alert("Please enter raw material name");
    return;
  }
  const code = document.getElementById('newMatCode')?.value.trim() || undefined;
  const minStock = parseFloat(document.getElementById('newMatMinStock')?.value) || 500;

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.dataset.originalText = submitBtn.innerText;
    submitBtn.innerText = "Saving Material...";
  }

  try {
    const res = await fetch('/api/procurement/raw-materials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        code,
        category: document.getElementById('newMatCategory').value,
        standard_unit: document.getElementById('newMatUnit').value,
        storage_temp: document.getElementById('newMatTemp').value,
        shelf_life_days: document.getElementById('newMatShelfLife').value,
        min_stock_level: minStock
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to create raw material");

    window.closeRawMaterialModal();
    sessionStorage.setItem('foodman_highlight_first_card', 'true');
    if (window.showToast) window.showToast("Success", "Raw material registered successfully", "success");
    window.location.reload();
  } catch (err) {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = submitBtn.dataset.originalText || "Save Raw Material";
    }
    if (window.showToast) window.showToast("Error", err.message, "danger");
    else alert("Error: " + err.message);
  }
};

window.submitPurchaseOrder = async (e) => {
  const submitBtn = e && e.target ? e.target : document.querySelector('#poModalPanel .btn-primary-action');
  const supplierSelect = document.getElementById('poSupplierSelect');
  const supplierId = supplierSelect ? supplierSelect.value : '';
  const expectedDate = document.getElementById('poExpectedDate').value;
  const notes = document.getElementById('poNotes').value;
  const rows = document.querySelectorAll('#poItemsTableBody tr');
  if (rows.length === 0) {
    const table = document.getElementById('poItemsTableBody');
    if (window.FoodManAnimations) window.FoodManAnimations.shakeField(table);
    if (window.showToast) window.showToast("Validation Error", "Please add at least 1 line item!", "danger");
    else alert("Please add at least 1 line item!");
    return;
  }

  const items = [];
  rows.forEach(row => {
    const select = row.querySelector('select');
    const inputs = row.querySelectorAll('input');
    const unitSpan = row.querySelector('.po-row-unit');
    if (select && inputs.length >= 2) {
      items.push({
        raw_material_id: parseInt(select.value),
        quantity_ordered: parseFloat(inputs[0].value),
        unit_price: parseFloat(inputs[1].value),
        unit: unitSpan ? unitSpan.textContent : 'Tons'
      });
    }
  });

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.dataset.originalText = submitBtn.innerText;
    submitBtn.innerText = "Creating PO...";
  }

  try {
    const res = await fetch('/api/procurement/purchase-orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        supplier_id: parseInt(supplierId),
        expected_delivery_date: expectedDate,
        notes: notes,
        items: items
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to create purchase order");

    window.closePoBuilderModal();
    sessionStorage.setItem('foodman_highlight_first_card', 'true');
    if (window.showToast) window.showToast("Purchase Order Created", `PO ${data.data.po_number} created successfully`, "success");
    window.location.href = '/procurement?view=po';
  } catch (err) {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = submitBtn.dataset.originalText || "Confirm Purchase Order";
    }
    if (window.showToast) window.showToast("Error", err.message, "danger");
    else alert("Error: " + err.message);
  }
};
