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
