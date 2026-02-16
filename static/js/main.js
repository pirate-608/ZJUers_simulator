// ==========================================
// 主入口文件 - 模块组装与初始化
// ==========================================

import { CONFIG, loadServerConfig } from './modules/config.js';
import { gameState, loadAchievements } from './modules/gameState.js';
import { setupBeforeUnload, clearLog } from './modules/utils.js';
import { WebSocketManager } from './modules/websocket.js';
import { uiManager } from './modules/uiManager.js';
import { CourseManager } from './modules/courseManager.js';
import { ExamConsole } from './modules/examConsole.js';
import { EventHandler } from './modules/eventHandler.js';
import { SaveManager } from './modules/saveManager.js';

// ==========================================
// 全局变量（供HTML内联事件使用）
// ==========================================
let wsManager;
let courseManager;
let examConsole;
let eventHandler;
let saveManager;
let actionCooldown = false;
let driverInstance = null;
let driverTourStarted = false;
let tourLocked = false;

// ==========================================
// 初始化
// ==========================================
window.addEventListener('DOMContentLoaded', async () => {
    // 加载配置和数据
    await Promise.all([
        loadServerConfig(),
        loadAchievements()
    ]);

    // 初始化各个管理器
    courseManager = new CourseManager(null); // 先创建，稍后设置 wsManager
    examConsole = new ExamConsole(null);
    saveManager = new SaveManager(null);

    // 初始化 WebSocket（传入消息处理回调）
    wsManager = new WebSocketManager((msg) => eventHandler.handleServerMessage(msg));

    // 设置管理器之间的引用
    courseManager.wsManager = wsManager;
    examConsole.wsManager = wsManager;
    saveManager.wsManager = wsManager;

    // 初始化事件处理器
    eventHandler = new EventHandler(wsManager, courseManager, examConsole, saveManager);

    // 连接WebSocket
    wsManager.connect();

    // 设置页面关闭前提醒
    setupBeforeUnload(() => wsManager.getWebSocket());

    // 身份验证检查
    if (typeof auth !== 'undefined') {
        auth.checkLogin();
    }

    // 初始化 Bootstrap 工具提示
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    console.log('[Main] Game initialized with SaveManager');
});

// ==========================================
// 全局函数导出（供HTML调用）
// ==========================================
window.sendAction = function (type, target) {
    if (actionCooldown || tourLocked) return;

    if (type === 'relax' && target) {
        const btn = document.getElementById(`btn-${target}`);
        if (btn && btn.disabled) return;
    }

    // 不再在本地立即更新暂停状态，等待服务器返回消息后再更新
    console.log('[Main] Sending action:', type, target);

    wsManager.send({ action: type, target: target });
    actionCooldown = true;
    setTimeout(() => { actionCooldown = false; }, 500);

    if (type === 'relax' && target && CONFIG.COOLDOWNS[target]) {
        gameState.updateRelaxCooldown(target);
        uiManager.updateRelaxButtons();
    }
};

window.changeCourseState = function (courseId, newState) {
    if (tourLocked) return;
    courseManager.changeCourseState(courseId, newState);
};

window.takeFinalExam = function () {
    examConsole.takeFinalExam();
};

window.setGameSpeed = function (multiplier) {
    examConsole.setGameSpeed(multiplier);
};

window.nextSemester = function () {
    wsManager.send({ action: 'next_semester' });
};

window.restartGame = function () {
    wsManager.send({ action: 'restart' });
    const modal = document.getElementById('gameover-modal');
    if (modal) modal.remove();
};

window.clearLog = clearLog;

// 暴露 updatePauseButton 给外部调用
window.updatePauseButton = function () {
    uiManager.updatePauseButton();
};

// 暴露存档管理功能
window.showExitConfirm = function () {
    if (saveManager) {
        saveManager.showExitConfirmModal();
    }
};

window.saveGame = function () {
    if (saveManager) {
        saveManager.saveGame();
    }
};

// ========== 引导（driver.js） ==========
function setTourLock(flag) {
    tourLocked = flag;
}

function buildDriverSteps() {
    const strategyEl = document.querySelector('.course-list-panel .course-item .btn-group');
    const hudEl = document.getElementById('hud-bars');
    const relaxEl = document.querySelector('.relax-actions');
    const timerEl = document.getElementById('semester-timer') || document.getElementById('exam-console-container');
    const finishEl = document.getElementById('tour-finish-anchor');

    if (!strategyEl || !hudEl || !relaxEl || !timerEl || !finishEl) {
        return null;
    }

    return [
        {
            element: strategyEl,
            popover: {
                title: '选择策略：摆 / 摸 / 卷',
                description: '消耗与成长不同，点击按钮切换策略，影响精力消耗和擅长度提升。',
                side: 'right',
                align: 'start'
            }
        },
        {
            element: hudEl,
            popover: {
                title: '属性与最佳区间',
                description: '心态>50更稳，压力40-70最佳；精力/心态归零会 Game Over。',
                side: 'left',
                align: 'start'
            }
        },
        {
            element: relaxEl,
            popover: {
                title: '休闲与冷却',
                description: '健身/开黑/散步/CC98；冷却圈转动时不可用。',
                side: 'top',
                align: 'center'
            }
        },
        {
            element: timerEl,
            popover: {
                title: '学期计时与考试',
                description: '倒计时结束参加期末，分数→绩点→GPA；挂科扣心态，全过有奖励。',
                side: 'bottom',
                align: 'center'
            }
        },
        {
            element: finishEl,
            popover: {
                title: '开始前的三条提醒',
                description: '暂停后再操作更安全；心态<50有减益；压力40-70最佳区间。点击“完成”开始游戏。',
                side: 'center',
                align: 'center'
            }
        }
    ];
}

function ensureDriver() {
    if (driverInstance) return driverInstance;
    if (typeof Driver === 'undefined') return null;
    driverInstance = new Driver({
        animate: true,
        opacity: 0.45,
        allowClose: true,
        showButtons: true,
        nextBtnText: '确认',
        prevBtnText: '上一步',
        doneBtnText: '完成',
        closeBtnText: '跳过',
        onHighlightStarted: () => setTourLock(true),
        onReset: () => setTourLock(false)
    });
    return driverInstance;
}

function startDriverTour(force = false) {
    if (driverTourStarted && !force) return true;
    const driver = ensureDriver();
    if (!driver) return false;

    const steps = buildDriverSteps();
    if (!steps) return false;

    driver.defineSteps(steps);
    driver.start();
    driverTourStarted = true;
    setTourLock(true);
    return true;
}

// 允许事件处理器调用
window.startDriverTour = startDriverTour;
