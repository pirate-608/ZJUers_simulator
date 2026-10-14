/** Focused modal coverage for acknowledged semester changes and holiday choices. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useGameStore } from '@/stores/gameStore'
import TranscriptModal from './TranscriptModal.vue'
import RandomEventModal from './RandomEventModal.vue'

describe('semester recovery modals', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.useFakeTimers() })
  afterEach(() => { vi.clearAllTimers(); vi.useRealTimers() })

  it('emits next_semester without hiding the transcript, then disables duplicate clicks', async () => {
    const store = useGameStore()
    store.showModal('transcript', { semester_name: '大一秋冬', courses: [] })
    const wrapper = mount(TranscriptModal)
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('send-action')).toEqual([[{ action: 'next_semester', expected_semester_idx: 1 }]])
    expect(store.activeModal).toBe('transcript')
    store.beginSemesterTransition()
    await wrapper.vm.$nextTick()
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('offers an explicit state resync after a failed confirmation', async () => {
    const store = useGameStore()
    store.showModal('transcript', {})
    store.finishSemesterTransition('暂未确认')
    const wrapper = mount(TranscriptModal)
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('send-action')).toEqual([[{ action: 'get_state' }]])
    wrapper.unmount()
  })

  it('labels holiday choices, sends the event ID and never resumes a paused game implicitly', async () => {
    const store = useGameStore()
    store.showModal('random_event', { id: 'holiday_2', kind: 'holiday', title: '返校', desc: '假期', options: [{ id: 'A', text: '休息', effects: {} }] })
    store.setPaused(true)
    const wrapper = mount(RandomEventModal)
    expect(wrapper.text()).toContain('假期回顾')
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('send-action')).toBeUndefined()
    store.setPaused(false)
    await wrapper.vm.$nextTick()
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('send-action')).toEqual([[{ action: 'event_choice', option_id: 'A', event_id: 'holiday_2' }]])
    wrapper.unmount()
  })
})
