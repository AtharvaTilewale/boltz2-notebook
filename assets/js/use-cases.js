document.addEventListener('DOMContentLoaded', () => {
  const scenarioLabel = document.getElementById('builderScenarioLabel');
  const fieldType = document.getElementById('builderFieldType');
  const fieldId = document.getElementById('builderFieldId');
  const fieldSequence = document.getElementById('builderFieldSequence');
  const fieldLigandOption = document.getElementById('builderFieldMsa');
  const fieldDna = document.getElementById('builderFieldDna');
  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
  let renderProtein = null;
  let currentScene = 'chain-a';
  let running = true;

  const typewriter = async (element, text, speed = 22) => {
    element.textContent = '';
    for (let i = 0; i < text.length; i += 1) {
      element.textContent += text[i];
      await sleep(speed);
    }
  };

  const appendWriter = async (element, text, speed = 22) => {
    for (let i = 0; i < text.length; i += 1) {
      element.textContent += text[i];
      await sleep(speed);
    }
  };

  const rows = {
    type: fieldType?.closest('.builder-input-row'),
    id: fieldId?.closest('.builder-input-row'),
    sequence: fieldSequence?.closest('.builder-input-row'),
    ligandOption: fieldLigandOption?.closest('.builder-input-row'),
    dna: fieldDna?.closest('.builder-input-row')
  };

  const setRowVisible = (rowName, visible) => {
    const row = rows[rowName];
    if (!row) return;
    row.hidden = !visible;
  };

  const setActiveRow = (rowName) => {
    Object.entries(rows).forEach(([name, row]) => {
      if (!row) return;
      row.classList.toggle('is-active', name === rowName);
    });
  };

  const setStaticFields = () => {
    if (fieldType) fieldType.textContent = 'protein';
    if (fieldLigandOption) fieldLigandOption.textContent = '';
    if (fieldDna) fieldDna.textContent = '';
    if (fieldId) fieldId.textContent = '';
    if (fieldSequence) fieldSequence.textContent = '';
  };

  const clearAllFields = () => {
    if (fieldType) fieldType.textContent = '';
    if (fieldLigandOption) fieldLigandOption.textContent = '';
    if (fieldDna) fieldDna.textContent = '';
    if (fieldId) fieldId.textContent = '';
    if (fieldSequence) fieldSequence.textContent = '';
  };

  const builderFields = [fieldType, fieldId, fieldSequence, fieldLigandOption, fieldDna];
  const hasBuilderCard = builderFields.every(Boolean) && scenarioLabel;

  if (hasBuilderCard) {
    const dnaResidues = new Set(['DA', 'DT', 'DG', 'DC', 'DU']);
    let dnaChains = ['E', 'F'];

    const extractDnaChains = (pdbData) => Array.from(new Set(
      pdbData
        .split(/\r?\n/)
        .filter((line) => (line.startsWith('ATOM') || line.startsWith('HETATM')) && dnaResidues.has(line.slice(17, 20).trim()))
        .map((line) => line.slice(21, 22).trim())
        .filter(Boolean)
    ));

    renderProtein = (viewer, proteinPdb, mode) => {
      if (typeof viewer.removeAllModels === 'function') {
        viewer.removeAllModels();
      } else if (typeof viewer.clear === 'function') {
        viewer.clear();
      }

      viewer.addModel(proteinPdb, 'pdb');

      if (mode === 'chain-a') {
        viewer.setStyle({ hetflag: false, chain: 'A' }, { cartoon: { color: '#66b7ff' } });
        viewer.setStyle({ hetflag: false, chain: 'B' }, { hidden: true });
        dnaChains.forEach((chain) => viewer.setStyle({ hetflag: false, chain }, { hidden: true }));
        viewer.setStyle({ hetflag: true }, { hidden: true });
      } else if (mode === 'chain-ab') {
        viewer.setStyle({ hetflag: false, chain: 'A' }, { cartoon: { color: '#66b7ff' } });
        viewer.setStyle({ hetflag: false, chain: 'B' }, { cartoon: { color: '#ff9f43' } });
        dnaChains.forEach((chain) => viewer.setStyle({ hetflag: false, chain }, { hidden: true }));
        viewer.setStyle({ hetflag: true }, { hidden: true });
      } else {
        viewer.setStyle({ hetflag: false, chain: 'A' }, { cartoon: { color: '#66b7ff' } });
        viewer.setStyle({ hetflag: false, chain: 'B' }, { cartoon: { color: '#ff9f43' } });
        viewer.setStyle({ hetflag: true }, { hidden: true });
        dnaChains.forEach((chain) => viewer.setStyle({ hetflag: false, chain }, { hidden: true }));
      }

      if (mode === 'complex' || mode === 'dna') {
        viewer.setStyle({ hetflag: true }, { hidden: false });
        ['C', 'D'].forEach((chain) => {
          viewer.setStyle({ hetflag: true, chain }, { stick: { radius: 0.22, color: '#7be0d3' } });
        });
      }

      if (mode === 'dna') {
        dnaChains.forEach((chain) => viewer.setStyle({ hetflag: false, chain }, { cartoon: { color: '#c084fc' } }));
      }

      viewer.zoomTo();
      viewer.render();
    };

    setStaticFields();
  }

  const viewerElement = document.getElementById('useCasesProteinViewer');
  if (!viewerElement || typeof $3Dmol === 'undefined') {
    return;
  }

  try {
    const viewer = $3Dmol.createViewer(viewerElement, { backgroundColor: 'transparent' });
    viewer.setBackgroundColor(0x000000, 0);
    const syncViewerSize = () => {
      viewer.resize();
      viewer.render();
    };
    let protLigDnaPdb = null;
    let sequenceComplete = false;
    let walkthroughInProgress = false;

    const renderCurrentScene = () => {
      if (!protLigDnaPdb || typeof renderProtein !== 'function') return;

      renderProtein(viewer, protLigDnaPdb, currentScene);

      const surfaceOpacity = 0;
      viewer.addSurface(
        $3Dmol.SurfaceType.VDW,
        { opacity: surfaceOpacity, color: '#66b7ff' },
        { hetflag: false, chain: 'A' }
      );

      if (currentScene !== 'chain-a') {
        viewer.addSurface(
          $3Dmol.SurfaceType.VDW,
          { opacity: surfaceOpacity, color: '#ff9f43' },
          { hetflag: false, chain: 'B' }
        );
      }

      if (typeof viewer.spin === 'function') {
        viewer.spin('y', 0.3);
      }
    };

    const clearViewer = () => {
      if (typeof viewer.spin === 'function') {
        viewer.spin(false);
      }
      if (typeof viewer.removeAllSurfaces === 'function') {
        viewer.removeAllSurfaces();
      }
      if (typeof viewer.removeAllModels === 'function') {
        viewer.removeAllModels();
      } else if (typeof viewer.clear === 'function') {
        viewer.clear();
      }
      viewer.render();
    };

    const renderUlvanLyase = (scene = 'chain-a') => {
      currentScene = scene;
      if (!protLigDnaPdb) return;

      clearViewer();
      renderCurrentScene();
    };

    const loadUlvanLyase = fetch('assets/pdb/prot_lig_dna.pdb')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.text();
      })
      .then((pdbData) => {
        protLigDnaPdb = pdbData;
        dnaChains = extractDnaChains(pdbData);
        if (dnaChains.length === 0) {
          dnaChains = ['F'];
        }
        if (sequenceComplete) {
          renderUlvanLyase(currentScene);
        }
        return pdbData;
      });

    loadUlvanLyase.catch(() => {
      clearViewer();
      viewer.render();
    });

    const runProteinWalkthrough = async () => {
      if (walkthroughInProgress || !running || document.hidden) return;

      walkthroughInProgress = true;
      try {
        while (running && !document.hidden) {
          scenarioLabel.textContent = 'Simple Biomolecules';
          setStaticFields();
          setActiveRow('id');

          await sleep(20);
          if (!running || document.hidden) break;
          await typewriter(fieldId, 'A', 45);

          await sleep(300);
          if (!running || document.hidden) break;
          setActiveRow('sequence');
          await typewriter(fieldSequence, 'MSEQNNTEMTFQIQRIYTKDISFEAPNAPHVFQ', 22);
          sequenceComplete = true;

          renderUlvanLyase('chain-a');

          await sleep(1500);
          if (!running || document.hidden) break;
          setActiveRow('id');
          await appendWriter(fieldId, ', B', 55);

          renderUlvanLyase('chain-ab');

          await sleep(1500);
          if (!running || document.hidden) break;
          setActiveRow('ligandOption');
          await typewriter(fieldLigandOption, 'OC[C@@H](O1)[C@@H](O)', 26);

          renderUlvanLyase('complex');

          await sleep(1500);
          if (!running || document.hidden) break;
          setActiveRow('dna');
          await typewriter(fieldDna, 'ATGCGTACCTGATTGATAGAGCCGCGGC', 26);

          renderUlvanLyase('dna');

          await sleep(5000);
          if (!running || document.hidden) break;
          clearAllFields();
          clearViewer();
          sequenceComplete = false;

          await sleep(100);
        }
      } finally {
        walkthroughInProgress = false;
      }
    };

    const startWalkthrough = () => {
      if (!hasBuilderCard || document.hidden) return;
      running = true;
      runProteinWalkthrough();
    };

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        running = false;
        clearViewer();
        return;
      }
      startWalkthrough();
    });

    window.addEventListener('focus', startWalkthrough);

    startWalkthrough();

    window.addEventListener('resize', syncViewerSize);
  } catch (error) {
    console.log('Use-cases 3D viewer failed to initialize:', error);
  }
});
