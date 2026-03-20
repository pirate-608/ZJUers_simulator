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
  text: string
  effects: unknown
}

export interface RandomEventModalData {
  title: string
  desc: string
  options?: RandomEventOption[]
  [k: string]: unknown
}

export interface DingTalkMessage {
  sender?: string
  role: string
  content: string
  is_urgent?: boolean
  [k: string]: unknown
}

export type ModalData = TranscriptModalData | RandomEventModalData | DingTalkMessage | Record<string, unknown>

