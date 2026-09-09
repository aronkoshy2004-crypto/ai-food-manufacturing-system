/**
 * FOOD MAN - GLOBAL GENERIC PROP-DRIVEN UI COMPONENTS
 * Phase 0 Foundation:
 * 1. StatusPill(status, label) - Maps strictly to PENDING, APPROVED, HOLD, REJECTED
 * 2. RecordCard(props) - Generic prop-driven 2-col card
 * 3. DetailDrawer(slots) - Generic drawer with visual, field, info-list slots
 */

const FoodManComponents = (() => {

  /**
   * Component 1: StatusPill
   * @param {string} status - PENDING | APPROVED | HOLD | REJECTED
   * @param {string} [label] - Optional override label
   * @returns {string} HTML markup
   */
  function StatusPill(status, label) {
    const statusUpper = (status || 'PENDING').toUpperCase();
    
    const statusMap = {
      PENDING: {
        pillClass: 'pill-pending',
        defaultLabel: 'Pending'
      },
      APPROVED: {
        pillClass: 'pill-approved',
        defaultLabel: 'Approved'
      },
      HOLD: {
        pillClass: 'pill-hold',
        defaultLabel: 'Hold / Quarantined'
      },
      REJECTED: {
        pillClass: 'pill-rejected',
        defaultLabel: 'Rejected'
      }
    };

    const config = statusMap[statusUpper] || statusMap.PENDING;
    const displayLabel = label || config.defaultLabel;

    return `
      <div class="status-pill-badge ${config.pillClass}" data-status="${statusUpper}">
        <span class="status-dot-bullet"></span>
        <span>${displayLabel}</span>
      </div>
    `;
  }

  /**
   * Component 2: RecordCard
   * Prop-driven generic card pattern for list-of-records screens
   * @param {Object} props
   * @param {string} props.id - Record Code (e.g. LOT-2026-089)
   * @param {string} props.title - Main product / lot title
   * @param {string} [props.category] - Small uppercase tag
   * @param {string} props.headerStat - Top-right secondary stat (e.g. 4,500 / 5,000 Cartons)
   * @param {string} [props.statSub] - Subtitle for header stat
   * @param {Array<{label: string, value: string}>} props.miniGrid - 2x2 label/value grid
   * @param {Array<{initial: string, bg: string, name: string}>} props.avatars - Assigned avatars
   * @param {string} props.status - PENDING | APPROVED | HOLD | REJECTED
   * @param {string} [props.statusLabel] - Custom status pill text
   * @param {number} [props.progress] - Optional progress percentage (0-100)
   * @param {boolean} [props.isActive] - Border highlight if selected
   * @returns {string} HTML markup
   */
  function RecordCard(props) {
    const miniGridHtml = (props.miniGrid || []).map(cell => `
      <div class="grid-cell-item">
        <span class="cell-label-text">${cell.label}</span>
        <span class="cell-value-text" title="${cell.value}">${cell.value}</span>
      </div>
    `).join('');

    const avatarsHtml = (props.avatars || []).map(av => `
      <div class="avatar-stack-disc" style="background-color: ${av.bg || '#162B4E'};" title="${av.name || ''}">
        ${av.initial || 'FM'}
      </div>
    `).join('');

    const progressHtml = props.progress !== undefined && props.progress !== null ? `
      <div class="card-progress-bar-slot">
        <div class="progress-info-row">
          <span>Completion Progress</span>
          <span style="font-family:'JetBrains Mono',monospace;">${props.progress}%</span>
        </div>
        <div class="progress-track-bg">
          <div class="progress-fill-bar" style="width: ${props.progress}%;"></div>
        </div>
      </div>
    ` : '';

    const pillHtml = StatusPill(props.status, props.statusLabel);

    return `
      <div class="record-card-box ${props.isActive ? 'card-active' : ''}" data-id="${props.id}" onclick="FoodManApp.selectCard('${props.id}')">
        <!-- Header Row -->
        <div class="card-top-row">
          <div class="card-title-col">
            <div>
              <span class="card-id-badge">${props.id}</span>
              ${props.category ? `<span class="card-category-sub">${props.category}</span>` : ''}
            </div>
            <h3 class="card-main-title">${props.title}</h3>
          </div>
          <div class="card-stat-widget">
            <span class="card-stat-number">${props.headerStat}</span>
            ${props.statSub ? `<span class="card-stat-caption">${props.statSub}</span>` : ''}
          </div>
        </div>

        <!-- 2x2 Mini Grid -->
        <div class="card-mini-grid-layout">
          ${miniGridHtml}
        </div>

        <!-- Optional Progress Bar -->
        ${progressHtml}

        <!-- Card Footer -->
        <div class="card-footer-slot">
          <div class="avatar-stack-slot">
            ${avatarsHtml}
          </div>
          ${pillHtml}
        </div>
      </div>
    `;
  }

  /**
   * Component 3: DetailDrawer
   * Generic drawer with slots: Visual, Field, Info-list, Footer Actions
   */
  class DetailDrawerController {
    constructor(panelId, backdropId) {
      this.panel = document.getElementById(panelId);
      this.backdrop = document.getElementById(backdropId);
      this.activeItem = null;
      this.onSaveCallback = null;
      this.initEvents();
    }

    initEvents() {
      if (this.backdrop) {
        this.backdrop.addEventListener('click', () => this.close());
      }
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') this.close();
      });
    }

    open(data, onSave) {
      this.activeItem = data;
      this.onSaveCallback = onSave;

      // 1. Visual slot
      const visualSlot = document.getElementById('drawerVisualSlot');
      if (visualSlot) {
        visualSlot.innerHTML = this.renderVisualSlot(data);
      }

      // 2. ID badge
      const idBadge = document.getElementById('drawerRecordId');
      if (idBadge) {
        idBadge.textContent = data.id;
      }

      // 3. Field slot (2-column editable fields)
      const fieldSlot = document.getElementById('drawerFieldSlot');
      if (fieldSlot) {
        fieldSlot.innerHTML = this.renderFieldSlot(data);
      }

      // 4. Info-list slot (Read-only technical specs)
      const infoSlot = document.getElementById('drawerInfoListSlot');
      if (infoSlot) {
        infoSlot.innerHTML = this.renderInfoListSlot(data);
      }

      // Slide in
      this.panel.classList.add('open');
      this.backdrop.classList.add('show');
    }

    close() {
      if (this.panel) this.panel.classList.remove('open');
      if (this.backdrop) this.backdrop.classList.remove('show');
      FoodManApp.clearCardSelection();
    }

    renderVisualSlot(data) {
      return `
        <div style="padding: 0 24px; position: relative; z-index: 2; width: 100%;">
          <div style="font-size: 11px; font-weight: 700; color: #93C5FD; text-transform: uppercase; letter-spacing: 0.5px;">
            ${data.category || 'FOOD MAN VERIFIED'}
          </div>
          <div style="font-size: 18px; font-weight: 800; color: #FFFFFF; line-height: 1.3; margin-top: 4px;">
            ${data.title}
          </div>
          <div style="font-size: 12px; color: #FCD34D; font-family: 'JetBrains Mono', monospace; margin-top: 4px;">
            ${data.headerStat || ''} ${data.statSub || ''}
          </div>
        </div>
      `;
    }

    renderFieldSlot(data) {
      const fields = data.editableFields || [
        { label: "Status", key: "status", type: "select", options: ["PENDING", "APPROVED", "HOLD", "REJECTED"], value: data.status },
        { label: "Classification Note", key: "category", type: "text", value: data.category || "" }
      ];

      const fieldsHtml = fields.map(f => {
        if (f.type === 'select') {
          const opts = f.options.map(o => `
            <option value="${o}" ${o === f.value ? 'selected' : ''}>${o}</option>
          `).join('');
          return `
            <div class="field-slot-group">
              <label class="field-slot-label">${f.label}</label>
              <select class="field-slot-select" id="drawer_input_${f.key}">
                ${opts}
              </select>
            </div>
          `;
        } else {
          return `
            <div class="field-slot-group">
              <label class="field-slot-label">${f.label}</label>
              <input type="text" class="field-slot-input" id="drawer_input_${f.key}" value="${f.value || ''}">
            </div>
          `;
        }
      }).join('');

      return `
        <div class="drawer-slot-title">ADJUSTMENT ATTRIBUTES (2-COLUMN FIELD SLOT)</div>
        <div class="field-slot-grid">
          ${fieldsHtml}
        </div>
      `;
    }

    renderInfoListSlot(data) {
      const specs = data.readonlySpecs || [
        { label: "Record ID", value: data.id, mono: true },
        { label: "Responsible Module", value: data.module || "Core System" },
        { label: "Compliance Standard", value: "HACCP Class A Standard" }
      ];

      const rows = specs.map(s => `
        <div class="infolist-row-item">
          <span style="color: var(--text-muted); font-weight: 500;">${s.label}</span>
          <span style="font-weight: 700; color: var(--text-main); ${s.mono ? "font-family:'JetBrains Mono',monospace;" : ""}">${s.value}</span>
        </div>
      `).join('');

      return `
        <div class="drawer-slot-title">TRACEABILITY ATTRIBUTES (INFO-LIST SLOT)</div>
        <div class="infolist-card-box">
          ${rows}
        </div>
      `;
    }

    save() {
      if (!this.activeItem) return;
      const statusSelect = document.getElementById('drawer_input_status');
      const newStatus = statusSelect ? statusSelect.value : this.activeItem.status;

      const saveBtn = document.querySelector('.btn-drawer-save');
      if (this.onSaveCallback) {
        if (saveBtn && FoodManAnimations && !FoodManAnimations.isReducedMotion()) {
          FoodManAnimations.buttonAction(saveBtn, async () => {
            await this.onSaveCallback(this.activeItem, newStatus);
          }, {
            successText: 'Saved ✓',
            holdMs: 250,
            onComplete: () => this.close()
          });
        } else {
          const res = this.onSaveCallback(this.activeItem, newStatus);
          if (res && typeof res.then === 'function') {
            res.then(() => this.close());
          }
        }
      }
    }
  }

  // ==========================================================================
  // CENTRALIZED INDUSTRIAL ANIMATION CONTROLLER (FOODMAN INTERNAL OPS)
  // Non-bouncy, ease-out enter, ease-in exit, strictly under ~300ms
  // ==========================================================================
  const FoodManAnimations = {
    isReducedMotion() {
      return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    },

    // 1. KPI & Confidence Score Count-Up
    countUp(el, start, end, duration = 280, formatFn = null) {
      if (!el) return;
      if (this.isReducedMotion() || duration <= 0) {
        el.innerText = formatFn ? formatFn(end) : end;
        return;
      }

      const startTime = performance.now();
      const diff = end - start;

      function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // ease-out cubic (non-bouncy)
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const currentVal = start + (diff * easeOut);

        el.innerText = formatFn ? formatFn(currentVal) : Math.round(currentVal);

        if (progress < 1) {
          requestAnimationFrame(update);
        } else {
          el.innerText = formatFn ? formatFn(end) : end;
        }
      }

      requestAnimationFrame(update);
    },

    // 2. Button Inline Spinner → Checkmark Morph
    async buttonAction(btn, asyncCallback, options = {}) {
      if (!btn) return;
      const loadingText = options.loadingText || 'Saving...';
      const successText = options.successText || 'Saved ✓';
      const holdMs = options.holdMs || 260;

      const originalHtml = btn.innerHTML;
      const originalWidth = btn.offsetWidth;
      btn.style.minWidth = `${originalWidth}px`;
      btn.disabled = true;
      btn.classList.add('btn-anim-loading');
      btn.innerHTML = `<span class="btn-spinner-icon"></span><span>${loadingText}</span>`;

      try {
        await asyncCallback();
        btn.classList.remove('btn-anim-loading');
        btn.classList.add('btn-anim-success');
        btn.innerHTML = `
          <svg class="checkmark-morph-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
            <path class="checkmark-morph-path" d="M20 6L9 17l-5-5"></path>
          </svg>
          <span>${successText}</span>
        `;

        await new Promise(resolve => setTimeout(resolve, holdMs));

        if (options.onComplete) {
          options.onComplete();
        }
      } catch (err) {
        console.error("Button action error:", err);
        btn.classList.remove('btn-anim-loading');
        this.shakeField(btn);
        throw err;
      } finally {
        setTimeout(() => {
          btn.disabled = false;
          btn.classList.remove('btn-anim-loading', 'btn-anim-success');
          btn.innerHTML = originalHtml;
          btn.style.minWidth = '';
        }, 150);
      }
    },

    // 3. Validation Error: Gentle Field Shake
    shakeField(inputEl) {
      if (!inputEl) return;
      inputEl.classList.remove('input-error-shake');
      void inputEl.offsetWidth; // force reflow
      inputEl.classList.add('input-error-shake');

      const cleanup = () => inputEl.classList.remove('input-error-shake');
      inputEl.addEventListener('animationend', cleanup, { once: true });
      setTimeout(cleanup, 280);
    },

    // 4. Toast Notifications with Top-Right Slide & Shrinking Progress Bar
    showToast(title, msg, type = 'info', duration = 3500) {
      let container = document.getElementById('toastContainer');
      if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
      }

      const toast = document.createElement('div');
      toast.className = `toast-item toast-${type}`;
      toast.style.setProperty('--toast-duration', `${duration}ms`);

      let iconSvg = '';
      if (type === 'success') {
        iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"></path></svg>`;
      } else if (type === 'danger') {
        iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
      } else if (type === 'warning') {
        iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
      } else {
        iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
      }

      toast.innerHTML = `
        <div class="toast-icon-wrap">${iconSvg}</div>
        <div class="toast-content">
          <div class="toast-title">${title}</div>
          <div class="toast-msg">${msg}</div>
        </div>
        <button class="toast-close-btn" aria-label="Close" onclick="this.closest('.toast-item').remove()">✕</button>
        <div class="toast-progress-track">
          <div class="toast-progress-bar"></div>
        </div>
      `;

      container.appendChild(toast);

      // Auto-dismiss with exit transition
      const timer = setTimeout(() => {
        toast.classList.add('toast-leaving');
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
        setTimeout(() => toast.remove(), 250);
      }, duration);

      toast.dataset.timerId = timer;
    },

    // 5. Notification Bell: Single Subtle Pulse
    pulseBell() {
      const bell = document.getElementById('btnNotificationBell');
      if (!bell) return;
      bell.classList.remove('bell-pulse-once');
      void bell.offsetWidth; // trigger reflow
      bell.classList.add('bell-pulse-once');
      bell.addEventListener('animationend', () => {
        bell.classList.remove('bell-pulse-once');
      }, { once: true });
    },

    // 6. Sidebar Sliding Active Indicator
    initSidebarSlider() {
      const sidebarMenu = document.querySelector('.sidebar-menu');
      if (!sidebarMenu) return;

      let indicator = document.getElementById('sidebarActiveIndicator');
      if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'sidebarActiveIndicator';
        indicator.className = 'sidebar-active-indicator';
        sidebarMenu.appendChild(indicator);
      }

      sidebarMenu.classList.add('has-indicator');

      function moveTo(targetLink, isInitial = false) {
        if (!targetLink || !sidebarMenu.contains(targetLink)) return;
        const menuRect = sidebarMenu.getBoundingClientRect();
        const linkRect = targetLink.getBoundingClientRect();
        const topOffset = linkRect.top - menuRect.top + sidebarMenu.scrollTop;
        const height = linkRect.height;

        if (isInitial && sessionStorage.getItem('foodman_last_nav_top') && !FoodManAnimations.isReducedMotion()) {
          const lastTop = parseFloat(sessionStorage.getItem('foodman_last_nav_top'));
          indicator.style.transition = 'none';
          indicator.style.transform = `translateY(${lastTop}px)`;
          indicator.style.height = `${height}px`;
          indicator.classList.add('is-visible');

          requestAnimationFrame(() => {
            indicator.style.transition = '';
            indicator.style.transform = `translateY(${topOffset}px)`;
          });
        } else {
          indicator.style.height = `${height}px`;
          indicator.style.transform = `translateY(${topOffset}px)`;
          indicator.classList.add('is-visible');
        }

        sessionStorage.setItem('foodman_last_nav_top', topOffset);
      }

      const activeLink = sidebarMenu.querySelector('.nav-workflow-link.active');
      if (activeLink) {
        moveTo(activeLink, true);
      }

      sidebarMenu.querySelectorAll('.nav-workflow-link').forEach(link => {
        link.addEventListener('click', () => {
          sidebarMenu.querySelectorAll('.nav-workflow-link').forEach(l => l.classList.remove('active'));
          link.classList.add('active');
          moveTo(link, false);
        });
      });

      window.addEventListener('resize', () => {
        const currentActive = sidebarMenu.querySelector('.nav-workflow-link.active');
        if (currentActive) moveTo(currentActive, false);
      }, { passive: true });
    },

    // 7. Newly Created Record Slide-in
    animateNewRecord(element) {
      if (!element) return;
      element.classList.remove('card-enter-animate');
      void element.offsetWidth;
      element.classList.add('card-enter-animate');
    }
  };

  // Expose globally
  window.FoodManAnimations = FoodManAnimations;
  window.showToast = FoodManAnimations.showToast.bind(FoodManAnimations);
  window.pulseNotificationBell = FoodManAnimations.pulseBell.bind(FoodManAnimations);

  return {
    StatusPill,
    RecordCard,
    DetailDrawerController,
    Animations: FoodManAnimations
  };

})();
