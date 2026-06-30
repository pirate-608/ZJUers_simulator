<template>
  <section
    class="prologue-root"
    :class="[`tone-${currentScene.tone}`, { 'is-diary': isDiaryPhase }]"
    aria-live="polite"
  >
    <div
      class="prologue-background"
      :style="{ backgroundImage: `url('${currentScene.image}')` }"
    />

    <button
      type="button"
      class="prologue-skip"
      data-testid="prologue-skip"
      @click="finish"
    >
      跳过
    </button>

    <div v-if="phase === 'dedication'" class="prologue-copy-wrap">
      <p class="prologue-kicker">
        ZJUers Simulator
      </p>
      <Transition name="prologue-line" mode="out-in">
        <p
          :key="dedicationIndex"
          class="prologue-line"
          data-testid="prologue-line"
        >
          {{ currentDedicationLine }}
        </p>
      </Transition>
    </div>

    <div
      v-else
      class="prologue-notebook-wrap"
      :class="{ flipping: isPageFlipping }"
      data-testid="prologue-notebook"
    >
      <div class="notebook-cover" aria-hidden="true" />
      <article class="notebook-page">
        <header class="notebook-header">
          <span>启真湖畔</span>
          <span>{{ pageIndex + 1 }} / {{ PROLOGUE_DIARY_PAGES.length }}</span>
        </header>

        <div class="notebook-lines">
          <p
            v-for="(line, index) in currentDiaryPage"
            :key="`${pageIndex}-${index}`"
            class="notebook-line"
            :class="{
              visible: isDiaryLineVisible(index),
              typing: isTypingDiaryLine(index),
            }"
            data-testid="prologue-diary-line"
          >
            <span class="line-text">{{ getDiaryLineText(line, index) }}</span>
            <span
              v-if="isTypingDiaryLine(index)"
              class="typewriter-caret"
              aria-hidden="true"
            />
          </p>
        </div>
      </article>
      <div class="page-turn-sheet" aria-hidden="true" />
    </div>

    <div class="prologue-progress" aria-hidden="true">
      <span
        v-for="(_, index) in PROLOGUE_LINES"
        :key="index"
        class="prologue-dot"
        :class="{ active: index < completedLineCount }"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * Skippable first-visit prologue shown before any normal startup flow.
 *
 * The component intentionally owns only visual pacing. App.vue still owns the
 * gate that blocks login/save routing and WebSocket startup until completion.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  getPrologueScene,
  PROLOGUE_DEDICATION_LINES,
  PROLOGUE_DIARY_PAGES,
  PROLOGUE_FIRST_DIARY_INDEX,
  PROLOGUE_IMAGES,
  PROLOGUE_LINES,
} from '@/data/prologue'

const emit = defineEmits<{
  complete: []
}>()

const DEDICATION_LINE_MS = 2300
const DIARY_FIRST_LINE_DELAY_MS = 720
const DIARY_CHAR_MS = 44
const DIARY_LINE_PAUSE_MS = 760
const PAGE_FLIP_MS = 1180
const FINAL_HOLD_MS = 2200

const phase = ref<'dedication' | 'diary'>('dedication')
const dedicationIndex = ref(0)
const pageIndex = ref(0)
const visibleDiaryLineCount = ref(0)
const typedCharCount = ref(0)
const isPageFlipping = ref(false)

let timer: ReturnType<typeof setTimeout> | null = null
let hasFinished = false

const currentDedicationLine = computed(
  () => PROLOGUE_DEDICATION_LINES[dedicationIndex.value],
)
const currentDiaryPage = computed(() => PROLOGUE_DIARY_PAGES[pageIndex.value])
const isDiaryPhase = computed(() => phase.value === 'diary')

const previousDiaryLinesCount = computed(() =>
  PROLOGUE_DIARY_PAGES
    .slice(0, pageIndex.value)
    .reduce((total, page) => total + page.length, 0),
)

