<template>
  <div
    id="tour-mid-panel"
    class="card mid-panel-card mb-3 d-flex flex-column h-100"
  >
    <div class="card-header pb-0 mid-panel-header">
      <ul
        class="nav nav-tabs card-header-tabs"
        role="tablist"
      >
        <li class="nav-item">
          <button
            class="nav-link"
            :class="{ active: activeTab === 'events' }"
            @click="switchTab('events')"
          >
            📅 求是园动态
          </button>
        </li>
        <li class="nav-item">
          <button
            class="nav-link d-flex align-items-center gap-2"
            :class="{ active: activeTab === 'dingtalk' }"
            @click="switchTab('dingtalk')"
          >
            💬 钉钉
            <span
              v-if="store.unreadDingtalk > 0"
              class="badge ding-tab-unread rounded-pill pulse-animation"
            >
              {{ store.unreadDingtalk }}
            </span>
          </button>
        </li>
        <li class="nav-item">
          <button
            class="nav-link"
            :class="{ active: activeTab === 'items' }"
            @click="switchTab('items')"
          >
            🛠️ 道具
          </button>
        </li>
      </ul>
    </div>

    <div
      class="card-body p-0 position-relative mid-panel-body"
    >
      <div
        v-if="activeTab === 'events'"
        class="h-100 d-flex flex-column"
      >
        <div
          class="event-log flex-grow-1 overflow-auto border-0 p-3"
        >
          <div
            v-if="store.eventLogs.length === 0"
            class="text-muted"
          >
            暂无求是园动态
          </div>
          <div
            v-for="log in store.eventLogs"
            :key="log.id"
            class="small mb-1"
            :class="log.cssClass"
          >
            <b>[{{ log.type }}]</b> {{ log.message }}
          </div>
        </div>
        <div class="text-end border-top py-1 px-2 event-log-footer">
          <button
            class="btn btn-link btn-sm text-decoration-none text-secondary"
            @click="store.clearEventLogs()"
          >
            清空日志
          </button>
        </div>
      </div>

      <div
        v-if="activeTab === 'dingtalk'"
        class="dingtalk-shell h-100"
      >
        <div class="ding-contact-list border-end">
          <div
            v-if="sortedContacts.length === 0"
            class="text-center text-muted small px-2 py-4"
          >
            <p class="mb-1">暂无联系人</p>
            <p class="mb-0">收到第一条消息后会出现在这里</p>
          </div>

          <button
            v-for="contact in sortedContacts"
            :key="contact.contact_id"
            type="button"
            class="ding-contact"
            :class="{ active: activeContactId === contact.contact_id }"
            @click="selectContact(contact.contact_id)"
          >
            <span
              class="ding-avatar"
              :style="{ backgroundColor: getRoleConfig(contact.role).bg }"
            >
              {{ getRoleConfig(contact.role).icon }}
            </span>
            <span class="ding-contact-main">
              <span class="ding-contact-name">
                {{ contact.sender || getRoleConfig(contact.role).name }}
              </span>
              <span class="ding-contact-preview">
                {{ contactPreview(contact) }}
              </span>
            </span>
            <span
              v-if="contact.unread_count > 0"
              class="ding-unread"
            >
              {{ contact.unread_count }}
            </span>
          </button>
        </div>

        <div class="ding-thread">
          <div
            v-if="!activeContact"
            class="h-100 d-flex align-items-center justify-content-center text-muted small"
          >
            选择一个联系人查看私聊
          </div>

          <template v-else>
            <div class="ding-thread-header border-bottom">
              <div>
                <div class="fw-bold text-dark">
                  {{ activeContact.sender }}
                  <span
                    v-if="activeContact.is_urgent"
                    class="badge urgent-badge ms-1"
                  >紧急</span>
                </div>
                <div class="text-muted small">
                  {{ getRoleConfig(activeContact.role).name }}
                </div>
              </div>
            </div>

            <div
              ref="dingScrollContainer"
              class="ding-messages"
            >
              <div
                v-for="msg in activeContact.messages"
                :key="msg.message_id"
                class="ding-bubble-row"
                :class="msg.speaker === 'player' ? 'from-player' : 'from-npc'"
              >
                <div class="ding-bubble">
                  <p class="mb-0">
                    {{ msg.content }}
                  </p>
                  <span class="ding-time">{{ formatTime(msg.created_at) }}</span>
                </div>
              </div>
            </div>

            <div class="ding-replies border-top">
              <template v-if="activeContact.pending_options.length > 0">
                <button
                  v-for="option in activeContact.pending_options"
                  :key="option.option_id"
                  type="button"
                  class="btn btn-outline-primary btn-sm text-start"
                  :disabled="store.isPaused"
                  :title="store.isPaused ? '游戏暂停中，回复选项冷却中' : option.text"
                  @click="sendReply(option.option_id)"
                >
                  {{ option.text }}
                </button>
                <div
                  v-if="store.isPaused"
                  class="reply-paused-hint text-muted small"
                >
                  游戏暂停中，回复选项冷却中
                </div>
              </template>
              <div
                v-else
                class="text-muted small text-center py-2"
              >
                {{ isContactReplyable(activeContact) ? '等待对方的新消息' : '该联系人暂不支持回复' }}
              </div>
            </div>
          </template>
        </div>
      </div>

      <div
        v-if="activeTab === 'items'"
        class="item-shell h-100"
      >
        <div class="item-toolbar">
          <div>
            <div class="item-kicker">
              Backpack
            </div>
            <div class="item-gold">
              金币 {{ goldAmount }}
            </div>
          </div>
          <input
            v-model="itemSearch"
            class="form-control form-control-sm item-search"
            type="search"
            placeholder="搜索道具、分类或标签"
          >
        </div>

        <div class="item-bonus-panel">
          <span class="item-bonus-title">当前持有加成</span>
          <span
            v-if="bonusRows.length === 0"
            class="text-muted small"
          >暂无加成</span>
          <span
            v-for="bonus in bonusRows"
            :key="bonus.field"
            class="item-bonus-pill"
          >
            {{ bonus.label }} {{ formatSigned(bonus.delta) }}
          </span>
        </div>

        <div class="item-list">
          <div
            v-if="filteredItems.length === 0"
            class="text-center text-muted small py-4"
          >
            暂无匹配道具
          </div>

          <article
            v-for="item in filteredItems"
            :key="item.id"
            class="item-card"
            :class="{ owned: isItemOwned(item.id) }"
          >
            <div class="item-card-main">
              <div class="d-flex justify-content-between gap-2 align-items-start">
                <div>
                  <div class="item-name">
                    {{ item.name }}
                  </div>
                  <div class="item-category">
                    {{ item.category }}
                  </div>
                </div>
                <span
                  v-if="isItemOwned(item.id)"
                  class="item-owned-badge"
                >已拥有</span>
              </div>
              <p class="item-description">
                {{ item.description }}
              </p>
              <div class="item-tags">
                <span
                  v-for="tag in item.tags"
                  :key="tag"
                  class="item-tag"
                >{{ tag }}</span>
              </div>
              <div class="item-effects">
                <span
                  v-for="effect in itemEffectRows(item)"
                  :key="effect.field"
                  class="item-effect"
                >
                  {{ effect.label }} {{ formatSigned(effect.delta) }}
                </span>
              </div>
            </div>
            <div class="item-card-action">
              <div class="item-price">
                {{ isItemOwned(item.id) ? `回收 ${item.sell_price}` : `${item.price} 金币` }}
              </div>
              <button
                type="button"
                class="btn btn-sm item-action-btn"
                :class="isItemOwned(item.id) ? 'btn-outline-secondary' : 'btn-primary'"
                :disabled="itemActionDisabled(item)"
                :title="itemActionTitle(item)"
                @click="toggleItem(item)"
              >
                {{ isItemOwned(item.id) ? '出售' : '购买' }}
              </button>
            </div>
          </article>
        </div>
      </div>
    </div>

    <div class="card-footer mid-panel-footer border-top p-3 d-flex flex-column gap-2">
      <div class="btn-group w-100 speed-control">
        <button
          v-for="speed in [1.0, 1.5, 2.0]"
          :key="speed"
          class="btn btn-sm speed-btn"
          :class="{ active: store.gameSpeed === speed }"
          @click="setSpeed(speed)"
        >
          {{ speed }}x
        </button>
      </div>
      <small class="text-muted text-center mt-1 speed-label">游戏速度</small>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import { STAT_META_BY_ID } from '@/data/statDefinitions.generated'
