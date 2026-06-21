/**
 * Game WebSocket composable.
 *
 * This module owns the auth handshake, heartbeat, reconnect policy, and mapping
 * of server messages into the global Pinia store.
 */
import { ref, onUnmounted } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { CourseMetadata } from '../types/course'
import type { FeedbackChange } from '../types/modal'
import type { WsMessage, WsClientAction } from '../types/websocket'
import { extractGraduationFinalStats, extractNewSemesterName } from '../types/websocket'
import { ALLOCATABLE_STATS } from '@/data/statDefinitions.generated'
import { safeNumber, statDefault } from '@/utils/statDisplay'

/**
 * Narrow an unknown value to an object record.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/**
 * Parse a WebSocket text frame without throwing into the event handler.
 */
function parseWsJson(data: unknown): unknown {
  if (typeof data !== 'string') return null
  try {
    return JSON.parse(data)
  } catch {
    return null
  }
}

/**
 * Parse course metadata JSON from stats payloads.
 */
function parseCourseMetadataArray(data: unknown): CourseMetadata[] {
  if (typeof data !== 'string' || data.trim() === '') return []
  try {
    const parsed = JSON.parse(data)
    return Array.isArray(parsed) ? parsed as CourseMetadata[] : []
  } catch {
    return []
  }
}

/**
 * Preserve cooldown maps only when the payload is object-like.
 */
function readCooldowns(data: unknown): Record<string, unknown> | null {
  return isRecord(data) ? data : null
}

/**
 * Normalize backend feedback change entries for the feedback modal.
 */
function readFeedbackChanges(data: unknown): FeedbackChange[] | undefined {
  if (!Array.isArray(data)) return undefined
  const changes = data.flatMap((item): FeedbackChange[] => {
    if (!isRecord(item)) return []
    const field = typeof item.field === 'string' ? item.field : ''
    const label = typeof item.label === 'string' ? item.label : field
    const delta = Number(item.delta)
    if (!field || !label || !Number.isFinite(delta)) return []
    const change: FeedbackChange = { field, label, delta }
    if (typeof item.value === 'number' || typeof item.value === 'string') {
      change.value = item.value
    }
    if (typeof item.unit === 'string') {
      change.unit = item.unit
    }
    return [change]
  })
  return changes.length ? changes : undefined
}

/**
 * Create and manage one game WebSocket session.
 */
