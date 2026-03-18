import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export const useGameStore = defineStore('game', () => {
    // --- 核心状态 ---
    const currentPhase = ref('login') // login, admission, playing
    const userInfo = ref({})
    
    // 🌟 修复：使用 reactive 初始化，确保所有后端可能发来的核心属性都是响应式的！
    // 坚决使用你后端的字段名：iq, eq, energy, sanity, gpa
    const currentStats = reactive({
        username: '',
        major: '',
        major_abbr: '',
        semester: '大一秋冬',
        semester_idx: 1,
        semester_start_time: 0,
        energy: 100,
        sanity: 80,
        stress: 0,
        iq: 100,
        eq: 100,
        luck: 50,
        gpa: 0.0,
        highest_gpa: 0.0,
        reputation: 0,
        efficiency: 100,
        courses: {} // 存放实时的掌握度进度
    })

    const courseMetadata = ref([]) // 存放课程的静态信息 (名称、学分、描述)
    const semesterTimeLeft = ref(0)
    const isPaused = ref(false)
    const gameSpeed = ref(1)
    const eventLogs = ref([])
    const dingMessages = ref([])
    const unreadDingtalk = ref(0)

    const activeModal = ref(null)
    const modalData = ref({})
    const isPendingExit = ref(false)

    // --- 动作与方法 ---
    function setPhase(phase) { currentPhase.value = phase }

    function updateStats(newStats) {
        if (!newStats) return
        // 🌟 修复：安全地将新状态合并到 reactive 对象中
        Object.keys(newStats).forEach(key => {
            // 我们不在这里合并 courses，留给专门的逻辑处理，避免覆盖
            if (key !== 'courses') {
                currentStats[key] = newStats[key]
            }
        })
    }

    function setCourseMetadata(data) {
        // 确保它是一个数组
        courseMetadata.value = Array.isArray(data) ? data : []
    }

    // 🌟 修复：专门处理 tick 发来的实时课程状态 (掌握度、策略)
    function updateCourseStates(courseUpdates) {
         if (!courseUpdates) return
         // 遍历后端发来的 {"CS101": {"progress": 10.5, "state": 1}}
         for (const courseId in courseUpdates) {
             if (!currentStats.courses[courseId]) {
                 currentStats.courses[courseId] = {}
             }
             // 响应式更新
             Object.assign(currentStats.courses[courseId], courseUpdates[courseId])
         }
    }

    function setPaused(val) { isPaused.value = val }
    function setGameSpeed(speed) { gameSpeed.value = speed }

    function addLog(source, message, colorClass = '') {
        eventLogs.value.push({ source, message, colorClass })
        if (eventLogs.value.length > 50) eventLogs.value.shift()
    }

    function addDingMessage(msg) {
        dingMessages.value.push(msg)
        unreadDingtalk.value++
    }
    
    function clearUnreadDingtalk() { unreadDingtalk.value = 0 }

    function showModal(modalName, data = {}) {
        activeModal.value = modalName
        modalData.value = data
    }
    
    function closeModal() {
        activeModal.value = null
        modalData.value = {}
    }

    function triggerEndGame(type, data) {
        showModal('end_screen', { type, ...data })
        setPaused(true)
    }

    return {
        currentPhase, setPhase,
        userInfo, currentStats, updateStats,
        courseMetadata, setCourseMetadata, updateCourseStates,
        semesterTimeLeft,
        isPaused, setPaused,
        gameSpeed, setGameSpeed,
        eventLogs, addLog,
        dingMessages, addDingMessage, unreadDingtalk, clearUnreadDingtalk,
        activeModal, modalData, showModal, closeModal,
        isPendingExit, triggerEndGame
    }
})