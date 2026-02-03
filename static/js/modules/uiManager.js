// ==========================================
// UI 管理模块 - 状态条、效率显示、摸鱼按钮
// ==========================================

import { CONFIG } from './config.js';
import { gameState } from './gameState.js';

export class UIManager {
    updateStatsUI(stats) {
        this.setBar('energy', stats.energy);
        this.setBar('sanity', stats.sanity);
        this.setBar('stress', stats.stress);

        ['iq', 'eq', 'luck', 'reputation'].forEach(k => {
            const el = document.getElementById(`val-${k}`);
            if (el) el.innerText = stats[k] || 0;
        });

        this.updateEfficiencyDisplay(stats.sanity, stats.stress);

        // 更新GPA显示
        const gpaEl = document.getElementById('gpa-display');
        if (gpaEl && stats.gpa) {
            gpaEl.innerText = stats.gpa;
        }
    }

    setBar(id, val, max = 100) {
        const v = parseInt(val) || 0;
        const percent = Math.min(100, Math.max(0, (v / max) * 100));

        const bar = document.getElementById(`bar-${id}`);
        const text = document.getElementById(`val-${id}`);

        if (bar) bar.style.width = `${percent}%`;
        if (text) text.innerText = `${v}/${max}`;

        if (id === 'energy' && bar) {
            bar.className = v < 20 ? 'progress-bar bg-danger' :
                (v < 50 ? 'progress-bar bg-warning' : 'progress-bar bg-success');
        }
    }

    updateEfficiencyDisplay(sanity, stress) {
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

        const efficiency = sanityFactor * stressFactor;
        const percent = Math.round(efficiency * 100);

        efficiencyEl.textContent = `${percent}%`;

        if (efficiency >= 1.4) {
            efficiencyEl.className = 'fw-bold text-success';
            hintEl.textContent = '🔥 状态极佳';
            hintEl.style.color = '#198754';
        } else if (efficiency >= 1.2) {
            efficiencyEl.className = 'fw-bold text-primary';
            hintEl.textContent = '✨ 状态优秀';
            hintEl.style.color = '#0d6efd';
        } else if (efficiency >= 0.9) {
            efficiencyEl.className = 'fw-bold text-info';
            hintEl.textContent = '😐 状态一般';
            hintEl.style.color = '#0dcaf0';
        } else if (efficiency >= 0.7) {
            efficiencyEl.className = 'fw-bold text-warning';
            hintEl.textContent = '⚠️ 需要调整';
            hintEl.style.color = '#ffc107';
        } else {
            efficiencyEl.className = 'fw-bold text-danger';
            hintEl.textContent = '💀 急需休息';
            hintEl.style.color = '#dc3545';
        }
    }

    updateRelaxButtons() {
        const buttons = {
            gym: { id: 'btn-gym', icon: '🏋️‍♂️', name: '健身房' },
            game: { id: 'btn-game', icon: '🎮', name: '打游戏' },
            cc98: { id: 'btn-cc98', icon: '🌊', name: '刷CC98' },
            walk: { id: 'btn-walk', icon: '🚶', name: '散步启真湖' }
        };

        const now = Date.now();
        const cooldowns = gameState.getRelaxCooldowns();

        for (const [action, config] of Object.entries(buttons)) {
            const btn = document.getElementById(config.id);
            if (!btn) continue;

            const cooldownTime = CONFIG.COOLDOWNS[action];
            const lastUse = cooldowns[action];

            if (!lastUse || !cooldownTime) {
                btn.disabled = false;
                btn.textContent = `${config.icon} ${config.name}`;
                continue;
            }

            const elapsed = (now - lastUse) / 1000;
            const remaining = Math.max(0, cooldownTime - elapsed);

            if (remaining > 0) {
                btn.disabled = true;
                btn.textContent = `${config.icon} ${config.name} (${Math.ceil(remaining)}s)`;
            } else {
                btn.disabled = false;
                btn.textContent = `${config.icon} ${config.name}`;
            }
        }
    }

    updatePauseButton() {
        const btn = document.getElementById('pause-resume-btn');
        if (!btn) return;

        if (gameState.isPaused) {
            btn.classList.remove('btn-outline-danger');
            btn.classList.add('btn-outline-success');
            btn.textContent = '▶️ 继续游戏';
        } else {
            btn.classList.remove('btn-outline-success');
            btn.classList.add('btn-outline-danger');
            btn.textContent = '⏸️ 暂停游戏';
        }
    }
}

export const uiManager = new UIManager();

// 启动定时更新摸鱼按钮
setInterval(() => uiManager.updateRelaxButtons(), 1000);
