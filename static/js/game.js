// ==========================================
// 0. 全局配置与状态
// ==========================================
const CONFIG = {
    COEFFS: {
        0: { name: "摆", emoji: "💤", drain: 0.0, class: "btn-outline-secondary", activeClass: "btn-secondary" },
        1: { name: "摸", emoji: "😐", drain: 0.8, class: "btn-outline-primary", activeClass: "btn-primary" },
        2: { name: "卷", emoji: "🔥", drain: 3.0, class: "btn-outline-danger", activeClass: "btn-danger" }
    },
    BASE_DRAIN: 2.0,
    COOLDOWNS: {
        gym: 60,   // 健身60秒冷却
        walk: 45,  // 散步45秒冷却
        game: 30,  // 游戏30秒冷却
        cc98: 15   // CC98 15秒冷却
    },
    SEMESTER_DURATIONS: {},  // 将从服务器加载
    SPEED_MODES: {},          // 将从服务器加载
    currentSpeedMultiplier: 1.0  // 当前速度倍率
};

// 全局数据缓存
let courseMetadata = [];
let currentStats = {};
let currentCourseStates = {};
let ACHIEVEMENTS = null; // 全局成就表缓存
let relaxCooldowns = {}; // 摸鱼按钮冷却时间记录

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
let isPaused = false;

if (typeof auth !== 'undefined') {
    auth.checkLogin();
}

// ==========================================
// 1. 初始化与 WebSocket
// ==========================================

// 初始化时加载成就表和游戏配置
fetch('world/achievements.json')
    .then(res => res.json())
    .then(data => {
        ACHIEVEMENTS = data;
    })
    .catch(() => {
        // 兼容旧格式或本地开发
        ACHIEVEMENTS = {};
    });

// 加载游戏配置
fetch('/api/game/config')
    .then(res => res.json())
    .then(config => {
        if (config.semester) {
            CONFIG.SEMESTER_DURATIONS = config.semester.durations || {};
            CONFIG.SPEED_MODES = config.semester.speed_modes || {};
            CONFIG.DEFAULT_DURATION = config.semester.default_duration || 360;
        }
        if (config.cooldowns) {
            CONFIG.COOLDOWNS = config.cooldowns;
        }
    })
    .catch(err => {
        console.warn('加载游戏配置失败，使用默认值', err);
        // 兜底默认值
        CONFIG.SEMESTER_DURATIONS = {
            "1": 420, "2": 420, "3": 420, "4": 420,
            "5": 300, "6": 300, "7": 300, "8": 300
        };
        CONFIG.DEFAULT_DURATION = 360;
        CONFIG.SPEED_MODES = {
            "1.0": {"label": "正常速度", "multiplier": 1.0},
            "1.5": {"label": "1.5x 加速", "multiplier": 1.5},
            "2.0": {"label": "2x 加速", "multiplier": 2.0}
        };
    });

window.onload = initGame;

