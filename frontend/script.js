console.log('App initializing...');

const RATIOS = [
    { label: '方图 1:1', value: '1:1', width: 1, height: 1 },
    { label: '横屏 4:3', value: '4:3', width: 4, height: 3 },
    { label: '竖屏 3:4', value: '3:4', width: 3, height: 4 },
    { label: '宽屏 16:9', value: '16:9', width: 16, height: 9 },
    { label: '竖屏 9:16', value: '9:16', width: 9, height: 16 },
];

class App {
    constructor() {
        this.currentMode = 'txt2img';
        this.selectedRatio = RATIOS[1]; // Default to 4:3 (Horizontal)
        this.selectedScenario = 'free_mode';
        this.uploadedImages = [];
        this.activeImageIndex = -1;
        this.uploadedImage = null;
        this.canvas = null;
        this.ctx = null;
        this.isDrawing = false;
        this.history = [];

        this.loadHistory();
        this.initTabs();
        this.initRatios();
        this.initScenario();
        this.initUpload();
        this.initGeneration();
        this.renderHistory();
    }

    loadHistory() {
        const saved = localStorage.getItem('img_history');
        if (saved) {
            try {
                this.history = JSON.parse(saved);
            } catch (e) {
                console.error('Failed to load history', e);
            }
        }
    }

    addToHistory(data) {
        const item = {
            id: Date.now().toString(),
            url: data.url,
            prompt: data.prompt,
            optimizedPrompt: data.optimizedPrompt,
            originalImages: data.originalImages || [],
            timestamp: Date.now()
        };
        this.history.unshift(item);

        // Hard limit first
        if (this.history.length > 20) {
            this.history = this.history.slice(0, 20);
        }

        this.saveHistory();
    }

    saveHistory() {
        try {
            localStorage.setItem('img_history', JSON.stringify(this.history));
        } catch (e) {
            if (e.name === 'QuotaExceededError' || e.code === 22 || e.code === 1014) {
                console.warn('LocalStorage quota exceeded. Trimming history...');
                // Remove oldest items until it fits or is empty
                while (this.history.length > 0) {
                    this.history.pop(); // Remove last
                    try {
                        localStorage.setItem('img_history', JSON.stringify(this.history));
                        // If success, break
                        break;
                    } catch (e2) {
                        // Continue trimming
                    }
                }
                this.renderHistory();
            } else {
                console.error('Failed to save history', e);
            }
        }
        this.renderHistory();
    }

    renderHistory() {
        const container = document.getElementById('history-list');
        if (!container) return;

        if (this.history.length === 0) {
            container.innerHTML = '<div class="history-empty">你的生成历史将显示在这里</div>';
            return;
        }

        container.innerHTML = this.history.map(item => `
      <div class="history-item" data-id="${item.id}">
        <img src="${item.url}" alt="Generated Image">
      </div>
    `).join('');

        container.querySelectorAll('.history-item').forEach(el => {
            el.addEventListener('click', () => {
                const id = el.dataset.id;
                const item = this.history.find(i => i.id === id);
                if (item) this.openModal(item);
            });
        });
    }

    openModal(item) {
        const modal = document.getElementById('image-modal');
        const modalImg = document.getElementById('modal-image');
        const modalPrompt = document.getElementById('modal-prompt');
        const modalOptimized = document.getElementById('modal-optimized-prompt');
        const modalOriginalGroup = document.getElementById('modal-original-image-group');
        const modalOriginalImg = document.getElementById('modal-original-image');
        const closeBtn = document.querySelector('.close-modal');

        if (!modal) return;

        modalImg.src = item.url;
        modalPrompt.textContent = item.prompt || '无';
        modalOptimized.textContent = item.optimizedPrompt || '无';

        if (item.originalImages && item.originalImages.length > 0) {
            modalOriginalGroup.classList.remove('hidden');
            modalOriginalImg.classList.add('hidden'); // Hide single img if exists

            // Create or update gallery in modal
            let gallery = modalOriginalGroup.querySelector('.modal-original-gallery');
            if (!gallery) {
                gallery = document.createElement('div');
                gallery.className = 'modal-original-gallery';
                modalOriginalGroup.appendChild(gallery);
            }

            gallery.innerHTML = item.originalImages.map(src => `
                <img src="${src}" class="modal-gallery-thumb" onclick="window.open('${src}', '_blank')">
            `).join('');
        } else {
            modalOriginalGroup.classList.add('hidden');
        }

        modal.classList.remove('hidden');

        // Enable zoom for modal image
        this.enableZoomPan(modalImg, document.querySelector('.modal-image-container'));

        const close = () => {
            modal.classList.add('hidden');
            // Reset zoom
            modalImg.style.transform = 'translate(0px, 0px) scale(1)';
        };

        closeBtn.onclick = close;
        modal.onclick = (e) => {
            if (e.target === modal) close();
        };
    }

