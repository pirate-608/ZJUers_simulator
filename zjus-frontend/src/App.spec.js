import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import App from './App.vue'
import { PROLOGUE_SEEN_STORAGE_KEY } from './data/prologue'

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
        ExitConfirmModal: true,
        EndScreen: true,
      },
    },
  })

  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('renders the prologue before the login flow on first visit', () => {
    const wrapper = mountApp()

    expect(wrapper.find('.prologue-root').exists()).toBe(true)
    expect(wrapper.find('[data-testid="prologue-line"]').text()).toBe('我被卡住了')
    expect(wrapper.find('[data-testid="login-view"]').exists()).toBe(false)

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
