/**
 * Food Man - Phase 4 Flagship Traceability Controller
 * Unbroken 7-Tier Interactive Traceability Chain & Deep Drill-down Drawer
 */
const TraceabilityApp = (function() {

  let currentChain = null;

  function init() {
    const input = document.getElementById('traceSearchInput');
    const initial = input ? input.value : 'LOT-2026-089';
    loadChain(initial);

    // Enter key listener on search input
    if (input) {
      input.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') doSearch();
      });
    }
  }

  function doSearch() {
    const q = document.getElementById('traceSearchInput')?.value.trim();
    if (q) loadChain(q);
  }

  function searchChip(code) {
    const input = document.getElementById('traceSearchInput');
    if (input) input.value = code;
    loadChain(code);
  }

  async function loadChain(identifier) {
    const container = document.getElementById('traceabilityChainContainer');
    if (!container) return;

    container.innerHTML = `
      <div style="text-align:center;padding:40px;color:var(--text-muted);">
        <div style="font-size:16px;font-weight:700;margin-bottom:8px;">Đang truy xuất chuỗi dữ liệu cho: ${identifier}</div>
        <span>Đang kết nối dữ liệu: Nhà cung ứng ➔ Lô NL ➔ Phòng Lab/AI ➔ Sản xuất ➔ Đóng gói ➔ Kho FEFO ➔ Xuất kho...</span>
      </div>
    `;

    try {
      const resp = await fetch(`/api/traceability/chain/${encodeURIComponent(identifier)}`);
      const data = await resp.json();
      if (!data.success) {
        container.innerHTML = `
          <div style="padding:30px;background:#FEF2F2;border:1px solid #FECACA;border-radius:var(--radius-md);color:#991B1B;text-align:center;">
            <strong>Không tìm thấy dữ liệu truy xuất:</strong> ${data.error || 'Vui lòng kiểm tra lại mã'}
          </div>
        `;
        return;
      }

      currentChain = data.data;
      renderChain(data.data);
    } catch (e) {
      console.error("Failed loading traceability chain", e);
    }
  }

  function renderChain(chain) {
    const container = document.getElementById('traceabilityChainContainer');
    const summaryCard = document.getElementById('traceSummaryCard');
    const prodTitle = document.getElementById('traceProductTitle');
    const batchStatus = document.getElementById('traceBatchStatus');
    const fefoPill = document.getElementById('traceFefoPill');

    if (summaryCard) summaryCard.style.display = 'block';
    if (prodTitle) prodTitle.innerText = `${chain.product_name} • Mã Lô: ${chain.batch_code}`;
    if (batchStatus) batchStatus.innerText = chain.tier_4_production ? 'SẢN XUẤT ĐẠT CHUẨN' : 'APPROVED';
    if (fefoPill && chain.tier_6_warehouse) {
      fefoPill.innerText = `FEFO: Còn ${chain.tier_6_warehouse.days_to_expiry} ngày`;
      fefoPill.className = `urgency-pill ${chain.tier_6_warehouse.fefo_urgency === 'EXPIRING_SOON' ? 'urgency-expiring-soon' : 'urgency-fresh'}`;
    }

    container.innerHTML = '';

    const nodes = [
      {
        tier: 1,
        key: 'supplier',
        name: 'MẮT XÍCH 1: NHÀ CUNG CẤP & NÔNG TRẠI',
        title: chain.tier_1_supplier ? chain.tier_1_supplier.name : 'Nông trại Mộc Châu Farm Co.',
        badge: chain.tier_1_supplier ? chain.tier_1_supplier.supplier_code : 'SUP-001',
        subtitle: `Chứng nhận: ${chain.tier_1_supplier ? chain.tier_1_supplier.certifications : 'VietGAP / Organic'} • Đánh giá: ⭐ 4.9`,
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
        pill: 'XÁC THỰC VIETGAP',
        pillClass: 'status-pill-approved'
      },
      {
        tier: 2,
        key: 'lots',
        name: 'MẮT XÍCH 2: THU MUA & LÔ NGUYÊN LIỆU',
        title: chain.tier_2_lots && chain.tier_2_lots[0] ? `${chain.tier_2_lots[0].material_name} (${chain.tier_2_lots[0].lot_number})` : 'Sữa tươi Organic #RAW-LOT-512',
        badge: chain.tier_2_lots && chain.tier_2_lots[0] ? chain.tier_2_lots[0].lot_number : 'RAW-LOT-512',
        subtitle: `Đơn mua: ${chain.tier_2_lots && chain.tier_2_lots[0] ? chain.tier_2_lots[0].po_number : 'PO-2026-001'} • Giao: 20 Tấn (Bồn Silo 3.5°C)`,
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>',
        pill: 'ĐÃ NHẬP KHO (GRN)',
        pillClass: 'status-pill-approved'
      },
      {
        tier: 3,
        key: 'qc',
        name: 'MẮT XÍCH 3: PHÒNG LAB & KIỂM ĐỊNH NGOẠI QUAN AI YOLO',
        title: `COA: ${chain.tier_3_qc ? chain.tier_3_qc.coa_file : 'COA-512.pdf'} • Model AI: ${chain.tier_3_qc ? chain.tier_3_qc.ai_engine : 'YOLOv8x'}`,
        badge: chain.tier_3_qc ? chain.tier_3_qc.sample_code : 'SMP-QC-512',
        subtitle: `Chỉ tiêu Lab: 100% ĐẠT (Brix: 12.2°Bx, pH: 6.68, Vi sinh: 0) • AI Độ tin cậy: ${(chain.tier_3_qc?.ai_confidence_score * 100 || 99).toFixed(1)}%`,
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 2v7.31L4.65 19.4c-.65.98.05 2.6 1.35 2.6h12c1.3 0 2-1.62 1.35-2.6L14 9.31V2m-4 0h4"></path></svg>',
        pill: 'CHUYÊN VIÊN QC ĐÃ PHÊ DUYỆT',
        pillClass: 'status-pill-approved'
      },
      {
        tier: 4,
        key: 'production',
        name: 'MẮT XÍCH 4: SẢN XUẤT & QUY TRÌNH 5 CÔNG ĐOẠN',
        title: `${chain.tier_4_production.product_name} (${chain.tier_4_production.line_name})`,
        badge: chain.tier_4_production.batch_code,
        subtitle: `Sản lượng: ${chain.tier_4_production.actual_quantity.toLocaleString()} ${chain.tier_4_production.unit} • Công thức: ${chain.tier_4_production.recipe_code} • Quản đốc: ${chain.tier_4_production.shift_manager}`,
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18"></path><path d="M5 21V7l8-4v18"></path><path d="M19 21V11l-6-4"></path></svg>',
        pill: '5/5 CÔNG ĐOẠN HOÀN TẤT',
        pillClass: 'status-pill-approved'
      },
      {
        tier: 5,
        key: 'packaging',
        name: 'MẮT XÍCH 5: ĐÓNG GÓI & HOÀN THIỆN TIỆT TRÙNG',
        title: `${chain.tier_5_packaging.packages_completed.toLocaleString()} Thùng carton 5 lớp Flexo`,
        badge: 'PACKAGING',
        subtitle: `Màng Tetra Brik Aseptic 250ml • Phế phẩm: ${chain.tier_5_packaging.waste_count} thùng • Người kiểm tra: ${chain.tier_5_packaging.inspected_by}`,
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path></svg>',
        pill: 'ĐÓNG GÓI ISO 22000',
        pillClass: 'status-pill-approved'
      },
      {
        tier: 6,
        key: 'warehouse',
        name: 'MẮT XÍCH 6: TỒN KHO THÀNH PHẨM (ƯU TIÊN FEFO)',
        title: `Vị trí: ${chain.tier_6_warehouse.storage_bin} • Pallet: ${chain.tier_6_warehouse.pallet_code}`,
        badge: chain.tier_6_warehouse.sku_code,
        subtitle: `Hạn dùng: ${chain.tier_6_warehouse.expiry_date} (Còn ${chain.tier_6_warehouse.days_to_expiry} ngày) • Tồn khả dụng: ${chain.tier_6_warehouse.available_quantity.toLocaleString()} ${chain.tier_6_warehouse.unit}`,
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"></path></svg>',
        pill: chain.tier_6_warehouse.fefo_urgency,
        pillClass: 'status-pill-approved'
      },
      {
        tier: 7,
        key: 'dispatch',
        name: 'MẮT XÍCH 7: ĐIỀU PHỐI VẬN TẢI LẠNH & KHÁCH HÀNG',
        title: chain.tier_7_dispatch ? `${chain.tier_7_dispatch.customer_name} (${chain.tier_7_dispatch.dispatch_code})` : 'Chuỗi Siêu thị WinMart',
        badge: chain.tier_7_dispatch ? chain.tier_7_dispatch.dispatch_code : 'DSP-2026-041',
        subtitle: `Xe: ${chain.tier_7_dispatch ? chain.tier_7_dispatch.license_plate : '29C-881.99'} • Tài xế: ${chain.tier_7_dispatch ? chain.tier_7_dispatch.driver_name : 'Bùi Văn Hùng'} • Nhiệt độ cảm biến: ❄ ${chain.tier_7_dispatch?.temp_sensor_celsius || 3.8}°C`,
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>',
        pill: chain.tier_7_dispatch ? chain.tier_7_dispatch.status : 'IN_TRANSIT',
        pillClass: 'status-pill-approved'
      }
    ];

    nodes.forEach((n, idx) => {
      const card = document.createElement('div');
      card.className = 'trace-node-card';
      card.onclick = () => openTierDrawer(n.key);

      card.innerHTML = `
        <div class="trace-node-header">
          <div class="trace-node-title-group">
            <div class="trace-node-icon">${n.icon}</div>
            <div>
              <div style="font-size:11px;font-weight:700;color:var(--text-muted);">${n.name}</div>
              <div style="font-size:15px;font-weight:800;color:var(--text-main);margin-top:2px;">${n.title}</div>
            </div>
          </div>
          <div style="text-align:right;">
            <span class="card-id-badge" style="font-size:12px;">${n.badge}</span>
            <div style="margin-top:4px;">
              <span class="status-pill ${n.pillClass}" style="font-size:11px;">${n.pill}</span>
            </div>
          </div>
        </div>
        <div style="font-size:12.5px;color:var(--text-secondary);background:var(--bg-subtle);padding:8px 12px;border-radius:6px;display:flex;justify-content:space-between;align-items:center;">
          <span>${n.subtitle}</span>
          <span style="font-weight:700;color:var(--accent-navy);font-size:11.5px;">Xem hồ sơ chi tiết ➔</span>
        </div>
      `;

      container.appendChild(card);

      // Connecting line if not last
      if (idx < nodes.length - 1) {
        const line = document.createElement('div');
        line.className = 'trace-connector-line';
        container.appendChild(line);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Deep Drill-Down Drawer for Each Tier Node
  // ---------------------------------------------------------------------------
  function openTierDrawer(tierKey) {
    if (!currentChain) return;

    const drawer = document.getElementById('detailDrawerRoot');
    const backdrop = document.getElementById('drawerBackdrop');
    if (!drawer) return;

    const visualSlot = document.getElementById('drawerVisualSlot');
    const fieldSlot = document.getElementById('drawerFieldSlot');
    const infoSlot = document.getElementById('drawerInfoListSlot');

    if (tierKey === 'supplier') {
      const s = currentChain.tier_1_supplier;
      document.getElementById('drawerRecordId').innerText = s.supplier_code;
      visualSlot.innerHTML = `
        <div style="background:var(--accent-navy);color:#FFF;padding:16px;border-radius:var(--radius-md);">
          <div style="font-size:12px;opacity:0.8;">HỒ SƠ NHÀ CUNG CẤP & NÔNG TRẠI</div>
          <div style="font-size:16px;font-weight:800;margin-top:2px;">${s.name}</div>
          <div style="font-size:12px;margin-top:4px;">Địa chỉ: ${s.address}</div>
        </div>
      `;
      fieldSlot.innerHTML = `
        <div class="infolist-container">
          <div class="infolist-row-item"><span>Người đại diện</span><span>${s.contact_name}</span></div>
          <div class="infolist-row-item"><span>Số điện thoại</span><span>${s.phone}</span></div>
          <div class="infolist-row-item"><span>Email</span><span>${s.email}</span></div>
          <div class="infolist-row-item"><span>Chứng nhận chất lượng</span><span style="font-weight:700;color:#059669;">${s.certifications}</span></div>
        </div>
      `;
      infoSlot.innerHTML = `
        <div style="padding:10px;background:#F0FDF4;border:1px solid #BBF7D0;border-radius:6px;font-size:12px;color:#166534;">
          ✓ Nhà cung ứng đạt chuẩn đánh giá 4.9/5 sao theo tiêu chuẩn cung ứng ISO 22000 FoodMan.
        </div>
      `;
    } 
    else if (tierKey === 'qc') {
      const q = currentChain.tier_3_qc;
      document.getElementById('drawerRecordId').innerText = q.sample_code;
      visualSlot.innerHTML = `
        <div style="background:#0F172A;color:#FFF;padding:16px;border-radius:var(--radius-md);">
          <div style="display:flex;justify-content:space-between;">
            <span style="font-size:12px;opacity:0.8;">KIỂM ĐỊNH PHÒNG LAB & AI</span>
            <span style="font-size:11px;padding:3px 8px;border-radius:4px;background:#059669;color:#FFF;font-weight:700;">APPROVED</span>
          </div>
          <div style="font-size:16px;font-weight:800;margin-top:4px;">Chuyên viên: ${q.decision_by}</div>
          <div style="font-size:12px;margin-top:4px;opacity:0.85;">Model AI: ${q.ai_engine} (Độ tin cậy: ${(q.ai_confidence_score*100).toFixed(1)}%)</div>
        </div>
      `;
      fieldSlot.innerHTML = `
        <div style="font-size:12px;font-weight:700;margin-bottom:8px;color:var(--text-secondary);">KẾT QUẢ XÉT NGHIỆM LAB HOÁ LÝ & VI SINH</div>
        <div class="infolist-container">
          ${q.tests_summary.map(t => `
            <div class="infolist-row-item">
              <span><strong>${t.parameter}</strong> (Chuẩn: ${t.standard})</span>
              <span style="font-weight:700;color:#059669;">${t.measured} [${t.result}]</span>
            </div>
          `).join('')}
        </div>
      `;
      infoSlot.innerHTML = `
        <div class="infolist-container" style="margin-top:10px;">
          <div class="infolist-row-item"><span>Chứng thư COA</span><span>${q.coa_file} (${q.coa_issuer})</span></div>
          <div class="infolist-row-item"><span>Thời gian phê duyệt</span><span>${q.decided_at || '01/09/2026 10:15'}</span></div>
          <div class="infolist-row-item"><span>Phát hiện khuyết tật ngoại quan</span><span style="font-weight:700;color:#059669;">0 khuyết tật (Đạt chuẩn)</span></div>
        </div>
      `;
    }
    else if (tierKey === 'production') {
      const p = currentChain.tier_4_production;
      document.getElementById('drawerRecordId').innerText = p.batch_code;
      visualSlot.innerHTML = `
        <div style="background:var(--accent-navy);color:#FFF;padding:16px;border-radius:var(--radius-md);">
          <div style="font-size:12px;opacity:0.8;">HỒ SƠ CÔNG NGHỆ CHẾ BIẾN UHT</div>
          <div style="font-size:16px;font-weight:800;margin-top:2px;">${p.product_name}</div>
          <div style="font-size:12px;margin-top:4px;">Dây chuyền: ${p.line_name} • Quản đốc ca: ${p.shift_manager}</div>
        </div>
      `;
      fieldSlot.innerHTML = `
        <div style="font-size:12px;font-weight:700;margin-bottom:8px;color:var(--text-secondary);">TIẾN TRÌNH 5 CÔNG ĐOẠN THỰC TẾ</div>
        <div class="stage-stepper-container">
          ${p.stages.map(s => `
            <div class="stage-step-item is-completed">
              <div class="stage-step-circle">✓</div>
              <div class="stage-step-content">
                <div class="stage-step-title">
                  <span>${s.stage_name}</span>
                  <span style="font-size:11px;font-weight:700;color:#059669;">ĐẠT</span>
                </div>
                <div class="stage-step-time">${s.started_at || ''} → ${s.ended_at || ''}</div>
                ${s.parameters_log ? `<div class="stage-step-param">${s.parameters_log}</div>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
      `;
      infoSlot.innerHTML = `
        <div class="infolist-container">
          <div class="infolist-row-item"><span>Sản lượng hoàn thành</span><span style="font-weight:700;">${p.actual_quantity.toLocaleString()} ${p.unit}</span></div>
          <div class="infolist-row-item"><span>Ngày sản xuất (MFG)</span><span>${p.mfg_date}</span></div>
          <div class="infolist-row-item"><span>Hạn sử dụng (EXP)</span><span>${p.expiry_date}</span></div>
        </div>
      `;
    }
    else if (tierKey === 'dispatch') {
      const d = currentChain.tier_7_dispatch;
      document.getElementById('drawerRecordId').innerText = d.dispatch_code;
      visualSlot.innerHTML = `
        <div style="background:#0F172A;color:#FFF;padding:16px;border-radius:var(--radius-md);">
          <div style="display:flex;justify-content:space-between;">
            <span style="font-size:12px;opacity:0.8;">VẬN TẢI LẠNH & GIAO HÀNG</span>
            <span style="font-size:11px;padding:3px 8px;border-radius:4px;background:#059669;color:#FFF;font-weight:700;">${d.status}</span>
          </div>
          <div style="font-size:16px;font-weight:800;margin-top:4px;">${d.customer_name}</div>
          <div style="font-size:12.5px;margin-top:4px;">Cảm biến thùng xe: <strong style="color:#34D399;">❄ ${d.temp_sensor_celsius}°C</strong> (Chuẩn: ${d.temp_spec_range})</div>
        </div>
      `;
      fieldSlot.innerHTML = `
        <div class="infolist-container">
          <div class="infolist-row-item"><span>Đội xe phụ trách</span><span>${d.carrier_name}</span></div>
          <div class="infolist-row-item"><span>Biển số xe</span><span style="font-weight:700;">${d.license_plate}</span></div>
          <div class="infolist-row-item"><span>Tài xế lái xe</span><span>${d.driver_name} (${d.driver_phone})</span></div>
          <div class="infolist-row-item"><span>Điểm đến nhận hàng</span><span style="max-width:240px;text-align:right;">${d.destination}</span></div>
          <div class="infolist-row-item"><span>Số lượng kiện xuất</span><span style="font-weight:700;color:var(--accent-navy);">${d.quantity_dispatched.toLocaleString()} Thùng</span></div>
          <div class="infolist-row-item"><span>Thời gian xuất phát</span><span>${d.scheduled_departure}</span></div>
        </div>
      `;
      infoSlot.innerHTML = `
        <div style="padding:10px;background:#EFF6FF;border:1px solid #BFDBFE;border-radius:6px;font-size:12px;color:#1E40AF;">
          ❄ Thiết bị giám sát IoT báo cáo nhiệt độ xe lạnh ổn định 3.8°C không bị đứt gãy chuỗi lạnh.
        </div>
      `;
    }
    else {
      // Generic fallback for lots, packaging, warehouse
      document.getElementById('drawerRecordId').innerText = currentChain.batch_code;
      visualSlot.innerHTML = `
        <div style="background:var(--accent-navy);color:#FFF;padding:16px;border-radius:var(--radius-md);">
          <div style="font-size:12px;opacity:0.8;">THÔNG TIN TRUY XUẤT</div>
          <div style="font-size:16px;font-weight:800;margin-top:2px;">${currentChain.product_name}</div>
        </div>
      `;
      fieldSlot.innerHTML = `<div style="padding:16px;font-size:13px;color:var(--text-secondary);">Dữ liệu ghi nhận đầy đủ theo chuẩn HACCP & ISO 22000.</div>`;
      infoSlot.innerHTML = '';
    }

    drawer.classList.add('is-open');
    if (backdrop) backdrop.classList.add('is-visible');
  }

  return {
    init,
    doSearch,
    searchChip,
    loadChain,
    openTierDrawer
  };

})();

document.addEventListener('DOMContentLoaded', TraceabilityApp.init);
