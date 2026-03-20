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
              +{{ data.gold_earned ?? 0 }} 💰
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
                <td>{{ course.credit }}</td>
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
      </div>

      <div class="card-footer bg-white border-0 py-3 text-center">
        <button 
          class="btn btn-primary btn-lg px-5 rounded-pill shadow-sm fw-bold pulse-btn"
          @click="startNextSemester"
        >
          {{ store.currentStats.semester_idx >= 8 ? '🎓 参加毕业典礼 ➔' : '🚀 开启新学期 ➔' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useGameStore } from '../../stores/gameStore.ts'

const store = useGameStore()
const emit = defineEmits(['send-action'])

// 动态获取模态框附带的数据
const data = computed(() => store.modalData)

// 计算是否有挂科
const hasFailedCourse = computed(() => {
  if (!data.value.courses) return false
  return data.value.courses.some(c => c.grade < 60)
})

const startNextSemester = () => {
  store.closeModal()
  // 永远只发送 next_semester，让后端自己去算是不是该毕业了
  emit('send-action', { action: 'next_semester' }) 
}
</script>

<style scoped>
/* 半透明黑色遮罩，覆盖全屏 */
.modal-backdrop-custom {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.6);
  z-index: 9999;
  backdrop-filter: blur(3px); /* 背景模糊效果 */
}

/* 简单的入场动画 */
.fade-in { animation: fadeIn 0.3s ease-out; }
.scale-in { animation: scaleIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes scaleIn { from { transform: scale(0.8); opacity: 0; } to { transform: scale(1); opacity: 1; } }

.pulse-btn {
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(13, 110, 253, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(13, 110, 253, 0); }
  100% { box-shadow: 0 0 0 0 rgba(13, 110, 253, 0); }
}
</style>