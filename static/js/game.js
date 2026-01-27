// ==========================================
// 0. 全局配置与状态
// ==========================================
const CONFIG = {
    COEFFS: {
        0: { name: "摆", emoji: "💤", drain: 0.0, class: "btn-outline-secondary", activeClass: "btn-secondary" },
        1: { name: "摸", emoji: "😐", drain: 0.8, class: "btn-outline-primary", activeClass: "btn-primary" },
        2: { name: "卷", emoji: "🔥", drain: 3.0, class: "btn-outline-danger", activeClass: "btn-danger" }
    },
    BASE_DRAIN: 2.0
};

// 全局数据缓存
let courseMetadata = [];       
let currentStats = {};         
let currentCourseStates = {};  

// 防手滑
window.onbeforeunload = function(e) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        e.preventDefault();
        e.returnValue = '游戏正在进行中，进度可能丢失，确定退出吗？';
        return e.returnValue;
    }
};

let isCooldown = false;
let ws = null;
const logContainer = document.getElementById('event-log');

if (typeof auth !== 'undefined') {
    auth.checkLogin();
}

// ==========================================
// 1. 初始化与 WebSocket
// ==========================================
window.onload = initGame;

function initGame() {
    const token = typeof auth !== 'undefined' ? auth.getToken() : 'test_token';
    const baseUrl = typeof WS_BASE_URL !== 'undefined' ? WS_BASE_URL : 'ws://localhost:8000';
    ws = new WebSocket(`${baseUrl}/ws/game?token=${token}`);

    ws.onopen = () => {
        logEvent("系统", "已连接教务系统 (状态模式)...", "text-success");
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
    };

    ws.onclose = () => {
        logEvent("系统", "连接已断开，请刷新页面。", "text-danger");
    };
    
    ws.onerror = (err) => {
        console.error("WS Error", err);
    };
}

function handleServerMessage(msg) {
    switch (msg.type) {
        case 'init':
            updateUserInfo(msg.data);
            if (msg.data.course_info_json) {
                courseMetadata = JSON.parse(msg.data.course_info_json);
            }
            updateGameView(msg.data, null, null);
            break;

        case 'tick':
            updateGameView(msg.stats, msg.courses, msg.course_states);
            break;

        case 'event':
            logEvent("事件", msg.data.desc, "text-primary");
            break;

        case 'game_over':
            showGameOverModal(msg.reason, msg.restartable);
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
            location.reload();
            break;
            
        case 'graduation':
            alert(msg.data.msg);
            break;
    }
}

// ==========================================
// 2. 核心渲染逻辑 (State-Based)
// ==========================================

function updateGameView(stats, courses, states) {
    if (stats) {
        currentStats = stats;
        updateStatsUI(stats);
    }
    // 【关键】必须把课程进度缓存到全局变量，供乐观更新使用
    if (courses) {
        currentStats.courses = courses;
    }
    if (states) {
        currentCourseStates = states;
    }

    if (courseMetadata.length > 0) {
        const safeCourses = courses || currentStats.courses || {};
        // 如果后端没传 states，给个默认全“摸”的状态
        if (!currentCourseStates || Object.keys(currentCourseStates).length === 0) {
             courseMetadata.forEach(c => currentCourseStates[c.id] = 1);
        }
        renderCourseList(safeCourses, currentCourseStates);
        updateEnergyProjection(); 
    }
}