export function useGameWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const gameStore = useGameStore()

  /**
   * Keep course metadata in sync when the backend embeds it in stats.
   */
  const syncCourseMetadataFromStats = (stats: Record<string, unknown>) => {
    const courseInfoJson = stats.course_info_json
    if (typeof courseInfoJson !== 'string') return
    const metadata = parseCourseMetadataArray(courseInfoJson)
    if (metadata.length > 0) gameStore.setCourseMetadata(metadata)
  }

  let reconnectAttempts = 0
  const maxReconnectAttempts = 3
  const reconnectDelay = 3000
  let heartbeatInterval: ReturnType<typeof setInterval> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let shouldReconnect = true

  /**
   * Send a client action only when the socket is open.
   */
  const send = (data: WsClientAction) => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(data))
    }
  }

  const startHeartbeat = () => {
    if (heartbeatInterval) clearInterval(heartbeatInterval)
    heartbeatInterval = setInterval(() => {
      send({ action: 'ping' })
    }, 25000)
  }

  const stopHeartbeat = () => {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
      heartbeatInterval = null
    }
  }

  const clearReconnectTimer = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  /**
   * Open the game socket and send the first-message auth handshake.
   */
  const connect = (token: string = 'test_token', baseUrl: string = 'ws://localhost:8000') => {
    clearReconnectTimer()
    shouldReconnect = true
    ws.value = new WebSocket(`${baseUrl}/ws/game`)

    ws.value.onopen = () => {
      const llmProvider = sessionStorage.getItem('custom_llm_provider')
      const llmModel = sessionStorage.getItem('custom_llm_model')
      const llmKey = sessionStorage.getItem('custom_llm_key')
      const rpKey = sessionStorage.getItem('custom_rp_key')
      const selectedSaveSlot = localStorage.getItem('selected_save_slot')

      const payload: Record<string, unknown> = { token }
      if (llmProvider) payload.custom_llm_provider = llmProvider
      if (llmModel && llmModel.trim() !== '') payload.custom_llm_model = llmModel.trim()
      if (llmKey && llmKey.trim() !== '') payload.custom_llm_api_key = llmKey.trim()
      if (rpKey && rpKey.trim() !== '') payload.custom_rp_api_key = rpKey.trim()
      if (selectedSaveSlot && selectedSaveSlot.trim() !== '') {
        const slot = Number(selectedSaveSlot)
        if (Number.isInteger(slot) && slot > 0) {
          payload.load_save_slot = slot
        }
      }

      ws.value?.send(JSON.stringify(payload))
    }

    ws.value.onmessage = (event: MessageEvent) => {
      const parsed = parseWsJson(event.data)
      if (!isRecord(parsed)) return

      const msgType = parsed.type
      if (typeof msgType !== 'string') return

      const WS_TYPES: WsMessage['type'][] = [
        'auth_ok',
        'auth_error',
        'init',
        'tick',
        'state',
        'paused',
        'resumed',
        'event',
        'feedback',
        'game_over',
        'semester_summary',
        'random_event',
        'dingtalk_message',
        'dingtalk_state',
        'dingtalk_thread_update',
        'dingtalk_effect',
        'items_state',
        'achievement_unlocked',
        'graduation',
        'new_semester',
        'mode_changed',
        'toast',
        'save_result',
        'exit_confirmed',
      ]
      if (!WS_TYPES.includes(msgType as WsMessage['type'])) return

      const wsMsg = parsed as WsMessage

      switch (wsMsg.type) {
        case 'auth_ok': {
          isConnected.value = true
          reconnectAttempts = 0
          startHeartbeat()
          gameStore.addLog('系统', '已连接服务器...', 'text-success')
          break
        }

        case 'auth_error': {
          shouldReconnect = false
          const message = typeof wsMsg.message === 'string' ? wsMsg.message : '认证失败'
          gameStore.addLog('系统', message, 'text-danger')
          gameStore.showToast(message, 'danger')
          localStorage.removeItem('game_started')
          localStorage.removeItem('selected_save_slot')
          if (message.includes('存档') && localStorage.getItem('zju_saves')) {
            gameStore.setPhase('save_select')
          } else {
            localStorage.removeItem('zju_token')
            localStorage.removeItem('zju_jwt')
            gameStore.setPhase('login')
          }
          break
        }

        case 'init': {
          const data = isRecord(wsMsg.data) ? wsMsg.data : {}
          gameStore.resetRuntimeStateForInit()
          gameStore.setPhase('playing')
          gameStore.userInfo = data

          syncCourseMetadataFromStats(data)

          gameStore.updateStats(data)

          // Newer init messages put course maps at the top level; old ones nest them in data.
          const courses = wsMsg.courses ?? (data as Record<string, unknown>).courses
          if (isRecord(courses)) {
            gameStore.updateCourseProgress(courses as Record<string, unknown>)
          }
          const c_states = wsMsg.course_states ?? (data as Record<string, unknown>).course_states
          if (isRecord(c_states)) {
            gameStore.updateCourseStatesRaw(c_states as Record<string, unknown>)
          }

          const stl = wsMsg.semester_time_left
          if (typeof stl === 'number') {
            gameStore.semesterTimeLeft = stl
          }
          gameStore.setRelaxCooldowns(
            readCooldowns(wsMsg.relax_cooldowns) ||
            (isRecord(data.relax_cooldowns) ? data.relax_cooldowns : null),
          )
          if ('dingtalk_state' in wsMsg && isRecord(wsMsg.dingtalk_state)) {
            gameStore.setDingTalkState(wsMsg.dingtalk_state)
          }
          if ('items_state' in wsMsg && isRecord(wsMsg.items_state)) {
            gameStore.setItemsState(wsMsg.items_state)
          }
          gameStore.addLog('系统', '已连接折大服务器，游戏状态已同步。', 'text-success')
          break
        }

        case 'tick': {
          if (gameStore.currentPhase !== 'playing') {
            gameStore.setPhase('playing')
          }

          const stats = wsMsg.stats
          if (isRecord(stats)) {
            gameStore.updateStats(stats)
            syncCourseMetadataFromStats(stats)
          }

          if (isRecord(wsMsg.courses)) gameStore.updateCourseProgress(wsMsg.courses as Record<string, unknown>)
          if (isRecord(wsMsg.course_states)) gameStore.updateCourseStatesRaw(wsMsg.course_states as Record<string, unknown>)

          if (wsMsg.semester_time_left !== undefined && typeof wsMsg.semester_time_left === 'number') {
            gameStore.semesterTimeLeft = wsMsg.semester_time_left
          }
          gameStore.setRelaxCooldowns(readCooldowns(wsMsg.relax_cooldowns))
          break
        }

        case 'state': {
          if (gameStore.currentPhase !== 'playing') {
            gameStore.setPhase('playing')
          }

          const data = wsMsg.data
          if (isRecord(data)) {
            gameStore.updateStats(data)
            syncCourseMetadataFromStats(data)
            if (isRecord(data.courses)) {
              gameStore.updateCourseProgress(data.courses as Record<string, unknown>)
            }
            if (isRecord(data.course_states)) {
              gameStore.updateCourseStatesRaw(data.course_states as Record<string, unknown>)
            }
            gameStore.setRelaxCooldowns(
              readCooldowns(wsMsg.relax_cooldowns) ||
              (isRecord(data.relax_cooldowns) ? data.relax_cooldowns : null),
            )
          }
          break
        }

        case 'paused': {
          gameStore.setPaused(true)
          const text = typeof wsMsg.msg === 'string' ? wsMsg.msg : '游戏已暂停。'
          gameStore.addLog('系统', text, 'text-warning')
          break
        }

        case 'resumed': {
          gameStore.setPaused(false)
          const text = typeof wsMsg.msg === 'string' ? wsMsg.msg : '游戏已继续。'
          gameStore.addLog('系统', text, 'text-success')
          break
        }

        case 'event': {
          const desc =
            (typeof wsMsg.data?.desc === 'string' && wsMsg.data.desc) ||
            (typeof wsMsg.desc === 'string' ? wsMsg.desc : undefined) ||
            '发生了未知事件'
          gameStore.addLog('事件', desc, 'text-primary')
          break
        }

        case 'feedback': {
          const data = isRecord(wsMsg.data) ? wsMsg.data : {}
          const title = typeof data.title === 'string' && data.title.trim() !== ''
            ? data.title
            : '结果反馈'
          const message = typeof data.message === 'string' && data.message.trim() !== ''
            ? data.message
            : '操作已完成。'
          const kind = typeof data.kind === 'string' ? data.kind : 'info'
          const autoCloseMs = typeof data.auto_close_ms === 'number'
            ? data.auto_close_ms
            : typeof data.autoCloseMs === 'number'
              ? data.autoCloseMs
              : 3000
          gameStore.showFeedback({
            title,
            message,
            kind: kind as 'event' | 'relax' | 'info' | 'warning',
            autoCloseMs,
            changes: readFeedbackChanges(data.changes),
          })
          break
        }

        case 'game_over': {
          const reason =
            (typeof wsMsg.data?.reason === 'string' && wsMsg.data.reason) ||
            (typeof wsMsg.reason === 'string' ? wsMsg.reason : undefined) ||
            '你在求是园中迷失了自我'
          gameStore.triggerEndGame('game_over', { reason })
          break
        }

        case 'semester_summary': {
          gameStore.showModal('transcript', isRecord(wsMsg.data) ? wsMsg.data : wsMsg)
          break
        }

        case 'random_event': {
          gameStore.showModal('random_event', isRecord(wsMsg.data) ? wsMsg.data : wsMsg)
          break
        }

        case 'dingtalk_message': {
          gameStore.addDingMessage(isRecord(wsMsg.data) ? wsMsg.data : wsMsg)
          break
        }

        case 'dingtalk_state': {
          const state = isRecord(wsMsg.state)
            ? wsMsg.state
            : isRecord(wsMsg.data)
              ? wsMsg.data
              : null
          gameStore.setDingTalkState(state)
          break
        }

        case 'dingtalk_thread_update': {
          const data = isRecord(wsMsg.data) ? wsMsg.data : {}
          const contact = isRecord(wsMsg.contact)
            ? wsMsg.contact
            : isRecord(data.contact)
              ? data.contact
              : null
          gameStore.upsertDingTalkContact(contact)
          break
        }

        case 'dingtalk_effect': {
          if (typeof wsMsg.summary === 'string' && wsMsg.summary.trim() !== '') {
            gameStore.addLog('钉钉', wsMsg.summary, 'text-info')
          }
          break
        }

        case 'items_state': {
          gameStore.setItemsState(isRecord(wsMsg.data) ? wsMsg.data : null)
          break
        }

        case 'achievement_unlocked': {
          const achievement = gameStore.addUnlockedAchievement(
            isRecord(wsMsg.data) ? wsMsg.data : null,
          )
          if (achievement) {
            const message = `${achievement.icon ?? '🏅'} ${achievement.name}${achievement.desc ? `：${achievement.desc}` : ''}`
            gameStore.addLog('成就', message, 'text-warning fw-bold')
            gameStore.showToast(`成就解锁：${achievement.name}`, 'success', 3500)
            gameStore.showFeedback({
              title: '成就解锁',
              message,
              kind: 'info',
              autoCloseMs: 3500,
            })
          }
          break
        }

        case 'graduation': {
          const { finalStats, llmSummary: llmSummaryExtracted } = extractGraduationFinalStats(wsMsg)

          const gpaRaw = finalStats.gpa
          const gpa = typeof gpaRaw === 'number' ? gpaRaw : parseFloat(String(gpaRaw ?? 0)) || 0

          const achievementsRaw = finalStats.achievements
          const achievementDetailsRaw = finalStats.achievement_details
          const finalStatPayload = Object.fromEntries(
            ALLOCATABLE_STATS.map((stat) => [
              stat.id,
              safeNumber(finalStats[stat.id], stat.default),
            ]),
          )

          const achievementsArr = Array.isArray(achievementsRaw) ? achievementsRaw : []
          const achievementDetails = Array.isArray(achievementDetailsRaw)
            ? achievementDetailsRaw
            : achievementsArr.map((code) => ({ code: String(code), name: String(code) }))
          gameStore.setUnlockedAchievements(achievementDetails)
          const llmSummary = llmSummaryExtracted || '此子聪颖过人，勤勉有加...'

          gameStore.triggerEndGame('graduation', {
            gpa,
            ...finalStatPayload,
            gold: safeNumber(finalStats.gold, statDefault('gold')),
            achievements_count: achievementDetails.length || achievementsArr.length,
            achievement_details: gameStore.unlockedAchievements,
            llm_summary: llmSummary,
          })
          break
        }

        case 'new_semester': {
          gameStore.closeModal()
          if (gameStore.currentPhase !== 'playing') gameStore.setPhase('playing')
          const nsData = isRecord(wsMsg.data) ? wsMsg.data : wsMsg as Record<string, unknown>
          const stats = isRecord(nsData.stats) ? nsData.stats : {}
          const newCourseJson = typeof nsData.course_info_json === 'string'
            ? nsData.course_info_json as string
            : typeof stats.course_info_json === 'string'
              ? stats.course_info_json
              : '[]'
          const courses = parseCourseMetadataArray(newCourseJson)
          gameStore.resetForNewSemester(courses)
          gameStore.updateStats(stats)
          if (isRecord(nsData.courses)) {
            gameStore.updateCourseProgress(nsData.courses as Record<string, unknown>)
          }
          if (isRecord(nsData.course_states)) {
            gameStore.updateCourseStatesRaw(nsData.course_states as Record<string, unknown>)
          }
          if (typeof nsData.semester_time_left === 'number') {
            gameStore.semesterTimeLeft = nsData.semester_time_left
          }
          gameStore.clearEventLogs()
          const semesterName = extractNewSemesterName(wsMsg)
          gameStore.addLog('系统', `=== 欢迎来到 ${semesterName} ===`, 'text-success fw-bold')
          break
        }

        case 'mode_changed': {
          const data = isRecord((wsMsg as Record<string, unknown>).data)
            ? (wsMsg as Record<string, unknown>).data as Record<string, unknown>
            : {}
          const rawMode = typeof wsMsg.mode === 'string'
            ? wsMsg.mode
            : typeof data.mode === 'string'
              ? data.mode
              : 'hybrid'
          const mode = ['library', 'ai', 'hybrid'].includes(rawMode) ? rawMode : 'hybrid'
          gameStore.gameMode = mode as 'library' | 'ai' | 'hybrid'
          gameStore.llmAvailable = typeof wsMsg.llm_available === 'boolean'
            ? wsMsg.llm_available
            : typeof data.llm_available === 'boolean'
              ? data.llm_available
              : true
          break
        }

        case 'toast': {
          const data = isRecord((wsMsg as Record<string, unknown>).data)
            ? (wsMsg as Record<string, unknown>).data as Record<string, unknown>
            : {}
          const message = typeof wsMsg.message === 'string'
            ? wsMsg.message
            : typeof data.message === 'string'
              ? data.message
              : ''
          const level = typeof (wsMsg as Record<string, unknown>).level === 'string'
            ? (wsMsg as Record<string, unknown>).level as string
            : typeof data.level === 'string'
              ? data.level
            : 'info'
          gameStore.showToast(message, level as 'success' | 'danger' | 'warning' | 'info')
          break
        }

        case 'save_result': {
          const message = typeof wsMsg.message === 'string' ? wsMsg.message : ''
          const success = typeof wsMsg.success === 'boolean' ? wsMsg.success : false
          gameStore.showToast(message, success ? 'success' : 'danger')

          if (gameStore.isPendingExit && success) {
            shouldReconnect = false
            localStorage.removeItem('zju_token')
            localStorage.removeItem('zju_jwt')
            localStorage.removeItem('game_started')
            localStorage.removeItem('selected_save_slot')
            window.location.reload()
          } else if (gameStore.isPendingExit && !success) {
            gameStore.isPendingExit = false
            gameStore.addLog('系统', '保存失败，无法安全退出！', 'text-danger')
          }
          break
        }

        case 'exit_confirmed': {
          shouldReconnect = false
          localStorage.removeItem('zju_token')
          localStorage.removeItem('zju_jwt')
          localStorage.removeItem('game_started')
          localStorage.removeItem('selected_save_slot')
          window.location.reload()
          break
        }
        default:
          // Future server message types should not break current clients.
          break
      }
    }

    ws.value.onclose = (event: CloseEvent) => {
      isConnected.value = false
      stopHeartbeat()

      const closedDuringPendingExit = gameStore.isPendingExit
      if (closedDuringPendingExit) {
        gameStore.isPendingExit = false
        gameStore.showToast('连接在保存确认前断开，请重试保存并退出。', 'warning', 5000)
        gameStore.addLog('系统', '保存退出未收到服务器确认，已解除等待状态。', 'text-warning')
      }

      const retryableCloseCodes = new Set([1001, 1006])
      if (
        shouldReconnect
        && (closedDuringPendingExit || retryableCloseCodes.has(event.code))
        && reconnectAttempts < maxReconnectAttempts
      ) {
        reconnectAttempts += 1
        gameStore.addLog('系统', `断开连接，准备重连 (${reconnectAttempts}/${maxReconnectAttempts})...`, 'text-warning')
        clearReconnectTimer()
        reconnectTimer = setTimeout(() => connect(token, baseUrl), reconnectDelay)
      }
    }
  }

  onUnmounted(() => {
    shouldReconnect = false
    clearReconnectTimer()
    if (ws.value) ws.value.close()
    stopHeartbeat()
  })

  /**
   * Close the socket intentionally and disable reconnect.
   */
  const disconnect = () => {
    shouldReconnect = false
    clearReconnectTimer()
    stopHeartbeat()
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    isConnected.value = false
  }

  return { ws, isConnected, connect, send, disconnect }
}

