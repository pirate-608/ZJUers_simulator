<template>
  <div
    v-if="store.activeModal === 'exam_confirm'"
    class="modal-backdrop-custom d-flex justify-content-center align-items-center fade-in"
  >
    <div class="card confirm-card shadow-lg border-0 scale-in">
      <div class="card-header text-white py-3 text-center">
        <h5 class="mb-0 fw-bold">
          确认参加期末考
        </h5>
      </div>

      <div class="card-body p-4">
        <p class="mb-2 fw-bold text-dark">
          现在参加期末考会立即结算本学期成绩。
        </p>
        <p class="mb-0 text-muted small">
          如果只是等待倒计时归零，系统会自动结算；主动提前考试需要你再次确认。
        </p>
      </div>

      <div class="card-footer bg-white border-0 py-3 d-flex justify-content-end gap-2">
        <button
          type="button"
          class="btn btn-outline-secondary px-3"
          @click="store.closeModal()"
        >
          再等等
        </button>
        <button
          type="button"
          class="btn confirm-btn fw-bold px-4"
          @click="confirmExam"
        >
          确认考试
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useGameStore } from '../../stores/gameStore.ts'
import type { WsClientAction } from '@/types/websocket'

const store = useGameStore()
const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()

const confirmExam = () => {
  store.closeModal()
  emit('send-action', { action: 'exam' })
}
</script>

<style scoped>
.modal-backdrop-custom {
  position: fixed;
  inset: 0;
  padding: 14px;
  background: rgba(8, 19, 32, 0.56);
  z-index: 9999;
  backdrop-filter: blur(3px);
}

.confirm-card {
  width: min(92vw, 440px);
  border: 1px solid rgba(89, 113, 139, 0.22) !important;
  border-radius: 8px;
  overflow: hidden;
  background: #fbfdff;
}

.card-header {
  background: linear-gradient(180deg, #18395d 0%, #244f7b 100%);
}

.confirm-btn {
  color: #fff;
  border-color: #824047;
  background: linear-gradient(180deg, #a7565b 0%, #824047 100%);
}

.confirm-btn:hover {
  color: #fff;
  border-color: #70383f;
  background: linear-gradient(180deg, #944c52 0%, #723941 100%);
}

.fade-in {
  animation: fadeIn 0.18s ease-out;
}

.scale-in {
  animation: scaleIn 0.2s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes scaleIn {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>
