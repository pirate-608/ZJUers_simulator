<template>
  <div class="login-root">
    <div
      class="bg-fade"
      :style="{ backgroundImage: `url('${bgImages[bgIndex]}')`, opacity: bgOpacity }"
    />

    <div class="login-shell container-fluid px-3 px-md-4 py-4 py-md-5">
      <div class="mx-auto login-card-wrap">
        <div class="card login-card border-0 overflow-hidden">
          <div class="card-header login-header text-white text-center py-4">
            <h2 class="mb-1 fw-bold">🎓 ZJUers Simulator</h2>
            <p class="mb-0 opacity-75">新生报到</p>
          </div>

          <div class="card-body p-4 p-md-5">
            <!-- 登录表单 -->
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
                <label class="form-label fw-bold">邀请码</label>
                <input
                  v-model="form.inviteCode"
                  type="text"
                  class="form-control form-control-lg"
                  placeholder="请输入入学邀请码"
                >
              </div>

              <div class="mb-3">
                <label class="form-label fw-bold">学生凭证 <span class="text-muted fw-normal">(可选，老玩家返校)</span></label>
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
                  <label class="form-check-label" for="llm-toggle">使用自定义大模型（可选）</label>
                </div>
                <a
                  href="https://zjusim-docs.67656.fun/user/models"
                  target="_blank"
                  class="text-decoration-none small text-primary"
                ><i class="bi bi-info-circle" /> 关于模型配置</a>
              </div>

              <div
                v-if="form.useCustomLlm"
                class="card card-body border border-info-subtle llm-config-box mb-3"
              >
                <div class="mb-2">
                  <label class="form-label small fw-bold">服务商</label>
                  <select v-model="form.llmProvider" class="form-select form-select-sm">
                    <option value="openai">OpenAI (默认)</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="qwen">阿里云百炼 (Qwen)</option>
                    <option value="glm">智谱 (GLM)</option>
                    <option value="moonshot">月之暗面 (Kimi)</option>
                    <option value="minimax">MiniMax</option>
                  </select>
                </div>
                <div class="mb-2">
                  <label class="form-label small fw-bold">模型代号</label>
                  <input v-model="form.llmModel" type="text" class="form-control form-control-sm" placeholder="如: gpt-4o-mini">
                </div>
                <div class="mb-2">
                  <label class="form-label small fw-bold">API Key</label>
                  <input v-model="form.llmKey" type="password" class="form-control form-control-sm" placeholder="仅在本地会话中使用">
                </div>
              </div>

              <div class="form-check form-switch mb-2">
                <input
                  id="rp-toggle"
                  v-model="form.useCustomRp"
                  class="form-check-input"
                  type="checkbox"
                >
                <label class="form-check-label" for="rp-toggle">钉钉私聊使用自定义 MiniMax RP Key（可选）</label>
              </div>

              <div
                v-if="form.useCustomRp"
                class="card card-body border border-primary-subtle llm-config-box mb-3"
              >
                <div class="mb-2">
                  <label class="form-label small fw-bold">MiniMax API Key</label>
                  <input v-model="form.rpKey" type="password" class="form-control form-control-sm" placeholder="用于 M2-her 钉钉角色私聊">
                </div>
                <div class="form-text small">
                  留空时不会使用你的 RP Key；若已配置通用自定义模型，钉钉会回退到通用模型。
                </div>
              </div>

              <div class="d-grid gap-2 mt-4">
                <button
                  class="btn btn-primary btn-lg fw-bold"
                  :disabled="!form.username || !form.inviteCode"
                  @click="handleLogin"
                >
                  📝 进入求是园
                </button>
              </div>
            </div>

            <!-- 加载中 -->
            <div v-else-if="viewState === 'loading'" class="text-center py-5">
              <div class="spinner-border text-primary mb-3" style="width: 3rem; height: 3rem;" role="status" />
              <h5 class="text-muted">{{ loadingText }}</h5>
            </div>
          </div>
        </div>
      </div>

      <!-- 安全政策确认弹窗 -->
      <div
        v-if="showLlmWarning"
        class="modal-backdrop-custom d-flex justify-content-center align-items-center"
      >
        <div class="card shadow-lg border-0 p-4 mx-3" style="max-width: 500px;">
          <h4 class="text-danger fw-bold mb-3">⚠️ 安全政策确认</h4>
          <p class="mb-2">你正在使用自定义模型 API Key。</p>
          <ul class="text-muted small">
            <li>你的 API Key 仅在当前浏览器会话和后端临时连接中使用。</li>
            <li>游戏绝不会将你的密钥持久化存储到数据库。</li>
            <li>关闭浏览器后配置即失效。</li>
            <li>阅读<a href="https://zjusim-docs.67656.fun/user/models/#security-notice">安全须知</a></li>
          </ul>
          <div class="d-flex justify-content-end gap-2 mt-4">
            <button class="btn btn-secondary" @click="cancelLlmAction">返回修改</button>
            <button class="btn btn-danger fw-bold" @click="confirmLlmAction">我已知晓并同意</button>
          </div>
        </div>
      </div>
    </div>

    <footer class="beian-footer mt-4">
      <div class="d-flex flex-column flex-md-row justify-content-center gap-3 align-items-center">
        <a href="https://zjusim-docs.67656.fun/user/notice/" target="_blank" class="text-secondary small">折姜大学招生减章</a>
        <a href="http://beian.miit.gov.cn/" target="_blank" class="text-secondary small">浙ICP备2026007685号</a>
        <a href="https://beian.mps.gov.cn/#/query/webSearch?code=33010602014394" rel="noreferrer" target="_blank" class="text-secondary small d-flex align-items-center gap-1">
          <img src="https://67656.fun/static/images/beian-icon.png" style="height: 1.2em; width: auto;" alt="公安备案">
          <span>浙公网安备33010602014394号</span>
        </a>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import { auth } from '@/api/client'

