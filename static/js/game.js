// 1. 防手滑：刷新/关闭 警告
window.onbeforeunload = function(e) {
    // 只有在 WebSocket 连接且游戏进行中才提示
    if (ws && ws.readyState === WebSocket.OPEN) {
        e.preventDefault();
        e.returnValue = '游戏正在进行中，进度可能丢失，确定退出吗？';
        return e.returnValue;
    }
};

// 2. 按钮冷却锁
let isCooldown = false;

// 检查登录
auth.checkLogin();

let ws = null;
const logContainer = document.getElementById('event-log');

// 初始化
function initGame() {
    const token = auth.getToken();
    // 建立 WebSocket 连接，带上 token (可以通过 query param 或 协议头，这里用 query param 简单点)
    ws = new WebSocket(`${WS_BASE_URL}/ws/game?token=${token}`);

    ws.onopen = () => {
        logEvent("系统", "已成功连接到浙大教务网...", "text-success");
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
    };

    ws.onclose = () => {
        logEvent("系统", "连接已断开，请刷新页面重试。", "text-danger");
    };
    
    ws.onerror = (err) => {
        console.error("WS Error", err);
    };
}


// 全局变量：存储课程静态信息（名字、ID等）
let courseMetadata = [];

function handleServerMessage(msg) {
    switch (msg.type) {
        case 'init':
            updateUserInfo(msg.data);
            // 解析课程静态数据 (后端传过来的是 JSON 字符串)
            if (msg.data.course_info_json) {
                courseMetadata = JSON.parse(msg.data.course_info_json);
                // 初始渲染列表（进度全为0）
                renderCourseList({});
            }
            updateStats(msg.data);
            break;
        case 'tick':
            updateStats(msg.stats);
            // 如果消息里包含课程进度，则更新
            if (msg.courses) {
                renderCourseList(msg.courses);
            }
            break;
        case 'event':
            logEvent("事件", msg.data.desc, "text-primary");
            if(msg.data.effect) {
                // 可以加一些浮动文字特效，这里暂时省略
            }
            break;
        case 'game_over':
            alert(`游戏结束: ${msg.reason}`);
            auth.clearToken();
            window.location.href = 'index.html';
            break;
            case 'semester_summary':
                showTranscript(msg.data);
                break;
        case 'random_event':
            showRandomEventModal(msg.data);
            break;
        case 'achievement_unlocked':
            showToast(`🏆 解锁成就：${msg.data.name}`, msg.data.desc);
            break;
        case 'new_semester':
            alert(`假期结束，${msg.data.semester_name} 开始了！`);
            // 如果有假期事件可以在这里弹窗，逻辑同 random_event
            location.reload();
            break;
    // --- 新增辅助函数 ---
    function showRandomEventModal(eventData) {
        // 动态生成一个 Modal 并在 HTML 里插入
        // 这里简单用 confirm 模拟，实际建议写个好看的 Modal
        // 假设 eventData.options 是个数组
        // 为了简化代码，这里只展示第一个选项的交互逻辑
        // 真实项目请在 dashboard.html 预留一个 #eventModal
        let choiceIdx = prompt(`【随机事件】${eventData.title}\n\n${eventData.desc}\n\n请输入选项序号(0/1):\n0: ${eventData.options[0].text}\n1: ${eventData.options[1].text}`);
        if (choiceIdx !== null && eventData.options[choiceIdx]) {
            const choice = eventData.options[choiceIdx];
            // 发送选择回后端
            if (ws) {
                ws.send(JSON.stringify({
                    action: "event_choice",
                    effects: choice.effects // 把效果传回去结算
                }));
            }
        }
    }

    function showToast(title, body) {
        // 在 dashboard.html 底部加一个 toast container 容器
        // 这里简单 alert
        console.log(`成就解锁: ${title}`);
        alert(`🎉 ${title}\n${body}`);
    }
    }
}

    // 触发考试
    function takeFinalExam() {
        if(!confirm("确定要参加期末考试吗？考试后将结算本学期GPA。")) return;
        sendAction('exam', 'final');
    }

    // 显示成绩单
    function showTranscript(data) {
        const tbody = document.getElementById('transcript-body');
        tbody.innerHTML = '';
        data.details.forEach(item => {
            let scoreColor = item.score < 60 ? 'text-danger fw-bold' : '';
            tbody.innerHTML += `
                <tr>
                    <td>${item.name}</td>
                    <td class="${scoreColor}">${item.score.toFixed(1)}</td>
                    <td>${item.gp.toFixed(1)}</td>
                </tr>
            `;
        });
        document.getElementById('transcript-gpa').innerText = data.gpa;
        document.getElementById('gpa-display').innerText = data.gpa; // 更新主界面GPA
        // 显示评语
        const msgDiv = document.getElementById('transcript-msg');
        if (data.failed_count > 0) {
            msgDiv.innerHTML = `<span class="text-danger">⚠️ 你挂了 ${data.failed_count} 门课！心态大崩！</span>`;
        } else {
            msgDiv.innerHTML = `<span class="text-success">全科通过，假期愉快！</span>`;
        }
        const modal = new bootstrap.Modal(document.getElementById('summaryModal'));
        modal.show();
    }

    function nextSemester() {
        // 刷新页面重新开始（简化逻辑，或者请求后端重置学期）
        location.reload();
    }
