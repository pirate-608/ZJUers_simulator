<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore.ts'
import { useGameWebSocket } from '@/composables/useGameWebSocket.ts'
import { useGameGuide } from '@/composables/useGameGuide.ts'
import { PROLOGUE_SEEN_STORAGE_KEY } from '@/data/prologue'
import PrologueScene from './components/PrologueScene.vue'
import LoginView from './components/LoginView.vue'
import SaveSelect from './components/SaveSelect.vue'
import CharacterCreate from './components/CharacterCreate.vue'
import HudBar from './components/HudBar.vue'
import MidPanel from './components/MidPanel.vue'
import RightPanel from './components/RightPanel.vue'
import CourseList from './components/CourseList.vue'
import TranscriptModal from './components/modals/TranscriptModal.vue'
import RandomEventModal from './components/modals/RandomEventModal.vue'
import FeedbackModal from './components/modals/FeedbackModal.vue'
import ExamConfirmModal from './components/modals/ExamConfirmModal.vue'
import TopNav from './components/TopNav.vue'
import ExitConfirmModal from './components/modals/ExitConfirmModal.vue'
import EndScreen from './components/EndScreen.vue'

const store = useGameStore()
// 将 connect 暴露出来
const { connect, isConnected, send } = useGameWebSocket()
const { startGuide } = useGameGuide()

const hasSeenPrologue = () => {
  try {
    return localStorage.getItem(PROLOGUE_SEEN_STORAGE_KEY) === '1'
  } catch {
    return true
  }
}

const markPrologueSeen = () => {
  try {
    localStorage.setItem(PROLOGUE_SEEN_STORAGE_KEY, '1')
  } catch {
    // localStorage can be unavailable in restricted browsers; the main flow should still continue.
  }
}

const isPrologueActive = ref(!hasSeenPrologue())
let hasBootstrappedEntry = false

// 首次进入 playing 阶段后触发引导
watch(
  () => [store.currentPhase, isConnected.value] as const,
  ([phase, connected]) => {
    if (phase === 'playing' && connected) {
      requestAnimationFrame(() => startGuide(send))
    }
  },
)

const bootstrapEntryFlow = () => {
  if (hasBootstrappedEntry) return
  hasBootstrappedEntry = true

  const storedJwt = localStorage.getItem('zju_jwt')
  if (storedJwt) localStorage.setItem('zju_token', storedJwt)

  let existingToken = localStorage.getItem('zju_token')
  if (!storedJwt && existingToken && existingToken.split('.').length !== 3) {
    localStorage.setItem('zju_user_token', existingToken)
    localStorage.removeItem('zju_token')
    existingToken = null
  }
  const gameStarted = localStorage.getItem('game_started')
  const savedChoices = localStorage.getItem('zju_saves')

  if (existingToken) {
    if (savedChoices && !gameStarted) {
      store.setPhase('save_select')
    } else if (gameStarted) {
      handleEnterGame()
    } else {
      store.setPhase('character_create')
    }
  } else {
    store.setPhase('login')
  }
}

const handlePrologueComplete = () => {
  markPrologueSeen()
  isPrologueActive.value = false
  bootstrapEntryFlow()
}

onMounted(() => {
  if (!isPrologueActive.value) {
    bootstrapEntryFlow()
  }
})

// 当 phase 变为 loading 时，连接 WebSocket
watch(
  () => store.currentPhase,
  (phase) => {
    if (phase === 'loading') {
      const token = localStorage.getItem('zju_token') || ''
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${wsProtocol}//${window.location.host}`
      connect(token, wsUrl)
    }
  },
)

const handleEnterGame = () => {
  store.setPhase('loading')
}
</script>

