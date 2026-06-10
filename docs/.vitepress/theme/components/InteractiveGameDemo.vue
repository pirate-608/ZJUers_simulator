<template>
  <section ref="demoRoot" class="interactive-demo">
    <div class="demo-toolbar">
      <div>
        <p>{{ eyebrow }}</p>
        <h3>{{ title }}</h3>
      </div>
      <div class="demo-tabs" aria-label="Demo scenes">
        <button
          v-for="item in modes"
          :key="item.mode"
          type="button"
          :class="{ active: activeMode === item.mode }"
          @click="activeMode = item.mode"
        >
          {{ item.label }}
        </button>
      </div>
    </div>

    <div v-if="activeMode === 'entry'" class="demo-entry">
      <div class="demo-login-card">
        <span class="demo-card-kicker">Invite Code Login</span>
        <h4>欢迎来到折姜大学</h4>
        <label>昵称<input value="折姜新生" readonly></label>
        <label>邀请码<input value="LOCAL_TEST_CODE" readonly></label>
        <label>学生凭证<input placeholder="老玩家返校时填写" readonly></label>
        <button type="button">进入求是园</button>
      </div>
      <div class="demo-entry-copy">
        <h4>序章之后，才会进入登录/存档/角色创建流程。</h4>
        <p>文档 demo 使用静态 mock 状态，不会发送登录请求，也不会建立 WebSocket。</p>
      </div>
    </div>

    <div v-else-if="activeMode === 'character'" class="demo-character">
      <div class="demo-major-list">
        <button
          v-for="major in demoMajors"
          :key="major.abbr"
          type="button"
          :class="{ active: selectedMajor === major.abbr }"
          @click="selectedMajor = major.abbr"
        >
          <span>{{ major.name }}</span>
          <small>{{ major.abbr }} · IQ +{{ major.iq }}</small>
        </button>
      </div>
      <div class="demo-stat-card">
        <h4>初始属性分配</h4>
        <div v-for="stat in demoStats" :key="stat.name" class="demo-stat-row">
          <span>{{ stat.name }}</span>
          <input type="range" min="50" max="150" :value="stat.value" readonly>
          <strong>{{ stat.value }}</strong>
        </div>
        <p>基础点数合计 250，专业加成在创建后额外叠加。</p>
      </div>
    </div>

    <div v-else class="demo-dashboard">
      <HudBar />
      <div class="demo-layout">
        <div class="demo-column left">
          <div class="card mb-3 border-0 shadow-sm h-100">
            <div class="card-header bg-info text-white text-center fw-bold py-2">学在折大</div>
            <div class="card-body p-0">
              <CourseList @send-action="handleAction" />
            </div>
          </div>
        </div>
        <div class="demo-column center">
          <MidPanel @send-action="handleAction" />
        </div>
        <div class="demo-column right">
          <RightPanel @send-action="handleAction" />
        </div>
      </div>

      <div v-if="activeMode === 'event'" class="demo-event-card">
        <span>随机事件</span>
        <h4>社团活动邀请</h4>
        <p>{{ eventResult || '你收到一次临时社团活动邀请。要不要挤出一点时间参加？' }}</p>
        <div>
          <button type="button" @click="chooseEvent('你参加了活动，心态 +4，压力 +3。')">参加</button>
          <button type="button" @click="chooseEvent('你留在图书馆推进课程，掌握度小幅上升。')">继续学习</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import HudBar from '@/components/HudBar.vue'
import CourseList from '@/components/CourseList.vue'
import MidPanel from '@/components/MidPanel.vue'
import RightPanel from '@/components/RightPanel.vue'
import { useGameStore } from '@/stores/gameStore.ts'
import type { WsClientAction } from '@/types/websocket'

type DemoMode = 'entry' | 'character' | 'dashboard' | 'event' | 'dingtalk'

const props = withDefaults(defineProps<{
  mode?: DemoMode
}>(), {
  mode: 'dashboard',
})

const store = useGameStore()
const demoRoot = ref<HTMLElement | null>(null)
const activeMode = ref<DemoMode>(props.mode)
const selectedMajor = ref('CS')
const eventResult = ref('')

const modes: Array<{ mode: DemoMode; label: string }> = [
  { mode: 'entry', label: '入口' },
  { mode: 'character', label: '角色' },
  { mode: 'dashboard', label: '主界面' },
  { mode: 'event', label: '事件' },
  { mode: 'dingtalk', label: '钉钉' },
]

const demoMajors = [
  { name: '计算机科学与技术', abbr: 'CS', iq: 15 },
  { name: '人工智能', abbr: 'AI', iq: 18 },
  { name: '软件工程', abbr: 'SE', iq: 12 },
]

const demoStats = [
  { name: 'IQ', value: 100 },
  { name: 'EQ', value: 80 },
  { name: 'Luck', value: 70 },
]

const title = computed(() => ({
  entry: '登录与返校入口',
  character: '角色创建与属性预算',
  dashboard: '主循环控制台',
  event: '随机事件反馈',
  dingtalk: '钉钉联系人私聊',
}[activeMode.value]))

const eyebrow = computed(() => activeMode.value === 'dingtalk' ? 'Private Chat Demo' : 'Game UI Demo')

