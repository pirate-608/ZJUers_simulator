<template>
  <div v-if="store.activeModal === 'exit_confirm'" 
       class="modal-backdrop-custom d-flex justify-content-center align-items-center fade-in">
    
    <div class="card shadow-lg border-0 modal-card scale-in" style="width: 90%; max-width: 420px;">
      
      <div class="card-header bg-danger text-white py-3 text-center">
        <h5 class="mb-0 fw-bold">⚠️ 确认退出游戏</h5>
      </div>

      <div class="card-body p-4 text-center">
        <!-- 退出保存的等待状态 UI -->
        <div v-if="store.isPendingExit">
           <div class="spinner-border text-success mb-3" role="status"></div>
           <p class="fs-6 mb-0">正在将数据持久化到服务器...</p>
        </div>
        <!-- 默认确认提示 UI -->
        <div v-else>
            <p class="fs-6 mb-2">你要结束这段折大生涯了吗？</p>
            <p class="small text-muted mb-0">如果你直接退出，<span class="text-danger fw-bold">未保存的进度将会永久丢失！</span></p>
        </div>
      </div>

      <div class="card-footer bg-light border-0 py-3 d-flex justify-content-between gap-2 px-4">
        <button class="btn btn-outline-secondary px-3" :disabled="store.isPendingExit" @click="store.closeModal()">
          点错了 (取消)
        </button>
        <div class="d-flex gap-2">
          <button class="btn btn-danger px-3" :disabled="store.isPendingExit" @click="exitWithoutSave">
            直接退出
          </button>
          <button class="btn btn-success fw-bold px-3 shadow-sm" :disabled="store.isPendingExit" @click="saveAndExit">
            {{ store.isPendingExit ? '保存中...' : '保存并退出' }}
          </button>
        </div>
      </div>
      
    </div>
  </div>
</template>

<script setup>
import { useGameStore } from '../../stores/gameStore'

const store = useGameStore()
const emit = defineEmits(['send-action'])

const exitWithoutSave = () => {
  store.closeModal()
  // 直接销毁 Token 并强刷网页，断开的 WS 会让后端自动清理连接
  localStorage.removeItem('zju_token')
  window.location.reload()
}

const saveAndExit = () => {
  // 🌟 修复：不再使用 setTimeout，而是设置等待标记，发送保存指令
  // 配合 useGameWebSocket.js 里的 save_result 拦截，实现完美闭环
  store.isPendingExit = true
  emit('send-action', { action: 'save_game' })
}
</script>

<style scoped>
.modal-backdrop-custom {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  background-color: rgba(0, 0, 0, 0.65); z-index: 9999; backdrop-filter: blur(3px);
}
.fade-in { animation: fadeIn 0.2s ease-out; }
.scale-in { animation: scaleIn 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes scaleIn { from { transform: scale(0.9); opacity: 0; } to { transform: scale(1); opacity: 1; } }
</style>