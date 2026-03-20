<template>
  <div
    v-if="store.activeModal === 'random_event'"
    class="modal-backdrop-custom d-flex justify-content-center align-items-center fade-in"
  >
    <div
      class="card shadow border-0 modal-card scale-in"
      style="width: 90%; max-width: 500px;"
    >
      <div class="card-header text-white py-3 bg-primary">
        <h5 class="mb-0 fw-bold">
          🌟 突发事件：{{ data.title }}
        </h5>
      </div>
      <div class="card-body p-4">
        <p
          class="fs-6 mb-4"
          style="line-height: 1.6; white-space: pre-wrap;"
        >
          {{ data.desc }}
        </p>
        
        <div
          v-if="data.options && data.options.length > 0"
          class="d-grid gap-3"
        >
          <button
            v-for="(opt, idx) in data.options"
            :key="idx" 
            class="btn btn-outline-primary text-start p-3"
            @click="makeChoice(opt.effects)"
          >
            <strong>选项 {{ idx + 1 }}:</strong> {{ opt.text }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useGameStore } from '../../stores/gameStore.ts'

const store = useGameStore()
const emit = defineEmits(['send-action'])
const data = computed(() => store.modalData)

const makeChoice = (effects) => {
  store.closeModal()
  // 完全对齐旧版逻辑和后端的 _handle_event_choice 需求
  emit('send-action', { action: 'event_choice', effects: effects })
  
  if (store.isPaused) {
    emit('send-action', { action: 'resume' })
  }
}
</script>

<style scoped>
.modal-backdrop-custom {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  background-color: rgba(0, 0, 0, 0.6); z-index: 9999; backdrop-filter: blur(2px);
}
.fade-in { animation: fadeIn 0.2s ease-out; }
.scale-in { animation: scaleIn 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes scaleIn { from { transform: scale(0.9); opacity: 0; } to { transform: scale(1); opacity: 1; } }
</style>