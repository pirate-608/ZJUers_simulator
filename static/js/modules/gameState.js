// ==========================================
// 游戏状态管理模块
// ==========================================

export class GameState {
    constructor() {
        this.courseMetadata = [];
        this.currentStats = {};
        this.currentCourseStates = {};
        this.achievements = null;
        this.relaxCooldowns = {};
        this.isPaused = false;
    }

    setCourseMetadata(data) {
        this.courseMetadata = data;
    }

    getCourseMetadata() {
        return this.courseMetadata;
    }

    updateStats(stats) {
        this.currentStats = stats;
    }

    getStats() {
        return this.currentStats;
    }

    updateCourseStates(states) {
        this.currentCourseStates = states;
    }

    getCourseStates() {
        return this.currentCourseStates;
    }

    setCourseState(courseId, state) {
        this.currentCourseStates[courseId] = state;
    }

    setAchievements(data) {
        this.achievements = data;
    }

    getAchievements() {
        return this.achievements;
    }

    updateRelaxCooldown(action) {
        this.relaxCooldowns[action] = Date.now();
    }

    getRelaxCooldowns() {
        return this.relaxCooldowns;
    }

    setPaused(paused) {
        this.isPaused = paused;
    }

    isPaused() {
        return this.isPaused;
    }

    // 从stats中恢复课程元数据
    restoreCourseMetadataFromStats() {
        if (this.courseMetadata.length === 0 && this.currentStats.course_info_json) {
            try {
                console.log('[GameState] Restoring course metadata from stats');
                this.courseMetadata = JSON.parse(this.currentStats.course_info_json);
            } catch (e) {
                console.error('[GameState] Failed to parse course metadata:', e);
            }
        }
    }
}

// 单例实例
export const gameState = new GameState();

// 加载成就表
export async function loadAchievements() {
    try {
        const response = await fetch('world/achievements.json');
        const data = await response.json();
        gameState.setAchievements(data);
        console.log('[GameState] Achievements loaded');
    } catch (err) {
        console.warn('[GameState] Failed to load achievements', err);
        gameState.setAchievements({});
    }
}
