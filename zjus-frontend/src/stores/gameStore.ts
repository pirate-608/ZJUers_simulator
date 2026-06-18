import { defineStore } from 'pinia'
import { computed, ref, reactive } from 'vue'
import type { GamePhase, PlayerStats } from '../types/game'
import type { CoursesMap, CourseMetadata, CourseProgressUpdate } from '../types/course'
import type { GameItem, ItemsState } from '../types/items'
import type { DingTalkContact, DingTalkMessage, DingTalkState, FeedbackModalData, ModalData } from '../types/modal'
import type { RelaxTarget } from '../types/websocket'

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

type ActiveModalName = 'transcript' | 'random_event' | 'exit_confirm' | 'exam_confirm' | null
export type ConsoleTheme = 'lantian' | 'yunfeng' | 'danqing'

type EventLog = {
  id: number
  type: string
  message: string
  cssClass: string
}

const CONSOLE_THEME_STORAGE_KEY = 'zjus_console_theme'
const CONSOLE_THEMES: ConsoleTheme[] = ['lantian', 'yunfeng', 'danqing']

function isConsoleTheme(value: unknown): value is ConsoleTheme {
  return typeof value === 'string' && CONSOLE_THEMES.includes(value as ConsoleTheme)
}

function readStoredConsoleTheme(): ConsoleTheme {
  try {
    const storedTheme = localStorage.getItem(CONSOLE_THEME_STORAGE_KEY)
    return isConsoleTheme(storedTheme) ? storedTheme : 'lantian'
  } catch {
    return 'lantian'
  }
}

