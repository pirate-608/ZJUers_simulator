<template>
  <div class="container py-5 vh-100 d-flex justify-content-center align-items-center relative">
    <div class="col-md-8 col-lg-6 w-100">
      <div class="card shadow-lg border-0 rounded-3">
        <div class="card-header bg-primary text-white text-center py-4">
          <h2 class="mb-0">🎓 ZJUers Simulator</h2>
          <p class="mb-0 opacity-75">入学资格审查</p>
        </div>

        <div class="card-body p-4 p-md-5">
          
          <!-- 状态 1：登录表单 -->
          <div v-if="viewState === 'login'">
            <div class="mb-3">
              <label class="form-label fw-bold">请输入你的姓名/昵称</label>
              <input v-model="form.username" type="text" class="form-control form-control-lg" placeholder="灿若星辰的折大人...">
            </div>
            
            <div class="mb-3">
              <label class="form-label fw-bold">学生凭证 <span class="text-muted fw-normal">(可选，老玩家免试登录)</span></label>
              <input v-model="form.token" type="text" class="form-control" placeholder="如有请粘贴，否则留空">
            </div>

            <!-- 自定义 LLM 配置区 -->
            <div class="form-check form-switch mb-2">
              <input v-model="form.useCustomLlm" class="form-check-input" type="checkbox" id="llm-toggle">
              <label class="form-check-label" for="llm-toggle">使用自定义大模型（可选）</label>
            </div>
            
            <div v-if="form.useCustomLlm" class="card card-body border border-info bg-light mb-3">
              <div class="mb-2">
                <label class="form-label small fw-bold">模型代号</label>
                <input v-model="form.llmModel" type="text" class="form-control form-control-sm" placeholder="如: gpt-4o-mini">
              </div>
              <div class="mb-2">
                <label class="form-label small fw-bold">API Key</label>
                <input v-model="form.llmKey" type="password" class="form-control form-control-sm" placeholder="仅在本地会话中使用">
              </div>
            </div>

            <div class="d-grid gap-2 mt-4">
              <button class="btn btn-primary btn-lg fw-bold" :disabled="!form.username && !form.token" @click="handleAction('exam')">
                📝 开始入学考试
              </button>
              <button class="btn btn-outline-success btn-lg fw-bold" :disabled="!form.token" @click="handleAction('quick')">
                🚀 直接报到 (老玩家免试)
              </button>
            </div>
          </div>

          <!-- 状态 2：考试答题界面 -->
          <div v-else-if="viewState === 'exam'">
            <h5 class="text-center mb-4 text-danger fw-bold">请回答以下问题 (及格分: 60)</h5>
            <div v-for="(q, index) in examQuestions" :key="index" class="mb-4">
              <p class="fw-bold mb-2">{{ index + 1 }}. {{ q.content }}</p>
              <div v-for="option in q.options" :key="option" class="form-check">
                <input class="form-check-input" type="radio" :name="'question_'+index" :value="option" v-model="examAnswers[index]">
                <label class="form-check-label">{{ option }}</label>
              </div>
            </div>
            <div class="d-flex gap-2 mt-4">
              <button class="btn btn-secondary w-25" @click="viewState = 'login'">返回</button>
              <button class="btn btn-success w-75 fw-bold" :disabled="!allQuestionsAnswered" @click="submitExam">
                提交试卷
              </button>
            </div>
          </div>

          <!-- 状态 3：加载中 -->
          <div v-else-if="viewState === 'loading'" class="text-center py-5">
            <div class="spinner-border text-primary mb-3" style="width: 3rem; height: 3rem;" role="status"></div>
            <h5 class="text-muted">{{ loadingText }}</h5>
          </div>

        </div>
      </div>
    </div>

    <!-- 🌟 修复：安全政策确认弹窗 -->
    <div v-if="showLlmWarning" class="modal-backdrop-custom d-flex justify-content-center align-items-center">
      <div class="card shadow-lg border-0 p-4 mx-3" style="max-width: 500px;">
        <h4 class="text-danger fw-bold mb-3">⚠️ 安全政策确认</h4>
        <p class="mb-2">你正在使用自定义的 LLM API Key。</p>
        <ul class="text-muted small">
          <li>你的 API Key 仅在当前浏览器内存和本次后端的临时会话中使用。</li>
          <li>游戏绝不会将你的密钥持久化存储到数据库。</li>
          <li>关闭浏览器后配置即失效，游戏可能面临模型回退。</li>
        </ul>
        <div class="d-flex justify-content-end gap-2 mt-4">
          <button class="btn btn-secondary" @click="cancelLlmAction">返回修改</button>
          <button class="btn btn-danger fw-bold" @click="confirmLlmAction">我已知晓并同意</button>
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
  llmModel: '',
  llmKey: ''
})

const examQuestions = ref([])
const examAnswers = ref({})

const allQuestionsAnswered = computed(() => {
  if (examQuestions.value.length === 0) return false
  return Object.keys(examAnswers.value).length === examQuestions.value.length
})

// === 弹窗状态管理 ===
const showLlmWarning = ref(false)
const pendingAction = ref(null) // 'exam' 或 'quick'

const handleAction = (actionType) => {
  if (form.useCustomLlm && form.llmKey.trim() !== '') {
    pendingAction.value = actionType
    showLlmWarning.value = true // 拦截并展示弹窗
  } else {
    // 没填密钥则直接放行
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

// ----------------- API 交互逻辑 -----------------

// 1. 获取考题 (修复 API 路径和方法)
const startExam = async () => {
  viewState.value = 'loading'
  loadingText.value = '正在为您生成专属考卷...'
  
  try {
    const response = await fetch('/api/exam/generate', { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: form.username })
    })
    const data = await response.json()
    
    examQuestions.value = data.questions || []
    examAnswers.value = {}
    viewState.value = 'exam'

  } catch (error) {
    alert('获取考卷失败，请检查网络！')
    viewState.value = 'login'
  }
}

// 2. 提交考卷
const submitExam = async () => {
  viewState.value = 'loading'
  loadingText.value = '正在由 C 语言判卷系统阅卷中...'

  try {
    const payload = { 
      username: form.username,
      answers: examAnswers.value,
      custom_llm_model: form.useCustomLlm ? form.llmModel : null,
      custom_llm_api_key: form.useCustomLlm ? form.llmKey : null
    }

    const response = await fetch('/api/exam/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await response.json()

    if (data.status === 'success') {
      saveTokenAndConfig(data.token)
      store.setPhase('admission') 
    } else {
      alert(`❌ 判卷结果：${data.message}`)
      viewState.value = 'login'
    }
  } catch (error) {
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
      // 如果没有填用户名，传 null，让后端从 Token 解析
      username: form.username || null,
      token: form.token,
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
      saveTokenAndConfig(data.token)
      store.setPhase('admission')
    } else {
      alert(`登录失败：${data.message}`)
      form.token = ''
      viewState.value = 'login'
    }
  } catch (error) {
    alert('验证失败，请重试。')
    viewState.value = 'login'
  }
}

const saveTokenAndConfig = (token) => {
  if (token) localStorage.setItem('zju_token', token)
  
  if (form.useCustomLlm && form.llmKey) {
    sessionStorage.setItem('custom_llm_model', form.llmModel)
    sessionStorage.setItem('custom_llm_key', form.llmKey)
  } else {
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
</style>