// ==========================================
// 游戏配置模块
// ==========================================

export const CONFIG = {
    COEFFS: {
        0: { name: "摆", emoji: "💤", drain: 0.0, class: "btn-outline-secondary", activeClass: "btn-secondary" },
        1: { name: "摸", emoji: "😐", drain: 0.8, class: "btn-outline-primary", activeClass: "btn-primary" },
        2: { name: "卷", emoji: "🔥", drain: 3.0, class: "btn-outline-danger", activeClass: "btn-danger" }
    },
    BASE_DRAIN: 2.0,
    COOLDOWNS: {
        gym: 60,
        walk: 45,
        game: 30,
        cc98: 15
    },
    SEMESTER_DURATIONS: {},
    SPEED_MODES: {},
    DEFAULT_DURATION: 360,
    currentSpeedMultiplier: 1.0
};

// 加载服务器配置
export async function loadServerConfig() {
    try {
        const response = await fetch('/api/game/config');
        const config = await response.json();

        if (config.semester) {
            CONFIG.SEMESTER_DURATIONS = config.semester.durations || {};
            CONFIG.SPEED_MODES = config.semester.speed_modes || {};
            CONFIG.DEFAULT_DURATION = config.semester.default_duration || 360;
        }
        if (config.cooldowns) {
            CONFIG.COOLDOWNS = config.cooldowns;
        }

        console.log('[Config] Server configuration loaded');
    } catch (err) {
        console.warn('[Config] Failed to load server config, using defaults', err);
        // 兜底默认值
        CONFIG.SEMESTER_DURATIONS = {
            "1": 420, "2": 420, "3": 420, "4": 420,
            "5": 300, "6": 300, "7": 300, "8": 300
        };
        CONFIG.DEFAULT_DURATION = 360;
        CONFIG.SPEED_MODES = {
            "1.0": { "label": "正常速度", "multiplier": 1.0 },
            "1.5": { "label": "1.5x 加速", "multiplier": 1.5 },
            "2.0": { "label": "2x 加速", "multiplier": 2.0 }
        };
    }
}
