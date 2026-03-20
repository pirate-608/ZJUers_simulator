/**
 * 类型安全的 HTTP API 客户端
 * 封装所有与后端 REST API 的交互，入参和返回值均有类型约束。
 */
import type {
  ExamQuestion,
  ExamSubmission,
  ExamResponse,
  QuickLoginPayload,
} from '@/types/api'

// ─── 考试相关 ───

export async function fetchExamQuestions(): Promise<ExamQuestion[]> {
  const res = await fetch('/api/exam/questions')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data: unknown = await res.json()
  // 后端可能返回 { questions: [...] } 或直接 [...]
  if (Array.isArray(data)) return data as ExamQuestion[]
  if (typeof data === 'object' && data !== null && 'questions' in data) {
    return (data as { questions: ExamQuestion[] }).questions
  }
  return []
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

export async function quickLogin(payload: QuickLoginPayload): Promise<ExamResponse> {
  const res = await fetch('/api/exam/quick_login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as ExamResponse
}

// ─── 专业分配 ───

export async function assignMajor(token: string): Promise<string> {
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

  const rawText = await res.text()

  try {
    const jsonObj = JSON.parse(rawText) as unknown
    if (typeof jsonObj === 'string') return jsonObj
    if (typeof jsonObj === 'object' && jsonObj !== null) {
      const obj = jsonObj as Record<string, unknown>
      const major = obj.assigned_major || obj.major || obj.data || obj.result || ''
      return String(major)
    }
  } catch {
    // 非 JSON，直接返回纯文本
  }

  return rawText.replace(/^["']|["']$/g, '').trim()
}

// ─── 入学信息 ───

export async function getAdmissionInfo(token: string): Promise<Record<string, unknown>> {
  const res = await fetch('/api/admission_info', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as Record<string, unknown>
}
