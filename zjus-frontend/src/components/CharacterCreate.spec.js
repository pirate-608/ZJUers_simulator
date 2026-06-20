import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ALLOCATABLE_STATS } from '@/data/statDefinitions.generated'
import CharacterCreate from './CharacterCreate.vue'

const apiMocks = vi.hoisted(() => ({
  fetchMajors: vi.fn(),
  initCharacter: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  fetchMajors: apiMocks.fetchMajors,
  initCharacter: apiMocks.initCharacter,
}))

describe('CharacterCreate stat registry integration', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('zju_jwt', 'jwt-token')
    apiMocks.fetchMajors.mockReset()
    apiMocks.initCharacter.mockReset()
    apiMocks.fetchMajors.mockResolvedValue([
      {
        name: '计算机科学与技术',
        abbr: 'CS',
        iq_buff: 10,
        stress_base: 5,
        desc: '写代码，也写人生。',
      },
    ])
    apiMocks.initCharacter.mockResolvedValue({
      success: true,
      major: '计算机科学与技术',
      major_abbr: 'CS',
      courses: [],
    })
    setActivePinia(createPinia())
  })

  it('renders allocatable stats from generated metadata and submits stats map', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(CharacterCreate, {
      global: {
        plugins: [pinia],
      },
    })

    await flushPromises()

    for (const stat of ALLOCATABLE_STATS) {
      expect(wrapper.text()).toContain(stat.label)
    }
    expect(wrapper.findAll('input[type="range"]')).toHaveLength(
      ALLOCATABLE_STATS.length,
    )

    await wrapper.find('.major-card').trigger('click')
    await wrapper.find('button.btn-primary').trigger('click')

    expect(apiMocks.initCharacter).toHaveBeenCalledWith(
      expect.objectContaining({
        token: 'jwt-token',
        major_abbr: 'CS',
        iq: 100,
        eq: 100,
        luck: 50,
        charm: 50,
        stats: {
          iq: 100,
          eq: 100,
          luck: 50,
          charm: 50,
        },
      }),
    )
  })
})