    enableZoomPan(imgElement, containerElement) {
        let scale = 1;
        let panning = false;
        let pointX = 0;
        let pointY = 0;
        let startX = 0;
        let startY = 0;

        // Reset transform
        imgElement.style.transform = 'translate(0px, 0px) scale(1)';

        const setTransform = () => {
            imgElement.style.transform = `translate(${pointX}px, ${pointY}px) scale(${scale})`;
        };

        containerElement.onwheel = (e) => {
            e.preventDefault();
            const delta = -e.deltaY;
            (delta > 0) ? (scale *= 1.1) : (scale /= 1.1);
            scale = Math.min(Math.max(0.5, scale), 5);
            setTransform();
        };

        imgElement.onmousedown = (e) => {
            e.preventDefault();
            startX = e.clientX - pointX;
            startY = e.clientY - pointY;
            panning = true;
        };

        document.onmouseup = (e) => {
            panning = false;
        };

        document.onmousemove = (e) => {
            if (!panning) return;
            e.preventDefault();
            pointX = e.clientX - startX;
            pointY = e.clientY - startY;
            setTransform();
        };
    }

    showPreview(url) {
        const container = document.getElementById('preview-container');
        if (container) {
            container.innerHTML = `<img src="${url}" style="max-width: 100%; max-height: 100%; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">`;

            // Enable zoom for preview
            const img = container.querySelector('img');
            this.enableZoomPan(img, container);
        }
    }

    initTabs() {
        const btnModify = document.getElementById('btn-img-modify');
        const btnTxt = document.getElementById('btn-txt2img');
        const btnImg = document.getElementById('btn-img2img');
        const groupImage = document.getElementById('group-image');
        const groupScenario = document.getElementById('group-scenario');

        const setMode = (mode) => {
            this.currentMode = mode;
            // Reset all active states
            btnModify?.classList.remove('active');
            btnTxt?.classList.remove('active');
            btnImg?.classList.remove('active');

            if (mode === 'txt2img') {
                btnTxt?.classList.add('active');
                groupImage?.classList.add('hidden');
                groupScenario?.classList.remove('hidden');
            } else if (mode === 'img2img') {
                btnImg?.classList.add('active');
                groupImage?.classList.remove('hidden');
                groupScenario?.classList.remove('hidden');
            } else if (mode === 'img_modify') {
                btnModify?.classList.add('active');
                groupImage?.classList.remove('hidden');
                groupScenario?.classList.add('hidden');
            }
        };

        btnTxt?.addEventListener('click', () => setMode('txt2img'));
        btnImg?.addEventListener('click', () => setMode('img2img'));
        btnModify?.addEventListener('click', () => setMode('img_modify'));

        // Auto-switch mode based on model selection
        const modelSelect = document.getElementById('model-select');
        modelSelect?.addEventListener('change', () => {
            if (modelSelect.value === 'doubao_seededit') {
                setMode('img_modify');
            }
        });
    }

