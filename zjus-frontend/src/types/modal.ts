export interface TranscriptModalCourseRow {
  name: string
  credit: number
  progress?: number
  grade: number
  gpa?: number
}

export interface TranscriptModalData {
  semester_name?: string
  term_gpa?: number
  cgpa?: number
  gold_earned?: number
  courses?: TranscriptModalCourseRow[]
  [k: string]: unknown
}

export interface RandomEventOption {
  id?: string
  text: string
  effects: unknown
}

export interface RandomEventModalData {
  title: string
  desc: string
  options?: RandomEventOption[]
  [k: string]: unknown
}

export interface DingTalkLegacyMessage {
  sender?: string
  role: string
  content: string
  is_urgent?: boolean
  [k: string]: unknown
}

export interface DingTalkReplyOption {
  option_id: string
  text: string
}

export interface DingTalkThreadMessage {
  message_id: string
  speaker: 'npc' | 'player' | 'system'
  content: string
  created_at: number
  round_id?: string | null
}

export interface DingTalkRoundState {
  round_id: string
  status: 'open' | 'closed'
  player_reply_count: number
}

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

export interface DingTalkState {
  version: number
  contacts: Record<string, DingTalkContact>
  updated_at: number
}

export type DingTalkMessage = DingTalkLegacyMessage

export interface FeedbackChange {
  field: string
  label: string
  delta: number
  value?: number | string
  unit?: string
}

export interface FeedbackModalData {
  title: string
  message: string
  kind?: 'event' | 'relax' | 'info' | 'warning'
  autoCloseMs?: number
  changes?: FeedbackChange[]
  [k: string]: unknown
}

export type ModalData = TranscriptModalData | RandomEventModalData | DingTalkMessage | DingTalkContact | FeedbackModalData | Record<string, unknown>