const store = useGameStore()

const viewState = ref<'login' | 'loading'>('login')
const loadingText = ref('正在验证邀请码...')

const form = reactive({
  username: '',
  inviteCode: '',
  token: '',
  useCustomLlm: false,
  llmProvider: 'openai',
  llmModel: '',
  llmKey: '',
  useCustomRp: false,
  rpKey: '',
})

// LLM 安全弹窗
const showLlmWarning = ref(false)
const pendingAction = ref<(() => void) | null>(null)

const handleLogin = () => {
  const hasCustomLlmKey = form.useCustomLlm && form.llmKey.trim() !== ''
  const hasCustomRpKey = form.useCustomRp && form.rpKey.trim() !== ''
  if (hasCustomLlmKey || hasCustomRpKey) {
    pendingAction.value = doLogin
    showLlmWarning.value = true
  } else {
    doLogin()
  }
}

const cancelLlmAction = () => {
  showLlmWarning.value = false
  pendingAction.value = null
}

const confirmLlmAction = () => {
  showLlmWarning.value = false
  if (pendingAction.value) pendingAction.value()
}

const doLogin = async () => {
  viewState.value = 'loading'
  try {
    const result = await auth({
      username: form.username.trim(),
      invite_code: form.inviteCode.trim(),
      token: form.token || null,
    })

    if (result.status === 'error') {
      alert(result.message || '认证失败')
      viewState.value = 'login'
      return
    }

    // zju_token is the short-lived JWT used by HTTP/WS auth.
    if (result.jwt) localStorage.setItem('zju_token', result.jwt)
    if (result.jwt) localStorage.setItem('zju_jwt', result.jwt)
    if (result.user_token) localStorage.setItem('zju_user_token', result.user_token)
    localStorage.setItem('zju_username', result.username || form.username.trim())

    // 保存会话级模型配置；每次登录先清理旧值，避免关闭开关后沿用上次密钥。
    sessionStorage.removeItem('custom_llm_provider')
    sessionStorage.removeItem('custom_llm_model')
    sessionStorage.removeItem('custom_llm_key')
    sessionStorage.removeItem('custom_rp_key')
    if (form.useCustomLlm && form.llmKey.trim() !== '') {
      sessionStorage.setItem('custom_llm_provider', form.llmProvider)
      sessionStorage.setItem('custom_llm_model', form.llmModel.trim())
      sessionStorage.setItem('custom_llm_key', form.llmKey.trim())
    }
    if (form.useCustomRp && form.rpKey.trim() !== '') {
      sessionStorage.setItem('custom_rp_key', form.rpKey.trim())
    }

    if (result.status === 'returning') {
      localStorage.setItem('zju_saves', JSON.stringify(result.saves || []))
      localStorage.removeItem('game_started')
      localStorage.removeItem('selected_save_slot')
      store.setPhase('save_select')
    } else {
      localStorage.removeItem('zju_saves')
      localStorage.removeItem('selected_save_slot')
      localStorage.removeItem('game_started')
      store.setPhase('character_create')
    }
  } catch (err) {
    console.error('Auth error:', err)
    alert('连接服务器失败，请检查网络')
    viewState.value = 'login'
  }
}

