/**
 * 类型安全的 HTTP API 客户端
 */
import type { components } from '@/types/api.generated'

export type AuthRequest = {
  username: string
  invite_code: string
  token?: string | null
  custom_llm_model?: string | null
  custom_llm_api_key?: string | null
  custom_llm_provider?: string | null
}

export type AuthResponse = {
  status: string
  jwt?: string | null
  user_token?: string | null
  username: string
  user_id?: number | null
  message?: string | null
}

export type MajorOption = {
  name: string
  abbr: string
  iq_buff: number
  stress_base: number
  desc: string
}

export type InitCharacterRequest = {
  token: string
  major_abbr: string
  iq: number
  eq: number
  luck: number
}

export type InitCharacterResponse = {
  success: boolean
  major: string
  major_abbr: string
  courses: Record<string, string>[]
}

// ─── 认证 ───

export async function auth(payload: AuthRequest): Promise<AuthResponse> {
  const res = await fetch('/api/auth', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as AuthResponse
}

// ─── 专业列表 ───

export async function fetchMajors(): Promise<MajorOption[]> {
  const res = await fetch('/api/majors')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as MajorOption[]
}

// ─── 初始化角色 ───

export async function initCharacter(payload: InitCharacterRequest): Promise<InitCharacterResponse> {
  const res = await fetch('/api/init_character', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    if (res.status === 401) throw new Error('TOKEN_EXPIRED')
    throw new Error(`HTTP ${res.status}`)
  }
  return (await res.json()) as InitCharacterResponse
}

// ─── 入学信息 ───

export type AdmissionInfoResponse = components['schemas']['AdmissionInfoResponse']

export async function getAdmissionInfo(token: string): Promise<AdmissionInfoResponse> {
  const res = await fetch('/api/admission_info', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as AdmissionInfoResponse
}
