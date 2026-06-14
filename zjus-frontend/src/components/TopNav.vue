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
      <div
        class="theme-switch"
        role="group"
        aria-label="控制台主题"
      >
        <button
          v-for="theme in consoleThemes"
          :key="theme.id"
          type="button"
          class="theme-switch-btn"
          :class="{ active: store.consoleTheme === theme.id }"
          :title="`切换为${theme.label}主题`"
          @click="store.setConsoleTheme(theme.id)"
        >
          {{ theme.label }}
        </button>
      </div>

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
import { useGameStore, type ConsoleTheme } from '../stores/gameStore.ts'
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

const consoleThemes: Array<{ id: ConsoleTheme; label: string }> = [
  { id: 'lantian', label: '蓝田' },
  { id: 'yunfeng', label: '云峰' },
  { id: 'danqing', label: '丹青' },
]
</script>

<style scoped>
.top-nav {
  padding: 12px 14px;
  border: 1px solid var(--console-border);
  border-radius: 8px;
  background: var(--console-surface-gradient);
  box-shadow: var(--console-card-shadow);
}

.top-nav-actions {
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.title {
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
  color: var(--console-strong);
  letter-spacing: 0.04em;
}

.top-nav-meta {
  color: var(--console-muted) !important;
}

.theme-switch {
  display: inline-flex;
  align-items: center;
  padding: 2px;
  border: 1px solid var(--console-primary-border);
  border-radius: 999px;
  background: color-mix(in srgb, var(--console-surface-soft) 86%, transparent);
  box-shadow: inset 0 1px 2px rgba(20, 43, 70, 0.06);
}

.theme-switch-btn {
  min-width: 42px;
  border: 0;
  border-radius: 999px;
  color: var(--console-muted);
  background: transparent;
  font-size: 0.74rem;
  font-weight: 800;
  line-height: 1;
  padding: 0.38rem 0.48rem;
  transition: color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
}

.theme-switch-btn:hover {
  color: var(--console-primary-dark);
}

.theme-switch-btn.active {
  color: #fff;
  background: var(--console-primary-gradient);
  box-shadow: 0 2px 8px color-mix(in srgb, var(--console-primary-dark) 24%, transparent);
}

.top-action {
  min-width: 76px;
  color: var(--console-primary);
  border: 1px solid var(--console-primary-border);
  background: color-mix(in srgb, var(--console-surface-soft) 84%, transparent);
  border-radius: 6px;
}

.top-action:hover {
  color: #fff;
  border-color: var(--console-primary);
  background: var(--console-primary-gradient);
}

.top-action-primary {
  color: #fff;
  border-color: var(--console-primary-dark);
  background: var(--console-primary-gradient);
}

.top-action-gold {
  color: var(--console-gold-text);
  border-color: var(--console-gold-border);
  background: var(--console-warn-gradient);
}

.top-action-danger {
  color: var(--console-danger-dark);
  border-color: var(--console-danger-border);
}

.top-action-danger:hover {
  color: #fff;
  border-color: var(--console-danger-dark);
  background: var(--console-danger-gradient);
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

  .theme-switch {
    grid-column: 1 / -1;
    width: 100%;
    justify-content: stretch;
  }

  .theme-switch-btn {
    flex: 1;
  }

  .top-nav-actions .btn {
    font-size: 0.76rem;
    padding: 0.36rem 0.45rem;
    white-space: nowrap;
  }
}
</style>