const activeLineIndex = computed(() => {
  if (phase.value === 'dedication') {
    return dedicationIndex.value
  }

  const activeDiaryLine = typedCharCount.value > 0
    ? visibleDiaryLineCount.value
    : Math.max(visibleDiaryLineCount.value - 1, 0)

  return (
    PROLOGUE_FIRST_DIARY_INDEX
    + previousDiaryLinesCount.value
    + Math.min(activeDiaryLine, currentDiaryPage.value.length - 1)
  )
})

const completedLineCount = computed(() => {
  if (phase.value === 'dedication') {
    return dedicationIndex.value + 1
  }

  return (
    PROLOGUE_FIRST_DIARY_INDEX
    + previousDiaryLinesCount.value
    + visibleDiaryLineCount.value
    + (typedCharCount.value > 0 ? 1 : 0)
  )
})

const currentScene = computed(() => getPrologueScene(activeLineIndex.value))

const clearTimer = () => {
  if (timer) clearTimeout(timer)
  timer = null
}

const schedule = (callback: () => void, delay: number) => {
  clearTimer()
  timer = setTimeout(callback, delay)
}

const finish = () => {
  if (hasFinished) return
  hasFinished = true
  clearTimer()
  emit('complete')
}

const isTypingDiaryLine = (index: number) => {
  const line = currentDiaryPage.value[index]
  return Boolean(
    phase.value === 'diary'
    && line
    && !isPageFlipping.value
    && index === visibleDiaryLineCount.value
    && typedCharCount.value > 0
    && typedCharCount.value < line.length,
  )
}

const isDiaryLineVisible = (index: number) =>
  index < visibleDiaryLineCount.value || (
    index === visibleDiaryLineCount.value && typedCharCount.value > 0
  )

const getDiaryLineText = (line: string, index: number) => {
  if (index < visibleDiaryLineCount.value) return line
  if (index === visibleDiaryLineCount.value) {
    return line.slice(0, typedCharCount.value)
  }
  return ''
}

const turnDiaryPage = () => {
  if (pageIndex.value >= PROLOGUE_DIARY_PAGES.length - 1) {
    schedule(finish, FINAL_HOLD_MS)
    return
  }

  isPageFlipping.value = true
  pageIndex.value += 1
  visibleDiaryLineCount.value = 0
  typedCharCount.value = 0
  schedule(() => {
    isPageFlipping.value = false
    writeDiaryLine()
  }, PAGE_FLIP_MS)
}

const writeDiaryLine = () => {
  const line = currentDiaryPage.value[visibleDiaryLineCount.value]
  if (!line) {
    turnDiaryPage()
    return
  }

  const delay =
    visibleDiaryLineCount.value === 0 && typedCharCount.value === 0
      ? DIARY_FIRST_LINE_DELAY_MS
      : DIARY_CHAR_MS

  schedule(() => {
    if (typedCharCount.value < line.length) {
      typedCharCount.value += 1
      writeDiaryLine()
      return
    }

    schedule(() => {
      visibleDiaryLineCount.value += 1
      typedCharCount.value = 0
      writeDiaryLine()
    }, DIARY_LINE_PAUSE_MS)
  }, delay)
}

const startDiary = () => {
  phase.value = 'diary'
  pageIndex.value = 0
  visibleDiaryLineCount.value = 0
  typedCharCount.value = 0
  writeDiaryLine()
}

const playDedicationLine = () => {
  schedule(() => {
    if (dedicationIndex.value < PROLOGUE_DEDICATION_LINES.length - 1) {
      dedicationIndex.value += 1
      playDedicationLine()
      return
    }

    startDiary()
  }, DEDICATION_LINE_MS)
}

onMounted(() => {
  if (typeof Image !== 'undefined') {
    PROLOGUE_IMAGES.forEach((src) => {
      const img = new Image()
      img.src = src
    })
  }
  playDedicationLine()
})

onUnmounted(clearTimer)
</script>

<style scoped>
.prologue-root {
  position: relative;
  display: flex;
  min-height: 100vh;
  overflow: hidden;
  align-items: center;
  justify-content: center;
  isolation: isolate;
  color: #fffaf0;
  background: #111927;
}

