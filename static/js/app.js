/**
 * FOOD MAN - MAIN APP CONTROLLER
 * Handles:
 * - Module switching & fetching generic prop-driven cards
 * - Search & status filtering (ALL, PENDING, APPROVED, HOLD, REJECTED)
 * - DetailDrawer slide-in & saving updates via REST API
 * - Live topbar clock
 */

const FoodManApp = (() => {
  let drawer = null;
  let currentCards = [];
  let selectedCardId = null;
  let currentStatusFilter = 'ALL';
  let searchQuery = '';

  function init(activeModule) {
    drawer = new FoodManComponents.DetailDrawerController('detailDrawerRoot', 'drawerBackdrop');
    startLiveClock();
    setupEventListeners();
    loadCards(activeModule);
  }

  function setupEventListeners() {
    const searchInput = document.getElementById('topbarSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value.toLowerCase().trim();
        renderCards();
      });
    }

    document.querySelectorAll('.tab-pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentStatusFilter = btn.dataset.status;
        renderCards();
      });
    });
  }

  async function loadCards(module) {
    const container = document.getElementById('recordCardsContainer');
    if (!container) return;

    container.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
        Đang tải dữ liệu từ máy chủ...
      </div>
    `;

    try {
      const res = await fetch(`/api/cards?module=${encodeURIComponent(module)}`);
      if (!res.ok) throw new Error("Failed to fetch cards");
      const data = await res.json();
      currentCards = data.cards || [];
      renderCards();
    } catch (err) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #DC2626;">
          Không thể tải dữ liệu: ${err.message}
        </div>
      `;
    }
  }

  function renderCards() {
    const container = document.getElementById('recordCardsContainer');
    if (!container) return;

    const filtered = currentCards.filter(card => {
      const matchStatus = (currentStatusFilter === 'ALL') || (card.status === currentStatusFilter);
      const matchSearch = !searchQuery ||
        card.id.toLowerCase().includes(searchQuery) ||
        card.title.toLowerCase().includes(searchQuery) ||
        (card.category && card.category.toLowerCase().includes(searchQuery));
      return matchStatus && matchSearch;
    });

    // Update counts
    const countBadge = document.getElementById('headerRecordCount');
    if (countBadge) countBadge.textContent = `${filtered.length} bản ghi`;

    if (filtered.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--border-subtle);">
          <div style="font-size: 15px; font-weight: 700; color: var(--text-main);">Chưa có bản ghi nào phù hợp</div>
          <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">Thử điều chỉnh bộ lọc hoặc từ khóa tìm kiếm.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(card => {
      const isSelected = card.id === selectedCardId;
      return FoodManComponents.RecordCard({
        ...card,
        isActive: isSelected
      });
    }).join('');
  }

  function selectCard(cardId) {
    selectedCardId = cardId;
    renderCards();
    const card = currentCards.find(c => c.id === cardId);
    if (!card) return;

    drawer.open(card, (item, newStatus) => {
      handleSaveCard(item, newStatus);
    });
  }

  function clearCardSelection() {
    selectedCardId = null;
    renderCards();
  }

  async function handleSaveCard(item, newStatus) {
    try {
      const res = await fetch(`/api/cards/${item.module}/${item.db_id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });

      if (!res.ok) throw new Error("Cập nhật thất bại");
      const result = await res.json();

      item.status = newStatus;
      item.statusLabel = result.label;
      item.statusPill = result.pill;

      renderCards();
      drawer.close();
      alert(`Đã cập nhật trạng thái của ${item.id} thành ${newStatus}!`);
    } catch (err) {
      alert(`Lỗi: ${err.message}`);
    }
  }

  function startLiveClock() {
    function update() {
      const now = new Date();
      const days = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
      const dayStr = days[now.getDay()];
      const dateStr = `${String(now.getDate()).padStart(2, '0')}/${String(now.getMonth() + 1).padStart(2, '0')}/${now.getFullYear()}`;
      const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

      const dateEl = document.getElementById('liveDateText');
      const timeEl = document.getElementById('liveTimeText');

      if (dateEl) dateEl.textContent = `${dayStr}, ${dateStr}`;
      if (timeEl) timeEl.textContent = timeStr;
    }
    update();
    setInterval(update, 1000);
  }

  return {
    init,
    selectCard,
    clearCardSelection
  };
})();
