document.addEventListener('DOMContentLoaded', function () {
  const modal = document.getElementById('tradeModal');
  const openBtn = document.getElementById('openModalBtn');
  const closeBtn = document.getElementById('closeModalBtn');
  const tradeForm = document.getElementById('tradeForm');
  const filtersForm = document.getElementById('filtersForm');
  const toggleBtn = document.getElementById('toggleFilters');

  // 🟢 Öppna ny modal (lägg till trade)
  if (openBtn) {
    openBtn.addEventListener('click', () => {
      tradeForm.action = '/upload';
      tradeForm.reset();
      tradeForm.querySelector('input[name="trade_id"]').value = "";
      modal.classList.remove('hidden');
      tradeForm.querySelector('input[name="bild1"]').required = true;
      tradeForm.querySelector('input[name="bild2"]').required = true;
    });
  }

  // 🔴 Stäng modal
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      modal.classList.add('hidden');
    });
  }

  // Klick utanför modalen stänger den
  window.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.classList.add('hidden');
    }
  });

  // 🟣 Visa/Dölj filtrering
  if (toggleBtn && filtersForm) {
    toggleBtn.addEventListener('click', () => {
      filtersForm.classList.toggle('hidden');
    });
  }

  // 🔁 Koppla redigera-knappar
  function rebindEditButtons() {
    document.querySelectorAll('[data-edit-id]').forEach(button => {
      button.addEventListener('click', () => {
        const tradeId = button.getAttribute('data-edit-id');
        openEditModal(tradeId);
      });
    });
  }

  rebindEditButtons(); // Kör vid laddning

  // ✏️ Redigera befintlig trade
  window.openEditModal = function (tradeId) {
    fetch(`/get_trade/${tradeId}`)
      .then(response => response.json())
      .then(data => {
        modal.classList.remove('hidden');
        tradeForm.action = '/update';
        tradeForm.querySelector('input[name="bild1"]').required = false;
        tradeForm.querySelector('input[name="bild2"]').required = false;

        // Fyll formulär
        tradeForm.querySelector('input[name="trade_id"]').value = data.id || "";
        tradeForm.querySelector('input[name="datum"]').value = data.datum || "";
        tradeForm.querySelector('select[name="instrument"]').value = data.instrument || "";
        tradeForm.querySelector('select[name="setup"]').value = data.setup || "";
        tradeForm.querySelector('input[name="rr_logisk"]').value = data.rr_logisk || "";
        tradeForm.querySelector('input[name="rr_max"]').value = data.rr_max || "";
        tradeForm.querySelector('textarea[name="kommentar"]').value = data.kommentar || "";

        // 🔢 Nya numeriska fält
        tradeForm.querySelector('input[name="entry_price"]').value = data.entry_price ?? "";
        tradeForm.querySelector('input[name="exit_price"]').value = data.exit_price ?? "";
        tradeForm.querySelector('input[name="stop_loss"]').value = data.stop_loss ?? "";
        tradeForm.querySelector('input[name="take_profit"]').value = data.take_profit ?? "";
        tradeForm.querySelector('input[name="quantity"]').value = data.quantity ?? "";
        tradeForm.querySelector('input[name="fees"]').value = data.fees ?? "";
        tradeForm.querySelector('input[name="exit_date"]').value = data.exit_date ?? "";
        tradeForm.querySelector('input[name="gross_pl"]').value = data.gross_pl ?? "";
        tradeForm.querySelector('input[name="net_pl"]').value = data.net_pl ?? "";
        tradeForm.querySelector('input[name="exit_price_max"]').value = data.exit_price_max ?? "";


        ['direction', 'outcome'].forEach(field => {
          if (data[field]) {
            const radio = tradeForm.querySelector(`input[name="${field}"][value="${data[field]}"]`);
            if (radio) radio.checked = true;
          }
        });

        const checkboxFields = [
          { name: 'regler[]', dataKey: 'regler' },
          { name: 'entry_logic', dataKey: 'entry_logic' },
          { name: 'exit_logic', dataKey: 'exit_logic' },
          { name: 'premarket', dataKey: 'premarket' },
          { name: 'obalans', dataKey: 'obalans' },
          { name: 'återtesten', dataKey: 'återtesten' },
          { name: 'reversal_rules', dataKey: 'reversal_rules' },
          { name: 'continuation_rules', dataKey: 'continuation_rules' }
        ];

        checkboxFields.forEach(({ name, dataKey }) => {
          tradeForm.querySelectorAll(`input[name="${name}"]`).forEach(cb => cb.checked = false);
          const values = (data[dataKey] || "").split(',').map(s => s.trim());
          values.forEach(val => {
            const checkbox = tradeForm.querySelector(`input[name="${name}"][value="${val}"]`);
            if (checkbox) checkbox.checked = true;
          });
        });
      });
  };

  // 📌 Hoppa till trade om #trade-id finns i URL (efter update t.ex.)
  if (window.location.hash.startsWith("#trade-")) {
    const el = document.querySelector(window.location.hash);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // 🔁 Fliksystem
  const tabButtons = document.querySelectorAll('.tab-button');
  const tabContents = document.querySelectorAll('.tab-content');
  const modalContent = document.getElementById('modalContent');

  function adjustModalHeight() {
    tabContents.forEach(tab => tab.classList.remove('hidden'));

    let maxHeight = 0;
    tabContents.forEach(tab => {
      const height = tab.offsetHeight;
      if (height > maxHeight) {
        maxHeight = height;
      }
    });

    if (modalContent) {
      modalContent.style.minHeight = (maxHeight + 300) + 'px';
    }

    const activeTabId = document.querySelector('.tab-button.border-green-500')?.dataset.tab || "tab1";
    tabContents.forEach(tab => {
      tab.classList.toggle('hidden', tab.id !== activeTabId);
    });
  }

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('border-green-500'));
      btn.classList.add('border-green-500');
      adjustModalHeight();
    });
  });

  if (tabButtons.length > 0) {
    tabButtons[0].classList.add('border-green-500');
    adjustModalHeight();
  }

  // 🔽 Dropdown-filter (filtrering/header)
  document.querySelectorAll('.filter-dropdown-toggle').forEach(btn => {
    const dropdown = btn.nextElementSibling;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.classList.toggle('hidden');
    });
    window.addEventListener('click', () => dropdown.classList.add('hidden'));
    dropdown.addEventListener('click', (e) => e.stopPropagation());
  });

  // 🔽 Dropdowns för taggar i modalen (flik 2)
  const tagDropdowns = [
    { btnId: 'entryLogicBtn', menuId: 'entryLogicDropdown' },
    { btnId: 'exitLogicBtn', menuId: 'exitLogicDropdown' },
    { btnId: 'preMarketBtn', menuId: 'preMarketDropdown' },
    { btnId: 'obalansBtn', menuId: 'obalansDropdown' },
    { btnId: 'återtestenBtn', menuId: 'återtestenDropdown' },
    { btnId: 'reversalRulesBtn', menuId: 'reversalRulesDropdown' },
    { btnId: 'continuationRulesBtn', menuId: 'continuationRulesDropdown' }
  ];

  tagDropdowns.forEach(({ btnId, menuId }) => {
    const btn = document.getElementById(btnId);
    const menu = document.getElementById(menuId);

    if (btn && menu) {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.toggle('hidden');
      });

      window.addEventListener('click', () => {
        menu.classList.add('hidden');
      });

      menu.addEventListener('click', (e) => {
        e.stopPropagation();
      });
    }
  });

  // 📤 Skicka formuläret direkt när något filter ändras
  document.querySelectorAll('#filtersForm select, #filtersForm input[type="date"], #filtersForm input[type="checkbox"]').forEach(el => {
    el.addEventListener('change', () => {
      document.getElementById('filtersForm').submit();
    });
  });

  // 🔁 Klicka på rad för att redigera trade
  document.querySelectorAll('tr[data-edit-id]').forEach(row => {
    row.addEventListener('click', () => {
      const tradeId = row.getAttribute('data-edit-id');
      if (tradeId) openEditModal(tradeId);
    });
  });

  // 🔔 Auto-stäng flash-meddelande
  const flashContainer = document.getElementById("flash-messages");
  if (flashContainer) {
    setTimeout(() => {
      flashContainer.remove();
    }, 4000); // 4 sekunder
  }
});

