<template>
  <!-- 背景淡入淡出层 -->
  <div
    class="bg-fade"
    :style="{ backgroundImage: `url('${bgImages[bgIndex]}')`, opacity: bgOpacity }"
  />
  <div class="container py-5">
    <div class="col-md-8 col-lg-6 w-100">
      <div class="card shadow-lg border-0 rounded-3">
        <div class="card-header bg-primary text-white text-center py-4">
          <h2 class="mb-0">
            🎓 ZJUers Simulator
          </h2>
          <p class="mb-0 opacity-75">
            入学资格审查
          </p>
        </div>

        <div class="card-body p-4 p-md-5">
          <!-- 状态 1：登录表单 -->
          <div v-if="viewState === 'login'">
            <div class="mb-3">
              <label class="form-label fw-bold">请输入你的姓名/昵称</label>
              <input
                v-model="form.username"
                type="text"
                class="form-control form-control-lg"
                placeholder="灿若星辰的折大人..."
              >
            </div>
            
            <div class="mb-3">
              <label class="form-label fw-bold">学生凭证 <span class="text-muted fw-normal">(可选，老玩家免试登录)</span></label>
              <input
                v-model="form.token"
                type="text"
                class="form-control"
                placeholder="如有请粘贴，否则留空"
              >
            </div>

            <div class="d-flex justify-content-between align-items-center mb-2">
              <div class="form-check form-switch">
                <input
                  id="llm-toggle"
                  v-model="form.useCustomLlm"
                  class="form-check-input"
                  type="checkbox"
                >
                <label
                  class="form-check-label"
                  for="llm-toggle"
                >使用自定义大模型（可选）</label>
              </div>
              <a
                href="https://zjusim-docs.67656.fun/user/models"
                target="_blank"
                class="text-decoration-none small text-primary"
              >
                <i class="bi bi-info-circle" /> 关于模型配置
              </a>
            </div>
            
            <div
              v-if="form.useCustomLlm"
              class="card card-body border border-info bg-light mb-3"
            >
              <div class="mb-2">
                <label class="form-label small fw-bold">服务商</label>
                <select
                  v-model="form.llmProvider"
                  class="form-select form-select-sm"
                >
                  <option value="openai">
                    OpenAI (默认)
                  </option>
                  <option value="deepseek">
                    DeepSeek
                  </option>
                  <option value="qwen">
                    阿里通义千问 (Qwen)
                  </option>
                  <option value="glm">
                    智谱清言 (GLM)
                  </option>
                  <option value="moonshot">
                    月之暗面 (Kimi)
                  </option>
                  <option value="minimax">
                    MiniMax
                  </option>
                </select>
              </div>
              <div class="mb-2">
                <label class="form-label small fw-bold">模型代号</label>
                <input
                  v-model="form.llmModel"
                  type="text"
                  class="form-control form-control-sm"
                  placeholder="如: gpt-4o-mini 或 deepseek-chat"
                >
              </div>
              <div class="mb-2">
                <label class="form-label small fw-bold">API Key</label>
                <input
                  v-model="form.llmKey"
                  type="password"
                  class="form-control form-control-sm"
                  placeholder="仅在本地会话中使用"
                >
              </div>
            </div>

            <div class="d-grid gap-2 mt-4">
              <button
                class="btn btn-primary btn-lg fw-bold"
                :disabled="!form.username && !form.token"
                @click="handleAction('exam')"
              >
                📝 开始入学考试
              </button>
              <button
                class="btn btn-outline-success btn-lg fw-bold"
                :disabled="!form.token"
                @click="handleAction('quick')"
              >
                🚀 直接报到 (老玩家免试)
              </button>
            </div>
          </div>

          <!-- 状态 2：考试答题界面 -->
          <div v-else-if="viewState === 'exam'">
            <h5 class="text-center mb-4 text-danger fw-bold">
              请回答以下问题 (及格分: 60)
            </h5>
            
            <div
              v-for="(q, index) in examQuestions"
              :key="index"
              class="mb-4"
            >
              <!-- 兼容 json 中的 content 字段 -->
              <label class="form-label fw-bold mb-2">{{ index + 1 }}. {{ q.content || q.question }}</label>
              <input
                v-model="examAnswers[index]"
                type="text" 
                class="form-control form-control-lg bg-light" 
                placeholder="请输入你的答案..."
              >
            </div>
            
            <div class="d-flex gap-2 mt-4">
              <button
                class="btn btn-secondary w-25"
                @click="viewState = 'login'"
              >
                返回
              </button>
              <button
                class="btn btn-success w-75 fw-bold"
                :disabled="!allQuestionsAnswered"
                @click="submitExam"
              >
                提交试卷
              </button>
            </div>
          </div>

          <!-- 状态 3：加载中 -->
          <div
            v-else-if="viewState === 'loading'"
            class="text-center py-5"
          >
            <div
              class="spinner-border text-primary mb-3"
              style="width: 3rem; height: 3rem;"
              role="status"
            />
            <h5 class="text-muted">
              {{ loadingText }}
            </h5>
          </div>
        </div>
      </div>
    </div>

    <!-- 安全政策确认弹窗 -->
    <div
      v-if="showLlmWarning"
      class="modal-backdrop-custom d-flex justify-content-center align-items-center"
    >
      <div
        class="card shadow-lg border-0 p-4 mx-3"
        style="max-width: 500px;"
      >
        <h4 class="text-danger fw-bold mb-3">
          ⚠️ 安全政策确认
        </h4>
        <p class="mb-2">
          你正在使用自定义的 LLM API Key。
        </p>
        <ul class="text-muted small">
          <li>你的 API Key 仅在当前浏览器内存和本次后端的临时会话中使用。</li>
          <li>游戏绝不会将你的密钥持久化存储到数据库。</li>
          <li>关闭浏览器后配置即失效，游戏可能面临模型回退。</li>
          <li>阅读<a href="https://zjusim-docs.67656.fun/user/models/#security-notice">安全须知</a></li>
        </ul>
        <div class="d-flex justify-content-end gap-2 mt-4">
          <button
            class="btn btn-secondary"
            @click="cancelLlmAction"
          >
            返回修改
          </button>
          <button
            class="btn btn-danger fw-bold"
            @click="confirmLlmAction"
          >
            我已知晓并同意
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useGameStore } from '../stores/gameStore'

