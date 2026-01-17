const checkBtn = document.getElementById('checkBtn');
const stopBtn = document.getElementById('stopBtn');
const resetBtn = document.getElementById('resetBtn');
const progressSection = document.getElementById('progressSection');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');
const progressPercent = document.getElementById('progressPercent');
const cardsGrid = document.getElementById('cardsGrid');
const emptyState = document.getElementById('emptyState');
const updateCount = document.getElementById('updateCount');
const statusIndicator = document.getElementById('statusIndicator');
const searchInput = document.getElementById('searchInput');
const toastContainer = document.getElementById('toastContainer');

// Settings Elements
const navSettings = document.getElementById('navSettings');
const settingsModal = document.getElementById('settingsModal');
const closeSettings = document.getElementById('closeSettings');
const saveSettings = document.getElementById('saveSettings');
const cancelSettings = document.getElementById('cancelSettings');
const settingRange = document.getElementById('settingRange');
const settingUnit = document.getElementById('settingUnit');
const settingInterval = document.getElementById('settingInterval');
const settingBrowserPath = document.getElementById('settingBrowserPath');
const settingAutoCheck = document.getElementById('settingAutoCheck');

let isChecking = false;
let ws = null;
let reconnectInterval = null;
let allCards = []; // Store card data for filtering
let originalTitle = document.title;
let currentSettings = {
    update_range_days: 7,
    check_interval: 3600,
    auto_check: false,
    browser_path: ''
};

// --- WebSocket & Connection ---

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/progress`);

    ws.onopen = () => {
        statusIndicator.classList.add('connected');
        statusIndicator.title = "已连接到服务器";
        if (reconnectInterval) {
            clearInterval(reconnectInterval);
            reconnectInterval = null;
        }
    };

    ws.onclose = () => {
        statusIndicator.classList.remove('connected');
        statusIndicator.title = "连接断开";
        if (!reconnectInterval) {
            reconnectInterval = setInterval(connectWebSocket, 3000);
        }
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };
}

function handleMessage(msg) {
    if (msg.type === 'progress') {
        updateProgress(msg);
    } else if (msg.type === 'item') {
        addCard(msg.data);
    } else if (msg.type === 'done') {
        finishCheck(msg.count);
    }
}

// --- UI Logic ---

function updateProgress(data) {
    if (!isChecking) {
        setCheckingState(true);
    }
    const percent = Math.round((data.current / data.total) * 100);
    progressBar.style.width = `${percent}%`;
    progressPercent.textContent = `${percent}%`;
    progressText.textContent = `正在检查: ${data.name}`;
}

function addCard(item) {
    if (emptyState.style.display !== 'none') {
        emptyState.style.display = 'none';
    }

    // Store raw data for search
    const cardData = {
        element: null,
        title: item.video.title.toLowerCase(),
        author: item.bookmark.name.toLowerCase()
    };

    const card = document.createElement('div'); // Wrapper div
    card.className = 'card';

    // HTML Construction
    let videoUrl = '';
    try {
        if (item.bookmark && item.bookmark.url) {
            const bookmarkUrl = new URL(item.bookmark.url);
            const domain = bookmarkUrl.hostname;

            // Check for hsex domains
            if (domain.includes('hsex.men') || domain.includes('hsex.icu')) {
                videoUrl = `https://${domain}/video-${item.video.video_id}.htm`;
            } else if (domain.includes('bilibili.com')) {
                videoUrl = `https://www.bilibili.com/video/${item.video.video_id}`;
            } else {
                // Generic fallback: try to construct based on domain or use search
                videoUrl = item.bookmark.url;
            }
        } else {
            // Fallback if no bookmark URL
            videoUrl = `https://www.bilibili.com/video/${item.video.video_id}`;
        }
    } catch (e) {
        console.error("Error constructing video URL:", e);
        videoUrl = '#';
    }

    card.innerHTML = `
        <div class="card-thumb-wrapper" onclick="openVideo('${videoUrl}')">
            <div class="play-overlay">
                <div class="play-icon">▶</div>
            </div>
            <img class="card-thumb" src="${item.video.thumbnail_url}" alt="${item.video.title}" loading="lazy" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzMjAiIGhlaWdodD0iMTgwIiB2aWV3Qm94PSIwIDAgMzIwIDE4MCI+PHJlY3Qgd2lkdGg9IjMyMCIgaGVpZ2h0PSIxODAiIGZpbGw9IiMxZTI5M2IiLz48dGV4dCB4PSI1MCUiIHk9IjUwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0iIzQ3NTU2OSIgZm9udC1zaXplPSIyMCI+Tm8gSW1hZ2U8L3RleHQ+PC9zdmc+'">
            <div class="card-duration">${item.video.relative_time}</div>
            <div class="card-actions">
                <div class="action-btn" title="复制链接" onclick="copyLink(event, '${videoUrl}')">
                   🔗
                </div>
            </div>
        </div>
        <div class="card-body">
            <div class="card-title" title="${item.video.title}" onclick="openVideo('${videoUrl}')">${item.video.title}</div>
            <div class="card-footer">
                <div class="author">
                    <img class="avatar" src="${item.bookmark.avatar_url}" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMCIgaGVpZ2h0PSIyMCI+PGNpcmNsZSBjeD0iMTAiIGN5PSIxMCIgcj0iMTAiIGZpbGw9IiMzMzMiLz48L3N2Zz4='">
                    <span>${item.bookmark.name}</span>
                </div>
            </div>
        </div>
    `;

    // Add entrance animation
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';

    cardsGrid.insertBefore(card, cardsGrid.firstChild);

    // Trigger reflow
    requestAnimationFrame(() => {
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
    });

    cardData.element = card;
    allCards.unshift(cardData); // Add to beginning

    updateCountBadge();
    updateTitle();
}