function renderCourseList(masteryData, statesData) {
    const listContainer = document.getElementById('course-list');
    if(!listContainer) return;
    listContainer.innerHTML = '';

    let total = 0, count = 0;
    
    // 确保 statesData 是一个对象，防止未定义报错
    const safeStates = statesData || {};

    courseMetadata.forEach(course => {
        // 【关键修复】统一将 ID 转为字符串，防止 int/string 不匹配导致状态找不到
        const cId = String(course.id);
        
        // 获取进度
        const val = parseFloat(masteryData[cId] || 0);
        total += val; 
        count++;

        // 【关键修复】获取当前状态，如果字典里没有，默认设为 1 (摸)
        // 注意：这里检查 safeStates[cId] 是否为 undefined，因为状态 0 是有效值
        let currentState = safeStates[cId];
        if (currentState === undefined || currentState === null) {
            currentState = 1;
        }
        currentState = parseInt(currentState); // 确保是整数

        // 进度条颜色逻辑
        let badgeClass = "bg-secondary";
        if (val > 60) badgeClass = "bg-warning";
        if (val > 85) badgeClass = "bg-success";

        // 构建 DOM
        const item = document.createElement('div');
        item.className = "list-group-item p-2 mb-2 border-0 shadow-sm course-item flat-course-item";
        item.style.transition = "all 0.3s";

        // 左侧边框色：根据状态改变
        if (currentState === 2) item.style.borderLeft = "5px solid #dc3545"; // 卷 - 红
        else if (currentState === 0) item.style.borderLeft = "5px solid #6c757d"; // 摆 - 灰
        else item.style.borderLeft = "5px solid #0d6efd"; // 摸 - 蓝

        // 状态切换时的闪烁动画
        if (item.dataset.lastState && item.dataset.lastState != currentState) {
            item.classList.add('state-changed');
            setTimeout(() => item.classList.remove('state-changed'), 600);
        }
        item.dataset.lastState = currentState;

        // 获取当前状态对应的配置（名字、表情、颜色）
        const stateConfig = CONFIG.COEFFS[currentState] || CONFIG.COEFFS[1];

        item.innerHTML = `
            <div class="d-flex w-100 justify-content-between align-items-center mb-1">
                <h6 class="mb-0 fw-bold text-dark" style="font-size:1rem;">
                    ${course.name} 
                    <small class="text-muted ms-1" style="font-weight:normal;">(${course.credits}学分)</small>
                </h6>
                <span class="badge ${badgeClass} rounded-pill" style="font-size:0.9em;">${val.toFixed(1)}%</span>
            </div>
            
            <div class="progress mb-2" style="height: 6px; background-color: #e9ecef;">
                <div class="progress-bar ${badgeClass}" role="progressbar" style="width: ${val}%"></div>
            </div>
            
            <div class="d-flex justify-content-between align-items-center mt-2">
                <div class="d-flex align-items-center">
                    <small class="text-muted me-2">策略:</small>
                    <div class="btn-group btn-group-sm" role="group">
                        ${renderStateButton(cId, 0, currentState)}
                        ${renderStateButton(cId, 1, currentState)}
                        ${renderStateButton(cId, 2, currentState)}
                    </div>
                </div>
                <span class="fs-5" title="当前状态">${stateConfig.emoji}</span>
            </div>
        `;
        listContainer.appendChild(item);
    });

    // 渲染右侧底部的考试卡片
    const avgProgress = count > 0 ? (total / count) : 0;
    renderExamConsole(avgProgress);
}

// 辅助：生成状态按钮
function renderStateButton(courseId, stateValue, currentState) {
    const config = CONFIG.COEFFS[stateValue];
    const isActive = (stateValue === currentState);
    
    // 如果激活：使用实心 activeClass (如 btn-danger)
    // 如果未激活：使用轮廓 class (如 btn-outline-danger)
    const btnClass = isActive ? config.activeClass : config.class;
    
    // 激活状态下增加 shadow 效果，增强视觉反馈
    const activeStyle = isActive ? "box-shadow: 0 0 0 2px rgba(0,0,0,0.1) inset;" : "";

    return `<button type="button" class="btn ${btnClass} ${isActive ? 'active fw-bold' : ''}" 
            style="${activeStyle} min-width: 40px;"
            onclick="changeCourseState('${courseId}', ${stateValue})">
            ${config.name}
            </button>`;
}

// ==========================================
// 3. 交互逻辑
// ==========================================

function changeCourseState(courseId, newState) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: "change_course_state",
            target: courseId,
            value: newState
        }));
    }
}

function sendAction(type, target) {
    if (isCooldown) return;
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: type,
            target: target
        }));
        
        isCooldown = true;
        setTimeout(() => { isCooldown = false; }, 500);
    }
}

// ==========================================
// 4. 数值计算与展示
// ==========================================

