import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ALLOCATABLE_STATS } from '@/data/statDefinitions.generated'
import EndScreen from './EndScreen.vue'
import { useGameStore } from '../stores/gameStore'

describe('EndScreen navigation actions', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('offers a return-home action on game over', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useGameStore()
    store.triggerEndGame('game_over', { reason: '心态崩了' })

    const wrapper = mount(EndScreen, {
      global: {
        plugins: [pinia],
      },
    })

    const homeButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('回到首页'))

    expect(homeButton).toBeTruthy()
    await homeButton.trigger('click')

    expect(wrapper.emitted('go-home')).toHaveLength(1)
  })

  it('shows the GPA-specific graduation line', () => {
    vi.useFakeTimers()
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useGameStore()
    store.triggerEndGame('graduation', { gpa: 3.8, llm_summary: '毕业快乐' })

    const wrapper = mount(EndScreen, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.text()).toContain('虽然仍旧平凡，但这一次我问心无愧')
    for (const stat of ALLOCATABLE_STATS) {
      expect(wrapper.text()).toContain(stat.label)
      expect(wrapper.text()).toContain(String(stat.default))
    }
    wrapper.unmount()
  })
})
