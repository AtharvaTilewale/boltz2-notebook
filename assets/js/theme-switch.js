/* Boltz2 Notebook website - light / dark switch (vanilla JS, no dependencies).
   The site opens in its dark design. Choosing light sets <html data-theme="light"> and is remembered in this browser.
   A two-line snippet in each page's <head> applies a remembered choice before the first paint, so there is no flash. */
(function () {
  'use strict';
  var KEY = 'bz-site-theme', root = document.documentElement;
  var COLORS = { dark: '#0b1020', light: '#f4f7fc' };

  function stored() {
    try { var v = window.localStorage.getItem(KEY); return v === 'light' || v === 'dark' ? v : null; } catch (e) { return null; }
  }
  function current() { return root.getAttribute('data-theme') === 'light' ? 'light' : 'dark'; }

  function paint() {
    var t = current(), label = t === 'light' ? 'Switch to dark theme' : 'Switch to light theme';
    var buttons = document.querySelectorAll('[data-act="theme"]'), i;
    for (i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute('aria-label', label);
      buttons[i].setAttribute('title', label);
    }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) { meta.setAttribute('content', COLORS[t]); }
  }

  function set(t, remember) {
    if (t === 'light') { root.setAttribute('data-theme', 'light'); } else { root.removeAttribute('data-theme'); }
    if (remember) { try { window.localStorage.setItem(KEY, t); } catch (e) { /* storage may be blocked */ } }
    paint();
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target && ev.target.closest ? ev.target.closest('[data-act="theme"]') : null;
    if (b) { set(current() === 'light' ? 'dark' : 'light', true); }
  });
  window.addEventListener('storage', function (ev) {      // another tab changed it
    if (ev.key === KEY && (ev.newValue === 'light' || ev.newValue === 'dark')) { set(ev.newValue, false); }
  });
  // Printed pages are light whatever the screen theme is (pale text would vanish on white paper).
  var screenTheme = null;
  window.addEventListener('beforeprint', function () { screenTheme = current(); root.setAttribute('data-theme', 'light'); });
  window.addEventListener('afterprint', function () { if (screenTheme === 'dark') { root.removeAttribute('data-theme'); } screenTheme = null; });

  if (stored() === 'light') { set('light', false); } else { paint(); }
}());
