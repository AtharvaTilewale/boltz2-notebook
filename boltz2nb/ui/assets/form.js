/* Boltz2 Notebook - input builder. Vanilla ES2017, no dependencies. */
(function () {
'use strict';
var UID = '@@UID@@';
// Defaults, presets and ranges come from Python and are embedded here, in this one script element: notebook front-ends
// differ in how they re-insert <script> tags, and a second element looked up by id may not survive that.
var CFG = /*@@CONFIG@@*/ {};

// Shown in place of silence: if anything in the form fails, the message appears at the top of the form.
function showProblem(root, title, lines) {
  var box = root.querySelector('[data-f="ui-problem"]');
  if (!box) {
    box = document.createElement('div');
    box.setAttribute('data-f', 'ui-problem'); box.setAttribute('role', 'alert'); box.className = 'bz-alert bz-alert--err';
    box.style.cssText = 'margin:12px;white-space:pre-wrap;font:12.5px/1.5 ui-monospace,Menlo,Consolas,monospace';
    root.insertBefore(box, root.firstChild);
  }
  box.textContent = title + '\n' + lines.slice(0, 6).join('\n') + '\n\nCopy this message into a GitHub issue (the browser console has the full details).';
}

function start(root) {
var bootNote = root.querySelector('[data-f="boot-note"]');   // static fallback text for a script that never runs
if (bootNote) { bootNote.remove(); }
var ADV = CFG.mode === 'advanced';

// ------------------------------------------------------------------------------------ helpers
function $(sel, ctx) { return (ctx || root).querySelector(sel); }
function $$(sel, ctx) { return Array.prototype.slice.call((ctx || root).querySelectorAll(sel)); }
function F(name, ctx) { return (ctx || root).querySelector('[data-f="' + name + '"]'); }
function E(name, ctx) { return (ctx || root).querySelector('[data-e="' + name + '"]'); }
var _seq = 0;
function nextId() { _seq += 1; return UID + _seq; }
function ICON(n) { return '<svg class="i" aria-hidden="true"><use href="#bz-i-' + n + '"/></svg>'; }
function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
function debounce(fn, ms) { var t; return function () { var a = arguments, self = this; clearTimeout(t); t = setTimeout(function () { fn.apply(self, a); }, ms); }; }
function fmtNum(n) { return Number(n).toLocaleString('en-US'); }
function plural(n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); }

function cloneT(name) {
  var t = root.querySelector('template[data-t="' + name + '"]');
  var wrap = document.createElement('div');
  wrap.innerHTML = t.innerHTML.replace(/__ID__/g, nextId());
  return wrap.firstElementChild;
}

// ------------------------------------------------------------------------------------ kernel RPC
function unwrap(r) {
  // Colab answers an invokeFunction call with the notebook's display of the value the Python callback returned:
  // {status: 'ok', data: {<mime type>: ...}}. Parsed JSON is only there when the callback returned IPython.display.JSON
  // (boltz2nb.ui.callbacks.as_json_reply); a plain dict would arrive as its Python repr under 'text/plain'. The reply's own
  // top-level `status` describes the execution, not our result, so it must never be mistaken for it.
  if (r && typeof r === 'object' && r.data && typeof r.data === 'object') {
    var j = r.data['application/json'];
    if (j !== undefined && j !== null && typeof j === 'object') { return j; }
    throw new Error('The notebook kernel replied in an unexpected format (' + Object.keys(r.data).join(', ') +
      '). Restart the session (Runtime > Restart session), then run the cells again.');
  }
  return r;      // a bare object: the test harness and front-ends that return the value itself
}
function describeError(err) {
  // A Python exception in a callback arrives as {ename, evalue, traceback}, not as an Error.
  if (err && err.message) { return String(err.message); }
  if (err && (err.evalue || err.ename)) { return (err.ename ? err.ename + ': ' : '') + (err.evalue || ''); }
  if (typeof err === 'string' && err) { return err; }
  return 'The notebook kernel did not answer.';
}
function rpc(name, args) {
  var k = window.google && window.google.colab && window.google.colab.kernel;
  if (!k) { return Promise.reject(new Error('Not connected to a Colab runtime. Run this cell inside Colab.')); }
  return Promise.resolve().then(function () { return k.invokeFunction(name, args, {}); })
    .then(unwrap, function (err) { throw new Error(describeError(err)); });
}

// ------------------------------------------------------------------------------------ constants
var ALPHA = { protein: 'ACDEFGHIKLMNPQRSTVWYX', dna: 'ACGTN', rna: 'ACGUN' };
var TYPE = {
  protein: { title: 'Protein', letter: 'P', unit: 'residue', label: 'Amino-acid sequence', ph: 'Paste a sequence or a FASTA record' },
  dna: { title: 'DNA', letter: 'D', unit: 'nucleotide', label: 'DNA sequence (A C G T)', ph: 'Paste a DNA sequence, for example ACGTACGT' },
  rna: { title: 'RNA', letter: 'R', unit: 'nucleotide', label: 'RNA sequence (A C G U)', ph: 'Paste an RNA sequence, for example ACGUACGU' },
  ligand: { title: 'Ligand', letter: 'L' }
};
var ID_RE = /^[A-Za-z0-9]{1,4}$/;
var CCD_RE = /^[A-Za-z0-9]{1,5}$/;
var JOB_RE = /^[A-Za-z0-9_.-]{1,60}$/;
var CONTACT_RE = /^[A-Za-z0-9]{1,4}:[A-Za-z0-9_'*]{1,8}$/;
var state = { step: 1, strict: false, saved: false, visited: { 1: true }, previewReq: 0, lastPreview: null };

// ------------------------------------------------------------------------------------ chips input
function initChips(box, opts) {
  opts = opts || {};
  var input = document.createElement('input');
  input.type = 'text'; input.autocomplete = 'off'; input.spellcheck = false;
  input.setAttribute('aria-label', opts.label || 'Add value');
  box.appendChild(input);
  box._tokens = [];
  function render() {
    $$('.bz-token', box).forEach(function (n) { n.remove(); });
    box._tokens.forEach(function (t, i) {
      var chip = document.createElement('span');
      chip.className = 'bz-token';
      chip.innerHTML = esc(t) + '<button type="button" aria-label="Remove ' + esc(t) + '">' + ICON('x') + '</button>';
      chip.querySelector('button').addEventListener('click', function (ev) {
        ev.stopPropagation(); box._tokens.splice(i, 1); render(); changed(); input.focus();
      });
      box.insertBefore(chip, input);
    });
    input.placeholder = box._tokens.length ? '' : (opts.placeholder || '');
  }
  function changed() { box.dispatchEvent(new CustomEvent('chipschange', { bubbles: true })); }
  function commit(raw) {
    var parts = String(raw).split(/[\s,;]+/).filter(Boolean), bad = [], added = false;
    parts.forEach(function (p0) {
      var p = opts.normalize ? opts.normalize(p0) : p0;
      if (opts.pattern && !opts.pattern.test(p)) { bad.push(p0); return; }
      if (box._tokens.indexOf(p) < 0) { box._tokens.push(p); added = true; }
    });
    render();
    if (added) { changed(); }
    return bad;
  }
  input.addEventListener('keydown', function (ev) {
    if ((ev.key === 'Enter' || ev.key === ',' || ev.key === ' ' || ev.key === ';') && input.value.trim()) {
      ev.preventDefault(); input.value = commit(input.value).join(' ');
    } else if (ev.key === 'Backspace' && !input.value && box._tokens.length) {
      box._tokens.pop(); render(); changed();
    }
  });
  input.addEventListener('input', function () { box.removeAttribute('data-pending-bad'); });
  input.addEventListener('blur', function () { if (input.value.trim()) { input.value = commit(input.value).join(' '); } });
  input.addEventListener('paste', function (ev) {
    var text = (ev.clipboardData || window.clipboardData).getData('text');
    ev.preventDefault(); input.value = commit(text).join(' ');
  });
  box.addEventListener('click', function () { input.focus(); });
  box.setTokens = function (arr) { box._tokens = []; commit((arr || []).join(' ')); };
  box.getTokens = function () { return box._tokens.slice(); };
  box.flush = function () { if (input.value.trim()) { input.value = commit(input.value).join(' '); } return input.value.trim(); };
  box.pendingText = function () { return input.value.trim(); };
  render();
}

// ------------------------------------------------------------------------------------ files
function bindDrop(label, onFile) {
  var input = label.querySelector('input[type=file]');
  label.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); input.click(); } });
  ['dragenter', 'dragover'].forEach(function (n) { label.addEventListener(n, function (ev) { ev.preventDefault(); label.setAttribute('data-over', '1'); }); });
  ['dragleave', 'drop'].forEach(function (n) { label.addEventListener(n, function (ev) { ev.preventDefault(); label.removeAttribute('data-over'); }); });
  label.addEventListener('drop', function (ev) { var f = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0]; if (f) { onFile(f); } });
  input.addEventListener('change', function () { if (input.files && input.files[0]) { onFile(input.files[0]); } input.value = ''; });
}
function readB64(file) {
  return new Promise(function (resolve, reject) {
    var r = new FileReader();
    r.onload = function (e) { resolve(String(e.target.result).split(',')[1] || ''); };
    r.onerror = function () { reject(new Error('Could not read the file.')); };
    r.readAsDataURL(file);
  });
}
function readText(file) {
  return new Promise(function (resolve, reject) {
    var r = new FileReader();
    r.onload = function (e) { resolve(String(e.target.result)); };
    r.onerror = function () { reject(new Error('Could not read the file.')); };
    r.readAsText(file);
  });
}
function fileChip(name, size, onRemove) {
  var kb = size ? (size > 1048576 ? (size / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(size / 1024)) + ' KB') : '';
  var el = document.createElement('div');
  el.className = 'bz-file';
  el.innerHTML = ICON('check-circle') + '<span>' + esc(name) + (kb ? ' (' + kb + ')' : '') + '</span>' +
    '<button type="button" class="bz-btn bz-btn--icon bz-btn--sm" aria-label="Remove file" style="width:22px;height:22px;color:inherit">' + ICON('x') + '</button>';
  el.querySelector('button').addEventListener('click', onRemove);
  return el;
}
function uploadInto(file, kind, statusEl, onDone) {
  statusEl.innerHTML = '<div class="bz-file" style="background:var(--bz-surface-3);color:var(--bz-text-2)"><span class="bz-spin"></span><span>Uploading ' + esc(file.name) + '...</span></div>';
  return readB64(file).then(function (b64) { return rpc('save_uploaded_file', [kind, file.name, b64]); }).then(function (res) {
    if (res && res.status === 'ok') {
      statusEl.innerHTML = '';
      statusEl.appendChild(fileChip(res.name || file.name, res.size, function () { statusEl.innerHTML = ''; onDone(null); }));
      onDone(res.path);
    } else {
      statusEl.innerHTML = '<div class="bz-error">' + ICON('x-circle') + '<span>' + esc((res && res.message) || 'Upload failed.') + '</span></div>';
      onDone(null);
    }
  }).catch(function (err) {
    statusEl.innerHTML = '<div class="bz-error">' + ICON('x-circle') + '<span>' + esc(err.message) + '</span></div>';
    onDone(null);
  });
}

