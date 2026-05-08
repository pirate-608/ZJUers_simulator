/**
 * 类型安全的 HTTP API 客户端
 * 使用从 OpenAPI schema 生成的类型，与后端 Pydantic response_model 保持一致。
 */
import type { components } from '@/types/api.generated'

export type ExamQuestion = components['schemas']['ExamQuestion']
export type ExamSubmission = components['schemas']['ExamSubmission']
export type ExamResponse = components['schemas']['ExamResponse']
export type QuickLoginRequest = components['schemas']['QuickLoginRequest']
export type QuickLoginResponse = components['schemas']['QuickLoginResponse']
export type AssignMajorResponse = components['schemas']['AssignMajorResponse']
export type AdmissionInfoResponse = components['schemas']['AdmissionInfoResponse']

// ─── 考试相关 ───

export async function fetchExamQuestions(): Promise<ExamQuestion[]> {
  const res = await fetch('/api/exam/questions')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as ExamQuestion[]
}

export async function submitExam(payload: ExamSubmission): Promise<ExamResponse> {
  const res = await fetch('/api/exam/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (res.status === 422) {
    const errData = await res.json()
    console.error('422 Validation Error:', errData.detail)
    throw new Error('参数校验失败')
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as ExamResponse
}

export async function quickLogin(payload: QuickLoginRequest): Promise<QuickLoginResponse> {
  const res = await fetch('/api/exam/quick_login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as QuickLoginResponse
}

// ─── 专业分配 ───

export async function assignMajor(token: string): Promise<AssignMajorResponse> {
  const res = await fetch('/api/assign_major', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ token }),
  })

  if (!res.ok) {
    if (res.status === 401 || res.status === 404) {
      throw new Error('TOKEN_EXPIRED')
    }
    throw new Error(`HTTP ${res.status}`)
  }

  return (await res.json()) as AssignMajorResponse
}

// ─── 入学信息 ───

export async function getAdmissionInfo(token: string): Promise<AdmissionInfoResponse> {
  const res = await fetch('/api/admission_info', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as AdmissionInfoResponse
}
