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
   * @param {string} props.headerStat - Top-right secondary stat (e.g. 4,500 / 5,000 Thùng)
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

      if (this.onSaveCallback) {
        this.onSaveCallback(this.activeItem, newStatus);
      }
    }
  }

  return {
    StatusPill,
    RecordCard,
    DetailDrawerController
  };

})();