async function openVideo(url) {
    try {
        const res = await fetch('/api/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });

        const data = await res.json();
        if (data.status === 'success') {
            if (data.method === 'custom') {
                showToast('🖥️ 已在指定浏览器打开');
            } else {
                showToast('🌐 已在默认浏览器打开');
            }
        } else {
            // Fallback
            window.open(url, '_blank');
        }
    } catch (e) {
        console.error("Open failed:", e);
        window.open(url, '_blank');
    }
}

function setCheckingState(checking) {
    isChecking = checking;
    if (checking) {
        checkBtn.style.display = 'none';
        stopBtn.style.display = 'flex';
        resetBtn.disabled = true;
        progressSection.classList.add('active');
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        progressText.textContent = '准备开始...';
        searchInput.disabled = true;
    } else {
        checkBtn.style.display = 'flex';
        stopBtn.style.display = 'none';
        resetBtn.disabled = false;
        searchInput.disabled = false;
    }
}

function finishCheck(count) {
    setCheckingState(false);

    if (count > 0) {
        showToast(`🎉 发现 ${count} 个新更新！`, 'success');
        if (Notification.permission === "granted") {
            new Notification("更新检查完毕", { body: `发现 ${count} 个新视频` });
        }
    } else {
        showToast('✅ 检查完毕，暂无新更新');
        // Delay hiding progress bar if finished
        setTimeout(() => {
            if (!isChecking) progressSection.classList.remove('active');
        }, 3000);
    }

    progressText.textContent = `检查完成，共发现 ${count} 个更新`;
    progressBar.style.width = '100%';
    progressPercent.textContent = '100%';
}

// --- Settings Logic ---

function openSettingsModal() {
    loadSettings();
    settingsModal.classList.add('active');
}

function closeSettingsModal() {
    settingsModal.classList.remove('active');
}

async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        if (res.ok) {
            const data = await res.json();
            currentSettings = data;
            applySettingsToForm(data);
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
        showToast('⚠️ 加载设置失败', 'error');
    }
}

function applySettingsToForm(data) {
    let days = data.update_range_days;
    let unit = 1;

    if (days % 365 === 0) {
        unit = 365;
    } else if (days % 30 === 0) {
        unit = 30;
    }

    settingRange.value = days / unit;
    settingUnit.value = unit;

    settingInterval.value = Math.max(1, Math.round(data.check_interval / 3600));
    settingBrowserPath.value = data.browser_path || '';
    settingAutoCheck.checked = data.auto_check;
}

async function saveSettingsToServer() {
    const newSettings = {
        update_range_days: parseInt(settingRange.value) * parseInt(settingUnit.value),
        check_interval: parseInt(settingInterval.value) * 3600,
        auto_check: settingAutoCheck.checked,
        browser_path: settingBrowserPath.value.trim() || null
    };

    saveSettings.disabled = true;
    saveSettings.textContent = '保存中...';

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newSettings)
        });

        if (res.ok) {
            currentSettings = newSettings;
            showToast('✅ 设置已保存', 'success');
            closeSettingsModal();
        } else {
            throw new Error('Save failed');
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
        showToast('❌ 保存设置失败', 'error');
    } finally {
        saveSettings.disabled = false;
        saveSettings.textContent = '保存设置';
    }
}

// --- Helpers ---

function updateCountBadge() {
    // Only count visible cards
    const count = allCards.filter(c => c.element.style.display !== 'none').length;
    updateCount.textContent = count;
}

function updateTitle() {
    const count = allCards.length;
    if (count > 0) {
        document.title = `(${count}) 更新检查器 Pro`;
    } else {
        document.title = originalTitle;
    }
}

window.copyLink = function (e, url) {
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.writeText(url).then(() => {
        showToast('📋 链接已复制');
    });
};

