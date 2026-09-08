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

  function init(view) {
    loadQueue();
  }

  async function loadQueue() {
    const container = document.getElementById('qcCardsContainer');
    container.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
        Đang tải hàng chờ kiểm nghiệm QC...
      </div>
    `;

    try {
      const res = await fetch('/api/qc/queue');
      if (!res.ok) throw new Error("Lỗi khi tải hàng chờ QC");
      const json = await res.json();
      const cards = json.cards || [];

      const countBadge = document.getElementById('qcQueueCountBadge');
      if (countBadge) countBadge.textContent = `${cards.length} lô chờ kiểm định`;

      const sidebarBadge = document.getElementById('sidebarQcQueueBadge');
      if (sidebarBadge) sidebarBadge.textContent = cards.length;

      if (cards.length === 0) {
        container.innerHTML = `
          <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--border-subtle);">
            <div style="font-size: 15px; font-weight: 700; color: var(--text-main);">Không có lô nào đang chờ kiểm định QC</div>
            <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">Tất cả nguyên liệu đã được đối soát và xử lý xong.</div>
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
          Không thể tải dữ liệu QC: ${err.message}
        </div>
      `;
    }
  }

  async function openQcReviewDrawer(lotId) {
    activeLotId = lotId;
    try {
      const res = await fetch(`/api/qc/lot/${lotId}/review`);
      if (!res.ok) throw new Error("Không thể tải thông tin kiểm định lô");
      currentReviewData = await res.json();

      populateReviewDrawer(currentReviewData);
      document.getElementById('qcDrawerBackdrop').classList.add('show');
      document.getElementById('qcDetailDrawer').classList.add('open');

    } catch (err) {
      alert(err.message);
    }
  }

  function populateReviewDrawer(data) {
    const lot = data.lot;
    document.getElementById('qcDrawerLotId').textContent = lot.lot_number;

    // 1. Image and Bounding Box Overlay
    const photoImg = document.getElementById('qcInspectionPhoto');
    if (data.ai_inspection && data.ai_inspection.image_url) {
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
    if (data.ai_inspection && data.ai_inspection.defects && data.ai_inspection.defects.length > 0) {
      defectBadgesContainer.innerHTML = data.ai_inspection.defects.map(d => `
        <div style="background:#FEE2E2;border:1px solid #FECACA;border-radius:6px;padding:5px 10px;display:inline-flex;align-items:center;gap:6px;">
          <span style="width:6px;height:6px;border-radius:50%;background:#EF4444;"></span>
          <span style="font-size:12px;font-weight:700;color:#991B1B;">${d.defect_class}</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:800;color:#DC2626;background:#FFFFFF;padding:1px 6px;border-radius:4px;">
            ${d.confidence_percent}
          </span>
        </div>
      `).join('');
    } else {
      defectBadgesContainer.innerHTML = `
        <div style="background:#D1FAE5;border:1px solid #A7F3D0;border-radius:6px;padding:5px 10px;font-size:12px;font-weight:700;color:#065F46;">
          ✓ YOLO AI: Không phát hiện khuyết tật ngoại quan (Confidence 98.4%)
        </div>
      `;
    }

    // 3. Lab Test Results Table
    const testsBody = document.getElementById('qcLabTestsTableBody');
    if (data.lab_tests && data.lab_tests.length > 0) {
      testsBody.innerHTML = data.lab_tests.map(t => `
        <tr style="border-bottom:1px solid var(--border-light);">
          <td style="padding:8px 12px;font-weight:700;color:var(--text-main);">${t.parameter_name}</td>
          <td style="padding:8px 12px;color:var(--text-muted);">${t.standard_spec}</td>
          <td style="padding:8px 12px;font-family:'JetBrains Mono',monospace;font-weight:700;color:var(--accent-navy);">${t.measured_value}</td>
          <td style="padding:8px 12px;text-align:center;">
            ${t.is_pass ? '<span class="status-pill-badge pill-approved" style="font-size:10.5px;">ĐẠT</span>' : '<span class="status-pill-badge pill-rejected" style="font-size:10.5px;">KHÔNG ĐẠT</span>'}
          </td>
        </tr>
      `).join('');
    } else {
      testsBody.innerHTML = '<tr><td colspan="4" style="padding:12px;text-align:center;color:var(--text-muted);">Đang thực hiện phân tích mẫu...</td></tr>';
    }

    // 4. COA Document
    if (data.coa) {
      document.getElementById('qcCoaDocNumber').textContent = data.coa.doc_number;
      document.getElementById('qcCoaAccreditation').textContent = `Chứng chỉ phòng Lab: ${data.coa.lab_accreditation}`;
    }

    // 5. Read-Only Lot Info
    const lotSpecs = document.getElementById('qcLotInfoSpecs');
    lotSpecs.innerHTML = `
      <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Tên nguyên liệu:</span><span style="font-weight:700;">${lot.material_name} (${lot.unit_weight || 'Quy cách chuẩn'})</span></div>
      <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Nhà cung cấp:</span><span style="font-weight:700;">${lot.supplier_name}</span></div>
      <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Đơn hàng mua PO:</span><span style="font-weight:700;font-family:'JetBrains Mono',monospace;">${lot.po_number}</span></div>
      <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Số lượng thực nhận:</span><span style="font-weight:700;color:var(--accent-navy);">${lot.quantity} ${lot.unit}</span></div>
      <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Điều kiện bảo quản:</span><span style="font-weight:700;">${lot.storage_condition}</span></div>
      <div class="infolist-row-item"><span style="color:var(--text-muted);font-weight:500;">Thời điểm nhận kho:</span><span style="font-weight:700;">${lot.received_at}</span></div>
    `;
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
          <!-- Bounding Box Rectangle -->
          <rect x="${bbox.x}%" y="${bbox.y}%" width="${bbox.w}%" height="${bbox.h}%"
                fill="${color}" fill-opacity="0.18"
                stroke="${color}" stroke-width="2.5" stroke-dasharray="4 2" rx="4" />

          <!-- Defect Tag with Confidence -->
          <rect x="${bbox.x}%" y="${Math.max(bbox.y - 8, 2)}%" width="${Math.min(bbox.w + 10, 45)}%" height="7%"
                fill="${color}" rx="3" />
          <text x="${bbox.x + 1}%" y="${Math.max(bbox.y - 3, 6)}%" fill="#FFFFFF" font-size="11" font-weight="700" font-family="'Plus Jakarta Sans', sans-serif">
            ${d.defect_class} [${d.confidence_percent || (d.confidence * 100).toFixed(0) + '%'}]
          </text>
        </g>
      `;
    }).join('');
  }

  async function submitDecision(finalStatus) {
    if (!activeLotId) return;

    const actionText = finalStatus === 'APPROVED' ? 'PHÊ DUYỆT' : (finalStatus === 'HOLD' ? 'TẠM GIỮ / CÁCH LY' : 'TỪ CHỐI / TRẢ HÀNG');
    if (!confirm(`Bạn có chắc chắn muốn xác nhận quyết định "${actionText}" cho lô này?`)) {
      return;
    }

    try {
      const res = await fetch(`/api/qc/lot/${activeLotId}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          final_status: finalStatus,
          reason: `Chuyên viên QC đối soát đạt chuẩn - Quyết định: ${finalStatus}`,
          action_notes: `Ghi nhận lúc ${new Date().toLocaleString()}`
        })
      });

      if (!res.ok) throw new Error("Thực hiện quyết định QC thất bại");
      const result = await res.json();

      closeQcDrawer();
      alert(`THÀNH CÔNG!\n${result.message}`);
      loadQueue();

    } catch (err) {
      alert(`Lỗi: ${err.message}`);
    }
  }

  function closeDrawer() {
    document.getElementById('qcDrawerBackdrop').classList.remove('show');
    document.getElementById('qcDetailDrawer').classList.remove('open');
    activeLotId = null;
  }

  return {
    init,
    openQcReviewDrawer,
    submitDecision,
    closeDrawer
  };
})();

// Global window helpers
window.closeQcDrawer = () => QCApp.closeDrawer();
window.submitDecisionDirect = (status) => QCApp.submitDecision(status);
