<template>
  <div
    class="end-screen"
    :class="isSuccess ? 'end-screen--graduation' : 'end-screen--failure'"
  >
    <div
      v-if="isSuccess"
      class="graduation-bg"
      :style="{ backgroundImage: `url('${bgImages[bgIndex]}')`, opacity: bgOpacity }"
      aria-hidden="true"
    />

    <section
      v-if="!isSuccess"
      class="failure-scene fade-in-up"
    >
      <div class="notebook-sheet">
        <p class="failure-date">
          退学通知后的夜晚
        </p>
        <h1 class="failure-title">
          很多年后，我才明白，
          <span>我也许只属于灿烂星辰背后的那片黑夜。</span>
        </h1>
        <p class="failure-reason">
          {{ store.endData.reason || '你在求是园中迷失了自我' }}
        </p>
        <p class="failure-note">
          这页日记被雨水泡得发皱。可如果还能再来一次，我想把那个没有说出口的“明天会更好”，亲手写完。
        </p>
        <div class="end-actions">
          <button
            class="end-btn end-btn--light"
            @click="restartGame"
          >
            重新开始
          </button>
          <button
            class="end-btn end-btn--ghost"
            @click="returnHome"
          >
            回到首页
          </button>
        </div>
      </div>
    </section>

    <section
      v-else
      class="graduation-scene fade-in-up"
    >
      <div class="graduation-card">
        <div class="graduation-heading">
          <p class="graduation-kicker">
            Graduation Ceremony
          </p>
          <h1>毕业典礼</h1>
          <p class="graduation-line">
            {{ graduationLine }}
          </p>
        </div>

        <div class="graduation-stats">
          <div class="stat-tile stat-tile--gpa">
            <span>最终 GPA</span>
            <strong>{{ finalGpa.toFixed(2) }}</strong>
          </div>
          <div class="stat-tile">
            <span>智商 / 情商 / 魅力</span>
            <strong>{{ store.endData.iq ?? 100 }} / {{ store.endData.eq ?? 100 }} / {{ store.endData.charm ?? 50 }}</strong>
          </div>
          <div class="stat-tile">
            <span>累计财富</span>
            <strong>{{ store.endData.gold ?? 0 }} 金币</strong>
          </div>
          <div class="stat-tile">
            <span>解锁成就</span>
            <strong>{{ store.endData.achievements_count ?? 0 }} 个</strong>
          </div>
        </div>

        <div
          v-if="achievements.length"
          class="achievement-list"
        >
          <div class="section-label">
            已解锁成就
          </div>
          <div class="achievement-grid">
            <div
              v-for="achievement in achievements"
              :key="achievement.code"
              class="achievement-card"
            >
              <span class="achievement-card-icon">{{ achievement.icon || '🏅' }}</span>
              <span>
                <span class="achievement-name">{{ achievement.name }}</span>
                <span class="achievement-desc">{{ achievement.desc || achievement.code }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="graduation-summary">
          <div class="section-label">
            校史公曰
          </div>
          <p>
            {{ typedText }}<span
              v-if="isTyping"
              class="cursor-blink"
            >|</span>
          </p>
        </div>

        <div class="end-actions end-actions--graduation">
          <button
            class="end-btn end-btn--primary"
            :disabled="isTyping"
            @click="restartGame"
          >
            重返大一
          </button>
          <button
            class="end-btn end-btn--paper"
            @click="returnHome"
          >
            回到首页
          </button>
        </div>
      </div>
    </section>

    <div
      class="world-links fade-in-up"
      style="animation-delay: 1s;"
    >
      <div
        class="world-links-label"
      >
        世界观与开发者指南：
      </div>
      <div class="world-links-row">
        <a
          href="https://zjusim-docs.67656.fun/user/rules/"
          target="_blank"
          class="world-link"
        >折大校规</a>
        <a
          href="https://zjusim-docs.67656.fun/world/keywords/"
          target="_blank"
          class="world-link"
        >关键词表</a>
        <a
          href="https://zjusim-docs.67656.fun/world/majors/"
          target="_blank"
          class="world-link"
        >专业列表</a>
        <a
          href="https://zjusim-docs.67656.fun/world/achievements/"
          target="_blank"
          class="world-link"
        >成就配置</a>
        <a
          href="https://zjusim-docs.67656.fun/world/courses/"
          target="_blank"
          class="world-link"
        >课程数据</a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import type { WsClientAction } from '@/types/websocket'

const store = useGameStore()
const emit = defineEmits<{
  'send-action': [payload: WsClientAction]
  'go-home': []
}>()
// 判断是否是好结局
const isSuccess = computed(() => store.endType === 'graduation')
const finalGpa = computed(() => {
  const parsed = Number(store.endData.gpa ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
})
const graduationLine = computed(() => (
  finalGpa.value < 4
    ? '虽然仍旧平凡，但这一次我问心无愧'
    : '这一世，我活出了更好的自己'
))
const achievements = computed(() => (
  Array.isArray(store.endData.achievement_details)
    ? store.endData.achievement_details
    : []
))

const baseUrl = import.meta.env.BASE_URL || '/'
const bgImages = [
  `${baseUrl}images/qiushimen.webp`,
  `${baseUrl}images/zjg_night.jpeg`,
  `${baseUrl}images/zjg_autumn.jpg`,
  `${baseUrl}images/qizhen_lake.jpg`,
  `${baseUrl}images/sunset.webp`,
]
const bgIndex = ref(0)
const bgOpacity = ref(1)
let bgSwitchTimeout: ReturnType<typeof setTimeout> | null = null
let bgSwitchInterval: ReturnType<typeof setInterval> | null = null
let typewriterInterval: ReturnType<typeof setInterval> | null = null
const fadeDuration = 900

const switchBg = () => {
  bgOpacity.value = 0
  bgSwitchTimeout = setTimeout(() => {
    bgIndex.value = (bgIndex.value + 1) % bgImages.length
    bgOpacity.value = 1
  }, fadeDuration)
}

// 打字机特效状态
const typedText = ref('')
const isTyping = ref(false)

onMounted(() => {
  if (isSuccess.value) {
    bgImages.forEach((src) => {
      const img = new Image()
      img.src = src
    })
    bgSwitchInterval = setInterval(switchBg, 9000)
    const fullText = store.endData.llm_summary || "此子聪颖过人，勤勉有加。求是园中四载，风华正茂，未来可期。前程似锦，望珍重！"
    startTypewriter(fullText)
  }
})

onUnmounted(() => {
  if (bgSwitchTimeout) clearTimeout(bgSwitchTimeout)
  if (bgSwitchInterval) clearInterval(bgSwitchInterval)
  clearTypewriter()
})

const clearTypewriter = () => {
  if (typewriterInterval) {
    clearInterval(typewriterInterval)
    typewriterInterval = null
  }
}

// 打字机特效函数
const startTypewriter = (text: string) => {
  clearTypewriter()
  isTyping.value = true
  let i = 0
  typedText.value = ''

  typewriterInterval = setInterval(() => {
    if (i < text.length) {
      typedText.value += text.charAt(i)
      i++
    } else {
      clearTypewriter()
      isTyping.value = false
    }
  }, 50) // 每 50ms 吐出一个字
}

// 重新开始游戏逻辑
const restartGame = () => {
  // 发送重开指令
  emit('send-action', { action: 'restart' })
}

const returnHome = () => {
  emit('go-home')
}
</script>

<style scoped>
.end-screen {
  position: relative;
  isolation: isolate;
  display: flex;
  min-height: 100vh;
  width: 100%;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: clamp(20px, 4vw, 42px);
  color: #f9f4e8;
}

.end-screen--failure {
  background:
    radial-gradient(circle at 18% 8%, rgba(89, 43, 44, 0.28), transparent 34%),
    radial-gradient(circle at 84% 92%, rgba(36, 73, 108, 0.18), transparent 30%),
    linear-gradient(160deg, #05070b 0%, #10131a 48%, #050609 100%);
}

.end-screen--failure::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -2;
  opacity: 0.34;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
  background-size: 42px 42px;
}

.end-screen--failure::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background:
    linear-gradient(90deg, rgba(0, 0, 0, 0.76), transparent 30%, transparent 70%, rgba(0, 0, 0, 0.66)),
    radial-gradient(circle at 50% 42%, transparent 0%, rgba(0, 0, 0, 0.42) 78%);
}

.graduation-bg {
  position: absolute;
  inset: 0;
  z-index: -3;
  background-position: center;
  background-size: cover;
  transition: opacity 0.9s ease;
  transform: scale(1.04);
}

.end-screen--graduation::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -2;
  background:
    linear-gradient(180deg, rgba(8, 19, 31, 0.18), rgba(8, 18, 27, 0.68)),
    linear-gradient(90deg, rgba(8, 12, 18, 0.54), rgba(17, 39, 54, 0.16), rgba(8, 12, 18, 0.5));
}

