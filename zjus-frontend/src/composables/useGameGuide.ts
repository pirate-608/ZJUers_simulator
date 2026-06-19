import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import { useGameStore } from '@/stores/gameStore'
import type { WsClientAction } from '@/types/websocket'

const GUIDE_FLAG = 'zjus_guide_shown'

interface GuideStep {
  element: string
  title: string
  description: string
  side?: 'top' | 'bottom' | 'left' | 'right'
  align?: 'start' | 'center' | 'end'
}

const STEPS: GuideStep[] = [
  {
    element: '#tour-game-header',
    title: '🎓 欢迎来到折姜大学',
    description:
      '这里显示你的姓名、专业和当前学期。你将在求是园中度过八个学期的学习生活，努力成为一名优秀的折大人。',
    side: 'bottom',
    align: 'start',
  },
  {
    element: '#hud-bars',
    title: '⚡ 核心状态条',
    description:
      '精力、心态、压力是三大核心状态。IQ 影响学习效率，EQ 与魅力影响社交互动，GPA 决定你的学业成绩。时刻关注这些数值，精力或心态归零游戏即告结束。',
    side: 'bottom',
    align: 'center',
  },
  {
    element: '#tour-course-list',
    title: '📚 课程与策略',
    description:
      '每学期有若干门课程，右侧进度条显示掌握度。你可以为每门课单独设定策略：<b>摆</b>（放弃）、<b>摸</b>（最低投入）、<b>卷</b>（全力冲刺）。不同策略消耗精力的速度不同。',
    side: 'right',
    align: 'start',
  },
  {
    element: '#tour-right-panel',
    title: '☕ 放松与学期进度',
    description:
      '学习累了可以通过放松动作恢复状态。下方倒计时显示学期剩余时间，到期将自动触发期末考试。你也可以手动申请提前考试。',
    side: 'left',
    align: 'start',
  },
  {
    element: '#tour-mid-panel',
    title: '📋 事件日志与钉钉消息',
    description:
      '「求是园动态」标签页记录游戏中发生的所有事件。「钉钉」标签页接收 NPC 私聊和系统通知，记得偶尔查看以免错过重要信息。',
    side: 'left',
    align: 'start',
  },
  {
    element: '#tour-pause-btn',
    title: '⏸️ 暂停与继续',
    description:
      '需要暂时离开时可以暂停游戏。暂停期间游戏时间停止流逝，你不会受到任何消耗。回来时点击继续即可。',
    side: 'bottom',
    align: 'center',
  },
  {
    element: '#tour-save-btn',
    title: '💾 存档与退出',
    description:
      '点击快速保存将当前进度写入服务器。退出时可以选择保存并退出或不保存直接离开。祝你游戏愉快！',
    side: 'bottom',
    align: 'end',
  },
]

export function useGameGuide() {
  const store = useGameStore()

  function startGuide(sendAction?: (payload: WsClientAction) => void) {
    // 仅首次进入 playing 时展示
    if (localStorage.getItem(GUIDE_FLAG)) return
    localStorage.setItem(GUIDE_FLAG, '1')

    // 引导期间显式锁住前端倒计时，并通知后端暂停 tick。
    const wasPaused = store.isPaused
    store.setGuideActive(true)
    if (!wasPaused) {
      store.setPaused(true)
      sendAction?.({ action: 'pause' })
    }

    const driverObj = driver({
      showProgress: true,
      progressText: '{{current}} / {{total}}',
      doneBtnText: '开始游戏 🚀',
      nextBtnText: '下一步 ➔',
      prevBtnText: '← 上一步',
      steps: STEPS.map((step) => ({
        element: step.element,
        popover: {
          title: step.title,
          description: step.description,
          side: step.side || 'bottom',
          align: step.align || 'center',
        },
      })),
      onDestroyed: () => {
        store.setGuideActive(false)
        if (!wasPaused) {
          store.setPaused(false)
          sendAction?.({ action: 'resume' })
        }
      },
    })

    driverObj.drive()
  }

  return { startGuide }
}
