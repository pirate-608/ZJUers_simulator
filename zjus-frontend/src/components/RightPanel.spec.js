import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import RightPanel from './RightPanel.vue'
import ExamConfirmModal from './modals/ExamConfirmModal.vue'
import { useGameStore } from '../stores/gameStore'

describe('RightPanel exam confirmation', () => {
  beforeEach(() => {
    vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('opens a confirmation modal instead of sending exam immediately', async () => {
    const wrapper = mount(RightPanel, {
      global: {
        plugins: [createTestingPinia({ stubActions: false })],
      },
    })
    const store = useGameStore()
    store.currentStats.exam_completed = 0

    await wrapper.find('.exam-btn').trigger('click')

    expect(store.activeModal).toBe('exam_confirm')
    expect(wrapper.emitted('send-action')).toBeUndefined()

    wrapper.unmount()
  })

  it('sends exam only after the confirmation is accepted', async () => {
    const wrapper = mount(ExamConfirmModal, {
      global: {
        plugins: [createTestingPinia({ stubActions: false })],
      },
    })
    const store = useGameStore()
    store.showModal('exam_confirm')
    await wrapper.vm.$nextTick()

    await wrapper.find('.confirm-btn').trigger('click')

    expect(store.activeModal).toBeNull()
    expect(wrapper.emitted('send-action')).toEqual([[{ action: 'exam' }]])

    wrapper.unmount()
  })
})
