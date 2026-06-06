import { ref, onUnmounted } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { CourseMetadata } from '../types/course'
import type { WsMessage, WsClientAction } from '../types/websocket'
import { extractGraduationFinalStats, extractNewSemesterName } from '../types/websocket'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function parseWsJson(data: unknown): unknown {
  if (typeof data !== 'string') return null
  try {
    return JSON.parse(data)
  } catch {
    return null
  }
}

function parseCourseMetadataArray(data: unknown): CourseMetadata[] {
  if (typeof data !== 'string' || data.trim() === '') return []
  try {
    const parsed = JSON.parse(data)
    return Array.isArray(parsed) ? parsed as CourseMetadata[] : []
  } catch {
    return []
  }
}

function readCooldowns(data: unknown): Record<string, unknown> | null {
  return isRecord(data) ? data : null
}

export function useGameWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const gameStore = useGameStore()

  let reconnectAttempts = 0
  const maxReconnectAttempts = 3
  const reconnectDelay = 3000
  let heartbeatInterval: ReturnType<typeof setInterval> | null = null
  let shouldReconnect = true

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

  const connect = (token: string = 'test_token', baseUrl: string = 'ws://localhost:8000') => {
    shouldReconnect = true
    ws.value = new WebSocket(`${baseUrl}/ws/game`)

    ws.value.onopen = () => {
      const llmProvider = sessionStorage.getItem('custom_llm_provider')
      const llmModel = sessionStorage.getItem('custom_llm_model')
      const llmKey = sessionStorage.getItem('custom_llm_key')
      const selectedSaveSlot = localStorage.getItem('selected_save_slot')

      const payload: Record<string, unknown> = { token }
      if (llmProvider) payload.custom_llm_provider = llmProvider
      if (llmModel && llmModel.trim() !== '') payload.custom_llm_model = llmModel.trim()
      if (llmKey && llmKey.trim() !== '') payload.custom_llm_api_key = llmKey.trim()
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
          gameStore.setPhase('playing')
          gameStore.userInfo = data

          // 静态元数据
          const courseInfoJson = data.course_info_json
          if (typeof courseInfoJson === 'string') {
            gameStore.setCourseMetadata(parseCourseMetadataArray(courseInfoJson))
          }

          // 基础属性
          gameStore.updateStats(data)

          // 课程掌握度 & 策略状态：优先从 wsMsg 顶层读（新版 init），兼容旧版 data 内嵌
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
          break
        }

        case 'tick': {
          if (gameStore.currentPhase !== 'playing') {
            gameStore.setPhase('playing')
          }

          const stats = wsMsg.stats
          if (isRecord(stats)) {
            gameStore.updateStats(stats)
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

        case 'graduation': {
          const { finalStats, llmSummary: llmSummaryExtracted } = extractGraduationFinalStats(wsMsg)

          const gpaRaw = finalStats.gpa
          const gpa = typeof gpaRaw === 'number' ? gpaRaw : parseFloat(String(gpaRaw ?? 0)) || 0

          const iqRaw = finalStats.iq
          const eqRaw = finalStats.eq
          const goldRaw = finalStats.gold
          const achievementsRaw = finalStats.achievements

          const achievementsArr = Array.isArray(achievementsRaw) ? achievementsRaw : []
          const llmSummary = llmSummaryExtracted || '此子聪颖过人，勤勉有加...'

          gameStore.triggerEndGame('graduation', {
            gpa,
            iq: typeof iqRaw === 'number' ? iqRaw : Number(iqRaw ?? 100),
            eq: typeof eqRaw === 'number' ? eqRaw : Number(eqRaw ?? 100),
            gold: typeof goldRaw === 'number' ? goldRaw : Number(goldRaw ?? 0),
            achievements_count: achievementsArr.length,
            llm_summary: llmSummary,
          })
          break
        }

        case 'new_semester': {
          const nsData = isRecord(wsMsg.data) ? wsMsg.data : {}
          const newCourseJson = typeof nsData.course_info_json === 'string' ? nsData.course_info_json as string : '[]'
          const courses = parseCourseMetadataArray(newCourseJson)
          gameStore.resetForNewSemester(courses)
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
          // 未知消息类型：当前实现不强处理，避免前端因为后端新增字段而崩溃
          break
      }
    }

    ws.value.onclose = (event: CloseEvent) => {
      isConnected.value = false
      if (heartbeatInterval) clearInterval(heartbeatInterval)

      const retryableCloseCodes = new Set([1001, 1006])
      if (shouldReconnect && retryableCloseCodes.has(event.code) && reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts += 1
        gameStore.addLog('系统', `断开连接，准备重连 (${reconnectAttempts}/${maxReconnectAttempts})...`, 'text-warning')
        setTimeout(() => connect(token, baseUrl), reconnectDelay)
      }
    }
  }

  onUnmounted(() => {
    if (ws.value) ws.value.close()
    if (heartbeatInterval) clearInterval(heartbeatInterval)
  })

  return { ws, isConnected, connect, send }
}

