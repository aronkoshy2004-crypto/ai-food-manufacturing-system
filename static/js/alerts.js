/**
 * Food Man - Phase 4 Alerts & Automated Monitoring Rules Controller
 */
const AlertsCenter = (function() {

  let currentAlerts = [];
  let currentRules = [];
  let filterSev = 'ALL';
  let filterCat = 'ALL';

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

        const hasUnreadCritical = currentAlerts.some(a => !a.is_read && a.severity === 'CRITICAL');
        if (hasUnreadCritical && window.FoodManAnimations) {
          window.FoodManAnimations.pulseBell('btnNotificationBell');
        }
      }
    } catch (e) {
      console.error("Failed loading alerts", e);
    }
  }

  function filterSeverity(sev) {
    filterSev = sev;
    renderAlerts();
  }

  function filterCategory(cat) {
    filterCat = cat;
    document.querySelectorAll('#alertCategoryPills button').forEach(btn => btn.classList.remove('active'));
    const activeMap = {
      'ALL': 'catBtnALL',
      'QC_FAIL': 'catBtnQC',
      'LOW_STOCK': 'catBtnSTOCK',
      'EXPIRY': 'catBtnEXPIRY',
      'SYSTEM': 'catBtnSYSTEM'
    };
    const targetId = activeMap[cat];
    if (targetId && document.getElementById(targetId)) {
      document.getElementById(targetId).classList.add('active');
    }
    renderAlerts();
  }

  function matchesCategory(a, cat) {
    if (cat === 'ALL') return true;
    const ref = (a.reference_type || '').toLowerCase();
    const mod = (a.module || '').toLowerCase();
    const title = (a.title || '').toLowerCase();

    if (cat === 'QC_FAIL') {
      return ref.includes('qc') || mod.includes('qc') || title.includes('qc');
    }
    if (cat === 'LOW_STOCK') {
      return ref.includes('raw_material') || ref.includes('inventory') || ref.includes('stock') || title.includes('stock');
    }
    if (cat === 'EXPIRY') {
      return ref.includes('expir') || ref.includes('fefo') || title.includes('fefo') || title.includes('expir');
    }
    if (cat === 'SYSTEM') {
      return ref.includes('system') || mod.includes('system') || (!ref.includes('qc') && !ref.includes('stock') && !ref.includes('expir') && !ref.includes('raw_material') && !ref.includes('inventory'));
    }
    return true;
  }

  function renderAlerts() {
    const container = document.getElementById('alertsListContainer');
    const countEl = document.getElementById('alertsTotalCount');
    if (!container) return;

    let filtered = currentAlerts;
    if (filterSev !== 'ALL') {
      filtered = filtered.filter(a => a.severity === filterSev);
    }
    if (filterCat !== 'ALL') {
      filtered = filtered.filter(a => matchesCategory(a, filterCat));
    }

    if (countEl) countEl.innerText = `${filtered.length} Alerts (${currentAlerts.filter(a => !a.is_read).length} unread)`;
    container.innerHTML = '';

    if (filtered.length === 0) {
      container.innerHTML = `
        <div style="background:#FFF;border:1px solid var(--border-subtle);border-radius:var(--radius-md);padding:30px;text-align:center;color:var(--text-muted);">
          ✓ Currently no active alerts for this filter.
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
              Mark Read
            </button>
          ` : `<span style="font-size:11px;color:var(--text-muted);font-weight:600;">Read</span>`}
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
          <div style="color:var(--text-muted);margin-top:2px;font-size:11px;">Type: ${r.rule_type} • Threshold: ${r.threshold_value}</div>
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
    const nameEl = document.getElementById('newRuleName');
    const name = nameEl?.value?.trim();
    const type = document.getElementById('newRuleType')?.value;
    const thresh = document.getElementById('newRuleThreshold')?.value;
    const sev = document.getElementById('newRuleSeverity')?.value;

    if (!name) {
      if (window.FoodManAnimations) window.FoodManAnimations.shakeField(nameEl);
      if (window.showToast) window.showToast("Validation Error", "Please enter a rule name!", "danger");
      else alert("Please enter a rule name!");
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
        if (window.showToast) window.showToast("Rule Created", data.message, "success");
        else alert(data.message);
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
        if (window.showToast) window.showToast("Alerts Evaluated", `${data.message}. Unread: ${data.unread_count}`, "info");
        else alert(`✓ ${data.message} Total unread alerts: ${data.unread_count}`);
      }
    } catch (e) {
      console.error("Failed evaluating alerts", e);
      if (window.showToast) window.showToast("Evaluation Error", "Failed to evaluate system alert rules", "danger");
      else alert("Error evaluating system alert rules");
    }
  }

  async function clearAllAlerts() {
    if (!confirm("Are you sure you want to mark all alerts as read?")) return;
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
    filterCategory,
    markAsRead,
    openRuleModal,
    closeRuleModal,
    submitRule,
    evaluateSystemAlerts,
    clearAllAlerts
  };

})();

document.addEventListener('DOMContentLoaded', AlertsCenter.init);
