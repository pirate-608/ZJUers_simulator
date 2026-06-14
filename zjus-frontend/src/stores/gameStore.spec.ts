import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGameStore } from './gameStore'

describe('gameStore DingTalk threads', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('restores contacts and recalculates unread count', () => {
    const store = useGameStore()

    store.setDingTalkState({
      version: 1,
      updated_at: 1,
      contacts: {
        dt_roommate: {
          contact_id: 'dt_roommate',
          sender: '【室友】',
          role: 'roommate',
          is_replyable: true,
          is_urgent: false,
          unread_count: 2,
          last_message_at: 10,
          messages: [],
          pending_options: [],
          round: { round_id: '', status: 'closed', player_reply_count: 0 },
        },
      },
    })

    expect(store.unreadDingtalk).toBe(2)
    expect(store.dingtalkContacts.dt_roommate.sender).toBe('【室友】')
  })

  it('marks one contact read without clearing other contacts', () => {
    const store = useGameStore()
    store.setDingTalkState({
      version: 1,
      updated_at: 1,
      contacts: {
        a: {
          contact_id: 'a',
          sender: 'A',
          role: 'roommate',
          is_replyable: true,
          is_urgent: false,
          unread_count: 1,
          last_message_at: 1,
          messages: [],
          pending_options: [],
          round: { round_id: '', status: 'closed', player_reply_count: 0 },
        },
        b: {
          contact_id: 'b',
          sender: 'B',
          role: 'teacher',
          is_replyable: true,
          is_urgent: true,
          unread_count: 3,
          last_message_at: 2,
          messages: [],
          pending_options: [],
          round: { round_id: '', status: 'closed', player_reply_count: 0 },
        },
      },
    })

    store.markDingContactReadLocal('a')

    expect(store.dingtalkContacts.a.unread_count).toBe(0)
    expect(store.dingtalkContacts.b.unread_count).toBe(3)
    expect(store.unreadDingtalk).toBe(3)
  })
})

describe('gameStore console theme', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('defaults to the Lantian theme when storage is empty or invalid', () => {
    let store = useGameStore()
    expect(store.consoleTheme).toBe('lantian')

    localStorage.setItem('zjus_console_theme', 'unknown')
    setActivePinia(createPinia())
    store = useGameStore()

    expect(store.consoleTheme).toBe('lantian')
  })

  it('persists the selected console theme', () => {
    const store = useGameStore()

    store.setConsoleTheme('yunfeng')

    expect(store.consoleTheme).toBe('yunfeng')
    expect(localStorage.getItem('zjus_console_theme')).toBe('yunfeng')
  })
})