function seedGameState() {
  store.setPhase('playing')
  store.setPaused(false)
  store.setGuideActive(false)
  store.setGameSpeed(1)
  store.gameMode = 'hybrid'
  store.llmAvailable = true
  store.semesterTimeLeft = 368
  store.updateStats({
    username: '折姜新生',
    major: '计算机科学与技术',
    major_abbr: 'CS',
    semester: '大一秋冬',
    semester_idx: 1,
    energy: 82,
    sanity: 76,
    stress: 38,
    iq: 115,
    eq: 82,
    luck: 64,
    gpa: 3.72,
    reputation: 4,
    efficiency: 112,
  })
  store.resetForNewSemester([
    { id: 'CS101', name: '程序设计基础', credit: 4 },
    { id: 'MATH101', name: '微积分 I', credit: 5 },
    { id: 'PHY101', name: '大学物理', credit: 3 },
    { id: 'HUM101', name: '写作与沟通', credit: 2 },
  ])
  store.updateCourseProgress({
    CS101: 72,
    MATH101: 58,
    PHY101: 46,
    HUM101: 86,
  })
  store.updateCourseStatesRaw({
    CS101: 2,
    MATH101: 1,
    PHY101: 1,
    HUM101: 0,
  })
  store.clearEventLogs()
  store.addLog('课程', '程序设计基础掌握度上升，效率加成生效。', 'text-success')
  store.addLog('CC98', '有人发帖讨论“绩点焦虑与夜宵自由”。', 'text-primary')
  store.addLog('系统', '距离期末考试还有 06:08。', 'text-muted')
  store.setRelaxCooldowns({ gym: 0, game: 12, walk: 0, cc98: 5 })
  store.setDingTalkState({
    version: 1,
    updated_at: Math.floor(Date.now() / 1000),
    contacts: {
      roommate_luo: {
        contact_id: 'roommate_luo',
        sender: '罗同学',
        role: 'roommate',
        is_replyable: true,
        is_urgent: false,
        unread_count: 2,
        last_message_at: Math.floor(Date.now() / 1000) - 60,
        messages: [
          {
            message_id: 'm1',
            speaker: 'npc',
            content: '今晚要不要一起去食堂？顺便聊聊高数作业。',
            created_at: Math.floor(Date.now() / 1000) - 160,
            round_id: 'r1',
          },
          {
            message_id: 'm2',
            speaker: 'npc',
            content: '我看你压力有点高，别把自己卷坏了。',
            created_at: Math.floor(Date.now() / 1000) - 60,
            round_id: 'r1',
          },
        ],
        pending_options: [
          { option_id: 'o1', text: '走，吃完我再刷题。' },
          { option_id: 'o2', text: '今天先算了，我想早点休息。' },
        ],
        round: { round_id: 'r1', status: 'open', player_reply_count: 1 },
      },
      ta_lin: {
        contact_id: 'ta_lin',
        sender: '林助教',
        role: 'teaching_assistant',
        is_replyable: true,
        is_urgent: true,
        unread_count: 0,
        last_message_at: Math.floor(Date.now() / 1000) - 380,
        messages: [
          {
            message_id: 'm3',
            speaker: 'npc',
            content: '实验报告记得今晚提交，有问题可以先发我。',
            created_at: Math.floor(Date.now() / 1000) - 380,
            round_id: 'r2',
          },
        ],
        pending_options: [],
        round: { round_id: 'r2', status: 'closed', player_reply_count: 0 },
      },
    },
  })
}

function handleAction(payload: WsClientAction) {
  if (payload.action === 'set_speed') {
    store.setGameSpeed(payload.speed)
    return
  }
  if (payload.action === 'set_mode') {
    store.gameMode = payload.mode
    store.addLog('模式', `内容生成模式切换为 ${payload.mode}。`, 'text-info')
    return
  }
  if (payload.action === 'relax') {
    store.setRelaxCooldowns({ ...store.relaxCooldowns, [payload.target]: 18 })
    store.addLog('摸鱼', `${payload.target} 触发了一次演示冷却。`, 'text-success')
    return
  }
  if (payload.action === 'exam') {
    eventResult.value = '你提前参加了期末考试，系统弹出了成绩单预览。'
    store.addLog('期末', '演示中不会真正结算 GPA。', 'text-warning')
    return
  }
  if (payload.action === 'dingtalk_reply') {
    const contact = store.dingtalkContacts[payload.contact_id]
    const option = contact?.pending_options.find(item => item.option_id === payload.option_id)
    if (!contact || !option) return
    const now = Math.floor(Date.now() / 1000)
    contact.messages.push({
      message_id: `player_${now}`,
      speaker: 'player',
      content: option.text,
      created_at: now,
      round_id: contact.round.round_id,
    })
    contact.messages.push({
      message_id: `npc_${now}`,
      speaker: 'npc',
      content: '收到，那我就按这个节奏来。别忘了给自己留一点喘气的时间。',
      created_at: now + 1,
      round_id: contact.round.round_id,
    })
    contact.pending_options = [
      { option_id: `again_${now}`, text: '我会注意的，谢谢你。' },
      { option_id: `study_${now}`, text: '等我把这题做完再说。' },
    ]
    contact.round.player_reply_count += 1
    contact.last_message_at = now + 1
    store.upsertDingTalkContact(contact)
  }
}

function chooseEvent(result: string) {
  eventResult.value = result
  store.addLog('随机事件', result, 'text-info')
}

async function activateDingTalkTab() {
  await nextTick()
  if (activeMode.value !== 'dingtalk' || !demoRoot.value) return
  const button = Array.from(demoRoot.value.querySelectorAll('.mid-panel-card .nav-link'))
    .find(item => item.textContent?.includes('钉钉'))
  button?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
}

onMounted(() => {
  seedGameState()
  activateDingTalkTab()
})

watch(activeMode, async () => {
  eventResult.value = ''
  await activateDingTalkTab()
})
</script>
