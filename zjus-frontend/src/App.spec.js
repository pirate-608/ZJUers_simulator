import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'
import { PROLOGUE_LINES, PROLOGUE_SEEN_STORAGE_KEY } from './data/prologue'

const webSocketMock = vi.hoisted(() => ({
  connect: vi.fn(),
  disconnect: vi.fn(),
  send: vi.fn(),
}))

vi.mock('@/composables/useGameWebSocket.ts', () => ({
  useGameWebSocket: () => ({
    connect: webSocketMock.connect,
    disconnect: webSocketMock.disconnect,
    isConnected: { value: false },
    send: webSocketMock.send,
  }),
}))

describe('App.vue', () => {
  const mountApp = () => mount(App, {
    global: {
      plugins: [createTestingPinia({
        stubActions: false, // 让 pinia 正常工作而不全是 stub
      })],
      stubs: {
        LoginView: { template: '<main data-testid="login-view">login</main>' },
        SaveSelect: { template: '<main data-testid="save-select">saves</main>' },
        CharacterCreate: { template: '<main data-testid="character-create">create</main>' },
        TopNav: true,
        HudBar: true,
        CourseList: true,
        MidPanel: true,
        RightPanel: true,
        TranscriptModal: true,
        RandomEventModal: true,
        FeedbackModal: true,
        ExamConfirmModal: true,
        ExitConfirmModal: true,
        EndScreen: true,
      },
    },
  })

  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    webSocketMock.connect.mockClear()
    webSocketMock.disconnect.mockClear()
    webSocketMock.send.mockClear()
  })

  afterEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('renders the prologue before the login flow on first visit', () => {
    const wrapper = mountApp()

    expect(wrapper.find('.prologue-root').exists()).toBe(true)
    expect(wrapper.find('[data-testid="prologue-line"]').text()).toBe(PROLOGUE_LINES[0])
    expect(wrapper.find('[data-testid="login-view"]').exists()).toBe(false)
    expect(webSocketMock.connect).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('holds returning-game startup behind the first-visit prologue until skipped', async () => {
    localStorage.setItem('zju_jwt', 'header.payload.signature')
    localStorage.setItem('zju_token', 'header.payload.signature')
    localStorage.setItem('game_started', '1')

    const wrapper = mountApp()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.prologue-root').exists()).toBe(true)
    expect(wrapper.find('.app-loading').exists()).toBe(false)
    expect(wrapper.find('[data-testid="login-view"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="save-select"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="character-create"]').exists()).toBe(false)
    expect(webSocketMock.connect).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="prologue-skip"]').trigger('click')
    await wrapper.vm.$nextTick()

    expect(localStorage.getItem(PROLOGUE_SEEN_STORAGE_KEY)).toBe('1')
    expect(wrapper.find('.prologue-root').exists()).toBe(false)
    expect(wrapper.find('.app-loading').exists()).toBe(true)
    expect(wrapper.find('[data-testid="login-view"]').exists()).toBe(false)
    expect(webSocketMock.connect).toHaveBeenCalledTimes(1)
    expect(webSocketMock.connect).toHaveBeenCalledWith(
      'header.payload.signature',
      expect.stringMatching(/^ws:\/\/|^wss:\/\//),
    )

    wrapper.unmount()
  })

  it('marks the prologue seen and starts the login flow when skipped', async () => {
    const wrapper = mountApp()

    await wrapper.find('[data-testid="prologue-skip"]').trigger('click')
    await wrapper.vm.$nextTick()

    expect(localStorage.getItem(PROLOGUE_SEEN_STORAGE_KEY)).toBe('1')
    expect(wrapper.find('.prologue-root').exists()).toBe(false)
    expect(wrapper.find('[data-testid="login-view"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('bypasses the prologue after it has been seen', async () => {
    localStorage.setItem(PROLOGUE_SEEN_STORAGE_KEY, '1')

    const wrapper = mountApp()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.prologue-root').exists()).toBe(false)
    expect(wrapper.find('[data-testid="login-view"]').exists()).toBe(true)

    wrapper.unmount()
  })
})
