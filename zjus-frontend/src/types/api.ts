// ─── HTTP API 类型定义（对齐后端 Pydantic 模型） ───

export interface ExamQuestion {
  id: string | number
  content: string
  score: number
  options?: string[]
  [k: string]: unknown
}

export interface ExamSubmission {
  username: string
  answers: Record<string, string>
  token?: string | null
  custom_llm_provider?: string | null
  custom_llm_model?: string | null
  custom_llm_api_key?: string | null
}

export interface ExamResponse {
  status: string
  score?: number | null
  tier?: string | null
  token?: string | null
  message?: string | null
}

export interface QuickLoginPayload {
  username: string
  token: string
  custom_llm_provider?: string | null
  custom_llm_model?: string | null
  custom_llm_api_key?: string | null
}

export interface AssignMajorResponse {
  assigned_major?: string
  major?: string
  data?: string
  result?: string
  [k: string]: unknown
}

export interface AdmissionInfo {
  username?: string
  major?: string
  [k: string]: unknown
}
