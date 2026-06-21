/**
 * Global Pinia store for the game console.
 *
 * The store keeps WebSocket state, player stats, modals, DingTalk inbox,
 * item inventory, toasts, and session presentation preferences in one place.
 */
import { defineStore } from 'pinia'
import { computed, ref, reactive } from 'vue'
import { STAT_DEFINITIONS } from '@/data/statDefinitions.generated'
import type { GamePhase, PlayerStats } from '../types/game'
import type { CoursesMap, CourseMetadata, CourseProgressUpdate } from '../types/course'
import type { GameItem, ItemsState } from '../types/items'
import type { AchievementSummary, DingTalkContact, DingTalkMessage, DingTalkState, FeedbackModalData, ModalData } from '../types/modal'
import type { RelaxTarget } from '../types/websocket'

type ToastType = 'success' | 'danger' | 'warning' | 'info'
type ToastState = { message: string; type: ToastType }

type EndType = 'game_over' | 'graduation'

type EndData = {
  reason?: string
  gpa?: number
  iq?: number
  eq?: number
  charm?: number
  gold?: number
  achievements_count?: number
  achievement_details?: AchievementSummary[]
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
const DEFAULT_STAT_VALUES = Object.fromEntries(
  STAT_DEFINITIONS.map((stat) => [stat.id, stat.default]),
) as Record<string, number>

/**
 * Narrow a persisted string to a supported console theme.
 */
function isConsoleTheme(value: unknown): value is ConsoleTheme {
  return typeof value === 'string' && CONSOLE_THEMES.includes(value as ConsoleTheme)
}

/**
 * Read theme preference without letting storage failures break startup.
 */
function readStoredConsoleTheme(): ConsoleTheme {
  try {
    const storedTheme = localStorage.getItem(CONSOLE_THEME_STORAGE_KEY)
    return isConsoleTheme(storedTheme) ? storedTheme : 'lantian'
  } catch {
    return 'lantian'
  }
}

/**
 * Parse an unknown backend value into a finite number.
 */
function finiteNumber(value: unknown, fallback: number = 0): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

/**
 * Normalize course metadata from stats JSON or WebSocket payloads.
 */
function normalizeCourseMetadata(data: unknown): CourseMetadata[] {
  if (!Array.isArray(data)) return []
  return data.flatMap((item): CourseMetadata[] => {
    if (!item || typeof item !== 'object') return []
    const record = item as Record<string, unknown>
    const id = typeof record.id === 'string' ? record.id : ''
    if (!id) return []
    const name = typeof record.name === 'string' && record.name.trim() !== ''
      ? record.name
      : id
    const credit = finiteNumber(record.credit ?? record.credits, 0)
    return [{
      ...record,
      id,
      name,
      credit,
      credits: credit,
    } as CourseMetadata]
  })
}

export const useGameStore = defineStore('game', () => {
  const currentPhase = ref<GamePhase>('login')
  const userInfo = ref<Record<string, unknown>>({})

  const toast = ref<ToastState | null>(null)
  let toastTimer: ReturnType<typeof setTimeout> | null = null

  const endType = ref<EndType | null>(null)
  const endData = ref<EndData>({})

  /** Reactive stat object; dynamic registry fields can be assigned in place. */
  const currentStats = reactive<PlayerStats>({
    ...DEFAULT_STAT_VALUES,
    username: '',
    major: '',
    major_abbr: '',
    semester: '大一秋冬',
    semester_idx: 1,
    semester_start_time: 0,
    gpa: 0.0,
    highest_gpa: 0.0,
    item_bonuses: {},
    courses: {},
    exam_completed: 0,
  })

  const courseMetadata = ref<CourseMetadata[]>([])

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
  const unlockedAchievements = ref<AchievementSummary[]>([])
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

  /**
   * Set the current high-level route phase.
   */
  function setPhase(phase: GamePhase) {
    currentPhase.value = phase
  }

  /**
   * Show a transient global toast.
   */
  function showToast(message: string, type: ToastType = 'info', durationMs: number = 2500) {
    toast.value = { message, type }
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      toast.value = null
      toastTimer = null
    }, durationMs)
  }

  /**
   * Merge backend stat updates without replacing nested course progress maps.
   */
  function updateStats(newStats: Partial<PlayerStats> | null | undefined) {
    if (!newStats) return
    // Course progress and strategy state are merged through dedicated methods.
    for (const [key, value] of Object.entries(newStats)) {
      if (key === 'courses') continue
      ;(currentStats as Record<string, unknown>)[key] = value
    }
  }

  /**
   * Replace static course metadata after init or semester transition.
   */
  function setCourseMetadata(data: unknown) {
    courseMetadata.value = normalizeCourseMetadata(data)
  }

  /**
   * Clear course runtime maps and install metadata for a new semester.
   */
  function resetForNewSemester(newCourseMetadata: CourseMetadata[]) {
    setCourseMetadata(newCourseMetadata)
    for (const key in currentStats.courses) {
      delete currentStats.courses[key]
    }
    for (const key in currentCourseStates) {
      delete currentCourseStates[key]
    }
  }

  /**
   * Merge course mastery progress keyed by course ID.
   */
  function updateCourseProgress(progressMap: Record<string, unknown> | null | undefined) {
    if (!progressMap) return
    for (const courseId in progressMap) {
      if (!currentStats.courses[courseId]) currentStats.courses[courseId] = {}
      currentStats.courses[courseId].progress = Number(progressMap[courseId]) || 0
    }
  }

  /**
   * Merge raw course strategy state keyed by course ID.
   */
  function updateCourseStatesRaw(statesMap: Record<string, unknown> | null | undefined) {
    if (!statesMap) return
    for (const courseId in statesMap) {
      const s = Number(statesMap[courseId])
      currentCourseStates[courseId] = s
      if (!currentStats.courses[courseId]) currentStats.courses[courseId] = {}
      currentStats.courses[courseId].state = s
    }
  }

  /**
   * Optimistically set one course strategy in the local UI.
   */
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

  /**
   * Persist a purely visual console theme preference when storage works.
   */
  function setConsoleTheme(theme: ConsoleTheme) {
    consoleTheme.value = theme
    try {
      localStorage.setItem(CONSOLE_THEME_STORAGE_KEY, theme)
    } catch {
      // Ignore persistence failures; the visual switch should still work for this session.
    }
  }

  /**
   * Normalize server cooldown seconds into local integer counters.
   */
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
  /**
   * Append a bounded event log row to the right panel feed.
   */
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

  /**
   * Adapt a legacy single DingTalk message into the contact-thread model.
   */
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

  /**
   * Clear all DingTalk unread counters locally.
   */
  function clearUnreadDingtalk() {
    for (const contact of Object.values(dingtalkContacts)) {
      contact.unread_count = 0
    }
    unreadDingtalk.value = 0
  }

  /**
   * Recompute the aggregate unread DingTalk badge.
   */
  function recalcUnreadDingtalk() {
    unreadDingtalk.value = Object.values(dingtalkContacts).reduce(
      (sum, contact) => sum + Number(contact.unread_count || 0),
      0,
    )
  }

  /**
   * Replace the DingTalk inbox with server-authoritative state.
   */
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

  /**
   * Normalize and replace item catalog, ownership, and passive bonuses.
   */
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

  /**
   * Upsert one DingTalk contact pushed by a thread-update message.
   */
  function upsertDingTalkContact(contact: DingTalkContact | Record<string, unknown> | null | undefined) {
    if (!contact || typeof contact !== 'object') return
    const contactId = (contact as DingTalkContact).contact_id
    if (!contactId) return
    dingtalkContacts[contactId] = contact as DingTalkContact
    recalcUnreadDingtalk()
  }

  /**
   * Mark one DingTalk contact as read without waiting for the server echo.
   */
  function markDingContactReadLocal(contactId: string) {
    const contact = dingtalkContacts[contactId]
    if (!contact) return
    contact.unread_count = 0
    recalcUnreadDingtalk()
  }

  /**
   * Normalize achievement payloads from old code-only saves and new details.
   */
  function normalizeAchievement(raw: Record<string, unknown>): AchievementSummary {
    const code = typeof raw.code === 'string' && raw.code.trim() !== ''
      ? raw.code.trim()
      : typeof raw.name === 'string'
        ? raw.name.trim()
        : 'achievement'
    const name = typeof raw.name === 'string' && raw.name.trim() !== ''
      ? raw.name.trim()
      : code
    return {
      code,
      name,
      desc: typeof raw.desc === 'string'
        ? raw.desc
        : typeof raw.description === 'string'
          ? raw.description
          : '',
      icon: typeof raw.icon === 'string' && raw.icon.trim() !== '' ? raw.icon : '🏅',
    }
  }

  /**
   * Add or replace one unlocked achievement in local state.
   */
  function addUnlockedAchievement(raw: AchievementSummary | Record<string, unknown> | null | undefined) {
    if (!raw || typeof raw !== 'object') return null
    const achievement = normalizeAchievement(raw as Record<string, unknown>)
    const existingIndex = unlockedAchievements.value.findIndex((item) => item.code === achievement.code)
    if (existingIndex >= 0) {
      unlockedAchievements.value[existingIndex] = achievement
    } else {
      unlockedAchievements.value.push(achievement)
    }
    return achievement
  }

  /**
   * Replace the unlocked achievement list from server or save data.
   */
  function setUnlockedAchievements(rawItems: unknown) {
    unlockedAchievements.value = []
    if (!Array.isArray(rawItems)) return
    for (const item of rawItems) {
      if (item && typeof item === 'object') {
        addUnlockedAchievement(item as Record<string, unknown>)
      } else if (typeof item === 'string') {
        addUnlockedAchievement({ code: item, name: item })
      }
    }
  }

  /**
   * Open a global modal with its payload.
   */
  function showModal(modalName: Exclude<ActiveModalName, null>, data: ModalData | Record<string, unknown> = {}) {
    activeModal.value = modalName
    modalData.value = data
  }

  /**
   * Close the active global modal.
   */
  function closeModal() {
    activeModal.value = null
    modalData.value = {}
  }

  /**
   * Show a feedback modal with optional auto-close behavior.
   */
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

  /**
   * Close feedback and cancel its auto-close timer.
   */
  function closeFeedback() {
    if (feedbackTimer) clearTimeout(feedbackTimer)
    feedbackTimer = null
    feedbackModal.value = null
  }

  /**
   * Move the app into an end-state screen.
   */
  function triggerEndGame(type: EndType, data: EndData | Record<string, unknown> = {}) {
    endType.value = type
    endData.value = data as EndData
    setPaused(true)
    setPhase('ended')
  }

  /**
   * Clear per-session runtime state before applying a fresh `init` payload.
   */
  function resetRuntimeStateForInit() {
    endType.value = null
    endData.value = {}
    isPaused.value = false
    isGuideActive.value = false
    gameSpeed.value = 1
    semesterTimeLeft.value = 0
    eventLogs.value = []
    dingMessages.value = []
    unlockedAchievements.value = []
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
    unlockedAchievements,
    addUnlockedAchievement,
    setUnlockedAchievements,
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

