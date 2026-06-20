<template>
  <div class="create-wrapper min-vh-100 d-flex flex-column justify-content-center align-items-center px-3 py-4">
    <div v-if="loading" class="text-center fade-in">
      <div class="spinner-border mb-3" style="width: 3rem; height: 3rem; color: #b93a32;" />
      <h4 class="fw-bold text-dark" style="letter-spacing: 2px;">正在初始化角色...</h4>
    </div>

    <div v-else class="content-container fade-in">
      <h2 class="text-center mb-4 fw-bold" style="color: #2e5275;">🎓 创建你的角色</h2>

      <div class="row g-4">
        <!-- 左侧：专业选择 -->
        <div class="col-lg-7">
          <h5 class="fw-bold mb-3">📚 选择专业</h5>
          <div class="major-grid">
            <div
              v-for="m in majors"
              :key="m.abbr"
              class="major-card card border-0 shadow-sm cursor-pointer transition-all p-3"
              :class="{ 'border-primary bg-primary bg-opacity-10': selectedMajor === m.abbr }"
              :style="selectedMajor === m.abbr ? 'border: 2px solid #2f5d88;' : ''"
              @click="selectedMajor = m.abbr"
            >
              <div class="d-flex justify-content-between align-items-start mb-1">
                <span class="fw-bold" style="font-size: 0.95rem;">{{ m.name }}</span>
                <span class="badge bg-secondary">{{ m.abbr }}</span>
              </div>
              <small class="text-muted mb-2 d-block" style="font-size: 0.78rem;">{{ m.desc }}</small>
              <div class="d-flex gap-3 small">
                <span class="text-primary">🧠 IQ +{{ m.iq_buff }}</span>
                <span class="text-danger">😰 压力 {{ m.stress_base }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：属性分配 -->
        <div class="col-lg-5">
          <div class="card border-0 shadow-sm">
            <div class="card-header text-white text-center fw-bold py-2" style="background: linear-gradient(120deg, #2e5275, #3a698f);">
              ⚖️ 属性分配
            </div>
            <div class="card-body">
              <div class="text-center mb-3">
                <span class="fs-4 fw-bold" :class="remainingPoints >= 0 ? 'text-primary' : 'text-danger'">{{ remainingPoints }}</span>
                <span class="text-muted"> 剩余点数</span>
              </div>

              <div
                v-for="stat in ALLOCATABLE_STATS"
                :key="stat.id"
                class="mb-4"
              >
                <div class="d-flex justify-content-between mb-1">
                  <span class="fw-bold small">{{ stat.icon }} {{ stat.label }}</span>
                  <span class="fw-bold small">{{ stats[stat.id] }}</span>
                </div>
                <input type="range" class="form-range" :min="stat.min" :max="stat.max" v-model.number="stats[stat.id]" @input="onSliderChange">
                <div class="d-flex justify-content-between"><small class="text-muted">{{ stat.min }}</small><small class="text-muted">{{ stat.max }}</small></div>
              </div>

              <hr>
              <div class="small text-muted mb-3">
                ⚡ 精力固定 100 ｜ 💖 心态固定 80<br>
                总预算 <b>{{ STAT_INITIAL_BUDGET }}</b> 点，默认 {{ defaultStatsText }}
              </div>

              <button
                class="btn btn-primary btn-lg w-100 fw-bold"
                :disabled="!selectedMajor || remainingPoints !== 0"
                @click="confirmCreate"
              >
                {{ selectedMajor ? `确认入学 · ${selectedMajor}` : '请先选择专业' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useGameStore } from '../stores/gameStore.ts'
import { fetchMajors, initCharacter } from '@/api/client'
import type { MajorOption } from '@/api/client'
import {
  ALLOCATABLE_STATS,
  STAT_INITIAL_BUDGET,
} from '@/data/statDefinitions.generated'

const store = useGameStore()

const loading = ref(true)
const majors = ref<MajorOption[]>([])
const selectedMajor = ref<string | null>(null)

const stats = reactive<Record<string, number>>(
  Object.fromEntries(
    ALLOCATABLE_STATS.map((stat) => [stat.id, stat.default]),
  ),
)

const totalUsed = computed(() => (
  ALLOCATABLE_STATS.reduce(
    (total, stat) => total + Number(stats[stat.id] ?? stat.default),
    0,
  )
))
const remainingPoints = computed(() => STAT_INITIAL_BUDGET - totalUsed.value)
const defaultStatsText = computed(() => (
  ALLOCATABLE_STATS
    .map((stat) => `${stat.label} ${stat.default}`)
    .join(' | ')
))

function onSliderChange() {
  for (const stat of ALLOCATABLE_STATS) {
    stats[stat.id] = Math.min(
      stat.max,
      Math.max(stat.min, Number(stats[stat.id]) || stat.default),
    )
  }
}

onMounted(async () => {
  try {
    majors.value = await fetchMajors()
  } catch (err) {
    console.error('Failed to load majors:', err)
  } finally {
    loading.value = false
  }
})

const confirmCreate = async () => {
  if (!selectedMajor.value) return
  onSliderChange()
  if (remainingPoints.value !== 0) {
    const labels = ALLOCATABLE_STATS.map((stat) => stat.label).join('/')
    alert(`${labels} 初始总点数必须等于 ${STAT_INITIAL_BUDGET}`)
    return
  }
  const jwt = localStorage.getItem('zju_jwt')
  if (!jwt) {
    alert('认证凭据已过期，请重新登录')
    store.setPhase('login')
    return
  }

  loading.value = true
  try {
    const statPayload = Object.fromEntries(
      ALLOCATABLE_STATS.map((stat) => [stat.id, stats[stat.id] ?? stat.default]),
    ) as Record<string, number>
    const payload = {
      token: jwt,
      major_abbr: selectedMajor.value,
      iq: statPayload.iq ?? 100,
      eq: statPayload.eq ?? 100,
      luck: statPayload.luck ?? 50,
      charm: statPayload.charm ?? 50,
      stats: statPayload,
    }
    await initCharacter(payload)
    localStorage.setItem('game_started', '1')
    localStorage.removeItem('selected_save_slot')
    store.setPhase('loading')
  } catch (err) {
    console.error('Init character error:', err)
    if (err instanceof Error && err.message === 'TOKEN_EXPIRED') {
      alert('认证凭据已过期，请重新登录')
      store.setPhase('login')
    } else {
      alert('角色初始化失败，请重试')
    }
    loading.value = false
  }
}
</script>

<style scoped>
.create-wrapper {
  background: linear-gradient(160deg, #f8fbff 0%, #edf3f9 100%);
  min-height: 100vh;
}
.content-container {
  width: 100%;
  max-width: 1100px;
}
.major-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}
.major-card {
  background: rgba(251, 248, 240, 0.94);
  cursor: pointer;
  transition: all 0.2s;
}
.major-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(47, 93, 136, 0.15);
}
.fade-in { animation: fadeIn 0.5s ease-out forwards; }
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}
.major-grid::-webkit-scrollbar { width: 6px; }
.major-grid::-webkit-scrollbar-thumb { background: #b59c87; border-radius: 3px; }
@media (max-width: 768px) {
  .major-grid { max-height: 45vh; }
}
</style>
