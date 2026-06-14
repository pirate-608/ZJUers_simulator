<template>
  <div class="d-flex flex-column h-100" id="tour-course-list">
    <div
      v-if="enrichedCourses.length === 0"
      class="text-center text-muted py-5"
    >
      <div
        class="spinner-border spinner-border-sm text-info mb-2"
        role="status"
      />
      <div>正在加载课程大纲...</div>
    </div>

    <div
      v-else
      class="list-group list-group-flush course-list-panel overflow-auto flex-grow-1"
      style="max-height: 500px;"
    >
      <div
        v-for="course in enrichedCourses"
        :key="course.id" 
        class="list-group-item px-3 py-3 course-item border-bottom"
      >
        <div class="d-flex justify-content-between align-items-center mb-2">
          <span
            class="fw-bold course-title"
          >{{ course.name }}</span>
          <span class="badge course-credit">{{ course.credit }} 学分</span>
        </div>
        
        <div
          class="progress mb-2"
        >
          <div
            class="progress-bar"
            :class="getProgressColor(course.progress)" 
            :style="{ width: `${course.progress}%` }"
          />
        </div>
        
        <div class="d-flex justify-content-between align-items-center">
          <small class="text-muted fw-bold">掌握度: {{ course.progress.toFixed(1) }}%</small>
          
          <!-- 策略切换按钮组 (0:摆, 1:摸, 2:卷) -->
          <!-- 🌟 修复：绑定 :disabled="store.isPaused" 冻结交互 -->
          <div
            class="btn-group btn-group-sm shadow-sm"
            role="group"
          >
            <button
              class="btn strategy-btn strategy-rest"
              :disabled="store.isPaused"
              :class="{ active: course.state === 0 }"
              @click="changeStrategy(course.id, 0)"
            >
              摆
            </button>
            <button
              class="btn strategy-btn strategy-steady"
              :disabled="store.isPaused"
              :class="{ active: course.state === 1 }"
              @click="changeStrategy(course.id, 1)"
            >
              摸
            </button>
            <button
              class="btn strategy-btn strategy-focus"
              :disabled="store.isPaused"
              :class="{ active: course.state === 2 }"
              @click="changeStrategy(course.id, 2)"
            >
              卷
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { WsClientAction } from '@/types/websocket'

const store = useGameStore()
const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()

// 🌟 核心魔法：数据缝合计算属性
// 我们将 courseMetadata(静态数据), courses(进度数据), courseStates(策略数据) 缝合成一个数组
const enrichedCourses = computed(() => {
  if (!store.courseMetadata || store.courseMetadata.length === 0) return []
  if (!store.currentStats?.courses) return []

  return store.courseMetadata.map(meta => {
    // 获取当前这门课的进度数据，如果没有则默认为 0
    const progressData = store.currentStats.courses[meta.id] || { progress: 0 }
    // 获取当前这门课的策略状态，如果没有则默认为 1 (摸)
    const state = store.currentCourseStates[meta.id] ?? 1

    return {
      id: meta.id,
      name: meta.name,
      credit: meta.credit,
      progress: (progressData.progress as number) ?? 0,
      state: state
    }
  })
})

// 根据进度改变进度条颜色
const getProgressColor = (progress: number): string => {
  if (progress >= 85) return 'course-progress-high'
  if (progress >= 60) return 'course-progress-mid'
  return 'course-progress-low'
}

// 切换课程策略的方法
const changeStrategy = (courseId: string, newState: number) => {
  store.setCourseState(courseId, newState)
  emit('send-action', {
    action: 'change_course_state',
    target: courseId,
    value: newState
  })
}
</script>

<style scoped>
.course-list-panel {
  background: linear-gradient(180deg, #f8fbfe 0%, #eef4fa 100%);
  scrollbar-color: #9eb2c6 transparent;
}

.course-item {
  border-color: #dce6f0 !important;
  background: rgba(255, 255, 255, 0.72);
}

.course-item:hover {
  background: rgba(255, 255, 255, 0.95);
}

.course-title {
  color: #1b3048;
  font-size: 0.94rem;
  letter-spacing: 0.01em;
}

.course-credit {
  color: #46627c;
  border: 1px solid #c7d5e3;
  background: #eef4fa;
}

.progress {
  height: 8px;
  background: #e3ebf4;
}

.course-progress-high {
  background: linear-gradient(90deg, #2f7569 0%, #65a296 100%) !important;
}

.course-progress-mid {
  background: linear-gradient(90deg, #3b709e 0%, #7aa9ce 100%) !important;
}

.course-progress-low {
  background: linear-gradient(90deg, #6a7888 0%, #9aa8b6 100%) !important;
}

/* 给按钮组增加一点点击时的缩放动画，提升手感 */
.btn-group .btn {
  transition: all 0.2s ease-in-out;
}
.btn-group .btn:active {
  transform: scale(0.95);
}

.strategy-btn {
  color: #31536f;
  border-color: #c2d0dd;
  background: #f7fbff;
  min-width: 36px;
}

.strategy-btn:hover:not(:disabled) {
  color: #15324f;
  border-color: #8fa8bf;
  background: #e9f1f8;
}

.strategy-rest.active {
  color: #fff;
  border-color: #7d4850;
  background: linear-gradient(180deg, #a25d63 0%, #85444c 100%);
}

.strategy-steady.active {
  color: #24384d;
  border-color: #b88a44;
  background: linear-gradient(180deg, #d9bf7a 0%, #bf9350 100%);
}

.strategy-focus.active {
  color: #fff;
  border-color: #275f55;
  background: linear-gradient(180deg, #448373 0%, #2e6d62 100%);
}

@media (max-width: 430px) {
  .course-list-panel {
    max-height: 360px !important;
  }

  .course-item {
    padding: 0.7rem 0.65rem !important;
  }

  .course-item .course-title {
    max-width: 66%;
    line-height: 1.25;
    font-size: 0.86rem !important;
  }

  .course-item .badge {
    font-size: 0.7rem;
  }

  .course-item .btn-group .btn {
    font-size: 0.75rem;
    padding: 0.2rem 0.42rem;
  }
}
</style>