// 背景轮播
const baseUrl = import.meta.env.BASE_URL || '/'
const bgImages = [
  `${baseUrl}images/qiushimen.webp`,
  `${baseUrl}images/zjg_night.jpeg`,
  `${baseUrl}images/zjg_autumn.jpg`,
  `${baseUrl}images/qizhen_lake.jpg`,
]
const bgIndex = ref(0)
const bgOpacity = ref(1)
let bgSwitchTimeout: ReturnType<typeof setTimeout> | null = null
let bgSwitchInterval: ReturnType<typeof setInterval> | null = null

const fadeDuration = 800
const switchBg = () => {
  bgOpacity.value = 0
  bgSwitchTimeout = setTimeout(() => {
    bgIndex.value = (bgIndex.value + 1) % bgImages.length
    bgOpacity.value = 1
  }, fadeDuration)
}

onMounted(() => {
  form.username = localStorage.getItem('zju_username') || ''
  form.token = localStorage.getItem('zju_user_token') || ''
  bgImages.forEach((src) => { const img = new Image(); img.src = src })
  bgSwitchInterval = setInterval(switchBg, 10000)
})

onUnmounted(() => {
  if (bgSwitchTimeout) clearTimeout(bgSwitchTimeout)
  if (bgSwitchInterval) clearInterval(bgSwitchInterval)
})
</script>

<style scoped>
.login-root {
  position: relative;
  min-height: 100vh;
  isolation: isolate;
}
.login-shell {
  position: relative;
  z-index: 1;
  min-height: calc(100vh - 64px);
}
.login-card-wrap {
  width: 100%;
  max-width: 760px;
}
.login-card {
  background: rgba(251, 248, 240, 0.94);
  border: 1px solid rgba(216, 205, 182, 0.72);
  backdrop-filter: blur(8px);
}
.login-header {
  background: linear-gradient(120deg, #2e5275 0%, #3a698f 100%);
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
}
.llm-config-box {
  background: rgba(236, 242, 250, 0.85);
}
.modal-backdrop-custom {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  background-color: rgba(0, 0, 0, 0.65); z-index: 9999; backdrop-filter: blur(3px);
}
.bg-fade {
  position: fixed;
  top: 0; left: 0; width: 100vw; height: 100vh;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  z-index: 0;
  transition: opacity 0.8s;
}
.bg-fade::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(160deg, rgba(11, 26, 41, 0.5), rgba(28, 51, 74, 0.2));
}
.beian-footer {
  position: relative;
  z-index: 1;
  padding: 0 12px 20px;
}
.beian-footer a { color: #eef5ff !important; }
@media (max-width: 768px) {
  .login-shell { min-height: calc(100vh - 86px); }
}
@media (max-width: 430px) {
  .login-shell { padding-top: 14px !important; min-height: calc(100vh - 102px); }
  .login-card .card-body { padding: 1rem !important; }
  .login-header { padding: 1rem 0.8rem !important; }
  .login-header h2 { font-size: 1.4rem; }
  .login-header p { font-size: 0.82rem; }
  .beian-footer { padding: 0 10px 12px; margin-top: 10px !important; }
  .beian-footer .small { font-size: 0.72rem !important; }
}
</style>