import type { GameItem } from '@/types/items'
import type { DingTalkContact } from '@/types/modal'
import type { WsClientAction } from '@/types/websocket'

const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()

const store = useGameStore()
const activeTab = ref<string>('events')
const activeContactId = ref<string>('')
const dingScrollContainer = ref<HTMLDivElement | null>(null)
const itemSearch = ref('')

const sortedContacts = computed(() => (
  Object.values(store.dingtalkContacts)
    .sort((a, b) => Number(b.last_message_at || 0) - Number(a.last_message_at || 0))
))

const activeContact = computed(() => (
  activeContactId.value ? store.dingtalkContacts[activeContactId.value] : null
))

const goldAmount = computed(() => Math.floor(Number(store.currentStats.gold ?? 0) || 0))

const ownedItemIds = computed(() => new Set(store.ownedItems))

const bonusRows = computed(() => (
  Object.entries(store.itemBonuses)
    .filter(([, delta]) => Number.isFinite(Number(delta)) && Number(delta) !== 0)
    .map(([field, delta]) => ({
      field,
      label: STAT_META_BY_ID[field]?.label || field,
      delta: Number(delta),
    }))
))

const filteredItems = computed(() => {
  const query = itemSearch.value.trim().toLowerCase()
  const items = store.itemCatalog
  if (!query) return items
  return items.filter((item) => {
    const haystack = [
      item.name,
      item.category,
      item.description,
      ...item.tags,
    ].join(' ').toLowerCase()
    return haystack.includes(query)
  })
})