export const useGameStore = defineStore('game', () => {
  // --- 核心状态 ---
  const currentPhase = ref<GamePhase>('login') // login, character_create, loading, playing, ended
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
    gold: 0,
    item_bonuses: {},
    courses: {}, // 存放实时的掌握度进度
    exam_completed: 0,
  })

  const courseMetadata = ref<CourseMetadata[]>([]) // 静态课程信息

  // 课程策略（0:摆 1:摸 2:卷）
  const currentCourseStates = reactive<Record<string, number>>({})

  const semesterTimeLeft = ref<number>(0)
  const isPaused = ref<boolean>(false)
  const isGuideActive = ref<boolean>(false)
  const gameSpeed = ref<number>(1)
  const relaxCooldowns = reactive<Record<RelaxTarget, number>>({
    gym: 0,
    game: 0,
    walk: 0,
    cc98: 0,
  })

  const eventLogs = ref<EventLog[]>([])
  const dingMessages = ref<DingTalkMessage[]>([])
  const dingtalkContacts = reactive<Record<string, DingTalkContact>>({})
  const unreadDingtalk = ref<number>(0)
  const itemCatalog = ref<GameItem[]>([])
  const ownedItems = ref<string[]>([])
  const itemBonuses = reactive<Record<string, number>>({})
  const itemsUpdatedAt = ref<number>(0)
  const ownedItemSet = computed(() => new Set(ownedItems.value))

  const activeModal = ref<ActiveModalName>(null)
  const modalData = ref<ModalData | Record<string, unknown>>({})
  const feedbackModal = ref<FeedbackModalData | null>(null)
  let feedbackTimer: ReturnType<typeof setTimeout> | null = null

  const gameMode = ref<'library' | 'ai' | 'hybrid'>('hybrid')
  const llmAvailable = ref<boolean>(true)
  const consoleTheme = ref<ConsoleTheme>(readStoredConsoleTheme())

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

  function resetForNewSemester(newCourseMetadata: CourseMetadata[]) {
    setCourseMetadata(newCourseMetadata)
    // 清空课程进度 (currentStats.courses)
    for (const key in currentStats.courses) {
      delete currentStats.courses[key]
    }
    // 清空课程策略 (currentCourseStates)
    for (const key in currentCourseStates) {
      delete currentCourseStates[key]
    }
  }

  function updateCourseProgress(progressMap: Record<string, unknown> | null | undefined) {
    if (!progressMap) return
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

  function setGuideActive(val: boolean) {
    isGuideActive.value = val
  }

  function setGameSpeed(speed: number) {
    gameSpeed.value = speed
  }

  function setConsoleTheme(theme: ConsoleTheme) {
    consoleTheme.value = theme
    try {
      localStorage.setItem(CONSOLE_THEME_STORAGE_KEY, theme)
    } catch {
      // Ignore persistence failures; the visual switch should still work for this session.
    }
  }

  function setRelaxCooldowns(cooldowns: Record<string, unknown> | null | undefined) {
    if (!cooldowns) return
    for (const target of Object.keys(relaxCooldowns) as RelaxTarget[]) {
      const value = Number(cooldowns[target])
      relaxCooldowns[target] = Number.isFinite(value) ? Math.max(0, Math.ceil(value)) : 0
    }
  }

  function tickRelaxCooldowns(seconds: number = 1) {
    for (const target of Object.keys(relaxCooldowns) as RelaxTarget[]) {
      relaxCooldowns[target] = Math.max(0, relaxCooldowns[target] - seconds)
    }
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
    const role = typeof msg.role === 'string' ? msg.role : 'unknown'
    const sender = typeof msg.sender === 'string' ? msg.sender : role
    const contactId = typeof msg.contact_id === 'string'
      ? msg.contact_id
      : `legacy_${role}_${sender}`.replace(/[^\w-]+/g, '_')
    const existing = dingtalkContacts[contactId]
    const createdAt = Math.floor(Date.now() / 1000)
    const contact: DingTalkContact = existing || {
      contact_id: contactId,
      sender,
      role,
      is_replyable: false,
      is_urgent: Boolean(msg.is_urgent),
      unread_count: 0,
      last_message_at: 0,
      messages: [],
      pending_options: [],
      round: { round_id: '', status: 'closed', player_reply_count: 0 },
    }
    contact.messages.push({
      message_id: `legacy_${createdAt}_${contact.messages.length}`,
      speaker: 'npc',
      content: typeof msg.content === 'string' ? msg.content : '',
      created_at: createdAt,
      round_id: null,
    })
    contact.unread_count += 1
    contact.last_message_at = createdAt
    dingtalkContacts[contactId] = contact
    recalcUnreadDingtalk()
  }

  function clearUnreadDingtalk() {
    for (const contact of Object.values(dingtalkContacts)) {
      contact.unread_count = 0
    }
    unreadDingtalk.value = 0
  }

  function recalcUnreadDingtalk() {
    unreadDingtalk.value = Object.values(dingtalkContacts).reduce(
      (sum, contact) => sum + Number(contact.unread_count || 0),
      0,
    )
  }

  function setDingTalkState(state: DingTalkState | Record<string, unknown> | null | undefined) {
    for (const key in dingtalkContacts) {
      delete dingtalkContacts[key]
    }
    const contacts = state && typeof state === 'object' && 'contacts' in state
      ? (state as DingTalkState).contacts
      : {}
    if (contacts && typeof contacts === 'object') {
      for (const [id, contact] of Object.entries(contacts)) {
        dingtalkContacts[id] = contact as DingTalkContact
      }
    }
    recalcUnreadDingtalk()
  }

  function setItemsState(state: ItemsState | Record<string, unknown> | null | undefined) {
    const record = state && typeof state === 'object' ? state as Record<string, unknown> : {}
    const itemsRaw = Array.isArray(record.items) ? record.items : []
    itemCatalog.value = itemsRaw.flatMap((item): GameItem[] => {
      if (!item || typeof item !== 'object') return []
      const data = item as Record<string, unknown>
      const id = typeof data.id === 'string' ? data.id : ''
      if (!id) return []
      return [{
        id,
        name: typeof data.name === 'string' ? data.name : id,
        category: typeof data.category === 'string' ? data.category : '通用',
        description: typeof data.description === 'string' ? data.description : '',
        price: Number(data.price ?? 0),
        sell_price: Number(data.sell_price ?? 0),
        tags: Array.isArray(data.tags) ? data.tags.map(String).filter(Boolean) : [],
        effects: data.effects && typeof data.effects === 'object'
          ? Object.fromEntries(
              Object.entries(data.effects as Record<string, unknown>)
                .map(([key, value]) => [key, Number(value)])
                .filter(([, value]) => Number.isFinite(value) && value !== 0),
            )
          : {},
      }]
    })

    ownedItems.value = Array.isArray(record.owned)
      ? record.owned.map(String).filter(Boolean)
      : []

    for (const key in itemBonuses) {
      delete itemBonuses[key]
    }
    const bonuses = record.bonuses && typeof record.bonuses === 'object'
      ? record.bonuses as Record<string, unknown>
      : {}
    for (const [key, value] of Object.entries(bonuses)) {
      const parsed = Number(value)
      if (Number.isFinite(parsed) && parsed !== 0) itemBonuses[key] = parsed
    }
    itemsUpdatedAt.value = Number(record.updated_at ?? 0) || 0
  }

  function upsertDingTalkContact(contact: DingTalkContact | Record<string, unknown> | null | undefined) {
    if (!contact || typeof contact !== 'object') return
    const contactId = (contact as DingTalkContact).contact_id
    if (!contactId) return
    dingtalkContacts[contactId] = contact as DingTalkContact
    recalcUnreadDingtalk()
  }

  function markDingContactReadLocal(contactId: string) {
    const contact = dingtalkContacts[contactId]
    if (!contact) return
    contact.unread_count = 0
    recalcUnreadDingtalk()
  }

  function showModal(modalName: Exclude<ActiveModalName, null>, data: ModalData | Record<string, unknown> = {}) {
    activeModal.value = modalName
    modalData.value = data
  }

  function closeModal() {
    activeModal.value = null
    modalData.value = {}
  }

  function showFeedback(data: FeedbackModalData) {
    feedbackModal.value = data
    if (feedbackTimer) clearTimeout(feedbackTimer)
    const timeout = data.autoCloseMs ?? 3000
    if (timeout > 0) {
      feedbackTimer = setTimeout(() => {
        feedbackModal.value = null
        feedbackTimer = null
      }, timeout)
    }
  }

  function closeFeedback() {
    if (feedbackTimer) clearTimeout(feedbackTimer)
    feedbackTimer = null
    feedbackModal.value = null
  }

  function triggerEndGame(type: EndType, data: EndData | Record<string, unknown> = {}) {
    endType.value = type
    endData.value = data as EndData
    setPaused(true)
    setPhase('ended')
  }

  function resetRuntimeStateForInit() {
    endType.value = null
    endData.value = {}
    isPaused.value = false
    isGuideActive.value = false
    gameSpeed.value = 1
    semesterTimeLeft.value = 0
    eventLogs.value = []
    dingMessages.value = []
    for (const key in dingtalkContacts) {
      delete dingtalkContacts[key]
    }
    unreadDingtalk.value = 0
    itemCatalog.value = []
    ownedItems.value = []
    for (const key in itemBonuses) {
      delete itemBonuses[key]
    }
    itemsUpdatedAt.value = 0
    for (const target of Object.keys(relaxCooldowns) as RelaxTarget[]) {
      relaxCooldowns[target] = 0
    }
    for (const key in currentStats.courses) {
      delete currentStats.courses[key]
    }
    for (const key in currentCourseStates) {
      delete currentCourseStates[key]
    }
    closeModal()
    closeFeedback()
    isPendingExit.value = false
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
    resetRuntimeStateForInit,
    courseMetadata,
    setCourseMetadata,
    resetForNewSemester,
    updateCourseProgress,
    updateCourseStatesRaw,
    currentCourseStates,
    setCourseState,
    semesterTimeLeft,
    isPaused,
    setPaused,
    isGuideActive,
    setGuideActive,
    gameSpeed,
    setGameSpeed,
    relaxCooldowns,
    setRelaxCooldowns,
    tickRelaxCooldowns,
    eventLogs,
    addLog,
    clearEventLogs,
    dingMessages,
    addDingMessage,
    dingtalkContacts,
    setDingTalkState,
    upsertDingTalkContact,
    markDingContactReadLocal,
    unreadDingtalk,
    clearUnreadDingtalk,
    itemCatalog,
    ownedItems,
    ownedItemSet,
    itemBonuses,
    itemsUpdatedAt,
    setItemsState,
    activeModal,
    modalData,
    showModal,
    closeModal,
    feedbackModal,
    showFeedback,
    closeFeedback,
    gameMode,
    llmAvailable,
    consoleTheme,
    setConsoleTheme,
    isPendingExit,
  }
})

