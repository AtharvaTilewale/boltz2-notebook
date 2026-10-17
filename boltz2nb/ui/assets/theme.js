/* Boltz2 Notebook - colour theme shared by every panel on the page. Vanilla ES2017, no dependencies.
   Light is the default. The choice is kept on <html data-bz-theme> (which outlives the run panel's refreshes), in localStorage
   (so a saved report or the website remembers it) and in the Python session (so panels drawn later start in the same theme). */
(function () {
'use strict';
var W = window, D = document, KEY = 'bz-theme', current = null;
if (W.__bzTheme) { W.__bzTheme.apply(); return; }

function valid(t) { return t === 'light' || t === 'dark'; }
function stored() { try { var v = W.localStorage.getItem(KEY); return valid(v) ? v : null; } catch (e) { return null; } }
function hint() {   // the theme Python drew the first panel in
  var el = D.querySelector('.bz[data-theme]'), v = el ? el.getAttribute('data-theme') : null;
  return valid(v) ? v : null;
}
function tellPython(t) {
  try {
    var k = W.google && W.google.colab && W.google.colab.kernel;
    var p = k && k.invokeFunction ? k.invokeFunction('set_theme', [t], {}) : null;
    if (p && p.catch) { p.catch(function () { /* kernel busy or callback not registered: the browser keeps the choice */ }); }
  } catch (e) { /* ignore */ }
}

var api = W.__bzTheme = {
  get: function () { return current || hint() || stored() || 'light'; },
  apply: function () {
    var t = api.get(), label = t === 'dark' ? 'Switch to light theme' : 'Switch to dark theme', i, list;
    D.documentElement.setAttribute('data-bz-theme', t);
    list = D.querySelectorAll('.bz');
    for (i = 0; i < list.length; i++) { list[i].setAttribute('data-theme', t); }
    if (list.length) { current = t; }          // adopt the first panel's theme only once a panel exists
    list = D.querySelectorAll('[data-act="theme"]');
    for (i = 0; i < list.length; i++) { list[i].setAttribute('title', label); list[i].setAttribute('aria-label', label); }
    return t;
  },
  set: function (t) {
    if (!valid(t)) { return; }
    current = t;
    try { W.localStorage.setItem(KEY, t); } catch (e) { /* storage may be blocked */ }
    api.apply();
    tellPython(t);
    try { W.dispatchEvent(new CustomEvent('bz-theme', { detail: t })); } catch (e) { /* ignore */ }
  }
};

D.addEventListener('click', function (ev) {
  var b = ev.target && ev.target.closest ? ev.target.closest('[data-act="theme"]') : null;
  if (b) { api.set(api.get() === 'dark' ? 'light' : 'dark'); }
});
// Printed pages are light whatever the screen theme is (dark text colours would vanish without backgrounds).
W.addEventListener('beforeprint', function () {
  var list = D.querySelectorAll('.bz'), i;
  D.documentElement.setAttribute('data-bz-theme', 'light');
  for (i = 0; i < list.length; i++) { list[i].setAttribute('data-theme', 'light'); }
});
W.addEventListener('afterprint', function () { api.apply(); });
W.addEventListener('storage', function (ev) { if (ev.key === KEY && valid(ev.newValue)) { current = ev.newValue; api.apply(); } });
api.apply();
})();
