import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import { useGameWebSocket } from './useGameWebSocket'

class MockWebSocket {
  static OPEN = 1
  static CLOSED = 3
  static instances: MockWebSocket[] = []

  readonly url: string
  readyState = MockWebSocket.OPEN
  sent: string[] = []
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(data)
  }

  close(code = 1000) {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close', { code }))
  }

  emitClose(code: number) {
    this.close(code)
  }

  emitMessage(payload: Record<string, unknown>) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(payload) }))
  }
}

describe('useGameWebSocket', () => {
  let originalWebSocket: typeof WebSocket

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    MockWebSocket.instances = []
    originalWebSocket = globalThis.WebSocket
    globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket
  })

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('keeps a connected status log after init resets runtime state', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()

    connect('token', 'ws://game.test')
    const socket = MockWebSocket.instances[0]
    socket.onopen?.(new Event('open'))
    socket.emitMessage({ type: 'auth_ok' })
    socket.emitMessage({
      type: 'init',
      data: {
        username: 'tester',
        course_info_json: '[]',
      },
      courses: {},
      course_states: {},
      semester_time_left: 120,
    })

    expect(store.currentPhase).toBe('playing')
    expect(store.eventLogs).toHaveLength(1)
    expect(store.eventLogs[0]).toMatchObject({
      type: '系统',
      message: '已连接折大服务器，游戏状态已同步。',
      cssClass: 'text-success',
    })
  })

  it('stores feedback stat changes for the result modal', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()

    connect('token', 'ws://game.test')
    MockWebSocket.instances[0].emitMessage({
      type: 'feedback',
      data: {
        title: '事件结果',
        message: '你做出了选择。',
        kind: 'event',
        changes: [
          { field: 'sanity', label: '心态', delta: -3, value: 67 },
          { field: 'stress', label: '压力', delta: 5, value: 45 },
        ],
      },
    })

    expect(store.feedbackModal).toMatchObject({
      title: '事件结果',
      message: '你做出了选择。',
      changes: [
        { field: 'sanity', label: '心态', delta: -3, value: 67 },
        { field: 'stress', label: '压力', delta: 5, value: 45 },
      ],
    })
  })

  it('applies new semester state and timer from the transition message', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()

    connect('token', 'ws://game.test')
    MockWebSocket.instances[0].emitMessage({
      type: 'new_semester',
      data: {
        semester_name: '大一春夏',
        stats: {
          semester: '大一春夏',
          semester_idx: 2,
          course_info_json: '[{"id":"cs101","name":"程序设计基础"}]',
        },
        courses: { cs101: 0 },
        course_states: { cs101: 1 },
        course_info_json: '[{"id":"cs101","name":"程序设计基础"}]',
        semester_time_left: 180,
      },
    })

    expect(store.currentStats.semester).toBe('大一春夏')
    expect(store.currentStats.semester_idx).toBe(2)
    expect(store.semesterTimeLeft).toBe(180)
    expect(store.courseMetadata).toEqual([{ id: 'cs101', name: '程序设计基础' }])
    expect(store.currentStats.courses.cs101).toMatchObject({ progress: 0, state: 1 })
  })

  it('cancels a scheduled reconnect when the owning component unmounts', () => {
    const Harness = defineComponent({
      setup() {
        const { connect } = useGameWebSocket()
        connect('token', 'ws://game.test')
        return () => null
      },
    })
    const wrapper = mount(Harness, {
      global: {
        plugins: [createPinia()],
      },
    })

    expect(MockWebSocket.instances).toHaveLength(1)
    MockWebSocket.instances[0].emitClose(1006)

    wrapper.unmount()
    vi.advanceTimersByTime(3000)

    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('releases save-and-exit pending state and reconnects if the socket closes before confirmation', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()

    connect('token', 'ws://game.test')
    store.isPendingExit = true
    MockWebSocket.instances[0].emitClose(1000)

    expect(store.isPendingExit).toBe(false)
    expect(store.toast).toMatchObject({
      type: 'warning',
      message: '连接在保存确认前断开，请重试保存并退出。',
    })

    vi.advanceTimersByTime(3000)

    expect(MockWebSocket.instances).toHaveLength(2)
  })
})
