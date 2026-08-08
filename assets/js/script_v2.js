const navToggle = document.getElementById('navToggle');
const navMenu = document.getElementById('navMenu');

if (navToggle && navMenu) {
  navToggle.addEventListener('click', () => {
    const open = navMenu.classList.toggle('open');
    navToggle.setAttribute('aria-expanded', String(open));
  });

  navMenu.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      navMenu.classList.remove('open');
      navToggle.setAttribute('aria-expanded', 'false');
    });
  });
}

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.12 }
);

document.querySelectorAll('.reveal').forEach((node) => observer.observe(node));

// Modern Progress Bar Interactivity
(function initProgressBar() {
  const progressSteps = document.querySelectorAll('.progress-step');
  const detailCards = document.querySelectorAll('.detail-card');

  if (progressSteps.length === 0 || detailCards.length === 0) return;

  // Set first card as active by default
  detailCards[0].classList.add('active');

  progressSteps.forEach((step, index) => {
    step.addEventListener('mouseenter', () => {
      // Remove active from all cards
      detailCards.forEach((card) => card.classList.remove('active'));
      // Add active to corresponding card
      if (detailCards[index]) {
        detailCards[index].classList.add('active');
      }
    });

    // Also support click for better mobile experience
    step.addEventListener('click', () => {
      detailCards.forEach((card) => card.classList.remove('active'));
      if (detailCards[index]) {
        detailCards[index].classList.add('active');
      }
    });
  });

  // Restore first card on mouse leaving the entire progress section
  const progressTrack = document.querySelector('.progress-track');
  if (progressTrack) {
    progressTrack.addEventListener('mouseleave', () => {
      detailCards.forEach((card) => card.classList.remove('active'));
      detailCards[0].classList.add('active');
    });
  }
})();

// Citation format selector and copy handler
document.addEventListener('DOMContentLoaded', function () {
  const formatSelect = document.getElementById('citationFormatSelect');
  const citationText = document.getElementById('citationText');
  const copyCitationBtn = document.getElementById('copyCitationBtn');
  const citationStatus = document.getElementById('citationCopyStatus');

  if (!formatSelect || !citationText) return;

  const citations = {
    apa: 'Tilewale, A., & Patel, D. (2026). Boltz2-Notebook: A streamlined Colab-based pipeline for biomolecular structure prediction and binding affinity analysis using the Boltz2 deep learning model. https://doi.org/10.5281/zenodo.21850102',
    mla: 'Tilewale, Atharva, and Dhaval Patel. Boltz2-Notebook: A streamlined Colab-based pipeline for biomolecular structure prediction and binding affinity analysis using the Boltz2 deep learning model. 2026. Zenodo, https://doi.org/10.5281/zenodo.21850102.',
    ieee: 'A. Tilewale and D. Patel, "Boltz2-Notebook: A streamlined Colab-based pipeline for biomolecular structure prediction and binding affinity analysis using the Boltz2 deep learning model," Zenodo, 2026. DOI: 10.5281/zenodo.21850102',
    chicago: 'Tilewale, Atharva, and Dhaval Patel. 2026. "Boltz2-Notebook: A streamlined Colab-based pipeline for biomolecular structure prediction and binding affinity analysis using the Boltz2 deep learning model." Zenodo. https://doi.org/10.5281/zenodo.21850102.'
  };

  function updateCitationDisplay() {
    const fmt = formatSelect.value || 'apa';
    citationText.textContent = citations[fmt] || citations.apa;
  }

  formatSelect.addEventListener('change', updateCitationDisplay);

  // initialize
  updateCitationDisplay();

  if (copyCitationBtn) {
    copyCitationBtn.addEventListener('click', async function () {
      const text = citationText.innerText.trim();
      try {
        await navigator.clipboard.writeText(text);
        if (citationStatus) citationStatus.textContent = 'Citation copied to clipboard.';
      } catch (e) {
        if (citationStatus) citationStatus.textContent = 'Copy failed — select and copy manually.';
      }
      setTimeout(() => { if (citationStatus) citationStatus.textContent = ''; }, 3000);
    });
  }
});

