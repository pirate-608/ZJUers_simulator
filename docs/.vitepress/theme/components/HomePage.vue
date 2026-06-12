<template>
  <main class="zjus-home">
    <canvas ref="canvasRef" class="zjus-stars" aria-hidden="true" />

    <section class="zjus-hero">
      <p class="zjus-kicker">ZJU Simulator Project</p>
      <h1 class="zjus-title">
        <span class="zjus-title-accent">ZJUers Simulator</span>
        <span class="zjus-type">{{ typedText }}</span>
        <span class="zjus-cursor" aria-hidden="true" />
      </h1>
      <p class="zjus-subtitle">
        我在这里放了67656颗星星，希望每个折大人都能找到属于自己的一颗。
      </p>
      <div class="zjus-actions">
        <a href="https://67656.fun" class="zjus-action primary">开始游戏</a>
        <a href="/user/online_guide" class="zjus-action">阅读指南</a>
        <a href="#interactive-demo" class="zjus-action">查看 Demo</a>
      </div>
    </section>

    <section id="interactive-demo" class="zjus-section zjus-demo-section">
      <div class="zjus-section-head">
        <p>Interactive Preview</p>
        <h2>不用离开文档，就能摸到游戏主界面</h2>
      </div>
      <InteractiveGameDemo mode="dashboard" />
    </section>

    <section class="zjus-section">
      <div class="zjus-section-head">
        <p>Core Experience</p>
        <h2>把校园生活变成一场轻策略叙事</h2>
      </div>
      <div class="zjus-card-grid">
        <article v-for="item in features" :key="item.title" class="zjus-card">
          <span>{{ item.icon }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.desc }}</p>
        </article>
      </div>
    </section>

    <section class="zjus-section zjus-links">
      <a href="/user/notice">游戏说明</a>
      <a href="/user/rules">游戏规则</a>
      <a href="/user/dingtalk">钉钉私聊</a>
      <a href="/world/majors">相关设定</a>
      <a href="/dev/api">开发人员指南</a>
      <a href="https://github.com/pirate-608/ZJUers_simulator/discussions/">参与讨论</a>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import InteractiveGameDemo from './InteractiveGameDemo.vue'

const typedText = ref('')
const phrase = 'A mirror world of 67656 ZJU Students.'
const canvasRef = ref<HTMLCanvasElement | null>(null)

const features = [
  { icon: '课程', title: '课程策略', desc: '在有限学期内平衡课程掌握度、精力、压力和 GPA。' },
  { icon: '事件', title: '随机事件', desc: '由本地事件库、混合模式或 AI 生成校园叙事分支。' },
  { icon: '钉钉', title: '角色私聊', desc: '联系人、红点、回复选项和一轮对话结算贯穿游戏进程。' },
  { icon: '存档', title: '长期存档', desc: 'Redis 实时状态与 PostgreSQL 存档协同保存每一次返校。' },
]

let animationId = 0
let typingTimer: ReturnType<typeof setTimeout> | null = null

function startTyping(index = 0) {
  typedText.value = phrase.slice(0, index)
  if (index <= phrase.length) {
    typingTimer = setTimeout(() => startTyping(index + 1), index < 14 ? 80 : 42)
  }
}

function drawStars(canvas: HTMLCanvasElement) {
  const context = canvas.getContext('2d')
  if (!context) return

  const resize = () => {
    canvas.width = window.innerWidth * window.devicePixelRatio
    canvas.height = window.innerHeight * window.devicePixelRatio
    canvas.style.width = `${window.innerWidth}px`
    canvas.style.height = `${window.innerHeight}px`
  }

  resize()
  window.addEventListener('resize', resize)

  const stars = Array.from({ length: Math.floor((window.innerWidth * window.innerHeight) / 2600) }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    r: Math.random() * 1.5 + 0.25,
    phase: Math.random() * Math.PI * 2,
    speed: Math.random() * 0.018 + 0.004,
  }))

  let tick = 0
  const render = () => {
    const isDark = document.documentElement.classList.contains('dark')
    tick += 1
    context.clearRect(0, 0, canvas.width, canvas.height)
    context.fillStyle = isDark ? 'rgba(2, 8, 23, 0.92)' : 'rgba(245, 250, 255, 0.94)'
    context.fillRect(0, 0, canvas.width, canvas.height)

    const gradient = context.createRadialGradient(
      canvas.width * 0.5,
      canvas.height * 0.18,
      0,
      canvas.width * 0.5,
      canvas.height * 0.18,
      canvas.width * 0.65,
    )
    gradient.addColorStop(0, isDark ? 'rgba(58, 116, 255, 0.16)' : 'rgba(82, 166, 255, 0.2)')
    gradient.addColorStop(0.42, isDark ? 'rgba(17, 41, 87, 0.12)' : 'rgba(189, 225, 255, 0.32)')
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)')
    context.fillStyle = gradient
    context.fillRect(0, 0, canvas.width, canvas.height)

    for (const star of stars) {
      const alpha = 0.35 + Math.sin(tick * star.speed + star.phase) * 0.35
      context.beginPath()
      context.arc(star.x, star.y, star.r * window.devicePixelRatio, 0, Math.PI * 2)
      context.fillStyle = isDark
        ? `rgba(220, 235, 255, ${Math.max(0.18, alpha)})`
        : `rgba(38, 112, 190, ${Math.max(0.12, alpha * 0.45)})`
      context.fill()
    }

    animationId = requestAnimationFrame(render)
  }

  render()
}

