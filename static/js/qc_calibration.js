/**
 * Colour Screening Calibration Engine
 * PRD Quality Control - Classical Lab Otsu & Threshold Margin Separation (No Machine Learning)
 * 
 * Invariants:
 * 1. Labels strictly "Normal" and "Suspect (discoloured)". Never write "mold" in colour mode.
 * 2. Footer notice: "Colour screening only. Not a mold or lab test."
 * 3. Sunflower uses the same engine and never gets an automatic Pass.
 */

(function () {
  'use strict';

  // State
  let thresholds = {
    Peanut: 40.0,
    Corn: 40.0,
    Sunflower: 40.0
  };
  let separationTable = [];
  let allKernels = [];
  let activeFilterMaterial = 'all';
  let activeFilterStatus = 'all';

  // DOM Elements
  const separationTableBody = document.getElementById('separationTableBody');
  const kernelCardsGrid = document.getElementById('kernelCardsGrid');
  const kernelCardsSubtitle = document.getElementById('kernelCardsSubtitle');
  const btnFitThresholds = document.getElementById('btnFitThresholds');
  const btnResetThresholds = document.getElementById('btnResetThresholds');
  const btnClearMarks = document.getElementById('btnClearMarks');
  const tableLastUpdated = document.getElementById('tableLastUpdated');

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    setupFilters();
    setupActionButtons();
    loadCalibrationData();
  });

  /**
   * Loads calibration data from /api/qc/calibration/data
   */
  async function loadCalibrationData() {
    try {
      const resp = await fetch('/api/qc/calibration/data');
      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }
      const data = await resp.json();
      if (!data.success) {
        throw new Error(data.error || 'Failed to load calibration data');
      }

      thresholds = data.thresholds || thresholds;
      separationTable = data.separation_table || [];
      allKernels = data.kernels || [];

      renderSeparationTable();
      renderKernelCards();

      if (tableLastUpdated) {
        tableLastUpdated.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
      }
    } catch (err) {
      console.error('Error loading calibration data:', err);
      if (separationTableBody) {
        separationTableBody.innerHTML = `
          <tr>
            <td colspan="10" style="padding:24px;text-align:center;color:#EF4444;">
              Failed to load calibration data: ${escapeHtml(err.message)}
            </td>
          </tr>
        `;
      }
      if (kernelCardsGrid) {
        kernelCardsGrid.innerHTML = `
          <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:12px;padding:32px;text-align:center;color:#991B1B;grid-column:1/-1;">
            Failed to load kernel cards. Please check server logs.
          </div>
        `;
      }
    }
  }

  /**
   * Renders the Separation Performance Table
   */
  function renderSeparationTable() {
    if (!separationTableBody) return;

    if (!separationTable || separationTable.length === 0) {
      separationTableBody.innerHTML = `
        <tr>
          <td colspan="10" style="padding:20px;text-align:center;color:#64748B;">No material separation data available.</td>
        </tr>
      `;
      return;
    }

    separationTableBody.innerHTML = separationTable.map(row => {
      const mat = row.material;
      const t = parseFloat(row.threshold).toFixed(1);
      const total = row.total_marked || 0;
      const normal = row.marked_normal || 0;
      const suspect = row.marked_suspect || 0;
      const tn = row.true_normal || 0;
      const fs = row.false_suspect || 0;
      const ts = row.true_suspect || 0;
      const fn = row.false_normal || 0;
      const acc = row.accuracy_pct;

      let accBadge = `<span style="color:#94A3B8;font-style:italic;font-size:12px;">Awaiting marks</span>`;
      if (acc !== null && acc !== undefined) {
        if (acc >= 99.9) {
          accBadge = `<span style="background:#ECFDF5;color:#065F46;border:1px solid #A7F3D0;padding:4px 10px;border-radius:12px;font-weight:700;font-size:12px;display:inline-flex;align-items:center;gap:4px;">
            <span>✓</span> ${acc.toFixed(1)}% Perfect
          </span>`;
        } else if (acc >= 80.0) {
          accBadge = `<span style="background:#EFF6FF;color:#1E40AF;border:1px solid #BFDBFE;padding:4px 10px;border-radius:12px;font-weight:700;font-size:12px;">
            ${acc.toFixed(1)}% Good
          </span>`;
        } else {
          accBadge = `<span style="background:#FEF2F2;color:#991B1B;border:1px solid #FECACA;padding:4px 10px;border-radius:12px;font-weight:700;font-size:12px;">
            ${acc.toFixed(1)}%
          </span>`;
        }
      }

      let matBadgeColor = '#3B82F6';
      if (mat === 'Peanut') matBadgeColor = '#D97706';
      else if (mat === 'Corn') matBadgeColor = '#EAB308';
      else if (mat === 'Sunflower') matBadgeColor = '#8B5CF6';

      return `
        <tr style="border-bottom:1px solid #F1F5F9;transition:background 0.15s ease;" onmouseover="this.style.background='#F8FAFC'" onmouseout="this.style.background='transparent'">
          <td style="padding:12px 14px;font-weight:600;color:#0F172A;">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${matBadgeColor};margin-right:8px;"></span>
            ${escapeHtml(mat)}
          </td>
          <td style="padding:12px 14px;">
            <span style="background:#0F172A;color:#FFFFFF;padding:3px 9px;border-radius:6px;font-family:monospace;font-size:12px;font-weight:700;">
              Score &ge; ${t}
            </span>
          </td>
          <td style="padding:12px 14px;text-align:center;font-weight:600;color:#0F172A;">${total}</td>
          <td style="padding:12px 14px;text-align:center;color:#059669;font-weight:600;">${normal}</td>
          <td style="padding:12px 14px;text-align:center;color:#D97706;font-weight:600;">${suspect}</td>
          <td style="padding:12px 14px;text-align:center;color:#059669;font-family:monospace;font-weight:600;">${tn}</td>
          <td style="padding:12px 14px;text-align:center;color:#DC2626;font-family:monospace;font-weight:600;">${fs}</td>
          <td style="padding:12px 14px;text-align:center;color:#059669;font-family:monospace;font-weight:600;">${ts}</td>
          <td style="padding:12px 14px;text-align:center;color:#DC2626;font-family:monospace;font-weight:600;">${fn}</td>
          <td style="padding:12px 14px;text-align:right;">${accBadge}</td>
        </tr>
      `;
    }).join('');
  }

  /**
   * Renders the Grid of Kernel Cards based on active filters
   */
  function renderKernelCards() {
    if (!kernelCardsGrid) return;

    let filtered = allKernels.slice();

    // 1. Filter by Material
    if (activeFilterMaterial !== 'all') {
      filtered = filtered.filter(k => (k.material || '').toLowerCase() === activeFilterMaterial.toLowerCase());
    }

    // 2. Filter by Mark Status
    if (activeFilterStatus === 'unmarked') {
      filtered = filtered.filter(k => !k.user_mark);
    } else if (activeFilterStatus === 'normal') {
      filtered = filtered.filter(k => k.user_mark === 'normal');
    } else if (activeFilterStatus === 'suspect') {
      filtered = filtered.filter(k => k.user_mark === 'suspect');
    }

    if (kernelCardsSubtitle) {
      kernelCardsSubtitle.innerHTML = `Showing <strong>${filtered.length}</strong> of <strong>${allKernels.length}</strong> kernels from saved frames. Mark each as <strong>Normal</strong> or <strong>Suspect (discoloured)</strong>.`;
    }

    if (filtered.length === 0) {
      kernelCardsGrid.innerHTML = `
        <div style="background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:12px;padding:48px 20px;text-align:center;color:#64748B;grid-column:1/-1;">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="1.5" style="margin-bottom:8px;"><circle cx="12" cy="12" r="10"></circle><path d="M8 15h8M9 9h.01M15 9h.01"/></svg>
          <div style="font-weight:600;font-size:15px;color:#1E293B;">No kernel cards match the current filter.</div>
          <div style="font-size:13px;margin-top:4px;">Try selecting "All Materials" or "All" mark status above.</div>
        </div>
      `;
      return;
    }

    kernelCardsGrid.innerHTML = filtered.map(k => {
      const uid = k.kernel_uid;
      const mat = k.material || 'Peanut';
      const thresh = thresholds[mat] || 40.0;
      const score = parseFloat(k.suspect_score || 0.0);
      const isPredictedSuspect = score >= thresh;
      const predLabel = isPredictedSuspect ? "Suspect (discoloured)" : "Normal";

      const mark = k.user_mark; // 'normal', 'suspect', or undefined
      const isMarkedNormal = mark === 'normal';
      const isMarkedSuspect = mark === 'suspect';

      let cardClass = 'kernel-card';
      if (isMarkedNormal) cardClass += ' marked-normal';
      if (isMarkedSuspect) cardClass += ' marked-suspect';

      // Score bar color
      let barColor = '#10B981'; // Green
      if (score >= thresh) {
        barColor = '#EF4444'; // Red
      } else if (score >= thresh * 0.75) {
        barColor = '#F59E0B'; // Amber
      }

      // Reason tags
      const tags = (k.reason_tags || []).map(t => {
        let tagClass = 'tag-pill';
        const tl = t.toLowerCase();
        if (tl.includes('dark')) tagClass += ' tag-pill-dark';
        else if (tl.includes('green') || tl.includes('grey')) tagClass += ' tag-pill-green';
        else if (tl.includes('bluish') || tl.includes('white')) tagClass += ' tag-pill-blue';
        else if (tl.includes('uneven')) tagClass += ' tag-pill-uneven';
        return `<span class="${tagClass}">${escapeHtml(t)}</span>`;
      }).join('');

      // Median Lab formatting
      const lab = k.median_lab || [0, 0, 0];
      const labStr = `L:${lab[0]} a:${lab[1]} b:${lab[2]}`;

      return `
        <div class="${cardClass}" id="card_${uid}" data-uid="${uid}" style="position:relative;">
          <!-- Card Header -->
          <div style="padding:10px 14px;background:#F8FAFC;border-bottom:1px solid #E2E8F0;display:flex;align-items:center;justify-content:space-between;">
            <div style="display:flex;align-items:center;gap:6px;">
              <span style="font-weight:700;font-size:13px;color:#0F172A;">Frame #${k.frame_id}</span>
              <span style="color:#94A3B8;font-size:12px;">&bull;</span>
              <span style="font-weight:600;font-size:13px;color:#3B82F6;">#${k.kernel_id}</span>
            </div>
            <span style="font-size:11px;font-weight:600;background:#E2E8F0;color:#334155;padding:2px 7px;border-radius:10px;">
              ${escapeHtml(mat)}
            </span>
          </div>

          <!-- Kernel Thumbnail Crop -->
          <div style="width:100%;height:140px;background:#0A0F1D;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;">
            <img src="${k.crop_url}" alt="Kernel #${k.kernel_id}" loading="lazy" style="max-width:100%;max-height:100%;object-fit:contain;display:block;" onerror="this.onerror=null;this.src='/static/img/placeholder_kernel.png';">
            
            <!-- Model screening prediction pill -->
            <div style="position:absolute;bottom:8px;left:8px;background:${isPredictedSuspect ? 'rgba(220, 38, 38, 0.92)' : 'rgba(16, 185, 129, 0.92)'};color:#FFFFFF;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:700;backdrop-filter:blur(4px);box-shadow:0 2px 4px rgba(0,0,0,0.3);">
              ${predLabel}
            </div>

            <!-- User Mark badge if marked -->
            ${isMarkedNormal ? `
              <div style="position:absolute;top:8px;right:8px;background:#10B981;color:#FFFFFF;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700;box-shadow:0 2px 6px rgba(0,0,0,0.3);display:flex;align-items:center;gap:4px;">
                <span>✓</span> Marked Normal
              </div>
            ` : ''}
            ${isMarkedSuspect ? `
              <div style="position:absolute;top:8px;right:8px;background:#F59E0B;color:#FFFFFF;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700;box-shadow:0 2px 6px rgba(0,0,0,0.3);display:flex;align-items:center;gap:4px;">
                <span>⚠️</span> Marked Suspect
              </div>
            ` : ''}
          </div>

          <!-- Metrics Body -->
          <div style="padding:12px 14px;flex:1;display:flex;flex-direction:column;gap:8px;">
            <!-- Suspect Score Gauge -->
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;margin-bottom:4px;">
                <span style="font-weight:600;color:#475569;">Suspect Score</span>
                <span style="font-weight:700;color:${score >= thresh ? '#DC2626' : '#059669'};font-family:monospace;font-size:13px;">
                  ${score.toFixed(1)} <span style="font-size:10px;color:#94A3B8;font-weight:normal;">/ 100</span>
                </span>
              </div>
              <div style="width:100%;height:6px;background:#E2E8F0;border-radius:3px;overflow:hidden;position:relative;">
                <div style="width:${Math.min(100, Math.max(0, score))}%;height:100%;background:${barColor};transition:width 0.3s ease;"></div>
                <!-- Threshold marker indicator line -->
                <div style="position:absolute;left:${thresh}%;top:0;bottom:0;width:2px;background:#0F172A;z-index:2;" title="Active threshold: ${thresh}"></div>
              </div>
            </div>

            <!-- Lab colour metrics breakdown -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 8px;font-size:11px;color:#64748B;background:#F8FAFC;padding:6px 8px;border-radius:6px;border:1px solid #F1F5F9;">
              <div>Dark Patch: <strong style="color:#0F172A;">${k.dark_patch_pct}%</strong></div>
              <div>Patch: <strong style="color:#0F172A;">${k.patch_pct}%</strong></div>
              <div>Unevenness: <strong style="color:#0F172A;">${k.unevenness}</strong></div>
              <div title="Median Lab: ${labStr}">Lab: <strong style="color:#0F172A;">${labStr}</strong></div>
            </div>

            <!-- Reason tags -->
            <div style="min-height:24px;">
              ${tags || '<span style="color:#94A3B8;font-size:11px;font-style:italic;">No suspect defect tags</span>'}
            </div>
          </div>

          <!-- Mark Actions Footer (Normal vs Suspect) -->
          <div style="padding:10px 14px;background:#F8FAFC;border-top:1px solid #E2E8F0;display:flex;gap:8px;">
            <button class="btn-mark-normal" onclick="window.markKernel('${uid}', 'normal', '${mat}', ${score}, ${k.frame_id}, ${k.kernel_id})" style="flex:1;padding:7px 0;border-radius:6px;font-size:12px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:4px;transition:all 0.15s ease;${isMarkedNormal ? 'background:#10B981;color:#FFFFFF;border:1px solid #10B981;font-weight:700;' : 'background:#FFFFFF;color:#059669;border:1px solid #A7F3D0;font-weight:600;'}" title="Mark this kernel as Normal">
              <span>✓</span> Normal
            </button>

            <button class="btn-mark-suspect" onclick="window.markKernel('${uid}', 'suspect', '${mat}', ${score}, ${k.frame_id}, ${k.kernel_id})" style="flex:1;padding:7px 0;border-radius:6px;font-size:12px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:4px;transition:all 0.15s ease;${isMarkedSuspect ? 'background:#F59E0B;color:#FFFFFF;border:1px solid #F59E0B;font-weight:700;' : 'background:#FFFFFF;color:#D97706;border:1px solid #FDE68A;font-weight:600;'}" title="Mark this kernel as Suspect (discoloured)">
              <span>⚠️</span> Suspect
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  /**
   * User marks a kernel card as Normal or Suspect (or toggles unmark)
   */
  window.markKernel = async function (kernelUid, newMark, material, score, frameId, kernelId) {
    const cardEl = document.getElementById(`card_${kernelUid}`);
    const kernelObj = allKernels.find(k => k.kernel_uid === kernelUid);

    // If already has this mark, toggle to clear
    let finalMark = newMark;
    if (kernelObj && kernelObj.user_mark === newMark) {
      finalMark = 'clear';
    }

    try {
      const resp = await fetch('/api/qc/calibration/mark', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
          kernel_uid: kernelUid,
          mark: finalMark,
          material: material,
          score: score,
          frame_id: frameId,
          kernel_id: kernelId
        })
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const res = await resp.json();
      if (!res.success) {
        throw new Error(res.error || 'Failed to update mark');
      }

      // Update local state
      if (kernelObj) {
        kernelObj.user_mark = (finalMark === 'clear' ? undefined : finalMark);
      }
      separationTable = res.separation_table || separationTable;
      thresholds = res.thresholds || thresholds;

      // Re-render UI components
      renderSeparationTable();
      renderKernelCards();

      if (tableLastUpdated) {
        tableLastUpdated.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
      }
    } catch (err) {
      console.error('Error marking kernel:', err);
      alert(`Could not save mark: ${err.message}`);
    }
  };

  /**
   * Action buttons: Fit Thresholds, Reset Thresholds, Clear Marks
   */
  function setupActionButtons() {
    // 1. Fit Thresholds (No ML)
    if (btnFitThresholds) {
      btnFitThresholds.addEventListener('click', async () => {
        const origText = btnFitThresholds.innerHTML;
        btnFitThresholds.disabled = true;
        btnFitThresholds.innerHTML = `<span>⏳ Fitting...</span>`;

        try {
          const resp = await fetch('/api/qc/calibration/fit', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ material: 'all' })
          });
          const data = await resp.json();
          if (!data.success) {
            throw new Error(data.error || 'Failed to fit thresholds');
          }

          thresholds = data.thresholds || thresholds;
          separationTable = data.separation_table || separationTable;

          renderSeparationTable();
          renderKernelCards();

          showToast('⚡ Simple thresholds fitted successfully from manual marks (no machine learning)!');
        } catch (err) {
          console.error('Error fitting thresholds:', err);
          alert(`Fitting failed: ${err.message}`);
        } finally {
          btnFitThresholds.disabled = false;
          btnFitThresholds.innerHTML = origText;
        }
      });
    }

    // 2. Reset Thresholds back to 40.0
    if (btnResetThresholds) {
      btnResetThresholds.addEventListener('click', async () => {
        if (!confirm('Reset all material thresholds in settings back to default 40.0?')) {
          return;
        }

        const origText = btnResetThresholds.innerHTML;
        btnResetThresholds.disabled = true;
        btnResetThresholds.innerHTML = `<span>⏳ Resetting...</span>`;

        try {
          const resp = await fetch('/api/qc/calibration/reset', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ material: 'all' })
          });
          const data = await resp.json();
          if (!data.success) {
            throw new Error(data.error || 'Failed to reset thresholds');
          }

          thresholds = data.thresholds || thresholds;
          separationTable = data.separation_table || separationTable;

          renderSeparationTable();
          renderKernelCards();

          showToast('↺ Thresholds reset to default (40.0).');
        } catch (err) {
          console.error('Error resetting thresholds:', err);
          alert(`Reset failed: ${err.message}`);
        } finally {
          btnResetThresholds.disabled = false;
          btnResetThresholds.innerHTML = origText;
        }
      });
    }

    // 3. Clear All Marks
    if (btnClearMarks) {
      btnClearMarks.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to clear ALL manual marks across all saved frames?')) {
          return;
        }

        try {
          const resp = await fetch('/api/qc/calibration/clear-marks', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Requested-With': 'XMLHttpRequest'
            }
          });
          const data = await resp.json();
          if (!data.success) {
            throw new Error(data.error || 'Failed to clear marks');
          }

          allKernels.forEach(k => { k.user_mark = undefined; });
          separationTable = data.separation_table || separationTable;
          thresholds = data.thresholds || thresholds;

          renderSeparationTable();
          renderKernelCards();

          showToast('All user marks cleared.');
        } catch (err) {
          console.error('Error clearing marks:', err);
          alert(`Clear failed: ${err.message}`);
        }
      });
    }
  }

  /**
   * Filter controls
   */
  function setupFilters() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-btn').forEach(b => {
          b.classList.remove('active');
          b.style.background = 'transparent';
          b.style.color = '#64748B';
          b.style.fontWeight = '500';
          b.style.boxShadow = 'none';
        });

        const target = e.currentTarget;
        target.classList.add('active');
        target.style.background = '#FFFFFF';
        target.style.color = '#0F172A';
        target.style.fontWeight = '600';
        target.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)';

        activeFilterMaterial = target.getAttribute('data-filter-material') || 'all';
        renderKernelCards();
      });
    });

    document.querySelectorAll('.filter-status-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-status-btn').forEach(b => {
          b.classList.remove('active');
          b.style.background = 'transparent';
          b.style.color = '#64748B';
          b.style.fontWeight = '500';
          b.style.boxShadow = 'none';
        });

        const target = e.currentTarget;
        target.classList.add('active');
        target.style.background = '#FFFFFF';
        target.style.color = '#0F172A';
        target.style.fontWeight = '600';
        target.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)';

        activeFilterStatus = target.getAttribute('data-filter-status') || 'all';
        renderKernelCards();
      });
    });
  }

  /**
   * Helper: Toast banner
   */
  function showToast(msg) {
    const toast = document.createElement('div');
    toast.textContent = msg;
    toast.style.position = 'fixed';
    toast.style.bottom = '24px';
    toast.style.right = '24px';
    toast.style.background = '#0F172A';
    toast.style.color = '#FFFFFF';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 6px 16px rgba(0,0,0,0.2)';
    toast.style.fontSize = '13px';
    toast.style.fontWeight = '600';
    toast.style.zIndex = '9999';
    toast.style.transition = 'opacity 0.25s ease';
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => { toast.remove(); }, 250);
    }, 2800);
  }

  /**
   * Helper: Escape HTML
   */
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

})();
