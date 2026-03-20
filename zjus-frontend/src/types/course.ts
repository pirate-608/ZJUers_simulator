export type CourseProgressUpdate = {
  progress?: number
  state?: number
  // 后端未来可能会扩展更多字段，先保留通道
  [k: string]: unknown
}

export type CoursesMap = Record<string, CourseProgressUpdate>

export type CourseMetadata = {
  id: string
  name: string
  credit: number
  [k: string]: unknown
}