onMounted(() => {
  startTyping()
  if (canvasRef.value) drawStars(canvasRef.value)
})

onUnmounted(() => {
  if (typingTimer) clearTimeout(typingTimer)
  if (animationId) cancelAnimationFrame(animationId)
})
</script>

<style scoped>
.zjus-home {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  padding-bottom: 80px;
}

.zjus-stars {
  position: fixed;
  inset: 0;
  z-index: -1;
  background: var(--zjus-home-canvas-bg, #020817);
}

.zjus-hero {
  min-height: calc(100vh - var(--nav-height));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 96px 24px 72px;
  text-align: center;
}

.zjus-kicker {
  margin: 0 0 22px;
  color: var(--zjus-home-kicker, rgba(202, 226, 255, 0.62));
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.24em;
  text-transform: uppercase;
}

.zjus-title {
  display: flex;
  min-height: 152px;
  flex-direction: column;
  align-items: center;
  margin: 0;
  font-size: clamp(2.45rem, 7vw, 5.4rem);
  line-height: 1.06;
}

.zjus-title-accent {
  background: var(--zjus-home-title-gradient, linear-gradient(120deg, #f8fbff 0%, #8cc8ff 38%, #a8b8ff 72%, #ffffff 100%));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.zjus-type {
  min-height: 1.2em;
  margin-top: 12px;
  color: var(--zjus-home-type, rgba(232, 242, 255, 0.88));
  font-size: clamp(1.25rem, 3vw, 2.1rem);
  font-weight: 650;
}

.zjus-cursor {
  width: 3px;
  height: 0.86em;
  margin-top: -0.86em;
  margin-left: min(76vw, 740px);
  background: var(--zjus-home-cursor, #80c7ff);
  box-shadow: 0 0 16px var(--zjus-home-cursor-glow, rgba(128, 199, 255, 0.9));
  animation: blink 0.8s infinite;
}

.zjus-subtitle {
  max-width: 720px;
  margin: 28px auto 0;
  color: var(--zjus-home-subtitle, rgba(224, 239, 255, 0.64));
  font-size: 1.12rem;
  line-height: 1.9;
}

.zjus-actions,
.zjus-links {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 14px;
  margin-top: 34px;
}

.zjus-action,
.zjus-links a {
  border: 1px solid var(--zjus-home-action-border, rgba(142, 198, 255, 0.22));
  border-radius: 999px;
  padding: 12px 22px;
  color: var(--zjus-home-action-text, rgba(235, 247, 255, 0.78));
  background: var(--zjus-home-action-bg, rgba(255, 255, 255, 0.045));
  text-decoration: none;
  backdrop-filter: blur(16px);
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.zjus-action:hover,
.zjus-links a:hover {
  transform: translateY(-2px);
  border-color: var(--zjus-home-action-hover-border, rgba(142, 198, 255, 0.56));
  background: var(--zjus-home-action-hover-bg, rgba(78, 150, 255, 0.16));
}

.zjus-action.primary {
  color: var(--zjus-home-primary-text, #06111f);
  background: var(--zjus-home-primary-bg, linear-gradient(120deg, #b7e3ff, #7dbdff));
  border-color: transparent;
  font-weight: 800;
}

.zjus-section {
  width: min(1180px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 82px 0;
}

.zjus-demo-section {
  scroll-margin-top: calc(var(--nav-height) + 28px);
  width: min(1480px, calc(100vw - 96px));
}

.zjus-section-head {
  margin-bottom: 28px;
}

.zjus-section-head p {
  margin: 0 0 8px;
  color: var(--zjus-home-section-kicker, #83c3ff);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.zjus-section-head h2 {
  margin: 0;
  color: var(--zjus-home-section-title, rgba(245, 250, 255, 0.92));
  font-size: clamp(1.8rem, 4vw, 3rem);
  line-height: 1.2;
}

.zjus-card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.zjus-card {
  min-height: 210px;
  border: 1px solid rgba(145, 199, 255, 0.12);
  border-radius: 8px;
  padding: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.02)),
    var(--zjus-home-card-bg, rgba(6, 17, 33, 0.72));
  box-shadow: 0 22px 80px rgba(0, 0, 0, 0.18);
}

.zjus-card span {
  display: inline-flex;
  margin-bottom: 22px;
  color: var(--zjus-home-card-label, #9ed0ff);
  font-weight: 800;
}

.zjus-card h3 {
  margin: 0 0 12px;
  color: var(--zjus-home-card-title, #f6fbff);
  font-size: 1.12rem;
}

.zjus-card p {
  margin: 0;
  color: var(--zjus-home-card-text, rgba(221, 237, 255, 0.62));
  line-height: 1.7;
}

.zjus-links {
  padding-top: 20px;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

@media (max-width: 900px) {
  .zjus-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .zjus-title {
    min-height: 132px;
  }

  .zjus-card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