function showToast(message, type = 'normal') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = message;

    toastContainer.appendChild(toast);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// --- Event Listeners ---

checkBtn.addEventListener('click', async () => {
    if (isChecking) return;

    // Request notification permission
    if (Notification.permission === "default") {
        Notification.requestPermission();
    }

    setCheckingState(true);
    showToast('🚀 开始检查更新...');

    try {
        // Use current settings for the check
        await fetch('/api/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                update_range_days: currentSettings.update_range_days
            })
        });
    } catch (error) {
        console.error('Start check failed:', error);
        setCheckingState(false);
        showToast('❌ 启动失败，请检查网络', 'error');
    }
});

stopBtn.addEventListener('click', async () => {
    if (!isChecking) return;

    try {
        stopBtn.disabled = true;
        progressText.textContent = '正在停止...';
        await fetch('/api/stop', { method: 'POST' });
        showToast('🛑 已请求停止...');

        setTimeout(() => {
            if (isChecking) {
                setCheckingState(false);
                progressText.textContent = '已停止';
                showToast('⏹检查已停止');
            }
            stopBtn.disabled = false;
        }, 1000);
    } catch (error) {
        console.error('Stop failed:', error);
        stopBtn.disabled = false;
    }
});

resetBtn.addEventListener('click', () => {
    if (allCards.length === 0) return;

    if (confirm('确定要清除所有结果吗？')) {
        cardsGrid.innerHTML = '';
        allCards = [];
        updateCount.textContent = '0';
        emptyState.style.display = 'block';
        progressSection.classList.remove('active');
        progressBar.style.width = '0%';
        updateTitle();
        showToast('🗑 已清除所有结果');
    }
});

searchInput.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase();
    let visibleCount = 0;

    allCards.forEach(card => {
        const visible = card.title.includes(term) || card.author.includes(term);
        card.element.style.display = visible ? 'flex' : 'none';
        if (visible) visibleCount++;
    });

    // Update empty state based on search result
    if (visibleCount === 0 && allCards.length > 0) {
        // Maybe show a "No search results" state?
    }

    updateCountBadge();
});

// Settings Events
navSettings.addEventListener('click', (e) => {
    e.preventDefault();
    openSettingsModal();
});

closeSettings.addEventListener('click', closeSettingsModal);
cancelSettings.addEventListener('click', closeSettingsModal);
saveSettings.addEventListener('click', saveSettingsToServer);

settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) {
        closeSettingsModal();
    }
});

// Logs Logic
const navLogs = document.getElementById('navLogs');
navLogs.addEventListener('click', async (e) => {
    e.preventDefault();
    await showLogs();
});

