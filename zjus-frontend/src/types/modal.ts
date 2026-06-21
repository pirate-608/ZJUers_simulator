/**
 * One course row in an end-of-semester transcript modal.
 */
export interface TranscriptModalCourseRow {
  name: string
  credit?: number
  credits?: number
  progress?: number
  grade: number
  gpa?: number
}

/**
 * User-facing achievement details.
 */
export interface AchievementSummary {
  code: string
  name: string
  desc?: string
  icon?: string
}

/**
 * Transcript payload emitted after final-exam settlement.
 */
export interface TranscriptModalData {
  semester_name?: string
  term_gpa?: number
  cgpa?: number
  gold_earned?: number
  courses?: TranscriptModalCourseRow[]
  achievements?: AchievementSummary[]
  [k: string]: unknown
}

/**
 * One selectable option in a random-event modal.
 */
export interface RandomEventOption {
  id?: string
  text: string
  effects: unknown
}

/**
 * Random-event modal payload emitted by the backend.
 */
export interface RandomEventModalData {
  title: string
  desc: string
  options?: RandomEventOption[]
  [k: string]: unknown
}

/**
 * Backward-compatible DingTalk message shape from the old single-message UI.
 */
export interface DingTalkLegacyMessage {
  sender?: string
  role: string
  content: string
  is_urgent?: boolean
  [k: string]: unknown
}

/**
 * Player reply option for an open DingTalk conversation round.
 */
export interface DingTalkReplyOption {
  option_id: string
  text: string
}

/**
 * Persisted private-message entry in a DingTalk thread.
 */
export interface DingTalkThreadMessage {
  message_id: string
  speaker: 'npc' | 'player' | 'system'
  content: string
  created_at: number
  round_id?: string | null
}

/**
 * Conversation-round state used for three-reply settlement.
 */
export interface DingTalkRoundState {
  round_id: string
  status: 'open' | 'closed'
  player_reply_count: number
}

/**
 * DingTalk contact thread shown in the private-message list.
 */
export interface DingTalkContact {
  contact_id: string
  sender: string
  role: string
  is_replyable: boolean
  is_urgent?: boolean
  unread_count: number
  last_message_at: number
  messages: DingTalkThreadMessage[]
  pending_options: DingTalkReplyOption[]
  round: DingTalkRoundState
}

/**
 * Full DingTalk inbox state synchronized from the backend.
 */
export interface DingTalkState {
  version: number
  contacts: Record<string, DingTalkContact>
  updated_at: number
}

export type DingTalkMessage = DingTalkLegacyMessage

/**
 * One numeric change displayed in feedback modals.
 */
export interface FeedbackChange {
  field: string
  label: string
  delta: number
  value?: number | string
  unit?: string
}

/**
 * Generic feedback modal payload for events, relax actions, and DingTalk effects.
 */
export interface FeedbackModalData {
  title: string
  message: string
  kind?: 'event' | 'relax' | 'info' | 'warning'
  autoCloseMs?: number
  changes?: FeedbackChange[]
  [k: string]: unknown
}

/**
 * Union of modal payloads stored by the global game store.
 */
export type ModalData = TranscriptModalData | RandomEventModalData | DingTalkMessage | DingTalkContact | FeedbackModalData | Record<string, unknown>