const roleAliases: Record<string, string> = {
  student: 'classmate',
  students: 'classmate',
  同学: 'classmate',
  同班同学: 'classmate',
  室友: 'roommate',
  舍友: 'roommate',
  roomie: 'roommate',
  ta: 'teaching_assistant',
  assistant: 'teaching_assistant',
  助教: 'teaching_assistant',
  老师: 'teacher',
  教师: 'teacher',
  朋友: 'friend',
  好友: 'friend',
  暗恋对象: 'crush',
}

const replyableRoles = new Set([
  'roommate',
  'classmate',
  'friend',
  'teaching_assistant',
  'teacher',
  'crush',
])

function normalizeRole(role: string): string {
  const normalized = String(role || 'unknown').trim().toLowerCase()
  return roleAliases[normalized] || normalized
}

const getRoleConfig = (role: string) => {
  const normalizedRole = normalizeRole(role)
  const configs: Record<string, { bg: string; icon: string; name: string }> = {
    counselor: { bg: '#a5753d', icon: '导', name: '辅导员' },
    teacher: { bg: '#3f719e', icon: '师', name: '老师' },
    teaching_assistant: { bg: '#315f8a', icon: '助', name: '助教' },
    classmate: { bg: '#477f8a', icon: '同', name: '同学' },
    roommate: { bg: '#626f95', icon: '寝', name: '室友' },
    friend: { bg: '#4f8378', icon: '友', name: '朋友' },
    crush: { bg: '#9b6475', icon: '心', name: 'crush' },
    system: { bg: '#778596', icon: '系', name: '系统通知' },
    volunteer_coordinator: { bg: '#7c6f95', icon: '志', name: '志愿活动' },
  }
  return configs[normalizedRole] || { bg: '#477f8a', icon: '生', name: '同学' }
}

