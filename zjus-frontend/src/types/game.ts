import type { CoursesMap } from './course'

export type GamePhase = 'login' | 'admission' | 'loading' | 'playing' | 'ended'

// 后端会推送一个“当前学期/角色”的大对象，这里先按你现有字段做一个尽量宽松的定义。
// 重点是把关键数值字段收口，避免后续迁移时各处散落类型。
export interface PlayerStats {
  username?: string
  major?: string
  major_abbr?: string
  semester?: string
  semester_idx?: number
  semester_start_time?: number

  energy?: number
  sanity?: number
  stress?: number

  iq?: number
  eq?: number
  luck?: number
  gpa?: number
  highest_gpa?: number
  reputation?: number
  efficiency?: number

  courses: CoursesMap

  // 兼容后端可能新增字段
  [k: string]: unknown
}

