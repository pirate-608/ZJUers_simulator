import {
  STAT_META_BY_ID,
  type StatDefinitionMeta,
} from '@/data/statDefinitions.generated'

const STAT_META = STAT_META_BY_ID as Partial<Record<string, StatDefinitionMeta>>

export function getStatMeta(field: string): StatDefinitionMeta | undefined {
  return STAT_META[field]
}

export function statLabel(field: string): string {
  return getStatMeta(field)?.label ?? field
}

export function statIcon(field: string): string {
  return getStatMeta(field)?.icon ?? ''
}

export function statDefault(field: string, fallback: number = 0): number {
  return getStatMeta(field)?.default ?? fallback
}

export function statMin(field: string, fallback: number = 0): number {
  return getStatMeta(field)?.min ?? fallback
}

export function statMax(field: string, fallback: number = 100): number {
  return getStatMeta(field)?.max ?? fallback
}

export function safeNumber(value: unknown, fallback: number = 0): number {
  if (value === null || value === undefined) return fallback
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function statValue(
  stats: Record<string, unknown>,
  field: string,
  fallback?: number,
): number {
  return safeNumber(stats[field], fallback ?? statDefault(field))
}

export function statPercent(stats: Record<string, unknown>, field: string): number {
  const min = statMin(field)
  const max = statMax(field)
  if (max <= min) return 0
  const raw = statValue(stats, field)
  return Math.min(100, Math.max(0, ((raw - min) / (max - min)) * 100))
}

export function formatStatValue(
  stats: Record<string, unknown>,
  field: string,
  options: { floor?: boolean; showMax?: boolean } = {},
): string {
  const value = options.floor === false
    ? statValue(stats, field)
    : Math.floor(statValue(stats, field))
  if (!options.showMax) return String(value)
  return `${value} / ${statMax(field)}`
}