function isContactReplyable(contact: DingTalkContact): boolean {
  return Boolean(contact.is_replyable) || replyableRoles.has(normalizeRole(contact.role))
}

function formatSigned(value: number): string {
  return `${value > 0 ? '+' : ''}${value}`
}

function itemEffectRows(item: GameItem) {
  return Object.entries(item.effects)
    .filter(([, delta]) => Number(delta) !== 0)
    .map(([field, delta]) => ({
      field,
      label: STAT_META_BY_ID[field]?.label || field,
      delta: Number(delta),
    }))
}

function isItemOwned(itemId: string): boolean {
  return ownedItemIds.value.has(itemId)
}

function itemActionDisabled(item: GameItem): boolean {
  if (store.isPaused) return true
  if (isItemOwned(item.id)) return false
  return goldAmount.value < item.price
}

function itemActionTitle(item: GameItem): string {
  if (store.isPaused) return '游戏暂停中，暂不能买卖道具'
  if (isItemOwned(item.id)) return `出售后回收 ${item.sell_price} 金币`
  if (goldAmount.value < item.price) return `金币不足，还差 ${item.price - goldAmount.value} 枚`
  return `购买 ${item.name}`
}

function toggleItem(item: GameItem) {
  if (itemActionDisabled(item)) return
  emit('send-action', {
    action: isItemOwned(item.id) ? 'item_sell' : 'item_buy',
    item_id: item.id,
  })
}

function contactPreview(contact: DingTalkContact): string {
  const last = contact.messages[contact.messages.length - 1]
  return last?.content || '暂无消息'
}

function formatTime(value: number): string {
  if (!value) return ''
  return new Date(value * 1000).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function markActiveRead() {
  const contact = activeContact.value
  if (!contact || contact.unread_count <= 0) return
  store.markDingContactReadLocal(contact.contact_id)
  emit('send-action', {
    action: 'dingtalk_mark_read',
    contact_id: contact.contact_id,
  })
}

function switchTab(tabName: string) {
  activeTab.value = tabName
  if (tabName === 'dingtalk') {
    markActiveRead()
    scrollToBottom()
  }
}

function selectContact(contactId: string) {
  activeContactId.value = contactId
  markActiveRead()
  scrollToBottom()
}

function sendReply(optionId: string) {
  const contact = activeContact.value
  if (!contact || store.isPaused) return
  emit('send-action', {
    action: 'dingtalk_reply',
    contact_id: contact.contact_id,
    option_id: optionId,
  })
}

async function scrollToBottom() {
  await nextTick()
  if (dingScrollContainer.value) {
    dingScrollContainer.value.scrollTop = dingScrollContainer.value.scrollHeight
  }
}

watch(sortedContacts, (contacts) => {
  if (!contacts.length) {
    activeContactId.value = ''
    return
  }
  if (!activeContactId.value || !store.dingtalkContacts[activeContactId.value]) {
    activeContactId.value = contacts[0].contact_id
  }
}, { immediate: true })

watch(() => activeContact.value?.messages.length, async () => {
  if (activeTab.value === 'dingtalk') {
    markActiveRead()
    await scrollToBottom()
  }
})

function setSpeed(speed: number) {
  store.gameSpeed = speed
  emit('send-action', { action: 'set_speed', speed })
}
</script>

<style scoped>
.event-log {
  font-family: 'Courier New', Courier, monospace;
  color: var(--console-text);
  background: var(--console-surface-gradient);
}

.event-log b {
  color: var(--console-primary);
}

.mid-panel-header {
  background: var(--console-surface-gradient) !important;
  border-bottom: 1px solid var(--console-border-strong);
}

.mid-panel-card {
  overflow: hidden;
}

.event-log-footer {
  background: var(--console-surface);
  border-color: var(--console-border-strong) !important;
}

.mid-panel-card .nav-tabs {
  gap: 6px;
  border-bottom: 0;
}

.mid-panel-card .nav-link {
  color: var(--console-muted);
  border: 1px solid transparent;
  border-radius: 6px 6px 0 0;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.mid-panel-card .nav-link:hover {
  color: var(--console-primary-dark);
  border-color: var(--console-primary-border);
  background: color-mix(in srgb, var(--console-surface) 58%, transparent);
}

.mid-panel-card .nav-link.active {
  color: var(--console-strong);
  font-weight: 700;
  background: var(--console-surface);
  border-color: var(--console-primary-border) var(--console-primary-border) var(--console-surface);
  box-shadow: 0 -1px 8px rgba(20, 43, 70, 0.06);
}

.ding-tab-unread,
.urgent-badge {
  background: #9f4d52;
}

.mid-panel-body {
  height: clamp(320px, 38vh, 450px);
  min-height: 0;
  overflow: hidden;
}

.dingtalk-shell {
  display: grid;
  grid-template-columns: minmax(116px, 34%) 1fr;
  background: var(--console-surface-alt);
  min-height: 0;
  overflow: hidden;
}

.ding-contact-list {
  min-height: 0;
  overflow-y: auto;
  background: var(--console-surface-gradient-strong);
  border-color: var(--console-border-strong) !important;
}

.ding-contact {
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--console-border-strong);
  background: transparent;
  display: grid;
  grid-template-columns: 34px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 9px 10px;
  text-align: left;
}

.ding-contact.active {
  background: var(--console-surface);
  box-shadow: inset 3px 0 0 var(--console-primary);
}

.ding-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: white;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.78rem;
  box-shadow: inset 0 -1px 0 rgba(0, 0, 0, 0.16);
}