.end-screen--graduation::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background:
    radial-gradient(circle at 24% 12%, rgba(224, 194, 121, 0.2), transparent 30%),
    radial-gradient(circle at 82% 14%, rgba(112, 160, 193, 0.18), transparent 32%);
}

.failure-scene,
.graduation-scene {
  width: min(100%, 1060px);
  display: flex;
  justify-content: center;
}

.notebook-sheet {
  position: relative;
  width: min(780px, 100%);
  padding: clamp(32px, 6vw, 64px);
  border: 1px solid rgba(221, 205, 174, 0.2);
  border-radius: 4px;
  color: #efe3cf;
  background:
    linear-gradient(90deg, rgba(122, 44, 44, 0.3) 0 1px, transparent 1px 100%),
    repeating-linear-gradient(180deg, transparent 0 31px, rgba(237, 220, 187, 0.12) 32px),
    linear-gradient(180deg, rgba(31, 27, 25, 0.9), rgba(17, 18, 22, 0.94));
  background-position: 70px 0, 0 0, 0 0;
  box-shadow:
    0 34px 90px rgba(0, 0, 0, 0.58),
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    inset 0 0 72px rgba(0, 0, 0, 0.36);
}

.notebook-sheet::before {
  content: '';
  position: absolute;
  inset: 16px;
  border: 1px solid rgba(237, 220, 187, 0.12);
  pointer-events: none;
}

