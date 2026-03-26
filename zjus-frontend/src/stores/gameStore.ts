import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import type { GamePhase, PlayerStats } from '../types/game'
import type { CoursesMap, CourseMetadata, CourseProgressUpdate } from '../types/course'
import type { DingTalkMessage, ModalData } from '../types/modal'

type ToastType = 'success' | 'danger' | 'warning' | 'info'
type ToastState = { message: string; type: ToastType }

type EndType = 'game_over' | 'graduation'

type EndData = {
  reason?: string
  gpa?: number
  iq?: number
  eq?: number
  gold?: number
  achievements_count?: number
  llm_summary?: string
  [k: string]: unknown
}

type ActiveModalName = 'transcript' | 'random_event' | 'exit_confirm' | null

type EventLog = {
  id: number
  type: string
  message: string
  cssClass: string
}

export const useGameStore = defineStore('game', () => {
  // --- 核心状态 ---
  const currentPhase = ref<GamePhase>('login') // login, admission, loading, playing, ended
  const userInfo = ref<Record<string, unknown>>({})

  // toast：供 App.vue 顶部提示使用
  const toast = ref<ToastState | null>(null)
  let toastTimer: ReturnType<typeof setTimeout> | null = null

  // 结局信息：供 EndScreen.vue 使用
  const endType = ref<EndType | null>(null)
  const endData = ref<EndData>({})

  // 🌟 修复：使用 reactive 初始化，确保所有后端可能发来的核心属性都是响应式的！
  const currentStats = reactive<PlayerStats>({
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
    courses: {}, // 存放实时的掌握度进度
  })

  const courseMetadata = ref<CourseMetadata[]>([]) // 静态课程信息

  // 课程策略（0:摆 1:摸 2:卷）
  const currentCourseStates = reactive<Record<string, number>>({})

  const semesterTimeLeft = ref<number>(0)
  const isPaused = ref<boolean>(false)
  const gameSpeed = ref<number>(1)

  const eventLogs = ref<EventLog[]>([])
  const dingMessages = ref<DingTalkMessage[]>([])
  const unreadDingtalk = ref<number>(0)

  const activeModal = ref<ActiveModalName>(null)
  const modalData = ref<ModalData | Record<string, unknown>>({})

  const isPendingExit = ref<boolean>(false)

  // --- 动作与方法 ---
  function setPhase(phase: GamePhase) {
    currentPhase.value = phase
  }

  function showToast(message: string, type: ToastType = 'info', durationMs: number = 2500) {
    toast.value = { message, type }
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      toast.value = null
      toastTimer = null
    }, durationMs)
  }

  function updateStats(newStats: Partial<PlayerStats> | null | undefined) {
    if (!newStats) return
    // 不合并 courses：课程进度/策略单独由 updateCourseStates 管理，避免覆盖。
    for (const [key, value] of Object.entries(newStats)) {
      if (key === 'courses') continue
      ;(currentStats as Record<string, unknown>)[key] = value
    }
  }

  function setCourseMetadata(data: unknown) {
    courseMetadata.value = Array.isArray(data) ? (data as CourseMetadata[]) : []
  }

  function updateCourseProgress(progressMap: Record<string, unknown> | null | undefined) {
    if (!progressMap) return
    // 空对象表示新学期：清空旧课程进度
    if (Object.keys(progressMap).length === 0) {
      for (const key in currentStats.courses) {
        delete currentStats.courses[key]
      }
      return
    }
    for (const courseId in progressMap) {
      if (!currentStats.courses[courseId]) currentStats.courses[courseId] = {}
      currentStats.courses[courseId].progress = Number(progressMap[courseId]) || 0
    }
  }

  function updateCourseStatesRaw(statesMap: Record<string, unknown> | null | undefined) {
    if (!statesMap) return
    for (const courseId in statesMap) {
      const s = Number(statesMap[courseId])
      currentCourseStates[courseId] = s
      if (!currentStats.courses[courseId]) currentStats.courses[courseId] = {}
      currentStats.courses[courseId].state = s
    }
  }

  function setCourseState(courseId: string, newState: number) {
    if (!courseId) return
    currentCourseStates[courseId] = newState
    if (!currentStats.courses[courseId]) currentStats.courses[courseId] = {}
    currentStats.courses[courseId].state = newState
  }

  function setPaused(val: boolean) {
    isPaused.value = val
  }

  function setGameSpeed(speed: number) {
    gameSpeed.value = speed
  }

  let logSeq = 0
  function addLog(source: string, message: string, colorClass: string = '') {
    logSeq += 1
    eventLogs.value.push({
      id: logSeq,
      type: source,
      message,
      cssClass: colorClass,
    })
    if (eventLogs.value.length > 50) eventLogs.value.shift()
  }

  function clearEventLogs() {
    eventLogs.value = []
  }

  function addDingMessage(msg: DingTalkMessage | Record<string, unknown>) {
    dingMessages.value.push(msg as DingTalkMessage)
    unreadDingtalk.value++
  }

  function clearUnreadDingtalk() {
    unreadDingtalk.value = 0
  }

  function showModal(modalName: Exclude<ActiveModalName, null>, data: ModalData | Record<string, unknown> = {}) {
    activeModal.value = modalName
    modalData.value = data
  }

  function closeModal() {
    activeModal.value = null
    modalData.value = {}
  }

  function triggerEndGame(type: EndType, data: EndData | Record<string, unknown> = {}) {
    endType.value = type
    endData.value = data as EndData
    setPaused(true)
    setPhase('ended')
  }

  return {
    currentPhase,
    setPhase,
    userInfo,
    currentStats,
    updateStats,
    toast,
    showToast,
    endType,
    endData,
    triggerEndGame,
    courseMetadata,
    setCourseMetadata,
    updateCourseProgress,
    updateCourseStatesRaw,
    currentCourseStates,
    setCourseState,
    semesterTimeLeft,
    isPaused,
    setPaused,
    gameSpeed,
    setGameSpeed,
    eventLogs,
    addLog,
    clearEventLogs,
    dingMessages,
    addDingMessage,
    unreadDingtalk,
    clearUnreadDingtalk,
    activeModal,
    modalData,
    showModal,
    closeModal,
    isPendingExit,
  }
})

