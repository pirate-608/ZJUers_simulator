import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useGameStore = defineStore('game', () => {
    // ==========================================
    // 1. State (状态数据) - 使用 ref 让数据变成响应式
    // ==========================================
    const courseMetadata = ref([])
    const currentStats = ref({})
    const currentCourseStates = ref({})
    const achievements = ref(null)
    const relaxCooldowns = ref({})
    const isPaused = ref(false)
    // ✨ 新增：用于替代 eventHandler.js 中的直接 DOM 操作
    const eventLogs = ref([])          // 存储左侧的事件日志
    const activeModal = ref(null)      // 当前激活的弹窗，如 'game_over', 'transcript', 'random_event', 'graduation'
    const modalData = ref({})          // 弹窗附带的数据
    const semesterTimeLeft = ref(null) // 学期倒计时
    const userInfo = ref({})           // 玩家基本信息
    // ✨ 新增：钉钉消息相关状态
    const dingMessages = ref([])       // 存储所有钉钉消息
    const unreadDingtalk = ref(0)      // 未读消息数量
    const gameSpeed = ref(1.0)         // 游戏倍速

    // 添加日志的方法
    function addLog(type, message, cssClass = '') {
        eventLogs.value.unshift({ id: Date.now(), type, message, cssClass })
        if (eventLogs.value.length > 50) eventLogs.value.pop() // 最多保留50条
    }

    // 控制弹窗的方法
    function showModal(modalName, data = {}) {
        activeModal.value = modalName
        modalData.value = data
    }

    function closeModal() {
        activeModal.value = null
        modalData.value = {}
    }

    // ==========================================
    // 2. Actions (修改状态的方法和业务逻辑)
    // ==========================================
    
    // 注意：在 Pinia 中，对于简单的赋值，你其实可以直接在组件里写 store.isPaused = true
    // 但保留这些 setter 方法可以方便后续添加复杂的验证逻辑
    
    function setCourseMetadata(data) {
        courseMetadata.value = data
    }

    function updateStats(stats) {
        currentStats.value = stats
    }

    function updateCourseStates(states) {
        currentCourseStates.value = states
    }

    function setCourseState(courseId, state) {
        currentCourseStates.value[courseId] = state
    }

    function setAchievements(data) {
        achievements.value = data
    }

    function updateRelaxCooldown(action) {
        relaxCooldowns.value[action] = Date.now()
    }

    function setPaused(paused) {
        isPaused.value = paused
    }

    // ✨ 新增：处理钉钉消息的方法
    function addDingMessage(msg) {
        dingMessages.value.push(msg)
        // 注意：这里先简单地自增未读数，具体的清零逻辑我们会在 Vue 组件里根据 Tab 状态处理
        unreadDingtalk.value++ 
    }

    function clearUnreadDingtalk() {
        unreadDingtalk.value = 0
    }

    function clearEventLogs() {
        eventLogs.value = []
    }

    // 核心逻辑：从 stats 中恢复课程元数据
    function restoreCourseMetadataFromStats() {
        if (courseMetadata.value.length === 0 && currentStats.value.course_info_json) {
            try {
                console.log('[GameStore] Restoring course metadata from stats')
                courseMetadata.value = JSON.parse(currentStats.value.course_info_json)
            } catch (e) {
                console.error('[GameStore] Failed to parse course metadata:', e)
            }
        }
    }

    // 异步逻辑：加载成就表
    async function loadAchievements() {
        try {
            // 💡 Vite 提示：把后端的 world 文件夹拷贝到新前端的 public/ 目录下
            // 这样 fetch('/world/achievements.json') 就能直接获取到了
            const response = await fetch('/world/achievements.json') 
            const data = await response.json()
            achievements.value = data
            console.log('[GameStore] Achievements loaded')
        } catch (err) {
            console.warn('[GameStore] Failed to load achievements', err)
            achievements.value = {}
        }
    }

    // ==========================================
    // 3. 返回暴露给外部使用的数据和方法
    // ==========================================
    return {
        // State
        courseMetadata,
        currentStats,
        currentCourseStates,
        achievements,
        relaxCooldowns,
        isPaused,
        
        // Actions
        setCourseMetadata,
        updateStats,
        updateCourseStates,
        setCourseState,
        setAchievements,
        updateRelaxCooldown,
        setPaused,
        restoreCourseMetadataFromStats,
        loadAchievements, 

        eventLogs, 
        clearEventLogs,
        dingMessages, unreadDingtalk, gameSpeed,
        addDingMessage, clearUnreadDingtalk,
        activeModal, 
        modalData, 
        semesterTimeLeft, 
        userInfo,
        addLog, 
        showModal, 
        closeModal
    }
})