.prologue-background {
  position: absolute;
  inset: 0;
  z-index: -2;
  background-position: center;
  background-size: cover;
  transition: background-image 0.8s ease, filter 0.8s ease, transform 1s ease;
}

.prologue-root.is-diary .prologue-background {
  filter: saturate(0.92) brightness(0.7);
  transform: scale(1.025);
}

.prologue-root::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background:
    linear-gradient(180deg, rgba(10, 13, 18, 0.18), rgba(10, 13, 18, 0.68)),
    linear-gradient(90deg, rgba(8, 13, 18, 0.52), rgba(8, 13, 18, 0.12), rgba(8, 13, 18, 0.55));
  transition: background 0.5s ease;
}

.prologue-root.tone-morning::after,
.prologue-root.tone-threshold::after {
  background:
    radial-gradient(circle at 50% 42%, rgba(255, 247, 221, 0.08), transparent 36%),
    linear-gradient(180deg, rgba(13, 24, 32, 0.12), rgba(13, 24, 32, 0.56)),
    linear-gradient(90deg, rgba(15, 27, 38, 0.42), rgba(40, 55, 56, 0.08), rgba(15, 27, 38, 0.42));
}

.prologue-root.tone-lake::after {
  background:
    radial-gradient(circle at 48% 42%, rgba(32, 61, 78, 0.06), transparent 34%),
    linear-gradient(180deg, rgba(8, 12, 18, 0.24), rgba(8, 12, 18, 0.76)),
    linear-gradient(90deg, rgba(7, 12, 22, 0.58), rgba(16, 32, 48, 0.16), rgba(7, 12, 22, 0.5));
}

.prologue-root.tone-sunset::after {
  background:
    linear-gradient(180deg, rgba(26, 18, 16, 0.1), rgba(20, 15, 18, 0.64)),
    linear-gradient(90deg, rgba(26, 20, 22, 0.42), rgba(92, 66, 44, 0.08), rgba(26, 20, 22, 0.42));
}

.prologue-skip {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 3;
  min-width: 68px;
  border: 1px solid rgba(255, 255, 255, 0.55);
  border-radius: 999px;
  padding: 8px 16px;
  color: #fffaf0;
  background: rgba(12, 19, 28, 0.34);
  backdrop-filter: blur(8px);
}

.prologue-skip:hover,
.prologue-skip:focus {
  border-color: rgba(255, 255, 255, 0.88);
  background: rgba(255, 255, 255, 0.14);
}

.prologue-copy-wrap {
  width: calc(100vw - 44px);
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  text-shadow: 0 3px 20px rgba(0, 0, 0, 0.55);
}

.prologue-kicker {
  margin: 0 0 22px;
  font-size: 0.88rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
  opacity: 0.78;
}

.prologue-line {
  margin: 0;
  white-space: nowrap;
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
  font-size: clamp(0.88rem, 3.85vw, 2.85rem);
  font-weight: 700;
  line-height: 1.45;
  letter-spacing: 0;
}

.prologue-notebook-wrap {
  position: relative;
  width: min(920px, calc(100vw - 44px));
  min-height: min(720px, calc(100vh - 96px));
  perspective: 1600px;
  animation: notebook-arrive 0.72s ease both;
}

.notebook-cover {
  position: absolute;
  inset: 16px -8px -18px 22px;
  border-radius: 20px 28px 28px 20px;
  background:
    linear-gradient(90deg, rgba(43, 28, 23, 0.95), rgba(84, 55, 40, 0.9)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.12), transparent 42%);
  box-shadow:
    0 38px 80px rgba(0, 0, 0, 0.42),
    inset 13px 0 22px rgba(0, 0, 0, 0.28);
}

