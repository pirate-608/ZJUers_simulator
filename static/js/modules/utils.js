// ==========================================
// 工具函数模块
// ==========================================

export function logEvent(source, message, cssClass = "") {
    const logContainer = document.getElementById('event-log');
    if (!logContainer) return;

    const time = new Date().toLocaleTimeString();
    const div = document.createElement('div');
    div.className = `mb-1 ${cssClass} border-bottom pb-1`;
    div.innerHTML = `<span class="badge bg-light text-dark me-1">${time}</span> <strong>${source}:</strong> ${message}`;
    logContainer.appendChild(div);
    logContainer.scrollTop = logContainer.scrollHeight;
}

export function clearLog() {
    const logContainer = document.getElementById('event-log');
    if (logContainer) {
        logContainer.innerHTML = '';
    }
}

export function showToast(title, body) {
    console.log(`[Toast] ${title} - ${body}`);
    // 可以扩展为真实的 Toast 通知
}

export function updateUserInfo(data) {
    const elName = document.getElementById('display-name');
    if (elName) elName.innerText = data.username;

    const elMajor = document.getElementById('display-major');
    if (elMajor) elMajor.innerText = data.major;

    const elSem = document.getElementById('display-semester');
    if (elSem) elSem.innerText = data.semester;
}

// 防止意外关闭
export function setupBeforeUnload(wsGetter) {
    window.onbeforeunload = function (e) {
        const ws = wsGetter();
        if (ws && ws.readyState === WebSocket.OPEN) {
            // 提示用户有未保存的游戏
            e.preventDefault();
            e.returnValue = '游戏正在进行中，建议先保存进度再离开。';
            return e.returnValue;
        }
    };

    // 监听页面可见性变化（用户切换标签页时不需要提示）
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            console.log('[Utils] Page hidden, game continues in background');
        } else {
            console.log('[Utils] Page visible again');
        }
    });
}
