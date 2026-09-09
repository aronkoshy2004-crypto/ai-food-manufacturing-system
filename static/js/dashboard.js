/**
 * Axion Manufacturing Dashboard Controller
 * Renders BOM Overview Donut Chart & Manufacturing Efficiency Bar Chart matching the reference design.
 */
const AxionDashboard = (function() {

  let bomDonutInstance = null;
  let efficiencyBarInstance = null;

  async function init() {
    renderBOMDonutChart();
    renderEfficiencyBarChart();
    setupDropdowns();
    animateKpiStats();
    fetchLiveStats();
  }

  function animateKpiStats() {
    if (window.FoodManAnimations) {
      const elParts = document.getElementById('kpiTotalParts');
      if (elParts) window.FoodManAnimations.countUp(elParts, 0, 1250, 280, v => v.toLocaleString());

      const elReady = document.getElementById('kpiReadyProduction');
      if (elReady) window.FoodManAnimations.countUp(elReady, 0, 68, 280, v => v + ' %');

      const elChange = document.getElementById('kpiOpenChange');
      if (elChange) window.FoodManAnimations.countUp(elChange, 0, 25, 280);

      const elStatus = document.getElementById('kpiProductionStatus');
      if (elStatus) window.FoodManAnimations.countUp(elStatus, 0, 12, 280);
    }
  }

  // 1. Donut Chart: BOM Overview
  function renderBOMDonutChart() {
    const ctx = document.getElementById('bomDonutChart')?.getContext('2d');
    if (!ctx) return;

    if (bomDonutInstance) bomDonutInstance.destroy();

    // Custom plugin to draw percentage labels directly on donut slices
    const slicePercentagePlugin = {
      id: 'slicePercentagePlugin',
      afterDraw(chart) {
        const { ctx } = chart;
        const meta = chart.getDatasetMeta(0);
        const percentages = ['65%', '20%', '10%', '5%'];

        ctx.save();
        ctx.font = '700 11px "Plus Jakarta Sans", sans-serif';
        ctx.fillStyle = '#1E293B';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        meta.data.forEach((element, i) => {
          // Calculate midpoint angle of arc
          const model = element;
          const midAngle = (model.startAngle + model.endAngle) / 2;
          const radius = (model.innerRadius + model.outerRadius) / 2;
          
          // Position text slightly outward
          const x = model.x + Math.cos(midAngle) * (radius * 1.05);
          const y = model.y + Math.sin(midAngle) * (radius * 1.05);

          // For the dominant blue slice (65%), draw text in white
          if (i === 0) {
            ctx.fillStyle = '#FFFFFF';
          } else {
            ctx.fillStyle = '#334155';
          }

          ctx.fillText(percentages[i] || '', x, y);
        });
        ctx.restore();
      }
    };

    bomDonutInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Assemblies', 'Components', 'Revisions Pending', 'Incomplete BOMs'],
        datasets: [{
          data: [65, 20, 10, 5],
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
  function renderEfficiencyBarChart() {
    const ctx = document.getElementById('efficiencyBarChart')?.getContext('2d');
    if (!ctx) return;

    if (efficiencyBarInstance) efficiencyBarInstance.destroy();

    // Data corresponding to Jan-Jun with peaks at Mar (100%), May (90%), Jun (85%)
    const labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
    const dataValues = [70, 75, 100, 75, 90, 85];
    const highlightedIndices = [2, 4, 5]; // Mar (100%), May (90%), Jun (85%)

    const backgroundColors = dataValues.map((val, idx) => {
      return highlightedIndices.includes(idx) ? '#2563EB' : '#E2E8F0';
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

  function setupDropdowns() {
    const bomSelect = document.getElementById('bomProductSelect');
    if (bomSelect) {
      bomSelect.addEventListener('click', () => {
        const currentText = bomSelect.querySelector('span');
        if (currentText.innerText === 'Product Alpha') {
          currentText.innerText = 'Product Beta';
          if (bomDonutInstance) {
            bomDonutInstance.data.datasets[0].data = [50, 30, 15, 5];
            bomDonutInstance.update(150);
          }
        } else {
          currentText.innerText = 'Product Alpha';
          if (bomDonutInstance) {
            bomDonutInstance.data.datasets[0].data = [65, 20, 10, 5];
            bomDonutInstance.update(150);
          }
        }
      });
    }

    const dateBtn = document.getElementById('axionDateRangeBtn');
    if (dateBtn) {
      dateBtn.addEventListener('click', () => {
        dateBtn.classList.toggle('active');
      });
    }
  }

  async function fetchLiveStats() {
    try {
      const resp = await fetch('/api/dashboard/stats');
      const resData = await resp.json();
      if (resData.success && resData.data && resData.data.kpi) {
        const kpi = resData.data.kpi;
        // Optionally update production status count or keep demo matching screenshot
        const statusEl = document.getElementById('kpiProductionStatus');
        if (statusEl && kpi.active_batches_count !== undefined) {
          statusEl.innerText = kpi.active_batches_count || 12;
        }
      }
    } catch (e) {
      console.log("Using Axion calibrated metrics", e);
    }
  }

  return {
    init,
    renderBOMDonutChart,
    renderEfficiencyBarChart
  };

})();

document.addEventListener('DOMContentLoaded', AxionDashboard.init);

