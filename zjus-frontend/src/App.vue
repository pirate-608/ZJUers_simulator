<template>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  
  <div class="container-fluid px-4 mt-4">
    <HudBar />

    <div class="row">
      
      <div class="col-md-3">
        <div class="card mb-3 border-0 shadow-sm">
          <div class="card-header bg-info text-white">📚 学在折大</div>
          <div class="card-body p-2 text-center text-muted">
            <CourseList @send-action="send" />
          </div>
        </div>
      </div>

      <div class="col-md-6">
        <MidPanel @send-action="send" />
      </div>

      <div class="col-md-3">
        <div class="card mb-3 border-0 shadow-sm text-center p-4 text-muted">
           <RightPanel @send-action="send" />
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useGameStore } from './stores/gameStore'
import { useGameWebSocket } from './composables/useGameWebSocket'
import HudBar from './components/HudBar.vue'
import MidPanel from './components/MidPanel.vue' // 引入重命名后的中间面板
import RightPanel from './components/RightPanel.vue'
import CourseList from './components/CourseList.vue'

const store = useGameStore()
// 从 hook 中解构出 send 方法，方便直接传给子组件
const { connect, isConnected, send } = useGameWebSocket()

onMounted(() => {
  connect('test_token', 'ws://localhost:8000') 
})
</script>
