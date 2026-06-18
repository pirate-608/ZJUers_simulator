import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import MidPanel from './MidPanel.vue'
import { useGameStore } from '../stores/gameStore'

const replyableContact = {
  contact_id: 'dt_roommate',
  sender: '【室友】',
  role: 'roommate',
  is_replyable: true,
  is_urgent: false,
  unread_count: 1,
  last_message_at: 1,
  messages: [
    {
      message_id: 'm1',
      speaker: 'npc',
      content: '你在吗？',
      created_at: 1,
      round_id: 'r1',
    },
  ],
  pending_options: [{ option_id: 'opt_1', text: '在的' }],
  round: { round_id: 'r1', status: 'open', player_reply_count: 0 },
}

function mountWithContact(paused = false) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useGameStore()
  store.setDingTalkState({
    version: 1,
    updated_at: 1,
    contacts: {
      [replyableContact.contact_id]: replyableContact,
    },
  })
  store.setPaused(paused)

  const wrapper = mount(MidPanel, {
    global: {
      plugins: [pinia],
    },
  })
  return { wrapper, store }
}

function mountWithItems(paused = false, gold = 100, owned = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useGameStore()
  store.updateStats({ gold })
  store.setItemsState({
    version: 1,
    updated_at: 1,
    items: [
      {
        id: 'planner',
        name: '求是日程本',
        category: '学习',
        description: '规划 ddl',
        price: 80,
        sell_price: 40,
        tags: ['学习'],
        effects: { iq: 4, stress: -2 },
      },
      {
        id: 'bike',
        name: '校园单车月卡',
        category: '生活',
        description: '赶课更轻松',
        price: 60,
        sell_price: 30,
        tags: ['通勤'],
        effects: { energy: 5 },
      },
    ],
    owned,
    bonuses: owned.includes('planner') ? { iq: 4, stress: -2 } : {},
  })
  store.setPaused(paused)

  const wrapper = mount(MidPanel, {
    global: {
      plugins: [pinia],
    },
  })
  return { wrapper, store }
}

async function openDingTalkTab(wrapper) {
  await wrapper.findAll('.nav-link')[1].trigger('click')
  await wrapper.vm.$nextTick()
}

async function openItemsTab(wrapper) {
  await wrapper.findAll('.nav-link')[2].trigger('click')
  await wrapper.vm.$nextTick()
}

describe('MidPanel DingTalk reply controls', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('sends a DingTalk reply while the game is running', async () => {
    const { wrapper } = mountWithContact(false)
    await openDingTalkTab(wrapper)

    await wrapper.find('.ding-replies button').trigger('click')

    expect(wrapper.emitted('send-action')).toEqual([
      [{ action: 'dingtalk_mark_read', contact_id: 'dt_roommate' }],
      [{ action: 'dingtalk_reply', contact_id: 'dt_roommate', option_id: 'opt_1' }],
    ])
  })

  it('cools down DingTalk reply options while the game is paused', async () => {
    const { wrapper } = mountWithContact(true)
    await openDingTalkTab(wrapper)

    const replyButton = wrapper.find('.ding-replies button')
    expect(replyButton.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('游戏暂停中，回复选项冷却中')

    await replyButton.trigger('click')

    const emittedActions = wrapper.emitted('send-action') || []
    expect(
      emittedActions.some(([payload]) => payload.action === 'dingtalk_reply'),
    ).toBe(false)
  })
})

describe('MidPanel item controls', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('filters items and emits a buy action for affordable items', async () => {
    const { wrapper } = mountWithItems(false, 100)
    await openItemsTab(wrapper)

    await wrapper.find('.item-search').setValue('日程')
    expect(wrapper.text()).toContain('求是日程本')
    expect(wrapper.text()).not.toContain('校园单车月卡')

    await wrapper.find('.item-action-btn').trigger('click')

    const emittedActions = wrapper.emitted('send-action') || []
    expect(emittedActions.some(([payload]) => (
      payload.action === 'item_buy' && payload.item_id === 'planner'
    ))).toBe(true)
  })

  it('emits a sell action for owned items', async () => {
    const { wrapper } = mountWithItems(false, 100, ['planner'])
    await openItemsTab(wrapper)

    await wrapper.find('.item-action-btn').trigger('click')

    const emittedActions = wrapper.emitted('send-action') || []
    expect(emittedActions.some(([payload]) => (
      payload.action === 'item_sell' && payload.item_id === 'planner'
    ))).toBe(true)
  })

  it('disables item buy and sell actions while paused', async () => {
    const { wrapper } = mountWithItems(true, 100)
    await openItemsTab(wrapper)

    const button = wrapper.find('.item-action-btn')
    expect(button.attributes('disabled')).toBeDefined()

    await button.trigger('click')

    const emittedActions = wrapper.emitted('send-action') || []
    expect(emittedActions.some(([payload]) => payload.action?.startsWith('item_'))).toBe(false)
  })
})
