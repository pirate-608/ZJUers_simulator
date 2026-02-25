<template>
  <div class="hud-container d-flex justify-content-between align-items-center p-3 bg-white border rounded shadow-sm mb-3" id="hud-bars">
    
    <div class="d-flex gap-4 flex-grow-1 me-4">
      
      <div class="stat-item flex-grow-1">
        <div class="d-flex justify-content-between small mb-1 fw-bold">
          <span>⚡ 精力</span>
          <span>{{ stats.energy ?? 100 }} / 100</span>
        </div>
        <div class="progress" style="height: 12px;">
          <div class="progress-bar bg-warning progress-bar-striped progress-bar-animated" 
               :style="{ width: `${stats.energy ?? 100}%` }">
          </div>
        </div>
      </div>

      <div class="stat-item flex-grow-1">
        <div class="d-flex justify-content-between small mb-1 fw-bold">
          <span>💖 心态</span>
          <span>{{ stats.sanity ?? 100 }} / 100</span>
        </div>
        <div class="progress" style="height: 12px;">
          <div class="progress-bar progress-bar-striped progress-bar-animated" 
               :class="sanityColorClass"
               :style="{ width: `${stats.sanity ?? 100}%` }">
          </div>
        </div>
      </div>

      <div class="stat-item flex-grow-1">
        <div class="d-flex justify-content-between small mb-1 fw-bold">
          <span>🌋 压力</span>
          <span>{{ stats.stress ?? 0 }} / 100</span>
        </div>
        <div class="progress" style="height: 12px;">
          <div class="progress-bar progress-bar-striped progress-bar-animated" 
               :class="stressColorClass"
               :style="{ width: `${stats.stress ?? 0}%` }">
          </div>
        </div>
      </div>
      
    </div>

    <div class="d-flex gap-4 border-start ps-4">
      <div class="text-center">
        <div class="small text-muted fw-bold">🧠 IQ / 🤝 EQ</div>
        <div class="fw-bold fs-5">{{ stats.iq ?? 100 }} <span class="text-muted fs-6">/</span> {{ stats.eq ?? 100 }}</div>
      </div>
      <div class="text-center">
        <div class="small text-muted fw-bold">💰 资金</div>
        <div class="fw-bold fs-5 text-warning">{{ stats.gold ?? 0 }}</div>
      </div>
      <div class="text-center">
        <div class="small text-muted fw-bold">🎓 GPA</div>
        <div class="fw-bold fs-5 text-success">{{ (stats.gpa ?? 0).toFixed(2) }}</div>
      </div>
    </div>
    
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useGameStore } from '../stores/gameStore'

// 1. 引入 Store
const store = useGameStore()

// 2. 映射当前状态 (使用 computed 确保数据是响应式的)
const stats = computed(() => store.currentStats)

// 3. 编写业务逻辑：根据数值自动变色的计算属性
const sanityColorClass = computed(() => {
  const sanity = stats.value.sanity ?? 100
  if (sanity > 60) return 'bg-success'
  if (sanity > 30) return 'bg-warning'
  return 'bg-danger'
})

const stressColorClass = computed(() => {
  const stress = stats.value.stress ?? 0
  if (stress > 80) return 'bg-danger'
  if (stress >= 40 && stress <= 70) return 'bg-info' // 你在引导里提到的最佳区间
  return 'bg-secondary'
})
</script>

<style scoped>
/* 这里的样式只对当前组件生效，不会污染全局 */
.stat-item {
  min-width: 120px;
}
</style>