.ding-contact-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.ding-contact-name {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--console-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ding-contact-preview {
  font-size: 0.72rem;
  color: var(--console-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ding-unread {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #9f4d52;
  color: white;
  font-size: 0.68rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ding-thread {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--console-surface-alt);
  overflow: hidden;
}

.ding-thread-header {
  min-height: 46px;
  padding: 7px 12px;
  background: var(--console-surface);
  border-color: var(--console-border-strong) !important;
}

.ding-thread-header .text-dark {
  color: var(--console-text) !important;
}

.ding-messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 10px 12px;
}

.ding-bubble-row {
  display: flex;
  margin-bottom: 8px;
}

.ding-bubble-row.from-player {
  justify-content: flex-end;
}

.ding-bubble {
  max-width: min(86%, 360px);
  border-radius: 8px;
  padding: 8px 10px 5px;
  font-size: 0.88rem;
  line-height: 1.45;
  box-shadow: 0 3px 10px color-mix(in srgb, var(--console-primary-dark) 8%, transparent);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.from-npc .ding-bubble {
  background: var(--console-surface);
  border: 1px solid var(--console-border-strong);
  border-top-left-radius: 2px;
}

.from-player .ding-bubble {
  color: var(--console-text);
  background: var(--console-thread-player-bg);
  border: 1px solid var(--console-thread-player-border);
  border-top-right-radius: 2px;
}

.ding-time {
  display: block;
  margin-top: 3px;
  font-size: 0.64rem;
  color: var(--console-muted);
  text-align: right;
}

.ding-replies {
  flex: 0 0 auto;
  min-height: 48px;
  display: flex;
  gap: 6px;
  padding: 7px;
  overflow-x: auto;
  background: var(--console-surface);
  border-color: var(--console-border-strong) !important;
}

.ding-replies .btn {
  white-space: nowrap;
}

.reply-paused-hint {
  align-self: center;
  white-space: nowrap;
}

.item-shell {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--console-surface-alt);
}

.item-toolbar {
  flex: 0 0 auto;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  background: var(--console-surface-gradient);
  border-bottom: 1px solid var(--console-border-strong);
}

.item-kicker {
  color: var(--console-primary);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.item-gold {
  color: var(--console-strong);
  font-size: 1.02rem;
  font-weight: 800;
}

.item-search {
  max-width: 220px;
  color: var(--console-text);
  background: var(--console-surface);
  border-color: var(--console-border-strong);
}

.item-bonus-panel {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  padding: 8px 12px;
  background: color-mix(in srgb, var(--console-surface) 72%, transparent);
  border-bottom: 1px solid var(--console-border-strong);
}

.item-bonus-title {
  color: var(--console-muted);
  font-size: 0.75rem;
  font-weight: 800;
}

.item-bonus-pill,
.item-effect,
.item-tag,
.item-owned-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  line-height: 1;
}

.item-bonus-pill,
.item-effect {
  padding: 4px 8px;
  color: var(--console-primary-dark);
  background: color-mix(in srgb, var(--console-primary) 12%, var(--console-surface));
  border: 1px solid var(--console-primary-border);
}

.item-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  gap: 10px;
  padding: 12px;
}

.item-card {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--console-border-strong);
  border-radius: 8px;
  background: var(--console-surface);
  box-shadow: 0 4px 14px color-mix(in srgb, var(--console-primary-dark) 7%, transparent);
}

