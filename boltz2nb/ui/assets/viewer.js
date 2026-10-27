/* The 3-D structure viewer of the result card and the report. Plain ES2017, no build step.
   The placeholders __UID__, __FORMAT__, __STRUCTURE__ and __FALLBACK__ are filled in by boltz2nb.ui.results.render_viewer.

   Which atoms are drawn as a cartoon and which as sticks is decided from the atoms themselves (a chain with a protein or nucleic-acid
   backbone is a polymer, everything else is a ligand), not from the ATOM / HETATM record type: a file that flags its records differently
   would otherwise fall back to 3Dmol's default wireframe, a tangle of lines. */
(function () {
  var uid = __UID__, fmt = __FORMAT__, structure = __STRUCTURE__, fallback = __FALLBACK__;
  var host = document.getElementById('v-' + uid), info = document.getElementById('vi-' + uid), tries = 0, injected = false;
  if (!host) { return; }
  var NUCLEIC = { A: 1, C: 1, G: 1, U: 1, T: 1, N: 1, DA: 1, DC: 1, DG: 1, DT: 1, DU: 1, DN: 1 };

  function say(html) { host.innerHTML = '<div class="bz-viewer-msg">' + html + '</div>'; }
  function band(a) { return a.b > 90 ? '#0053D6' : a.b > 70 ? '#65CBF3' : a.b > 50 ? '#FFDB13' : '#FF7D45'; }

  // One entry per chain: is it a polymer (protein / nucleic acid) or a small molecule, and how big is it.
  function chainsOf(atoms) {
    var by = {}, order = [];
    atoms.forEach(function (a) {
      var c = by[a.chain];
      if (!c) { c = by[a.chain] = { id: a.chain, atoms: 0, ca: 0, p: 0, res: {} }; order.push(c); }
      c.atoms += 1; c.res[String(a.resi) + (a.icode || '')] = 1;
      if (a.atom === 'CA' && a.elem === 'C') { c.ca += 1; } else if (a.atom === 'P' && NUCLEIC[a.resn]) { c.p += 1; }
    });
    order.forEach(function (c) {
      c.kind = c.ca >= 3 ? 'protein' : (c.p >= 3 ? 'nucleic acid' : 'ligand');
      c.polymer = c.kind !== 'ligand';
      c.nres = Object.keys(c.res).length;
    });
    return order;
  }
  function describe(chains) {
    return chains.map(function (c) {
      return '<b>' + c.id + '</b> ' + (c.polymer ? c.kind + ', ' + c.nres + (c.nres === 1 ? ' residue' : ' residues') : 'ligand, ' + c.atoms + (c.atoms === 1 ? ' atom' : ' atoms'));
    }).join(' &middot; ');
  }

  function build() {
    host.innerHTML = '';
    var v;
    try { v = $3Dmol.createViewer(host, { backgroundColor: 'white' }); }
    catch (err) { say('The 3-D viewer could not start because this browser has no WebGL. The structure file is saved with the results.'); return; }
    try {
      v.addModel(structure, fmt);
      var atoms = typeof v.selectedAtoms === 'function' ? v.selectedAtoms({}) : null;
      if (atoms && !atoms.length) { say('The viewer could not read the structure. The file is saved with the results.'); return; }
      var chains = atoms ? chainsOf(atoms) : null;
      var poly = chains ? chains.filter(function (c) { return c.polymer; }).map(function (c) { return c.id; }) : null;
      var other = chains ? chains.filter(function (c) { return !c.polymer; }).map(function (c) { return c.id; }) : null;
      if (info && chains) { info.innerHTML = describe(chains) + '<span class="bz-vhelp"> &middot; drag to rotate, scroll to zoom, hover an atom for its pLDDT</span>'; }

      function paint() {
        var color = document.querySelector('input[name="vc-' + uid + '"]:checked').value;
        var style = document.querySelector('input[name="vs-' + uid + '"]:checked').value;
        var spec = {}, ligand = { stick: { radius: 0.22, colorscheme: 'greenCarbon' } };
        spec[style] = color === 'plddt' ? { colorfunc: band } : { colorscheme: 'chain' };
        if (poly === null) {                                  // a viewer that cannot list atoms: fall back on the record type
          v.setStyle({ hetflag: false }, spec); v.setStyle({ hetflag: true }, ligand);
        } else if (!poly.length) {
          v.setStyle({}, ligand);                             // no polymer at all: everything is a small molecule
        } else {
          v.setStyle({ chain: poly }, spec);
          if (other.length) {
            v.setStyle({ chain: other }, ligand);
            try { v.addStyle({ chain: other, bonds: 0 }, { sphere: { radius: 0.7, colorscheme: 'Jmol' } }); } catch (e) { /* ions: optional */ }
          }
        }
        v.render();
      }
      paint(); v.zoomTo(); v.render();
      Array.prototype.forEach.call(document.querySelectorAll('input[name="vc-' + uid + '"],input[name="vs-' + uid + '"]'), function (i) { i.addEventListener('change', paint); });
      document.getElementById('vr-' + uid).addEventListener('click', function () { v.zoomTo(); v.render(); });

      // The panel can be laid out after the viewer was created (a notebook output frame that is sized late, a panel that was hidden).
      function refit() { try { if (v.resize) { v.resize(); } v.zoomTo(); v.render(); } catch (e) { /* cosmetic */ } }
      if (window.ResizeObserver) {
        var first = true;
        new ResizeObserver(function () { if (first) { first = false; return; } try { if (v.resize) { v.resize(); } v.render(); } catch (e) { /* cosmetic */ } }).observe(host);
      }
      if (window.requestAnimationFrame) { window.requestAnimationFrame(function () { setTimeout(refit, 60); }); }

      // pLDDT of whatever the pointer rests on
      try {
        v.setHoverable({}, true, function (a, vw) {
          if (a.label) { return; }
          a.label = vw.addLabel(a.resn + ' ' + a.resi + (a.chain ? ' (' + a.chain + ')' : '') + '  pLDDT ' + Number(a.b).toFixed(0),
            { position: a, backgroundColor: '#0B1220', backgroundOpacity: 0.88, fontColor: '#FFFFFF', fontSize: 12, borderThickness: 0 });
        }, function (a, vw) { if (a.label) { vw.removeLabel(a.label); delete a.label; } });
        v.render();
      } catch (e) { /* hover is a convenience */ }
    } catch (err) {
      say('The 3-D viewer could not draw this structure (' + String(err && err.message ? err.message : err).replace(/[<>&]/g, '').slice(0, 160) + '). The file is saved with the results.');
    }
  }

  // The library (about 1 MB) comes from the pinned <script> tag before this one. A second host is tried as soon as that tag fails, or
  // after 4 s without it; a slow connection gets a progress note and up to 45 s (BZ_3DMOL_WAIT_MS) before the viewer gives up.
  var started = Date.now(), waitMs = typeof window.BZ_3DMOL_WAIT_MS === 'number' ? window.BZ_3DMOL_WAIT_MS : 45000, noted = false, fallbackFailed = false;
  function inject() {
    injected = true;
    var sc = document.createElement('script'); sc.src = fallback; sc.async = true;
    sc.onerror = function () { fallbackFailed = true; };
    (document.head || document.body).appendChild(sc);
  }
  // 3Dmol sizes its canvas from the box when the viewer is created; a notebook output frame can be laid out later than the script runs.
  function whenSized(then) {
    var waited = 0;
    (function check() {
      if ((host.clientWidth > 0 && host.clientHeight > 0) || waited > 10000) { then(); return; }
      waited += 100; setTimeout(check, 100);
    })();
  }
  function start() {
    if (!window.$3Dmol) {
      tries += 1;
      var elapsed = Date.now() - started;
      if (!injected && fallback && (window.BZ_3DMOL_CDN_FAILED || elapsed > 4000)) { inject(); }
      if (elapsed > waitMs || (window.BZ_3DMOL_CDN_FAILED && (!fallback || fallbackFailed))) {   // both hosts failed: say so now
        say('The 3-D viewer needs an internet connection to load (the 3Dmol library could not be downloaded). The structure file is saved with the results.');
        return;
      }
      if (!noted && elapsed > 3000) { noted = true; say('Loading 3-D viewer... (downloading the 3Dmol library; this can take a few seconds on a slow connection)'); }
      setTimeout(start, 150); return;
    }
    whenSized(build);
  }
  start();
})();
