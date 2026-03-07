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
    // ✨ 新增：游戏当前所处的阶段
    // 可能的值: 'loading' (连接中), 'admission' (开局选择), 'playing' (主游戏), 'ended' (游戏结束)
    const currentPhase = ref('loading')
    // ✨ 新增：全局 Toast 状态
    const toast = ref(null)
    // ==========================================

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

    // ✨ 新增：结局相关状态
    const endType = ref(null) // 'game_over' (坏结局) 或 'graduation' (好结局)
    const endData = ref({})   // 存储后端的总结数据和 LLM 生成的文言文

    // 🌟 新增：标记是否正在执行退出保存流程
    const isPendingExit = ref(false)

    function triggerEndGame(type, data) {
        endType.value = type
        endData.value = data || {}
        currentPhase.value = 'ended' // 切换到大结局场景
        closeModal() // 确保没有任何弹窗残留
    }

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

    // 新增：切换场景的 Action
    function setPhase(phase) {
        currentPhase.value = phase
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

    // ✨ 新增：显示 Toast 的方法
    function showToast(message, type = 'success') {
        toast.value = { message, type }
        // 3秒后自动消失
        setTimeout(() => {
            if (toast.value && toast.value.message === message) {
                toast.value = null
            }
        }, 3000)
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
        currentPhase,
        setPhase, // ✨ 新增：暴露切换场景的方法
        toast, showToast, // ✨ 新增：暴露 Toast 状态和方法
        endType, endData, triggerEndGame, // ✨ 新增：暴露结局相关状态和方法
        
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
        isPendingExit,

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