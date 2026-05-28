/**
 * 类型安全的 HTTP API 客户端
 */
import type { components } from '@/types/api.generated'

export type AuthRequest = components['schemas']['AuthRequest']
export type AuthResponse = components['schemas']['AuthResponse']
export type MajorOption = components['schemas']['MajorOption']
export type InitCharacterRequest = components['schemas']['InitCharacterRequest']
export type InitCharacterResponse = components['schemas']['InitCharacterResponse']
export type SaveSummary = components['schemas']['SaveSummary']

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
