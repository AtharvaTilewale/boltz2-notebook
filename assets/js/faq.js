document.addEventListener('DOMContentLoaded', () => {
  const faqGrid = document.querySelector('[data-faq-grid]');
  if (!faqGrid) return;

  const faqCategoryBar = document.getElementById('faqCategoryBar');
  const faqSearchForm = document.getElementById('faqSearchForm');
  const faqSearchInput = document.getElementById('faqSearchInput');
  const faqResetButton = document.getElementById('faqResetButton');
  const faqResultCount = document.getElementById('faqResultCount');
  const faqEmptyState = document.getElementById('faqEmptyState');

  const faqItems = [
    {
      category: 'General',
      source: 'Root README',
      question: 'Do I need a local GPU or CUDA installation?',
      answer: 'No. The notebooks are designed around Google Colab, so you can run the main workflow without managing a local CUDA setup.'
    },
    {
      category: 'General',
      source: 'Root README',
      question: 'Which notebook should I start with?',
      answer: 'Use the main notebook for general predictions, V1 for the stable workflow, V2 for advanced modeling, and Batch when you want to process many jobs.'
    },
    {
      category: 'General',
      source: 'Version table',
      question: 'What is the difference between the latest notebook and the release-specific notebooks?',
      answer: 'The latest notebook is the current default entry point, while the release-specific notebooks document the stable V1 workflow, the V2 beta feature set, and the batch automation flow.'
    },
    {
      category: 'Inputs',
      source: 'Root README',
      question: 'What can I predict in the main notebook?',
      answer: 'The core workflow supports protein structures, multi-chain complexes, protein-ligand systems, confidence analysis, and affinity-oriented outputs.'
    },
    {
      category: 'Inputs',
      source: 'Root README',
      question: 'Can I work with ligands and binding partners?',
      answer: 'Yes. The repository includes ligand-bound workflows and binder-aware inputs so you can model protein-ligand interactions and inspect affinity-linked results.'
    },
    {
      category: 'Inputs',
      source: 'V2 changelog',
      question: 'Does V2 support DNA and RNA?',
      answer: 'Yes. V2 extends the modeling stack to DNA and RNA chains alongside proteins and ligands.'
    },
    {
      category: 'Inputs',
      source: 'V2 changelog',
      question: 'Can I upload a template structure?',
      answer: 'Yes. V2 adds template upload support for PDB and CIF files, along with explicit chain mapping for template-guided jobs.'
    },
    {
      category: 'Inputs',
      source: 'V2 changelog',
      question: 'Can I provide a custom MSA?',
      answer: 'Yes. V2 supports custom or precomputed MSA uploads in addition to the default server-assisted flow.'
    },
    {
      category: 'Inputs',
      source: 'V2 changelog',
      question: 'Are cyclic polymers and modified residues supported?',
      answer: 'Yes. V2 includes cyclic polymer support and a modified residue editor for more advanced modeling cases.'
    },
    {
      category: 'Analysis',
      source: 'Root README',
      question: 'What outputs will I get after a prediction?',
      answer: 'You can expect predicted structures, confidence metrics such as pLDDT and PAE, affinity-oriented outputs where applicable, and exportable artifacts for later analysis.'
    },
    {
      category: 'Analysis',
      source: 'Root README',
      question: 'How are pLDDT and PAE used?',
      answer: 'pLDDT summarizes per-residue confidence, while PAE shows expected alignment error between residues. Together they help you judge whether a structure is trustworthy and where uncertainty is concentrated.'
    },
    {
      category: 'Analysis',
      source: 'Root README',
      question: 'Does the notebook include visualization tools?',
      answer: 'Yes. The project is built around interactive inspection and structure review so you can visualize predictions instead of only reading raw output files.'
    },
    {
      category: 'Analysis',
      source: 'Root README',
      question: 'How should I interpret low-confidence regions?',
      answer: 'Regions with low pLDDT or high PAE often correspond to flexible loops, poorly constrained termini, or interfaces that need extra validation.'
    },
    {
      category: 'Analysis',
      source: 'Root README',
      question: 'Can I compare multiple candidate predictions?',
      answer: 'Yes. The workflow is designed for side-by-side review so you can compare confidence, affinity, and structural consistency across candidate models.'
    },
    {
      category: 'Batch',
      source: 'Batch README',
      question: 'What is the Batch notebook for?',
      answer: 'The Batch notebook is for high-throughput screening. It automates many jobs, ranks results, and helps you manage large sets of protein or protein-ligand predictions.'
    },
    {
      category: 'Batch',
      source: 'Batch README',
      question: 'What batch input modes are supported?',
      answer: 'Batch supports CSV, FASTA, YAML ZIP bundles, and YAML folder workflows so you can choose the input style that matches your data source.'
    },
    {
      category: 'Batch',
      source: 'Batch README',
      question: 'Which batch run profiles are available?',
      answer: 'The batch workflow includes Fast, Balanced, and Scientific profiles, letting you trade off speed and quality depending on the use case.'
    },
    {
      category: 'Batch',
      source: 'Batch README',
      question: 'Can Batch resume interrupted runs?',
      answer: 'Yes. The batch workflow is designed to launch new sessions or resume interrupted jobs, which is useful when you are processing many inputs.'
    },
    {
      category: 'Batch',
      source: 'Batch README',
      question: 'Can I export batch results and logs?',
      answer: 'Yes. Batch is built to package predictions, logs, manifests, and related artifacts into downloadable archives and optional Drive exports.'
    },
    {
      category: 'Batch',
      source: 'Batch README',
      question: 'How does batch ranking work?',
      answer: 'The batch workflow can rank jobs using confidence, affinity probability, and related metrics so you can focus on the strongest predictions first.'
    },
    {
      category: 'Batch',
      source: 'Batch README',
      question: 'What should I use for high-throughput screening?',
      answer: 'Use CSV or YAML-based batch manifests, start with the Balanced profile for production-like tests, and switch to Fast when you only need a quick pass.'
    },
    {
      category: 'Technical',
      source: 'V2 changelog',
      question: 'Does V2 support covalent bond and pocket builders?',
      answer: 'Yes. V2 adds covalent ligand bond and pocket conditioning support, which is useful for more structured design problems.'
    },
    {
      category: 'Technical',
      source: 'V2 changelog',
      question: 'Can I define contact constraints between chains?',
      answer: 'Yes. The advanced V2 workflow includes contact conditioning so you can bias interactions between specific residues or chains.'
    },
    {
      category: 'Technical',
      source: 'V2 changelog',
      question: 'Can I use the modified residue editor for PTMs?',
      answer: 'Yes. The modified residue editor is intended for post-translational modifications and other residue-level chemistry changes.'
    },
    {
      category: 'Technical',
      source: 'Batch README',
      question: 'What output formats are available?',
      answer: 'The batch workflow supports PDB, MMCIF, and CIF output selection so you can match downstream tooling and archive preferences.'
    },
    {
      category: 'Technical',
      source: 'Batch README',
      question: 'How do I handle multi-chain proteins in batch mode?',
      answer: 'Multi-chain proteins are represented with colon-separated sequences, which the batch manifest builder can translate into the appropriate job structure.'
    },
    {
      category: 'Technical',
      source: 'Batch README',
      question: 'Can I skip completed jobs or retry failed ones?',
      answer: 'Yes. The batch workflow includes job filtering options so you can skip completed items or retry failed jobs during follow-up runs.'
    },
    {
      category: 'Technical',
      source: 'Root README',
      question: 'Does the project support Drive integration?',
      answer: 'Yes. Drive export is part of the workflow so you can keep outputs and archives in persistent cloud storage.'
    },
    {
      category: 'Technical',
      source: 'Root README',
      question: 'What runtime should I use for best results?',
      answer: 'A GPU runtime such as a T4 in Google Colab is the recommended starting point for the notebook workflows.'
    },
    {
      category: 'Access',
      source: 'Root README',
      question: 'Is this project open source?',
      answer: 'Yes. The repository is published under the MIT License so you can review, reuse, and adapt the code within the license terms.'
    },
    {
      category: 'Access',
      source: 'Root README',
      question: 'Can I run everything from Google Colab?',
      answer: 'Yes. The notebooks are organized around Google Colab so you can launch them without local environment setup.'
    }
  ];

  const categories = ['All', ...new Set(faqItems.map((item) => item.category))];
  let activeCategory = 'All';

  const renderFaqs = () => {
    faqGrid.innerHTML = '';

    faqItems.forEach((item) => {
      const details = document.createElement('details');
      details.className = 'faq-item';
      details.dataset.faqItem = 'true';
      details.dataset.category = item.category.toLowerCase();
      details.dataset.searchText = [item.question, item.answer, item.category, item.source].join(' ').toLowerCase();

      const summary = document.createElement('summary');
      summary.textContent = item.question;

      const answer = document.createElement('p');
      answer.textContent = item.answer;

      const tags = document.createElement('div');
      tags.className = 'faq-tags';

      [item.category, item.source].forEach((label) => {
        const tag = document.createElement('span');
        tag.textContent = label;
        tags.appendChild(tag);
      });

      details.append(summary, answer, tags);
      faqGrid.appendChild(details);
    });
  };

  const renderCategories = () => {
    if (!faqCategoryBar) return;

    faqCategoryBar.innerHTML = '';
    categories.forEach((category) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'faq-category-chip';
      button.textContent = category;
      button.dataset.category = category;
      button.setAttribute('aria-pressed', String(category === activeCategory));

      if (category === activeCategory) {
        button.classList.add('active');
      }

      button.addEventListener('click', () => {
        activeCategory = category;
        faqCategoryBar.querySelectorAll('button').forEach((chip) => {
          const isActive = chip.dataset.category === activeCategory;
          chip.classList.toggle('active', isActive);
          chip.setAttribute('aria-pressed', String(isActive));
        });
        updateVisibility(faqSearchInput ? faqSearchInput.value : '');
      });

      faqCategoryBar.appendChild(button);
    });
  };

  const updateVisibility = (query) => {
    const normalizedQuery = query.trim().toLowerCase();
    const items = Array.from(faqGrid.querySelectorAll('[data-faq-item]'));
    let visibleCount = 0;

    items.forEach((item) => {
      const matchesCategory = activeCategory === 'All' || item.dataset.category === activeCategory.toLowerCase();
      const matchesQuery = !normalizedQuery || (item.dataset.searchText || '').includes(normalizedQuery);
      const matches = matchesCategory && matchesQuery;
      item.hidden = !matches;
      if (matches) {
        visibleCount += 1;
      }
    });

    if (faqResultCount) {
      faqResultCount.textContent = `${visibleCount} FAQ${visibleCount === 1 ? '' : 's'} shown`;
    }

    if (faqEmptyState) {
      faqEmptyState.hidden = visibleCount > 0;
    }
  };

  renderFaqs();
  renderCategories();

  const initialQuery = new URLSearchParams(window.location.search).get('q') || '';
  if (faqSearchInput) {
    faqSearchInput.value = initialQuery;
  }

  updateVisibility(initialQuery);

  if (faqSearchForm) {
    faqSearchForm.addEventListener('submit', (event) => {
      event.preventDefault();
      updateVisibility(faqSearchInput ? faqSearchInput.value : '');
    });
  }

  if (faqSearchInput) {
    faqSearchInput.addEventListener('input', () => {
      updateVisibility(faqSearchInput.value);
    });
  }

  if (faqResetButton) {
    faqResetButton.addEventListener('click', () => {
      if (faqSearchInput) {
        faqSearchInput.value = '';
        faqSearchInput.focus();
      }
      activeCategory = 'All';
      renderCategories();
      updateVisibility('');
    });
  }
});