// ------------------------------------------------------------------------------------ entities
var entitiesEl = F('entities');
function cards() { return $$('.bz-entity', entitiesEl); }
function cardIds(card) { var b = F('ids', card); return b && b.getTokens ? b.getTokens() : []; }
function usedIds(except) {
  var s = {};
  cards().forEach(function (c) { if (c !== except) { cardIds(c).forEach(function (i) { s[i] = true; }); } });
  return s;
}
function nextFreeId() {
  var used = usedIds(null), L = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', i, j;
  for (i = 0; i < L.length; i++) { if (!used[L[i]]) { return L[i]; } }
  for (j = 1; j < 10; j++) { for (i = 0; i < L.length; i++) { if (!used[L[i] + j]) { return L[i] + j; } } }
  return 'Z9';
}
function isPristine(card) {
  if (card.dataset.type === 'ligand') { return !F('value', card).value.trim(); }
  return !F('seq', card).value.trim();
}
function setTouched(card, key) { card._touched = card._touched || {}; card._touched[key] = true; }

function cleanSeq(s) { return String(s).replace(/[\s\d]+/g, '').replace(/\*+$/, '').toUpperCase(); }
function parseFasta(text) {
  var recs = [], cur = null;
  String(text).split(/\r?\n/).forEach(function (line) {
    if (line.charAt(0) === '>') { cur = { header: line.slice(1).trim(), seq: '' }; recs.push(cur); }
    else { if (!cur) { cur = { header: '', seq: '' }; recs.push(cur); } cur.seq += line; }
  });
  return recs.filter(function (r) { return cleanSeq(r.seq).length; }).map(function (r) { return { header: r.header, seq: cleanSeq(r.seq) }; });
}

function addEntity(type, opts) {
  opts = opts || {};
  var card = cloneT(type === 'ligand' ? 'ligand' : 'polymer');
  if (opts.after && opts.after.parentNode === entitiesEl) { entitiesEl.insertBefore(card, opts.after.nextSibling); }
  else { entitiesEl.appendChild(card); }
  card._touched = {}; card._err = {};
  initChips(F('ids', card), { pattern: ID_RE, normalize: function (s) { return s.toUpperCase(); }, placeholder: nextFreeId(), label: 'Chain ID' });
  F('ids', card).setTokens(opts.ids && opts.ids.length ? opts.ids : [nextFreeId()]);
  if (type === 'ligand') { setupLigand(card, opts); } else { setupPolymer(card, type, opts); }
  refreshAll();
  return card;
}

