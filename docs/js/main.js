(function () {
  // Mobile navigation toggle
  var navToggle = document.getElementById('navToggle');
  var primaryNav = document.getElementById('primaryNav');

  if (navToggle && primaryNav) {
    navToggle.addEventListener('click', function () {
      var isOpen = primaryNav.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });

    primaryNav.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        primaryNav.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  // Installation tabs
  var tabs = document.querySelectorAll('.tab');
  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      var panelId = tab.getAttribute('aria-controls');
      var tabList = tab.closest('.tabs');

      tabList.querySelectorAll('.tab').forEach(function (t) {
        t.setAttribute('aria-selected', 'false');
      });
      tabList.querySelectorAll('.tab-panel').forEach(function (p) {
        p.classList.remove('active');
      });

      tab.setAttribute('aria-selected', 'true');
      document.getElementById(panelId).classList.add('active');
    });
  });

  // Datum der aktuellen csv2pdf-gui.exe aus dem neuesten Release laden.
  // Ohne Netz oder bei API-Limit bleibt das Datum aus dem HTML stehen.
  var exeDates = document.querySelectorAll('.exe-date');
  if (exeDates.length && window.fetch) {
    fetch('https://api.github.com/repos/Lutherschule30167/csv2pdf-gui/releases/latest')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (release) {
        if (!release || !release.assets) return;
        var exe = release.assets.filter(function (a) { return a.name === 'csv2pdf-gui.exe'; })[0];
        if (!exe) return;
        var d = new Date(exe.updated_at);
        if (isNaN(d)) return;
        var text = d.toLocaleDateString('de-DE', { day: 'numeric', month: 'long', year: 'numeric' });
        exeDates.forEach(function (el) {
          el.textContent = text;
          el.setAttribute('datetime', exe.updated_at.slice(0, 10));
        });
      })
      .catch(function () {});
  }
})();