function initGame() {
    const token = typeof auth !== 'undefined' ? auth.getToken() : 'test_token';
    const baseUrl = typeof WS_BASE_URL !== 'undefined' ? WS_BASE_URL : 'ws://localhost:8000';
    ws = new WebSocket(`${baseUrl}/ws/game?token=${token}`);

    ws.onopen = () => {
        logEvent("系统", "已连接教务系统...", "text-success");
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
        case 'paused':
            isPaused = true;
            updatePauseButton();
            logEvent("系统", msg.msg || "游戏已暂停。", "text-warning");
            // 停止倒计时
            if (window.semesterTimerInterval) {
                clearInterval(window.semesterTimerInterval);
                window.semesterTimerInterval = null;
                window.timerRunning = false;
            }
            break;
        case 'resumed':
            isPaused = false;
            updatePauseButton();
            logEvent("系统", msg.msg || "游戏已继续。", "text-success");
            // 恢复倒计时（如果有数据）
            if (typeof startSemesterTimer === 'function' && typeof currentStats === 'object' && currentStats.semester_time_left) {
                startSemesterTimer(currentStats.semester_time_left);
            }
            break;
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

        case 'dingtalk_message':
            renderDingtalkMessage(msg.data);
            break;

        case 'achievement_unlocked':
            showToast(`🏆 解锁成就：${msg.data.name}`, msg.data.desc);
            break;

        case 'new_semester':
            // 1. 弹窗提示
            alert(`假期结束，${msg.data.semester_name} 开始了！`);

            // 2. 软重置
            courseMetadata = [];
            currentCourseStates = {};

            // 3. 清空日志
            clearLog();
            logEvent("系统", `=== 欢迎来到 ${msg.data.semester_name} ===`, "text-success fw-bold");

            // 4. 重置倒计时器
            const timerEl = document.getElementById('semester-timer');
            if (timerEl) timerEl.innerText = "--:--";
            // 停止旧的计时器循环（如有）
            if (window.semesterTimerInterval) {
                clearInterval(window.semesterTimerInterval);
                window.semesterTimerInterval = null;
                window.timerRunning = false;
            }

            // 5. 假期事件弹窗（如有）
            if (msg.data.holiday_event) {
                // showRandomEventModal(msg.data.holiday_event);
            }
            break;
            
        case 'graduation':
            showGraduationModal(msg.data);
            break;
    // 毕业总结弹窗
    function showGraduationModal(data) {
        // 移除已存在的弹窗
        let old = document.getElementById('graduation-modal');
        if (old) old.remove();
        const modal = document.createElement('div');
        modal.id = 'graduation-modal';
        const stats = data.final_stats || {};
        // 直接用全局 ACHIEVEMENTS
        let achievementsHtml = '';
        if (Array.isArray(stats.achievements) && stats.achievements.length > 0) {
            achievementsHtml = `<h5 class='mt-4'>成就展示</h5><div class='row'>` +
                stats.achievements.map(code => {
                    const ach = (ACHIEVEMENTS && ACHIEVEMENTS[code]) ? ACHIEVEMENTS[code] : {name: code, desc: '', icon: '🏅'};
                    return `<div class='col-6 mb-2'><div class='border rounded p-2 bg-white d-flex align-items-center'>
                        <span style='font-size:2rem;margin-right:10px;'>${ach.icon}</span>
                        <div><b>${ach.name}</b><br><span class='text-muted small'>${ach.desc}</span></div>
                    </div></div>`;
                }).join('') + '</div>';
        }
        modal.innerHTML = `
        <div class="modal fade show" style="display:block;background:rgba(0,0,0,0.85);z-index:9999;" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content p-4">
                    <div class="modal-header border-0">
                        <h2 class="modal-title w-100 text-center">🎓 毕业总结</h2>
                    </div>
                    <div class="modal-body">
                        <h4 class="text-success text-center mb-3">${data.msg || '恭喜毕业！'}</h4>
                        <div class="row">
                            <div class="col-md-6">
                                <h5>结业数据</h5>
                                <ul class="list-group">
                                    <li class="list-group-item">专业：<b>${stats.major || ''}</b></li>
                                    <li class="list-group-item">GPA：<b>${stats.gpa || ''}</b></li>
                                    <li class="list-group-item">能力：IQ <span>${stats.iq || ''}</span> / EQ <span>${stats.eq || ''}</span></li>
                                    <li class="list-group-item">心态：<span>${stats.sanity || ''}</span></li>
                                    <li class="list-group-item">精力：<span>${stats.energy || ''}</span></li>
                                </ul>
                                ${achievementsHtml}
                            </div>
                            <div class="col-md-6">
                                <h5>AI文言文总结</h5>
                                <div class="border rounded p-3 bg-light" id="wenyan-report" style="min-height: 120px;white-space:pre-line;">${data.wenyan_report || '生成中...'}</div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer border-0 justify-content-center">
                        <button class="btn btn-primary" onclick="location.reload()">重开人生</button>
                    </div>
                </div>
            </div>
        </div>`;
        document.body.appendChild(modal);
    }
    }
}

