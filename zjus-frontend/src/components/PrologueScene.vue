<template>
  <section
    class="prologue-root"
    :class="`tone-${currentScene.tone}`"
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

    <div class="prologue-copy-wrap">
      <p class="prologue-kicker">
        ZJUers Simulator
      </p>
      <Transition name="prologue-line" mode="out-in">
        <p
          :key="currentIndex"
          class="prologue-line"
          data-testid="prologue-line"
        >
          {{ currentLine }}
        </p>
      </Transition>
    </div>

    <div class="prologue-progress" aria-hidden="true">
      <span
        v-for="(_, index) in PROLOGUE_LINES"
        :key="index"
        class="prologue-dot"
        :class="{ active: index <= currentIndex }"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * Skippable first-visit prologue shown before any normal startup flow.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  getPrologueScene,
  PROLOGUE_IMAGES,
  PROLOGUE_LINES,
} from '@/data/prologue'

const emit = defineEmits<{
  complete: []
}>()

const LINE_DURATION_MS = 2600
const FADE_DURATION_MS = 480

const currentIndex = ref(0)
const currentLine = computed(() => PROLOGUE_LINES[currentIndex.value])
const currentScene = computed(() => getPrologueScene(currentIndex.value))

let lineTimer: ReturnType<typeof setTimeout> | null = null
let fadeTimer: ReturnType<typeof setTimeout> | null = null
let hasFinished = false

const clearTimers = () => {
  if (lineTimer) clearTimeout(lineTimer)
  if (fadeTimer) clearTimeout(fadeTimer)
  lineTimer = null
  fadeTimer = null
}

const finish = () => {
  if (hasFinished) return
  hasFinished = true
  clearTimers()
  emit('complete')
}

const advanceLine = () => {
  clearTimers()
  lineTimer = setTimeout(() => {
    fadeTimer = setTimeout(() => {
      if (currentIndex.value >= PROLOGUE_LINES.length - 1) {
        finish()
        return
      }
      currentIndex.value += 1
      advanceLine()
    }, FADE_DURATION_MS)
  }, LINE_DURATION_MS)
}

onMounted(() => {
  if (typeof Image !== 'undefined') {
    PROLOGUE_IMAGES.forEach((src) => {
      const img = new Image()
      img.src = src
    })
  }
  advanceLine()
})

onUnmounted(clearTimers)
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
  transition: background-image 0.8s ease;
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
    linear-gradient(180deg, rgba(13, 24, 32, 0.16), rgba(13, 24, 32, 0.58)),
    linear-gradient(90deg, rgba(15, 27, 38, 0.42), rgba(40, 55, 56, 0.08), rgba(15, 27, 38, 0.42));
}

.prologue-root.tone-lake::after {
  background:
    linear-gradient(180deg, rgba(8, 12, 18, 0.22), rgba(8, 12, 18, 0.72)),
    linear-gradient(90deg, rgba(7, 12, 22, 0.58), rgba(16, 32, 48, 0.18), rgba(7, 12, 22, 0.5));
}

.prologue-root.tone-sunset::after {
  background:
    linear-gradient(180deg, rgba(26, 18, 16, 0.12), rgba(20, 15, 18, 0.64)),
    linear-gradient(90deg, rgba(26, 20, 22, 0.42), rgba(92, 66, 44, 0.1), rgba(26, 20, 22, 0.42));
}

.prologue-skip {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 2;
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
  width: min(860px, calc(100vw - 48px));
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
  max-width: 820px;
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
  font-size: clamp(1.55rem, 5vw, 3rem);
  font-weight: 700;
  line-height: 1.45;
  letter-spacing: 0;
}

.prologue-progress {
  position: fixed;
  left: 50%;
  bottom: 28px;
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

@media (max-width: 640px) {
  .prologue-skip {
    top: 14px;
    right: 14px;
    min-width: 60px;
    padding: 7px 13px;
  }

  .prologue-copy-wrap {
    width: min(100vw - 32px, 520px);
    min-height: 260px;
  }

  .prologue-kicker {
    margin-bottom: 16px;
    font-size: 0.78rem;
  }

  .prologue-line {
    font-size: 1.55rem;
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