async function showLogs() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay active';
    overlay.innerHTML = `
        <div class="modal-content glass-panel" style="width: 800px; max-width: 95%;">
            <div class="modal-header">
                <h2>📜 运行日志 (最后10000字)</h2>
                <button class="close-btn" onclick="this.closest('.modal-overlay').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <pre id="logContent" style="background:#111; padding:10px; border-radius:8px; overflow:auto; max-height:60vh; font-family:monospace; font-size:12px; color:#ddd; white-space:pre-wrap;">加载中...</pre>
                <div style="margin-top:10px; text-align:right;">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">关闭</button>
                    <button class="btn btn-primary" onclick="showLogs()">刷新</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        const pre = overlay.querySelector('#logContent');
        if (data.data) {
            pre.textContent = data.data;
            // Scroll to bottom
            pre.scrollTop = pre.scrollHeight;
        } else {
            pre.textContent = "暂无日志或无法读取日志文件\n(可能是首次运行，请先点击'开始检查')";
        }
    } catch (e) {
        overlay.querySelector('#logContent').textContent = "读取失败: " + e.message;
    }
}

// Keyboard Shortcuts
document.addEventListener('keydown', (e) => {
    if (document.activeElement === searchInput) return;

    if (e.key === 'Enter' && !isChecking) {
        checkBtn.click();
    } else if (e.key === 'Escape') {
        if (settingsModal.classList.contains('active')) {
            closeSettingsModal();
        } else if (isChecking) {
            stopBtn.click();
        }
    }
});

// Init
async function initApp() {
    // Detect mode
    try {
        const res = await fetch('/api/stats', { method: 'HEAD', timeout: 2000 }); // Short timeout
        if (res.ok) {
            // Dynamic Mode (Local Server)
            console.log("Dynamic mode detected");
            connectWebSocket();
            loadSettings();
        } else {
            throw new Error("API not reachable");
        }
    } catch (e) {
        // Static Mode (GitHub Pages)
        console.log("Static mode detected (or server offline)");
        document.body.classList.add('static-mode');

        // Modify UI for static mode
        checkBtn.style.display = 'none';
        const staticLabel = document.createElement('div');
        staticLabel.className = 'static-status';
        staticLabel.innerHTML = '⚡ 自动托管模式 (每小时运行)';
        document.querySelector('.actions-area').prepend(staticLabel);

        // Load static data
        try {
            const dataRes = await fetch('data.json');
            if (dataRes.ok) {
                const data = await dataRes.json();

                if (data.encrypted) {
                    handleEncryptedData(data);
                } else if (data.items && Array.isArray(data.items)) {
                    loadItems(data);
                }
            }
        } catch (err) {
            console.error("Failed to load static data:", err);
            showToast('⚠️ 无法加载数据', 'error');
        }
    }
}

function handleEncryptedData(data) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay active';
    overlay.style.zIndex = '9999';
    overlay.style.backdropFilter = 'blur(20px)';
    overlay.innerHTML = `
        <div class="modal-content glass-panel" style="max-width:320px; text-align:center; padding: 40px 30px;">
            <div style="font-size: 48px; margin-bottom: 20px;">🔒</div>
            <h2 style="margin-bottom: 10px;">私密访问</h2>
            <p style="color: var(--text-secondary); margin-bottom: 25px; font-size: 0.9rem;">请输入密码解锁内容</p>
            
            <div class="form-group">
                <input type="password" id="sitePassword" 
                    style="text-align: center; font-size: 1.2rem; letter-spacing: 4px;" 
                    placeholder="••••••">
            </div>
            
            <button class="btn btn-primary glow-effect" id="unlockBtn" style="width:100%; justify-content: center; height: 48px;">
                解锁
            </button>
            <p id="unlockError" style="color: var(--danger); margin-top: 15px; font-size: 0.85rem; opacity: 0; transition: opacity 0.3s;">
                密码错误，请重试
            </p>
        </div>
    `;
    document.body.appendChild(overlay);

    // ... rest of logic
    const input = overlay.querySelector('#sitePassword');
    const btn = overlay.querySelector('#unlockBtn');
    const errorMsg = overlay.querySelector('#unlockError');

    const tryUnlock = () => {
        const password = input.value;
        if (!password) return;

        btn.textContent = '验证中...';
        btn.disabled = true;
        errorMsg.style.opacity = '0';

        setTimeout(() => {
            const decrypted = decryptData(data, password);
            if (decrypted) {
                // Success animation
                btn.textContent = '🔓 已解锁';
                btn.style.background = 'var(--success)';
                setTimeout(() => {
                    loadItems(decrypted);
                    overlay.style.opacity = '0';
                    setTimeout(() => overlay.remove(), 300);
                }, 500);
            } else {
                // Shake animation for error
                const content = overlay.querySelector('.modal-content');
                content.style.animation = 'shake 0.4s ease';
                setTimeout(() => content.style.animation = '', 400);

                errorMsg.style.opacity = '1';
                btn.textContent = '解锁';
                btn.disabled = false;
                btn.style.background = '';
                input.value = '';
                input.focus();
            }
        }, 300);
    };

    btn.addEventListener('click', tryUnlock);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') tryUnlock();
    });

    // Add shake keyframes if not exists
    if (!document.getElementById('shake-anim')) {
        const style = document.createElement('style');
        style.id = 'shake-anim';
        style.textContent = `
            @keyframes shake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-10px); }
                75% { transform: translateX(10px); }
            }
        `;
        document.head.appendChild(style);
    }

    input.focus();
}

function decryptData(encryptedData, password) {
    try {
        const salt = CryptoJS.enc.Base64.parse(encryptedData.salt);
        const iv = CryptoJS.enc.Base64.parse(encryptedData.iv);
        const content = encryptedData.content;

        const key = CryptoJS.PBKDF2(password, salt, {
            keySize: 256 / 32,
            iterations: 1000
        });

        const decrypted = CryptoJS.AES.decrypt(content, key, {
            iv: iv,
            padding: CryptoJS.pad.Pkcs7,
            mode: CryptoJS.mode.CBC
        });

        const utf8 = decrypted.toString(CryptoJS.enc.Utf8);
        return JSON.parse(utf8);
    } catch (e) {
        console.error("Decryption failed", e);
        return null;
    }
}

function loadItems(data) {
    // Clear existing
    cardsGrid.innerHTML = '';
    allCards = [];

    if (data.items && Array.isArray(data.items)) {
        // Add items (reverse since addCard unshifts)
        [...data.items].reverse().forEach(item => addCard(item));

        if (data.metadata?.generated_at) {
            progressText.textContent = `更新于: ${data.metadata.generated_at}`;
            progressBar.style.width = '100%';
            progressSection.classList.add('active');
            setTimeout(() => progressSection.classList.remove('active'), 5000);
        }
    }
}

// Run ID checks or other initializers
initApp();

