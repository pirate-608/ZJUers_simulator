<template>
  <div class="admission-wrapper vh-100 d-flex flex-column justify-content-center align-items-center">
    <!-- 加载中 -->
    <div
      v-if="loading"
      class="text-center fade-in"
    >
      <div
        class="spinner-border mb-3"
        style="width: 3rem; height: 3rem; color: #b93a32;"
      />
      <h4
        class="fw-bold text-dark"
        style="letter-spacing: 2px;"
      >
        正在连接到zdbk...
      </h4>
    </div>

    <!-- 正常展示区 -->
    <div
      v-else
      class="content-container d-flex flex-column justify-content-center align-items-center fade-in"
    >
      <!-- 📜 核心区域：1:1 完美复刻 HTML 录取通知书 -->
      <div class="admission-card-wrapper">
        <div class="admission-card relative overflow-hidden">
          <!-- 底部建筑风景矢量剪影 -->
          <div
            class="footer-landscape"
            style="position: absolute; bottom: 0; left: 0; width: 100%; height: 200px; pointer-events: none; z-index: 1; opacity: 0.6;"
          >
            <svg
              viewBox="0 0 1000 200"
              preserveAspectRatio="none"
              width="100%"
              height="100%"
            >
              <!-- 远山/云层 -->
              <path
                d="M0,150 Q150,120 300,160 T700,130 T1000,160 L1000,200 L0,200 Z"
                fill="#d8c5b3"
                opacity="0.5"
              />
              <path
                d="M0,170 Q200,140 400,180 T800,150 T1000,180 L1000,200 L0,200 Z"
                fill="#cfbba8"
                opacity="0.6"
              />
              <!-- 飞鸟 -->
              <g
                stroke="#b59c87"
                stroke-width="2"
                fill="none"
              >
                <path d="M 120,60 Q 130,50 140,60 Q 130,55 120,60" />
                <path d="M 150,80 Q 160,70 170,80 Q 160,75 150,80" />
                <path d="M 100,100 Q 115,85 130,100 Q 115,90 100,100" />
              </g>
              <!-- 桥梁 (左侧) -->
              <path
                d="M -50,200 L -50,140 L 350,140 L 350,200 Z"
                fill="#e2d6ca"
                stroke="#b59c87"
                stroke-width="1.5"
              />
              <!-- 桥洞 -->
              <path
                d="M 20,200 A 40 40 0 0 1 100,200"
                fill="#f4e8d8"
                stroke="#b59c87"
                stroke-width="1.5"
              />
              <path
                d="M 140,200 A 40 40 0 0 1 220,200"
                fill="#f4e8d8"
                stroke="#b59c87"
                stroke-width="1.5"
              />
              <path
                d="M 260,200 A 40 40 0 0 1 340,200"
                fill="#f4e8d8"
                stroke="#b59c87"
                stroke-width="1.5"
              />
              <!-- 主建筑群 (中间与右侧) -->
              <rect
                x="380"
                y="150"
                width="350"
                height="50"
                fill="#e2d6ca"
                stroke="#b59c87"
                stroke-width="1.5"
              />
              <rect
                x="750"
                y="120"
                width="150"
                height="80"
                fill="#e2d6ca"
                stroke="#b59c87"
                stroke-width="1.5"
              />
              <rect
                x="920"
                y="140"
                width="100"
                height="60"
                fill="#e2d6ca"
                stroke="#b59c87"
                stroke-width="1.5"
              />
              <!-- 建筑屋顶 -->
              <path
                d="M 360,150 L 555,100 L 750,150 Z"
                fill="#c3b09e"
                stroke="#b59c87"
                stroke-width="1.5"
              />
              <path
                d="M 400,125 L 555,80 L 710,125 Z"
                fill="#d2c0ae"
                stroke="#b59c87"
                stroke-width="1.5"
              />
              <!-- 柱子/细节门窗纹理模拟 -->
              <g
                fill="#b59c87"
                opacity="0.4"
              >
                <rect
                  x="420"
                  y="160"
                  width="10"
                  height="40"
                />
                <rect
                  x="450"
                  y="160"
                  width="10"
                  height="40"
                />
                <rect
                  x="480"
                  y="160"
                  width="10"
                  height="40"
                />
                <rect
                  x="620"
                  y="160"
                  width="10"
                  height="40"
                />
                <rect
                  x="650"
                  y="160"
                  width="10"
                  height="40"
                />
                <rect
                  x="680"
                  y="160"
                  width="10"
                  height="40"
                />
                <rect
                  x="770"
                  y="140"
                  width="30"
                  height="20"
                />
                <rect
                  x="830"
                  y="140"
                  width="30"
                  height="20"
                />
              </g>
              <!-- 装饰性文字牌匾 -->
              <rect
                x="530"
                y="130"
                width="50"
                height="15"
                fill="#b93a32"
                opacity="0.8"
              />
            </svg>
          </div>

          <!-- 右上角：页面竖直排列标题 -->
          <div
            class="absolute z-10 text-right vertical-title-true"
            style="right: 2rem; top: 2rem;"
          >
            <div style="display: flex; flex-direction: column; align-items: flex-end;">
              <span
                class="font-bold text-red-accent vertical-text-true"
                style="font-size: 2.5rem; letter-spacing: 0.5em;"
              >折</span>
              <span
                class="font-bold text-red-accent vertical-text-true"
                style="font-size: 2.5rem; letter-spacing: 0.5em;"
              >姜</span>
              <span
                class="font-bold text-red-accent vertical-text-true"
                style="font-size: 2.5rem; letter-spacing: 0.5em;"
              >大</span>
              <span
                class="font-bold text-red-accent vertical-text-true"
                style="font-size: 2.5rem; letter-spacing: 0.5em;"
              >学</span>
              <span
                class="text-red-accent vertical-text-true"
                style="font-size: 1.8rem; letter-spacing: 1em; margin-top: 2rem;"
              >录</span>
              <span
                class="text-red-accent vertical-text-true"
                style="font-size: 1.8rem; letter-spacing: 1em;"
              >取</span>
              <span
                class="text-red-accent vertical-text-true"
                style="font-size: 1.8rem; letter-spacing: 1em;"
              >通</span>
              <span
                class="text-red-accent vertical-text-true"
                style="font-size: 1.8rem; letter-spacing: 1em;"
              >知</span>
              <span
                class="text-red-accent vertical-text-true"
                style="font-size: 1.8rem; letter-spacing: 1em;"
              >书</span>
            </div>
          </div>

          <!-- 中部：正文 -->
          <div
            class="absolute z-10 font-serif text-gray-800 vertical-rl"
            style="right: 10rem; top: 4rem; bottom: 4rem; left: 28rem; text-align: justify;"
          >
            <p
              class="font-bold text-lg"
              style="margin-right: 0rem;"
            >
              <span style="border-right: 1px solid #4b5563; padding-right: 4px; text-orientation: upright;">{{ info.username }}</span> 同学：
            </p>
              
            <p
              class="text-lg leading-loose"
              style="margin-right: 1rem;"
            >
              你已经被折姜大学正式录取为二零二五级新生。
            </p>

            <p
              class="text-lg leading-loose"
              style="margin-right: 1rem;"
            >
              谨向你表示热烈祝贺！
            </p>

            <p
              class="text-lg leading-loose"
              style="margin-right: 1rem;"
            >
              在过去的学习生涯中，你是一位当之无愧的佼佼者。
            </p>
              
            <p
              class="text-lg leading-loose"
              style="margin-right: 1rem;"
            >
              现在，你将踏入美丽的求是园，在更广阔的天地里
            </p>

            <p
              class="text-lg leading-loose"
              style="margin-right: 1rem;"
            >
              开启更加卓越、更有梦想的人生。
            </p>
              
            <p
              class="text-lg leading-loose"
              style="margin-right: 1rem;"
            >
              此后，你将与历史上众多灿若星辰的名字一起，
            </p>
              
            <p
              class="text-lg leading-loose"
              style="margin-right: 1rem;"
            >
              分享「折大人」这个光荣的称号，共同承担起服务
            </p>

            <p
              class="text-lg leading-loose"
              style="margin-right: 1rem;"
            >
              民族复兴、促进人类进步的责任。
            </p>

            <p
              class="text-lg leading-loose"
              style="margin-right: 1rem;"
            >
              录取专业：<span class="text-red-accent font-bold px-1">{{ info.major }}</span>
            </p>
          </div>

          <!-- 左侧：落款与印章 -->
          <div
            class="absolute z-10 font-serif text-gray-800 vertical-rl"
            style="left: 4rem; bottom: 18rem;"
          >
            <p
              class="font-bold text-lg"
              style="margin-top: 2rem;"
            >
              折姜大学
            </p>
            <p
              class="font-bold text-lg"
              style="margin-right: 1.5rem; margin-top: 2rem;"
            >
              二〇二六年秋
            </p>
            <div
              class="seal-box"
              style="writing-mode: horizontal-tb; transform: rotate(-2deg); margin-top: 1rem; margin-right: 1rem;"
            >
              <span
                class="tracking-widest"
                style="letter-spacing: 0.15em;"
              >求柿<br>创辛</span>
            </div>
          </div>

          <!-- 🌟 左下角： Token 与入园按钮 -->
          <div
            class="absolute z-20"
            style="left: 4rem; bottom: 4rem; width: 300px;"
          >
            <div class="d-flex justify-content-between align-items-center w-100 mb-1">
              <span
                class="text-gray-500 font-bold"
                style="font-size: 0.7rem; font-family: sans-serif; letter-spacing: 0.1em;"
              >NO. CREDENTIAL</span>
              <span
                class="text-red-accent font-bold"
                style="font-size: 0.7rem;"
              >机密 / 请妥善保存，下次登录凭此报到</span>
            </div>
              
            <!-- 仿溯源码的专属凭证展示 -->
            <div
              class="w-100 font-mono text-gray-600 p-2 border border-dashed border-gray-400 bg-white-50 rounded select-all cursor-pointer transition-all hover-border-red shadow-sm"
              style="font-size: 0.75rem; word-break: break-all;"
              title="双击全选并保存此凭证"
            >
              {{ playerToken }}
            </div>

            <div class="d-flex gap-2 mt-2">
              <button
                class="flex-fill py-1 bg-white text-gray-600 rounded border border-gray-400 shadow-sm transition-all hover-border-red"
                style="font-size: 0.75rem;"
                @click="copyToken"
              >
                复制凭证
              </button>
              <button
                class="flex-fill py-1 bg-white text-gray-600 rounded border border-gray-400 shadow-sm transition-all hover-border-red"
                style="font-size: 0.75rem;"
                @click="downloadTokenTxt"
              >
                下载 TXT
              </button>
            </div>
              
            <!-- 沉浸式入园按钮 -->
            <button
              class="w-100 mt-3 py-2 bg-red-accent text-white font-bold tracking-widest shadow-sm hover-shadow-md transition-all rounded border-0 cursor-pointer d-block"
              @click="enterGame"
            >
              报到 ➔
            </button>
          </div>
        </div>
      </div>
      
      <!-- 🌟 终极自救按钮：清理浏览器缓存防止僵尸状态 -->
      <button
        class="btn-reset mt-3"
        @click="forceReset"
      >
        🔄 档案数据异常？或者卡在白屏？点击此处清除缓存并重新参加入学考试
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'

