import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'

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

describe('App.vue entry flow', () => {
  let wrapper

  const mountApp = () => {
    wrapper = mount(App, {
      global: {
        plugins: [createTestingPinia({ stubActions: false })],
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
    return wrapper
  }

  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    wrapper?.unmount()
    localStorage.clear()
    sessionStorage.clear()
  })

  it.each([null, '1'])('opens login directly with legacy seen flag %s', async (seenFlag) => {
    if (seenFlag !== null) localStorage.setItem('zjus_prologue_seen_v1', seenFlag)

    const app = mountApp()
    await app.vm.$nextTick()

    expect(app.find('[data-testid="login-view"]').exists()).toBe(true)
    expect(app.find('.prologue-root').exists()).toBe(false)
    expect(localStorage.getItem('zjus_prologue_seen_v1')).toBe(seenFlag)
    expect(webSocketMock.connect).not.toHaveBeenCalled()
  })

  it('opens save selection directly for an authenticated returning player', async () => {
    localStorage.setItem('zju_jwt', 'header.payload.signature')
    localStorage.setItem('zju_saves', JSON.stringify([{ slot: 1 }]))

    const app = mountApp()
    await app.vm.$nextTick()

    expect(app.find('[data-testid="save-select"]').exists()).toBe(true)
    expect(app.find('[data-testid="login-view"]').exists()).toBe(false)
    expect(localStorage.getItem('zju_token')).toBe('header.payload.signature')
    expect(webSocketMock.connect).not.toHaveBeenCalled()
  })

  it('opens character creation directly when a JWT has no started game or saves', async () => {
    localStorage.setItem('zju_jwt', 'header.payload.signature')

    const app = mountApp()
    await app.vm.$nextTick()

    expect(app.find('[data-testid="character-create"]').exists()).toBe(true)
    expect(app.find('[data-testid="login-view"]').exists()).toBe(false)
    expect(webSocketMock.connect).not.toHaveBeenCalled()
  })

  it('connects a started game once without waiting for a prologue callback', async () => {
    localStorage.setItem('zju_jwt', 'header.payload.signature')
    localStorage.setItem('game_started', '1')
    localStorage.setItem('selected_save_slot', '1')

    const app = mountApp()
    await app.vm.$nextTick()

    expect(app.find('.app-loading').exists()).toBe(true)
    expect(app.find('.prologue-root').exists()).toBe(false)
    expect(webSocketMock.connect).toHaveBeenCalledExactlyOnceWith(
      'header.payload.signature',
      expect.stringMatching(/^wss?:\/\//),
    )
    expect(localStorage.getItem('selected_save_slot')).toBe('1')
  })

  it('keeps legacy student credentials out of the game WebSocket handshake', async () => {
    localStorage.setItem('zju_token', 'legacy-student-credential')
    localStorage.setItem('game_started', '1')

    const app = mountApp()
    await app.vm.$nextTick()

    expect(app.find('[data-testid="login-view"]').exists()).toBe(true)
    expect(localStorage.getItem('zju_token')).toBeNull()
    expect(localStorage.getItem('zju_user_token')).toBe('legacy-student-credential')
    expect(webSocketMock.connect).not.toHaveBeenCalled()
  })
})
