/**
 * Thin, type-safe HTTP API client over generated OpenAPI schemas.
 *
 * Keep this file hand-written. Schema changes should be made in FastAPI models
 * and reflected here through regenerated `api.generated.ts` imports.
 */
import type { components } from '@/types/api.generated'

export type AuthRequest = components['schemas']['AuthRequest']
export type AuthResponse = components['schemas']['AuthResponse']
export type MajorOption = components['schemas']['MajorOption']
export type InitCharacterRequest = components['schemas']['InitCharacterRequest']
export type InitCharacterResponse = components['schemas']['InitCharacterResponse']
export type SaveSummary = components['schemas']['SaveSummary']

/**
 * Authenticate a player with invite code and optional persistent credential.
 */
export async function auth(payload: AuthRequest): Promise<AuthResponse> {
  const res = await fetch('/api/auth', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as AuthResponse
}

/**
 * Fetch all majors available during character creation.
 */
export async function fetchMajors(): Promise<MajorOption[]> {
  const res = await fetch('/api/majors')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as MajorOption[]
}

/**
 * Initialize a character's major and stat allocation.
 */
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

export type AdmissionInfoResponse = components['schemas']['AdmissionInfoResponse']

/**
 * Fetch legacy admission information for compatibility screens.
 */
export async function getAdmissionInfo(token: string): Promise<AdmissionInfoResponse> {
  const res = await fetch('/api/admission_info', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as AdmissionInfoResponse
}
