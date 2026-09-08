/**
 * Food Man - Phase 4 Alerts & Automated Monitoring Rules Controller
 */
const AlertsCenter = (function() {

  let currentAlerts = [];
  let currentRules = [];
  let filterSev = 'ALL';

  async function init() {
    loadAlerts();
  }

  async function loadAlerts() {
    try {
      const resp = await fetch('/api/alerts');
      const data = await resp.json();
      if (data.success) {
        currentAlerts = data.data;
        currentRules = data.rules;
        renderAlerts();
        renderRules();
      }
    } catch (e) {
      console.error("Failed loading alerts", e);
    }
  }

  function filterSeverity(sev) {
    filterSev = sev;
    renderAlerts();
  }

  function renderAlerts() {
    const container = document.getElementById('alertsListContainer');
    const countEl = document.getElementById('alertsTotalCount');
    if (!container) return;

    let filtered = currentAlerts;
    if (filterSev !== 'ALL') {
      filtered = currentAlerts.filter(a => a.severity === filterSev);
    }

    if (countEl) countEl.innerText = `${filtered.length} Cảnh báo (${currentAlerts.filter(a => !a.is_read).length} chưa đọc)`;
    container.innerHTML = '';

    if (filtered.length === 0) {
      container.innerHTML = `
        <div style="background:#FFF;border:1px solid var(--border-subtle);border-radius:var(--radius-md);padding:30px;text-align:center;color:var(--text-muted);">
          ✓ Hiện không có cảnh báo nào thuộc bộ lọc này.
        </div>
      `;
      return;
    }

    filtered.forEach(a => {
      const isCritical = a.severity === 'CRITICAL';
      const isWarning = a.severity === 'WARNING';
      const borderLeft = isCritical ? '4px solid #DC2626' : (isWarning ? '4px solid #D97706' : '4px solid #3B82F6');
      const badgeClass = isCritical ? 'urgency-expired' : (isWarning ? 'urgency-attention' : 'urgency-fresh');

      const card = document.createElement('div');
      card.style.cssText = `background:#FFFFFF;border:1px solid var(--border-subtle);border-left:${borderLeft};border-radius:var(--radius-md);padding:14px 18px;box-shadow:var(--shadow-card);display:flex;justify-content:space-between;align-items:flex-start;`;
      if (a.is_read) card.style.opacity = '0.75';

      card.innerHTML = `
        <div style="flex:1;">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <span class="urgency-pill ${badgeClass}" style="font-size:10.5px;">${a.severity}</span>
            <span style="font-size:11px;font-weight:700;color:var(--text-muted);">${a.module} • ${a.created_at}</span>
            ${a.reference_id ? `<span class="card-id-badge" style="font-size:11px;">${a.reference_id}</span>` : ''}
          </div>
          <div style="font-size:14px;font-weight:800;color:var(--text-main);">${a.title}</div>
          <div style="font-size:12.5px;color:var(--text-secondary);margin-top:4px;">${a.message}</div>
        </div>
        <div style="display:flex;gap:8px;margin-left:16px;">
          ${!a.is_read ? `
            <button onclick="AlertsCenter.markAsRead(${a.id})" style="padding:6px 12px;border:1px solid var(--border-subtle);border-radius:var(--radius-sm);background:#FFF;font-size:11.5px;cursor:pointer;font-weight:600;">
              Đánh dấu đã đọc
            </button>
          ` : `<span style="font-size:11px;color:var(--text-muted);font-weight:600;">Đã đọc</span>`}
        </div>
      `;

      container.appendChild(card);
    });
  }

  function renderRules() {
    const container = document.getElementById('alertRulesContainer');
    if (!container) return;

    container.innerHTML = '';
    currentRules.forEach(r => {
      const row = document.createElement('div');
      row.style.cssText = 'padding:10px 12px;border:1px solid var(--border-light);border-radius:6px;background:var(--bg-subtle);display:flex;justify-content:space-between;align-items:center;font-size:12px;';
      row.innerHTML = `
        <div>
          <div style="font-weight:700;color:var(--accent-navy);">${r.rule_name}</div>
          <div style="color:var(--text-muted);margin-top:2px;font-size:11px;">Loại: ${r.rule_type} • Ngưỡng: ${r.threshold_value}</div>
        </div>
        <span class="urgency-pill ${r.severity === 'CRITICAL' ? 'urgency-expired' : 'urgency-attention'}" style="font-size:10px;">
          ${r.severity}
        </span>
      `;
      container.appendChild(row);
    });
  }

  async function markAsRead(alertId) {
    try {
      const resp = await fetch(`/api/alerts/${alertId}/read`, { method: 'POST' });
      const data = await resp.json();
      if (data.success) {
        const found = currentAlerts.find(a => a.id === alertId);
        if (found) found.is_read = true;
        renderAlerts();
      }
    } catch (e) {
      console.error("Failed marking read", e);
    }
  }

  function openRuleModal() {
    const modal = document.getElementById('ruleModalPanel');
    const backdrop = document.getElementById('ruleModalBackdrop');
    if (modal) modal.classList.add('is-open');
    if (backdrop) backdrop.classList.add('is-visible');
  }

  function closeRuleModal() {
    const modal = document.getElementById('ruleModalPanel');
    const backdrop = document.getElementById('ruleModalBackdrop');
    if (modal) modal.classList.remove('is-open');
    if (backdrop) backdrop.classList.remove('is-visible');
  }

  async function submitRule() {
    const name = document.getElementById('newRuleName')?.value;
    const type = document.getElementById('newRuleType')?.value;
    const thresh = document.getElementById('newRuleThreshold')?.value;
    const sev = document.getElementById('newRuleSeverity')?.value;

    if (!name) {
      alert("Vui lòng nhập tên quy tắc!");
      return;
    }

    try {
      const resp = await fetch('/api/alerts/rules', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          rule_name: name,
          rule_type: type,
          threshold_value: parseFloat(thresh),
          severity: sev
        })
      });
      const data = await resp.json();
      if (data.success) {
        closeRuleModal();
        loadAlerts();
        alert(data.message);
      }
    } catch (e) {
      console.error("Failed creating alert rule", e);
    }
  }

  async function evaluateSystemAlerts() {
    try {
      const resp = await fetch('/api/alerts/evaluate', { method: 'POST' });
      const data = await resp.json();
      if (data.success) {
        await loadAlerts();
        alert(`✓ ${data.message} Tổng cảnh báo chưa đọc: ${data.unread_count}`);
      }
    } catch (e) {
      console.error("Failed evaluating alerts", e);
      alert("Lỗi khi quét đánh giá cảnh báo hệ thống");
    }
  }

  async function clearAllAlerts() {
    if (!confirm("Bạn có chắc chắn muốn đánh dấu tất cả cảnh báo là đã đọc?")) return;
    try {
      const resp = await fetch('/api/alerts/clear-all', { method: 'POST' });
      const data = await resp.json();
      if (data.success) {
        await loadAlerts();
      }
    } catch (e) {
      console.error("Failed clearing alerts", e);
    }
  }

  return {
    init,
    loadAlerts,
    filterSeverity,
    markAsRead,
    openRuleModal,
    closeRuleModal,
    submitRule,
    evaluateSystemAlerts,
    clearAllAlerts
  };

})();

document.addEventListener('DOMContentLoaded', AlertsCenter.init);
