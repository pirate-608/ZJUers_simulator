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

// ==========================================
// 全局变量（供HTML内联事件使用）
// ==========================================
let wsManager;
let courseManager;
let examConsole;
let eventHandler;
let actionCooldown = false;

// ==========================================
// 初始化
// ==========================================
window.addEventListener('DOMContentLoaded', async () => {
    // 加载配置和数据
    await Promise.all([
        loadServerConfig(),
        loadAchievements()
    ]);

    // 初始化WebSocket
    wsManager = new WebSocketManager((msg) => eventHandler.handleServerMessage(msg));

    // 初始化各个管理器
    courseManager = new CourseManager(wsManager);
    examConsole = new ExamConsole(wsManager);
    eventHandler = new EventHandler(wsManager, courseManager, examConsole);

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

    console.log('[Main] Game initialized');
});

// ==========================================
// 全局函数导出（供HTML调用）
// ==========================================
window.sendAction = function (type, target) {
    if (actionCooldown) return;

    if (type === 'relax' && target) {
        const btn = document.getElementById(`btn-${target}`);
        if (btn && btn.disabled) return;
    }

    if (type === 'pause') {
        gameState.setPaused(true);
        uiManager.updatePauseButton();
    } else if (type === 'resume') {
        gameState.setPaused(false);
        uiManager.updatePauseButton();
    }

    wsManager.send({ action: type, target: target });
    actionCooldown = true;
    setTimeout(() => { actionCooldown = false; }, 500);

    if (type === 'relax' && target && CONFIG.COOLDOWNS[target]) {
        gameState.updateRelaxCooldown(target);
        uiManager.updateRelaxButtons();
    }
};

window.changeCourseState = function (courseId, newState) {
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
