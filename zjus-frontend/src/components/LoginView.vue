<template>
  <div class="container py-5 vh-100 d-flex justify-content-center align-items-center">
    <div class="col-md-8 col-lg-6 w-100">
      <div class="card shadow-lg border-0 rounded-3">
        <div class="card-header bg-primary text-white text-center py-4">
          <h2 class="mb-0">🎓 ZJUers 模拟器</h2>
          <p class="mb-0 opacity-75">入学资格审查</p>
        </div>

        <div class="card-body p-4 p-md-5">
          
          <div v-if="viewState === 'login'">
            <div class="mb-3">
              <label class="form-label fw-bold">请输入你的姓名/昵称</label>
              <input v-model="form.username" type="text" class="form-control form-control-lg" placeholder="灿若星辰的折大人...">
            </div>
            
            <div class="mb-3">
              <label class="form-label fw-bold">学生凭证 <span class="text-muted fw-normal">(可选，老玩家免试登录)</span></label>
              <input v-model="form.token" type="text" class="form-control" placeholder="如有请粘贴，否则留空">
            </div>

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
              <p class="text-muted mb-0" style="font-size: 0.75rem;">
                如填写 API Key，则视为授权在本次会话内使用，平台不会存储你的密钥。
              </p>
            </div>

            <div class="d-grid gap-2 mt-4">
              <button class="btn btn-primary btn-lg fw-bold" :disabled="!form.username && !form.token" @click="startExam">
                📝 开始入学考试
              </button>
              <button class="btn btn-outline-success btn-lg fw-bold" :disabled="!form.token" @click="quickLogin">
                🚀 直接报到 (老玩家免试)
              </button>
            </div>
          </div>

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

          <div v-else-if="viewState === 'loading'" class="text-center py-5">
            <div class="spinner-border text-primary mb-3" style="width: 3rem; height: 3rem;" role="status"></div>
            <h5 class="text-muted">{{ loadingText }}</h5>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useGameStore } from '../stores/gameStore'

const store = useGameStore()

// 视图状态机：'login' -> 'exam' -> 'loading'
const viewState = ref('login')
const loadingText = ref('正在连接服务器...')

// 表单数据
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

// ----------------- 真实 API 交互逻辑 -----------------

// 1. 获取考题 (对应: GET /api/exam/questions)
const startExam = async () => {
  viewState.value = 'loading'
  loadingText.value = '正在为您生成专属考卷...'
  
  try {
    const response = await fetch('/api/exam/questions')
    const data = await response.json()
    
    examQuestions.value = data
    examAnswers.value = {}
    viewState.value = 'exam'

  } catch (error) {
    alert('获取考卷失败，请检查网络！')
    viewState.value = 'login'
  }
}

// 2. 提交考卷进行判卷 (对应: POST /api/exam/submit)
const submitExam = async () => {
  viewState.value = 'loading'
  loadingText.value = '正在由 C 语言判卷系统阅卷中...'

  try {
    const payload = { 
      username: form.username,
      answers: examAnswers.value,
      // 如果用户勾选了自定义大模型，则传过去
      custom_llm_model: form.useCustomLlm ? form.llmModel : null,
      custom_llm_api_key: form.useCustomLlm ? form.llmKey : null
    }

    const response = await fetch('/api/exam/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await response.json()

    // 后端返回的结构包含 status: "success" 或 "failed" / "error"
    if (data.status === 'success') {
      saveTokenAndConfig(data.token)
      alert(`🎉 恭喜及格！专业大类：${data.tier}，得分：${data.score}`)
      store.setPhase('admission') 
    } else {
      alert(`❌ 判卷结果：${data.message} ${data.score ? '(得分:'+data.score+')' : ''}`)
      viewState.value = 'login'
    }
  } catch (error) {
    alert('判卷请求失败，请联系管理员！')
    viewState.value = 'login'
  }
}

// 3. 老玩家凭 Token/用户名 免试登录 (对应: POST /api/exam/quick_login)
const quickLogin = async () => {
  if (!form.username) {
    alert('免试登录也需要填写你的姓名/昵称！')
    return
  }

  viewState.value = 'loading'
  loadingText.value = '正在验证学生凭证...'

  try {
    const payload = {
      username: form.username,
      token: form.token || null,
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
      // 验证成功，直接切场景去录取通知书
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

// 辅助方法：保存 Token 和 LLM 配置到 LocalStorage/SessionStorage
const saveTokenAndConfig = (token) => {
  if (token) {
    localStorage.setItem('zju_token', token)
  }
  if (form.useCustomLlm && form.llmKey) {
    sessionStorage.setItem('custom_llm_model', form.llmModel)
    sessionStorage.setItem('custom_llm_key', form.llmKey)
  }
}
</script>