/**
 * Food Man - UI Enhancements & Interactive Micro-Behaviors
 * Ref: Modern Poshaco Enterprise Shell
 * Non-invasive helper layer: pure visual polish, zero core mutation.
 */

(function () {
  'use strict';

  function initUI() {
    updateTelemetryChips();
    enhanceCardSelection();
    syncRealNotifications();
  }

  // Format today's date in English reference format: "Sat, Oct 17, 2026"
  function updateTelemetryChips() {
    const dateChip = document.getElementById('baseLiveDateChip');
    if (dateChip) {
      const now = new Date();
      const options = { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' };
      dateChip.textContent = now.toLocaleDateString('en-US', options);
    }
  }

  // Visual card selection feedback
  function enhanceCardSelection() {
    document.addEventListener('click', function (e) {
      const card = e.target.closest('.card-selectable, .lot-card, .batch-card, .operational-card');
      if (card) {
        document.querySelectorAll('.card-selectable.is-selected, .lot-card.is-selected, .batch-card.is-selected, .operational-card.is-selected').forEach(c => {
          c.classList.remove('is-selected');
        });
        card.classList.add('is-selected');
      }
    });
  }

  // Real database notification synchronization for bell dot and dropdown
  async function syncRealNotifications() {
    const dot = document.getElementById('topbarNotifDot');
    const notifBody = document.getElementById('topbarNotifBody');
    try {
      const resp = await fetch('/api/alerts');
      if (!resp.ok) return;
      const data = await resp.json();
      if (!data || !data.success) return;

      const unreadCount = data.unread_count || 0;
      if (dot) {
        dot.style.display = unreadCount > 0 ? 'block' : 'none';
      }

      if (notifBody && Array.isArray(data.data)) {
        if (data.data.length === 0) {
          notifBody.innerHTML = '<div style="padding:16px;text-align:center;color:#64748B;font-size:12px;">No unread system alerts.</div>';
        } else {
          notifBody.innerHTML = data.data.slice(0, 5).map(alert => {
            const isUnread = !alert.is_read;
            const sevColor = alert.severity === 'CRITICAL' ? '#DC2626' : (alert.severity === 'WARNING' ? '#D97706' : '#059669');
            const alertUrl = alert.link_url || '/alerts';
            return `
              <div class="notif-dropdown-item ${isUnread ? 'is-unread' : ''}" onclick="window.location.href='${alertUrl}'">
                <div>
                  <div style="font-weight:700;color:${sevColor};font-size:12.5px;">${alert.title || 'System Alert'}</div>
                  <div style="font-size:11.5px;color:#64748B;margin-top:2px;">${alert.message || ''}</div>
                  <div style="font-size:10px;color:#94A3B8;margin-top:4px;">${alert.created_at || ''}</div>
                </div>
              </div>
            `;
          }).join('');
        }
      }
    } catch (e) {
      // Graceful fallback
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initUI);
  } else {
    initUI();
  }
})();