.failure-date {
  margin: 0 0 24px;
  color: rgba(226, 197, 164, 0.7);
  font-size: 0.9rem;
  letter-spacing: 0;
}

.failure-title,
.failure-note,
.failure-reason {
  font-family: "Kaiti", "STKaiti", "KaiTi", "Songti SC", serif;
}

.failure-title {
  margin: 0;
  max-width: 650px;
  color: #fff2dc;
  font-size: clamp(2rem, 6vw, 4rem);
  font-weight: 500;
  line-height: 1.34;
  letter-spacing: 0;
}

.failure-title span {
  display: block;
  margin-top: 10px;
}

.failure-reason {
  margin: 32px 0 0;
  color: #e5a8a0;
  font-size: clamp(1.2rem, 3vw, 1.7rem);
  line-height: 1.6;
}

.failure-reason::before {
  content: '退学原因：';
  color: rgba(235, 210, 179, 0.66);
}

.failure-note {
  margin: 28px 0 0;
  max-width: 620px;
  color: rgba(245, 230, 206, 0.76);
  font-size: clamp(1.05rem, 2.4vw, 1.35rem);
  line-height: 1.9;
}

.graduation-card {
  width: min(1080px, 100%);
  padding: clamp(24px, 4vw, 46px);
  border: 1px solid rgba(255, 255, 255, 0.32);
  border-radius: 8px;
  color: #172133;
  background:
    linear-gradient(180deg, rgba(255, 250, 239, 0.94), rgba(247, 238, 221, 0.9)),
    rgba(255, 255, 255, 0.86);
  box-shadow:
    0 30px 90px rgba(0, 0, 0, 0.36),
    inset 0 1px 0 rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(14px);
}

.graduation-heading {
  text-align: center;
  padding-bottom: 28px;
  border-bottom: 1px solid rgba(73, 93, 112, 0.18);
}

.graduation-kicker,
.section-label {
  margin: 0;
  color: #2f668e;
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.graduation-heading h1 {
  margin: 8px 0 12px;
  color: #1e3147;
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
  font-size: clamp(2.4rem, 7vw, 5.2rem);
  font-weight: 800;
  letter-spacing: 0;
}

.graduation-line {
  margin: 0 auto;
  max-width: 780px;
  color: #6d5129;
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
  font-size: clamp(1.25rem, 3vw, 2rem);
  font-weight: 700;
  line-height: 1.5;
}

.graduation-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 24px 0;
}