// ---- polymers
function setupPolymer(card, type, opts) {
  var ta = F('seq', card);
  $$('input[name^="ty-"]', card).forEach(function (r) { r.addEventListener('change', function () { if (r.checked) { applyType(card, r.value); refreshAll(); } }); });
  $$('input[name^="msa-"]', card).forEach(function (r) { r.addEventListener('change', function () { applyMsa(card); refreshAll(); }); });
  // What is typed is filtered as it arrives: capitals only, no spaces or line breaks, and only the letters that are valid for this
  // chain type. The `input` listener below catches every other way text can get in (drag, autofill, composition, old browsers).
  ta.addEventListener('beforeinput', function (ev) {
    if (ev.isComposing || card._inserting) { return; }
    var kind = ev.inputType || '';
    if (kind === 'insertLineBreak' || kind === 'insertParagraph') { ev.preventDefault(); return; }
    if (kind !== 'insertText' || typeof ev.data !== 'string') { return; }
    var r = sanitizeSeq(ev.data, card.dataset.type);
    if (r.seq === ev.data) { return; }
    ev.preventDefault();
    if (r.count) { noteRejected(card, r.dropped, true); }
    if (r.seq) { insertAtCaret(ta, r.seq, card); }
    validateSeq(card); refreshAll();
  });
  ta.addEventListener('input', function () { cleanField(card); validateSeq(card); });
  ta.addEventListener('blur', function () { setTouched(card, 'seq'); normalizeSeq(card); refreshAll(); });
  ta.addEventListener('paste', function (ev) {
    var text = (ev.clipboardData || window.clipboardData).getData('text');
    if (!text) { return; }
    ev.preventDefault();
    takeText(card, text);
  });
  ta.addEventListener('drop', function (ev) {
    var text = ev.dataTransfer && ev.dataTransfer.getData('text');
    if (!text) { return; }
    ev.preventDefault();
    takeText(card, text);
  });
  F('msa-file', card) && bindDrop(F('msa-upload', card).querySelector('.bz-drop'), function (file) {
    uploadInto(file, 'msa', F('msa-file-status', card), function (path) { card._msaPath = path; setTouched(card, 'msa'); refreshAll(); });
  });
  var addMod = $('[data-act="add-mod"]', card);
  if (addMod) { addMod.addEventListener('click', function () { addModRow(card); }); }
  $('input[name^="ty-"][value="' + type + '"]', card).checked = true;
  applyType(card, type);
  applyMsa(card);
  if (opts.sequence) { F('seq', card).value = opts.sequence; }
  if (opts.label) { card._label = opts.label; }
  if (opts.msa) { var r = $('input[name^="msa-"][value="' + opts.msa + '"]', card); if (r) { r.checked = true; applyMsa(card); } }
  validateSeq(card);
}
function applyType(card, type) {
  card.dataset.type = type;
  var T = TYPE[type];
  var tile = F('tile', card);
  tile.textContent = T.letter; tile.className = 'bz-tile bz-tile--' + type;
  F('title', card).textContent = T.title;
  F('seq-label', card).textContent = T.label;
  F('seq', card).placeholder = T.ph;
  var ch = F('cyclic-hint', card);
  if (ch) { ch.textContent = type === 'protein' ? 'Head-to-tail cyclic chain, for example a macrocyclic peptide.' : 'Circular molecule: the 3\u2032 end is joined to the 5\u2032 end.'; }
  $$('[data-only="protein"]', card).forEach(function (el) { el.hidden = type !== 'protein'; });
  if (type === 'protein') { applyMsa(card); }
  validateSeq(card);
}
function applyMsa(card) {
  var mode = ($('input[name^="msa-"]:checked', card) || {}).value || 'server';
  var isProt = card.dataset.type === 'protein';
  F('msa-upload', card).hidden = !(isProt && mode === 'custom');
  F('msa-warn', card).hidden = !(isProt && mode === 'empty');
  F('msa-hint', card).textContent = { server: 'Generated for you with the ColabFold MSA server.', custom: 'Use your own alignment instead of the server.', empty: 'No alignment: single-sequence prediction.' }[mode];
  card._msaMode = mode;
}
function setExtra(card, recs) {
  card._extra = recs || [];
  var box = F('split', card);
  if (card._extra.length) {
    F('split-msg', card).textContent = (card._extra.length + 1) + ' FASTA records were pasted. The first is loaded here.';
    box.hidden = false;
  } else { box.hidden = true; }
}
// ---- sequence filtering
// Returns the sequence that may be kept from `text` (upper case, only letters of this chain type) and the characters that were refused.
// Spaces and line breaks are dropped without comment; digits are only reported when the text was typed (a pasted record is cleaned first).
function sanitizeSeq(text, type) {
  var ok = ALPHA[type] || '', up = String(text).toUpperCase(), out = '', dropped = {}, count = 0, i, ch;
  for (i = 0; i < up.length; i++) {
    ch = up.charAt(i);
    if (/\s/.test(ch)) { continue; }
    if (ok.indexOf(ch) < 0) { dropped[ch] = (dropped[ch] || 0) + 1; count += 1; continue; }
    out += ch;
  }
  return { seq: out, dropped: dropped, count: count };
}
// `merge`: typing refuses one character at a time, so those are added up; a paste or a drop replaces the note.
function noteRejected(card, dropped, merge) {
  var el = F('seq-meta', card), all = merge ? (card._rej || {}) : {};
  Object.keys(dropped || {}).forEach(function (k) { all[k] = (all[k] || 0) + dropped[k]; });
  card._rej = all;
  var keys = Object.keys(all).sort();
  clearTimeout(card._noteT);
  if (!keys.length) { el.textContent = ''; el.classList.remove('bz-meta-warn'); return; }
  dropped = all;
  var n = keys.reduce(function (a, k) { return a + dropped[k]; }, 0), T = TYPE[card.dataset.type];
  el.textContent = 'Ignored ' + plural(n, 'character') + ' that cannot be in a ' + T.title + ' sequence: ' + keys.slice(0, 8).join(' ') + (keys.length > 8 ? ' ...' : '') + '.';
  el.classList.add('bz-meta-warn');
  card._noteT = setTimeout(function () { card._rej = {}; noteRejected(card, {}); }, 9000);
}
function insertAtCaret(ta, text, card) {
  var done = false;
  card._inserting = true;
  try { done = document.execCommand('insertText', false, text); } catch (err) { done = false; }   // keeps the browser's undo history
  card._inserting = false;
  if (!done) { ta.setRangeText(text, ta.selectionStart, ta.selectionEnd, 'end'); }
}
// Safety net for text that arrived without a keystroke: clean it and keep the caret next to the same letter.
function cleanField(card) {
  var ta = F('seq', card), v = ta.value, type = card.dataset.type;
  if (/^[ \t]*>/m.test(v)) { takeText(card, v, true); return; }            // a FASTA record (header line) arrived: split it properly
  var r = sanitizeSeq(v, type);
  if (r.seq === v) { return; }
  var pos = ta.selectionStart, keep = sanitizeSeq(v.slice(0, pos), type).seq.length;
  ta.value = r.seq;
  try { ta.setSelectionRange(keep, keep); } catch (err) { /* not focusable */ }
  if (r.count) { noteRejected(card, r.dropped, true); }
}
// Pasted or dropped text, possibly one or several FASTA records: keep the valid letters of the first, offer the rest as extra molecules.
function takeText(card, text, replaceAll) {
  var ta = F('seq', card), type = card.dataset.type, recs = parseFasta(text), dropped = {}, any = false;
  recs = recs.map(function (r) {
    var s = sanitizeSeq(r.seq, type);
    Object.keys(s.dropped).forEach(function (k) { dropped[k] = (dropped[k] || 0) + s.dropped[k]; any = true; });
    return { header: r.header, seq: s.seq };
  }).filter(function (r) { return r.seq.length; });
  if (any) { noteRejected(card, dropped); } else { noteRejected(card, {}); }
  if (!recs.length) { if (replaceAll) { ta.value = ''; } validateSeq(card); refreshAll(); return; }
  var whole = replaceAll || (ta.selectionStart === 0 && ta.selectionEnd === ta.value.length) || !ta.value.trim();
  if (whole) { ta.value = ''; }
  ta.setRangeText(recs[0].seq, ta.selectionStart, ta.selectionEnd, 'end');
  card._label = recs[0].header || card._label || '';
  setExtra(card, recs.slice(1));
  validateSeq(card); refreshAll();
}
function normalizeSeq(card) {
  var ta = F('seq', card), recs = parseFasta(ta.value);
  if (!recs.length) { ta.value = ''; return; }
  if (/^\s*>/m.test(ta.value) || recs.length > 1) { card._label = recs[0].header || card._label; if (recs.length > 1) { setExtra(card, recs.slice(1)); } }
  ta.value = recs[0].seq;
}
function seqOf(card) {
  var recs = parseFasta(F('seq', card).value);
  return recs.length ? recs[0].seq : '';
}
function validateSeq(card) {
  var type = card.dataset.type, seq = seqOf(card), ok = ALPHA[type] || '';
  var bad = {}, nbad = 0, i;
  for (i = 0; i < seq.length; i++) { if (ok.indexOf(seq[i]) < 0) { bad[seq[i]] = (bad[seq[i]] || 0) + 1; nbad += 1; } }
  var T = TYPE[type];
  F('seq-count', card).textContent = seq ? plural(seq.length, T.unit) : '';
  var sub = card._label ? card._label : (seq ? plural(seq.length, T.unit) : 'Add a sequence');
  F('sub', card).textContent = sub.length > 70 ? sub.slice(0, 67) + '...' : sub;
  card._err = card._err || {};
  card._err.seq = !seq ? 'Enter a sequence.' : (nbad ? 'Not valid in ' + T.title + ' sequences: ' + Object.keys(bad).sort().join(', ') + ' (' + plural(nbad, 'character') + '). Allowed: ' + ok.split('').join(' ') + '.' : '');
  card._stepOf = 1;
  paintCard(card);
}