// ==========================================
// 修复后的 updateGameView
// ==========================================
function updateGameView(stats, courses, states) {
    if (stats) {
        currentStats = stats;
        updateStatsUI(stats);

        // 【关键修复】: 如果当前没有课程元数据（比如用户刷新了页面），
        // 尝试从 stats.course_info_json 中恢复。
        // 后端 Redis 的 stats 里一直存着这份数据，tick 消息也会带过来。
        if (courseMetadata.length === 0 && stats.course_info_json) {
            try {
                console.log("正在从心跳包恢复课程数据...");
                courseMetadata = JSON.parse(stats.course_info_json);
            } catch (e) {
                console.error("课程数据解析失败:", e);
            }
        }
    }
    
    if (states) {
        currentCourseStates = states;
    }

    if (courses) {
        // 缓存最新的课程进度
        currentStats.courses = courses; 
    }

    // 只有当元数据获取成功后，才开始渲染
    if (courseMetadata.length > 0) {
        const safeCourses = courses || currentStats.courses || {};
        
        // 如果后端没传 states，给个默认全“摸”的状态
        if (!currentCourseStates || Object.keys(currentCourseStates).length === 0) {
             courseMetadata.forEach(c => currentCourseStates[c.id] = 1);
        }
        
        // 渲染课程列表（这也会触发考试控制台的渲染）
        renderCourseList(safeCourses, currentCourseStates);
        
        // 更新精力预估
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

// ==========================================
// 6. 钉钉/IM 模块渲染
// ==========================================

function renderDingtalkMessage(msg) {
    const container = document.getElementById('ding-messages');
    if (!container) return;

    // 1. 如果是第一条消息，清空“暂无消息”的占位符
    if (container.querySelector('.text-center.text-muted')) {
        container.innerHTML = '';
    }

    // 2. 根据角色决定头像颜色和图标
    const roleConfig = {
        "counselor": { bg: "#FF9F43", icon: "导", name: "辅导员" },
        "teacher":   { bg: "#54a0ff", icon: "师", name: "老师" },
        "student":   { bg: "#1dd1a1", icon: "生", name: "同学" },
        "system":    { bg: "#8395a7", icon: "系", name: "系统通知" }
    };
    
    const config = roleConfig[msg.role] || roleConfig["student"];
    const senderName = msg.sender || config.name;
    const isUrgent = msg.is_urgent;

    // 3. 构建消息 HTML
    const msgDiv = document.createElement('div');
    msgDiv.className = "d-flex align-items-start mb-3 ding-msg-anim";
    
    // 紧急消息加个红色边框效果
    const bubbleStyle = isUrgent ? "border: 1px solid #ff6b6b; background: #fff0f0;" : "background: white; border: 1px solid #eee;";
    const urgentBadge = isUrgent ? `<span class="badge bg-danger ms-2" style="font-size:0.6rem">紧急</span>` : "";

    msgDiv.innerHTML = `
        <div class="flex-shrink-0">
            <div class="rounded-circle d-flex align-items-center justify-content-center text-white fw-bold shadow-sm" 
                 style="width: 36px; height: 36px; background-color: ${config.bg}; font-size: 0.85rem;">
                ${config.icon}
            </div>
        </div>
        <div class="flex-grow-1 ms-2">
            <div class="d-flex align-items-center mb-1">
                <span class="fw-bold text-dark" style="font-size: 0.85rem;">${senderName}</span>
                <span class="text-muted ms-2" style="font-size: 0.7rem;">刚刚</span>
                ${urgentBadge}
            </div>
            <div class="p-2 rounded shadow-sm position-relative" style="${bubbleStyle} border-radius: 0 8px 8px 8px;">
                <p class="mb-0 text-dark" style="font-size: 0.9rem; line-height: 1.4;">
                    ${msg.content}
                </p>
            </div>
        </div>
    `;

    // 4. 追加并滚动到底部
    container.appendChild(msgDiv);
    
    // 平滑滚动到底部
    const cardBody = container.parentElement;
    cardBody.scrollTo({ top: cardBody.scrollHeight, behavior: 'smooth' });

    // 5. 更新未读红点 (简单视觉反馈)
    const badge = document.getElementById('ding-unread');
    if (badge) {
        let count = parseInt(badge.innerText) || 0;
        badge.innerText = count + 1;
        badge.style.display = 'inline-block';
        
        // 加上跳动动画
        badge.classList.add('pulse-animation');
        setTimeout(() => badge.classList.remove('pulse-animation'), 1000);
    }
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
    // 乐观更新本地状态，立即刷新UI
    if (!currentCourseStates) currentCourseStates = {};
    currentCourseStates[courseId] = newState;
    renderCourseList(currentStats.courses || {}, currentCourseStates);
    // 发送到后端
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
    
    // 如果是摸鱼动作，检查冷却
    if (type === 'relax' && target) {
        const btn = document.getElementById(`btn-${target}`);
        if (btn && btn.disabled) {
            return; // 冷却中，不发送
        }
    }
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: type,
            target: target
        }));
        isCooldown = true;
        setTimeout(() => { isCooldown = false; }, 500);
        
        // 如果是摸鱼动作，记录冷却开始时间
        if (type === 'relax' && target && CONFIG.COOLDOWNS[target]) {
            relaxCooldowns[target] = Date.now();
            updateRelaxButtons();
        }
    }
}
function updatePauseButton() {
    const btn = document.getElementById('pause-resume-btn');
    if (!btn) return;
    if (isPaused) {
        btn.classList.remove('btn-outline-danger');
        btn.classList.add('btn-outline-success');
        btn.textContent = '▶️ 继续游戏';
        btn.onclick = () => sendAction('resume');
    } else {
        btn.classList.remove('btn-outline-success');
        btn.classList.add('btn-outline-danger');
        btn.textContent = '⏸️ 暂停游戏';
        btn.onclick = () => sendAction('pause');
    }
}
window.updatePauseButton = updatePauseButton;

