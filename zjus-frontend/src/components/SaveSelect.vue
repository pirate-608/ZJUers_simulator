<template>
  <div class="save-select-root min-vh-100 d-flex align-items-center justify-content-center px-3 py-4">
    <div class="save-panel w-100">
      <div class="text-center mb-4">
        <h2 class="fw-bold mb-2">选择游玩方式</h2>
        <p class="text-muted mb-0">加载已有存档，或重新创建角色开始新游戏。</p>
      </div>

      <div v-if="saves.length" class="mb-4">
        <h5 class="fw-bold mb-3">已有存档</h5>
        <div class="save-list d-grid gap-3">
          <button
            v-for="save in saves"
            :key="save.save_slot"
            type="button"
            class="save-card text-start border-0 shadow-sm p-3"
            @click="loadSave(save.save_slot)"
          >
            <div class="d-flex justify-content-between align-items-start gap-3">
              <div>
                <div class="fw-bold fs-5">{{ save.major }}</div>
                <div class="text-muted small">{{ save.semester }} · GPA {{ save.gpa }}</div>
              </div>
              <span class="badge bg-primary-subtle text-primary">Slot {{ save.save_slot }}</span>
            </div>
            <div class="text-muted small mt-3">
              最近保存：{{ formatSavedAt(save.saved_at) }}
            </div>
          </button>
        </div>
      </div>

      <div v-else class="empty-state text-center text-muted mb-4 p-4">
        还没有可加载的存档。
      </div>

      <button type="button" class="btn btn-outline-primary btn-lg w-100 fw-bold" @click="startNewGame">
        开始新游戏
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { SaveSummary } from '@/api/client'

const store = useGameStore()

const saves = computed<SaveSummary[]>(() => {
  const raw = localStorage.getItem('zju_saves')
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed as SaveSummary[] : []
  } catch {
    return []
  }
})

function formatSavedAt(value?: string | null): string {
  if (!value) return '未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function loadSave(slot: number) {
  if (!Number.isInteger(slot) || slot <= 0) {
    store.showToast('存档槽位无效，请重新登录刷新列表', 'warning')
    return
  }
  localStorage.setItem('selected_save_slot', String(slot))
  localStorage.setItem('game_started', '1')
  store.setPhase('loading')
}

function startNewGame() {
  localStorage.removeItem('selected_save_slot')
  localStorage.removeItem('zju_saves')
  localStorage.removeItem('game_started')
  store.setPhase('character_create')
}
</script>

<style scoped>
.save-select-root {
  background: linear-gradient(160deg, #f8fbff 0%, #edf3f9 100%);
}

.save-panel {
  max-width: 760px;
}

.save-card {
  width: 100%;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  transition: transform 0.16s ease, box-shadow 0.16s ease;
}

.save-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 0.5rem 1.25rem rgba(47, 93, 136, 0.14) !important;
}

.empty-state {
  border: 1px dashed rgba(47, 93, 136, 0.35);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
}
</style>
