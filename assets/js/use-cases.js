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
    const extractProteinPdb = (pdbData, allowedChains = ['A', 'B']) => pdbData
      .split(/\r?\n/)
      .filter((line) => line.startsWith('ATOM') && allowedChains.includes(line.slice(21, 22)))
      .join('\n');

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
        viewer.setStyle({ hetflag: true }, { hidden: true });
      } else {
        viewer.setStyle({ hetflag: false, chain: 'A' }, { cartoon: { color: '#66b7ff' } });
        viewer.setStyle({ hetflag: false, chain: 'B' }, { cartoon: { color: '#ff9f43' } });
        viewer.setStyle({ hetflag: true }, { hidden: true });
      }

      if (mode === 'complex') {
        viewer.setStyle({ hetflag: true }, { hidden: false });
        viewer.setStyle({ hetflag: true, chain: 'C' }, { stick: { radius: 0.22, color: '#7be0d3' } });
        viewer.setStyle({ hetflag: true, chain: 'D' }, { stick: { radius: 0.22, color: '#ffd166' } });
      }

      viewer.zoomTo();
      viewer.render();
    };

    setStaticFields();

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        running = false;
      }
    });
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
    let ulvanLyasePdb = null;
    let sequenceComplete = false;

    const renderCurrentScene = () => {
      if (!ulvanLyasePdb || typeof renderProtein !== 'function') return;

      renderProtein(viewer, ulvanLyasePdb, currentScene);

      const surfaceOpacity = 0.2;
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
        viewer.spin('y', 0.04);
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
      if (!ulvanLyasePdb) return;

      clearViewer();
      renderCurrentScene();
    };

    const loadUlvanLyase = fetch('https://files.rcsb.org/download/6D3U.pdb')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.text();
      })
      .then((pdbData) => {
        ulvanLyasePdb = pdbData;
        if (sequenceComplete) {
          renderUlvanLyase(currentScene);
        }
        return pdbData;
      });

    loadUlvanLyase.catch(() => {
      clearViewer();
      viewer.addModel('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C  ', 'pdb');
      viewer.setStyle({}, { sphere: { radius: 1.2, color: '#66b7ff' } });
      viewer.zoomTo();
      viewer.render();
    });

    const runProteinWalkthrough = async () => {
      scenarioLabel.textContent = 'Protein + ligand walkthrough';
      setStaticFields();
      setActiveRow('id');

      await sleep(250);
      await typewriter(fieldId, 'A', 45);

      await sleep(300);
      setActiveRow('sequence');
      await typewriter(fieldSequence, 'MSEQNNTEMTFQIQRIYTKDISFEAPNAPHVFQ', 22);
      sequenceComplete = true;

      renderUlvanLyase('chain-a');

      await sleep(700);
      setActiveRow('id');
      await appendWriter(fieldId, ', B', 55);

      renderUlvanLyase('chain-ab');

      await sleep(1500);
      setActiveRow('ligandOption');
      await typewriter(fieldLigandOption, 'OC[C@@H](O1)[C@@H](O)', 26);

      renderUlvanLyase('complex');

      await sleep(1500);
      setActiveRow('dna');
      await typewriter(fieldDna, 'ATGCGTACCTGATTGATAGAGCCGCGGC', 26);

      await sleep(5000);
      clearAllFields();
      clearViewer();
      sequenceComplete = false;

      await sleep(100);
      if (running) {
        runProteinWalkthrough();
      }
    };

    runProteinWalkthrough();

    window.addEventListener('resize', syncViewerSize);
  } catch (error) {
    console.log('Use-cases 3D viewer failed to initialize:', error);
  }
});