const store = useGameStore()

const viewState = ref('login')
const loadingText = ref('正在连接服务器...')

const form = reactive({
  username: '',
  token: '',
  useCustomLlm: false,
  llmProvider: 'openai',
  llmModel: '',
  llmKey: ''
})

const examQuestions = ref([])
const examAnswers = ref({})

const allQuestionsAnswered = computed(() => {
  if (examQuestions.value.length === 0) return false
  for (let i = 0; i < examQuestions.value.length; i++) {
    if (!examAnswers.value[i] || examAnswers.value[i].trim() === '') {
      return false
    }
  }
  return true
})

// === 弹窗状态管理 ===
const showLlmWarning = ref(false)
const pendingAction = ref(null) 

const handleAction = (actionType) => {
  if (form.useCustomLlm && form.llmKey.trim() !== '') {
    pendingAction.value = actionType
    showLlmWarning.value = true 
  } else {
    executeAction(actionType)
  }
}

const cancelLlmAction = () => {
  showLlmWarning.value = false
  pendingAction.value = null
}

const confirmLlmAction = () => {
  showLlmWarning.value = false
  executeAction(pendingAction.value)
}

const executeAction = (actionType) => {
  if (actionType === 'exam') startExam()
  else if (actionType === 'quick') quickLogin()
}

const bgImages = [
  '/images/qiushimen.webp',
  '/images/zjg_night.jpeg',
  '/images/zjg_autumn.jpg',
  '/images/qizhen_lake.jpg',
]
const bgIndex = ref(0)
const bgOpacity = ref(1)

const fadeDuration = 800 // ms
const switchBg = () => {
  bgOpacity.value = 0
  setTimeout(() => {
    bgIndex.value = (bgIndex.value + 1) % bgImages.length
    bgOpacity.value = 1
  }, fadeDuration)
}
// 初始设置
setTimeout(() => switchBg(), 10000)
setInterval(switchBg, 10000)

// ----------------- API 交互逻辑 -----------------