const store = useGameStore()
const emit = defineEmits<{
  'enter-game': [token: string]
}>()

const loading = ref(true)
const info = ref<{ username: string; major: string }>({ username: '折大人', major: '大类招生(未定)' })
const playerToken = ref('')

onMounted(async () => {
  const token = localStorage.getItem('zju_token')
  if (!token) {
    alert('未找到有效凭证，请重新参加入学考试！')
    store.setPhase('login')
    return
  }
  
  playerToken.value = token
  
  // 读取本地存储的真实姓名
  const savedUsername = localStorage.getItem('zju_username')
  if (savedUsername) {
    info.value.username = savedUsername
  }

  try {
    const response = await fetch(`/api/assign_major`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}` 
      },
      body: JSON.stringify({ token: token })
    })

    if (response.ok) {
      // 🌟 终极宽容解析大法
      const rawText = await response.text()
      console.log("【API Debug】后端 /api/assign_major 返回的原始数据:", rawText)
      
      let finalMajor = ''
      try {
        // 尝试按 JSON 解析
        const jsonObj = JSON.parse(rawText) as unknown
        if (typeof jsonObj === 'string') {
          finalMajor = jsonObj // 后端直接返回了 "专业名"
        } else if (typeof jsonObj === 'object' && jsonObj !== null) {
          const obj = jsonObj as Record<string, unknown>
          finalMajor = String(obj.assigned_major || obj.major || obj.data || obj.result || '')
        }
      } catch {
        // 解析 JSON 失败，说明后端返回的是纯文本 (Text)
        finalMajor = rawText
      }

      // 清理两端的残余引号和空格
      finalMajor = finalMajor.replace(/^["']|["']$/g, '').trim()

      if (finalMajor) {
        info.value.major = finalMajor
      } else {
        console.warn("【API Warning】虽然请求成功，但未能从返回内容中提取出有效专业名。")
      }
    } else {
      if (response.status === 401 || response.status === 404) {
        alert("登录凭证已过期或失效（服务器可能已重置数据库），请重新参加入学考试！")
        localStorage.removeItem('zju_token')
        localStorage.removeItem('zju_username')
        store.setPhase('login')
        return
      }
      console.warn(`专业分配接口请求失败 (${response.status})，触发降级保护`)
    }
  } catch (err) {
    console.error("分配专业网络异常:", err)
  } finally {
    loading.value = false
  }
})

const enterGame = () => {
  localStorage.setItem('game_started', '1')
  emit('enter-game', playerToken.value)
}

const buildCredentialText = () => {
  return [
    'ZJUers Simulator 学生凭证',
    `姓名: ${info.value.username}`,
    `专业: ${info.value.major}`,
    `Token: ${playerToken.value}`,
    `生成时间: ${new Date().toLocaleString('zh-CN')}`,
  ].join('\n')
}

const copyToken = async () => {
  if (!playerToken.value) {
    store.showToast('暂无可复制凭证', 'warning')
    return
  }

  try {
    await navigator.clipboard.writeText(playerToken.value)
    store.showToast('凭证已复制到剪贴板', 'success')
  } catch {
    store.showToast('复制失败，请手动选择文本复制', 'danger')
  }
}

const downloadTokenTxt = () => {
  if (!playerToken.value) {
    store.showToast('暂无可下载凭证', 'warning')
    return
  }

  const textBlob = new Blob([buildCredentialText()], { type: 'text/plain;charset=utf-8' })
  const fileName = `zju_credential_${(info.value.username || 'player').replace(/\s+/g, '_')}.txt`
  const blobUrl = URL.createObjectURL(textBlob)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(blobUrl)
  store.showToast('凭证 TXT 已下载', 'success')
}

const forceReset = () => {
  localStorage.removeItem('zju_token')
  localStorage.removeItem('zju_username')
  store.setPhase('login')
  window.location.reload()
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&display=swap');

.admission-wrapper {
  --bg-color: #f7ede1;
  --text-main: #2a2015;
  --red-accent: #b93a32;
  --line-color: #d8c8b8;
  background-color: #e0e0e0;
  font-family: "Noto Serif SC", "KaiTi", "STKaiti", "SimSun", serif;
  overflow-x: hidden;
}

.content-container {
  width: 100%;
  max-width: 1050px;
  padding: 10px;
}

.admission-card-wrapper {
  width: 100%;
  overflow-x: auto;
  display: flex;
  justify-content: center;
  padding-bottom: 10px;
}

.admission-card {
  width: 1000px;
  height: 660px;
  flex-shrink: 0;
  background: linear-gradient(to bottom, #fdfaf4 0%, #f4ebd9 100%);
  color: var(--text-main);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  border-radius: 2px;
}

.relative { position: relative; }
.absolute { position: absolute; }
.inset-0 { top: 0; right: 0; bottom: 0; left: 0; }
.z-0 { z-index: 0; }
.z-10 { z-index: 10; }
.z-20 { z-index: 20; }
.overflow-hidden { overflow: hidden; }
.pointer-events-none { pointer-events: none; }
.w-full { width: 100%; }
.h-full { height: 100%; }

.vertical-rl {
  writing-mode: vertical-rl;
  text-orientation: mixed;
}

.text-lg { font-size: 1.125rem; }
.font-bold { font-weight: 700; }
.font-serif { font-family: "Noto Serif SC", "KaiTi", "STKaiti", serif; }
.leading-loose { line-height: 2.2; }

.text-red-accent { color: var(--red-accent); }
.text-gray-800 { color: #1f2937; }
.text-gray-600 { color: #4b5563; }
.text-gray-500 { color: #6b7280; }
.text-white { color: #ffffff; }
.bg-red-accent { background-color: var(--red-accent); }
.bg-white-50 { background-color: rgba(255, 255, 255, 0.5); }

.px-1 { padding-left: 0.25rem; padding-right: 0.25rem; }
.border { border: 1px solid; }
.border-dashed { border-style: dashed; }
.border-gray-400 { border-color: #9ca3af; }
.rounded { border-radius: 0.25rem; }
.select-all { user-select: all; }
.cursor-pointer { cursor: pointer; }
.shadow-sm { box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); }

.seal-box {
  width: 4rem;
  height: 4rem;
  border: 4px solid var(--red-accent);
  color: var(--red-accent);
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.25;
}

.btn-reset {
  background: none;
  border: none;
  color: #6b7280;
  font-size: 0.85rem;
  text-decoration: underline;
  cursor: pointer;
  transition: color 0.3s;
}
.btn-reset:hover {
  color: var(--red-accent);
}

.transition-all { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.hover-border-red:hover { border-color: var(--red-accent); }
.hover-shadow-md:hover { box-shadow: 0 4px 6px -1px rgba(185, 58, 50, 0.4), 0 2px 4px -1px rgba(185, 58, 50, 0.2); transform: translateY(-1px); }

.fade-in { animation: fadeIn 0.6s cubic-bezier(0.2, 0.8, 0.2, 1); }
@keyframes fadeIn { 
  from { opacity: 0; transform: translateY(20px); } 
  to { opacity: 1; transform: translateY(0); } 
}

.admission-card-wrapper::-webkit-scrollbar { height: 8px; }
.admission-card-wrapper::-webkit-scrollbar-track { background: rgba(0,0,0,0.05); border-radius: 4px; }
.admission-card-wrapper::-webkit-scrollbar-thumb { background: #b59c87; border-radius: 4px; }
</style>