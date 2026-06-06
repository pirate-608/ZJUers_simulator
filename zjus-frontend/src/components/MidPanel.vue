<template>
  <div
    id="tour-mid-panel"
    class="card mid-panel-card mb-3 d-flex flex-column h-100 shadow-sm border-0"
  >
    <div class="card-header pb-0 bg-white border-bottom mid-panel-header">
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
              class="badge bg-danger rounded-pill pulse-animation"
            >
              {{ store.unreadDingtalk }}
            </span>
          </button>
        </li>
      </ul>
    </div>

    <div
      class="card-body p-0 position-relative"
      style="height: 280px;"
    >
      <div
        v-if="activeTab === 'events'"
        class="h-100 d-flex flex-column"
      >
        <div
          class="event-log flex-grow-1 overflow-auto border-0 p-3"
          style="background: #f8f9fa;"
        >
          <div
            v-if="store.eventLogs.length === 0"
            class="text-muted"
          >
            连接到折大服务器中...
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
        <div class="text-end border-top py-1 px-2 bg-white">
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
                    class="badge bg-danger ms-1"
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

            <div class="ding-replies border-top bg-white">
              <template v-if="activeContact.pending_options.length > 0">
                <button
                  v-for="option in activeContact.pending_options"
                  :key="option.option_id"
                  type="button"
                  class="btn btn-outline-primary btn-sm text-start"
                  @click="sendReply(option.option_id)"
                >
                  {{ option.text }}
                </button>
              </template>
              <div
                v-else
                class="text-muted small text-center py-2"
              >
                {{ activeContact.is_replyable ? '等待对方的新消息' : '该联系人暂不支持回复' }}
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <div class="card-footer bg-white border-top p-3 d-flex flex-column gap-2">
      <div class="btn-group w-100">
        <button
          v-for="speed in [1.0, 1.5, 2.0]"
          :key="speed"
          class="btn btn-sm"
          :class="store.gameSpeed === speed ? 'btn-secondary text-white' : 'btn-outline-secondary'"
          @click="setSpeed(speed)"
        >
          {{ speed }}x
        </button>
      </div>
      <small class="text-muted text-center mt-1">⚡ 游戏速度</small>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { DingTalkContact } from '@/types/modal'
import type { WsClientAction } from '@/types/websocket'

const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()

const store = useGameStore()
const activeTab = ref<string>('events')
const activeContactId = ref<string>('')
const dingScrollContainer = ref<HTMLDivElement | null>(null)

const sortedContacts = computed(() => (
  Object.values(store.dingtalkContacts)
    .sort((a, b) => Number(b.last_message_at || 0) - Number(a.last_message_at || 0))
))

const activeContact = computed(() => (
  activeContactId.value ? store.dingtalkContacts[activeContactId.value] : null
))

const getRoleConfig = (role: string) => {
  const configs: Record<string, { bg: string; icon: string; name: string }> = {
    counselor: { bg: '#FF9F43', icon: '导', name: '辅导员' },
    teacher: { bg: '#54a0ff', icon: '师', name: '老师' },
    teaching_assistant: { bg: '#2e86de', icon: '助', name: '助教' },
    classmate: { bg: '#1dd1a1', icon: '同', name: '同学' },
    roommate: { bg: '#5f27cd', icon: '寝', name: '室友' },
    friend: { bg: '#10ac84', icon: '友', name: '朋友' },
    crush: { bg: '#ff6b81', icon: '心', name: 'crush' },
    system: { bg: '#8395a7', icon: '系', name: '系统通知' },
    volunteer_coordinator: { bg: '#f368e0', icon: '志', name: '志愿活动' },
  }
  return configs[role] || { bg: '#1dd1a1', icon: '生', name: '同学' }
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
  if (!contact) return
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
}

.mid-panel-header {
  background: linear-gradient(180deg, #fbf9f1 0%, #f4f0e2 100%) !important;
}

.mid-panel-card .nav-link.active {
  color: #1f4368;
  font-weight: 700;
  border-color: #d9d2c2 #d9d2c2 #ffffff;
}

.dingtalk-shell {
  display: grid;
  grid-template-columns: minmax(116px, 34%) 1fr;
  background: #f7faff;
}

.ding-contact-list {
  overflow-y: auto;
  background: #f5f8fc;
}

.ding-contact {
  width: 100%;
  border: 0;
  border-bottom: 1px solid #e7edf5;
  background: transparent;
  display: grid;
  grid-template-columns: 34px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 9px 10px;
  text-align: left;
}

.ding-contact.active {
  background: #ffffff;
  box-shadow: inset 3px 0 0 #2e86de;
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
}

.ding-contact-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.ding-contact-name {
  font-size: 0.82rem;
  font-weight: 700;
  color: #26384d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ding-contact-preview {
  font-size: 0.72rem;
  color: #7b8794;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ding-unread {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #dc3545;
  color: white;
  font-size: 0.68rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ding-thread {
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #eef5ff;
}

.ding-thread-header {
  min-height: 46px;
  padding: 7px 12px;
  background: #ffffff;
}

.ding-messages {
  flex: 1 1 auto;
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
  box-shadow: 0 1px 4px rgba(31, 67, 104, 0.08);
}

.from-npc .ding-bubble {
  background: #ffffff;
  border: 1px solid #e4eaf2;
  border-top-left-radius: 2px;
}

.from-player .ding-bubble {
  background: #d9f7be;
  border: 1px solid #b7eb8f;
  border-top-right-radius: 2px;
}

.ding-time {
  display: block;
  margin-top: 3px;
  font-size: 0.64rem;
  color: #8c97a5;
  text-align: right;
}

.ding-replies {
  min-height: 48px;
  display: flex;
  gap: 6px;
  padding: 7px;
  overflow-x: auto;
}

.ding-replies .btn {
  white-space: nowrap;
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
  .card-body[style] {
    height: 300px !important;
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
    border-bottom: 1px solid #dbe4ef;
  }

  .ding-contact {
    min-width: 136px;
    border-bottom: 0;
    border-right: 1px solid #e7edf5;
  }

  .ding-contact.active {
    box-shadow: inset 0 -3px 0 #2e86de;
  }
}
</style>