// 渲染左侧课程列表
function renderCourseList(masteryData) {
    const listContainer = document.getElementById('course-list');
    listContainer.innerHTML = '';
    courseMetadata.forEach(course => {
        // 获取当前擅长度，如果没有则为 0
        let val = parseFloat(masteryData[course.id] || 0).toFixed(1);
        // 进度条颜色
        let badgeClass = "bg-secondary";
        if (val > 60) badgeClass = "bg-warning";
        if (val > 85) badgeClass = "bg-success";
        const item = document.createElement('div');
        item.className = "list-group-item";
        item.innerHTML = `
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1">${course.name} <small class="text-muted">(${course.credits}学分)</small></h6>
                <span class="badge ${badgeClass}">${val}%</span>
            </div>
            <div class="progress mt-1 mb-2" style="height: 5px;">
                <div class="progress-bar ${badgeClass}" style="width: ${val}%"></div>
            </div>
            <div class="btn-group btn-group-sm w-100">
                <button class="btn btn-outline-primary" onclick="sendAction('study', '${course.id}')">卷</button>
                <button class="btn btn-outline-secondary" onclick="sendAction('fish', '${course.id}')">摸</button>
                <button class="btn btn-outline-danger" onclick="sendAction('skip', '${course.id}')">翘</button>
            </div>
        `;
        listContainer.appendChild(item);
    });
}
// 发送动作
function sendAction(type, target) {
    if (isCooldown) {
        // 可选：加个 Toast 提示“操作太快了”
        return;
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: type,
            target: target
        }));
        // 开启冷却 (0.8秒)
        activateCooldown();
    } else {
        alert("网络未连接");
    }
}

function activateCooldown() {
    isCooldown = true;
    // 禁用页面所有业务按钮
    const buttons = document.querySelectorAll('.btn-outline-primary, .btn-outline-secondary, .btn-outline-danger, .btn-outline-success, .btn-outline-info');
    buttons.forEach(btn => btn.classList.add('disabled'));
    setTimeout(() => {
        isCooldown = false;
        buttons.forEach(btn => btn.classList.remove('disabled'));
    }, 800); // 800ms 冷却
}

// 更新界面数值
function updateStats(stats) {
    // 进度条颜色逻辑
    const setBar = (id, val, max=100) => {
        const percent = (val / max) * 100;
        const bar = document.getElementById(`bar-${id}`);
        const text = document.getElementById(`val-${id}`);
        bar.style.width = `${percent}%`;
        text.innerText = `${val}/${max}`;
        
        // 动态变色 (以精力为例)
        if(id === 'energy') {
            if(val < 20) { bar.className = 'progress-bar bg-danger'; }
            else if(val < 50) { bar.className = 'progress-bar bg-warning'; }
            else { bar.className = 'progress-bar bg-success'; }
        }
    };

    setBar('energy', stats.energy);
    setBar('sanity', stats.sanity);
    setBar('stress', stats.stress);

    document.getElementById('val-iq').innerText = stats.iq;
    document.getElementById('val-eq').innerText = stats.eq;
    document.getElementById('val-luck').innerText = stats.luck;
    document.getElementById('val-reputation').innerText = stats.reputation;
    
    // 如果后端传回了课程进度，可以在这里更新左侧列表
    // updateCourseList(stats.courses);
}

function updateUserInfo(data) {
    document.getElementById('display-name').innerText = data.username;
    document.getElementById('display-major').innerText = data.major;
    document.getElementById('display-semester').innerText = data.semester;
}

function logEvent(source, message, cssClass="") {
    const time = new Date().toLocaleTimeString();
    const div = document.createElement('div');
    div.className = `mb-1 ${cssClass}`;
    div.innerHTML = `<small>[${time}] [${source}]</small> ${message}`;
    logContainer.appendChild(div);
    logContainer.scrollTop = logContainer.scrollHeight; // 自动滚动到底部
}

function clearLog() {
    logContainer.innerHTML = '';
}

// 启动
window.onload = initGame;