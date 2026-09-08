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

  function init(view) {
    activeView = view || 'lots';
    drawer = new FoodManComponents.DetailDrawerController('detailDrawerRoot', 'drawerBackdrop');
    
    setupFilterTabs();
    setupSearch();
    loadAuxiliaryData();
    loadViewData(activeView);
    updatePendingQcBadge();
  }

  function setupFilterTabs() {
    document.querySelectorAll('.tab-pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const status = btn.dataset.status;
        filterAndRenderCards(status);
      });
    });
  }

  function setupSearch() {
    const searchInput = document.getElementById('topbarSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        filterAndRenderCards(null, q);
      });
    }
  }

  async function loadAuxiliaryData() {
    try {
      const [supRes, matRes, poRes] = await Promise.all([
        fetch('/api/procurement/suppliers'),
        fetch('/api/procurement/raw-materials'),
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
        Đang tải dữ liệu ${view}...
      </div>
    `;

    try {
      let url = '/api/procurement/lots';
      if (view === 'suppliers') url = '/api/procurement/suppliers';
      else if (view === 'raw-materials') url = '/api/procurement/raw-materials';
      else if (view === 'po') url = '/api/procurement/purchase-orders';
      else if (view === 'grn') url = '/api/procurement/grn';

      const res = await fetch(url);
      if (!res.ok) throw new Error("Lỗi khi tải dữ liệu");
      const json = await res.json();

      if (view === 'lots') {
        currentItems = json.cards || [];
      } else {
        currentItems = json.data || [];
      }

      const countBadge = document.getElementById('procurementCountBadge');
      if (countBadge) countBadge.textContent = `${currentItems.length} bản ghi`;

      filterAndRenderCards('ALL');
    } catch (err) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #DC2626;">
          Không thể tải dữ liệu: ${err.message}
        </div>
      `;
    }
  }

  function filterAndRenderCards(statusFilter, searchKeyword) {
    const container = document.getElementById('procurementCardsContainer');
    if (!container) return;

    let filtered = [...currentItems];

    if (statusFilter && statusFilter !== 'ALL') {
      filtered = filtered.filter(item => (item.qc_status || item.status) === statusFilter);
    }

    if (searchKeyword) {
      filtered = filtered.filter(item => {
        const str = `${item.id || ''} ${item.code || ''} ${item.name || ''} ${item.title || ''} ${item.po_number || ''} ${item.grn_number || ''}`.toLowerCase();
        return str.includes(searchKeyword);
      });
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--border-subtle);">
          <div style="font-size: 15px; font-weight: 700; color: var(--text-main);">Chưa có bản ghi nào phù hợp</div>
          <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">Vui lòng thêm mới hoặc đổi tiêu chí tìm kiếm.</div>
        </div>
      `;
      return;
    }

    if (activeView === 'lots') {
      container.innerHTML = filtered.map(card => FoodManComponents.RecordCard({
        ...card,
        onClick: () => openLotDrawer(card)
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
  }

  // Card renderers for other procurement views
  function renderSupplierCard(s) {
    return `
      <div class="record-card-box" onclick="ProcurementModule.selectSupplier(${s.id})">
        <div class="card-top-row">
          <div class="card-title-col">
            <div><span class="card-id-badge">${s.code}</span><span class="card-category-sub">Nhà cung cấp</span></div>
            <h3 class="card-main-title">${s.name}</h3>
          </div>
          <div class="card-stat-widget">
            <span class="card-stat-number">${s.rating} ★</span>
            <span class="card-stat-caption">Đánh giá</span>
          </div>
        </div>
        <div class="card-mini-grid-layout">
          <div class="grid-cell-item"><span class="cell-label-text">Người liên hệ</span><span class="cell-value-text">${s.contact_name}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Điện thoại</span><span class="cell-value-text">${s.phone}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Email</span><span class="cell-value-text">${s.email}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Địa chỉ</span><span class="cell-value-text">${s.address}</span></div>
        </div>
        <div class="card-footer-slot">
          <div class="avatar-stack-slot"><div class="avatar-stack-disc" style="background:#162B4E;">NCC</div></div>
          ${FoodManComponents.StatusPill("APPROVED", "Đối tác xác thực")}
        </div>
      </div>
    `;
  }

  function renderRawMaterialCard(m) {
    return `
      <div class="record-card-box" onclick="ProcurementModule.selectRawMaterial(${m.id})">
        <div class="card-top-row">
          <div class="card-title-col">
            <div><span class="card-id-badge">${m.code}</span><span class="card-category-sub">${m.category}</span></div>
            <h3 class="card-main-title">${m.name}</h3>
          </div>
          <div class="card-stat-widget">
            <span class="card-stat-number">${m.standard_unit}</span>
            <span class="card-stat-caption">Đơn vị chuẩn</span>
          </div>
        </div>
        <div class="card-mini-grid-layout">
          <div class="grid-cell-item"><span class="cell-label-text">Quy cách bao gói</span><span class="cell-value-text">${m.unit_weight}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Điều kiện lưu kho</span><span class="cell-value-text">${m.storage_temp}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Hạn dùng</span><span class="cell-value-text">${m.shelf_life_days} ngày</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Ngưỡng tối thiểu</span><span class="cell-value-text">${m.min_stock_level} ${m.standard_unit}</span></div>
        </div>
        <div class="card-footer-slot">
          <div class="avatar-stack-slot"><div class="avatar-stack-disc" style="background:#0D9488;">RM</div></div>
          ${FoodManComponents.StatusPill("APPROVED", "Đang lưu hành")}
        </div>
      </div>
    `;
  }

  function renderPurchaseOrderCard(p) {
    const itemsPreview = p.items.map(i => `${i.material_name}: ${i.quantity_ordered} ${i.unit}`).join(', ');
    return `
      <div class="record-card-box" onclick="ProcurementModule.selectPo(${p.id})">
        <div class="card-top-row">
          <div class="card-title-col">
            <div><span class="card-id-badge">${p.po_number}</span><span class="card-category-sub">Purchase Order</span></div>
            <h3 class="card-main-title">${p.supplier_name}</h3>
          </div>
          <div class="card-stat-widget">
            <span class="card-stat-number">${(p.total_amount || 0).toLocaleString()} VNĐ</span>
            <span class="card-stat-caption">${p.items_count} mặt hàng</span>
          </div>
        </div>
        <div class="card-mini-grid-layout">
          <div class="grid-cell-item"><span class="cell-label-text">Ngày đặt hàng</span><span class="cell-value-text">${p.order_date}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Dự kiến giao</span><span class="cell-value-text">${p.expected_delivery_date}</span></div>
          <div class="grid-cell-item" style="grid-column:1/-1;"><span class="cell-label-text">Chi tiết các dòng hàng</span><span class="cell-value-text">${itemsPreview || 'Chưa có mặt hàng'}</span></div>
        </div>
        <div class="card-footer-slot">
          <div class="avatar-stack-slot"><div class="avatar-stack-disc" style="background:#2563EB;">PO</div></div>
          ${FoodManComponents.StatusPill(p.status === 'COMPLETED' ? 'APPROVED' : 'PENDING', p.status === 'COMPLETED' ? 'Đã nhận đủ hàng' : 'Đang thực hiện')}
        </div>
      </div>
    `;
  }

  function renderGrnCard(g) {
    return `
      <div class="record-card-box" onclick="alert('Phiếu nhập kho: ${g.grn_number} theo đơn ${g.po_number}')">
        <div class="card-top-row">
          <div class="card-title-col">
            <div><span class="card-id-badge">${g.grn_number}</span><span class="card-category-sub">Goods Receipt Note</span></div>
            <h3 class="card-main-title">${g.supplier_name}</h3>
          </div>
          <div class="card-stat-widget">
            <span class="card-stat-number">${g.items_count} mặt hàng</span>
            <span class="card-stat-caption">Đã nhập kho</span>
          </div>
        </div>
        <div class="card-mini-grid-layout">
          <div class="grid-cell-item"><span class="cell-label-text">Đơn mua hàng PO</span><span class="cell-value-text">${g.po_number}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Ngày giờ nhập</span><span class="cell-value-text">${g.received_date}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Biển số xe</span><span class="cell-value-text">${g.truck_plate}</span></div>
          <div class="grid-cell-item"><span class="cell-label-text">Số vận đơn / Phiếu</span><span class="cell-value-text">${g.delivery_note_ref}</span></div>
        </div>
        <div class="card-footer-slot">
          <div class="avatar-stack-slot"><div class="avatar-stack-disc" style="background:#059669;">GRN</div></div>
          ${FoodManComponents.StatusPill("APPROVED", "Đã tạo lô QC")}
        </div>
      </div>
    `;
  }

  // Drawer Opening for Lot Selection
  function openLotDrawer(card) {
    drawer.open(card, async (item, newStatus) => {
      const matName = document.getElementById('drawer_input_material_name')?.value;
      const supName = document.getElementById('drawer_input_supplier_name')?.value;
      const unit = document.getElementById('drawer_input_unit')?.value;
      const storage = document.getElementById('drawer_input_storage_condition')?.value;

      try {
        const res = await fetch(`/api/procurement/lots/${item.db_id}`, {
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
        if (!res.ok) throw new Error("Cập nhật thất bại");
        drawer.close();
        loadViewData('lots');
        updatePendingQcBadge();
        alert(`Đã cập nhật thành công lô ${item.id}`);
      } catch (err) {
        alert(err.message);
      }
    });
  }

  // Drawer Opening for Supplier Selection
  function selectSupplier(id) {
    const s = currentItems.find(item => item.id === id);
    if (!s) return;
    drawer.open({
      id: s.code,
      title: s.name,
      category: "NHÀ CUNG CẤP",
      headerStat: `${s.rating} ★`,
      statSub: "Đánh giá uy tín",
      editableFields: [
        { label: "Tên nhà cung cấp", key: "name", type: "text", value: s.name },
        { label: "Người liên hệ", key: "contact_name", type: "text", value: s.contact_name },
        { label: "Số điện thoại", key: "phone", type: "text", value: s.phone },
        { label: "Email", key: "email", type: "text", value: s.email }
      ],
      readonlySpecs: [
        { label: "Địa chỉ trụ sở", value: s.address },
        { label: "Tổng số đơn đã ký", value: `${s.po_count} đơn PO` },
        { label: "Xác thực chất lượng", value: "HACCP & ISO 22000 Approved" }
      ]
    }, async (item) => {
      const name = document.getElementById('drawer_input_name')?.value;
      const contact = document.getElementById('drawer_input_contact_name')?.value;
      const phone = document.getElementById('drawer_input_phone')?.value;
      const email = document.getElementById('drawer_input_email')?.value;

      await fetch(`/api/procurement/suppliers/${s.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, contact_name: contact, phone, email })
      });
      drawer.close();
      loadViewData('suppliers');
    });
  }

  // Drawer Opening for Raw Material Selection
  function selectRawMaterial(id) {
    const m = currentItems.find(item => item.id === id);
    if (!m) return;
    drawer.open({
      id: m.code,
      title: m.name,
      category: m.category,
      headerStat: m.standard_unit,
      statSub: "Đơn vị đo lường",
      editableFields: [
        { label: "Tên nguyên vật liệu", key: "name", type: "text", value: m.name },
        { label: "Phân loại", key: "category", type: "text", value: m.category },
        { label: "Nhiệt độ lưu kho", key: "storage_temp", type: "text", value: m.storage_temp },
        { label: "Quy cách đóng gói", key: "unit_weight", type: "text", value: m.unit_weight }
      ],
      readonlySpecs: [
        { label: "Hạn sử dụng", value: `${m.shelf_life_days} ngày` },
        { label: "Tồn kho tối thiểu", value: `${m.min_stock_level} ${m.standard_unit}` },
        { label: "Tiêu chuẩn tiếp nhận", value: "QCVN 5-1:2010/BYT" }
      ]
    }, async (item) => {
      const name = document.getElementById('drawer_input_name')?.value;
      const category = document.getElementById('drawer_input_category')?.value;
      const storage_temp = document.getElementById('drawer_input_storage_temp')?.value;
      const unit_weight = document.getElementById('drawer_input_unit_weight')?.value;

      await fetch(`/api/procurement/raw-materials/${m.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, category, storage_temp, unit_weight })
      });
      drawer.close();
      loadViewData('raw-materials');
    });
  }

  function selectPo(id) {
    const p = currentItems.find(item => item.id === id);
    if (!p) return;
    alert(`Đơn đặt hàng: ${p.po_number}\nNhà cung cấp: ${p.supplier_name}\nTổng tiền: ${p.total_amount.toLocaleString()} VNĐ\nSố mặt hàng: ${p.items_count}`);
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

    const matOpts = materialsList.map(m => `<option value="${m.id}" data-unit="${m.standard_unit}">${m.name} (${m.code})</option>`).join('');

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
        <input type="number" class="field-slot-input" style="font-size:12px;padding:6px 8px;" value="10" min="0.1" step="0.1" onchange="ProcurementModule.recalculatePoTotal()">
      </td>
      <td style="padding:8px 4px;">
        <span class="po-row-unit" style="font-size:12px;color:var(--text-secondary);font-weight:600;">Tấn</span>
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
    const unit = selectedOpt.getAttribute('data-unit') || 'Tấn';
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
    if (totalEl) totalEl.textContent = `${total.toLocaleString()} VNĐ`;
  }

  async function submitPurchaseOrder() {
    const supplierId = document.getElementById('poSupplierSelect').value;
    const expectedDate = document.getElementById('poExpectedDate').value;
    const notes = document.getElementById('poNotes').value;

    const rows = document.querySelectorAll('#poItemsTableBody tr');
    if (rows.length === 0) {
      alert("Vui lòng thêm ít nhất 1 dòng mặt hàng!");
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
          unit: unitSpan ? unitSpan.textContent : 'Tấn'
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

      if (!res.ok) throw new Error("Tạo đơn mua hàng thất bại");
      const result = await res.json();
      closePoBuilder();
      alert(`Đã tạo thành công đơn hàng ${result.data.po_number}!`);
      loadAuxiliaryData();
      if (activeView === 'po') loadViewData('po');
    } catch (err) {
      alert(`Lỗi: ${err.message}`);
    }
  }

  // GRN Receipt Modal Methods
  function openGrn() {
    const poSelect = document.getElementById('grnPoSelect');
    if (poSelect) {
      poSelect.innerHTML = `<option value="">-- Chọn đơn hàng PO cần nhập --</option>` + 
        posList.map(p => `<option value="${p.id}">${p.po_number} - ${p.supplier_name} (${p.status})</option>`).join('');
    }
    document.getElementById('grnItemsContainer').innerHTML = '<div style="font-size:12px;color:var(--text-muted);">Vui lòng chọn đơn hàng PO ở trên.</div>';
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
      container.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">Vui lòng chọn đơn hàng PO ở trên.</div>';
      return;
    }
    const po = posList.find(p => p.id === parseInt(poId));
    if (!po || !po.items || po.items.length === 0) {
      container.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">Đơn hàng này chưa có dòng hàng chi tiết.</div>';
      return;
    }

    container.innerHTML = po.items.map(item => `
      <div class="grn-line-item-box" data-po-item-id="${item.id}" data-raw-material-id="${item.raw_material_id}" style="background:#F8FAFC;border:1px solid var(--border-subtle);border-radius:8px;padding:12px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
          <strong style="color:var(--text-main);font-size:13px;">${item.material_name}</strong>
          <span style="font-size:12px;color:var(--text-muted);">Đã đặt: ${item.quantity_ordered} ${item.unit} (Đã nhận: ${item.quantity_received} ${item.unit})</span>
        </div>
        <div class="field-slot-grid">
          <div class="field-slot-group">
            <label class="field-slot-label">Số lượng thực nhận *</label>
            <input type="number" class="field-slot-input grn-item-qty" value="${Math.max(item.quantity_ordered - item.quantity_received, 1)}" step="0.1">
          </div>
          <div class="field-slot-group">
            <label class="field-slot-label">Đơn vị & Quy cách</label>
            <input type="text" class="field-slot-input grn-item-unit" value="${item.unit}" readonly>
          </div>
        </div>
      </div>
    `).join('');
  }

  async function submitGoodsReceipt() {
    const poId = document.getElementById('grnPoSelect').value;
    if (!poId) {
      alert("Vui lòng chọn đơn hàng PO!");
      return;
    }
    const truckPlate = document.getElementById('grnTruckPlate').value;
    const deliveryNote = document.getElementById('grnDeliveryNote').value;

    const boxes = document.querySelectorAll('.grn-line-item-box');
    if (boxes.length === 0) {
      alert("Không có mặt hàng nào để nhập kho!");
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
          unit: unitInput ? unitInput.value : 'Tấn'
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

      if (!res.ok) throw new Error("Nhập kho GRN thất bại");
      const result = await res.json();
      closeGrn();

      alert(`THÀNH CÔNG!\n${result.message}\nCác lô mới được tạo: ${result.generated_lots.join(', ')} với trạng thái PENDING_QC.`);

      // Update badge & refresh view
      updatePendingQcBadge();
      loadAuxiliaryData();
      if (activeView === 'lots') {
        loadViewData('lots');
      } else if (activeView === 'grn') {
        loadViewData('grn');
      }
    } catch (err) {
      alert(`Lỗi: ${err.message}`);
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
    if (!name) return alert("Vui lòng nhập tên nhà cung cấp");
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
    if (!name) return alert("Vui lòng nhập tên nguyên vật liệu");
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
    selectSupplier,
    selectRawMaterial,
    selectPo,
    handlePoMaterialChange,
    recalculatePoTotal,
    addPoItemRow
  };
})();

// Global helpers for inline HTML event handlers
window.openPoBuilderModal = () => ProcurementModule.openPoBuilder ? ProcurementModule.openPoBuilder() : document.getElementById('poModalPanel')?.classList.add('open') || document.getElementById('poModalBackdrop')?.classList.add('show');
window.closePoBuilderModal = () => { document.getElementById('poModalPanel')?.classList.remove('open'); document.getElementById('poModalBackdrop')?.classList.remove('show'); };
window.addPoItemRow = () => ProcurementModule.addPoItemRow();
window.submitPurchaseOrder = () => ProcurementModule.submitPurchaseOrder ? ProcurementModule.submitPurchaseOrder() : null;

window.openGrnModal = () => {
  const poSelect = document.getElementById('grnPoSelect');
  fetch('/api/procurement/purchase-orders').then(r => r.json()).then(data => {
    if (poSelect) {
      poSelect.innerHTML = `<option value="">-- Chọn đơn hàng PO cần nhập --</option>` + 
        (data.data || []).map(p => `<option value="${p.id}">${p.po_number} - ${p.supplier_name} (${p.status})</option>`).join('');
    }
  });
  document.getElementById('grnModalBackdrop')?.classList.add('show');
  document.getElementById('grnModalPanel')?.classList.add('open');
};
window.closeGrnModal = () => { document.getElementById('grnModalBackdrop')?.classList.remove('show'); document.getElementById('grnModalPanel')?.classList.remove('open'); };
window.loadGrnPoItems = (val) => {
  fetch('/api/procurement/purchase-orders').then(r => r.json()).then(data => {
    const po = (data.data || []).find(p => p.id === parseInt(val));
    const container = document.getElementById('grnItemsContainer');
    if (!po || !po.items) return;
    container.innerHTML = po.items.map(item => `
      <div class="grn-line-item-box" data-po-item-id="${item.id}" data-raw-material-id="${item.raw_material_id}" style="background:#F8FAFC;border:1px solid var(--border-subtle);border-radius:8px;padding:12px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
          <strong style="color:var(--text-main);font-size:13px;">${item.material_name}</strong>
          <span style="font-size:12px;color:var(--text-muted);">Đã đặt: ${item.quantity_ordered} ${item.unit} (Đã nhận: ${item.quantity_received} ${item.unit})</span>
        </div>
        <div class="field-slot-grid">
          <div class="field-slot-group">
            <label class="field-slot-label">Số lượng thực nhận *</label>
            <input type="number" class="field-slot-input grn-item-qty" value="${Math.max(item.quantity_ordered - item.quantity_received, 1)}" step="0.1">
          </div>
          <div class="field-slot-group">
            <label class="field-slot-label">Đơn vị & Quy cách</label>
            <input type="text" class="field-slot-input grn-item-unit" value="${item.unit}" readonly>
          </div>
        </div>
      </div>
    `).join('');
  });
};
window.submitGoodsReceipt = async () => {
  const poId = document.getElementById('grnPoSelect').value;
  if (!poId) return alert("Vui lòng chọn đơn hàng PO!");
  const truckPlate = document.getElementById('grnTruckPlate').value;
  const deliveryNote = document.getElementById('grnDeliveryNote').value;
  const boxes = document.querySelectorAll('.grn-line-item-box');
  const items = [];
  boxes.forEach(b => {
    items.push({
      purchase_order_item_id: parseInt(b.getAttribute('data-po-item-id')),
      raw_material_id: parseInt(b.getAttribute('data-raw-material-id')),
      quantity_received: parseFloat(b.querySelector('.grn-item-qty')?.value) || 0,
      unit: b.querySelector('.grn-item-unit')?.value || 'Tấn'
    });
  });

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
  if (res.ok) {
    const data = await res.json();
    window.closeGrnModal();
    alert(`THÀNH CÔNG!\n${data.message}`);
    window.location.href = '/procurement?view=lots';
  } else {
    alert("Nhập kho thất bại");
  }
};

window.openSupplierModal = () => { document.getElementById('supModalBackdrop')?.classList.add('show'); document.getElementById('supModalPanel')?.classList.add('open'); };
window.closeSupplierModal = () => { document.getElementById('supModalBackdrop')?.classList.remove('show'); document.getElementById('supModalPanel')?.classList.remove('open'); };
window.submitNewSupplier = async () => {
  const name = document.getElementById('newSupName').value.trim();
  if (!name) return alert("Vui lòng nhập tên nhà cung cấp");
  await fetch('/api/procurement/suppliers', {
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
  window.closeSupplierModal();
  window.location.reload();
};

window.openRawMaterialModal = () => { document.getElementById('matModalBackdrop')?.classList.add('show'); document.getElementById('matModalPanel')?.classList.add('open'); };
window.closeRawMaterialModal = () => { document.getElementById('matModalBackdrop')?.classList.remove('show'); document.getElementById('matModalPanel')?.classList.remove('open'); };
window.submitNewRawMaterial = async () => {
  const name = document.getElementById('newMatName').value.trim();
  if (!name) return alert("Vui lòng nhập tên nguyên vật liệu");
  await fetch('/api/procurement/raw-materials', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      category: document.getElementById('newMatCategory').value,
      standard_unit: document.getElementById('newMatUnit').value,
      storage_temp: document.getElementById('newMatTemp').value,
      shelf_life_days: document.getElementById('newMatShelfLife').value
    })
  });
  window.closeRawMaterialModal();
  window.location.reload();
};

// Wire submit PO
window.submitPurchaseOrder = async () => {
  const supplierId = document.getElementById('poSupplierSelect').value;
  const expectedDate = document.getElementById('poExpectedDate').value;
  const notes = document.getElementById('poNotes').value;
  const rows = document.querySelectorAll('#poItemsTableBody tr');
  if (rows.length === 0) return alert("Vui lòng thêm ít nhất 1 dòng mặt hàng!");

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
        unit: unitSpan ? unitSpan.textContent : 'Tấn'
      });
    }
  });

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
  if (res.ok) {
    const data = await res.json();
    window.closePoBuilderModal();
    alert(`Đã tạo thành công đơn hàng ${data.data.po_number}!`);
    window.location.href = '/procurement?view=po';
  } else {
    alert("Tạo đơn hàng thất bại");
  }
};
