<template>
  <div class="card mb-3 d-flex flex-column h-100 shadow-sm border-0">
    <div class="card-header pb-0 bg-white border-bottom">
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
        class="h-100 d-flex flex-column"
        style="background: #f7faff;"
      >
        <div
          ref="dingScrollContainer"
          class="p-3 flex-grow-1 overflow-auto"
        >
          <div
            v-if="store.dingMessages.length === 0"
            class="text-center text-muted small mt-4"
          >
            <p>暂无新消息</p>
            <p>班级群通知、辅导员私信将在这里显示</p>
          </div>
          
          <div
            v-for="(msg, index) in store.dingMessages"
            :key="index"
            class="d-flex align-items-start mb-3 ding-msg-anim"
          >
            <div class="flex-shrink-0">
              <div
                class="rounded-circle d-flex align-items-center justify-content-center text-white fw-bold shadow-sm" 
                :style="{ width: '36px', height: '36px', backgroundColor: getRoleConfig(msg.role).bg, fontSize: '0.85rem' }"
              >
                {{ getRoleConfig(msg.role).icon }}
              </div>
            </div>
            <div class="flex-grow-1 ms-2">
              <div class="d-flex align-items-center mb-1">
                <span
                  class="fw-bold text-dark"
                  style="font-size: 0.85rem;"
                >{{ msg.sender || getRoleConfig(msg.role).name }}</span>
                <span
                  class="text-muted ms-2"
                  style="font-size: 0.7rem;"
                >刚刚</span>
                <span
                  v-if="msg.is_urgent"
                  class="badge bg-danger ms-2"
                  style="font-size:0.6rem"
                >紧急</span>
              </div>
              <div
                class="p-2 rounded shadow-sm position-relative" 
                :style="msg.is_urgent ? 'border: 1px solid #ff6b6b; background: #fff0f0;' : 'background: white; border: 1px solid #eee;'" 
                style="border-radius: 0 8px 8px 8px;"
              >
                <p
                  class="mb-0 text-dark"
                  style="font-size: 0.9rem; line-height: 1.4;"
                >
                  {{ msg.content }}
                </p>
              </div>
            </div>
          </div>
        </div>
        <div class="p-2 border-top bg-white">
          <form
            class="d-flex gap-2"
            @submit.prevent
          >
            <input
              type="text"
              class="form-control form-control-sm"
              placeholder="回复消息... (功能开发中)"
              disabled
            >
            <button
              class="btn btn-primary btn-sm"
              disabled
            >
              发送
            </button>
          </form>
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
import { ref, watch, nextTick } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { WsClientAction } from '@/types/websocket'

// 定义向外发送的事件（替代原本直接调用 wsManager.send）
const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()

const store = useGameStore()
const activeTab = ref<string>('events')
const dingScrollContainer = ref<HTMLDivElement | null>(null)

// 角色配置抽取（替代 dingTalkManager 中的硬编码逻辑）
const getRoleConfig = (role: string) => {
  const configs: Record<string, { bg: string; icon: string; name: string }> = {
    "counselor": { bg: "#FF9F43", icon: "导", name: "辅导员" },
    "teacher": { bg: "#54a0ff", icon: "师", name: "老师" },
    "student": { bg: "#1dd1a1", icon: "生", name: "同学" },
    "system": { bg: "#8395a7", icon: "系", name: "系统通知" }
  }
  return configs[role] || configs["student"]
}

// 切换 Tab 的逻辑
const switchTab = (tabName: string) => {
  activeTab.value = tabName
  if (tabName === 'dingtalk') {
    store.clearUnreadDingtalk() // 切过去时自动清空红点
    scrollToBottom()
  }
}

// 监听钉钉消息变化：如果当前在看钉钉，自动滚动到底部并清空未读；如果不在，红点由 Store 自己累加
watch(() => store.dingMessages.length, async () => {
  if (activeTab.value === 'dingtalk') {
    store.clearUnreadDingtalk()
    await scrollToBottom()
  }
})

// 优雅的自动滚动逻辑
const scrollToBottom = async () => {
  await nextTick() // 等待 Vue 将新的 DOM 节点渲染完毕
  if (dingScrollContainer.value) {
    dingScrollContainer.value.scrollTop = dingScrollContainer.value.scrollHeight
  }
}

// 控制面板动作

const setSpeed = (speed: number) => {
  store.gameSpeed = speed
  // ✅ 恢复发送给后端，现在后端能听懂了！
  emit('send-action', { action: 'set_speed', speed: speed })
}
</script>

<style scoped>
/* 局部样式，直接把原 dashboard.html 里的粘过来，但加上 scoped 保证不污染全局 */
.event-log {
  font-family: 'Courier New', Courier, monospace;
}
.ding-msg-anim {
  animation: slideIn 0.3s ease-out forwards;
}
@keyframes slideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.pulse-animation {
  animation: pulse 1s ease-in-out;
}
@keyframes pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.3); }
  100% { transform: scale(1); }
}
</style>