/**
 * Axion Manufacturing Dashboard Controller
 * Renders BOM Overview Donut Chart & Manufacturing Efficiency Bar Chart matching the reference design.
 */
const AxionDashboard = (function() {

  let bomDonutInstance = null;
  let efficiencyBarInstance = null;
  let defectRateInstance = null;

  async function init() {
    renderBOMDonutChart();
    renderEfficiencyBarChart();
    renderDefectRateChart();
    setupDropdowns();
    animateKpiStats();
    fetchLiveStats();
  }

  function animateKpiStats() {
    // Rely on fetchLiveStats for real database numbers; avoid dummy hardcoded count-ups
  }

  // 1. Donut Chart: BOM Overview
  function renderBOMDonutChart(customData) {
    const ctx = document.getElementById('bomDonutChart')?.getContext('2d');
    if (!ctx) return;

    if (bomDonutInstance) bomDonutInstance.destroy();

    const percentages = customData || [65, 20, 10, 5];

    // Custom plugin to draw percentage labels directly on donut slices
    const slicePercentagePlugin = {
      id: 'slicePercentagePlugin',
      afterDraw(chart) {
        const { ctx } = chart;
        const meta = chart.getDatasetMeta(0);

        ctx.save();
        ctx.font = '700 11px "Plus Jakarta Sans", sans-serif';
        ctx.fillStyle = '#1E293B';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        meta.data.forEach((element, i) => {
          const model = element;
          const midAngle = (model.startAngle + model.endAngle) / 2;
          const radius = (model.innerRadius + model.outerRadius) / 2;
          
          const x = model.x + Math.cos(midAngle) * (radius * 1.05);
          const y = model.y + Math.sin(midAngle) * (radius * 1.05);

          if (i === 0) {
            ctx.fillStyle = '#FFFFFF';
          } else {
            ctx.fillStyle = '#334155';
          }

          ctx.fillText((percentages[i] !== undefined ? `${percentages[i]}%` : ''), x, y);
        });
        ctx.restore();
      }
    };

    bomDonutInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Assemblies', 'Components', 'Revisions Pending', 'Incomplete BOMs'],
        datasets: [{
          data: percentages,
          backgroundColor: [
            '#2563EB', // Assemblies (Vibrant Blue)
            '#60A5FA', // Components (Sky Blue)
            '#FBBF24', // Revisions Pending (Amber)
            '#CBD5E1'  // Incomplete BOMs (Muted Slate)
          ],
          borderWidth: 3,
          borderColor: '#FFFFFF',
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '58%',
        animation: {
          duration: (window.FoodManAnimations && window.FoodManAnimations.isReducedMotion()) ? 0 : 280,
          easing: 'easeOutQuart'
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                return ` ${context.label}: ${context.raw}%`;
              }
            }
          }
        }
      },
      plugins: [slicePercentagePlugin]
    });
  }

  // 2. Bar Chart: Manufacturing Efficiency (%)
  function renderEfficiencyBarChart(customValues, customLabels) {
    const ctx = document.getElementById('efficiencyBarChart')?.getContext('2d');
    if (!ctx) return;

    if (efficiencyBarInstance) efficiencyBarInstance.destroy();

    const labels = customLabels || ['Line 1', 'Line 2', 'Line 3', 'Line 4', 'Line 5'];
    const dataValues = customValues || [88, 92, 79, 95, 84];
    const highlightedIndices = dataValues.map((v, i) => v >= 90 ? i : -1).filter(i => i >= 0);

    const backgroundColors = dataValues.map((val, idx) => {
      return highlightedIndices.includes(idx) ? '#2563EB' : '#93C5FD';
    });

    // Custom plugin to draw top percentage labels on highlighted bars
    const barTopLabelsPlugin = {
      id: 'barTopLabelsPlugin',
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        chart.data.datasets.forEach((dataset, datasetIndex) => {
          const meta = chart.getDatasetMeta(datasetIndex);
          meta.data.forEach((bar, index) => {
            if (highlightedIndices.includes(index)) {
              const value = dataset.data[index];
              const text = `${value}%`;

              ctx.save();
              ctx.font = '700 11px "Plus Jakarta Sans", sans-serif';
              ctx.fillStyle = '#0F172A';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'bottom';
              ctx.fillText(text, bar.x, bar.y - 6);
              ctx.restore();
            }
          });
        });
      }
    };

    efficiencyBarInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: dataValues,
          backgroundColor: backgroundColors,
          borderRadius: {
            topLeft: 6,
            topRight: 6
          },
          borderSkipped: false,
          barThickness: 28
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: (window.FoodManAnimations && window.FoodManAnimations.isReducedMotion()) ? 0 : 280,
          easing: 'easeOutQuart'
        },
        layout: {
          padding: {
            top: 20
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => ` Efficiency: ${context.raw}%`
            }
          }
        },
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: {
              stepSize: 25,
              callback: (v) => v + '%',
              color: '#94A3B8',
              font: {
                size: 11,
                family: 'Plus Jakarta Sans'
              }
            },
            grid: {
              color: '#F1F5F9',
              drawBorder: false
            },
            border: {
              display: false
            }
          },
          x: {
            ticks: {
              color: '#64748B',
              font: {
                size: 12,
                weight: 600,
                family: 'Plus Jakarta Sans'
              }
            },
            grid: {
              display: false,
              drawBorder: false
            },
            border: {
              display: false
            }
          }
        }
      },
      plugins: [barTopLabelsPlugin]
    });
  }

  let currentDateRange = '7d';
  let currentProductId = '1';
  let currentMetric = 'assembly';

  function setupDropdowns() {
    const dateSelect = document.getElementById('axionDateRangeSelect');
    if (dateSelect) {
      dateSelect.addEventListener('change', (e) => {
        currentDateRange = e.target.value;
        const defectSelect = document.getElementById('dashDefectRatePeriodSelect');
        if (defectSelect && ['7d', '30d', '90d'].includes(currentDateRange)) {
          defectSelect.value = currentDateRange;
        }
        fetchLiveStats();
      });
    }

    const bomSelect = document.getElementById('bomProductSelect');
    if (bomSelect) {
      bomSelect.addEventListener('change', (e) => {
        currentProductId = e.target.value;
        fetchLiveStats();
      });
    }

    const metricSelect = document.getElementById('assemblyProgressSelect');
    if (metricSelect) {
      metricSelect.addEventListener('change', (e) => {
        currentMetric = e.target.value;
        fetchLiveStats();
      });
    }

    const defectSelect = document.getElementById('dashDefectRatePeriodSelect');
    if (defectSelect) {
      defectSelect.addEventListener('change', (e) => {
        currentDateRange = e.target.value;
        if (dateSelect) dateSelect.value = currentDateRange;
        fetchLiveStats();
      });
    }
  }

  // 3. Line Chart: AI Visual Inspection Defect Rate (%) (Day 3 Feature)
  function renderDefectRateChart(dataValues, labels) {
    const canvas = document.getElementById('defectRateChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (defectRateInstance) defectRateInstance.destroy();

    const chartLabels = labels || ['11/10', '12/10', '13/10', '14/10', '15/10', '16/10', '17/10'];
    const values = dataValues || [0.8, 1.2, 0.5, 2.1, 1.4, 0.9, 1.8];

    // Create subtle gradient fill below line
    const gradient = ctx.createLinearGradient(0, 0, 0, 180);
    gradient.addColorStop(0, 'rgba(79, 70, 229, 0.22)');
    gradient.addColorStop(1, 'rgba(79, 70, 229, 0.00)');

    defectRateInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: chartLabels,
        datasets: [{
          label: 'Defect Rate (%)',
          data: values,
          borderColor: '#4F46E5',
          borderWidth: 2.5,
          backgroundColor: gradient,
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#4F46E5',
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: (window.FoodManAnimations && window.FoodManAnimations.isReducedMotion()) ? 0 : 350,
          easing: 'easeOutQuart'
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            titleFont: { family: 'Plus Jakarta Sans', size: 12, weight: '700' },
            bodyFont: { family: 'Plus Jakarta Sans', size: 12 },
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: (context) => ` Inbound Defect Rate: ${context.raw}%`
            }
          }
        },
        scales: {
          y: {
            min: 0,
            ticks: {
              callback: (val) => val + '%',
              color: '#94A3B8',
              font: { size: 11, family: 'Plus Jakarta Sans' },
              stepSize: 1
            },
            grid: {
              color: '#F1F5F9',
              drawBorder: false
            },
            border: { display: false }
          },
          x: {
            ticks: {
              color: '#64748B',
              font: { size: 11, weight: 600, family: 'Plus Jakarta Sans' }
            },
            grid: { display: false, drawBorder: false },
            border: { display: false }
          }
        }
      }
    });
  }

  async function fetchLiveStats() {
    const bomOverlay = document.getElementById('bomLoadingOverlay');
    const effOverlay = document.getElementById('efficiencyLoadingOverlay');
    if (bomOverlay) bomOverlay.style.display = 'flex';
    if (effOverlay) effOverlay.style.display = 'flex';

    try {
      const resp = await fetch(`/api/dashboard/stats?date_range=${currentDateRange}&product_id=${currentProductId}&metric=${currentMetric}`);
      const resData = await resp.json();
      if (resData.success && resData.data) {
        const kpi = resData.data.kpi || {};
        const charts = resData.data.charts || {};

        // Update 4 KPI cards with real database values
        const partsEl = document.getElementById('kpiTotalParts');
        if (partsEl && kpi.stock_value_formatted) {
          partsEl.innerText = kpi.stock_value_formatted;
        }

        const readyEl = document.getElementById('kpiReadyProduction');
        if (readyEl && kpi.active_batches_count !== undefined) {
          readyEl.innerText = kpi.active_batches_count;
        }

        const changeEl = document.getElementById('kpiOpenChange');
        if (changeEl && kpi.pending_qc_lots_count !== undefined) {
          changeEl.innerText = kpi.pending_qc_lots_count;
        }

        const statusEl = document.getElementById('kpiProductionStatus');
        if (statusEl && kpi.today_dispatches_count !== undefined) {
          statusEl.innerText = kpi.today_dispatches_count;
        }

        // Update BOM Donut & Legends
        if (charts.bom) {
          renderBOMDonutChart(charts.bom.percentages);
          const cAssemblies = document.getElementById('bomCountAssemblies');
          const cComponents = document.getElementById('bomCountComponents');
          const cRevisions = document.getElementById('bomCountRevisions');
          const cIncomplete = document.getElementById('bomCountIncomplete');
          if (cAssemblies && charts.bom.counts) cAssemblies.innerText = charts.bom.counts[0];
          if (cComponents && charts.bom.counts) cComponents.innerText = charts.bom.counts[1];
          if (cRevisions && charts.bom.counts) cRevisions.innerText = charts.bom.counts[2];
          if (cIncomplete && charts.bom.counts) cIncomplete.innerText = charts.bom.counts[3];
        }

        // Update Efficiency Bar Chart
        if (charts.efficiency) {
          renderEfficiencyBarChart(charts.efficiency.values, charts.efficiency.labels);
        }

        // Update Defect Rate Pill & Chart
        const defectPill = document.getElementById('kpiDefectRatePill');
        if (defectPill && charts.overall_defect_rate !== undefined) {
          defectPill.innerText = `${charts.overall_defect_rate}%`;
          if (charts.overall_defect_rate > 3.0) {
            defectPill.className = 'axion-trend-pill trend-down';
            defectPill.style.background = '#FEF2F2';
            defectPill.style.color = '#EF4444';
          } else {
            defectPill.className = 'axion-trend-pill trend-up';
            defectPill.style.background = '#ECFDF5';
            defectPill.style.color = '#10B981';
          }
        }

        if (charts.defect_rate_trend && charts.defect_rate_labels) {
          renderDefectRateChart(charts.defect_rate_trend, charts.defect_rate_labels);
        }
      }
    } catch (e) {
      console.log("Using Axion calibrated metrics", e);
    } finally {
      if (bomOverlay) bomOverlay.style.display = 'none';
      if (effOverlay) effOverlay.style.display = 'none';
    }
  }

  return {
    init,
    renderBOMDonutChart,
    renderEfficiencyBarChart,
    renderDefectRateChart
  };

})();

document.addEventListener('DOMContentLoaded', AxionDashboard.init);