// 考试控制台：嵌入右侧栏版本
function renderExamConsole(progress) {
    const consoleContainer = document.getElementById('exam-console-container');
    if (!consoleContainer) return;

    let examBtnClass = progress >= 80 ? 'btn btn-danger w-100 pulse-animation fw-bold py-2' : 'btn btn-secondary w-100 disabled';
    let examBtnTip = progress >= 80 ? '当前进度已达标，随时可考！' : '（建议总进度 >80% 后考试）';
    
    // 每次渲染只需更新内容，避免重复创建计时器
    // 检查是否已经初始化过，如果不需要每次重绘结构也可以优化，但这里为了简单直接重写innerHTML
    
    consoleContainer.innerHTML = `
        <div class="card border-danger shadow-sm">
            <div class="card-header bg-danger text-white d-flex justify-content-between align-items-center py-2">
                <span class="fw-bold">🔥 学期冲刺</span>
                <span class="badge bg-white text-danger rounded-pill">No.1</span>
            </div>
            <div class="card-body text-center p-3 bg-light-danger">
                <div class="mb-3">
                    <span class="text-muted small text-uppercase fw-bold" style="letter-spacing:1px;">总平均进度</span>
                    <h2 class="display-5 fw-bold mb-0 text-dark">${progress.toFixed(1)}%</h2>
                    <div class="progress mt-2" style="height: 6px;">
                        <div class="progress-bar bg-danger" role="progressbar" style="width: ${progress}%"></div>
                    </div>
                </div>
                
                <div class="alert alert-warning py-2 mb-3 d-flex align-items-center justify-content-center">
                    <span class="fs-5 me-2">⏳</span>
                    <div>
                        <div class="small text-muted" style="line-height:1;">距离期末自动交卷</div>
                        <span id="semester-timer" class="fw-bold fs-5 text-danger" style="font-family:monospace;">--:--</span>
                    </div>
                </div>

                <button onclick="takeFinalExam()" class="${examBtnClass}">
                    ✍️ 参加期末考试
                </button>
                <small class="d-block mt-2 text-muted" style="font-size: 0.75rem">${examBtnTip}</small>
            </div>
        </div>
    `;
    
    // 确保计时器运行
    initSemesterTimer();
}

// 精力消耗预估
function updateEnergyProjection() {
    if (courseMetadata.length === 0) return;

    let totalCredits = 0;
    let totalDrainWeight = 0;

    courseMetadata.forEach(c => {
        const credits = parseFloat(c.credits);
        totalCredits += credits;
        const state = currentCourseStates[c.id] || 1; 
        const drainCoeff = CONFIG.COEFFS[state].drain;
        totalDrainWeight += credits * drainCoeff;
    });

    if (totalCredits === 0) totalCredits = 1;
    const weightedFactor = totalDrainWeight / totalCredits;
    const estimatedCost = Math.floor(CONFIG.BASE_DRAIN * weightedFactor);

    // 尝试找 DOM
    let label = document.getElementById('energy-prediction');
    if (!label) {
        const energyContainer = document.getElementById('val-energy');
        if(energyContainer && energyContainer.parentNode) {
            label = document.createElement('small');
            label.id = 'energy-prediction';
            label.className = "ms-2 fw-bold";
            energyContainer.parentNode.appendChild(label);
        }
    }
    
    if (label) {
        if (estimatedCost === 0) {
            label.className = "ms-2 fw-bold text-success";
            label.innerText = "(+2/tick 回复)";
        } else {
            label.className = estimatedCost > 5 ? "ms-2 fw-bold text-danger" : "ms-2 fw-bold text-muted";
            label.innerText = `(-${estimatedCost}/tick)`;
        }
    }
}

function updateStatsUI(stats) {
    const setBar = (id, val, max=100) => {
        const v = parseInt(val) || 0;
        const percent = Math.min(100, Math.max(0, (v / max) * 100));
        
        const bar = document.getElementById(`bar-${id}`);
        const text = document.getElementById(`val-${id}`);
        
        if (bar) bar.style.width = `${percent}%`;
        if (text) text.innerText = `${v}/${max}`;
        
        if(id === 'energy' && bar) {
            bar.className = v < 20 ? 'progress-bar bg-danger' : 
                           (v < 50 ? 'progress-bar bg-warning' : 'progress-bar bg-success');
        }
    };

    setBar('energy', stats.energy);
    setBar('sanity', stats.sanity);
    setBar('stress', stats.stress);

    ['iq', 'eq', 'luck', 'reputation'].forEach(k => {
        const el = document.getElementById(`val-${k}`);
        if(el) el.innerText = stats[k] || 0;
    });
}

// ==========================================
// 5. 辅助功能
// ==========================================

function updateUserInfo(data) {
    const elName = document.getElementById('display-name');
    if(elName) elName.innerText = data.username;
    const elMajor = document.getElementById('display-major');
    if(elMajor) elMajor.innerText = data.major;
    const elSem = document.getElementById('display-semester');
    if(elSem) elSem.innerText = data.semester;
}

