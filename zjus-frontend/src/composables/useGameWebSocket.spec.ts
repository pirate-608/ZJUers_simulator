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

  it('keeps the transcript pending, deduplicates clicks and probes state before timeout', () => {
    const store = useGameStore()
    const { connect, send } = useGameWebSocket()
    connect('token', 'ws://game.test')
    const socket = MockWebSocket.instances[0]
    store.showModal('transcript', { semester_idx: 1 })
    send({ action: 'next_semester' })
    send({ action: 'next_semester' })
    expect(socket.sent.map((frame) => JSON.parse(frame))).toEqual([{ action: 'next_semester', expected_semester_idx: 1 }])
    expect(store.activeModal).toBe('transcript')
    expect(store.isPendingSemesterTransition).toBe(true)
    vi.advanceTimersByTime(5000)
    expect(JSON.parse(socket.sent.at(-1)!)).toEqual({ action: 'get_state' })
    vi.advanceTimersByTime(10000)
    expect(store.isPendingSemesterTransition).toBe(false)
    expect(store.semesterTransitionError).not.toBe('')
    expect(store.activeModal).toBe('transcript')
  })

  it.each(['new_semester', 'tick', 'state'])('recovers a complete new term from %s, not just its title', (type) => {
    const store = useGameStore()
    const { connect, send } = useGameWebSocket()
    connect('token', 'ws://game.test')
    store.currentStats.exam_completed = 1
    store.updateCourseProgress({ old: 91 })
    store.updateCourseStatesRaw({ old: 2 })
    store.setPaused(true)
    store.setConsoleTheme('yunfeng')
    store.setGameSpeed(2)
    store.ownedItems = ['planner']
    store.showModal('transcript', {})
    send({ action: 'next_semester' })
    const stats = { semester_idx: 2, semester: '大一春夏', exam_completed: 0, course_info_json: '[{"id":"new","name":"新课程","credits":4}]' }
    const payload = { stats, courses: { new: 0 }, course_states: { new: 1 }, semester_time_left: 360 }
    const socket = MockWebSocket.instances[0]
    socket.emitMessage(type === 'tick' ? { type, ...payload }
      : type === 'new_semester' ? { type, data: payload }
        : { type, data: { ...stats, courses: payload.courses, course_states: payload.course_states, semester_time_left: 360 } })
    expect(store.currentStats.semester_idx).toBe(2)
    expect(Object.keys(store.currentStats.courses)).toEqual(['new'])
    expect(Object.keys(store.currentCourseStates)).toEqual(['new'])
    expect(store.courseMetadata[0].credit).toBe(4)
    expect(store.activeModal).toBe(null)
    expect(store.isPaused).toBe(false)
    expect(store.isPendingSemesterTransition).toBe(false)
    expect(store.semesterTimeLeft).toBe(360)
    expect(store.consoleTheme).toBe('yunfeng')
    expect(store.gameSpeed).toBe(2)
    expect(store.ownedItems).toEqual(['planner'])
    const count = socket.sent.length
    vi.advanceTimersByTime(15000)
    expect(socket.sent.length).toBe(count)
  })

  it('ignores old-term ticks, events and transcripts after a confirmed transition', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()
    connect('token', 'ws://game.test')
    store.currentStats.semester_idx = 2
    store.semesterTimeLeft = 300
    const socket = MockWebSocket.instances[0]
    socket.emitMessage({ type: 'tick', stats: { semester_idx: 1, semester: '旧学期' }, courses: { old: 90 }, semester_time_left: 0 })
    socket.emitMessage({ type: 'semester_summary', data: { semester_idx: 1 } })
    socket.emitMessage({ type: 'random_event', data: { semester_idx: 1, title: '过期事件' } })
    expect(store.currentStats.semester_idx).toBe(2)
    expect(store.semesterTimeLeft).toBe(300)
    expect(store.activeModal).toBe(null)
    expect(store.currentStats.courses.old).toBeUndefined()
  })

  it('keeps autosave warnings separate from transition and exit confirmations', () => {
    const store = useGameStore()
    const { connect, send } = useGameWebSocket()
    connect('token', 'ws://game.test')
    send({ action: 'next_semester' })
    store.isPendingExit = true
    const socket = MockWebSocket.instances[0]
    socket.emitMessage({ type: 'toast', action: 'semester_autosave', level: 'warning', message: '自动保存失败' })
    expect(store.isPendingSemesterTransition).toBe(true)
    expect(store.isPendingExit).toBe(true)
    socket.emitMessage({ type: 'toast', action: 'next_semester', level: 'warning', message: '请重试' })
    expect(store.isPendingSemesterTransition).toBe(false)
    expect(store.semesterTransitionError).toBe('请重试')
  })

  it('does not leave the transcript waiting when disconnected or intentionally closed', () => {
    const store = useGameStore()
    const { connect, send, disconnect } = useGameWebSocket()
    store.showModal('transcript', {})
    send({ action: 'next_semester' })
    expect(store.isPendingSemesterTransition).toBe(false)
    expect(store.semesterTransitionError).not.toBe('')
    connect('token', 'ws://game.test')
    send({ action: 'next_semester' })
    disconnect()
    vi.advanceTimersByTime(15000)
    expect(store.isPendingSemesterTransition).toBe(false)
  })

  it('shows a holiday in the new term but does not let a late tick reopen an end screen', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()
    connect('token', 'ws://game.test')
    store.setPhase('playing')
    const socket = MockWebSocket.instances[0]
    socket.emitMessage({ type: 'random_event', data: { kind: 'holiday', id: 'holiday_1', semester_idx: 1, title: '假期' } })
    expect(store.activeModal).toBe('random_event')
    store.triggerEndGame('game_over', {})
    socket.emitMessage({ type: 'tick', stats: { semester_idx: 1 } })
    expect(store.currentPhase).toBe('ended')
    expect(store.activeModal).toBe(null)
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
                desc: '情商和魅力均达到 90 以上，并完成 3 轮钉钉对话',
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
        desc: '情商和魅力均达到 90 以上，并完成 3 轮钉钉对话',
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

  it('does not warn or reconnect when save-and-exit closes after success confirmation', () => {
    const store = useGameStore()
    const { connect } = useGameWebSocket()

    connect('token', 'ws://game.test')
    store.isPendingExit = true
    MockWebSocket.instances[0].emitMessage({
      type: 'save_result',
      success: true,
      message: '存档保存成功',
    })
    const timersAfterSaveResult = vi.getTimerCount()
    MockWebSocket.instances[0].emitClose(1000)

    expect(store.isPendingExit).toBe(false)
    expect(store.toast).toMatchObject({
      type: 'success',
      message: '存档保存成功',
    })
    expect(vi.getTimerCount()).toBe(timersAfterSaveResult + 1)
    expect(MockWebSocket.instances).toHaveLength(1)
  })
})
