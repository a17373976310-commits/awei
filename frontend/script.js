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
        this.logs = [];
        this.currentController = null;  // 添加: 跟踪当前任务的AbortController
        this.currentTimerInterval = null;  // 添加: 跟踪当前计时器

        this.loadHistory();
        this.initTabs();
        this.initRatios();
        this.initScenario();
        this.initUpload();
        this.initGeneration();
        this.initCancelButton();  // 添加: 初始化取消按钮
        this.initHistory();
        this.renderHistory();
        this.initLogPanel();
    }

    loadHistory() {
        const saved = localStorage.getItem('banana_history');
        if (saved) {
            try {
                this.history = JSON.parse(saved).slice(0, 4);
            } catch (e) {
                console.error('Failed to load history', e);
                this.history = [];
            }
        }
    }

    addToHistory(item) {
        if (!item) return;

        // Ensure item has an ID
        if (!item.id) {
            item.id = item.timestamp || Date.now().toString();
        }

        // Avoid duplicates
        if (this.history.find(h => h.id === item.id)) return;

        this.history.unshift(item);
        // Limit history to 4 items
        if (this.history.length > 4) this.history = this.history.slice(0, 4);

        this.saveHistory();
        this.renderHistory();
    }

    saveHistory() {
        try {
            localStorage.setItem('banana_history', JSON.stringify(this.history));
        } catch (e) {
            if (e.name === 'QuotaExceededError' || e.code === 22 || e.code === 1014) {
                console.warn('LocalStorage quota exceeded. Trimming history...');
                while (this.history.length > 0) {
                    this.history.pop();
                    try {
                        localStorage.setItem('banana_history', JSON.stringify(this.history));
                        break;
                    } catch (e2) { }
                }
            } else {
                console.error('Failed to save history', e);
            }
        }
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
                <img src="${item.url}" alt="Generated Image" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><rect width=%22100%22 height=%22100%22 fill=%22%23333%22/><text x=%2250%%22 y=%2250%%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 fill=%22%23666%22 font-size=%2212%22>加载失败</text></svg>'">
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
        modalPrompt.textContent = item.original_prompt || item.prompt || '无';
        modalOptimized.textContent = item.optimized_prompt || item.optimizedPrompt || '无';

        if (item.original_images && item.original_images.length > 0) {
            modalOriginalGroup.classList.remove('hidden');
            modalOriginalImg.classList.add('hidden');

            let gallery = modalOriginalGroup.querySelector('.modal-original-gallery');
            if (!gallery) {
                gallery = document.createElement('div');
                gallery.className = 'modal-original-gallery';
                modalOriginalGroup.appendChild(gallery);
            }

            gallery.innerHTML = item.original_images.map(src => `
                <img src="${src}" class="modal-gallery-thumb" onclick="window.open('${src}', '_blank')">
            `).join('');
        } else {
            modalOriginalGroup.classList.add('hidden');
        }

        modal.classList.remove('hidden');
        this.enableZoomPan(modalImg, document.querySelector('.modal-image-container'));

        const close = () => {
            modal.classList.add('hidden');
            modalImg.style.transform = 'translate(0px, 0px) scale(1)';
        };

        closeBtn.onclick = close;
        modal.onclick = (e) => {
            if (e.target === modal) close();
        };
    }

    enableZoomPan(imgElement, containerElement) {
        if (!imgElement || !containerElement) return;

        let scale = 1;
        let panning = false;
        let pointX = 0;
        let pointY = 0;
        let startX = 0;
        let startY = 0;

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

        document.onmouseup = () => {
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
            if (!url) {
                container.innerHTML = '<div style="color: #ff4d4d; padding: 20px;">未找到图像 URL</div>';
                return;
            }
            container.innerHTML = `<img src="${url}" style="max-width: 100%; max-height: 100%; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);" onerror="this.onerror=null; this.src=''; this.parentElement.innerHTML='<div style=\'color: #ff4d4d; padding: 20px;\'>图像加载失败，请检查网络或刷新页面</div>';">`;
            const img = container.querySelector('img');
            if (img) {
                this.enableZoomPan(img, container);
            }
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

        const modelSelect = document.getElementById('model-select');
        modelSelect?.addEventListener('change', () => {
            if (modelSelect.value === 'doubao_seededit') {
                setMode('img_modify');
            }
        });
    }

    initRatios() {
        const grid = document.getElementById('ratio-grid');
        if (!grid) return;
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
        const subBtns = subContainer?.querySelectorAll('.sub-btn');

        this.selectedScenario = 'free_mode';

        mainBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.currentTarget;
                const val = target.dataset.value;

                mainBtns.forEach(b => b.classList.remove('active'));
                target.classList.add('active');

                if (val === 'ecommerce') {
                    subContainer?.classList.remove('hidden');
                    const activeSub = subContainer?.querySelector('.sub-btn.active') || subBtns?.[0];
                    if (activeSub) {
                        this.selectedScenario = activeSub.dataset.value;
                        subBtns?.forEach(b => b.classList.remove('active'));
                        activeSub.classList.add('active');
                    }
                } else {
                    subContainer?.classList.add('hidden');
                    this.selectedScenario = val;
                }
            });
        });

        subBtns?.forEach(btn => {
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
        gallery?.classList.remove('hidden');

        Array.from(files).forEach(file => {
            if (!file.type.startsWith('image/')) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                this.uploadedImages.push(e.target.result);
                this.renderGallery();
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
            document.getElementById('upload-gallery')?.classList.add('hidden');
        } else {
            this.selectImage(Math.max(0, index - 1));
        }
    }

    selectImage(index) {
        if (index < 0 || index >= this.uploadedImages.length) return;
        this.activeImageIndex = index;
        this.uploadedImage = this.uploadedImages[index];
        this.renderGallery();
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

            const modelSelect = document.getElementById('model-select');
            const modelName = modelSelect ? modelSelect.options[modelSelect.selectedIndex].text : '未知模型';
            const scenarioMap = {
                'free_mode': '通用模式',
                'taobao_main': '淘宝主图',
                'taobao_detail': '淘宝详情页',
                'taobao_detail_suite': '整套详情页',
                'brand_story': '品牌故事',
                'creative_poster': '创意海报',
                'amazon_white': '亚马逊白底',
                'amazon_detail': '亚马逊A+',
                'image_modify': '图像修改'
            };
            const scenarioName = scenarioMap[this.selectedScenario] || this.selectedScenario;
            this.addLog('info', '🚀 开始生成任务', {
                '模型': modelName,
                '场景': scenarioName,
                '尺寸': this.selectedRatio.value,
                '图片数量': this.uploadedImages.length > 0 ? `${this.uploadedImages.length} 张` : '无'
            });

            btn.disabled = true;
            let elapsedSeconds = 0;
            const updateButton = () => {
                const minutes = Math.floor(elapsedSeconds / 60);
                const seconds = elapsedSeconds % 60;
                const timeStr = minutes > 0 ? `${minutes}分${seconds}秒` : `${seconds}秒`;
                btn.innerHTML = `<span class="icon">⏳</span> 生成中... (${timeStr})`;
            };
            updateButton();
            const timerInterval = setInterval(() => {
                elapsedSeconds++;
                updateButton();
            }, 1000);
            this.currentTimerInterval = timerInterval;

            const controller = new AbortController();
            this.currentController = controller;
            const timeoutId = setTimeout(() => controller.abort(), 600000); // 10 minutes

            // 显示取消按钮
            const cancelBtn = document.getElementById('cancel-btn');
            if (cancelBtn) cancelBtn.classList.remove('hidden');

            try {
                const formData = new FormData();
                formData.append('prompt', prompt);
                formData.append('ratio', this.selectedRatio.value);
                formData.append('scenario', this.selectedScenario);
                if (modelSelect) formData.append('model', modelSelect.value);
                const apiKeyInput = document.getElementById('api-key-input');
                if (apiKeyInput?.value) formData.append('api_key', apiKeyInput.value);

                const apiUrlInput = document.getElementById('api-url-input');
                if (apiUrlInput?.value) formData.append('api_url', apiUrlInput.value);

                if (this.uploadedImages.length > 0) {
                    for (let i = 0; i < this.uploadedImages.length; i++) {
                        const blob = await this.base64ToBlob(this.uploadedImages[i]);
                        formData.append('image', blob, `image_${i}.png`);
                    }
                }

                const response = await fetch('/api/generate', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Submission failed: ${errorText}`);
                }

                const submitData = await response.json();
                const result = await this.pollTaskStatus(submitData.task_id, controller.signal);

                const minutes = Math.floor(elapsedSeconds / 60);
                const seconds = elapsedSeconds % 60;
                const timeStr = minutes > 0 ? `${minutes}分${seconds}秒` : `${seconds}秒`;
                this.addLog('success', '✨ 图像生成成功', {
                    '耗时': timeStr,
                    '图片URL': result.url ? '已生成' : '无'
                });
                this.showPreview(result.url);
                this.addToHistory(result);

            } catch (error) {
                console.error(error);
                const msg = error.name === 'AbortError' ? '⏱️ 生成超时 (10分钟)' : error.message;
                this.addLog('error', '❌ 生成失败', {
                    '原因': msg,
                    '建议': error.name === 'AbortError' ? '图片生成时间较长,请稍后重试' : '请检查网络连接或联系管理员'
                });
                alert(`生成失败: ${msg}`);
            } finally {
                clearInterval(timerInterval);
                clearTimeout(timeoutId);
                btn.disabled = false;
                btn.innerHTML = '<span class="icon">✨</span> 应用编辑';

                // 隐藏取消按钮并清空controller
                const cancelBtn = document.getElementById('cancel-btn');
                if (cancelBtn) cancelBtn.classList.add('hidden');
                this.currentController = null;
                this.currentTimerInterval = null;
            }
        });
    }

    async pollTaskStatus(taskId, signal) {
        let retryCount = 0;
        const maxRetries = 3;

        return new Promise((resolve, reject) => {
            const poll = async () => {
                try {
                    const response = await fetch(`/api/tasks/${taskId}`, { signal });
                    if (!response.ok) throw new Error(`服务器响应异常: ${response.status}`);

                    const task = await response.json();
                    retryCount = 0;

                    if (task.status === 'succeed') {
                        resolve(task.result);
                    } else if (task.status === 'failed') {
                        reject(new Error(task.error || '生成失败'));
                    } else {
                        // 显示实时进度消息
                        if (task.progress_message) {
                            this.addLog('info', task.progress_message, { '进度': `${task.progress}%` });
                        }
                        setTimeout(poll, 2000);
                    }
                } catch (err) {
                    if (err.name === 'AbortError') {
                        reject(new Error('生成超时(10分钟)，请检查网络或尝试简化提示词'));
                        return;
                    }
                    retryCount++;
                    if (retryCount <= maxRetries) {
                        setTimeout(poll, 3000);
                    } else {
                        reject(new Error(`查询进度失败: ${err.message}`));
                    }
                }
            };
            poll();
        });
    }

    initLogPanel() {
        const clearBtn = document.getElementById('clear-log-btn');
        if (clearBtn) clearBtn.addEventListener('click', () => this.clearLogs());
        this.addLog('info', '系统已启动', '准备接收生成请求');
    }
    initCancelButton() {
        const cancelBtn = document.getElementById('cancel-btn');
        if (!cancelBtn) return;

        cancelBtn.addEventListener('click', () => {
            if (this.currentController) {
                // 取消当前任务
                this.currentController.abort();

                // 清除计时器
                if (this.currentTimerInterval) {
                    clearInterval(this.currentTimerInterval);
                    this.currentTimerInterval = null;
                }

                // 重置按钮状态
                const generateBtn = document.getElementById('generate-btn');
                if (generateBtn) {
                    generateBtn.disabled = false;
                    generateBtn.innerHTML = '<span class="icon">✨</span> 应用编辑';
                }

                // 隐藏取消按钮
                cancelBtn.classList.add('hidden');

                // 添加日志
                this.addLog('warning', '⏸️ 任务已取消', '用户手动取消了生成任务');

                // 清空controller
                this.currentController = null;
            }
        });
    }
    addLog(type, message, details = null) {
        const now = new Date();
        const timestamp = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
        const log = { id: Date.now(), type, message, details, timestamp };
        this.logs.unshift(log);
        if (this.logs.length > 50) this.logs = this.logs.slice(0, 50);
        this.renderLogs();
    }

    renderLogs() {
        const container = document.getElementById('log-list');
        if (!container) return;
        if (this.logs.length === 0) {
            container.innerHTML = '<div class="log-empty">📋 工作日志将显示在这里</div>';
            return;
        }

        const iconMap = {
            'info': '📘',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'progress': '⏳'
        };

        container.innerHTML = this.logs.map(log => {
            const icon = iconMap[log.type] || '📌';
            const detailsHtml = log.details ? `
                <div class="log-details">
                    ${typeof log.details === 'object' ?
                    Object.entries(log.details).map(([k, v]) => `<div>• <strong>${k}:</strong> ${v}</div>`).join('') :
                    log.details
                }
                </div>` : '';

            return `
                <div class="log-item log-${log.type}">
                    <div class="log-icon">${icon}</div>
                    <div class="log-body">
                        <div class="log-header">
                            <span class="log-message">${log.message}</span>
                            <span class="log-timestamp">${log.timestamp}</span>
                        </div>
                        ${detailsHtml}
                    </div>
                </div>
            `;
        }).join('');
        container.scrollTop = 0;
    }

    clearLogs() {
        if (this.logs.length === 0) return;
        if (confirm('确定要清空所有日志吗？')) {
            this.logs = [];
            this.renderLogs();
            this.addLog('info', '日志已清空', null);
        }
    }

    initCancelButton() {
        const cancelBtn = document.getElementById('cancel-btn');
        if (!cancelBtn) return;

        cancelBtn.addEventListener('click', () => {
            if (this.currentController) {
                // 取消当前任务
                this.currentController.abort();

                // 清除计时器
                if (this.currentTimerInterval) {
                    clearInterval(this.currentTimerInterval);
                    this.currentTimerInterval = null;
                }

                // 重置按钮状态
                const generateBtn = document.getElementById('generate-btn');
                if (generateBtn) {
                    generateBtn.disabled = false;
                    generateBtn.innerHTML = '<span class="icon">✨</span> 应用编辑';
                }

                // 隐藏取消按钮
                cancelBtn.classList.add('hidden');

                // 添加日志
                this.addLog('warning', '⏸️ 任务已取消', '用户手动取消了生成任务');

                // 清空controller
                this.currentController = null;
            }
        });
    }

    initHistory() {
        const clearBtn = document.getElementById('clear-history-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                if (this.history.length === 0) return;
                if (confirm('确定要清空所有历史记录吗？')) {
                    this.history = [];
                    this.saveHistory();
                    this.addLog('info', '历史记录已清空', null);
                }
            });
        }
    }
}

window.app = new App();
