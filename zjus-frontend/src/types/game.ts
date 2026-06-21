import type { CoursesMap } from './course'

/**
 * Top-level app phase used by `App.vue` to route the player entry flow.
 */
export type GamePhase = 'login' | 'save_select' | 'character_create' | 'loading' | 'playing' | 'ended'

/**
 * Runtime player stats pushed by the backend.
 *
 * Core fields are typed explicitly, while the index signature allows new
 * stat-registry fields to flow through before every component knows about
 * them.
 */
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
  charm?: number
  gpa?: number
  highest_gpa?: number
  reputation?: number
  efficiency?: number
  gold?: number
  exam_completed?: number
  item_bonuses?: Record<string, number>

  initial_major_abbr?: string
  initial_iq?: number
  initial_eq?: number
  initial_luck?: number
  initial_charm?: number

  courses: CoursesMap

  [k: string]: unknown
}

