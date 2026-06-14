<template>
  <div
    id="hud-bars"
    class="hud-container d-flex justify-content-between align-items-center p-3 mb-3"
  >
    <div class="d-flex gap-4 flex-grow-1 me-4">
      <div class="stat-item flex-grow-1">
        <div class="d-flex justify-content-between small mb-1 fw-bold stat-row">
          <span class="stat-label">精力</span>
          <span>{{ Math.floor(safeNumber(stats.energy, 100)) }} / 100</span>
        </div>
        <div
          class="progress"
        >
          <div
            class="progress-bar stat-bar-energy"
            :style="{ width: `${Math.min(100, Math.max(0, safeNumber(stats.energy, 100)))}%` }"
          />
        </div>
      </div>

      <div class="stat-item flex-grow-1">
        <div class="d-flex justify-content-between small mb-1 fw-bold stat-row">
          <span class="stat-label">心态</span>
          <span>{{ Math.floor(safeNumber(stats.sanity, 100)) }} / 100</span>
        </div>
        <div
          class="progress"
        >
          <div
            class="progress-bar"
            :class="sanityColorClass"
            :style="{ width: `${Math.min(100, Math.max(0, safeNumber(stats.sanity, 100)))}%` }"
          />
        </div>
      </div>

      <div class="stat-item flex-grow-1">
        <div class="d-flex justify-content-between small mb-1 fw-bold stat-row">
          <span class="stat-label">压力</span>
          <span>{{ Math.floor(safeNumber(stats.stress, 0)) }} / 100</span>
        </div>
        <div
          class="progress"
        >
          <div
            class="progress-bar"
            :class="stressColorClass"
            :style="{ width: `${Math.min(100, Math.max(0, safeNumber(stats.stress, 0)))}%` }"
          />
        </div>
      </div>
    </div>

    <div class="d-flex gap-4 border-start ps-4 hud-metrics">
      <div class="text-center hud-metric-block">
        <div class="small text-muted fw-bold metric-label">
          IQ / EQ
        </div>
        <div class="fw-bold fs-5 metric-value">
          {{ Math.floor(safeNumber(stats.iq, 100)) }} <span class="text-muted fs-6">/</span> {{ Math.floor(safeNumber(stats.eq, 100)) }}
        </div>
      </div>
      
      <div class="text-center hud-metric-block">
        <div class="small text-muted fw-bold metric-label">
          GPA
        </div>
        <div
          class="fw-bold fs-5 metric-value"
          :class="gpaColorClass"
        >
          <!-- 🌟 核心防御：保证 gpa 绝对是数字，再执行 toFixed -->
          {{ safeNumber(stats.gpa, 0).toFixed(2) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'

const store = useGameStore()
const stats = computed(() => store.currentStats)

// 🌟 安全转换函数，防止 undefined / null / string 导致页面崩溃
const safeNumber = (val: unknown, defaultVal: number = 0): number => {
  if (val === null || val === undefined) return defaultVal
  const num = Number(val)
  return isNaN(num) ? defaultVal : num
}

const sanityColorClass = computed(() => {
  const sanity = safeNumber(stats.value.sanity, 100)
  if (sanity > 70) return 'stat-bar-good'
  if (sanity > 30) return 'stat-bar-normal'
  return 'stat-bar-alert'
})

const gpaColorClass = computed(() => {
  const gpa = safeNumber(stats.value.gpa, 0)
  if (gpa >= 4.0) return 'metric-excellent'
  if (gpa >= 3.0) return 'metric-good'
  if (gpa >= 2.0) return 'metric-warn'
  return 'metric-alert'
})

const stressColorClass = computed(() => {
  const stress = safeNumber(stats.value.stress, 0)
  if (stress > 70) return 'stat-bar-alert'
  if (stress > 40) return 'stat-bar-energy'
  return 'stat-bar-good'
})
</script>

<style scoped>
.hud-container {
  z-index: 100;
  border: 1px solid rgba(89, 113, 139, 0.22);
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.95) 0%, rgba(242, 247, 252, 0.96) 100%);
  box-shadow: 0 14px 36px rgba(18, 44, 73, 0.12);
}
.stat-item {
  min-width: 150px;
}

.stat-row {
  color: #22384e;
}

.stat-label,
.metric-label {
  color: #496176 !important;
  letter-spacing: 0.04em;
}

.progress {
  height: 10px;
}

.progress-bar {
  border-radius: 999px;
}

.stat-bar-energy {
  background: linear-gradient(90deg, #bd8b3b 0%, #e0bd68 100%) !important;
}

.stat-bar-good {
  background: linear-gradient(90deg, #2f7569 0%, #65a296 100%) !important;
}

.stat-bar-normal {
  background: linear-gradient(90deg, #386f9d 0%, #79a9ce 100%) !important;
}

.stat-bar-alert {
  background: linear-gradient(90deg, #93484f 0%, #bf7478 100%) !important;
}

.hud-metrics {
  border-color: rgba(89, 113, 139, 0.24) !important;
}

.hud-metric-block {
  min-width: 72px;
}

.metric-value {
  color: #193553;
}

.metric-excellent {
  color: #244f7c;
}

.metric-good {
  color: #2f7767;
}

.metric-warn {
  color: #9a6d25;
}

.metric-alert {
  color: #94454c;
}

@media (max-width: 430px) {
  .hud-container {
    padding: 10px !important;
    flex-direction: column;
    align-items: stretch !important;
    gap: 10px;
    margin-bottom: 10px !important;
  }

  .hud-container > .d-flex:first-child {
    width: 100%;
    margin-right: 0 !important;
    gap: 8px !important;
    flex-direction: column;
  }

  .hud-container > .d-flex:last-child {
    width: 100%;
    border-left: 0 !important;
    padding-left: 0 !important;
    border-top: 1px solid rgba(89, 113, 139, 0.24);
    padding-top: 8px;
    justify-content: space-between;
    gap: 0.5rem !important;
  }

  .stat-item {
    min-width: 0;
  }
}
</style>
