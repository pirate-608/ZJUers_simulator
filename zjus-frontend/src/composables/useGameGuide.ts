/**
 * First-play guide orchestration.
 *
 * The guide pauses both frontend countdowns and backend ticking while driver.js
 * walks the player through the main console.
 */
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import { useGameStore } from '@/stores/gameStore'
import type { WsClientAction } from '@/types/websocket'
import { statLabel } from '@/utils/statDisplay'

const GUIDE_FLAG = 'zjus_guide_shown'

interface GuideStep {
  /** CSS selector for the highlighted UI element. */
  element: string
  title: string
  description: string
  side?: 'top' | 'bottom' | 'left' | 'right'
  align?: 'start' | 'center' | 'end'
}

const coreStateLabels = ['energy', 'sanity', 'stress'].map(statLabel).join('、')
const learningStatLabel = statLabel('iq')
const efficiencyStatLabel = statLabel('efficiency')
const socialStatLabels = [statLabel('eq'), statLabel('charm'), statLabel('luck')].join('、')
const goldLabel = statLabel('gold')
const reputationLabel = statLabel('reputation')

const STEPS: GuideStep[] = [
  {
    element: '#tour-game-header',
    title: '🎓 欢迎来到折姜大学',
    description:
      '这里显示你的姓名、专业和当前学期。你将在求是园中度过八个学期：每学期选策略、过事件、看成绩，最后走向毕业或 Game Over。',
    side: 'bottom',
    align: 'start',
  },
  {
    element: '#hud-bars',
    title: '⚡ 核心状态条',
    description:
      `${coreStateLabels}是生存核心，${statLabel('energy')}或${statLabel('sanity')}归零会结束本局。${learningStatLabel}影响${efficiencyStatLabel}，${socialStatLabels}和${reputationLabel}会参与事件、钉钉与成就；${goldLabel}可用来购买道具。`,
    side: 'bottom',
    align: 'center',
  },
  {
    element: '#tour-course-list',
    title: '📚 课程与策略',
    description:
      '每门课都有学分和掌握度，期末 GPA 会按学分加权。你可以为每门课设定 <b>摆</b>、<b>摸</b>、<b>卷</b> 三种策略；卷得越狠成长越快，但精力与压力成本也更高。',
    side: 'right',
    align: 'start',
  },
  {
    element: '#tour-right-panel',
    title: '☕ 放松、期末与内容模式',
    description:
      '摸鱼休闲有独立冷却，结果会弹窗列出实际数值变化；正向收益到顶时会尽量转移到其他状态。倒计时结束会自动期末，手动期末会先确认。下方还能切换算法、混合和 AI 内容模式。',
    side: 'left',
    align: 'start',
  },
  {
    element: '#tour-mid-panel',
    title: '📋 动态、钉钉与道具',
    description:
      '「求是园动态」记录事件和反馈；「钉钉」是联系人私聊，有红点就说明有新消息，三次回复算一轮并可能结算影响；「道具」可搜索、购买或出售持有即生效的加成道具。',
    side: 'left',
    align: 'start',
  },
  {
    element: '#tour-pause-btn',
    title: '⏸️ 暂停与继续',
    description:
      '需要离开时可以暂停。暂停期间倒计时、精力消耗、随机事件和钉钉推送都会停住，休闲、考试、课程策略、钉钉回复和道具买卖也会锁定。',
    side: 'bottom',
    align: 'center',
  },
  {
    element: '#tour-save-btn',
    title: '💾 存档与退出',
    description:
      '点击快速保存会把进度写入服务器。期末后会显示本学期 GPA、累计 GPA、金币收入和新解锁成就；进入新学期时课程会刷新，精力会向默认值回调一半。祝你游戏愉快！',
    side: 'bottom',
    align: 'end',
  },
]

/**
 * Create guide controls for the playing phase.
 */
export function useGameGuide() {
  const store = useGameStore()

  /**
   * Start the guide once and resume the previous pause state afterward.
   */
  function startGuide(sendAction?: (payload: WsClientAction) => void) {
    if (localStorage.getItem(GUIDE_FLAG)) return
    localStorage.setItem(GUIDE_FLAG, '1')

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
