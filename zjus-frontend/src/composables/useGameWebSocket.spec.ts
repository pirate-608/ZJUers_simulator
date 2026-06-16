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
})
