<template>
  <div class="d-flex flex-column h-100">
    <div v-if="enrichedCourses.length === 0" class="text-center text-muted py-5">
      <div class="spinner-border spinner-border-sm text-info mb-2" role="status"></div>
      <div>正在加载课程大纲...</div>
    </div>

    <div v-else class="list-group list-group-flush course-list-panel overflow-auto flex-grow-1" style="max-height: 500px;">
      
      <div v-for="course in enrichedCourses" :key="course.id" 
           class="list-group-item px-3 py-3 course-item border-bottom">
        
        <div class="d-flex justify-content-between align-items-center mb-2">
          <span class="fw-bold text-dark" style="font-size: 0.95rem;">{{ course.name }}</span>
          <span class="badge bg-light text-secondary border">{{ course.credit }} 学分</span>
        </div>
        
        <div class="progress mb-2 bg-light" style="height: 8px;">
          <div class="progress-bar progress-bar-striped" 
               :class="getProgressColor(course.progress)" 
               :style="{ width: `${course.progress}%` }">
          </div>
        </div>
        
        <div class="d-flex justify-content-between align-items-center">
          <small class="text-muted fw-bold">掌握度: {{ course.progress.toFixed(1) }}%</small>
          
          <!-- 策略切换按钮组 (0:摆, 1:摸, 2:卷) -->
          <!-- 🌟 修复：绑定 :disabled="store.isPaused" 冻结交互 -->
          <div class="btn-group btn-group-sm shadow-sm" role="group">
            <button class="btn" 
                    :disabled="store.isPaused"
                    :class="course.state === 0 ? 'btn-danger text-white fw-bold' : 'btn-outline-secondary'"
                    @click="changeStrategy(course.id, 0)">摆</button>
            <button class="btn" 
                    :disabled="store.isPaused"
                    :class="course.state === 1 ? 'btn-warning text-dark fw-bold' : 'btn-outline-secondary'"
                    @click="changeStrategy(course.id, 1)">摸</button>
            <button class="btn" 
                    :disabled="store.isPaused"
                    :class="course.state === 2 ? 'btn-success text-white fw-bold' : 'btn-outline-secondary'"
                    @click="changeStrategy(course.id, 2)">卷</button>
          </div>
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
      progress: progressData.progress ?? 0,
      state: state
    }
  })
})

// 根据进度改变进度条颜色
const getProgressColor = (progress) => {
  if (progress >= 85) return 'bg-success'
  if (progress >= 60) return 'bg-info'
  return 'bg-secondary' // 不及格时的颜色
}

// 切换课程策略的方法
const changeStrategy = (courseId, newState) => {
  store.setCourseState(courseId, newState)
  emit('send-action', {
    action: 'change_course_state',
    target: courseId,  // 之前写的是 course_id，后端不认
    value: newState    // 之前写的是 state，后端不认
  })
}
</script>

<style scoped>
/* 给按钮组增加一点点击时的缩放动画，提升手感 */
.btn-group .btn {
  transition: all 0.2s ease-in-out;
}
.btn-group .btn:active {
  transform: scale(0.95);
}
</style>