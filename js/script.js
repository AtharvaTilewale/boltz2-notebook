document.addEventListener('DOMContentLoaded', () => {
    // --- Global State & API Config ---
    const apiKey = "";
    const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key=${apiKey}`;
    let viewerInstance = null;

    // --- Modal Logic ---
    const modal = document.getElementById('explanation-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const showModal = (title) => {
        modalTitle.textContent = title;
        modalBody.innerHTML = '<div class="loader"></div>';
        modal.classList.add('visible');
    };
    const hideModal = () => modal.classList.remove('visible');
    modalCloseBtn.addEventListener('click', hideModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) hideModal();
    });

    // --- Gemini API Call ---
    // async function callGemini(prompt, retries = 3, delay = 1000) {
    //     const payload = {
    //         contents: [{
    //             parts: [{
    //                 text: prompt
    //             }]
    //         }]
    //     };
    //     try {
    //         const response = await fetch(apiUrl, {
    //             method: 'POST',
    //             headers: {
    //                 'Content-Type': 'application/json'
    //             },
    //             body: JSON.stringify(payload)
    //         });
    //         if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    //         const result = await response.json();
    //         return result.candidates?.[0]?.content?.parts?.[0]?.text || "Sorry, I couldn't generate a response.";
    //     } catch (error) {
    //         if (retries > 0) {
    //             await new Promise(res => setTimeout(res, delay));
    //             return callGemini(prompt, retries - 1, delay * 2);
    //         }
    //         console.error("Error calling Gemini API:", error);
    //         return "An error occurred while fetching the explanation.";
    //     }
    // }

    // // --- Event Listeners for Gemini Buttons ---
    // document.querySelectorAll('.gemini-btn').forEach(button => {
    //     button.addEventListener('click', async () => {
    //         const topic = button.dataset.topic;
    //         const analogy = button.dataset.analogy;
    //         const prompt = `You are a helpful science communicator. Explain the concept of "${topic}" in bioinformatics using a simple, clear analogy. The analogy should be similar in spirit to this example: "${analogy}". Keep your explanation concise and easy for a non-expert to understand.`;
    //         showModal(`Explaining: ${topic}`);
    //         const explanation = await callGemini(prompt);
    //         modalBody.innerHTML = `<p>${explanation.replace(/\n/g, '<br>')}</p>`;
    //     });
    // });

    // --- Tab navigation for Demo ---
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            const targetId = button.id.replace('btn', 'content');
            tabContents.forEach(content => {
                content.classList.toggle('active', content.id === targetId);
            });
            if (targetId === 'tab-content-3d' && !viewerInstance) {
                init3DViewer();
            }
        });
    });

    // --- 3Dmol.js Viewer for Demo ---
    function init3DViewer() {
        let element = document.getElementById('mol_viewer_container');
        let config = {
            backgroundColor: 'white'
        };
        viewerInstance = $3Dmol.createViewer(element, config);

        // Fetch PDB file from assets/pdb
        fetch('assets/pdb/prot_lig.pdb')
            .then(response => response.text())
            .then(pdbData => {
                viewerInstance.addModel(pdbData, 'pdb');
                viewerInstance.setStyle({}, {
                    cartoon: {
                        colorscheme: 'chain'
                    }
                });
                viewerInstance.addStyle({hetflag: true}, {stick: {colorscheme: 'default'}});
                viewerInstance.zoomTo();
                viewerInstance.render();
            })
            .catch(err => {
                console.error('Failed to load PDB file:', err);
            });
    }
    init3DViewer(); // Initialize on load

    // --- Chart.js Instances ---
    const createChart = (canvasId, type, data, options) => {
        const ctx = document.getElementById(canvasId).getContext('2d');
        new Chart(ctx, {
            type,
            data,
            options
        });
    };

    const plddtData = {
        labels: Array.from({ length: 150 }, (_, i) => i + 1),
        datasets: [{
            label: 'pLDDT Score',
            data: Array.from({ length: 150 }, (_, i) => (i > 30 && i < 120) ? 85 + Math.sin(i / 10) * 8 + Math.random() * 5 : 40 + Math.random() * 20),
            borderColor: '#0ea5e9',
            backgroundColor: 'rgba(14, 165, 233, 0.1)',
            fill: true,
            pointRadius: 0,
            tension: 0.4,
            borderWidth: 2
        }]
    };
    const plddtOptions = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true,
                max: 100,
                title: {
                    display: true,
                    text: 'Confidence (0-100)'
                }
            },
            x: {
                title: {
                    display: true,
                    text: 'Residue Index'
                }
            }
        },
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                callbacks: {
                    label: (ctx) => `Residue ${ctx.label}: ${ctx.parsed.y.toFixed(1)} pLDDT`
                }
            }
        }
    };
    createChart('plddtChartDemo', 'line', plddtData, plddtOptions);

    const paePoints = [];
    const size = 20;
    for (let i = 0; i < size; i++) {
        for (let j = 0; j < size; j++) {
            const error = Math.abs(i - j) < 3 ? Math.random() * 2 : 2 + (Math.sqrt(Math.pow(i - size / 2, 2) + Math.pow(j - size / 2, 2)) / size) * 20 + Math.random() * 5;
            paePoints.push({
                x: i,
                y: j,
                v: error
            });
        }
    }
    const paeData = {
        datasets: [{
            label: 'PAE (Å)',
            data: paePoints.map(p => ({
                x: p.x,
                y: p.y,
                r: 5
            })),
            backgroundColor: paePoints.map(p => `rgba(15, 118, 110, ${Math.max(0.1, 1 - (p.v / 25))})`)
        }]
    };
    const paeOptions = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true,
                grace: '5%',
                title: {
                    display: true,
                    text: 'Residue Index'
                }
            },
            x: {
                beginAtZero: true,
                grace: '5%',
                title: {
                    display: true,
                    text: 'Residue Index'
                }
            }
        },
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                callbacks: {
                    label: (ctx) => `Error between residue ${paePoints[ctx.dataIndex].x} & ${paePoints[ctx.dataIndex].y}: ${paePoints[ctx.dataIndex].v.toFixed(1)} Å`
                }
            }
        }
    };
    createChart('paeChartDemo', 'bubble', paeData, paeOptions);

    // --- Citation copy ---
    window.copyToClipboard = (elementId) => {
        const textToCopy = document.querySelector(`#${elementId} p`).textContent;
        navigator.clipboard.writeText(textToCopy);
        const feedback = document.getElementById(`${elementId}-feedback`);
        feedback.style.opacity = '1';
        setTimeout(() => {
            feedback.style.opacity = '0';
        }, 2000);
    };
    // --- Scroll Animations ---
    const animatedSections = document.querySelectorAll('.animated-section');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, {
        threshold: 0.1
    });
    animatedSections.forEach(section => {
        observer.observe(section);
    });
});