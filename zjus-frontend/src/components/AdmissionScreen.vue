<template>
  <div class="admission-body bg-light d-flex align-items-center justify-content-center vh-100">
    <div class="container">
      <div class="row justify-content-center">
        <div class="col-lg-8 col-md-10">
          
          <div class="admission-letter shadow-lg p-4 p-md-5 bg-white rounded-3 position-relative overflow-hidden fade-in-up">
            <div class="text-center mb-4 border-bottom pb-4">
              <h1 class="text-primary fw-bold mb-2">🎓 折姜大学</h1>
              <h2 class="admission-title mt-2 letter-spacing-wide">录取通知书</h2>
              <div class="text-uppercase text-muted ls-2 small">Admission Letter</div>
            </div>

            <div v-if="isLoading" class="text-center py-5">
              <div class="spinner-border text-danger mb-3" role="status"></div>
              <h5 class="text-muted">正在档案库中调取您的录取信息...</h5>
            </div>

            <div v-else class="admission-content my-4 px-md-4">
              <h4 class="mb-4">
                <span class="fw-bold text-primary border-bottom border-primary border-2 pb-1">{{ admissionData.username }}</span> 同学：
              </h4>
              <p class="lead" style="text-indent: 2em; line-height: 1.8;">
                经折姜大学招生委员会批准，你已被我校
                <span class="fw-bold text-danger mx-1 border-bottom border-danger border-2 pb-1">{{ admissionData.major }}</span>
                专业录取。
              </p>
              <p class="lead mt-4" style="text-indent: 2em; line-height: 1.8;">
                谨向你表示热烈祝贺！在过去学习生涯中，你是一位当之无愧的佼佼者。现在，你将踏入美丽的求是园，在更广阔的天地里，开启更加卓越、更有梦想的人生。请持本通知书于规定时间到校报到。
              </p>
            </div>

            <div v-if="!isLoading" class="d-flex justify-content-between align-items-end mt-5 px-md-4">
              <div class="text-center position-relative">
                <div class="rounded-circle border border-danger text-danger d-flex align-items-center justify-content-center mb-2"
                     style="width: 100px; height: 100px; transform: rotate(-15deg); opacity: 0.8; border-width: 3px !important;">
                  <small class="fw-bold">折姜大学<br>招生专用章</small>
                </div>
                <div class="text-muted small">{{ currentDate }}</div>
              </div>
            </div>
          </div>

          <div class="text-center mt-5 mb-5 fade-in-up delay-1">
            <button class="btn btn-primary btn-lg px-5 py-3 rounded-pill shadow fw-bold fs-5 pulse-btn" 
                    :disabled="isLoading"
                    @click="enterGame">
              🎒 我已确认，前往报到 (进入游戏)
            </button>
            <p class="text-muted mt-3 small">点击按钮即将开始你的大学生涯模拟，请确保已系好安全带</p>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useGameStore } from '../stores/gameStore'

const store = useGameStore()
const emit = defineEmits(['enter-game'])

const isLoading = ref(true)
const admissionData = ref({
  username: '新同学',
  major: '未分配专业'
})

// 计算当前日期
const now = new Date()
const currentDate = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`

// 组件挂载时，去后端拉取专业盲盒数据
onMounted(async () => {
  const token = localStorage.getItem('zju_token')
  if (!token) {
    alert('未找到学生凭证，请重新登录！')
    store.setPhase('login')
    return
  }

  try {
    // 携带 JWT Token 请求 API
    const response = await fetch('/api/admission_info', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (!response.ok) throw new Error('接口响应异常')
    
    const data = await response.json()
    // data 结构对应后端的 {"username": "...", "assigned_major": "...", "token": "..."}
    admissionData.value.username = data.username || '新同学'
    admissionData.value.major = data.assigned_major || '未分配专业'

    // 如果后端刷新了 Token，则更新本地缓存
    if (data.token) {
      localStorage.setItem('zju_token', data.token)
    }

  } catch (error) {
    console.error('无法获取录取信息:', error)
    alert('录取信息加载失败，请检查网络或重新登录。')
    store.setPhase('login')
  } finally {
    isLoading.value = false
  }
})

// 玩家点击按钮，触发正式进入游戏
const enterGame = () => {
  const token = localStorage.getItem('zju_token')
  if (token) {
    // 告诉父组件（App.vue），拿着这个 token 去连接 WebSocket！
    emit('enter-game', token)
  } else {
    store.setPhase('login')
  }
}
</script>

<style scoped>
/* 还原原生的出场动画 */
.fade-in-up {
  animation: fadeInUp 0.8s ease-out forwards;
}
.delay-1 { animation-delay: 0.3s; opacity: 0; }
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 按钮呼吸动画 */
.pulse-btn {
  animation: pulse 2s infinite;
  transition: transform 0.2s;
}
.pulse-btn:hover {
  transform: scale(1.05);
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(13, 110, 253, 0.4); }
  70% { box-shadow: 0 0 0 15px rgba(13, 110, 253, 0); }
  100% { box-shadow: 0 0 0 0 rgba(13, 110, 253, 0); }
}
</style>