.notebook-page,
.page-turn-sheet {
  background:
    linear-gradient(90deg, rgba(125, 64, 48, 0.24) 0 2px, transparent 2px 100%),
    repeating-linear-gradient(180deg, transparent 0 35px, rgba(97, 125, 150, 0.14) 36px, transparent 37px),
    radial-gradient(circle at 16% 14%, rgba(132, 86, 49, 0.1), transparent 14%),
    radial-gradient(circle at 82% 76%, rgba(119, 76, 43, 0.1), transparent 16%),
    linear-gradient(135deg, #fff7dc 0%, #f8e7bf 52%, #f3dbad 100%);
}

.notebook-page {
  position: relative;
  z-index: 1;
  min-height: inherit;
  overflow: hidden;
  border: 1px solid rgba(95, 70, 44, 0.22);
  border-radius: 16px 26px 26px 16px;
  padding: clamp(30px, 4vw, 48px) clamp(24px, 5vw, 66px) 36px;
  color: #382d27;
  box-shadow:
    0 24px 58px rgba(0, 0, 0, 0.34),
    inset 20px 0 30px rgba(112, 70, 44, 0.14),
    inset -14px 0 28px rgba(255, 255, 255, 0.44);
  transform-origin: left center;
}

.notebook-page::before,
.page-turn-sheet::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(rgba(92, 62, 42, 0.17) 0.7px, transparent 1px),
    radial-gradient(rgba(255, 255, 255, 0.5) 0.6px, transparent 1px),
    linear-gradient(90deg, rgba(75, 42, 34, 0.14), transparent 16%, transparent 86%, rgba(255, 255, 255, 0.34));
  background-position: 0 0, 7px 5px, 0 0;
  background-size: 14px 12px, 18px 16px, auto;
  mix-blend-mode: multiply;
  opacity: 0.44;
}

.notebook-page::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 22px;
  width: 1px;
  background: rgba(135, 70, 58, 0.24);
  box-shadow: 5px 0 16px rgba(96, 57, 36, 0.12);
}

.notebook-header {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  margin-bottom: 17px;
  color: rgba(87, 70, 54, 0.7);
  font-family: "Ma Shan Zheng", "HanziPen SC", "华文行楷", "STXingkai", "LXGW WenKai", "霞鹜文楷", "STKaiti", "Kaiti SC", "KaiTi", serif;
  font-size: 0.92rem;
  font-weight: 700;
}

.notebook-lines {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
}

.notebook-line {
  min-height: 32px;
  margin: 0;
  opacity: 0;
  transform: translateY(4px);
}

.notebook-line.visible {
  opacity: 1;
  transform: translateY(0);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.line-text {
  overflow-wrap: anywhere;
  font-family: "Ma Shan Zheng", "HanziPen SC", "华文行楷", "STXingkai", "LXGW WenKai", "霞鹜文楷", "STKaiti", "Kaiti SC", "KaiTi", cursive;
  font-size: clamp(1.08rem, 1.84vw, 1.38rem);
  font-weight: 500;
  line-height: 1.65;
  letter-spacing: 0;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.36);
}

.typewriter-caret {
  display: inline-block;
  width: 2px;
  height: 1.15em;
  margin-left: 2px;
  vertical-align: -0.17em;
  background: rgba(64, 45, 34, 0.7);
  animation: caret-blink 0.75s steps(2, start) infinite;
}

.page-turn-sheet {
  position: absolute;
  inset: 0;
  z-index: 2;
  border: 1px solid rgba(95, 70, 44, 0.2);
  border-radius: 16px 26px 26px 16px;
  opacity: 0;
  pointer-events: none;
  transform-origin: left center;
  box-shadow:
    18px 22px 42px rgba(0, 0, 0, 0.32),
    inset -30px 0 42px rgba(255, 255, 255, 0.5),
    inset 22px 0 34px rgba(112, 70, 44, 0.12);
}

.page-turn-sheet::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background:
    linear-gradient(90deg, rgba(62, 37, 27, 0.2), transparent 18%, rgba(255, 255, 255, 0.52) 52%, rgba(83, 49, 34, 0.16) 100%),
    radial-gradient(ellipse at 86% 50%, rgba(255, 255, 255, 0.7), transparent 36%);
  opacity: 0.76;
}