// ---- ligands
// A ligand is described by a SMILES or a CCD code. Both are checked as soon as they are typed: SMILES by the notebook (RDKit), CCD codes
// against the PDB's chemical component dictionary. The answer is shown as a status line (valid / not valid / could not be checked)
// and, when there is one, as a 2-D drawing. Only "not valid" blocks saving; "could not be checked" never does.
function setupLigand(card, opts) {
  var val = F('value', card);
  $$('input[name^="lk-"]', card).forEach(function (r) { r.addEventListener('change', function () { applyLigandKind(card); describeLigand(card); refreshAll(); }); });
  val.addEventListener('input', function () {
    card._ligDirty = true;
    if (kindOf(card) === 'ccd') { var up = val.value.toUpperCase().replace(/\s+/g, ''); if (up !== val.value) { val.value = up; } }
    scheduleDescribe(card);
  });
  val.addEventListener('blur', function () {
    var t = val.value.trim(); if (t !== val.value) { val.value = t; describeLigand(card); }
    setTouched(card, 'value'); refreshAll();
  });
  if (opts.kind === 'ccd') { $('input[name^="lk-"][value="ccd"]', card).checked = true; }
  applyLigandKind(card);
  if (opts.value) { val.value = opts.value; describeLigand(card); }
  scheduleDescribe(card);
}
function kindOf(card) { return ($('input[name^="lk-"]:checked', card) || {}).value || 'smiles'; }
function applyLigandKind(card) {
  var k = kindOf(card), val = F('value', card);
  F('val-label', card).textContent = k === 'smiles' ? 'SMILES string' : 'CCD code';
  val.placeholder = k === 'smiles' ? 'CC(=O)Oc1ccccc1C(=O)O' : 'SAH';
  val.style.textTransform = k === 'ccd' ? 'uppercase' : 'none';
  F('val-hint', card).textContent = k === 'smiles' ? 'Paste a SMILES from PubChem, ChEMBL or your drawing tool.' : 'The 1-5 character PDB component code, for example SAH, ATP or HEM. It is looked up in the PDB chemical component dictionary.';
  F('preview-col', card).hidden = false;
  if (k === 'ccd') { val.value = val.value.toUpperCase().replace(/\s+/g, ''); }
}
var scheduleDescribe = function (card) {
  clearTimeout(card._dt);
  card._dt = setTimeout(function () { describeLigand(card); }, 380);
};
// One status line under the field. state: '' (hidden) | busy | ok | bad | warn
function setLigStatus(card, state, text) {
  var el = F('val-status', card), val = F('value', card);
  card._vstat = state;
  if (!state) { el.hidden = true; el.innerHTML = ''; el.removeAttribute('data-state'); el.className = 'bz-vstat'; val.removeAttribute('data-valid'); return; }
  el.hidden = false; el.setAttribute('data-state', state); el.className = 'bz-vstat bz-vstat--' + state;
  el.innerHTML = (state === 'busy' ? '<span class="bz-spin"></span>' : ICON(state === 'ok' ? 'check-circle' : (state === 'bad' ? 'x-circle' : 'alert'))) + '<span>' + esc(text) + '</span>';
  if (state === 'ok') { val.setAttribute('data-valid', 'true'); } else if (state === 'bad') { val.setAttribute('data-valid', 'false'); } else { val.removeAttribute('data-valid'); }
}
function ligProps(card, chips, message) {
  F('props', card).innerHTML = chips.filter(function (c) { return c[1] !== undefined && c[1] !== null && c[1] !== ''; }).map(function (c) {
    return '<span class="bz-prop">' + esc(c[0]) + ' ' + esc(c[1]) + '</span>'; }).join('') + (message ? '<span class="bz-chip bz-chip--warn">' + esc(message) + '</span>' : '');
}
function describeLigand(card) {
  var kind = kindOf(card), value = F('value', card).value.trim(), pv = F('preview', card), what = kind === 'smiles' ? 'SMILES string' : 'CCD code';
  card._ligReq = (card._ligReq || 0) + 1;
  var req = card._ligReq;
  card._err = card._err || {}; card._lig = null;
  ligProps(card, []);
  if (!value) {
    setLigStatus(card, '');
    pv.innerHTML = '<span class="bz-muted">2-D preview</span>'; card._err.value = 'Enter a ' + what + '.';
    F('sub', card).textContent = 'Small molecule'; paintCard(card); refreshRail(); return;
  }
  if (kind === 'ccd' && !CCD_RE.test(value)) {                       // no round trip needed to see this is not a code
    setLigStatus(card, 'bad', "'" + (value.length > 12 ? value.slice(0, 12) + '...' : value) + "' is not a CCD code: codes are 1 to 5 letters or digits (for example SAH, ATP, HEM).");
    pv.innerHTML = '<span class="bz-muted">No preview</span>'; card._err.value = 'CCD codes are 1-5 letters or digits.';
    F('sub', card).textContent = 'Not a valid CCD code'; paintCard(card); refreshRail(); return;
  }
  card._err.value = ''; paintCard(card);
  setLigStatus(card, 'busy', kind === 'smiles' ? 'Checking the SMILES...' : 'Looking ' + value.toUpperCase() + ' up in the PDB component dictionary...');
  pv.innerHTML = '<span class="bz-spin" style="color:var(--bz-text-3)"></span>';
  rpc('describe_ligand', [{ kind: kind, value: value }]).then(function (r) {
    if (req !== card._ligReq) { return; }
    r = r || {};
    if (r.status === 'error') { throw new Error(r.message || 'The check failed.'); }
    if (r.valid === true) {
      var drawn = !!r.svg;
      pv.innerHTML = r.svg || '<span class="bz-muted" style="text-align:center;padding:8px">No drawing available<br>for this component</span>';
      if (kind === 'smiles') {
        setLigStatus(card, 'ok', 'Valid SMILES: ' + r.formula + ', ' + plural(r.heavy_atoms, 'heavy atom') + '.');
        ligProps(card, [['formula', r.formula], ['MW', r.mol_weight], ['heavy atoms', r.heavy_atoms], ['cLogP', r.clogp]], r.message);
        F('sub', card).textContent = r.formula + ' - ' + r.mol_weight + ' Da';
      } else {
        setLigStatus(card, 'ok', 'Valid CCD code: ' + r.code + (r.name ? ' - ' + r.name : '') + (r.formula ? ' (' + r.formula + ')' : '') + '.');
        ligProps(card, [['formula', r.formula], ['MW', r.mol_weight]]);
        F('sub', card).textContent = r.code + (r.name ? ' - ' + (r.name.length > 34 ? r.name.slice(0, 33) + '...' : r.name) : '');
      }
      card._err.value = ''; card._lig = r;
    } else if (r.valid === false) {
      setLigStatus(card, 'bad', r.message || (kind === 'smiles' ? 'This SMILES is not valid.' : 'This CCD code is not valid.'));
      pv.innerHTML = '<span class="bz-muted">No preview</span>';
      card._err.value = r.message || ('This ' + what + ' is not valid.'); card._lig = null;
      F('sub', card).textContent = kind === 'smiles' ? 'Not a valid SMILES' : 'Not a valid CCD code';
    } else {
      setLigStatus(card, 'warn', r.message || 'This could not be checked.');
      pv.innerHTML = '<span class="bz-muted">Preview unavailable</span>';
      F('sub', card).textContent = kind === 'ccd' ? 'CCD component ' + value : 'Small molecule';
    }
    paintCard(card); refreshAll();
  }).catch(function (err) {
    if (req !== card._ligReq) { return; }
    setLigStatus(card, 'warn', 'The notebook runtime did not answer, so this ' + what + ' could not be checked' + (err && err.message ? ' (' + String(err.message).split('\n')[0].slice(0, 140) + ')' : '') + '.');
    pv.innerHTML = '<span class="bz-muted" style="text-align:center;padding:8px">Preview needs a<br>connected runtime</span>';
  });
}

// ---- error painting (inline errors only after the user has touched a field, or on save)
function paintCard(card) {
  var map = { ids: F('ids', card), seq: F('seq', card), value: F('value', card), msa: null };
  Object.keys(map).forEach(function (k) {
    var errEl = E(k, card); if (!errEl) { return; }
    var msg = card._err && card._err[k];
    var show = !!msg && (state.strict || (card._touched && card._touched[k]));
    if (k === 'value' && card._vstat === 'bad') { show = false; }       // the live status line above already says why
    errEl.hidden = !show;
    errEl.innerHTML = show ? ICON('x-circle') + '<span>' + esc(msg) + '</span>' : '';
    if (map[k]) { if (show) { map[k].setAttribute('aria-invalid', 'true'); } else { map[k].removeAttribute('aria-invalid'); } }
  });
}

// ---- constraint rows
var ROW = { template: 'templates', bond: 'bonds', pocket: 'pockets', contact: 'contacts' };
function rowsOf(kind) { return $$('[data-row="' + kind + '"]', F(ROW[kind])); }
function addRow(kind) {
  var row = cloneT(kind);
  F(ROW[kind]).appendChild(row);
  $$('input[type=range]', row).forEach(function (r) {
    var out = r.parentNode.querySelector('output');
    r.addEventListener('input', function () { out.textContent = r.value; });
  });
  $$('[data-act="remove-row"]', row).forEach(function (b) { b.addEventListener('click', function () { row.remove(); refreshAll(); }); });
  var force = F('tpl-force', row);
  if (force) { force.addEventListener('change', function () { F('tpl-threshold', row).disabled = !force.checked; }); }
  if (kind === 'template') {
    initChips(F('tpl-chains', row), { pattern: ID_RE, normalize: function (s) { return s.toUpperCase(); }, placeholder: 'A, B', label: 'Your chain' });
    initChips(F('tpl-ids', row), { pattern: /^[A-Za-z0-9]{1,6}$/, placeholder: 'A, B', label: 'Template chain' });
    bindDrop($('.bz-drop', row), function (file) {
      uploadInto(file, 'template', F('tpl-status', row), function (path) { row._path = path; refreshAll(); });
    });
  }
  if (kind === 'pocket') {
    initChips(F('pocket-residues', row), { pattern: CONTACT_RE, normalize: function (s) { var p = s.split(':'); return p[0].toUpperCase() + ':' + p.slice(1).join(':'); }, placeholder: 'A:145', label: 'Pocket residue' });
  }
  refreshChainSelects();
  var det = row.closest('details'); if (det) { det.open = true; }
  refreshAll();
  return row;
}
function addModRow(card) {
  var row = cloneT('mod');
  F('mods', card).appendChild(row);
  $$('[data-act="remove-row"]', row).forEach(function (b) { b.addEventListener('click', function () { row.remove(); refreshAll(); }); });
  F('mods-acc', card).open = true;
  refreshAll();
}
function chainList() {
  var out = [];
  cards().forEach(function (c) { cardIds(c).forEach(function (id) { out.push({ id: id, type: c.dataset.type }); }); });
  return out;
}
function refreshChainSelects() {
  var chains = chainList();
  $$('select[data-chain-select]').forEach(function (sel) {
    var cur = sel.value;
    sel.innerHTML = '<option value="">Chain...</option>' + chains.map(function (c) {
      return '<option value="' + esc(c.id) + '">' + esc(c.id) + ' - ' + TYPE[c.type].title + '</option>';
    }).join('');
    if (chains.some(function (c) { return c.id === cur; })) { sel.value = cur; }
  });
}

// ---- affinity
function refreshAffinity() {
  var ligands = [];
  cards().forEach(function (c) { if (c.dataset.type === 'ligand') { cardIds(c).forEach(function (i) { ligands.push(i); }); } });
  var card = F('affinity-card'), sel = F('affinity-chain'), on = F('affinity-on');
  card.hidden = ligands.length === 0;
  if (!ligands.length) { on.checked = false; }
  var cur = sel.value;
  sel.innerHTML = ligands.map(function (i) { return '<option>' + esc(i) + '</option>'; }).join('');
  if (ligands.indexOf(cur) >= 0) { sel.value = cur; }
  F('affinity-pick').hidden = !on.checked;
  F('affinity-hint').textContent = ligands.length > 1 ? 'Boltz-2 affinity was trained on single-ligand complexes; results with several ligands are less reliable.' : '';
}

