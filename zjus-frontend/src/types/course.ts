/**
 * Runtime progress and strategy state for a single course.
 */
export type CourseProgressUpdate = {
  progress?: number
  state?: number
  [k: string]: unknown
}

/**
 * Runtime course progress keyed by course ID.
 */
export type CoursesMap = Record<string, CourseProgressUpdate>

/**
 * Static course metadata loaded from world data or WebSocket stats.
 */
export type CourseMetadata = {
  id: string
  name: string
  credit: number
  credits?: number
  [k: string]: unknown
}