.prologue-notebook-wrap.flipping .page-turn-sheet {
  animation: diary-page-turn 1.18s cubic-bezier(0.38, 0.02, 0.18, 1) both;
}

.prologue-notebook-wrap.flipping .notebook-page {
  animation: diary-page-settle 1.18s ease both;
}

.prologue-notebook-wrap.flipping .notebook-header,
.prologue-notebook-wrap.flipping .notebook-lines {
  opacity: 0;
  transition: opacity 0.08s ease;
}

.prologue-progress {
  position: fixed;
  left: 50%;
  bottom: 28px;
  z-index: 2;
  display: flex;
  max-width: min(540px, calc(100vw - 40px));
  transform: translateX(-50%);
  gap: 5px;
}

.prologue-dot {
  width: 14px;
  height: 3px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.28);
  transition: background 0.25s ease, width 0.25s ease;
}

.prologue-dot.active {
  width: 22px;
  background: rgba(255, 250, 240, 0.86);
}

.prologue-line-enter-active,
.prologue-line-leave-active {
  transition: opacity 0.48s ease, transform 0.48s ease;
}

.prologue-line-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.prologue-line-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@keyframes notebook-arrive {
  from {
    opacity: 0;
    transform: translateY(26px) rotateX(6deg);
  }

  to {
    opacity: 1;
    transform: translateY(0) rotateX(0);
  }
}

@keyframes caret-blink {
  50% {
    opacity: 0;
  }
}

@keyframes diary-page-turn {
  0% {
    opacity: 0;
    transform: rotateY(0deg) translateX(0) translateZ(2px) skewY(0deg);
    filter: brightness(1);
  }

  10% {
    opacity: 0.96;
    transform: rotateY(-18deg) translateX(-2px) translateZ(8px) skewY(-1deg);
  }

  46% {
    opacity: 0.98;
    transform: rotateY(-94deg) translateX(-8px) translateZ(28px) skewY(-2.2deg);
    filter: brightness(0.82);
  }

  68% {
    opacity: 0.88;
    transform: rotateY(-142deg) translateX(-18px) translateZ(18px) skewY(1.4deg);
    filter: brightness(0.96);
  }

  100% {
    opacity: 0;
    transform: rotateY(-178deg) translateX(-28px) translateZ(4px) skewY(0deg);
    filter: brightness(1.06);
  }
}

@keyframes diary-page-settle {
  0% {
    filter: brightness(0.98);
  }

  55% {
    filter: brightness(0.9);
  }

  100% {
    filter: brightness(1);
  }
}

@media (max-width: 740px) {
  .prologue-skip {
    top: 14px;
    right: 14px;
    min-width: 60px;
    padding: 7px 13px;
  }

  .prologue-copy-wrap {
    width: calc(100vw - 24px);
    min-height: 260px;
  }

  .prologue-kicker {
    margin-bottom: 16px;
    font-size: 0.78rem;
  }

  .prologue-line {
    font-size: clamp(0.86rem, 3.7vw, 1.2rem);
    line-height: 1.55;
  }

  .prologue-notebook-wrap {
    width: calc(100vw - 26px);
    min-height: calc(100vh - 86px);
  }

  .notebook-cover {
    inset: 12px -3px -12px 12px;
    border-radius: 14px 20px 20px 14px;
  }

  .notebook-page,
  .page-turn-sheet {
    border-radius: 12px 18px 18px 12px;
  }

  .notebook-page {
    padding: 24px 18px 34px;
  }

  .notebook-page::after {
    left: 13px;
  }

  .notebook-header {
    margin-bottom: 12px;
    font-size: 0.78rem;
  }

  .notebook-lines {
    gap: 5px;
  }

  .notebook-line {
    min-height: 28px;
  }

  .line-text {
    font-size: 0.98rem;
    line-height: 1.55;
  }

  .prologue-progress {
    bottom: 18px;
    gap: 4px;
  }

  .prologue-dot {
    width: 10px;
  }

  .prologue-dot.active {
    width: 16px;
  }
}
</style>