// ==========================================
// 3.1. 摸鱼按钮冷却管理
// ==========================================

function updateRelaxButtons() {
    const buttons = {
        gym: { id: 'btn-gym', label: '🏋️‍♂️ 健身房' },
        game: { id: 'btn-game', label: '🎮 打游戏' },
        cc98: { id: 'btn-cc98', label: '🌊 刷CC98' },
        walk: { id: 'btn-walk', label: '🚶 散步启真湖' }
    };
    
    const now = Date.now();
    
    for (const [action, config] of Object.entries(buttons)) {
        const btn = document.getElementById(config.id);
        if (!btn) continue;
        
        const cooldownTime = CONFIG.COOLDOWNS[action];
        const lastUse = relaxCooldowns[action];
        
        if (!lastUse || !cooldownTime) {
            // 无冷却记录或配置，保持可用
            btn.disabled = false;
            btn.textContent = config.label + ' (+精力/心态)'.replace('+精力/心态', 
                action === 'gym' ? '(+精力/心态)' : 
                action === 'game' ? '(+心态 -精力)' : 
                action === 'cc98' ? '(随机心态)' : '(-压力)');
            continue;
        }
        
        const elapsed = (now - lastUse) / 1000;
        const remaining = Math.max(0, cooldownTime - elapsed);
        
        if (remaining > 0) {
            btn.disabled = true;
            btn.textContent = `${config.label} (${Math.ceil(remaining)}s)`;
        } else {
            btn.disabled = false;
            btn.textContent = config.label + ' (+精力/心态)'.replace('+精力/心态', 
                action === 'gym' ? '(+精力/心态)' : 
                action === 'game' ? '(+心态 -精力)' : 
                action === 'cc98' ? '(随机心态)' : '(-压力)');
        }
    }
}