const startExam = async () => {
  viewState.value = 'loading'
  loadingText.value = '正在为您生成专属考卷...'
  
  try {
    const response = await fetch('/api/exam/questions', { method: 'GET' })
    if (!response.ok) throw new Error('网络响应异常')
    
    const data = await response.json()
    examQuestions.value = data.questions || data || []
    examAnswers.value = {}
    viewState.value = 'exam'

  } catch (error) {
    console.error("Fetch exam error:", error)
    alert('获取考卷失败，请检查网络！')
  }
}
// 2. 提交考卷
const submitExam = async () => {
  viewState.value = 'loading'
  loadingText.value = '正在由 C 语言判卷系统阅卷中...'

  try {
    const formattedAnswers = {}
    examQuestions.value.forEach((q, index) => {
      const ans = examAnswers.value[index] || "";
      const questionId = String(q.id !== undefined ? q.id : index + 1);
      formattedAnswers[questionId] = ans.trim();
    });

    const payload = { 
      username: form.username.trim(),
      answers: formattedAnswers
    }

    if (form.useCustomLlm) {
      if (form.llmProvider) payload.custom_llm_provider = form.llmProvider;
      if (form.llmModel) payload.custom_llm_model = form.llmModel.trim();
      if (form.llmKey) payload.custom_llm_api_key = form.llmKey.trim();
    }

    const response = await fetch('/api/exam/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (response.status === 422) {
      const errData = await response.json();
      console.error("422 Error:", errData.detail);
      alert('参数校验失败，请检查输入格式！');
      viewState.value = 'login';
      return;
    }

    if (!response.ok) throw new Error(`HTTP 异常: ${response.status}`);

    const data = await response.json()

    if (data.status === 'success') {
      // 🌟 修复：同时保存 Token 和真实的玩家姓名
      saveTokenAndConfig(data.token, form.username.trim())
      store.setPhase('admission') 
    } else {
      alert(`❌ 判卷结果：${data.message}`)
      viewState.value = 'login'
    }
  } catch (error) {
    console.error("Submit Exception:", error);
    alert('判卷请求失败，请联系管理员！')
    viewState.value = 'login'
  }
}

// 3. 快速登录
const quickLogin = async () => {
  viewState.value = 'loading'
  loadingText.value = '正在验证学生凭证...'

  try {
    const payload = {
      // 🌟 修复：后端 Pydantic 强制要求传入 username(str)，不能传 null
      username: form.username.trim() || localStorage.getItem('zju_username') || "折大人",
      token: form.token,
      custom_llm_provider: form.useCustomLlm ? form.llmProvider : null,
      custom_llm_model: form.useCustomLlm ? form.llmModel : null,
      custom_llm_api_key: form.useCustomLlm ? form.llmKey : null
    }

    const response = await fetch('/api/exam/quick_login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await response.json()

    if (data.status === 'success') {
      // 🌟 修复：同时保存 Token 和真实的玩家姓名
      saveTokenAndConfig(data.token, payload.username)
      store.setPhase('admission')
    } else {
      alert(`登录失败：${data.message}`)
      form.token = ''
      viewState.value = 'login'
    }
  } catch {
    alert('验证失败，请重试。')
    viewState.value = 'login'
  }
}

// 🌟 修复：增加 username 参数并存入 localStorage
const saveTokenAndConfig = (token, username) => {
  if (token) localStorage.setItem('zju_token', token)
  if (username) localStorage.setItem('zju_username', username)
  
  if (form.useCustomLlm && form.llmKey) {
    sessionStorage.setItem('custom_llm_provider', form.llmProvider)
    sessionStorage.setItem('custom_llm_model', form.llmModel)
    sessionStorage.setItem('custom_llm_key', form.llmKey)
  } else {
    sessionStorage.removeItem('custom_llm_provider')
    sessionStorage.removeItem('custom_llm_model')
    sessionStorage.removeItem('custom_llm_key')
  }
}
</script>

<style scoped>
.modal-backdrop-custom {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  background-color: rgba(0, 0, 0, 0.65); z-index: 9999; backdrop-filter: blur(3px);
}
/* 背景淡入淡出层 */
.bg-fade {
  position: fixed;
  top: 0; left: 0; width: 100vw; height: 100vh;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  z-index: -1;
  transition: opacity 0.8s;
}
</style>

