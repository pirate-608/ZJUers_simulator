<template>
  <div
    class="end-screen vh-100 w-100 d-flex flex-column align-items-center justify-content-center"
    :class="isSuccess ? 'bg-grad' : 'bg-dark text-white'"
  >
    <div
      v-if="!isSuccess"
      class="center-box fade-in-up text-center"
    >
      <h2
        class="mb-4 fw-light text-light"
        style="letter-spacing: 2px; line-height: 1.6;"
      >
        很多年后，我才明白，<br>我也许只属于灿烂星辰背后的那片黑夜......
      </h2>
      <div class="text-danger mb-4 fs-5 fw-bold">
        【退学原因】：{{ store.endData.reason || '你在求是园中迷失了自我' }}
      </div>
      
      <button
        class="btn btn-outline-light btn-lg mt-4 px-5 rounded-pill pulse-btn"
        @click="restartGame"
      >
        🔄 恍如隔世 (重新开始)
      </button>
    </div>

    <div
      v-else
      class="container fade-in-up my-auto"
    >
      <div class="row justify-content-center">
        <div class="col-lg-8 col-md-10">
          <div class="card shadow-lg border-0 bg-white rounded-4 overflow-hidden">
            <div
              class="card-header text-white text-center py-4"
              style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);"
            >
              <h1 class="mb-0 fw-bold">
                🎓 毕业典礼
              </h1>
              <p class="mb-0 mt-2 opacity-75">
                求是鹰飞，灿若星辰
              </p>
            </div>

            <div class="card-body p-4 p-md-5">
              <div class="row text-center mb-4 pb-4 border-bottom">
                <div class="col-6 col-md-3 mb-3 mb-md-0">
                  <div class="text-muted small fw-bold">
                    最终 GPA
                  </div>
                  <div class="fs-2 fw-bold text-primary">
                    {{ store.endData.gpa?.toFixed(2) ?? '0.00' }}
                  </div>
                </div>
                <div class="col-6 col-md-3 border-md-start border-md-end mb-3 mb-md-0">
                  <div class="text-muted small fw-bold">
                    智商 / 情商
                  </div>
                  <div class="fs-4 fw-bold text-success">
                    {{ store.endData.iq ?? 100 }} / {{ store.endData.eq ?? 100 }}
                  </div>
                </div>
                <div class="col-6 col-md-3 border-md-end">
                  <div class="text-muted small fw-bold">
                    累计财富
                  </div>
                  <div class="fs-4 fw-bold text-warning">
                    {{ store.endData.gold ?? 0 }} 💰
                  </div>
                </div>
                <div class="col-6 col-md-3">
                  <div class="text-muted small fw-bold">
                    解锁成就
                  </div>
                  <div class="fs-4 fw-bold text-info">
                    {{ store.endData.achievements_count ?? 0 }} 个
                  </div>
                </div>
              </div>

              <h5 class="fw-bold text-secondary mb-3 d-flex align-items-center gap-2">
                <span>📜</span> 校史公曰：
              </h5>
              <div
                class="ai-summary-box p-4 rounded bg-light border"
                style="min-height: 120px;"
              >
                <p
                  class="mb-0 text-dark fs-5"
                  style="font-family: 'Kaiti', 'STKaiti', serif; line-height: 1.8;"
                >
                  {{ typedText }}<span
                    v-if="isTyping"
                    class="cursor-blink"
                  >|</span>
                </p>
              </div>
            </div>
            
            <div class="card-footer bg-light border-0 py-4 text-center">
              <button
                class="btn btn-primary btn-lg px-5 rounded-pill shadow fw-bold pulse-btn" 
                :disabled="isTyping"
                @click="restartGame"
              >
                🔄 重返大一 (再来一局)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div
      class="world-links mt-5 text-center fade-in-up"
      style="animation-delay: 1s;"
    >
      <div
        class="small mb-2"
        :class="isSuccess ? 'text-muted' : 'text-secondary'"
      >
        世界观与开发者指南：
      </div>
      <div class="d-flex flex-wrap justify-content-center gap-2">
        <a
          href="https://zjusim-docs.67656.fun/user/rules/"
          target="_blank"
          class="btn btn-outline-secondary btn-sm rounded-pill"
        >折大校规</a>
        <a
          href="https://zjusim-docs.67656.fun/world/keywords/"
          target="_blank"
          class="btn btn-outline-secondary btn-sm rounded-pill"
        >关键词表</a>
        <a
          href="https://zjusim-docs.67656.fun/world/majors/"
          target="_blank"
          class="btn btn-outline-secondary btn-sm rounded-pill"
        >专业列表</a>
        <a
          href="https://zjusim-docs.67656.fun/world/achievements/"
          target="_blank"
          class="btn btn-outline-secondary btn-sm rounded-pill"
        >成就配置</a>
        <a
          href="https://zjusim-docs.67656.fun/world/courses/"
          target="_blank"
          class="btn btn-outline-secondary btn-sm rounded-pill"
        >课程数据</a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { WsClientAction } from '@/types/websocket'

const store = useGameStore()
const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
}>()
// 判断是否是好结局
const isSuccess = computed(() => store.endType === 'graduation')

// 打字机特效状态
const typedText = ref('')
const isTyping = ref(false)

onMounted(() => {
  if (isSuccess.value) {
    // 假设后端传过来的 AI 文言文存在 llm_summary 字段里
    const fullText = store.endData.llm_summary || "此子聪颖过人，勤勉有加。求是园中四载，风华正茂，未来可期。前程似锦，望珍重！"
    startTypewriter(fullText)
  }
})

// 打字机特效函数
const startTypewriter = (text: string) => {
  isTyping.value = true
  let i = 0
  typedText.value = ''
  
  const timer = setInterval(() => {
    if (i < text.length) {
      typedText.value += text.charAt(i)
      i++
    } else {
      clearInterval(timer)
      isTyping.value = false
    }
  }, 50) // 每 50ms 吐出一个字
}

// 重新开始游戏逻辑
const restartGame = () => {
  // 发送重开指令
  emit('send-action', { action: 'restart' })
}
</script>

<style scoped>
/* 渐变背景 (好结局) */
.bg-grad {
  background: linear-gradient(120deg, #fdfbfb 0%, #ebedee 100%);
}

/* 坏结局的暗黑居中框 (还原 end.html) */
.center-box {
  max-width: 600px;
  padding: 40px;
  background: rgba(17, 17, 17, 0.8);
  border-radius: 12px;
  box-shadow: 0 2px 24px rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(5px);
}

/* 动画特效 */
.fade-in-up {
  animation: fadeInUp 0.8s ease-out forwards;
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 打字机光标闪烁 */
.cursor-blink {
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}

/* 按钮呼吸 */
.pulse-btn {
  transition: transform 0.2s;
}
.pulse-btn:hover {
  transform: scale(1.05);
}

.world-links a {
  text-decoration: none;
  backdrop-filter: blur(2px);
}
</style>