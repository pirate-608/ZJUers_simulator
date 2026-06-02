<template>
  <div
    v-if="store.feedbackModal"
    class="feedback-backdrop d-flex justify-content-center align-items-center"
    @click.self="store.closeFeedback()"
  >
    <div class="feedback-card shadow-lg">
      <div class="feedback-header d-flex justify-content-between align-items-center">
        <div class="fw-bold">
          {{ store.feedbackModal.title }}
        </div>
        <button
          type="button"
          class="btn-close"
          aria-label="关闭"
          @click="store.closeFeedback()"
        />
      </div>
      <div class="feedback-body">
        {{ store.feedbackModal.message }}
      </div>
      <div class="feedback-footer text-end">
        <button
          type="button"
          class="btn btn-sm btn-primary px-3"
          @click="store.closeFeedback()"
        >
          知道了
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useGameStore } from '../../stores/gameStore.ts'

const store = useGameStore()
</script>

<style scoped>
.feedback-backdrop {
  position: fixed;
  inset: 0;
  z-index: 10020;
  padding: 16px;
  background: rgba(20, 24, 33, 0.34);
  backdrop-filter: blur(2px);
  animation: fadeIn 0.16s ease-out;
}

.feedback-card {
  width: min(460px, 100%);
  overflow: hidden;
  border: 1px solid rgba(63, 82, 105, 0.2);
  border-radius: 8px;
  background: #fffdf8;
  animation: riseIn 0.18s ease-out;
}

.feedback-header {
  padding: 12px 14px;
  color: #1f3041;
  background: #edf4fa;
  border-bottom: 1px solid rgba(63, 82, 105, 0.16);
}

.feedback-body {
  padding: 18px 16px;
  color: #2d3137;
  font-size: 0.98rem;
  line-height: 1.65;
  white-space: pre-wrap;
}

.feedback-footer {
  padding: 0 16px 14px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes riseIn {
  from { transform: translateY(8px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
</style>