// ------------------------------------------------------------------------------------ collect
function collect() {
  var issues = [], sequences = [], seen = {};
  function issue(step, msg, el) { issues.push({ step: step, msg: msg, el: el || null }); }
  cards().forEach(function (card, idx) {
    var type = card.dataset.type, box = F('ids', card), n = idx + 1, label = TYPE[type].title + ' ' + n;
    var pending = box.flush();
    card._err = card._err || {};
    var ids = box.getTokens(), idErr = '';
    if (pending) { idErr = '"' + pending + '" is not a valid chain ID (1-4 letters or digits).'; }
    else if (!ids.length) { idErr = 'Add at least one chain ID.'; }
    else {
      var dup = ids.filter(function (i) { return seen[i] && seen[i] !== card; });
      if (dup.length) { idErr = 'Chain ID ' + dup.join(', ') + ' is already used by another molecule.'; }
    }
    ids.forEach(function (i) { if (!seen[i]) { seen[i] = card; } });
    card._err.ids = idErr;
    if (idErr) { issue(1, label + ': ' + idErr, box); }
    if (type === 'ligand') {
      var kind = kindOf(card), val = F('value', card).value.trim();
      if (!val) { card._err.value = 'Enter a ' + (kind === 'smiles' ? 'SMILES string' : 'CCD code') + '.'; }
      else if (kind === 'ccd' && !CCD_RE.test(val)) { card._err.value = 'CCD codes are 1-5 letters or digits.'; }
      if (card._err.value) { issue(1, label + ': ' + card._err.value, F('value', card)); }
      var lig = { id: ids };
      if (kind === 'ccd') { lig.ccd = val.toUpperCase(); } else { lig.smiles = val; }
      sequences.push({ type: 'ligand', data: lig });
    } else {
      var sq = seqOf(card);
      validateSeq(card);
      if (card._err.seq) { issue(1, label + ': ' + card._err.seq, F('seq', card)); }
      var ent = { id: ids, sequence: sq };
      if (ADV && F('cyclic', card).checked) { ent.cyclic = true; }
      if (type === 'protein') {
        var mode = card._msaMode || 'server';
        if (mode === 'custom') {
          if (!card._msaPath) { card._err.msa = 'Upload an alignment or choose another MSA option.'; issue(1, label + ': ' + card._err.msa, F('msa-file', card)); }
          else { card._err.msa = ''; ent.msa = card._msaPath; }
        } else { card._err.msa = ''; if (mode === 'empty') { ent.msa = 'empty'; } }
      }
      var mods = [];
      $$('[data-row="mod"]', card).forEach(function (r, j) {
        var pos = F('pos', r).value, ccd = F('ccd', r).value.trim().toUpperCase();
        if (!pos && !ccd) { issue(1, label + ': modification ' + (j + 1) + ' is empty; fill it in or remove it.', F('pos', r)); return; }
        if (!pos || !ccd || !CCD_RE.test(ccd)) { issue(1, label + ': modification ' + (j + 1) + ' needs a position and a CCD code.', F('pos', r)); return; }
        if (sq && Number(pos) > sq.length) { issue(1, label + ': modification position ' + pos + ' is beyond the ' + sq.length + ' residues.', F('pos', r)); return; }
        mods.push({ position: Number(pos), ccd: ccd });
      });
      if (mods.length) { ent.modifications = mods; }
      sequences.push({ type: type, data: ent });
    }
    paintCard(card);
  });
  if (!sequences.length) { issue(1, 'Add at least one molecule.', null); }

  var known = {}; chainList().forEach(function (c) { known[c.id] = true; });
  var templates = [], bonds = [], pockets = [], contacts = [];
  rowsOf('template').forEach(function (row, j) {
    if (!row._path) { issue(2, 'Template ' + (j + 1) + ': upload a file or remove the row.', $('.bz-drop', row)); return; }
    var tc = F('tpl-chains', row), ti = F('tpl-ids', row); tc.flush(); ti.flush();
    var chains = tc.getTokens(), tids = ti.getTokens(), force = F('tpl-force', row).checked;
    var unknown = chains.filter(function (c) { return !known[c]; });
    if (unknown.length) { issue(2, 'Template ' + (j + 1) + ': chain ' + unknown.join(', ') + ' is not in your molecules.', tc); return; }
    templates.push({ path: row._path, chain_id: chains, template_id: tids, force: force, threshold: force ? F('tpl-threshold', row).value : '' });
  });
  rowsOf('bond').forEach(function (row, j) {
    var v = { chain1: F('chain1', row).value, res1: F('res1', row).value, atom1: F('atom1', row).value.trim(),
      chain2: F('chain2', row).value, res2: F('res2', row).value, atom2: F('atom2', row).value.trim() };
    if (!v.chain1 || !v.chain2 || !v.atom1 || !v.atom2 || !v.res1 || !v.res2) { issue(2, 'Bond ' + (j + 1) + ': choose both chains and give residue numbers and atom names.', F('chain1', row)); return; }
    bonds.push(v);
  });
  rowsOf('pocket').forEach(function (row, j) {
    var cb = F('pocket-residues', row); cb.flush();
    var binder = F('binder', row).value, toks = cb.getTokens(), err = '';
    if (!binder) { err = 'choose the binder chain'; } else if (!toks.length) { err = 'add at least one pocket residue such as A:145'; }
    else { var bad = toks.filter(function (t) { return !known[t.split(':')[0]]; }); if (bad.length) { err = bad.join(', ') + ' refers to a chain that does not exist'; } }
    var eEl = E('contacts', row); eEl.hidden = !(err && state.strict); eEl.innerHTML = err ? ICON('x-circle') + '<span>' + esc(err) + '</span>' : '';
    if (err) { issue(2, 'Pocket ' + (j + 1) + ': ' + err + '.', cb); return; }
    pockets.push({ binder: binder, contacts: toks.map(function (t) { var p = t.split(':'); return { chain: p[0], ref: p.slice(1).join(':') }; }),
      max_distance: F('maxd', row).value, force: F('force', row).checked });
  });
  rowsOf('contact').forEach(function (row, j) {
    var v = { chain1: F('chain1', row).value, ref1: F('ref1', row).value.trim(), chain2: F('chain2', row).value, ref2: F('ref2', row).value.trim(),
      max_distance: F('maxd', row).value, force: F('force', row).checked };
    if (!v.chain1 || !v.chain2 || !v.ref1 || !v.ref2) { issue(2, 'Contact ' + (j + 1) + ': choose both chains and fill both residue or atom fields.', F('chain1', row)); return; }
    contacts.push(v);
  });
  var payload = { sequences: sequences, templates: templates, constraints: { bonds: bonds, pockets: pockets, contacts: contacts }, properties: {} };
  if (F('affinity-on').checked && !F('affinity-card').hidden) {
    var binder = F('affinity-chain').value;
    if (!binder) { issue(1, 'Choose the ligand chain for affinity prediction.', F('affinity-chain')); } else { payload.properties.affinity_binder = binder; }
  }
  return { payload: payload, issues: issues };
}

