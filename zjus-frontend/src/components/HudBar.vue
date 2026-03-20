<template>
  <div
    id="hud-bars"
    class="hud-container d-flex justify-content-between align-items-center p-3 bg-white border rounded shadow-sm mb-3"
  >
    <div class="d-flex gap-4 flex-grow-1 me-4">
      <div class="stat-item flex-grow-1">
        <div class="d-flex justify-content-between small mb-1 fw-bold">
          <span>⚡ 精力</span>
          <span>{{ Math.floor(safeNumber(stats.energy, 100)) }} / 100</span>
        </div>
        <div
          class="progress"
          style="height: 12px;"
        >
          <div
            class="progress-bar bg-warning progress-bar-striped progress-bar-animated" 
            :style="{ width: `${Math.min(100, Math.max(0, safeNumber(stats.energy, 100)))}%` }"
          />
        </div>
      </div>

      <div class="stat-item flex-grow-1">
        <div class="d-flex justify-content-between small mb-1 fw-bold">
          <span>💖 心态</span>
          <span>{{ Math.floor(safeNumber(stats.sanity, 100)) }} / 100</span>
        </div>
        <div
          class="progress"
          style="height: 12px;"
        >
          <div
            class="progress-bar progress-bar-striped progress-bar-animated" 
            :class="sanityColorClass"
            :style="{ width: `${Math.min(100, Math.max(0, safeNumber(stats.sanity, 100)))}%` }"
          />
        </div>
      </div>
    </div>

    <div class="d-flex gap-4 border-start ps-4">
      <div class="text-center">
        <div class="small text-muted fw-bold">
          🧠 IQ / 🤝 EQ
        </div>
        <div class="fw-bold fs-5">
          {{ Math.floor(safeNumber(stats.iq, 100)) }} <span class="text-muted fs-6">/</span> {{ Math.floor(safeNumber(stats.eq, 100)) }}
        </div>
      </div>
      
      <div class="text-center">
        <div class="small text-muted fw-bold">
          🎓 GPA
        </div>
        <div
          class="fw-bold fs-5"
          :class="gpaColorClass"
        >
          <!-- 🌟 核心防御：保证 gpa 绝对是数字，再执行 toFixed -->
          {{ safeNumber(stats.gpa, 0).toFixed(2) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'

const store = useGameStore()
const stats = computed(() => store.currentStats)

// 🌟 安全转换函数，防止 undefined / null / string 导致页面崩溃
const safeNumber = (val, defaultVal = 0) => {
  if (val === null || val === undefined) return defaultVal
  const num = Number(val)
  return isNaN(num) ? defaultVal : num
}

const sanityColorClass = computed(() => {
  const sanity = safeNumber(stats.value.sanity, 100)
  if (sanity > 70) return 'bg-success'
  if (sanity > 30) return 'bg-info'
  return 'bg-danger'
})

const gpaColorClass = computed(() => {
  const gpa = safeNumber(stats.value.gpa, 0)
  if (gpa >= 4.0) return 'text-primary'
  if (gpa >= 3.0) return 'text-success'
  if (gpa >= 2.0) return 'text-warning'
  return 'text-danger'
})
</script>

<style scoped>
.hud-container {
  /* 确保它在页面上有足够的层级不被盖住 */
  z-index: 100;
}
.stat-item {
  min-width: 150px;
}
</style>