.stat-tile {
  min-width: 0;
  padding: 18px 16px;
  border: 1px solid rgba(63, 88, 112, 0.16);
  border-radius: 6px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(243, 238, 227, 0.74));
}

.stat-tile span {
  display: block;
  color: #647386;
  font-size: 0.82rem;
  font-weight: 700;
}

.stat-tile strong {
  display: block;
  margin-top: 6px;
  color: #26364b;
  font-size: clamp(1.2rem, 2.4vw, 1.9rem);
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.stat-tile--gpa strong {
  color: #26715f;
  font-size: clamp(2rem, 4vw, 3rem);
}

.achievement-list {
  margin-bottom: 24px;
  padding: 16px;
  border: 1px solid rgba(190, 159, 99, 0.25);
  border-radius: 6px;
  background: rgba(255, 248, 231, 0.68);
}

.achievement-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.achievement-card {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid rgba(160, 126, 70, 0.22);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.68);
}

.achievement-card-icon {
  flex: 0 0 auto;
  font-size: 1.45rem;
}

.achievement-name {
  display: block;
  color: #26364b;
  font-weight: 800;
}

.achievement-desc {
  display: block;
  margin-top: 2px;
  color: #6f7883;
  font-size: 0.88rem;
  line-height: 1.45;
}

.graduation-summary {
  padding: 20px;
  border: 1px solid rgba(68, 91, 114, 0.14);
  border-radius: 6px;
  background:
    linear-gradient(180deg, rgba(252, 248, 239, 0.92), rgba(241, 233, 220, 0.86));
}

.graduation-summary p {
  min-height: 96px;
  margin: 12px 0 0;
  color: #253045;
  font-family: "Kaiti", "STKaiti", "KaiTi", "Songti SC", serif;
  font-size: clamp(1.15rem, 2vw, 1.45rem);
  line-height: 1.9;
}

.end-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 34px;
}

.end-actions--graduation {
  justify-content: center;
}

.end-btn {
  min-height: 46px;
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 10px 26px;
  font-weight: 800;
  letter-spacing: 0;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.end-btn:hover:not(:disabled),
.end-btn:focus-visible:not(:disabled) {
  transform: translateY(-1px);
}

.end-btn:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.end-btn--light {
  color: #241d19;
  background: linear-gradient(180deg, #f4dfb4, #d6ad6a);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.26);
}

.end-btn--ghost {
  color: #f3e6ce;
  border-color: rgba(238, 219, 184, 0.38);
  background: rgba(255, 255, 255, 0.06);
}

.end-btn--primary {
  color: #fff9ea;
  background: linear-gradient(180deg, #2f668e, #214863);
  box-shadow: 0 14px 26px rgba(42, 86, 118, 0.24);
}

.end-btn--paper {
  color: #27435b;
  border-color: rgba(64, 92, 116, 0.25);
  background: rgba(255, 255, 255, 0.54);
}

.world-links {
  width: min(100%, 960px);
  margin-top: clamp(24px, 4vw, 44px);
  text-align: center;
}

.world-links-label {
  margin-bottom: 10px;
  color: rgba(247, 239, 224, 0.72);
  font-size: 0.82rem;
}

.world-links-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.world-link {
  border: 1px solid rgba(255, 255, 255, 0.26);
  border-radius: 999px;
  padding: 6px 12px;
  color: rgba(255, 250, 239, 0.86);
  background: rgba(5, 12, 18, 0.28);
  text-decoration: none;
  backdrop-filter: blur(8px);
}

.end-screen--graduation .world-link,
.end-screen--graduation .world-links-label {
  color: rgba(255, 250, 239, 0.9);
}

.fade-in-up {
  animation: fadeInUp 0.8s ease-out forwards;
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

.cursor-blink {
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}

@media (max-width: 900px) {
  .graduation-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .achievement-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 430px) {
  .end-screen {
    justify-content: flex-start;
    padding: 16px 10px 24px;
  }

  .graduation-stats {
    grid-template-columns: 1fr;
  }

  .end-actions {
    width: 100%;
  }

  .end-btn {
    width: 100%;
  }

  .world-link {
    padding: 5px 10px;
    font-size: 0.78rem;
  }
}
</style>