// ------------------------------------------------------------------------------------ rail
var TILE_CLASS = { protein: 'protein', dna: 'dna', rna: 'rna', ligand: 'ligand' };
function highlightYaml(text) {
  return esc(text).split('\n').map(function (line) {
    var m = /^(\s*(?:- )?)([A-Za-z_][\w]*)(:)(.*)$/.exec(line);
    if (!m) { return line.replace(/^(\s*-\s)(.*)$/, '<span class="p">$1</span>$2'); }
    var v = m[4].replace(/^(\s*)('.*'|&#39;.*&#39;)$/, '$1<span class="s">$2</span>').replace(/^(\s*)(-?\d+(?:\.\d+)?)$/, '$1<span class="n">$2</span>');
    return m[1] + '<span class="k">' + m[2] + '</span><span class="p">:</span>' + v;
  }).join('\n');
}
function refreshRail() {
  var ents = cards(), mols = F('rail-mols'), html = '';
  var nChains = 0, nRes = 0, nLig = 0;
  ents.forEach(function (c) {
    var t = c.dataset.type, ids = cardIds(c), what, meta;
    nChains += ids.length;
    if (t === 'ligand') {
      nLig += ids.length;
      var k = kindOf(c), v = F('value', c).value.trim();
      what = 'Ligand'; meta = v ? (k === 'ccd' ? 'CCD ' + v : (c._lig ? c._lig.formula + ' - ' + c._lig.heavy_atoms + ' heavy atoms' : 'SMILES')) : 'not set';
    } else {
      var n = seqOf(c).length; nRes += n * Math.max(ids.length, 1);
      what = TYPE[t].title; meta = n ? plural(n, TYPE[t].unit) + (ids.length > 1 ? ' x ' + ids.length : '') : 'no sequence yet';
      if (t === 'protein') { meta += ' - MSA ' + ({ server: 'server', custom: 'uploaded', empty: 'none' }[c._msaMode || 'server']); }
    }
    html += '<li class="bz-mol"><span class="bz-tile bz-tile--' + TILE_CLASS[t] + ' bz-tile--sm">' + TYPE[t].letter + '</span><div><b>' + esc(what) + '</b><small>' + esc(meta) + '</small></div>' +
      ids.map(function (i) { return '<span class="bz-token">' + esc(i) + '</span>'; }).join('') + '</li>';
  });
  mols.innerHTML = html || '<li class="bz-rail-empty">Add a molecule to begin.</li>';
  var nCons = rowsOf('bond').length + rowsOf('pocket').length + rowsOf('contact').length;
  F('rail-stats').innerHTML = ents.length ? [['Chains', nChains], ['Residues', fmtNum(nRes)], ['Ligands', nLig], ['Constraints', nCons + rowsOf('template').length]]
    .map(function (s) { return '<div class="bz-stat"><span>' + s[0] + '</span><b>' + s[1] + '</b></div>'; }).join('') : '';
  F('mol-count').textContent = ents.length; F('mol-count').setAttribute('data-n', ents.length);
  ['templates', 'bonds', 'pockets', 'contacts'].forEach(function (k) { var el = F('count-' + k); if (el) { var n = $$('[data-row]', F(k)).length; el.textContent = n; el.setAttribute('data-n', n); } });
  $$('[data-f="mods-count"]').forEach(function (el) { el.textContent = $$('[data-row="mod"]', el.closest('details')).length; el.setAttribute('data-n', el.textContent); });
}
function renderMessages(issues, preview) {
  var out = '', chip = F('status-chip');
  var errs = issues.map(function (i) { return i.msg; });
  if (preview && preview.status === 'error' && !errs.length) { errs = [preview.message]; }
  if (errs.length && (state.strict || cards().some(function (c) { return !isPristine(c); }))) {
    out += '<div class="bz-alert bz-alert--err">' + ICON('x-circle') + '<div><strong>' + (state.strict ? plural(errs.length, 'thing') + ' to fix' : 'Not ready yet') + '</strong><ul>' +
      errs.slice(0, 4).map(function (m) { return '<li>' + esc(m) + '</li>'; }).join('') + (errs.length > 4 ? '<li>and ' + (errs.length - 4) + ' more</li>' : '') + '</ul></div></div>';
  }
  if (preview && preview.status === 'ok') {
    (preview.warnings || []).forEach(function (w) { out += '<div class="bz-alert bz-alert--warn">' + ICON('alert') + '<div>' + esc(w) + '</div></div>'; });
    if ((preview.notes || []).length) { out += '<div class="bz-alert">' + ICON('info') + '<div><ul>' + preview.notes.map(function (n) { return '<li>' + esc(n) + '</li>'; }).join('') + '</ul></div></div>'; }
  }
  F('rail-messages').innerHTML = out;
  var ok = !errs.length && preview && preview.status === 'ok';
  if (!cards().length) { chip.textContent = 'Empty'; chip.className = 'bz-chip'; }
  else if (ok && (preview.warnings || []).length) { chip.textContent = 'Check warnings'; chip.className = 'bz-chip bz-chip--warn'; }
  else if (ok) { chip.textContent = 'Valid'; chip.className = 'bz-chip bz-chip--ok'; }
  else if (errs.length && state.strict) { chip.textContent = plural(errs.length, 'issue'); chip.className = 'bz-chip bz-chip--err'; }
  else { chip.textContent = 'Incomplete'; chip.className = 'bz-chip bz-chip--warn'; }
}
function updateStepStates(issues) {
  var by = { 1: 0, 2: 0 };
  issues.forEach(function (i) { by[i.step] = (by[i.step] || 0) + 1; });
  $$('.bz-step').forEach(function (b) {
    var n = Number(b.getAttribute('data-go')), st = '';
    if (n === 1) { st = by[1] ? (state.strict ? 'error' : '') : (cards().length && state.visited[2] || state.step > 1 ? 'done' : ''); }
    if (n === 2) { st = by[2] ? (state.strict ? 'error' : '') : (state.visited[3] || state.step > 2 ? 'done' : ''); }
    if (n === 3) { st = state.saved ? 'done' : (state.runIssues && state.runIssues.length && state.strict ? 'error' : ''); }
    var num = b.querySelector('.bz-step-num');
    if (st) { b.setAttribute('data-state', st); } else { b.removeAttribute('data-state'); }
    num.innerHTML = st === 'done' ? ICON('check') : (st === 'error' ? '!' : String(n === 3 && !ADV ? 2 : n));
  });
}
var previewNow = function () {
  var c = collect(), req = ++state.previewReq;
  refreshRail(); updateStepStates(c.issues);
  if (c.issues.length) { state.lastPreview = null; renderMessages(c.issues, null); F('yaml').textContent = '# Complete the highlighted fields to see the YAML.'; return; }
  rpc('preview_params', [c.payload]).then(function (r) {
    if (req !== state.previewReq) { return; }
    state.lastPreview = r;
    if (r && r.status === 'ok' && typeof r.yaml === 'string') { F('yaml').innerHTML = highlightYaml(r.yaml); }
    else { F('yaml').textContent = '# ' + ((r && r.message) || 'The notebook kernel did not return the YAML. Run the Generate Parameters cell again.'); }
    renderMessages(collect().issues, r);
  }).catch(function (err) {
    if (req !== state.previewReq) { return; }
    F('yaml').textContent = '# ' + err.message; renderMessages([], null);
  });
};
var previewSoon = debounce(previewNow, 420);
function refreshAll() { refreshChainSelects(); refreshAffinity(); refreshRail(); markDirty(); previewSoon(); }
function markDirty() {
  if (state.saved) { state.saved = false; F('saved').hidden = true; setMsg('Unsaved changes', ''); }
}
function setMsg(text, tone) { var m = F('action-msg'); m.textContent = text || ''; if (tone) { m.setAttribute('data-tone', tone); } else { m.removeAttribute('data-tone'); } }

// ------------------------------------------------------------------------------------ run settings
var PRESETS = {
  fast: { label: 'Fast', icon: 'zap', text: 'Quick sanity check. Fewer steps and a shallow alignment, good for testing inputs.' },
  balanced: { label: 'Balanced', icon: 'scale', text: 'The recommended default for most predictions.' },
  scientific: { label: 'Scientific', icon: 'sparkles', text: 'Five samples with steering potentials for results you intend to report.' }
};
var TUNED = ['recycling_steps', 'sampling_steps', 'diffusion_samples', 'step_scale', 'max_msa_seqs', 'use_potentials'];
function presetValues(name) { return Object.assign({}, CFG.defaults, CFG.profiles[name] || {}); }
function R(key) { return root.querySelector('[data-r="' + key + '"]'); }
function setRun(key, value) {
  var el = R(key); if (!el) { return; }
  if (el.type === 'checkbox') { el.checked = !!value; }
  else { el.value = value === null || value === undefined ? '' : value; }
  if (el.type === 'range') { el._exact = value; }
  var out = root.querySelector('[data-o="' + key + '"]');
  if (out) { out.textContent = key === 'step_scale' ? Number(value).toFixed(2) : value; }
}
function readRun() {
  var v = {};
  $$('[data-r]').forEach(function (el) {
    var k = el.getAttribute('data-r');
    // a slider snaps to its step (1.638 -> 1.65); keep the exact preset value until the user moves it
    v[k] = el.type === 'checkbox' ? el.checked : (el._exact !== undefined ? String(el._exact) : el.value);
  });
  return v;
}
function sameVal(a, b) { if (typeof b === 'number') { return Math.abs(Number(a) - b) < 0.011; } return a === b; }
function matchPreset(v) {
  var names = Object.keys(PRESETS);
  for (var i = 0; i < names.length; i++) {
    var p = presetValues(names[i]);
    if (TUNED.every(function (k) { return sameVal(k === 'max_msa_seqs' ? Number(v[k]) : v[k], p[k]); })) { return names[i]; }
  }
  return null;
}
function renderPresets() {
  var box = F('presets');
  box.innerHTML = Object.keys(PRESETS).map(function (name) {
    var P = PRESETS[name], v = presetValues(name);
    return '<button type="button" class="bz-preset" role="radio" aria-checked="false" data-preset="' + name + '">' +
      '<span class="bz-check">' + ICON('check') + '</span>' +
      '<span class="bz-preset-h"><span class="bz-tile">' + ICON(P.icon) + '</span>' + P.label + '</span><p>' + P.text + '</p>' +
      '<dl><div><dt>steps</dt><dd>' + v.sampling_steps + '</dd></div><div><dt>samples</dt><dd>' + v.diffusion_samples + '</dd></div>' +
      '<div><dt>MSA</dt><dd>' + fmtNum(v.max_msa_seqs) + '</dd></div><div><dt>potentials</dt><dd>' + (v.use_potentials ? 'on' : 'off') + '</dd></div></dl></button>';
  }).join('');
  $$('.bz-preset', box).forEach(function (b) { b.addEventListener('click', function () { applyPreset(b.getAttribute('data-preset')); }); });
}
function applyPreset(name) {
  var p = presetValues(name);
  TUNED.forEach(function (k) { setRun(k, p[k]); });
  syncPreset(); refreshAll();
}
function syncPreset() {
  var name = matchPreset(readRun());
  $$('.bz-preset').forEach(function (b) { b.setAttribute('aria-checked', b.getAttribute('data-preset') === name ? 'true' : 'false'); });
  var badge = F('preset-badge');
  badge.textContent = name ? PRESETS[name].label : 'Custom';
  badge.className = 'bz-chip ' + (name ? 'bz-chip--primary' : 'bz-chip--warn');
}
function initRun() {
  var fill = function (key, arr) { var el = R(key); el.innerHTML = arr.map(function (x) { return '<option value="' + x + '">' + fmtNum(x) + '</option>'; }).join(''); };
  fill('max_msa_seqs', CFG.msaChoices); fill('num_subsampled_msa', CFG.subsampleChoices);
  R('msa_pairing_strategy').innerHTML = CFG.pairing.map(function (x) { return '<option value="' + x + '">' + x + '</option>'; }).join('');
  var d = presetValues('balanced');
  ['recycling_steps', 'sampling_steps', 'diffusion_samples', 'step_scale', 'max_msa_seqs', 'use_potentials', 'override', 'subsample_msa', 'num_subsampled_msa', 'msa_pairing_strategy'].forEach(function (k) { setRun(k, d[k]); });
  setRun('seed', ''); setRun('job_name', '');
  renderPresets(); syncPreset();
  R('job_name').addEventListener('input', function () { this.value = this.value.replace(/\s+/g, '_'); });
  R('job_name').addEventListener('blur', function () { R('job_name')._touched = true; validateRun(false); });
  $$('[data-r]').forEach(function (el) {
    var evt = (el.type === 'range' || el.type === 'checkbox' || el.tagName === 'SELECT') ? 'input' : 'input';
    el.addEventListener(evt, function () {
      var k = el.getAttribute('data-r');
      if (el.type === 'range') { delete el._exact; }
      if (k === 'step_scale') { el.value = Math.round(Number(el.value) * 100) / 100; }
      var out = root.querySelector('[data-o="' + k + '"]'); if (out) { out.textContent = k === 'step_scale' ? Number(el.value).toFixed(2) : el.value; }
      syncPreset(); validateRun(false); refreshAll();
    });
  });
}
function validateRun(strict) {
  var v = readRun(), problems = [];
  var jn = R('job_name'), je = E('job_name');
  if (strict) { jn._touched = true; }           // keep the message visible when later passes re-validate quietly
  var msg = !v.job_name ? 'Give the job a name.' : (!JOB_RE.test(v.job_name) ? 'Use letters, digits, underscore, dash or dot only (max 60).' : '');
  var showJ = !!msg && (strict || jn._touched);
  je.hidden = !showJ; je.innerHTML = showJ ? ICON('x-circle') + '<span>' + esc(msg) + '</span>' : '';
  if (showJ) { jn.setAttribute('aria-invalid', 'true'); } else { jn.removeAttribute('aria-invalid'); }
  if (msg) { problems.push({ step: 3, msg: msg, el: jn }); }
  Object.keys(CFG.ranges).forEach(function (k) {
    var el = R(k); if (!el || el.value === '') { return; }
    var lo = CFG.ranges[k][0], hi = CFG.ranges[k][1], x = Number(el.value);
    if (!(x >= lo && x <= hi)) { problems.push({ step: 3, msg: k.replace(/_/g, ' ') + ' must be between ' + lo + ' and ' + hi + '.', el: el }); el.setAttribute('aria-invalid', 'true'); }
    else { el.removeAttribute('aria-invalid'); }
  });
  var sd = R('seed');
  if (sd.value !== '' && !(Number(sd.value) >= 0 && Math.floor(Number(sd.value)) === Number(sd.value))) { problems.push({ step: 3, msg: 'The random seed must be a whole number of 0 or more.', el: sd }); }
  state.runIssues = problems;
  return problems;
}
function runParamsText() {
  var v = readRun(), L = [];
  L.push('job_name = "' + v.job_name.trim() + '"');
  L.push('use_potentials = ' + v.use_potentials);
  L.push('override = ' + v.override);
  ['recycling_steps', 'sampling_steps', 'diffusion_samples', 'step_scale', 'max_msa_seqs'].forEach(function (k) { L.push(k + ' = ' + v[k]); });
  L.push('subsample_msa = ' + v.subsample_msa);
  L.push('num_subsampled_msa = ' + v.num_subsampled_msa);
  L.push('msa_pairing_strategy = "' + v.msa_pairing_strategy + '"');
  if (String(v.seed).trim() !== '') { L.push('seed = ' + Math.floor(Number(v.seed))); }
  return L.join('\n');
}

// ------------------------------------------------------------------------------------ structure import
function setupImport() {
  var zone = $('[data-drop="structure"]');
  bindDrop(zone, function (file) {
    var res = F('import-result'); res.hidden = false;
    res.innerHTML = '<div class="bz-file" style="background:var(--bz-surface-3);color:var(--bz-text-2)"><span class="bz-spin"></span><span>Reading ' + esc(file.name) + '...</span></div>';
    readText(file).then(function (text) { return rpc('process_pdb_upload', [{ pdb_content: text, filename: file.name }]); }).then(function (r) { renderImport(file.name, r); })
      .catch(function (err) { res.innerHTML = '<div class="bz-alert bz-alert--err">' + ICON('x-circle') + '<div>' + esc(err.message) + '</div></div>'; });
  });
}
function renderImport(name, r) {
  var res = F('import-result');
  if (!r || r.status !== 'ok' || !Array.isArray(r.entities)) {
    res.innerHTML = '<div class="bz-alert bz-alert--err">' + ICON('x-circle') + '<div><strong>' + esc((r && r.message) || 'The notebook kernel did not return the structure. Run the Generate Parameters cell again.') + '</strong>' + (r && r.hint ? '<br>' + esc(r.hint) : '') + '</div></div>';
    return;
  }
  var ents = r.entities.filter(function (e) { return ADV || e.kind === 'protein'; });
  var skipped = r.entities.length - ents.length;
  var html = '<div class="bz-import-h"><b>' + esc(name) + '</b><span class="bz-chip bz-chip--ok">' + plural(r.entities.length, 'entity', 'entities') + ' found</span>' +
    '<button type="button" class="bz-btn bz-btn--primary bz-btn--sm" style="margin-left:auto" data-imp="all">' + ICON('plus') + '<span>Add all chains</span></button></div>';
  ents.forEach(function (e, i) {
    html += '<div class="bz-import-ent"><span class="bz-tile bz-tile--' + e.kind + ' bz-tile--sm">' + TYPE[e.kind].letter + '</span><div><b>' + TYPE[e.kind].title + ' - chain' + (e.ids.length > 1 ? 's ' : ' ') + esc(e.ids.join(', ')) + '</b><small>' + plural(e.length, TYPE[e.kind].unit) + ' - ' + esc(e.sequence.slice(0, 48)) + (e.length > 48 ? '...' : '') + '</small></div>' +
      '<button type="button" class="bz-btn bz-btn--secondary bz-btn--sm" data-imp="ent' + i + '">' + ICON('plus') + '<span>Add</span></button></div>';
  });
  var ligs = (r.ligands || []).filter(function (l) { return !l.ion; });
  if (ligs.length) {
    html += '<div class="bz-hint" style="margin-top:12px">Ligand components in the file (added by CCD code):</div><div class="bz-inline" style="margin-top:6px">' +
      ligs.map(function (l, i) { return '<button type="button" class="bz-btn bz-btn--secondary bz-btn--sm" data-imp="lig' + i + '">' + ICON('plus') + '<span class="bz-mono">' + esc(l.ccd) + '</span></button>'; }).join('') + '</div>';
  }
  if (skipped) { html += '<div class="bz-alert bz-alert--warn" style="margin-top:12px">' + ICON('info') + '<div>' + plural(skipped, 'DNA/RNA entity', 'DNA/RNA entities') + ' not shown: nucleic acids are available in the Advanced notebook.</div></div>'; }
  res.innerHTML = html;
  function addEnt(e) { dropPristine(); addEntity(e.kind, { ids: e.ids, sequence: e.sequence }); }
  $('[data-imp="all"]', res).addEventListener('click', function () { ents.forEach(addEnt); this.disabled = true; });
  ents.forEach(function (e, i) { $('[data-imp="ent' + i + '"]', res).addEventListener('click', function () { addEnt(e); this.disabled = true; }); });
  ligs.forEach(function (l, i) { $('[data-imp="lig' + i + '"]', res).addEventListener('click', function () { dropPristine(); addEntity('ligand', { kind: 'ccd', value: l.ccd }); this.disabled = true; }); });
}
function dropPristine() { cards().forEach(function (c) { if (isPristine(c) && cards().length === 1) { c.remove(); } }); }

// ------------------------------------------------------------------------------------ navigation
function lastStep() { return 3; }
function go(n) {
  if (!ADV && n === 2) { n = 3; }
  state.step = n; state.visited[n] = true;
  $$('.bz-panel').forEach(function (p) { p.hidden = Number(p.getAttribute('data-panel')) !== n; });
  $$('.bz-step').forEach(function (b) { if (Number(b.getAttribute('data-go')) === n) { b.setAttribute('aria-current', 'step'); } else { b.removeAttribute('aria-current'); } });
  var last = n === lastStep();
  F('next-label').textContent = last ? 'Save configuration' : 'Continue';
  var nb = $('[data-act="next"]'), nbIcon = nb.querySelector('svg.i');     // absent while the save spinner is showing
  if (nbIcon) { nbIcon.innerHTML = '<use href="#bz-i-' + (last ? 'check' : 'arrow-right') + '"/>'; }
  $('[data-act="back"]').style.visibility = n === 1 ? 'hidden' : 'visible';
  if (n === 3) { validateRun(false); }
  updateStepStates(collect().issues);
  if (root.scrollIntoView) { try { root.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } catch (e) { /* ignore */ } }
}
function prevStep() { return state.step === 3 && !ADV ? 1 : state.step - 1; }
function nextStep() { return state.step === 1 && !ADV ? 3 : state.step + 1; }

// ------------------------------------------------------------------------------------ save
function setBusy(on) {
  var nb = $('[data-act="next"]');
  nb.disabled = on;
  if (on) { nb.querySelector('svg.i').outerHTML = '<span class="bz-spin" data-spin></span>'; }
  else { var sp = nb.querySelector('[data-spin]'); if (sp) { sp.outerHTML = ICON(state.step === lastStep() ? 'check' : 'arrow-right'); } }
}
function save() {
  state.strict = true;
  var c = collect(), run = validateRun(true), all = c.issues.concat(run);
  cards().forEach(paintCard); refreshRail(); updateStepStates(c.issues); renderMessages(c.issues, state.lastPreview);
  if (all.length) {
    var first = all[0];
    go(first.step);
    setMsg(plural(all.length, 'issue') + ' to fix before saving', 'err');
    if (first.el && first.el.focus) { setTimeout(function () { try { first.el.focus(); first.el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (e) { /* ignore */ } }, 60); }
    return Promise.resolve(false);
  }
  setBusy(true); setMsg('Saving...', '');
  return rpc('save_params', [c.payload]).then(function (a) {
    if (!a || a.status !== 'ok') { throw new Error((a && a.message) || 'Could not save the YAML.'); }
    return rpc('save_run_params', [{ filename: 'run_params.txt', content: runParamsText() }]).then(function (b) {
      if (!b || b.status !== 'ok') { throw new Error((b && b.message) || 'Could not save the run settings.'); }
      state.saved = true; state.lastPreview = a;
      F('saved').hidden = false;
      F('saved-msg').textContent = 'params.yaml and run_params.txt are written. Run the next cell, "Run Boltz2 Engine", to start the prediction.';
      setMsg('Saved', 'ok'); go(3); updateStepStates(collect().issues);
      return true;
    });
  }).catch(function (err) {
    setMsg(err.message, 'err'); F('rail-messages').insertAdjacentHTML('afterbegin', '<div class="bz-alert bz-alert--err">' + ICON('x-circle') + '<div>' + esc(err.message) + '</div></div>');
    return false;
  }).then(function (ok) { setBusy(false); return ok; });
}

// ------------------------------------------------------------------------------------ theme + misc
function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) { return navigator.clipboard.writeText(text); }
  return new Promise(function (resolve, reject) {
    var ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy') ? resolve() : reject(new Error('copy blocked')); } catch (e) { reject(e); } ta.remove();
  });
}

// ------------------------------------------------------------------------------------ wiring
root.addEventListener('click', function (ev) {
  var t = ev.target.closest('[data-act]'); if (!t || !root.contains(t)) { return; }
  var act = t.getAttribute('data-act'), card = t.closest('.bz-entity');
  if (act === 'add-protein') { dropPristine(); addEntity('protein'); }
  else if (act === 'add-dna') { dropPristine(); addEntity('dna'); }
  else if (act === 'add-rna') { dropPristine(); addEntity('rna'); }
  else if (act === 'add-ligand') { addEntity('ligand'); }
  else if (act === 'remove' && card) { card.remove(); refreshAll(); }
  else if (act === 'dup' && card) {
    var ty = card.dataset.type;
    if (ty === 'ligand') { addEntity('ligand', { after: card, kind: kindOf(card), value: F('value', card).value }); }
    else { addEntity(ty, { after: card, sequence: F('seq', card).value, msa: card._msaMode, label: card._label }); }
  }
  else if (act === 'split' && card) {
    var extras = card._extra || []; setExtra(card, []);
    extras.forEach(function (r) { addEntity(card.dataset.type, { sequence: r.seq, label: r.header, after: card }); });
  }
  else if (act === 'add-template') { addRow('template'); }
  else if (act === 'add-bond') { addRow('bond'); }
  else if (act === 'add-pocket') { addRow('pocket'); }
  else if (act === 'add-contact') { addRow('contact'); }
  else if (act === 'back') { go(prevStep()); }
  else if (act === 'next') { if (state.step === lastStep()) { save(); } else { go(nextStep()); } }
  else if (act === 'reset') {
    if (!t._armed) { t._armed = true; t.querySelector('span').textContent = 'Click again to reset'; setTimeout(function () { t._armed = false; t.querySelector('span').textContent = 'Reset'; }, 3000); return; }
    t._armed = false; t.querySelector('span').textContent = 'Reset';
    cards().forEach(function (c) { c.remove(); });
    ['templates', 'bonds', 'pockets', 'contacts'].forEach(function (k) { F(k).innerHTML = ''; });
    F('import-result').hidden = true; F('import-result').innerHTML = ''; state.strict = false; state.saved = false; F('saved').hidden = true;
    addEntity('protein'); setMsg('', '');
  }
  else if (act === 'copy-yaml') {
    var txt = F('yaml').textContent, span = t.querySelector('span');
    copyText(txt).then(function () { span.textContent = 'Copied'; }).catch(function () { span.textContent = 'Press Ctrl+C to copy'; });
    setTimeout(function () { span.textContent = 'Copy YAML'; }, 1800);
  }
});
$$('.bz-step').forEach(function (b) { b.addEventListener('click', function () { go(Number(b.getAttribute('data-go'))); }); });
$$('input[name^="tab-"]').forEach(function (r) {
  r.addEventListener('change', function () { $$('[data-view]').forEach(function (v) { v.hidden = v.getAttribute('data-view') !== r.value; }); });
});
root.addEventListener('chipschange', function () { refreshAll(); });
root.addEventListener('change', function (ev) { if (ev.target.matches('[data-f="affinity-on"], [data-f="affinity-chain"]')) { refreshAffinity(); refreshAll(); } });
root.addEventListener('input', function (ev) {
  var t = ev.target;
  if (t.closest('.bz-entity') || t.closest('[data-row]')) { refreshAll(); }
  if (t.matches('[data-f="maxd"]')) { var o = t.parentNode.querySelector('output'); if (o) { o.textContent = t.value; } }
});
root.addEventListener('focusout', function (ev) {
  var card = ev.target.closest && ev.target.closest('.bz-entity'); if (!card) { return; }
  var f = ev.target.closest('[data-f]'); var key = f && f.getAttribute('data-f');
  if (key === 'ids' || ev.target.closest('[data-f="ids"]')) { setTouched(card, 'ids'); paintCard(card); }
  if (key === 'seq') { setTouched(card, 'seq'); paintCard(card); }
});
$$('[data-f="rail-mols"] .bz-token').forEach(function () {});

// Each start-up step is isolated, so one failing part cannot leave the rest of the form dead.
var failures = [];
function step(name, fn) {
  try { fn(); } catch (err) {
    failures.push(name + ': ' + (err && err.message ? err.message : err));
    if (window.console) { console.error('[boltz2nb ui] ' + name, err); }
  }
}
step('import panel', setupImport);
step('run settings', initRun);
step('theme', function () { if (window.__bzTheme) { window.__bzTheme.apply(); } });   // adopt the theme once the markup exists
step('first molecule', function () { addEntity('protein'); });
step('step tracker', function () { go(1); });
step('live preview', previewNow);
root._bz = { state: state, collect: collect, go: go, save: save, addEntity: addEntity, addRow: addRow, readRun: readRun, applyPreset: applyPreset };
if (failures.length) { showProblem(root, 'Part of the form did not start:', failures); }

// An error raised right after the user touches the form is reported on screen too (not only in the console).
var lastUse = 0;
['pointerdown', 'keydown', 'input', 'change'].forEach(function (t) { root.addEventListener(t, function () { lastUse = Date.now(); }, true); });
window.addEventListener('error', function (ev) {
  if (root.isConnected && Date.now() - lastUse < 1500) { showProblem(root, 'The form hit an error:', [String(ev.message)]); }
});
}

// Start as soon as the markup is in the document. Some front-ends run a script before they have inserted the HTML that
// precedes it, so wait briefly instead of giving up.
(function boot(tries) {
  var root = document.getElementById('bz-root-' + UID);
  if (!root) { if (tries < 50) { setTimeout(function () { boot(tries + 1); }, 100); } return; }
  if (root._bzStarted) { return; }
  root._bzStarted = true;
  try { start(root); } catch (err) {
    if (window.console) { console.error('[boltz2nb ui] start failed', err); }
    showProblem(root, 'The form could not start:', [String(err && err.stack ? err.stack : err).split('\n').slice(0, 4).join('\n')]);
  }
})(0);
})();