function logEvent(source, message, cssClass="") {
    if (!logContainer) return;
    const time = new Date().toLocaleTimeString();
    const div = document.createElement('div');
    div.className = `mb-1 ${cssClass} border-bottom pb-1`;
    div.innerHTML = `<span class="badge bg-light text-dark me-1">${time}</span> <strong>${source}:</strong> ${message}`;
    logContainer.appendChild(div);
    logContainer.scrollTop = logContainer.scrollHeight; 
}

function takeFinalExam() {
    if(!confirm("确定要参加期末考试吗？考试后将结算本学期GPA。")) return;
    sendAction('exam', 'final');
}

function initSemesterTimer() {
    if (window.timerRunning) return;
    window.timerRunning = true;
    
    let remain = 600; // 10分钟倒计时
    const updateDisplay = () => {
        const el = document.getElementById('semester-timer');
        if (el) {
            let min = Math.floor(remain / 60);
            let sec = remain % 60;
            el.innerText = `${min}:${sec.toString().padStart(2, '0')}`;
        }
    };
    
    // 立即执行一次
    updateDisplay();

    setInterval(() => {
        remain--;
        if (remain >= 0) updateDisplay();
        if (remain === 0) takeFinalExam(); 
    }, 1000);
}

function showGameOverModal(reason, restartable) {
    let old = document.getElementById('gameover-modal');
    if (old) old.remove();
    const modal = document.createElement('div');
    modal.id = 'gameover-modal';
    modal.innerHTML = `
    <div class="modal fade show" style="display:block;background:rgba(0,0,0,0.8);z-index:9999;" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0">
                <div class="modal-header bg-dark text-white">
                    <h5 class="modal-title">☠️ GAME OVER</h5>
                </div>
                <div class="modal-body text-center py-5">
                    <h3 class="mb-3">${reason || '你倒下了...'}</h3>
                    <p class="text-muted">大学生活真是充满了变数啊</p>
                </div>
                <div class="modal-footer justify-content-center bg-light">
                    ${restartable ? `<button onclick="restartGame()" class="btn btn-primary btn-lg px-5">🔄 重新开始</button>` : ''}
                    <button onclick="location.href='index.html'" class="btn btn-outline-secondary">退出</button>
                </div>
            </div>
        </div>
    </div>`;
    document.body.appendChild(modal);
}

function restartGame() {
    ws.send(JSON.stringify({action: 'restart'}));
    document.getElementById('gameover-modal').remove();
}

function showTranscript(data) {
    const tbody = document.getElementById('transcript-body');
    if (tbody) {
        tbody.innerHTML = data.details.map(item => `
            <tr>
                <td>${item.name}</td>
                <td class="${item.score < 60 ? 'text-danger fw-bold' : ''}">${item.score}</td>
                <td>${item.gp}</td>
            </tr>
        `).join('');
    }
    
    const gpaDisplay = document.getElementById('transcript-gpa');
    if(gpaDisplay) gpaDisplay.innerText = data.gpa;
    
    try {
        const modalEl = document.getElementById('summaryModal');
        if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        }
    } catch(e) { console.error("Bootstrap Modal error", e); }
}

function showRandomEventModal(eventData) {
    if (!eventData.options || eventData.options.length < 2) return;
    const choiceIdx = prompt(`【随机事件】${eventData.title}\n${eventData.desc}\n\n请输入 [0] 或 [1] 选择:\n0: ${eventData.options[0].text}\n1: ${eventData.options[1].text}`);
    if (choiceIdx === '0' || choiceIdx === '1') {
        const idx = parseInt(choiceIdx);
        if (ws) {
            ws.send(JSON.stringify({
                action: "event_choice",
                effects: eventData.options[idx].effects
            }));
        }
    }
}

function showToast(title, body) {
    console.log(`Toast: ${title} - ${body}`);
}

function nextSemester() {
    sendAction('next_semester');
    // 关闭成绩单弹窗
    const modalEl = document.getElementById('summaryModal');
    if (modalEl) {
        // Bootstrap 5 关闭 Modal 的方法需要获取实例，这里简单暴力 reload 或者移除 DOM 类
        // 如果有保存实例可以直接 hide，这里为了通用简单重载页面即可
        // 实际上 'new_semester' 消息会触发 reload
    }
}

function clearLog() {
    if(logContainer) logContainer.innerHTML = '';
}