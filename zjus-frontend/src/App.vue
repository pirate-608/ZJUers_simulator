<script setup>
import { onMounted } from 'vue'
import { useGameStore } from './stores/gameStore'
import { useGameWebSocket } from './composables/useGameWebSocket'
import LoginView from './components/LoginView.vue'
import AdmissionScreen from './components/AdmissionScreen.vue'
import HudBar from './components/HudBar.vue'
import MidPanel from './components/MidPanel.vue'
import RightPanel from './components/RightPanel.vue'
import CourseList from './components/CourseList.vue'
import TranscriptModal from './components/modals/TranscriptModal.vue'
import RandomEventModal from './components/modals/RandomEventModal.vue'
import TopNav from './components/TopNav.vue'
import ExitConfirmModal from './components/modals/ExitConfirmModal.vue'
import EndScreen from './components/EndScreen.vue'

const store = useGameStore()
// 将 connect 暴露出来
const { connect, isConnected, send } = useGameWebSocket()

onMounted(() => {
  // SPA 路由入口：检查是否有 Token
  const existingToken = localStorage.getItem('zju_token')
  if (existingToken) {
    // 如果有，说明是老玩家刷新了页面，直接去录取通知书页面加载数据
    store.setPhase('admission')
  } else {
    // 如果没有，乖乖去考试
    store.setPhase('login')
  }
})

// 核心：处理正式进入游戏的动作
const handleEnterGame = (token) => {
  store.setPhase('loading') 
  
  // 动态获取当前协议和域名
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = window.location.host; // 会自动带上端口(如果有)
  const wsUrl = `${wsProtocol}//${wsHost}`; // 结果例如: wss://game.67656.fun
  
  // 同样，API fetch 请求因为写的是 '/api/xxx'，也会自动拼在这个域名后
  connect(token, wsUrl) 
}
</script>

<template>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

  <div class="toast-container position-fixed top-0 end-0 p-4" style="z-index: 10000;">
    <div v-if="store.toast" class="toast show align-items-center text-white border-0 shadow-lg fade-in" 
         :class="`bg-${store.toast.type}`" role="alert">
      <div class="d-flex px-1 py-1">
        <div class="toast-body fw-bold fs-6">
           {{ store.toast.type === 'success' ? '✅' : '⚠️' }} {{ store.toast.message }}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" @click="store.toast = null"></button>
      </div>
    </div>
  </div>
  
  <LoginView v-if="store.currentPhase === 'login'" />

  <AdmissionScreen v-else-if="store.currentPhase === 'admission'" @enter-game="handleEnterGame" />

  <div v-else-if="store.currentPhase === 'loading'" class="vh-100 d-flex flex-column justify-content-center align-items-center bg-light">
    <div class="spinner-border text-primary mb-3" style="width: 3rem; height: 3rem;" role="status"></div>
    <h4 class="text-muted">正在连接「zdbk」...</h4>
    <div v-if="!isConnected" class="text-danger small mt-2">（如果长时间卡住，请尝试刷新页面）</div>
  </div>

  <div v-else-if="store.currentPhase === 'playing'" class="container-fluid px-4 mt-4 fade-in-up">

    <TopNav @send-action="send" />
    
    <HudBar />
    <div class="row">
      <div class="col-md-3">
        <div class="card mb-3 border-0 shadow-sm h-100">
          <div class="card-header bg-info text-white text-center fw-bold py-2">📚 学在折大</div>
          <div class="card-body p-0">
            <CourseList @send-action="send" />
          </div>
        </div>
      </div>
      <div class="col-md-6">
        <MidPanel @send-action="send" />
      </div>
      <div class="col-md-3">
        <RightPanel @send-action="send" />
      </div>
    </div>

    <TranscriptModal @send-action="send" />
    <RandomEventModal @send-action="send" />
    <ExitConfirmModal @send-action="send" />

  </div>

  <EndScreen v-else-if="store.currentPhase === 'ended'" />

</template>

<style>
/* 增加 Toast 进场动画 */
.toast-container .fade-in {
  animation: slideInRight 0.3s ease-out forwards;
}
@keyframes slideInRight {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
</style>

<style>
/* 全局样式 */
body {
  background-color: #f0f2f5;
}
.fade-in-up {
  animation: fadeInUp 0.5s ease-out forwards;
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>