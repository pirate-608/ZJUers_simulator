// ==========================================
// 考试控制台模块 - 考试控制台、倒计时、速度控制
// ==========================================

import { CONFIG } from './config.js';
import { gameState } from './gameState.js';
import { logEvent } from './utils.js';

export class ExamConsole {
    constructor(wsManager) {
        this.wsManager = wsManager;
        this.semesterTimerInterval = null;
        this.timerRunning = false;
    }

    renderExamConsole(progress) {
        const container = document.getElementById('exam-console-container');
        if (!container) return;

        const progressEl = document.getElementById('console-progress-val');

        let examBtnClass = progress >= 80 ? 'btn btn-danger w-100 pulse-animation fw-bold py-2' : 'btn btn-secondary w-100 disabled';
        let examBtnTip = progress >= 80 ? '当前进度已达标！' : '（建议进度 >80% 后考试）';

        if (!progressEl) {
            container.innerHTML = `
                <div class="text-center p-3" style="background-color: #fff5f5;">
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

                        <button id="btn-take-exam" onclick="window.takeFinalExam()" class="${examBtnClass}">
                            ✍️ 参加期末考试
                        </button>
                        <small id="exam-tip" class="d-block mt-2 text-muted" style="font-size: 0.75rem">${examBtnTip}</small>
                </div>
            `;
            this.initSemesterTimer();
        } else {
            progressEl.innerText = `${progress.toFixed(1)}%`;

            const bar = document.getElementById('console-progress-bar');
            if (bar) bar.style.width = `${progress}%`;

            const btn = document.getElementById('btn-take-exam');
            if (btn) btn.className = examBtnClass;

            const tip = document.getElementById('exam-tip');
            if (tip) tip.innerText = examBtnTip;
        }
    }

    initSemesterTimer(serverTimeLeft = null) {
        if (this.semesterTimerInterval) {
            clearInterval(this.semesterTimerInterval);
        }
        this.timerRunning = true;

        // 优先使用服务器推送的剩余时间，保证刷新页面后同步
        let remain;
        if (serverTimeLeft !== null && serverTimeLeft !== undefined) {
            remain = parseInt(serverTimeLeft);
        } else {
            // 兜底：使用本地配置计算（仅用于没有服务器数据时）
            const currentStats = gameState.getStats();
            const currentSemester = currentStats.semester_idx || 1;
            let baseDuration = CONFIG.SEMESTER_DURATIONS[currentSemester] || CONFIG.DEFAULT_DURATION || 360;
            remain = Math.floor(baseDuration / CONFIG.currentSpeedMultiplier);
        }

        const updateDisplay = () => {
            const el = document.getElementById('semester-timer');
            if (el) {
                let min = Math.floor(remain / 60);
                let sec = remain % 60;
                el.innerText = `${min}:${sec.toString().padStart(2, '0')}`;
            }
        };

        updateDisplay();

        this.semesterTimerInterval = setInterval(() => {
            remain--;
            if (remain >= 0) updateDisplay();
            if (remain === 0) {
                clearInterval(this.semesterTimerInterval);
                this.takeFinalExam();
            }
        }, 1000);
    }

    takeFinalExam() {
        if (!confirm("确定要参加期末考试吗？考试后将结算本学期GPA。")) return;
        this.wsManager.send({ action: 'exam', target: 'final' });
    }

    setGameSpeed(multiplier) {
        CONFIG.currentSpeedMultiplier = multiplier;

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

        if (this.semesterTimerInterval) {
            this.initSemesterTimer();
        }

        logEvent("系统", `游戏速度已调整为 ${multiplier}x`, "text-info");
    }

    stopTimer() {
        if (this.semesterTimerInterval) {
            clearInterval(this.semesterTimerInterval);
            this.semesterTimerInterval = null;
            this.timerRunning = false;
        }
    }
}
