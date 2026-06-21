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
          
          <!-- Study intensity controls: 0 = low, 1 = steady, 2 = intense. -->
          <!-- The disabled binding freezes course interactions while paused. -->
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
/**
 * Course list with per-course strategy controls.
 */
import { computed } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { WsClientAction } from '@/types/websocket'

const store = useGameStore()
const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()

/** Merge static metadata, mastery progress, and strategy state for rendering. */
const enrichedCourses = computed(() => {
  if (!store.courseMetadata || store.courseMetadata.length === 0) return []
  if (!store.currentStats?.courses) return []

  return store.courseMetadata.map(meta => {
    const progressData = store.currentStats.courses[meta.id] || { progress: 0 }
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

/** Return the visual progress class for a course mastery percentage. */
const getProgressColor = (progress: number): string => {
  if (progress >= 85) return 'course-progress-high'
  if (progress >= 60) return 'course-progress-mid'
  return 'course-progress-low'
}

/** Emit a course-strategy change after updating local optimistic state. */
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
  background: var(--console-surface-gradient);
  scrollbar-color: var(--console-primary-border) transparent;
}

.course-item {
  border-color: var(--console-border-strong) !important;
  background: color-mix(in srgb, var(--console-surface) 72%, transparent);
}

.course-item:hover {
  background: color-mix(in srgb, var(--console-surface) 95%, transparent);
}

.course-title {
  color: var(--console-text);
  font-size: 0.94rem;
  letter-spacing: 0.01em;
}

.course-credit {
  color: var(--console-muted);
  border: 1px solid var(--console-primary-border);
  background: var(--console-surface-alt);
}

.progress {
  height: 8px;
  background: var(--console-primary-soft);
}

.course-progress-high {
  background: var(--console-good-gradient) !important;
}

.course-progress-mid {
  background: var(--console-normal-gradient) !important;
}

.course-progress-low {
  background: var(--console-low-gradient) !important;
}

/* Adds a subtle press animation to make study actions feel responsive. */
.btn-group .btn {
  transition: all 0.2s ease-in-out;
}
.btn-group .btn:active {
  transform: scale(0.95);
}

.strategy-btn {
  color: var(--console-primary);
  border-color: var(--console-primary-border);
  background: var(--console-surface-soft);
  min-width: 36px;
}

.strategy-btn:hover:not(:disabled) {
  color: var(--console-primary-dark);
  border-color: var(--console-primary);
  background: var(--console-primary-soft);
}

.strategy-rest.active {
  color: #fff;
  border-color: #7d4850;
  background: linear-gradient(180deg, #a25d63 0%, #85444c 100%);
}

.strategy-steady.active {
  color: var(--console-gold-text);
  border-color: var(--console-gold-border);
  background: var(--console-warn-gradient);
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
