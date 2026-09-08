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
      loadDispatches();
    } else if (activeView === 'customers') {
      loadCustomers();
    } else {
      loadInventory();
    }
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

    if (countEl) countEl.innerText = `${items.length} Lô thành phẩm tồn kho (Sắp xếp FEFO: Cận hạn xếp trước)`;
    container.innerHTML = '';

    items.forEach(item => {
      let urgencyClass = 'urgency-fresh';
      let urgencyLabel = `Còn ${item.days_to_expiry} ngày`;

      if (item.expiry_urgency === 'EXPIRED') {
        urgencyClass = 'urgency-expired';
        urgencyLabel = '⚠ Đã hết hạn';
      } else if (item.expiry_urgency === 'EXPIRING_SOON') {
        urgencyClass = 'urgency-expiring-soon';
        urgencyLabel = `⚠ Cận hạn: Còn ${item.days_to_expiry} ngày`;
      } else if (item.expiry_urgency === 'ATTENTION') {
        urgencyClass = 'urgency-attention';
        urgencyLabel = `Chú ý: Còn ${item.days_to_expiry} ngày`;
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
            <span class="card-secondary-stat">HSD: ${item.expiry_date}</span>
            <div style="margin-top:4px;">
              <span class="urgency-pill ${urgencyClass}">${urgencyLabel}</span>
            </div>
          </div>
        </div>

        <div class="card-minigrid" style="margin-top:14px;">
          <div class="minigrid-cell">
            <span class="minigrid-label">Vị trí Bin lưu trữ</span>
            <span class="minigrid-val">${item.storage_bin}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Mã Pallet / Lô SX</span>
            <span class="minigrid-val">${item.pallet_code} • ${item.batch_code}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Tồn khả dụng / Tổng</span>
            <span class="minigrid-val" style="font-weight:800;color:var(--accent-navy);">
              ${item.available_quantity.toLocaleString()} / ${item.initial_quantity.toLocaleString()} ${item.unit}
            </span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Định giá tồn kho</span>
            <span class="minigrid-val">${(item.total_value / 1000000).toFixed(1)} Triệu VNĐ</span>
          </div>
        </div>

        <div class="card-footer-row" style="margin-top:14px;">
          <div class="avatar-stack">
            <div class="avatar-stack-item">WH</div>
            <div class="avatar-stack-item" style="background:#059669;">KHO</div>
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

    if (countEl) countEl.innerText = `${dispatches.length} Lệnh xuất kho & Chuyến xe lạnh đang vận hành`;
    container.innerHTML = '';

    dispatches.forEach(d => {
      const isDelivered = d.status === 'DELIVERED';
      const statusPillClass = isDelivered ? 'status-pill-approved' : 'status-pill-pending';
      const statusDotClass = isDelivered ? 'dot-approved' : 'dot-pending';
      const statusLabel = isDelivered ? 'Đã giao hàng (DELIVERED)' : 'Đang vận chuyển (IN_TRANSIT)';

      const card = document.createElement('div');
      card.className = 'record-card';
      card.onclick = () => selectDispatch(d.id);

      card.innerHTML = `
        <div class="card-header-row">
          <div>
            <span class="card-id-badge" style="background:#EEF3FA;color:var(--accent-navy);">${d.dispatch_code}</span>
            <span class="card-title-text" style="display:block;margin-top:4px;font-weight:700;font-size:14px;">${d.customer_name}</span>
          </div>
          <span class="card-secondary-stat">${d.total_packages.toLocaleString()} Thùng</span>
        </div>

        <div class="card-minigrid" style="margin-top:14px;">
          <div class="minigrid-cell">
            <span class="minigrid-label">Đội xe & Biển số</span>
            <span class="minigrid-val">${d.license_plate} (${d.driver_name})</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Cảm biến nhiệt độ xe</span>
            <span class="minigrid-val" style="font-weight:700;color:#059669;">
              ❄ ${d.temp_sensor_celsius}°C (Chuẩn: ${d.temp_spec_range})
            </span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Điểm giao hàng</span>
            <span class="minigrid-val" style="font-size:11.5px;">${d.destination}</span>
          </div>
          <div class="minigrid-cell">
            <span class="minigrid-label">Giờ xuất phát</span>
            <span class="minigrid-val">${d.scheduled_departure || 'Hôm nay'}</span>
          </div>
        </div>

        <div class="card-footer-row" style="margin-top:14px;">
          <div class="avatar-stack">
            <div class="avatar-stack-item">TX</div>
            <div class="avatar-stack-item" style="background:#D97706;">DP</div>
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
        <div style="font-size:12px;opacity:0.8;">TỒN KHO THÀNH PHẨM (FEFO)</div>
        <div style="font-size:16px;font-weight:800;margin-top:2px;">${inv.product_name}</div>
        <div style="font-size:12px;margin-top:6px;">Lô sản xuất: <strong>${inv.batch_code}</strong> | Pallet: <strong>${inv.pallet_code}</strong></div>
      </div>
    `;

    // Field Slot
    document.getElementById('drawerFieldSlot').innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <label style="font-size:11px;color:var(--text-muted);">Vị trí lưu kho (Bin)</label>
          <input type="text" readonly value="${inv.storage_bin}" style="width:100%;padding:8px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;font-weight:600;">
        </div>
        <div>
          <label style="font-size:11px;color:var(--text-muted);">Hạn sử dụng</label>
          <input type="text" readonly value="${inv.expiry_date} (Còn ${inv.days_to_expiry} ngày)" style="width:100%;padding:8px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;font-weight:700;">
        </div>
        <div>
          <label style="font-size:11px;color:var(--text-muted);">Số lượng khả dụng</label>
          <input type="text" readonly value="${inv.available_quantity.toLocaleString()} ${inv.unit}" style="width:100%;padding:8px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;font-weight:800;color:var(--accent-navy);">
        </div>
        <div>
          <label style="font-size:11px;color:var(--text-muted);">Nhiệt độ bảo quản</label>
          <input type="text" readonly value="${inv.storage_temperature}" style="width:100%;padding:8px;border:1px solid var(--border-subtle);border-radius:4px;background:#F9FAFB;">
        </div>
      </div>
    `;

    // Info Slot
    document.getElementById('drawerInfoListSlot').innerHTML = `
      <div class="infolist-container" style="margin-top:14px;">
        <div class="infolist-row-item">
          <span>Ngày sản xuất</span>
          <span>${inv.mfg_date}</span>
        </div>
        <div class="infolist-row-item">
          <span>Ngày nhập kho</span>
          <span>${inv.received_at}</span>
        </div>
        <div class="infolist-row-item">
          <span>Thủ kho xác nhận</span>
          <span>${inv.audited_by}</span>
        </div>
        <div class="infolist-row-item">
          <span>Ưu tiên FEFO</span>
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
          <span style="font-size:12px;opacity:0.8;">LỆNH VẬN TẢI LẠNH</span>
          <span style="font-size:11px;padding:3px 8px;border-radius:4px;background:#059669;color:#FFF;font-weight:700;">
            ❄ ${dsp.temp_sensor_celsius}°C ĐẠT CHUẨN
          </span>
        </div>
        <div style="font-size:16px;font-weight:800;margin-top:4px;">${dsp.customer_name}</div>
        <div style="font-size:12px;margin-top:4px;opacity:0.9;">Xe: <strong>${dsp.license_plate}</strong> • Tài xế: <strong>${dsp.driver_name}</strong> (${dsp.driver_phone})</div>
      </div>
    `;

    // Field Slot: Items Dispatched
    const items = dsp.items || [];
    let itemsHtml = `
      <div style="font-size:12px;font-weight:700;margin-bottom:8px;color:var(--text-secondary);">DANH MỤC THÀNH PHẨM XUẤT KHO</div>
      <div class="infolist-container">
        <div class="infolist-row-item" style="background:var(--bg-subtle);font-weight:700;">
          <span>Sản phẩm / Lô</span>
          <span>Số lượng xuất</span>
        </div>
        ${items.map(i => `
          <div class="infolist-row-item">
            <span><strong>${i.product_name}</strong> (Lô ${i.batch_code})</span>
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
          <span>Địa chỉ nhận</span>
          <span style="max-width:240px;text-align:right;">${dsp.destination}</span>
        </div>
        <div class="infolist-row-item">
          <span>Giờ xuất bến</span>
          <span>${dsp.scheduled_departure || 'Hôm nay'}</span>
        </div>
        <div class="infolist-row-item">
          <span>Tổng giá trị đơn</span>
          <span style="font-weight:700;color:var(--accent-navy);">${(dsp.total_amount / 1000000).toFixed(1)} Triệu VNĐ</span>
        </div>
        <div class="infolist-row-item">
          <span>Trạng thái giao nhận</span>
          <span style="font-weight:700;">${dsp.status}</span>
        </div>
      </div>
    `;

    // Action button to complete delivery
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
            alert("Đã cập nhật trạng thái đơn thành DELIVERED (Đã giao hàng thành công)!");
          }
        }
      };
      document.querySelector('.btn-drawer-save').innerText = 'Xác nhận Đã giao hàng (DELIVERED)';
    }

    drawer.classList.add('is-open');
    if (backdrop) backdrop.classList.add('is-visible');
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
        custSelect.innerHTML = '<option value="">-- Chọn khách hàng nhận hàng --</option>';
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
        invSelect.innerHTML = '<option value="">-- Chọn lô thành phẩm tồn kho --</option>';
        invData.data.forEach(i => {
          const opt = document.createElement('option');
          opt.value = i.id;
          opt.innerText = `${i.product_name} • Lô ${i.batch_code} (Còn ${i.available_quantity} ${i.unit} - HSD: ${i.expiry_date})`;
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
    const customerId = document.getElementById('dispatchCustomerSelect')?.value;
    const inventoryId = document.getElementById('dispatchInventorySelect')?.value;
    const quantity = document.getElementById('dispatchQuantity')?.value;
    const licensePlate = document.getElementById('dispatchLicensePlate')?.value;
    const driverName = document.getElementById('dispatchDriverName')?.value;
    const notes = document.getElementById('dispatchNotes')?.value;

    if (!customerId) {
      alert("Vui lòng chọn khách hàng nhận!");
      return;
    }
    if (!inventoryId || !quantity || parseFloat(quantity) <= 0) {
      alert("Vui lòng chọn lô tồn kho và số lượng xuất hợp lệ!");
      return;
    }

    try {
      const resp = await fetch('/api/warehouse/dispatches', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          customer_id: parseInt(customerId),
          carrier_name: 'Đội xe lạnh Nhà Máy FoodMan',
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
        if (activeView === 'dispatches') {
          loadDispatches();
        } else {
          loadInventory();
        }
        alert(data.message);
      } else {
        alert("Lỗi xuất kho: " + data.error);
      }
    } catch (e) {
      console.error("Failed submitting dispatch", e);
    }
  }

  return {
    init,
    loadInventory,
    loadDispatches,
    selectInventory,
    selectDispatch,
    openDispatchDrawer,
    closeDispatchDrawer,
    submitDispatch
  };

})();

document.addEventListener('DOMContentLoaded', WarehouseApp.init);
