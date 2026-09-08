/**
 * FOOD MAN - REPORTS & ANALYTICS CONTROLLER
 * Phase 6 — Advanced Features & Polish
 * Renders:
 * - Throughput multi-stage comparison (Production vs Packaging vs Raw Material)
 * - Quality & Rejection rate trend (Defect % and YOLO defect categories)
 * - Dispatch trends & Cold-chain IoT temperature stability
 */

const ReportsApp = (() => {
  let activePeriod = '7d';
  let throughputChartInstance = null;
  let rejectionChartInstance = null;
  let dispatchChartInstance = null;

  function init() {
    loadAnalytics(activePeriod);
  }

  function setPeriod(period) {
    activePeriod = period;
    document.querySelectorAll('#periodPills .tab-pill-btn').forEach(btn => {
      if (btn.dataset.period === period) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
    loadAnalytics(period);
  }

  async function loadAnalytics(period) {
    try {
      const res = await fetch(`/api/reports/analytics?period=${period}`);
      if (!res.ok) throw new Error("Unable to load report analytics");
      const json = await res.json();
      
      updateKpis(json.kpis);
      renderThroughputChart(json.throughput);
      renderRejectionChart(json.rejection_rate);
      renderDispatchChart(json.dispatch_trends);
    } catch (err) {
      console.error("ReportsApp Error:", err);
    }
  }

  function updateKpis(kpis) {
    if (!kpis) return;
    const elT = document.getElementById('kpiThroughput');
    if (elT) elT.textContent = kpis.total_throughput_units;

    const elP = document.getElementById('kpiPassRate');
    if (elP) elP.textContent = kpis.quality_pass_rate;

    const elR = document.getElementById('kpiRejectionRate');
    if (elR) elR.textContent = kpis.rejection_rate;

    const elC = document.getElementById('kpiColdChain');
    if (elC) elC.textContent = kpis.cold_chain_compliance;
  }

  function renderThroughputChart(data) {
    const ctx = document.getElementById('throughputChart');
    if (!ctx) return;

    if (throughputChartInstance) {
      throughputChartInstance.destroy();
    }

    throughputChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.labels,
        datasets: [
          {
            label: 'Batch Production (Cases)',
            data: data.production_units,
            backgroundColor: '#162B4E',
            borderRadius: 5,
            yAxisID: 'y'
          },
          {
            label: 'Packaging Output (Cases)',
            data: data.packaging_units,
            backgroundColor: '#10B981',
            borderRadius: 5,
            yAxisID: 'y'
          },
          {
            label: 'Raw Material Intake (Tons)',
            data: data.raw_material_tons,
            type: 'line',
            borderColor: '#F59E0B',
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            borderWidth: 2.5,
            tension: 0.3,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            grid: { display: false }
          },
          y: {
            type: 'linear',
            position: 'left',
            grid: { color: '#F1F5F9' },
            title: { display: true, text: 'Output (Cases)', font: { size: 11 } }
          },
          y1: {
            type: 'linear',
            position: 'right',
            grid: { drawOnChartArea: false },
            title: { display: true, text: 'Raw Material (Tons)', font: { size: 11 } }
          }
        }
      }
    });
  }

  function renderRejectionChart(data) {
    const ctx = document.getElementById('rejectionTrendChart');
    if (!ctx) return;

    if (rejectionChartInstance) {
      rejectionChartInstance.destroy();
    }

    rejectionChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [{
          label: 'Rejection Rate (%)',
          data: data.daily_defect_rate_percent,
          borderColor: '#DC2626',
          backgroundColor: 'rgba(220, 38, 38, 0.1)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointBackgroundColor: '#DC2626'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: true,
            max: 3.0,
            grid: { color: '#F1F5F9' },
            ticks: {
              callback: val => val + '%'
            }
          }
        }
      }
    });

    // Populate defect badges
    const badgesContainer = document.getElementById('defectBadgesList');
    if (badgesContainer && data.yolo_defects_distribution) {
      const labels = data.yolo_defects_distribution.labels || [];
      const counts = data.yolo_defects_distribution.counts || [];
      badgesContainer.innerHTML = labels.map((lbl, idx) => `
        <span class="badge-amber" style="padding:4px 10px;border-radius:6px;font-size:11px;font-weight:700;display:inline-flex;align-items:center;gap:4px;">
          <span>${lbl}:</span> <strong>${counts[idx] || 0}</strong>
        </span>
      `).join('');
    }
  }

  function renderDispatchChart(data) {
    const ctx = document.getElementById('dispatchTrendsChart');
    if (!ctx) return;

    if (dispatchChartInstance) {
      dispatchChartInstance.destroy();
    }

    dispatchChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.labels,
        datasets: [
          {
            type: 'bar',
            label: 'Outbound Volume (Cases)',
            data: data.daily_volume,
            backgroundColor: '#3B82F6',
            borderRadius: 5,
            yAxisID: 'y'
          },
          {
            type: 'line',
            label: 'Avg Temperature (°C)',
            data: data.daily_avg_temp,
            borderColor: '#10B981',
            borderWidth: 2,
            pointBackgroundColor: '#10B981',
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: {
            position: 'left',
            grid: { color: '#F1F5F9' },
            title: { display: true, text: 'Dispatched (Cases)', font: { size: 11 } }
          },
          y1: {
            position: 'right',
            grid: { drawOnChartArea: false },
            min: 0,
            max: 8,
            title: { display: true, text: 'Reefer Temp (°C)', font: { size: 11 } },
            ticks: { callback: val => val + '°C' }
          }
        }
      }
    });

    if (data.status_breakdown) {
      const elDel = document.getElementById('statDelivered');
      if (elDel) elDel.textContent = data.status_breakdown.DELIVERED || 0;
      const elTra = document.getElementById('statInTransit');
      if (elTra) elTra.textContent = data.status_breakdown.IN_TRANSIT || 0;
      const elPen = document.getElementById('statPending');
      if (elPen) elPen.textContent = data.status_breakdown.PENDING || 0;
    }
  }

  function exportSummaryReport() {
    const csvContent = "data:text/csv;charset=utf-8," 
      + "Reporting Period,Total Output,QC Pass Rate,Rejection Rate,Cold Chain Compliance\n"
      + `${activePeriod},28500 Cases,96.4%,3.6%,100.0%\n`;
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `FoodMan_Performance_Report_${activePeriod}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  return {
    init,
    setPeriod,
    exportSummaryReport
  };
})();

document.addEventListener('DOMContentLoaded', ReportsApp.init);
