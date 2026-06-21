<template>
  <div
    v-if="store.activeModal === 'transcript'" 
    class="modal-backdrop-custom d-flex justify-content-center align-items-center fade-in"
  >
    <div
      class="card shadow-lg border-0 modal-card scale-in"
      style="width: 90%; max-width: 700px; max-height: 90vh;"
    >
      <div class="card-header bg-success text-white py-3 text-center">
        <h4 class="mb-0 fw-bold">
          📜 期末成绩单
        </h4>
        <div class="small opacity-75 mt-1">
          {{ data.semester_name || '本学期' }} 结算完毕
        </div>
      </div>

      <div class="card-body overflow-auto p-4">
        <div class="row text-center mb-4 pb-3 border-bottom">
          <div class="col-4">
            <div class="text-muted small fw-bold">
              当期 GPA
            </div>
            <div class="fs-2 fw-bold text-primary">
              {{ data.term_gpa?.toFixed(2) ?? '0.00' }}
            </div>
          </div>
          <div class="col-4 border-start border-end">
            <div class="text-muted small fw-bold">
              累计 GPA
            </div>
            <div class="fs-2 fw-bold text-success">
              {{ data.cgpa?.toFixed(2) ?? '0.00' }}
            </div>
          </div>
          <div class="col-4">
            <div class="text-muted small fw-bold">
              奖学金 / 兼职收入
            </div>
            <div class="fs-2 fw-bold text-warning">
              +{{ data.gold_earned ?? 0 }} {{ statIcon('gold') }}
            </div>
          </div>
        </div>

        <h6 class="fw-bold mb-3">
          详细成绩：
        </h6>
        <div class="table-responsive">
          <table class="table table-hover table-bordered align-middle text-center">
            <thead class="table-light">
              <tr>
                <th class="text-start">
                  课程名称
                </th>
                <th>学分</th>
                <th>考前掌握度</th>
                <th>最终分数</th>
                <th>获得绩点</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(course, index) in data.courses"
                :key="index" 
                :class="{ 'table-danger text-danger': course.grade < 60 }"
              >
                <td class="text-start fw-bold">
                  {{ course.name }}
                </td>
                <td>{{ courseCredit(course) }}</td>
                <td>{{ course.progress?.toFixed(1) }}%</td>
                <td class="fw-bold fs-5">
                  {{ course.grade }}
                </td>
                <td class="fw-bold">
                  {{ course.gpa?.toFixed(1) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <div
          v-if="hasFailedCourse"
          class="alert alert-danger mt-3 mb-0 small"
        >
          ⚠️ 警告：你有课程不及格！心态大幅下降，请下学期注意选课和学习策略。
        </div>

        <div
          v-if="newAchievements.length"
          class="achievement-summary mt-3"
        >
          <div class="fw-bold mb-2">
            本学期新解锁成就
          </div>
          <div class="d-flex flex-wrap gap-2">
            <div
              v-for="achievement in newAchievements"
              :key="achievement.code"
              class="achievement-chip"
            >
              <span class="achievement-icon">{{ achievement.icon || '🏅' }}</span>
              <span class="fw-bold">{{ achievement.name }}</span>
              <span
                v-if="achievement.desc"
                class="achievement-desc"
              >{{ achievement.desc }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card-footer bg-white border-0 py-3 text-center">
        <button 
          class="btn btn-primary btn-lg px-5 rounded-pill shadow-sm fw-bold pulse-btn"
          @click="startNextSemester"
        >
          {{ (store.currentStats.semester_idx ?? 1) >= 8 ? '🎓 参加毕业典礼 ➔' : '🚀 开启新学期 ➔' }}
        </button>
        <div class="refresh-hint small text-muted mt-2">
          如果开启后学期状态没有刷新，请手动刷新浏览器。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * End-of-semester transcript modal with GPA, gold, courses, and achievements.
 */
import { computed } from 'vue'
import { useGameStore } from '../../stores/gameStore.ts'
import type { WsClientAction } from '@/types/websocket'
import type { TranscriptModalData, TranscriptModalCourseRow } from '@/types/modal'
import { statIcon } from '@/utils/statDisplay'

const store = useGameStore()
const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()

/** Modal payload for the current semester transcript. */
const data = computed(() => store.modalData as TranscriptModalData)

/** Whether any course in the transcript failed. */
const hasFailedCourse = computed(() => {
  if (!data.value.courses) return false
  return data.value.courses.some((c: TranscriptModalCourseRow) => c.grade < 60)
})

const newAchievements = computed(() => Array.isArray(data.value.achievements) ? data.value.achievements : [])

const courseCredit = (course: TranscriptModalCourseRow): string => {
  const value = Number(course.credit ?? course.credits ?? 0)
  return Number.isFinite(value) ? String(value) : '0'
}

const startNextSemester = () => {
  store.closeModal()
  // The backend decides whether the next step is another semester or graduation.
  emit('send-action', { action: 'next_semester' }) 
}
</script>

<style scoped>
/* Full-screen translucent overlay for the semester transcript. */
.modal-backdrop-custom {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  padding: 14px;
  overflow-y: auto;
  background-color: rgba(0, 0, 0, 0.6);
  z-index: 9999;
  backdrop-filter: blur(3px);
}

.modal-card {
  margin: auto;
  background: #fdfaf2;
  border: 1px solid #d8d0bd !important;
}

/* Lightweight entrance animations for the modal shell. */
.fade-in { animation: fadeIn 0.3s ease-out; }
.scale-in { animation: scaleIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes scaleIn { from { transform: scale(0.8); opacity: 0; } to { transform: scale(1); opacity: 1; } }

.pulse-btn {
  animation: pulse 2s infinite;
}

.achievement-summary {
  padding: 12px;
  border: 1px solid rgba(180, 126, 45, 0.28);
  border-radius: 10px;
  background: rgba(255, 247, 226, 0.82);
}

.achievement-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 6px 10px;
  border: 1px solid rgba(161, 112, 39, 0.22);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: #5e431f;
}

.achievement-icon {
  font-size: 1rem;
}

.achievement-desc {
  color: #7d705e;
  font-size: 0.78rem;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(13, 110, 253, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(13, 110, 253, 0); }
  100% { box-shadow: 0 0 0 0 rgba(13, 110, 253, 0); }
}

@media (max-width: 768px) {
  .card-body {
    padding: 1rem !important;
  }
}

@media (max-width: 430px) {
  .modal-backdrop-custom {
    padding: 10px;
  }

  .modal-card {
    width: 100% !important;
  }

  .modal-card .row .col-4 {
    padding-left: 4px;
    padding-right: 4px;
  }

  .modal-card .fs-2 {
    font-size: 1.3rem !important;
  }

  .modal-card .btn-lg {
    width: 100%;
    font-size: 0.9rem;
    padding: 0.58rem 0.8rem;
  }
}
</style>
