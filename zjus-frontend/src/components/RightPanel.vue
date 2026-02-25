<template>
  <div class="d-flex flex-column gap-3 h-100">

    <div class="card border-0 shadow-sm">
      <div class="card-header bg-success text-white py-1 text-center fw-bold" style="font-size: 0.9rem;">
        📊 状态与增益
      </div>
      <div class="card-body p-2">
        <div class="d-flex justify-content-between align-items-center p-2 rounded mb-2" 
             style="background-color: rgba(13, 110, 253, 0.08); border: 1px solid rgba(13, 110, 253, 0.2);">
          <div>
            <span class="text-muted" style="font-size: 0.8rem;">学习效率</span>
            <div class="small text-muted" style="font-size: 0.7rem;">{{ efficiencyHint }}</div>
          </div>
          <span class="fw-bold text-primary fs-5">{{ store.currentStats.efficiency ?? 100 }}%</span>
        </div>

        <div class="d-flex justify-content-around align-items-center pt-1 border-top">
          <div class="text-center" title="运气影响随机事件的好坏">
            <span class="fs-5">🍀</span> <span class="fw-bold small">{{ store.currentStats.luck ?? '--' }}</span>
          </div>
          <div class="text-center" title="风评影响部分课程和NPC互动">
            <span class="fs-5">⭐</span> <span class="fw-bold small">{{ store.currentStats.reputation ?? 0 }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="card border-0 shadow-sm">
      <div class="card-header bg-warning text-dark py-1 text-center fw-bold" style="font-size: 0.9rem;">
        ☕ 摸鱼休闲
      </div>
      <div class="card-body p-2">
        <div class="row g-2">
          <div class="col-6">
            <button class="btn btn-sm btn-outline-primary w-100" @click="sendRelax('gym')">🏋️‍♂️ 健身</button>
          </div>
          <div class="col-6">
            <button class="btn btn-sm btn-outline-success w-100" @click="sendRelax('game')">🎮 游戏</button>
          </div>
          <div class="col-6">
            <button class="btn btn-sm btn-outline-info w-100" @click="sendRelax('cc98')">🌊 CC98</button>
          </div>
          <div class="col-6">
            <button class="btn btn-sm btn-outline-secondary w-100" @click="sendRelax('walk')">🚶 散步</button>
          </div>
        </div>
      </div>
    </div>

    <div class="card border-0 shadow-sm flex-grow-1">
      <div class="card-header bg-danger text-white py-1 text-center fw-bold" style="font-size: 0.9rem;">
        🔥 学期进度
      </div>
      <div class="card-body p-3 d-flex flex-column justify-content-center">
        
        <div class="d-flex justify-content-between align-items-end mb-1">
          <span class="small fw-bold text-muted">平均课程掌握度</span>
          <span class="text-primary fw-bold">{{ averageProgress.toFixed(1) }}%</span>
        </div>
        <div class="progress mb-3 shadow-sm" style="height: 12px;">
          <div class="progress-bar bg-info progress-bar-striped progress-bar-animated" 
               :style="{ width: `${averageProgress}%` }"></div>
        </div>

        <div class="d-flex justify-content-between align-items-center p-2 rounded bg-light border border-danger border-opacity-25">
          <div class="text-center px-2">
            <div class="small text-muted" style="font-size: 0.75rem;">倒计时</div>
            <div class="fw-bold text-danger fs-5" style="font-family: monospace;">
              {{ store.semesterTimeLeft ?? '--:--' }}
            </div>
          </div>
          <button class="btn btn-danger fw-bold shadow-sm px-3" 
                  :disabled="!canTakeExam"
                  @click="takeExam">
            参加期末考 ➔
          </button>
        </div>

      </div>
    </div>

  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useGameStore } from '../stores/gameStore'

const store = useGameStore()
const emit = defineEmits(['send-action'])

// --- 数据计算逻辑 ---

// 计算效率的文案提示（替代原先 uiManager.js 里的长串 if-else）
const efficiencyHint = computed(() => {
  const eff = store.currentStats.efficiency ?? 100
  if (eff >= 120) return '如有神助 🚀'
  if (eff >= 100) return '状态良好 ✅'
  if (eff >= 80) return '略显疲态 ⚠️'
  return '效率低下 ❌'
})

// 计算课程平均掌握度 (动态从 store 的课程数据中读取)
const averageProgress = computed(() => {
  const courses = store.currentStats.courses
  if (!courses || Object.keys(courses).length === 0) return 0
  
  let totalProgress = 0
  let count = 0
  for (const courseId in courses) {
    totalProgress += courses[courseId].progress ?? 0
    count++
  }
  return count > 0 ? Math.min(100, totalProgress / count) : 0
})

// 考试按钮是否可用（例如：倒计时显示为 0，或触发了特定状态）
const canTakeExam = computed(() => {
  // 你可以根据你的游戏逻辑调整，比如如果时间变成 '00:00' 就可以考
  return store.semesterTimeLeft === '00:00' || store.semesterTimeLeft === '考试周' 
})

// --- 发送指令逻辑 ---

const sendRelax = (activity) => {
  emit('send-action', { action: 'relax', type: activity })
}

const takeExam = () => {
  emit('send-action', { action: 'exam' })
}
</script>