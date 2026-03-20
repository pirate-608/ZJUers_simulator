import type { CoursesMap } from './course'
import type { PlayerStats } from './game'
import type { DingTalkMessage, RandomEventModalData, TranscriptModalData } from './modal'

export type WsMessage =
  | { type: 'auth_ok' }
  | { type: 'auth_error'; message?: string }
  | {
      type: 'init'
      data?: Partial<PlayerStats> & {
        course_info_json?: string
        courses?: CoursesMap
      }
      semester_time_left?: number
    }
  | {
      type: 'tick'
      stats?: Partial<PlayerStats>
      courses?: CoursesMap
      course_states?: CoursesMap
      semester_time_left?: number
    }
  | {
      type: 'state'
      data?: Partial<PlayerStats> & { courses?: CoursesMap }
    }
  | { type: 'paused'; msg?: string }
  | { type: 'resumed'; msg?: string }
  | { type: 'event'; data?: { desc?: string }; desc?: string }
  | { type: 'game_over'; data?: { reason?: string }; reason?: string }
  | { type: 'semester_summary'; data?: TranscriptModalData | unknown }
  | { type: 'random_event'; data?: RandomEventModalData | unknown }
  | { type: 'dingtalk_message'; data?: DingTalkMessage | unknown }
  | {
      type: 'graduation'
      data?: {
        // 你现在前端兼容的嵌套结构：msg.data.data.final_stats + msg.data.data.wenyan_report
        data?: {
          final_stats?: Record<string, unknown>
          wenyan_report?: string
        }
        final_stats?: Record<string, unknown>
        wenyan_report?: string
      }
    }
  | { type: 'new_semester'; data?: { semester_name?: string }; semester_name?: string }
  | { type: 'save_result'; message?: string; success?: boolean }
  | { type: 'exit_confirmed' }

export function extractGraduationFinalStats(msg: Extract<WsMessage, { type: 'graduation' }>): {
  finalStats: Record<string, unknown>
  llmSummary?: string
} {
  const candidate = msg.data?.data ?? msg.data
  const finalStats = (candidate?.final_stats && typeof candidate.final_stats === 'object' && candidate.final_stats
    ? candidate.final_stats
    : {}) as Record<string, unknown>
  const llmSummary =
    (typeof candidate?.wenyan_report === 'string' ? candidate.wenyan_report : undefined) ||
    (typeof msg.data?.wenyan_report === 'string' ? msg.data.wenyan_report : undefined)

  return { finalStats, llmSummary }
}

export function extractNewSemesterName(msg: Extract<WsMessage, { type: 'new_semester' }>): string {
  const fromNested = msg.data?.semester_name
  if (typeof fromNested === 'string' && fromNested.trim() !== '') return fromNested
  const fromTop = msg.semester_name
  if (typeof fromTop === 'string' && fromTop.trim() !== '') return fromTop
  return '新学期'
}

// ─── 客户端 → 服务器 动作类型（覆盖全部合法 action） ───

export type RelaxTarget = 'gym' | 'game' | 'walk' | 'cc98'

export type WsClientAction =
  | { action: 'ping' }
  | { action: 'start' }
  | { action: 'pause' }
  | { action: 'resume' }
  | { action: 'get_state' }
  | { action: 'set_speed'; speed: number }
  | { action: 'change_course_state'; target: string; value: number }
  | { action: 'relax'; target: RelaxTarget }
  | { action: 'exam' }
  | { action: 'next_semester' }
  | { action: 'event_choice'; effects: unknown }
  | { action: 'save_game' }
  | { action: 'save_and_exit' }
  | { action: 'exit_without_save' }
  | { action: 'restart' }

// ─── 运行时类型守卫 ───

export function isWsMessage(raw: unknown): raw is WsMessage {
  return typeof raw === 'object' && raw !== null && typeof (raw as Record<string, unknown>).type === 'string'
}
