// ==========================================
// 事件处理模块 - 消息分发与模态框处理
// ==========================================

import { gameState } from './gameState.js';
import { uiManager } from './uiManager.js';
import { logEvent, updateUserInfo, clearLog, showToast } from './utils.js';
import { dingTalkManager } from './dingTalkManager.js';

export class EventHandler {
    constructor(wsManager, courseManager, examConsole) {
        this.wsManager = wsManager;
        this.courseManager = courseManager;
        this.examConsole = examConsole;
    }

    handleServerMessage(msg) {
        switch (msg.type) {
            case 'pong':
                break;

            case 'paused':
                gameState.setPaused(true);
                uiManager.updatePauseButton();
                logEvent("系统", msg.msg || "游戏已暂停。", "text-warning");
                this.examConsole.stopTimer();
                break;

            case 'resumed':
                gameState.setPaused(false);
                uiManager.updatePauseButton();
                logEvent("系统", msg.msg || "游戏已继续。", "text-success");
                // 恢复时需要等待下一次tick消息推送最新倒计时
                break;

            case 'init':
                updateUserInfo(msg.data);
                if (msg.data.course_info_json) {
                    gameState.setCourseMetadata(JSON.parse(msg.data.course_info_json));
                }
                this.updateGameView(msg.data, null, null, msg.semester_time_left);
                break;

            case 'tick':
                this.updateGameView(msg.stats, msg.courses, msg.course_states, msg.semester_time_left);
                break;

            case 'event':
                logEvent("事件", msg.data.desc, "text-primary");
                break;

            case 'game_over':
                this.showGameOverModal(msg.reason, msg.restartable);
                break;

            case 'semester_summary':
                this.showTranscript(msg.data);
                break;

            case 'random_event':
                this.showRandomEventModal(msg.data);
                break;

            case 'dingtalk_message':
                dingTalkManager.renderDingtalkMessage(msg.data);
                break;

            case 'achievement_unlocked':
                showToast(`🏆 解锁成就：${msg.data.name}`, msg.data.desc);
                break;

            case 'new_semester':
                alert(`假期结束，${msg.data.semester_name} 开始了！`);
                gameState.setCourseMetadata([]);
                gameState.updateCourseStates({});
                clearLog();
                logEvent("系统", `=== 欢迎来到 ${msg.data.semester_name} ===`, "text-success fw-bold");

                const timerEl = document.getElementById('semester-timer');
                if (timerEl) timerEl.innerText = "--:--";
                this.examConsole.stopTimer();
                break;

            case 'graduation':
                this.showGraduationModal(msg.data);
                break;
        }
    }

    updateGameView(stats, courses, states, serverTimeLeft = null) {
        if (stats) {
            gameState.updateStats(stats);
            uiManager.updateStatsUI(stats);
            gameState.restoreCourseMetadataFromStats();
        }

        if (states) {
            gameState.updateCourseStates(states);
        }

        if (courses) {
            stats.courses = courses;
        }

        const courseMetadata = gameState.getCourseMetadata();
        if (courseMetadata.length > 0) {
            const safeCourses = courses || stats.courses || {};
            const currentStates = gameState.getCourseStates();

            if (!currentStates || Object.keys(currentStates).length === 0) {
                courseMetadata.forEach(c => gameState.setCourseState(c.id, 1));
            }

            const avgProgress = this.courseManager.renderCourseList(safeCourses, gameState.getCourseStates());
            this.examConsole.renderExamConsole(avgProgress);
            this.courseManager.updateEnergyProjection();

            // 使用服务器推送的倒计时更新计时器
            if (serverTimeLeft !== null && serverTimeLeft !== undefined && !gameState.isPaused()) {
                this.examConsole.initSemesterTimer(serverTimeLeft);
            }
        }
    }

    showGameOverModal(reason, restartable) {
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
                        ${restartable ? `<button onclick="window.restartGame()" class="btn btn-primary btn-lg px-5">🔄 重新开始</button>` : ''}
                        <button onclick="location.href='index.html'" class="btn btn-outline-secondary">退出</button>
                    </div>
                </div>
            </div>
        </div>`;
        document.body.appendChild(modal);
    }

    showTranscript(data) {
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
        if (gpaDisplay) gpaDisplay.innerText = data.gpa;

        try {
            const modalEl = document.getElementById('summaryModal');
            if (modalEl) {
                const modal = new bootstrap.Modal(modalEl);
                modal.show();
            }
        } catch (e) {
            console.error("Bootstrap Modal error", e);
        }
    }

    showRandomEventModal(eventData) {
        if (!eventData.options || eventData.options.length < 2) return;

        const choiceIdx = prompt(`【随机事件】${eventData.title}\n${eventData.desc}\n\n请输入 [0] 或 [1] 选择:\n0: ${eventData.options[0].text}\n1: ${eventData.options[1].text}`);

        if (choiceIdx === '0' || choiceIdx === '1') {
            const idx = parseInt(choiceIdx);
            this.wsManager.send({
                action: "event_choice",
                effects: eventData.options[idx].effects
            });
        }
    }

    showGraduationModal(data) {
        let old = document.getElementById('graduation-modal');
        if (old) old.remove();

        const modal = document.createElement('div');
        modal.id = 'graduation-modal';
        const stats = data.final_stats || {};
        const achievements = gameState.getAchievements() || {};

        let achievementsHtml = '';
        if (Array.isArray(stats.achievements) && stats.achievements.length > 0) {
            achievementsHtml = `<h5 class='mt-4'>成就展示</h5><div class='row'>` +
                stats.achievements.map(code => {
                    const ach = achievements[code] || { name: code, desc: '', icon: '🏅' };
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
                        <h4 class="text-success text-center mb-3">${data.msg || '恭喜毕业，每个折大人都灿若星辰！'}</h4>
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
                                <div class="border rounded p-3 bg-light" style="min-height: 120px;white-space:pre-line;">${data.wenyan_report || '生成中...'}</div>
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
