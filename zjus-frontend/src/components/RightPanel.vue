<template>
  <div class="right-panel d-flex flex-column gap-3 h-100" id="tour-right-panel">
    <div class="card">
      <div
        class="card-header section-header section-header-info py-1 text-center fw-bold"
        style="font-size: 0.9rem;"
      >
        状态与增益
      </div>
      <div class="card-body p-2">
        <div
          class="d-flex justify-content-between align-items-center p-2 rounded mb-2 efficiency-card"
        >
          <div>
            <span
              class="text-muted"
              style="font-size: 0.8rem;"
            >{{ statLabel('efficiency') }}</span>
            <div
              class="small text-muted"
              style="font-size: 0.7rem;"
            >
              {{ efficiencyHint }}
            </div>
          </div>
          <span class="fw-bold text-primary fs-5">{{ formatStatValue(store.currentStats, 'efficiency') }}%</span>
        </div>

        <div class="d-flex justify-content-around align-items-center pt-2 border-top mini-metrics">
          <div
            v-for="stat in miniStats"
            :key="stat.id"
            class="text-center"
            :title="stat.title"
          >
            <span class="fs-5">{{ stat.icon }}</span> <span class="fw-bold small">{{ stat.value }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div
        class="card-header section-header section-header-warn py-1 text-center fw-bold"
        style="font-size: 0.9rem;"
      >
        摸鱼休闲
      </div>
      <div class="card-body p-2">
        <div class="row g-2">
          <!-- 🌟 修复：全部绑定 :disabled="store.isPaused" -->
          <div class="col-6">
            <button
              class="btn btn-sm btn-outline-primary w-100 relax-btn"
              :disabled="isRelaxDisabled('gym')"
              :title="relaxButtonTitle('gym')"
              @click="sendRelax('gym')"
            >
              {{ relaxButtonLabel('gym') }}
            </button>
          </div>
          <div class="col-6">
            <button
              class="btn btn-sm btn-outline-success w-100 relax-btn"
              :disabled="isRelaxDisabled('game')"
              :title="relaxButtonTitle('game')"
              @click="sendRelax('game')"
            >
              {{ relaxButtonLabel('game') }}
            </button>
          </div>
          <div class="col-6">
            <button
              class="btn btn-sm btn-outline-info w-100 relax-btn"
              :disabled="isRelaxDisabled('cc98')"
              :title="relaxButtonTitle('cc98')"
              @click="sendRelax('cc98')"
            >
              {{ relaxButtonLabel('cc98') }}
            </button>
          </div>
          <div class="col-6">
            <button
              class="btn btn-sm btn-outline-secondary w-100 relax-btn"
              :disabled="isRelaxDisabled('walk')"
              :title="relaxButtonTitle('walk')"
              @click="sendRelax('walk')"
            >
              {{ relaxButtonLabel('walk') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="card flex-grow-1">
      <div
        class="card-header section-header section-header-danger py-1 text-center fw-bold"
        style="font-size: 0.9rem;"
      >
        学期进度
      </div>
      <div class="card-body p-3 d-flex flex-column justify-content-center">
        <div class="d-flex justify-content-between align-items-end mb-1">
          <span class="small fw-bold text-muted">平均课程掌握度</span>
          <span class="text-primary fw-bold">{{ averageProgress.toFixed(1) }}%</span>
        </div>
        <div
          class="progress mb-3"
        >
          <div
            class="progress-bar semester-progress-bar"
            :style="{ width: `${averageProgress}%` }"
          />
        </div>

        <!-- 倒计时与考试按钮放在同一个高亮框内，完美融合 -->
        <div class="d-flex justify-content-between align-items-center p-2 rounded exam-panel">
          <div class="text-center px-2">
            <div
              class="small text-muted"
              style="font-size: 0.75rem;"
            >
              倒计时
            </div>
            <div
              class="fw-bold text-danger fs-5"
              style="font-family: monospace;"
            >
              {{ formattedTime }}
            </div>
          </div>
          <!-- 🌟 修复：考试按钮同时受控于暂停和倒计时状态 -->
          <button
            class="btn exam-btn fw-bold px-3"
            :disabled="store.isPaused || !canTakeExam"
            @click="takeExam"
          >
            参加期末考 ➔
          </button>
        </div>
      </div>
    </div>

    <div class="card">
      <div
        class="card-header section-header section-header-info py-1 text-center fw-bold"
        style="font-size: 0.85rem;"
      >
        内容生成模式
      </div>
      <div class="card-body p-2">
        <div
          class="btn-group w-100 mode-group"
          role="group"
        >
          <button
            class="btn btn-sm"
            :class="store.gameMode === 'library' ? 'btn-primary' : 'btn-outline-secondary'"
            @click="setMode('library')"
          >
            📚 算法
          </button>
          <button
            class="btn btn-sm"
            :class="store.gameMode === 'hybrid' ? 'btn-primary' : 'btn-outline-secondary'"
            @click="setMode('hybrid')"
          >
            🔀 混合
          </button>
          <button
            class="btn btn-sm"
            :class="store.gameMode === 'ai' ? 'btn-primary' : 'btn-outline-secondary'"
            :disabled="!store.llmAvailable"
            :title="!store.llmAvailable ? 'LLM API 不可用' : '直接调用 AI 生成事件'"
            @click="setMode('ai')"
          >
            🤖 AI
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { WsClientAction, RelaxTarget } from '@/types/websocket'
import {
  formatStatValue,
  statDefault,
  statIcon,
  statLabel,
  statValue,
} from '@/utils/statDisplay'

const store = useGameStore()
const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()

function setMode(mode: 'library' | 'ai' | 'hybrid') {
  store.gameMode = mode
  emit('send-action', { action: 'set_mode', mode })
}

// ✨ 本地虚拟时间，用于丝滑渲染
const internalTime = ref(0)
let animationFrameId: number | null = null
let cooldownIntervalId: ReturnType<typeof setInterval> | null = null
let lastTick = performance.now()

// 监听后端推送过来的绝对准确时间，消除任何前端误差
watch(() => store.semesterTimeLeft, (newVal: number) => {
  if (newVal !== undefined) {
    internalTime.value = newVal // 每当后端 Tick 到达，强制校准
  }
}, { immediate: true })

// ✨ 60帧/秒的平滑倒计时器
const updateFrame = () => {
  const now = performance.now()
  const deltaMs = now - lastTick
  lastTick = now

  if (!store.isPaused && !store.isGuideActive && store.currentPhase === 'playing') {
    // 根据当前的倍速，扣减对应流逝的秒数
    // 如果是 2.0x，真实世界过去 16ms，游戏里就流逝 32ms
    internalTime.value -= (deltaMs / 1000) * store.gameSpeed
    if (internalTime.value < 0) internalTime.value = 0
  }
  animationFrameId = requestAnimationFrame(updateFrame)
}

onMounted(() => {
  lastTick = performance.now()
  animationFrameId = requestAnimationFrame(updateFrame)
  cooldownIntervalId = setInterval(() => {
    store.tickRelaxCooldowns(1)
  }, 1000)
})

onUnmounted(() => {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
  }
  if (cooldownIntervalId !== null) {
    clearInterval(cooldownIntervalId)
  }
})

// 将内部的浮点数秒数格式化为 MM:SS
const formattedTime = computed(() => {
  const totalSeconds = Math.ceil(internalTime.value) // 向上取整，显得紧凑
  if (totalSeconds <= 0) return '00:00'
  const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0')
  const s = (totalSeconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
})

// --- 数据计算逻辑 ---

// 计算效率的文案提示
const efficiencyHint = computed(() => {
  const baseline = statDefault('efficiency')
  const eff = statValue(store.currentStats, 'efficiency')
  if (eff >= baseline * 1.2) return '卓越状态'
  if (eff >= baseline) return '稳定运行'
  if (eff >= baseline * 0.8) return '略有疲态'
  return '需调整节奏'
})

const miniStats = computed(() => [
  {
    id: 'luck',
    icon: statIcon('luck'),
    value: formatStatValue(store.currentStats, 'luck'),
    title: `${statLabel('luck')}影响随机事件的好坏`,
  },
  {
    id: 'reputation',
    icon: statIcon('reputation'),
    value: formatStatValue(store.currentStats, 'reputation'),
    title: `${statLabel('reputation')}影响部分课程和NPC互动`,
  },
  {
    id: 'charm',
    icon: statIcon('charm'),
    value: formatStatValue(store.currentStats, 'charm'),
    title: `${statLabel('charm')}影响部分社交互动和事件反馈`,
  },
])

// 计算课程平均掌握度 (动态从 store 的课程数据中读取)
const averageProgress = computed(() => {
  const courses = store.currentStats.courses
  if (!courses || Object.keys(courses).length === 0) return 0
  let totalProgress = 0, count = 0
  for (const courseId in courses) {
    totalProgress += (courses[courseId].progress as number) ?? 0
    count++
  }
  return count > 0 ? Math.min(100, totalProgress / count) : 0
})

// 玩家可以主动提前考试，但本学期结算后不可重复触发。
const canTakeExam = computed(() => {
  return Number(store.currentStats.exam_completed || 0) <= 0
})

// --- 发送指令逻辑 ---

const relaxLabels: Record<RelaxTarget, string> = {
  gym: '健身',
  game: '游戏',
  walk: '散步',
  cc98: 'CC98',
}

const cooldownRemaining = (activity: RelaxTarget) => store.relaxCooldowns[activity] ?? 0

const isRelaxDisabled = (activity: RelaxTarget) => {
  return store.isPaused || cooldownRemaining(activity) > 0
}

const relaxButtonLabel = (activity: RelaxTarget) => {
  const remaining = cooldownRemaining(activity)
  if (remaining > 0) return `${relaxLabels[activity]} ${remaining}s`
  return relaxLabels[activity]
}

const relaxButtonTitle = (activity: RelaxTarget) => {
  const remaining = cooldownRemaining(activity)
  if (remaining > 0) return `冷却中，还剩 ${remaining} 秒`
  if (store.isPaused) return '游戏暂停中'
  return ''
}

const sendRelax = (activity: RelaxTarget) => {
  if (isRelaxDisabled(activity)) return
  emit('send-action', { action: 'relax', target: activity }) 
}
const takeExam = () => {
  store.showModal('exam_confirm')
}
</script>

<style scoped>
.section-header {
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
  color: var(--console-panel-header-text);
  border-bottom: 1px solid rgba(255, 255, 255, 0.16);
  letter-spacing: 0.08em;
}

.section-header-info {
  background: var(--console-panel-header-gradient) !important;
}

.section-header-warn {
  background: var(--console-panel-header-gradient-alt) !important;
}

.section-header-danger {
  background: var(--console-panel-header-gradient-deep) !important;
}

.efficiency-card {
  background: var(--console-surface-gradient);
  border: 1px solid var(--console-border-strong);
}

.mini-metrics {
  border-color: var(--console-border-strong) !important;
  color: var(--console-text);
}

.relax-btn {
  min-height: 31px;
  white-space: nowrap;
  border-color: var(--console-primary-border);
  color: var(--console-primary);
  background: var(--console-surface-soft);
  font-weight: 700;
}

.relax-btn:hover:not(:disabled) {
  color: #fff;
  border-color: var(--console-primary);
  background: var(--console-primary-gradient);
}

.semester-progress-bar {
  background: var(--console-normal-gradient) !important;
}

.exam-panel {
  background: var(--console-surface-gradient);
  border: 1px solid var(--console-border-strong);
}

.exam-btn {
  color: #fff;
  border-color: var(--console-danger-dark);
  background: var(--console-danger-gradient);
  box-shadow: 0 8px 18px color-mix(in srgb, var(--console-danger-dark) 18%, transparent);
}

.exam-btn:hover:not(:disabled) {
  color: #fff;
  border-color: var(--console-danger);
  background: var(--console-danger-gradient-hover);
}

.mode-group {
  border-radius: 7px;
  box-shadow: inset 0 0 0 1px var(--console-border-strong);
  overflow: hidden;
}

.mode-group .btn {
  border-color: transparent;
  font-weight: 700;
}

@media (max-width: 430px) {
  .right-panel {
    gap: 10px !important;
  }

  .right-panel .card-body {
    padding: 0.6rem !important;
  }

  .right-panel .btn {
    font-size: 0.78rem;
    padding: 0.34rem 0.2rem;
  }

  .right-panel .fs-5 {
    font-size: 1rem !important;
  }
}
</style>
