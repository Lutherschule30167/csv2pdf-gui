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
})();