// Citation copy-to-clipboard handler
document.addEventListener('DOMContentLoaded', function () {
  const copyBtn = document.getElementById('copyBibBtn');
  const bibBlock = document.getElementById('bibtexBlock');
  const status = document.getElementById('copyStatus');

  if (!copyBtn || !bibBlock) return;

  copyBtn.addEventListener('click', async function () {
    const text = bibBlock.innerText.trim();
    try {
      await navigator.clipboard.writeText(text);
      if (status) status.textContent = 'BibTeX copied to clipboard.';
      copyBtn.focus();
    } catch (e) {
      if (status) status.textContent = 'Copy failed — please select and copy manually.';
    }
    setTimeout(() => { if (status) status.textContent = ''; }, 3000);
  });
});

// Download-as dropdown menu handling
document.addEventListener('DOMContentLoaded', function () {
  const downloadBtn = document.getElementById('downloadAsBtn');
  const downloadMenu = document.getElementById('downloadAsMenu');
  const bibBlock = document.getElementById('bibtexBlock');

  if (!downloadBtn || !downloadMenu || !bibBlock) return;

  const meta = {
    id: 'tilewale2026boltz2',
    authors: [
      { given: 'Atharva', family: 'Tilewale' },
      { given: 'Dhaval', family: 'Patel' }
    ],
    title: 'Boltz2-Notebook: A streamlined Colab-based pipeline for biomolecular structure prediction and binding affinity analysis using the Boltz2 deep learning model',
    year: '2026',
    doi: '10.5281/zenodo.21850102',
    url: 'https://github.com/AtharvaTilewale/boltz2-notebook',
  };

  function generateBibtex() { return bibBlock.innerText.trim(); }

  function generateRIS() {
    let out = 'TY  - MISC\n';
    meta.authors.forEach(a => { out += `AU  - ${a.family}, ${a.given}\n`; });
    out += `TI  - ${meta.title}\n`;
    out += `PY  - ${meta.year}\n`;
    if (meta.doi) out += `DO  - ${meta.doi}\n`;
    if (meta.url) out += `UR  - ${meta.url}\n`;
    if (meta.note) out += `AB  - ${meta.note}\n`;
    out += 'ER  -\n';
    return out;
  }

  function generateEndNote() { return generateRIS(); }

  function generateCSLJSON() {
    const item = {
      id: meta.id,
      type: 'webpage',
      author: meta.authors.map(a => ({ given: a.given, family: a.family })),
      title: meta.title,
      URL: meta.url,
      DOI: meta.doi,
      issued: { 'date-parts': [[parseInt(meta.year)]] }
    };
    return JSON.stringify([item], null, 2);
  }

  function downloadFile(content, filename, mime) {
    const blob = new Blob([content], { type: mime || 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  // Toggle menu visibility
  downloadBtn.addEventListener('click', function (e) {
    const open = downloadBtn.getAttribute('aria-expanded') === 'true';
    downloadBtn.setAttribute('aria-expanded', String(!open));
    downloadMenu.hidden = open;
    if (!open) downloadMenu.querySelector('li')?.focus();
  });

  // Handle selection from menu
  downloadMenu.addEventListener('click', function (e) {
    const li = e.target.closest('li[role="menuitem"]');
    if (!li) return;
    const fmt = li.dataset.format;
    if (fmt === 'bibtex') {
      downloadFile(generateBibtex(), 'CITATION.bib', 'application/x-bibtex');
    } else if (fmt === 'ris') {
      downloadFile(generateRIS(), 'CITATION.ris', 'application/x-research-info-systems');
    } else if (fmt === 'endnote') {
      downloadFile(generateEndNote(), 'CITATION.enw', 'application/x-endnote-refer');
    } else if (fmt === 'csljson') {
      downloadFile(generateCSLJSON(), 'CITATION.json', 'application/json');
    }
    downloadMenu.hidden = true;
    downloadBtn.setAttribute('aria-expanded', 'false');
  });

  // Close menu on outside click or Escape
  document.addEventListener('click', function (e) {
    if (!downloadMenu.contains(e.target) && e.target !== downloadBtn) {
      downloadMenu.hidden = true;
      downloadBtn.setAttribute('aria-expanded', 'false');
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      downloadMenu.hidden = true;
      downloadBtn.setAttribute('aria-expanded', 'false');
    }
  });

});

// 3Dmol.js Protein Viewer Initialization - MAIN VIEWER
(function initMainViewer() {
  document.addEventListener('DOMContentLoaded', function() {
    const viewer = document.getElementById('viewer');
    if (!viewer) return;

    let config = { backgroundColor: '#07111f' };
    let v = $3Dmol.createViewer(viewer, config);

    $3Dmol.download('pdb:1HBA', v, {}, function() {
      const chainColors = {
        'A': '#3b82f6',
        'B': '#ef4444',
        'C': '#10b981',
        'D': '#f59e0b'
      };
      
      for (const [chain, color] of Object.entries(chainColors)) {
        v.setStyle({ chain: chain }, {});
        v.addSurface($3Dmol.SurfaceType.VDW, { 
          color: color,
          opacity: 0.85
        }, { chain: chain });
      }
      
      v.zoomTo();
      v.spin('y', 1);
      v.render();
    });

    const resetView = document.getElementById('resetView');
    const cartoonView = document.getElementById('cartoonView');
    const stickView = document.getElementById('stickView');
    const sphereView = document.getElementById('sphereView');

    if (resetView) {
      resetView.addEventListener('click', () => {
        v.removeAllSurfaces();
        const chainColors = {
          'A': '#3b82f6',
          'B': '#ef4444',
          'C': '#10b981',
          'D': '#f59e0b'
        };
        for (const [chain, color] of Object.entries(chainColors)) {
          v.addSurface($3Dmol.SurfaceType.VDW, { 
            color: color,
            opacity: 0.85
          }, { chain: chain });
        }
        v.zoomTo();
        v.spin('y', 1);
        v.render();
      });
    }

    if (cartoonView) {
      cartoonView.addEventListener('click', () => {
        v.removeAllSurfaces();
        v.setStyle({}, { cartoon: { colorscheme: 'chainHelix' } });
        v.spin('y', 1);
        v.render();
      });
    }

    if (stickView) {
      stickView.addEventListener('click', () => {
        v.removeAllSurfaces();
        v.setStyle({}, { stick: { colorscheme: 'chainHelix' } });
        v.spin('y', 1);
        v.render();
      });
    }

    if (sphereView) {
      sphereView.addEventListener('click', () => {
        v.removeAllSurfaces();
        const chainColors = {
          'A': '#3b82f6',
          'B': '#ef4444',
          'C': '#10b981',
          'D': '#f59e0b'
        };
        for (const [chain, color] of Object.entries(chainColors)) {
          v.addSurface($3Dmol.SurfaceType.VDW, { 
            color: color,
            opacity: 0.85
          }, { chain: chain });
        }
        v.spin('y', 1);
        v.render();
      });
    }
  });
})();

// 3Dmol.js BACKGROUND VIEWER - HERO SECTION
(function initBgViewer() {
  setTimeout(() => {
    const bgViewer = document.getElementById('bgViewer');
    if (!bgViewer) return;

    try {
      let bgConfig = { backgroundColor: 'rgba(0,0,0,0)' };
      let bgV = $3Dmol.createViewer(bgViewer, bgConfig);
      
      $3Dmol.download('pdb:1HBA', bgV, {}, function() {
        // Cartoon style is significantly lighter than full molecular surfaces.
        bgV.setStyle({}, { cartoon: { color: '#8b92a0' } });
        bgV.zoomTo();
        bgV.spin('y', 0.18);
        bgV.render();
      });
    } catch(e) {
      console.log('Background viewer error:', e);
    }
  }, 100);
})();
