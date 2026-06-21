import type { CoursesMap } from './course'
import type { PlayerStats } from './game'
import type { ItemsState } from './items'
import type { AchievementSummary, DingTalkContact, DingTalkMessage, DingTalkState, FeedbackModalData, RandomEventModalData, TranscriptModalData } from './modal'

/**
 * Server-to-client game WebSocket messages accepted by the frontend store.
 */
export type WsMessage =
  | { type: 'auth_ok' }
  | { type: 'auth_error'; message?: string }
  | {
      type: 'init'
      data?: Partial<PlayerStats> & {
        course_info_json?: string
        courses?: CoursesMap
      }
      courses?: CoursesMap
      course_states?: CoursesMap
      semester_time_left?: number
      relax_cooldowns?: Record<RelaxTarget, number>
      dingtalk_state?: DingTalkState | unknown
      items_state?: ItemsState | unknown
    }
  | {
      type: 'tick'
      stats?: Partial<PlayerStats>
      courses?: CoursesMap
      course_states?: CoursesMap
      semester_time_left?: number
      relax_cooldowns?: Record<RelaxTarget, number>
    }
  | {
      type: 'state'
      data?: Partial<PlayerStats> & { courses?: CoursesMap }
      relax_cooldowns?: Record<RelaxTarget, number>
    }
  | { type: 'paused'; msg?: string }
  | { type: 'resumed'; msg?: string }
  | { type: 'event'; data?: { desc?: string }; desc?: string }
  | { type: 'feedback'; data?: FeedbackModalData | unknown }
  | { type: 'game_over'; data?: { reason?: string }; reason?: string }
  | { type: 'semester_summary'; data?: TranscriptModalData | unknown }
  | { type: 'random_event'; data?: RandomEventModalData | unknown }
  | { type: 'dingtalk_message'; data?: DingTalkMessage | unknown }
  | { type: 'dingtalk_state'; state?: DingTalkState | unknown; data?: DingTalkState | unknown }
  | { type: 'dingtalk_thread_update'; contact?: DingTalkContact | unknown; data?: { contact?: DingTalkContact } | unknown }
  | { type: 'dingtalk_effect'; contact_id?: string; summary?: string; effects?: unknown }
  | { type: 'items_state'; data?: ItemsState | unknown }
  | { type: 'achievement_unlocked'; data?: AchievementSummary | unknown }
  | {
      type: 'graduation'
      data?: {
        data?: {
          final_stats?: Record<string, unknown>
          wenyan_report?: string
        }
        final_stats?: Record<string, unknown>
        wenyan_report?: string
      }
    }
  | {
      type: 'new_semester'
      data?: {
        semester_name?: string
        course_info_json?: string
        stats?: Partial<PlayerStats>
        courses?: CoursesMap
        course_states?: CoursesMap
        semester_time_left?: number
      }
      semester_name?: string
    }
  | { type: 'mode_changed'; mode?: string; llm_available?: boolean; data?: { mode?: string; llm_available?: boolean } }
  | { type: 'toast'; message?: string; level?: string; data?: { message?: string; level?: string } }
  | { type: 'save_result'; message?: string; success?: boolean }
  | { type: 'exit_confirmed' }

/**
 * Extract final stats from both legacy and current graduation payload shapes.
 */
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

/**
 * Extract the semester label from nested or top-level transition payloads.
 */
export function extractNewSemesterName(msg: Extract<WsMessage, { type: 'new_semester' }>): string {
  const fromNested = msg.data?.semester_name
  if (typeof fromNested === 'string' && fromNested.trim() !== '') return fromNested
  const fromTop = msg.semester_name
  if (typeof fromTop === 'string' && fromTop.trim() !== '') return fromTop
  return '新学期'
}

/**
 * Relax action targets accepted by the backend.
 */
export type RelaxTarget = 'gym' | 'game' | 'walk' | 'cc98'

/**
 * Client-to-server WebSocket actions currently emitted by the UI.
 */
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
  | { action: 'event_choice'; option_id: string }
  | { action: 'save_game' }
  | { action: 'save_and_exit' }
  | { action: 'exit_without_save' }
  | { action: 'set_mode'; mode: 'library' | 'ai' | 'hybrid' }
  | { action: 'dingtalk_mark_read'; contact_id: string }
  | { action: 'dingtalk_reply'; contact_id: string; option_id: string }
  | { action: 'item_buy'; item_id: string }
  | { action: 'item_sell'; item_id: string }
  | { action: 'restart' }

/**
 * Runtime guard for parsed WebSocket messages.
 */
export function isWsMessage(raw: unknown): raw is WsMessage {
  return typeof raw === 'object' && raw !== null && typeof (raw as Record<string, unknown>).type === 'string'
}