// 每秒更新一次按钮状态
setInterval(updateRelaxButtons, 1000);

// ==========================================
// 4. 数值计算与展示
// ==========================================

// 考试控制台：嵌入右侧栏版本
// static/js/game.js

// 【修复】考试控制台渲染：增量更新，防止倒计时被重置
function renderExamConsole(progress) {
    // 1. 获取侧边栏容器 (ID 修正为 exam-console-container)
    const container = document.getElementById('exam-console-container');
    if (!container) return; // 如果 HTML 里没写这个容器，就放弃渲染

    // 2. 检查是否已经渲染过框架（通过检查是否存在特定内部ID）
    const progressEl = document.getElementById('console-progress-val');
    
    // 3. 计算按钮状态
    let examBtnClass = progress >= 80 ? 'btn btn-danger w-100 pulse-animation fw-bold py-2' : 'btn btn-secondary w-100 disabled';
    let examBtnTip = progress >= 80 ? '当前进度已达标！' : '（建议进度 >80% 后考试）';

    // A. 如果是第一次渲染，生成完整 HTML
    // 注意：这里移除了 fixed 定位和固定宽度，改为普通的 Card
    if (!progressEl) {
        container.innerHTML = `
            <div class="card border-danger shadow-sm">
                <div class="card-header bg-danger text-white d-flex justify-content-between align-items-center py-2">
                    <span class="fw-bold">🔥 学期冲刺</span>
                    <span class="badge bg-white text-danger rounded-pill">No.1</span>
                </div>
                <div class="card-body text-center p-3 bg-light-danger">
                    <div class="mb-3">
                        <span class="text-muted small text-uppercase fw-bold" style="letter-spacing:1px;">总平均进度</span>
                        <h2 class="display-5 fw-bold mb-0 text-dark" id="console-progress-val">${progress.toFixed(1)}%</h2>
                        <div class="progress mt-2" style="height: 6px;">
                            <div id="console-progress-bar" class="progress-bar bg-danger" role="progressbar" style="width: ${progress}%"></div>
                        </div>
                    </div>
                    
                    <div class="alert alert-warning py-2 mb-3 d-flex align-items-center justify-content-center">
                        <span class="fs-5 me-2">⏳</span>
                        <div>
                            <div class="small text-muted" style="line-height:1;">距离期末</div>
                            <span id="semester-timer" class="fw-bold fs-5 text-danger" style="font-family:monospace;">--:--</span>
                        </div>
                    </div>

                    <button id="btn-take-exam" onclick="takeFinalExam()" class="${examBtnClass}">
                        ✍️ 参加期末考试
                    </button>
                    <small id="exam-tip" class="d-block mt-2 text-muted" style="font-size: 0.75rem">${examBtnTip}</small>
                </div>
            </div>
        `;
        // 只有第一次渲染框架时，才启动计时器
        initSemesterTimer();
    } 
    // B. 如果已经存在，只更新数值和样式 (增量更新)
    else {
        // 更新进度文字
        progressEl.innerText = `${progress.toFixed(1)}%`;
        
        // 更新进度条宽度
        const bar = document.getElementById('console-progress-bar');
        if (bar) bar.style.width = `${progress}%`;
        
        // 更新按钮样式
        const btn = document.getElementById('btn-take-exam');
        if (btn) btn.className = examBtnClass;
        
        // 更新提示文字
        const tip = document.getElementById('exam-tip');
        if (tip) tip.innerText = examBtnTip;
    }
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
    
    // 更新学习效率显示
    updateEfficiencyDisplay(stats.sanity, stats.stress);
}

