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
    localStorage.clear()
    sessionStorage.clear()
    MockWebSocket.instances = []
    originalWebSocket = globalThis.WebSocket
    globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket
  })

  afterEach(() => {
    localStorage.clear()
    sessionStorage.clear()
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

  it('sends session-scoped general and RP model overrides in the auth payload', () => {
    const { connect } = useGameWebSocket()
    sessionStorage.setItem('custom_llm_provider', 'deepseek')
    sessionStorage.setItem('custom_llm_model', 'deepseek-chat')
    sessionStorage.setItem('custom_llm_key', 'sk-general')
    sessionStorage.setItem('custom_rp_key', 'sk-minimax-rp')

    connect('token', 'ws://game.test')
    const socket = MockWebSocket.instances[0]
    socket.onopen?.(new Event('open'))

    expect(socket.sent).toHaveLength(1)
    expect(JSON.parse(socket.sent[0])).toMatchObject({
      token: 'token',
      custom_llm_provider: 'deepseek',
      custom_llm_model: 'deepseek-chat',
      custom_llm_api_key: 'sk-general',
      custom_rp_api_key: 'sk-minimax-rp',
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

  it('stores achievement unlock events and shows feedback', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()

    connect('token', 'ws://game.test')
    MockWebSocket.instances[0].emitMessage({
      type: 'achievement_unlocked',
      data: {
        code: 'gpa_king',
        name: '卷王之王',
        desc: '单学期 GPA 达到 4.5',
        icon: '👑',
      },
    })

    expect(store.unlockedAchievements).toEqual([
      {
        code: 'gpa_king',
        name: '卷王之王',
        desc: '单学期 GPA 达到 4.5',
        icon: '👑',
      },
    ])
    expect(store.feedbackModal).toMatchObject({
      title: '成就解锁',
      message: '👑 卷王之王：单学期 GPA 达到 4.5',
    })
  })

  it('stores item state messages from the server', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()

    connect('token', 'ws://game.test')
    MockWebSocket.instances[0].emitMessage({
      type: 'items_state',
      data: {
        items: [
          {
            id: 'planner',
            name: '求是日程本',
            category: '学习',
            description: '规划 ddl',
            price: 80,
            sell_price: 40,
            tags: ['学习'],
            effects: { iq: 4 },
          },
        ],
        owned: ['planner'],
        bonuses: { iq: 4 },
        updated_at: 1,
      },
    })

    expect(store.itemCatalog[0].id).toBe('planner')
    expect(store.ownedItems).toEqual(['planner'])
    expect(store.itemBonuses.iq).toBe(4)
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
    expect(store.courseMetadata).toEqual([
      { id: 'cs101', name: '程序设计基础', credit: 0, credits: 0 },
    ])
    expect(store.currentStats.courses.cs101).toMatchObject({ progress: 0, state: 1 })
  })

  it('stores graduation achievement details', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()

    connect('token', 'ws://game.test')
    MockWebSocket.instances[0].emitMessage({
      type: 'graduation',
      data: {
        data: {
          final_stats: {
            gpa: '3.9',
            iq: 110,
            eq: 108,
            charm: 95,
            gold: 300,
            achievements: ['social_butterfly'],
            achievement_details: [
              {
                code: 'social_butterfly',
                name: '紫金港交际花',
                desc: '情商或魅力达到 95 以上',
                icon: '🌸',
              },
            ],
          },
          wenyan_report: '学业既成。',
        },
      },
    })

    expect(store.currentPhase).toBe('ended')
    expect(store.endType).toBe('graduation')
    expect(store.endData.achievements_count).toBe(1)
    expect(store.endData.achievement_details).toEqual([
      {
        code: 'social_butterfly',
        name: '紫金港交际花',
        desc: '情商或魅力达到 95 以上',
        icon: '🌸',
      },
    ])
  })

  it('refreshes course metadata from tick stats when the transition message is missed', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()

    connect('token', 'ws://game.test')
    store.setCourseMetadata([{ id: 'old101', name: '旧学期课程', credit: 1 }])

    MockWebSocket.instances[0].emitMessage({
      type: 'tick',
      stats: {
        semester: '大一春夏',
        semester_idx: 2,
        course_info_json: '[{"id":"cs102","name":"数据结构","credits":4}]',
      },
      courses: { cs102: 12 },
      course_states: { cs102: 2 },
      semester_time_left: 180,
    })

    expect(store.currentStats.semester).toBe('大一春夏')
    expect(store.courseMetadata).toEqual([
      { id: 'cs102', name: '数据结构', credits: 4, credit: 4 },
    ])
    expect(store.currentStats.courses.cs102).toMatchObject({ progress: 12, state: 2 })
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

  it('disconnects without scheduling a reconnect', () => {
    const { connect, disconnect, isConnected } = useGameWebSocket()

    connect('token', 'ws://game.test')
    const socket = MockWebSocket.instances[0]
    socket.onopen?.(new Event('open'))
    socket.emitMessage({ type: 'auth_ok' })
    expect(isConnected.value).toBe(true)

    disconnect()
    vi.advanceTimersByTime(3000)

    expect(isConnected.value).toBe(false)
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
