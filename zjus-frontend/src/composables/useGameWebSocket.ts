import { ref, onUnmounted } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { CoursesMap } from '../types/course'
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

export function useGameWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const gameStore = useGameStore()

  let reconnectAttempts = 0
  const maxReconnectAttempts = 3
  const reconnectDelay = 3000
  let heartbeatInterval: ReturnType<typeof setInterval> | null = null

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
    ws.value = new WebSocket(`${baseUrl}/ws/game`)

    ws.value.onopen = () => {
      const llmProvider = sessionStorage.getItem('custom_llm_provider')
      const llmModel = sessionStorage.getItem('custom_llm_model')
      const llmKey = sessionStorage.getItem('custom_llm_key')

      const payload: Record<string, unknown> = { token }
      if (llmProvider) payload.custom_llm_provider = llmProvider
      if (llmModel && llmModel.trim() !== '') payload.custom_llm_model = llmModel.trim()
      if (llmKey && llmKey.trim() !== '') payload.custom_llm_api_key = llmKey.trim()

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
        'game_over',
        'semester_summary',
        'random_event',
        'dingtalk_message',
        'graduation',
        'new_semester',
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
          send({ action: 'start' })
          send({ action: 'resume' })
          send({ action: 'get_state' })
          break
        }

        case 'auth_error': {
          const message = typeof wsMsg.message === 'string' ? wsMsg.message : '认证失败'
          gameStore.addLog('系统', message, 'text-danger')
          break
        }

        case 'init': {
          const data = isRecord(wsMsg.data) ? wsMsg.data : {}
          gameStore.setPhase('playing')
          gameStore.userInfo = data

          // 静态元数据
          const courseInfoJson = data.course_info_json
          if (typeof courseInfoJson === 'string') {
            gameStore.setCourseMetadata(JSON.parse(courseInfoJson))
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
          gameStore.setCourseMetadata([])
          gameStore.updateCourseProgress({})
          gameStore.updateCourseStatesRaw({})
          gameStore.clearEventLogs()
          const semesterName = extractNewSemesterName(wsMsg)
          gameStore.addLog('系统', `=== 欢迎来到 ${semesterName} ===`, 'text-success fw-bold')
          break
        }

        case 'save_result': {
          const message = typeof wsMsg.message === 'string' ? wsMsg.message : ''
          const success = typeof wsMsg.success === 'boolean' ? wsMsg.success : false
          gameStore.showToast(message, success ? 'success' : 'danger')

          if (gameStore.isPendingExit && success) {
            localStorage.removeItem('zju_token')
            localStorage.removeItem('game_started')
            window.location.reload()
          } else if (gameStore.isPendingExit && !success) {
            gameStore.isPendingExit = false
            gameStore.addLog('系统', '保存失败，无法安全退出！', 'text-danger')
          }
          break
        }

        case 'exit_confirmed': {
          localStorage.removeItem('zju_token')
          localStorage.removeItem('game_started')
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

      if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
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

