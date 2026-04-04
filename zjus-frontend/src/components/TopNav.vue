<template>
  <div class="top-nav d-flex justify-content-between align-items-end mb-3">
    <div>
      <h3
        class="mb-0 fw-bold text-primary title"
        style="letter-spacing: 1px;"
      >
        🎓 ZJUers Simulator
      </h3>
      <div class="small text-muted fw-bold top-nav-meta">
        {{ store.currentStats.username || '折大人' }} · {{ store.currentStats.major || '??' }} · {{ store.currentStats.semester || '??' }}
      </div>
    </div>
    
    <div class="d-flex gap-2 top-nav-actions">
      <button
        class="btn btn-sm fw-bold shadow-sm"
        :class="store.isPaused ? 'btn-success' : 'btn-warning'"
        @click="togglePause"
      >
        {{ store.isPaused ? '▶️ 继续' : '⏸️ 暂停' }}
      </button>
      
      <a
        href="https://zjusim-docs.67656.fun/user/rules/"
        target="_blank"
        class="btn btn-sm btn-outline-info fw-bold shadow-sm"
      >
        📖 游戏规则
      </a>
      
      <button
        class="btn btn-sm btn-outline-success fw-bold shadow-sm"
        @click="saveGame"
      >
        💾 快速保存
      </button>
      
      <button
        class="btn btn-sm btn-outline-danger fw-bold shadow-sm"
        @click="requestExit"
      >
        🚪 退出游戏
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
.title {
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
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