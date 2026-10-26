/**
 * Food Man - Phase 4 Warehouse & Logistics Client Controller
 * FEFO Inventory, Outbound Dispatches, Live Decrement, and Customer Management
 */
const WarehouseApp = (function() {

  let currentInventory = [];
  let currentDispatches = [];
  let currentCustomers = [];
  let activeView = 'inventory';

  function init() {
    const urlParams = new URLSearchParams(window.location.search);
    activeView = urlParams.get('view') || 'inventory';

    if (activeView === 'dispatches') {
      loadDispatches().then(() => checkWarehouseOpenParam(urlParams));
    } else if (activeView === 'customers') {
      loadCustomers().then(() => checkWarehouseOpenParam(urlParams));
    } else {
      loadInventory();
    }
  }

  function checkWarehouseOpenParam(urlParams) {
    const openParam = urlParams.get('open');
    if (!openParam) return;
    setTimeout(() => {
      if (activeView === 'customers' && typeof selectCustomer === 'function') {
        const c = currentCustomers.find(item => String(item.id) === String(openParam) || item.customer_code === openParam);
        if (c) selectCustomer(c.id);
      } else if (activeView === 'dispatches' && typeof selectDispatch === 'function') {
        const d = currentDispatches.find(item => String(item.id) === String(openParam) || item.dispatch_code === openParam);
        if (d) selectDispatch(d.id);
      }
    }, 150);
  }

  // ---------------------------------------------------------------------------
  // 1. Warehouse Inventory in FEFO Order
  // ---------------------------------------------------------------------------
  async function loadInventory() {
    try {
      const resp = await fetch('/api/warehouse/inventory');
      const data = await resp.json();
      if (data.success) {
        currentInventory = data.data;
        renderInventory(data.data);
      }
    } catch (e) {
      console.error("Failed loading inventory", e);
    }
  }

  function renderInventory(items) {
    const container = document.getElementById('warehouseCardGrid');
    const countEl = document.getElementById('totalRecordsCount');
    if (!container) return;

    if (countEl) countEl.innerText = `${items.length} Finished goods lots in stock (FEFO sorted: Earliest expiry first)`;
    container.innerHTML = '';

    items.forEach(item => {
      let urgencyClass = 'urgency-fresh';
      let urgencyLabel = `${item.days_to_expiry} days left`;

      if (item.expiry_urgency === 'EXPIRED') {
        urgencyClass = 'urgency-expired';
        urgencyLabel = '⚠ Expired';
      } else if (item.expiry_urgency === 'EXPIRING_SOON') {
        urgencyClass = 'urgency-expiring-soon';
        urgencyLabel = `⚠ Expiring soon: ${item.days_to_expiry} days left`;
      } else if (item.expiry_urgency === 'ATTENTION') {
        urgencyClass = 'urgency-attention';
        urgencyLabel = `Attention: ${item.days_to_expiry} days left`;
      }

      const card = document.createElement('div');
      card.className = 'record-card';
      card.onclick = () => selectInventory(item.id);

      card.innerHTML = `
        <div class="card-header-row">
          <div>
            <span class="card-id-badge">${item.sku_code}</span>
            <span class="card-title-text" style="display:block;margin-top:4px;font-weight:700;font-size:14px;">${item.product_name}</span>
          </div>
          <div style="text-align:right;">
            <span class="card-secondary-stat">EXP: ${item.expiry_date}</span>
            <div style="margin-top:4px;">
              <span class="urgency-pill ${urgencyClass}">${urgencyLabel}</span>
            </div>
          </div>
        </div>

        <div class="card-minigrid" style="margin-top:14px;">
          <div class="minigrid-cell">
            <span class="minigrid-label">Storage Bin</span>
            <span class="minigrid-val">${item.storage_bin}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Pallet Code / Batch</span>
            <span class="minigrid-val">${item.pallet_code} • ${item.batch_code}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Available / Total Qty</span>
            <span class="minigrid-val" style="font-weight:800;color:var(--accent-navy);">
              ${item.available_quantity.toLocaleString()} / ${item.initial_quantity.toLocaleString()} ${item.unit}
            </span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Inventory Valuation</span>
            <span class="minigrid-val">${item.total_value ? item.total_value.toLocaleString() + ' VND' : 'N/A'}</span>
          </div>
        </div>

        <div class="card-footer-row" style="margin-top:14px;">
          <div class="avatar-stack">
            <div class="avatar-stack-item">WH</div>
            <div class="avatar-stack-item" style="background:#059669;">LOG</div>
          </div>
          <span class="status-pill status-pill-approved">
            <span class="status-indicator-dot dot-approved"></span>
            ${item.status}
          </span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  // ---------------------------------------------------------------------------
  // 2. Outbound Dispatches
  // ---------------------------------------------------------------------------
  async function loadDispatches() {
    try {
      const resp = await fetch('/api/warehouse/dispatches');
      const data = await resp.json();
      if (data.success) {
        currentDispatches = data.data;
        renderDispatches(data.data);
      }
    } catch (e) {
      console.error("Failed loading dispatches", e);
    }
  }

  function renderDispatches(dispatches) {
    const container = document.getElementById('warehouseCardGrid');
    const countEl = document.getElementById('totalRecordsCount');
    if (!container) return;

    if (countEl) countEl.innerText = `${dispatches.length} Outbound dispatches & Reefer fleet active`;
    container.innerHTML = '';

    dispatches.forEach(d => {
      const isDelivered = d.status === 'DELIVERED';
      const statusPillClass = isDelivered ? 'status-pill-approved' : 'status-pill-pending';
      const statusDotClass = isDelivered ? 'dot-approved' : 'dot-pending';
      const statusLabel = isDelivered ? 'Delivered' : 'In Transit (Fleet)';
      const progressPercent = isDelivered ? 100 : 65;

      const card = document.createElement('div');
      card.className = 'record-card tms-card';
      card.onclick = () => selectDispatch(d.id);

      card.innerHTML = `
        <div class="card-header-row">
          <div>
            <div style="display:flex;align-items:center;gap:6px;">
              <span class="card-id-badge">${d.dispatch_code}</span>
              <span class="card-category-sub" style="font-size:11px;color:var(--text-muted);font-weight:700;text-transform:uppercase;">Cold Chain Reefer</span>
            </div>
            <span class="card-title-text" style="display:block;margin-top:4px;font-weight:800;font-size:15px;color:#0F172A;">${d.customer_name}</span>
          </div>
          <div style="text-align:right;">
            <span class="card-secondary-stat">${d.total_packages.toLocaleString()} Cases</span>
            <span style="font-size:11px;color:var(--text-muted);display:block;margin-top:2px;">Outbound Fleet</span>
          </div>
        </div>

        <div class="card-minigrid" style="margin:12px 0;">
          <div class="minigrid-cell">
            <span class="minigrid-label">Truck & License Plate</span>
            <span class="minigrid-val" style="font-weight:700;">🚛 ${d.license_plate}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Reefer IoT Temperature</span>
            <span class="minigrid-val" style="font-weight:800;color:#0369A1;">
              ❄ ${d.temp_sensor_celsius}°C <span style="font-size:10px;color:#059669;font-weight:700;">(Normal)</span>
            </span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Delivery Destination</span>
            <span class="minigrid-val" style="font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">📍 ${d.destination}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Driver / Operator</span>
            <span class="minigrid-val">👤 ${d.driver_name}</span>
          </div>
        </div>

        <div class="card-progress-wrap" style="margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:4px;">
            <span>Route Transit Progress</span>
            <span style="color:#2563EB;">${progressPercent}%</span>
          </div>
          <div class="card-progress-bar">
            <div class="card-progress-fill" style="width:${progressPercent}%;"></div>
          </div>
        </div>

        <div class="card-footer-row">
          <div class="avatar-stack">
            <div class="avatar-stack-item" title="Driver: ${d.driver_name}">
              ${d.driver_name ? d.driver_name.split(' ').map(n=>n[0]).join('').slice(0,2) : 'DR'}
            </div>
            <div class="avatar-stack-item" style="background:#0EA5E9;" title="Fleet Dispatcher">DP</div>
          </div>
          <span class="status-pill ${statusPillClass}">
            <span class="status-indicator-dot ${statusDotClass}"></span>
            ${statusLabel}
          </span>
        </div>
      `;
      container.appendChild(card);
    });

    // Check if new dispatch record was flagged
    if (sessionStorage.getItem('foodman_new_dispatch_created') === 'true') {
      sessionStorage.removeItem('foodman_new_dispatch_created');
      const firstCard = container.querySelector('.record-card');
      if (firstCard && window.FoodManAnimations) {
        window.FoodManAnimations.animateNewRecord(firstCard);
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 2b. Customer Channels & Supermarket Accounts
  // ---------------------------------------------------------------------------
  async function loadCustomers() {
    const container = document.getElementById('warehouseCardGrid');
    const countEl = document.getElementById('totalRecordsCount');
    if (!container) return;

    if (countEl) countEl.innerText = "Syncing customer channels...";
    container.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; color: var(--text-muted);">
        <div style="font-size: 15px; font-weight: 600;">Loading customer channels...</div>
      </div>
    `;

    try {
      const resp = await fetch('/api/warehouse/customers');
      if (!resp.ok) throw new Error(`Server returned HTTP ${resp.status}`);
      const data = await resp.json();
      if (data.success) {
        currentCustomers = data.data || [];
        renderCustomers(currentCustomers);
      } else {
        throw new Error(data.error || "Failed to load customers");
      }
    } catch (e) {
      console.error("Failed loading customers", e);
      if (countEl) countEl.innerText = "Failed to sync customer channels";
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 40px; text-align: center; background: #FEF2F2; border-radius: 12px; border: 1px solid #FCA5A5;">
          <div style="font-size: 15px; font-weight: 700; color: #DC2626;">Unable to load customers</div>
          <div style="font-size: 13px; color: #991B1B; margin-top: 4px;">${e.message}</div>
          <button onclick="WarehouseApp.loadCustomers()" style="margin-top:12px;padding:6px 14px;background:#DC2626;color:#FFF;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Retry</button>
        </div>
      `;
    }
  }

  function renderCustomers(customers) {
    const container = document.getElementById('warehouseCardGrid');
    const countEl = document.getElementById('totalRecordsCount');
    if (!container) return;

    if (countEl) countEl.innerText = `${customers.length} Retailer & Distribution Channels`;

    if (customers.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--border-subtle);">
          <div style="font-size: 16px; font-weight: 700; color: var(--text-main);">No customers yet</div>
          <div style="font-size: 13px; color: var(--text-muted); margin-top: 6px;">Register distribution partners or supermarket chains using '+ Add Customer'.</div>
          <button class="btn-primary-action" onclick="WarehouseApp.openCustomerModal()" style="margin-top:16px;display:inline-flex;">+ Add Customer</button>
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    customers.forEach(cust => {
      const card = document.createElement('div');
      card.className = 'record-card';
      card.style.cursor = 'pointer';
      card.onclick = () => selectCustomer(cust.id);

      card.innerHTML = `
        <div class="card-header-row">
          <div>
            <span class="card-code-badge">${cust.customer_code}</span>
            <h3 class="card-title-text" style="margin-top:4px;">${cust.name}</h3>
          </div>
          <span class="status-pill status-pill-approved">
            <span class="status-indicator-dot dot-approved"></span>
            ${cust.status || 'ACTIVE'}
          </span>
        </div>

        <div class="card-mini-grid" style="grid-template-columns: 1fr 1fr; margin: 12px 0;">
          <div class="minigrid-cell">
            <span class="minigrid-label">Contact Person</span>
            <span class="minigrid-val" style="font-weight:600;">${cust.contact_person || 'N/A'}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Phone</span>
            <span class="minigrid-val" style="font-family:'JetBrains Mono',monospace;font-weight:600;">${cust.phone || 'N/A'}</span>
          </div>
          <div class="minigrid-cell" style="grid-column: 1 / -1;">
            <span class="minigrid-label">Delivery Destination</span>
            <span class="minigrid-val" style="font-size:12px;">📍 ${cust.delivery_address || 'N/A'}${cust.city ? ', ' + cust.city : ''}</span>
          </div>
        </div>

        <div class="card-footer-row" style="margin-top:10px;display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:12px;color:var(--text-muted);">${cust.email || 'No email registered'}</span>
          <span style="font-size:12px;font-weight:700;color:var(--accent-navy);">View Details →</span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  function selectCustomer(id) {
    const cust = currentCustomers.find(c => c.id === id);
    if (!cust) return;

    const drawer = document.getElementById('customerDrawerPanel');
    const backdrop = document.getElementById('customerDrawerBackdrop');
    if (!drawer) return;

    document.getElementById('custDrawerTitle').innerText = `${cust.name} (${cust.customer_code})`;
    document.getElementById('customerDrawerContent').innerHTML = `
      <div style="background:var(--accent-navy);color:#FFF;padding:18px;border-radius:10px;margin-bottom:16px;">
        <div style="font-size:11px;opacity:0.8;text-transform:uppercase;letter-spacing:0.5px;">REGISTERED RETAIL CHANNEL</div>
        <div style="font-size:18px;font-weight:800;margin-top:4px;">${cust.name}</div>
        <div style="font-size:12px;margin-top:6px;opacity:0.9;">Account Code: <strong>${cust.customer_code}</strong> | Status: <strong>${cust.status || 'ACTIVE'}</strong></div>
      </div>

      <div style="font-size:12px;font-weight:700;color:var(--text-secondary);margin-bottom:8px;text-transform:uppercase;">CONTACT & LOGISTICS DOSSIER</div>
      <div class="infolist-container" style="margin-bottom:16px;">
        <div class="infolist-row-item">
          <span style="color:var(--text-muted);">Contact Person</span>
          <span style="font-weight:700;">${cust.contact_person || 'N/A'}</span>
        </div>
        <div class="infolist-row-item">
          <span style="color:var(--text-muted);">Phone Number</span>
          <span style="font-weight:700;font-family:'JetBrains Mono',monospace;">${cust.phone || 'N/A'}</span>
        </div>
        <div class="infolist-row-item">
          <span style="color:var(--text-muted);">Email Address</span>
          <span style="font-weight:700;">${cust.email || 'N/A'}</span>
        </div>
        <div class="infolist-row-item">
          <span style="color:var(--text-muted);">City / Region</span>
          <span style="font-weight:700;">${cust.city || 'Hanoi'}</span>
        </div>
        <div class="infolist-row-item">
          <span style="color:var(--text-muted);">Delivery Destination</span>
          <span style="font-weight:700;max-width:240px;text-align:right;">${cust.delivery_address || 'N/A'}</span>
        </div>
      </div>
    `;

    drawer.classList.add('is-open');
    if (backdrop) backdrop.style.display = 'block';
  }

  function closeCustomerDrawer() {
    const drawer = document.getElementById('customerDrawerPanel');
    const backdrop = document.getElementById('customerDrawerBackdrop');
    if (drawer) drawer.classList.remove('is-open');
    if (backdrop) backdrop.style.display = 'none';
  }

  function openCustomerModal() {
    const modal = document.getElementById('customerModal');
    const backdrop = document.getElementById('customerBackdrop');
    const form = document.getElementById('addCustomerForm');
    const errBox = document.getElementById('customerFormError');
    if (form) form.reset();
    if (errBox) { errBox.style.display = 'none'; errBox.innerText = ''; }
    if (modal) modal.style.display = 'block';
    if (backdrop) backdrop.style.display = 'block';
  }

  function closeCustomerModal() {
    const modal = document.getElementById('customerModal');
    const backdrop = document.getElementById('customerBackdrop');
    if (modal) modal.style.display = 'none';
    if (backdrop) backdrop.style.display = 'none';
  }

  async function submitCustomer() {
    const btn = document.getElementById('btnSubmitCustomer');
    const errBox = document.getElementById('customerFormError');
    const name = document.getElementById('custNameInput')?.value.trim();
    const contact = document.getElementById('custContactInput')?.value.trim();
    const phone = document.getElementById('custPhoneInput')?.value.trim();
    const email = document.getElementById('custEmailInput')?.value.trim();
    const city = document.getElementById('custCityInput')?.value.trim();
    const address = document.getElementById('custAddressInput')?.value.trim();

    if (!name || !contact || !phone || !address) {
      if (errBox) {
        errBox.innerText = "Please complete all required fields (*)";
        errBox.style.display = 'block';
      }
      return;
    }

    // Prevent double clicks & give loading feedback
    if (btn) {
      btn.disabled = true;
      btn.dataset.originalHtml = btn.innerHTML;
      btn.innerHTML = `<span>Saving...</span>`;
    }

    try {
      const resp = await fetch('/api/warehouse/customers', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          name: name,
          contact_person: contact,
          phone: phone,
          email: email,
          city: city,
          delivery_address: address
        })
      });

      const resData = await resp.json();
      if (!resp.ok || !resData.success) {
        throw new Error(resData.error || "Failed to create customer");
      }

      closeCustomerModal();
      if (window.showToast) {
        window.showToast("Success", resData.message || "Customer created successfully!", "success");
      } else {
        alert(resData.message || "Customer created successfully!");
      }
      loadCustomers();
    } catch (err) {
      if (errBox) {
        errBox.innerText = err.message;
        errBox.style.display = 'block';
      } else {
        alert(err.message);
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = btn.dataset.originalHtml || '<span>Save Customer</span>';
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 3. Detail Drawer for Inventory & Dispatch
  // ---------------------------------------------------------------------------
  async function selectInventory(invId) {
    const inv = currentInventory.find(i => i.id === invId);
    if (!inv) return;

    const drawer = document.getElementById('detailDrawerRoot');
    const backdrop = document.getElementById('drawerBackdrop');
    if (!drawer) return;

    document.getElementById('drawerRecordId').innerText = inv.sku_code;

    // Visual Slot
    document.getElementById('drawerVisualSlot').innerHTML = `
      <div style="background:var(--accent-navy);color:#FFF;padding:16px;border-radius:var(--radius-md);margin-bottom:12px;">
        <div style="font-size:12px;opacity:0.8;">FINISHED GOODS INVENTORY (FEFO)</div>
        <div style="font-size:16px;font-weight:800;margin-top:2px;">${inv.product_name}</div>
        <div style="font-size:12px;margin-top:6px;">Batch: <strong>${inv.batch_code}</strong> | Pallet: <strong>${inv.pallet_code}</strong></div>
      </div>
    `;

    // Field Slot
    document.getElementById('drawerFieldSlot').innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <label style="font-size:11px;color:var(--text-muted);">Storage Bin Location</label>
          <input type="text" readonly value="${inv.storage_bin}" style="width:100%;padding:8px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;font-weight:600;">
        </div>
        <div>
          <label style="font-size:11px;color:var(--text-muted);">Expiration Date</label>
          <input type="text" readonly value="${inv.expiry_date} (${inv.days_to_expiry} days left)" style="width:100%;padding:8px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;font-weight:700;">
        </div>
        <div>
          <label style="font-size:11px;color:var(--text-muted);">Available Quantity</label>
          <input type="text" readonly value="${inv.available_quantity.toLocaleString()} ${inv.unit}" style="width:100%;padding:8px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;font-weight:800;color:var(--accent-navy);">
        </div>
        <div>
          <label style="font-size:11px;color:var(--text-muted);">Storage Temperature</label>
          <input type="text" readonly value="${inv.storage_temperature}" style="width:100%;padding:8px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;">
        </div>
      </div>
    `;

    // Info Slot
    document.getElementById('drawerInfoListSlot').innerHTML = `
      <div class="infolist-container" style="margin-top:14px;">
        <div class="infolist-row-item">
          <span>Production Date</span>
          <span>${inv.mfg_date}</span>
        </div>
        <div class="infolist-row-item">
          <span>Intake Date</span>
          <span>${inv.received_at}</span>
        </div>
        <div class="infolist-row-item">
          <span>Warehouse Auditor</span>
          <span>${inv.audited_by}</span>
        </div>
        <div class="infolist-row-item">
          <span>FEFO Priority</span>
          <span style="font-weight:700;color:${inv.days_to_expiry <= 15 ? '#DC2626' : '#059669'};">${inv.expiry_urgency}</span>
        </div>
      </div>
    `;

    drawer.classList.add('is-open');
    if (backdrop) backdrop.classList.add('is-visible');
  }

  async function selectDispatch(dispatchId) {
    const dsp = currentDispatches.find(d => d.id === dispatchId);
    if (!dsp) return;

    const drawer = document.getElementById('detailDrawerRoot');
    const backdrop = document.getElementById('drawerBackdrop');
    if (!drawer) return;

    document.getElementById('drawerRecordId').innerText = dsp.dispatch_code;

    // Visual Slot
    document.getElementById('drawerVisualSlot').innerHTML = `
      <div style="background:#0F172A;color:#FFF;padding:16px;border-radius:var(--radius-md);margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:12px;opacity:0.8;">COLD CHAIN DISPATCH ORDER</span>
          <span style="font-size:11px;padding:3px 8px;border-radius:4px;background:#059669;color:#FFF;font-weight:700;">
            ❄ ${dsp.temp_sensor_celsius}°C WITHIN SPEC
          </span>
        </div>
        <div style="font-size:16px;font-weight:800;margin-top:4px;">${dsp.customer_name}</div>
        <div style="font-size:12px;margin-top:4px;opacity:0.9;">Truck: <strong>${dsp.license_plate}</strong> • Driver: <strong>${dsp.driver_name}</strong> (${dsp.driver_phone})</div>
      </div>
    `;

    // Field Slot: Items Dispatched
    const items = dsp.items || [];
    let itemsHtml = `
      <div style="font-size:12px;font-weight:700;margin-bottom:8px;color:var(--text-secondary);">DISPATCHED FINISHED PRODUCTS</div>
      <div class="infolist-container">
        <div class="infolist-row-item" style="background:var(--bg-subtle);font-weight:700;">
          <span>Product / Batch</span>
          <span>Dispatch Quantity</span>
        </div>
        ${items.map(i => `
          <div class="infolist-row-item">
            <span><strong>${i.product_name}</strong> (Batch ${i.batch_code})</span>
            <span style="font-weight:700;color:var(--accent-navy);">${i.quantity.toLocaleString()} ${i.unit}</span>
          </div>
        `).join('')}
      </div>
    `;
    document.getElementById('drawerFieldSlot').innerHTML = itemsHtml;

    // Info Slot
    document.getElementById('drawerInfoListSlot').innerHTML = `
      <div class="infolist-container" style="margin-top:14px;">
        <div class="infolist-row-item">
          <span>Destination Address</span>
          <span style="max-width:240px;text-align:right;">${dsp.destination}</span>
        </div>
        <div class="infolist-row-item">
          <span>Departure Time</span>
          <span>${dsp.scheduled_departure || 'Today'}</span>
        </div>
        <div class="infolist-row-item">
          <span>Total Order Value</span>
          <span style="font-weight:700;color:var(--accent-navy);">${dsp.total_amount ? dsp.total_amount.toLocaleString() + ' VND' : 'N/A'}</span>
        </div>
        <div class="infolist-row-item">
          <span>Fulfillment Status</span>
          <span style="font-weight:700;">${dsp.status}</span>
        </div>
      </div>
    `;

    // Action button to complete delivery or void
    const saveBtn = document.querySelector('.btn-drawer-save');
    if (dsp.status === 'IN_TRANSIT') {
      drawer.__controller = {
        save: async () => {
          const resp = await fetch(`/api/warehouse/dispatches/${dsp.id}/advance-status`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ status: 'DELIVERED' })
          });
          const resData = await resp.json();
          if (resData.success) {
            FoodManApp.clearCardSelection();
            loadDispatches();
            alert("Order status updated to DELIVERED successfully!");
          }
        }
      };
      if (saveBtn) {
        saveBtn.style.display = 'inline-block';
        saveBtn.style.background = 'var(--accent-navy)';
        saveBtn.innerText = 'Confirm Delivered (DELIVERED)';
      }
    } else if (dsp.status === 'PENDING' || dsp.status === 'SCHEDULED') {
      drawer.__controller = {
        save: async () => {
          await voidDispatch(dsp.id);
        }
      };
      if (saveBtn) {
        saveBtn.style.display = 'inline-block';
        saveBtn.style.background = '#DC2626';
        saveBtn.innerText = 'Void Dispatch Order';
      }
    } else {
      if (saveBtn) saveBtn.style.display = 'none';
    }

    drawer.classList.add('is-open');
    if (backdrop) backdrop.classList.add('is-visible');
  }

  async function voidDispatch(dispatchId) {
    if (!confirm("Are you sure you want to void this dispatch order? This will cancel the shipment and return allocated inventory back to available stock.")) {
      return;
    }
    try {
      const resp = await fetch(`/api/warehouse/dispatches/${dispatchId}/void`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        throw new Error(data.error || "Failed to void dispatch order");
      }
      alert(data.message || "Dispatch order voided successfully.");
      const drawer = document.getElementById('detailDrawerRoot');
      const backdrop = document.getElementById('drawerBackdrop');
      if (drawer) drawer.classList.remove('is-open');
      if (backdrop) backdrop.classList.remove('is-visible');
      loadDispatches();
    } catch (e) {
      alert("Error: " + e.message);
    }
  }

  // ---------------------------------------------------------------------------
  // 4. Dispatch Creation Drawer & Live Decrement
  // ---------------------------------------------------------------------------
  async function openDispatchDrawer() {
    const panel = document.getElementById('dispatchDrawerPanel');
    const backdrop = document.getElementById('dispatchBackdrop');
    if (!panel) return;

    // Load customers and available inventory
    try {
      const [custResp, invResp] = await Promise.all([
        fetch('/api/warehouse/customers'),
        fetch('/api/warehouse/inventory')
      ]);

      const custData = await custResp.json();
      const invData = await invResp.json();

      if (custData.success) {
        currentCustomers = custData.data;
        const custSelect = document.getElementById('dispatchCustomerSelect');
        custSelect.innerHTML = '<option value="">-- Select receiving customer --</option>';
        custData.data.forEach(c => {
          const opt = document.createElement('option');
          opt.value = c.id;
          opt.innerText = `${c.name} (${c.city})`;
          custSelect.appendChild(opt);
        });
      }

      if (invData.success) {
        currentInventory = invData.data;
        const invSelect = document.getElementById('dispatchInventorySelect');
        invSelect.innerHTML = '<option value="">-- Select finished inventory lot --</option>';
        invData.data.forEach(i => {
          const opt = document.createElement('option');
          opt.value = i.id;
          opt.innerText = `${i.product_name} • Batch ${i.batch_code} (Available: ${i.available_quantity} ${i.unit} - EXP: ${i.expiry_date})`;
          invSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.error("Failed loading dispatch options", e);
    }

    panel.classList.add('is-open');
    if (backdrop) backdrop.classList.add('is-visible');
  }

  function closeDispatchDrawer() {
    const panel = document.getElementById('dispatchDrawerPanel');
    const backdrop = document.getElementById('dispatchBackdrop');
    if (panel) panel.classList.remove('is-open');
    if (backdrop) backdrop.classList.remove('is-visible');
  }

  async function submitDispatch() {
    const customerSelect = document.getElementById('dispatchCustomerSelect');
    const customerId = customerSelect ? customerSelect.value : '';
    const invSelect = document.getElementById('dispatchInventorySelect');
    const inventoryId = invSelect ? invSelect.value : '';
    const qtyInput = document.getElementById('dispatchQuantity');
    const quantity = qtyInput ? qtyInput.value : '';
    const licensePlate = document.getElementById('dispatchLicensePlate')?.value;
    const driverName = document.getElementById('dispatchDriverName')?.value;
    const notes = document.getElementById('dispatchNotes')?.value;

    if (!customerId) {
      if (window.FoodManAnimations) window.FoodManAnimations.shakeField(customerSelect);
      if (window.showToast) window.showToast("Validation Error", "Please select a destination customer!", "danger");
      else alert("Please select a destination customer!");
      return;
    }
    if (!inventoryId || !quantity || parseFloat(quantity) <= 0) {
      if (window.FoodManAnimations) window.FoodManAnimations.shakeField(!inventoryId ? invSelect : qtyInput);
      if (window.showToast) window.showToast("Validation Error", "Please select an inventory lot and enter a valid quantity!", "danger");
      else alert("Please select an inventory lot and enter a valid dispatch quantity!");
      return;
    }

    try {
      const resp = await fetch('/api/warehouse/dispatches', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          customer_id: parseInt(customerId),
          carrier_name: 'FoodMan Cold Chain Fleet',
          license_plate: licensePlate,
          driver_name: driverName,
          notes: notes,
          items: [
            {
              inventory_id: parseInt(inventoryId),
              quantity: parseFloat(quantity)
            }
          ]
        })
      });
      const data = await resp.json();
      if (data.success) {
        closeDispatchDrawer();
        sessionStorage.setItem('foodman_new_dispatch_created', 'true');
        if (window.showToast) window.showToast("Dispatch Created", data.message, "success");
        if (activeView === 'dispatches') {
          loadDispatches();
        } else {
          loadInventory();
        }
      } else {
        if (window.showToast) window.showToast("Dispatch Error", data.error, "danger");
        else alert("Dispatch error: " + data.error);
      }
    } catch (e) {
      console.error("Failed submitting dispatch", e);
    }
  }

  return {
    init,
    loadInventory,
    loadDispatches,
    loadCustomers,
    selectInventory,
    selectDispatch,
    selectCustomer,
    openDispatchDrawer,
    closeDispatchDrawer,
    openCustomerModal,
    closeCustomerModal,
    closeCustomerDrawer,
    submitCustomer,
    submitDispatch,
    voidDispatch
  };

})();

document.addEventListener('DOMContentLoaded', WarehouseApp.init);