.item-card.owned {
  border-color: var(--console-primary-border);
  background: color-mix(in srgb, var(--console-surface) 84%, var(--console-primary) 5%);
}

.item-card-main {
  min-width: 0;
}

.item-name {
  color: var(--console-strong);
  font-size: 0.95rem;
  font-weight: 800;
}

.item-category {
  color: var(--console-muted);
  font-size: 0.72rem;
  font-weight: 700;
}

.item-owned-badge {
  padding: 5px 8px;
  color: #fff;
  background: var(--console-primary-gradient);
}

.item-description {
  margin: 8px 0;
  color: var(--console-text);
  font-size: 0.82rem;
  line-height: 1.5;
}

.item-tags,
.item-effects {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.item-tags {
  margin-bottom: 7px;
}

.item-tag {
  padding: 4px 7px;
  color: var(--console-muted);
  background: var(--console-surface-alt);
  border: 1px solid var(--console-border);
}

.item-card-action {
  min-width: 92px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
}

.item-price {
  color: var(--console-gold-border);
  font-size: 0.78rem;
  font-weight: 800;
  white-space: nowrap;
}

.item-action-btn {
  min-width: 76px;
  font-weight: 800;
}

.mid-panel-footer {
  background: var(--console-surface-gradient);
  border-color: var(--console-border-strong) !important;
}

.speed-control {
  border-radius: 7px;
  box-shadow: inset 0 0 0 1px var(--console-border-strong);
  overflow: hidden;
}

.speed-btn {
  color: var(--console-primary);
  border-color: transparent;
  background: color-mix(in srgb, var(--console-surface) 62%, transparent);
  font-weight: 700;
}

.speed-btn.active {
  color: #fff;
  background: var(--console-primary-gradient);
}

.speed-label {
  color: var(--console-muted) !important;
  letter-spacing: 0.06em;
}

.pulse-animation {
  animation: pulse 1s ease-in-out;
}

@keyframes pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.3); }
  100% { transform: scale(1); }
}

@media (max-width: 430px) {
  .mid-panel-body {
    height: 300px;
  }

  .mid-panel-card .nav-link {
    padding: 0.45rem 0.52rem;
    font-size: 0.82rem;
    white-space: nowrap;
  }

  .dingtalk-shell {
    grid-template-columns: 1fr;
    grid-template-rows: 92px 1fr;
  }

  .ding-contact-list {
    display: flex;
    overflow-x: auto;
    overflow-y: hidden;
    border-right: 0 !important;
    border-bottom: 1px solid var(--console-border-strong);
  }

  .ding-contact {
    min-width: 136px;
    border-bottom: 0;
    border-right: 1px solid var(--console-border-strong);
  }

  .ding-contact.active {
    box-shadow: inset 0 -3px 0 var(--console-primary);
  }

  .item-toolbar {
    flex-direction: column;
    gap: 8px;
  }

  .item-search {
    max-width: none;
  }

  .item-card {
    grid-template-columns: 1fr;
  }

  .item-card-action {
    align-items: stretch;
  }
}
</style>
