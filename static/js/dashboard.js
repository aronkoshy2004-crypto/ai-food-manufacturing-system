/**
 * Food Man - Phase 4 Central Dashboard & Chart.js Visual Analytics Controller
 */
const DashboardAnalytics = (function() {

  let trendChartInstance = null;
  let donutChartInstance = null;

  async function init() {
    try {
      const resp = await fetch('/api/dashboard/stats');
      const resData = await resp.json();
      if (resData.success) {
        updateKPIs(resData.data.kpi);
        renderCharts(resData.data.charts);
      }
    } catch (e) {
      console.error("Failed loading dashboard analytics", e);
    }
  }

  function updateKPIs(kpi) {
    if (!kpi) return;
    const stockVal = document.getElementById('kpiStockValue');
    const expCount = document.getElementById('kpiExpiringCount');
    const dispCount = document.getElementById('kpiDispatchesCount');
    const dispVol = document.getElementById('kpiDispatchVolume');
    const alertCount = document.getElementById('kpiAlertsCount');

    if (stockVal) stockVal.innerText = kpi.stock_value_formatted || '1.58 Tỷ VNĐ';
    if (expCount) expCount.innerText = `${kpi.expiring_soon_count || 1} Lô`;
    if (dispCount) dispCount.innerText = `${kpi.today_dispatches_count || 4} Chuyến`;
    if (dispVol) dispVol.innerText = (kpi.today_dispatch_volume || 4200).toLocaleString();
    if (alertCount) alertCount.innerText = `${kpi.open_alerts_count || 2} Cảnh báo`;
  }

  function renderCharts(chartData) {
    if (!chartData || typeof Chart === 'undefined') return;

    // 1. Dual-line Trend Chart
    const trendCtx = document.getElementById('productionTrendChart')?.getContext('2d');
    if (trendCtx) {
      if (trendChartInstance) trendChartInstance.destroy();
      trendChartInstance = new Chart(trendCtx, {
        type: 'line',
        data: {
          labels: chartData.trend_labels || ['02/09', '03/09', '04/09', '05/09', '06/09', '07/09', '08/09'],
          datasets: [
            {
              label: 'Sản xuất (Thùng)',
              data: chartData.production_trend || [4500, 5200, 4800, 5100, 4900, 5300, 5000],
              borderColor: '#162B4E',
              backgroundColor: 'rgba(22, 43, 78, 0.08)',
              borderWidth: 2.5,
              tension: 0.35,
              fill: true
            },
            {
              label: 'Xuất kho (Thùng)',
              data: chartData.dispatch_trend || [3800, 4100, 4400, 4200, 4700, 4500, 4200],
              borderColor: '#10B981',
              backgroundColor: 'rgba(16, 185, 129, 0.05)',
              borderWidth: 2.5,
              tension: 0.35,
              fill: true
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            y: {
              beginAtZero: false,
              grid: { color: '#F1F4F9' }
            },
            x: {
              grid: { display: false }
            }
          }
        }
      });
    }

    // 2. Donut Category Chart
    const donutCtx = document.getElementById('categoryDonutChart')?.getContext('2d');
    if (donutCtx) {
      if (donutChartInstance) donutChartInstance.destroy();
      donutChartInstance = new Chart(donutCtx, {
        type: 'doughnut',
        data: {
          labels: chartData.category_labels || ['Sữa tiệt trùng', 'Nước ép', 'Sữa chua'],
          datasets: [
            {
              data: chartData.category_values || [850000000, 420000000, 310000000],
              backgroundColor: ['#162B4E', '#3B82F6', '#10B981'],
              borderWidth: 2,
              borderColor: '#FFFFFF'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                boxWidth: 12,
                font: { size: 11.5, family: 'Plus Jakarta Sans' }
              }
            }
          },
          cutout: '68%'
        }
      });
    }
  }

  return {
    init
  };

})();

document.addEventListener('DOMContentLoaded', DashboardAnalytics.init);