    initRatios() {
        const grid = document.getElementById('ratio-grid');
        grid.innerHTML = RATIOS.map(r => `
            <div class="ratio-btn ${r.value === this.selectedRatio.value ? 'active' : ''}" data-value="${r.value}">
                <div class="ratio-preview" style="width: ${r.width * 4}px; height: ${r.height * 4}px"></div>
                <span>${r.label}</span>
            </div>
        `).join('');

        grid.querySelectorAll('.ratio-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                grid.querySelectorAll('.ratio-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.selectedRatio = RATIOS.find(r => r.value === btn.dataset.value);
            });
        });
    }

    initScenario() {
        const mainBtns = document.querySelectorAll('.scenario-selector > .scenario-btn:not(.sub-btn)');
        const subContainer = document.getElementById('sub-scenario-container');
        const subBtns = subContainer.querySelectorAll('.sub-btn');

        // Default
        this.selectedScenario = 'free_mode';

        mainBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.currentTarget;
                const val = target.dataset.value;

                mainBtns.forEach(b => b.classList.remove('active'));
                target.classList.add('active');

                if (val === 'ecommerce') {
                    subContainer.classList.remove('hidden');
                    // Default to the active sub-button or the first one
                    const activeSub = subContainer.querySelector('.sub-btn.active') || subBtns[0];
                    this.selectedScenario = activeSub.dataset.value;
                    // Ensure visual state matches
                    subBtns.forEach(b => b.classList.remove('active'));
                    activeSub.classList.add('active');
                } else {
                    subContainer.classList.add('hidden');
                    this.selectedScenario = val;
                }
            });
        });

        subBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.currentTarget;
                subBtns.forEach(b => b.classList.remove('active'));
                target.classList.add('active');
                this.selectedScenario = target.dataset.value;
            });
        });
    }

    initUpload() {
        const dropZone = document.getElementById('upload-zone');
        const fileInput = document.getElementById('file-input');
        const gallery = document.getElementById('upload-gallery');

        if (!dropZone || !fileInput) return;

        dropZone.addEventListener('click', () => fileInput.click());

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = 'var(--primary)';
        });

        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = 'var(--border)';
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = 'var(--border)';
            const files = e.dataTransfer.files;
            if (files.length) this.handleFiles(files);
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) this.handleFiles(e.target.files);
        });
    }

    handleFiles(files) {
        const gallery = document.getElementById('upload-gallery');
        gallery.classList.remove('hidden');

        Array.from(files).forEach(file => {
            if (!file.type.startsWith('image/')) return;

            const reader = new FileReader();
            reader.onload = (e) => {
                this.uploadedImages.push(e.target.result);
                this.renderGallery();
                // Select the last one by default
                this.selectImage(this.uploadedImages.length - 1);
            };
            reader.readAsDataURL(file);
        });
    }

    renderGallery() {
        const gallery = document.getElementById('upload-gallery');
        if (!gallery) return;

        gallery.innerHTML = this.uploadedImages.map((src, idx) => `
            <div class="gallery-item ${idx === this.activeImageIndex ? 'active' : ''}" onclick="app.selectImage(${idx})">
                <img src="${src}">
                <div class="delete-btn" onclick="event.stopPropagation(); app.deleteImage(${idx})">×</div>
            </div>
        `).join('');
    }

    deleteImage(index) {
        this.uploadedImages.splice(index, 1);

        if (this.uploadedImages.length === 0) {
            this.activeImageIndex = -1;
            this.uploadedImage = null;
            const dropZone = document.getElementById('upload-zone');
            if (dropZone) {
                dropZone.classList.remove('has-image');
                dropZone.style.backgroundImage = '';
            }
            const gallery = document.getElementById('upload-gallery');
            if (gallery) gallery.classList.add('hidden');
        } else {
            if (index === this.activeImageIndex) {
                // If deleting active image, select the previous one or the first one
                this.selectImage(Math.max(0, index - 1));
            } else if (index < this.activeImageIndex) {
                // If deleting an image before the active one, shift index down
                this.activeImageIndex--;
                this.renderGallery();
            } else {
                this.renderGallery();
            }
        }
    }

    selectImage(index) {
        if (index < 0 || index >= this.uploadedImages.length) return;

        this.activeImageIndex = index;
        this.uploadedImage = this.uploadedImages[index]; // Base64 string
        this.renderGallery();

        // Update dropzone preview
        const dropZone = document.getElementById('upload-zone');
        if (dropZone) {
            dropZone.classList.add('has-image');
            dropZone.style.backgroundImage = `url(${this.uploadedImage})`;
            dropZone.style.backgroundSize = 'contain';
            dropZone.style.backgroundRepeat = 'no-repeat';
            dropZone.style.backgroundPosition = 'center';
        }
    }

    async base64ToBlob(base64, type = 'image/png') {
        const response = await fetch(base64);
        return await response.blob();
    }

    initGeneration() {
        const btn = document.getElementById('generate-btn');
        const promptInput = document.getElementById('prompt-input');

        if (!btn || !promptInput) return;

        btn.addEventListener('click', async () => {
            const prompt = promptInput.value.trim();
            if (!prompt) {
                alert('请输入指令');
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '<span class="icon">⏳</span> 生成中...';

            try {
                const formData = new FormData();
                formData.append('prompt', prompt);
                formData.append('ratio', this.selectedRatio.value);
                formData.append('scenario', this.selectedScenario);

                const modelSelect = document.getElementById('model-select');
                if (modelSelect) {
                    formData.append('model', modelSelect.value);
                }

                const apiKeyInput = document.getElementById('api-key-input');
                if (apiKeyInput && apiKeyInput.value) {
                    formData.append('api_key', apiKeyInput.value);
                }

                // Send all uploaded images for multi-view analysis
                if (this.uploadedImages.length > 0) {
                    for (let i = 0; i < this.uploadedImages.length; i++) {
                        const blob = await this.base64ToBlob(this.uploadedImages[i]);
                        formData.append('image', blob, `image_${i}.png`);
                    }
                }

                // Call Backend API
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error('Generation failed');
                }

                const data = await response.json();

                this.showPreview(data.url);
                this.addToHistory({
                    url: data.url,
                    prompt: data.original_prompt || prompt,
                    optimizedPrompt: data.optimized_prompt,
                    originalImages: data.original_images || []
                });

            } catch (error) {
                console.error(error);
                alert(`生成失败: ${error.message}`);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<span class="icon">✨</span> 应用编辑';
            }
        });
    }
}

// Initialize
window.app = new App();
