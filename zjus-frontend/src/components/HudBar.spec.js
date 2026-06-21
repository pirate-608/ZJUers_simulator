import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { STAT_META_BY_ID } from '@/data/statDefinitions.generated'
import { useGameStore } from '../stores/gameStore'
import HudBar from './HudBar.vue'

describe('HudBar stat registry display', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('uses generated stat metadata for labels, defaults, caps, and bar width', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useGameStore()
    store.currentStats.energy = 150

    const wrapper = mount(HudBar, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.text()).toContain(STAT_META_BY_ID.energy.label)
    expect(wrapper.text()).toContain(`150 / ${STAT_META_BY_ID.energy.max}`)
    expect(wrapper.text()).toContain(STAT_META_BY_ID.gold.label)
    expect(wrapper.find('.stat-bar-energy').attributes('style')).toContain('75%')
  })
})
