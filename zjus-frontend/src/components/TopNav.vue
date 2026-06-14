<template>
  <div class="top-nav d-flex justify-content-between align-items-end mb-3">
    <div id="tour-game-header">
      <h3
        class="mb-0 fw-bold title"
      >
        ZJUers Simulator
      </h3>
      <div class="small text-muted fw-bold top-nav-meta">
        {{ store.currentStats.username || '折大人' }} · {{ store.currentStats.major || '??' }} · {{ store.currentStats.semester || '??' }}
      </div>
    </div>

    <div class="d-flex gap-2 top-nav-actions">
      <button
        id="tour-pause-btn"
        class="btn btn-sm fw-bold top-action"
        :class="store.isPaused ? 'top-action-primary' : 'top-action-gold'"
        @click="togglePause"
      >
        {{ store.isPaused ? '继续' : '暂停' }}
      </button>

      <a
        href="https://zjusim-docs.67656.fun/user/rules/"
        target="_blank"
        class="btn btn-sm fw-bold top-action top-action-outline"
      >
        游戏规则
      </a>

      <button
        id="tour-save-btn"
        class="btn btn-sm fw-bold top-action top-action-outline"
        @click="saveGame"
      >
        快速保存
      </button>
      
      <button
        class="btn btn-sm fw-bold top-action top-action-danger"
        @click="requestExit"
      >
        退出游戏
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useGameStore } from '../stores/gameStore.ts'
import type { WsClientAction } from '@/types/websocket'

const store = useGameStore()
const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()

const saveGame = () => {
  emit('send-action', { action: 'save_game' })
}

const requestExit = () => {
  // 触发弹窗，而不是直接发送指令
  store.showModal('exit_confirm')
}

const togglePause = () => {
  emit('send-action', { action: store.isPaused ? 'resume' : 'pause' })
}
</script>

<style scoped>
.top-nav {
  padding: 12px 14px;
  border: 1px solid rgba(89, 113, 139, 0.22);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(251, 253, 255, 0.96) 0%, rgba(238, 245, 251, 0.96) 100%);
  box-shadow: 0 14px 36px rgba(18, 44, 73, 0.1);
}

.title {
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
  color: #143657;
  letter-spacing: 0.04em;
}

.top-nav-meta {
  color: #637588 !important;
}

.top-action {
  min-width: 76px;
  color: #2d567d;
  border: 1px solid #b9c8d8;
  background: rgba(248, 251, 255, 0.84);
  border-radius: 6px;
}

.top-action:hover {
  color: #fff;
  border-color: #2f5f8c;
  background: linear-gradient(180deg, #356894 0%, #244d76 100%);
}

.top-action-primary {
  color: #fff;
  border-color: #21486e;
  background: linear-gradient(180deg, #356894 0%, #244d76 100%);
}

.top-action-gold {
  color: #25384c;
  border-color: #b88a44;
  background: linear-gradient(180deg, #d7bd7b 0%, #b88a44 100%);
}

.top-action-danger {
  color: #824047;
  border-color: #caa3a6;
}

.top-action-danger:hover {
  color: #fff;
  border-color: #824047;
  background: linear-gradient(180deg, #a7565b 0%, #824047 100%);
}

@media (max-width: 430px) {
  .top-nav {
    align-items: stretch !important;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 10px !important;
  }

  .top-nav-meta {
    font-size: 0.78rem;
    margin-top: 4px;
  }

  .top-nav-actions {
    width: 100%;
    display: grid !important;
    grid-template-columns: 1fr 1fr;
    gap: 6px !important;
  }

  .top-nav-actions .btn {
    font-size: 0.76rem;
    padding: 0.36rem 0.45rem;
    white-space: nowrap;
  }
}
</style>