<template>
  <link
    href="https://cdn.bootcdn.net/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css"
    rel="stylesheet"
  >

  <PrologueScene
    v-if="isPrologueActive"
    @complete="handlePrologueComplete"
  />

  <template v-else>
    <div
      class="toast-container app-toast position-fixed top-0 end-0 p-4"
      style="z-index: 10000;"
    >
      <div
        v-if="store.toast"
        class="toast show align-items-center text-white border-0 shadow-lg fade-in" 
        :class="`bg-${store.toast.type}`"
        role="alert"
      >
        <div class="d-flex px-1 py-1">
          <div class="toast-body fw-bold fs-6">
            {{ store.toast.type === 'success' ? '✅' : '⚠️' }} {{ store.toast.message }}
          </div>
          <button
            type="button"
            class="btn-close btn-close-white me-2 m-auto"
            @click="store.toast = null"
          />
        </div>
      </div>
    </div>
    
    <LoginView v-if="store.currentPhase === 'login'" />

    <SaveSelect
      v-else-if="store.currentPhase === 'save_select'"
    />

    <CharacterCreate
      v-else-if="store.currentPhase === 'character_create'"
    />

    <div
      v-else-if="store.currentPhase === 'loading'"
      class="app-loading vh-100 d-flex flex-column justify-content-center align-items-center"
    >
      <div
        class="spinner-border text-primary mb-3"
        style="width: 3rem; height: 3rem;"
        role="status"
      />
      <h4 class="text-muted">
        正在连接「zdbk」...
      </h4>
      <div
        v-if="!isConnected"
        class="text-danger small mt-2"
      >
        （如果长时间卡住，请尝试刷新页面）
      </div>
    </div>

    <div
      v-else-if="store.currentPhase === 'playing'"
      class="container-fluid app-playing px-3 px-lg-4 py-3 py-lg-4 fade-in-up"
    >
      <TopNav @send-action="send" />
      
      <HudBar />
      <div class="row g-3 g-xl-4">
        <div class="col-12 col-lg-3">
          <div class="card app-console-panel app-course-panel mb-3 h-100">
            <div class="card-header app-panel-header text-center fw-bold py-2">
              学在折大
            </div>
            <div class="card-body p-0">
              <CourseList @send-action="send" />
            </div>
          </div>
        </div>
        <div class="col-12 col-lg-6">
          <MidPanel @send-action="send" />
        </div>
        <div class="col-12 col-lg-3">
          <RightPanel @send-action="send" />
        </div>
      </div>

      <TranscriptModal @send-action="send" />
      <RandomEventModal @send-action="send" />
      <FeedbackModal />
      <ExamConfirmModal @send-action="send" />
      <ExitConfirmModal @send-action="send" />
    </div>

    <EndScreen v-else-if="store.currentPhase === 'ended'" @send-action="send" />
  </template>
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
.app-loading {
  background: linear-gradient(160deg, #f8fbff 0%, #edf3f9 100%);
}

.app-playing {
  max-width: 1480px;
  margin: 0 auto;
  min-height: 100vh;
  position: relative;
  color: #172433;
}

.app-playing::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -1;
  background:
    linear-gradient(90deg, rgba(32, 72, 112, 0.045) 1px, transparent 1px),
    linear-gradient(180deg, rgba(32, 72, 112, 0.04) 1px, transparent 1px),
    linear-gradient(160deg, #eaf1f8 0%, #dce7f2 54%, #d2deeb 100%);
  background-size: 48px 48px, 48px 48px, auto;
}

.app-playing .card {
  border: 1px solid rgba(88, 111, 137, 0.22) !important;
  border-radius: 8px;
  background: rgba(251, 253, 255, 0.95);
  box-shadow: 0 16px 42px rgba(18, 44, 73, 0.13);
}

.app-playing .app-console-panel {
  overflow: hidden;
}

.app-playing .app-panel-header {
  background: linear-gradient(180deg, #18395d 0%, #234d78 100%) !important;
  color: #f3f8fc;
  border-bottom: 1px solid rgba(255, 255, 255, 0.18);
  font-size: 0.92rem;
  letter-spacing: 0.08em;
}

.app-playing .progress {
  height: 10px;
  background-color: #e6edf5 !important;
  border-radius: 999px;
  box-shadow: inset 0 1px 2px rgba(20, 43, 70, 0.1);
  overflow: hidden;
}

.app-playing .progress-bar {
  background-color: #426f9c;
}

.app-playing .bg-info {
  background-color: #4578a6 !important;
}

.app-playing .bg-success {
  background-color: #3f806e !important;
}

.app-playing .bg-warning {
  background-color: #c79a4b !important;
}

.app-playing .bg-danger {
  background-color: #9f4d52 !important;
}

.app-playing .text-primary {
  color: #285a87 !important;
}

.app-playing .text-success {
  color: #2f7767 !important;
}

.app-playing .text-warning {
  color: #9a6d25 !important;
}

.app-playing .text-info {
  color: #4578a6 !important;
}

.app-playing .text-danger {
  color: #94454c !important;
}

.app-playing .btn {
  border-radius: 6px;
}

.app-playing .btn-outline-secondary,
.app-playing .btn-outline-info,
.app-playing .btn-outline-success,
.app-playing .btn-outline-primary {
  color: #2c567d;
  border-color: #b9c8d8;
  background-color: rgba(248, 251, 255, 0.78);
}

.app-playing .btn-outline-secondary:hover,
.app-playing .btn-outline-info:hover,
.app-playing .btn-outline-success:hover,
.app-playing .btn-outline-primary:hover {
  color: #fff;
  background-color: #2f5f8c;
  border-color: #2f5f8c;
}

.app-playing .btn-secondary,
.app-playing .btn-primary,
.app-playing .btn-success {
  background: linear-gradient(180deg, #356894 0%, #244d76 100%) !important;
  border-color: #21486e !important;
}

.app-playing .btn-warning {
  color: #22384e !important;
  background: linear-gradient(180deg, #d7bd7b 0%, #b88a44 100%) !important;
  border-color: #a77b38 !important;
}

.app-playing .btn-danger {
  background: linear-gradient(180deg, #a7565b 0%, #824047 100%) !important;
  border-color: #793b42 !important;
}

.app-playing .btn:disabled {
  color: #8b9aaa !important;
  border-color: #d2dbe6 !important;
  background: #edf2f7 !important;
  opacity: 0.82;
}

.fade-in-up {
  animation: fadeInUp 0.5s ease-out forwards;
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 430px) {
  .app-toast {
    width: calc(100% - 12px);
    left: 6px;
    right: 6px;
    padding: 6px !important;
  }

  .app-toast .toast {
    width: 100%;
  }

  .app-playing {
    padding-top: 10px !important;
    padding-bottom: 14px !important;
  }
}
</style>
