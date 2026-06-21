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
        <div class="feedback-message">
          {{ store.feedbackModal.message }}
        </div>
        <div
          v-if="changes.length"
          class="feedback-changes"
        >
          <div class="feedback-changes-title">
            本次变化
          </div>
          <div class="feedback-change-list">
            <div
              v-for="change in changes"
              :key="change.field"
              class="feedback-change-row"
            >
              <span class="feedback-change-label">{{ change.label }}</span>
              <span
                class="feedback-change-delta"
                :class="deltaClass(change)"
              >
                {{ formatDelta(change) }}
              </span>
              <span
                v-if="change.value !== undefined"
                class="feedback-change-value"
              >
                当前 {{ formatValue(change.value, change.unit) }}
              </span>
            </div>
          </div>
        </div>
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
/**
 * Generic result feedback modal with optional stat-delta rows.
 */
import { computed } from 'vue'
import { useGameStore } from '../../stores/gameStore.ts'
import type { FeedbackChange } from '@/types/modal'

const store = useGameStore()

const changes = computed<FeedbackChange[]>(() => {
  const value = store.feedbackModal?.changes
  return Array.isArray(value) ? value : []
})

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function formatDelta(change: FeedbackChange) {
  const prefix = change.delta > 0 ? '+' : ''
  return `${prefix}${formatNumber(change.delta)}${change.unit ?? ''}`
}

function formatValue(value: FeedbackChange['value'], unit?: string) {
  if (typeof value === 'number') {
    return `${formatNumber(value)}${unit ?? ''}`
  }
  return `${value}${unit ?? ''}`
}

function deltaClass(change: FeedbackChange) {
  const delta = change.delta
  if (delta === 0) return 'is-neutral'
  const positiveImpact = change.field === 'stress' ? delta < 0 : delta > 0
  if (positiveImpact) return 'is-positive'
  return 'is-negative'
}
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
}

.feedback-message {
  white-space: pre-wrap;
}

.feedback-changes {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid rgba(63, 82, 105, 0.14);
  border-radius: 8px;
  background: rgba(237, 244, 250, 0.76);
}

.feedback-changes-title {
  margin-bottom: 8px;
  color: #516172;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.feedback-change-list {
  display: grid;
  gap: 6px;
}

.feedback-change-row {
  display: grid;
  grid-template-columns: minmax(72px, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  font-size: 0.92rem;
}

.feedback-change-label {
  font-weight: 700;
  color: #26384a;
}

.feedback-change-delta {
  min-width: 54px;
  padding: 2px 8px;
  border-radius: 999px;
  text-align: center;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  background: rgba(90, 105, 125, 0.1);
  color: #5a697d;
}

.feedback-change-delta.is-positive {
  background: rgba(34, 143, 104, 0.12);
  color: #187250;
}

.feedback-change-delta.is-negative {
  background: rgba(184, 72, 80, 0.12);
  color: #a0333c;
}

.feedback-change-value {
  color: #6c7887;
  font-size: 0.86rem;
  white-space: nowrap;
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

@media (max-width: 430px) {
  .feedback-change-row {
    grid-template-columns: minmax(68px, 1fr) auto;
  }

  .feedback-change-value {
    grid-column: 1 / -1;
  }
}
</style>