// 计算并更新学习效率显示
function updateEfficiencyDisplay(sanity, stress) {
    const efficiencyEl = document.getElementById('efficiency-value');
    const hintEl = document.getElementById('efficiency-hint');
    if (!efficiencyEl || !hintEl) return;
    
    // 计算心态修正
    let sanityFactor = 1.0;
    if (sanity < 20) {
        sanityFactor = 0.6;
    } else if (sanity < 50) {
        sanityFactor = 1 - (50 - sanity) * 0.013;
    } else if (sanity >= 80) {
        sanityFactor = 1.2;
    } else if (sanity > 50) {
        sanityFactor = 1 + (sanity - 50) * 0.007;
    }
    
    // 计算压力修正
    let stressFactor = 1.0;
    if (stress >= 40 && stress <= 70) {
        stressFactor = 1.3;
    } else if ((stress >= 20 && stress < 40) || (stress > 70 && stress <= 90)) {
        stressFactor = 0.85;
    } else {
        stressFactor = 0.6;
    }
    
    // 总效率
    const efficiency = sanityFactor * stressFactor;
    const percent = Math.round(efficiency * 100);
    
    efficiencyEl.textContent = `${percent}%`;
    
    // 根据效率调整颜色和提示
    if (efficiency >= 1.4) {
        efficiencyEl.className = 'fw-bold text-success';
        hintEl.textContent = '🔥 状态极佳！学习效率爆表！';
        hintEl.style.color = '#198754';
    } else if (efficiency >= 1.2) {
        efficiencyEl.className = 'fw-bold text-primary';
        hintEl.textContent = '✨ 状态优秀，保持心态和压力在最佳区间';
        hintEl.style.color = '#0d6efd';
    } else if (efficiency >= 0.9) {
        efficiencyEl.className = 'fw-bold text-info';
        hintEl.textContent = '😐 状态一般，注意调整心态/压力';
        hintEl.style.color = '#0dcaf0';
    } else if (efficiency >= 0.7) {
        efficiencyEl.className = 'fw-bold text-warning';
        hintEl.textContent = '⚠️ 学习效率下降，建议摸鱼调整状态';
        hintEl.style.color = '#ffc107';
    } else {
        efficiencyEl.className = 'fw-bold text-danger';
        hintEl.textContent = '💀 状态崩溃！急需休息恢复';
        hintEl.style.color = '#dc3545';
    }
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
    // 如果已经有计时器在跑，先清除，防止速度加倍
    if (window.semesterTimerInterval) {
        clearInterval(window.semesterTimerInterval);
    }
    window.timerRunning = true;
    
    // 从配置获取当前学期时长
    const currentSemester = currentStats.semester || 1;
    let baseDuration = CONFIG.SEMESTER_DURATIONS[currentSemester] || CONFIG.DEFAULT_DURATION || 360;
    
    // 应用速度倍率（加速模式）
    let remain = Math.floor(baseDuration / CONFIG.currentSpeedMultiplier);

    const updateDisplay = () => {
        const el = document.getElementById('semester-timer');
        if (el) {
            let min = Math.floor(remain / 60);
            let sec = remain % 60;
            el.innerText = `${min}:${sec.toString().padStart(2, '0')}`;
        }
    };

    updateDisplay();

    // 把 ID 存到 window 对象上，方便切学期时清除
    window.semesterTimerInterval = setInterval(() => {
        remain--;
        if (remain >= 0) updateDisplay();
        if (remain === 0) {
            clearInterval(window.semesterTimerInterval);
            takeFinalExam(); 
        }
    }, 1000);
}

// ==========================================
// 游戏速度控制
// ==========================================

function setGameSpeed(multiplier) {
    CONFIG.currentSpeedMultiplier = multiplier;
    
    // 更新按钮状态
    ['1.0', '1.5', '2.0'].forEach(speed => {
        const btn = document.getElementById(`speed-${speed}`);
        if (btn) {
            if (parseFloat(speed) === multiplier) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        }
    });
    
    // 如果有正在运行的计时器，重新启动（应用新速度）
    if (window.semesterTimerInterval) {
        initSemesterTimer();
    }
    
    logEvent("系统", `游戏速度已调整为 ${multiplier}x`, "text-info");
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
                    <p class="text-muted">折姜大学的生活真是充满了变数啊</p>
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