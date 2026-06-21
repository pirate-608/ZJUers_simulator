import {
  STAT_META_BY_ID,
  type StatDefinitionMeta,
} from '@/data/statDefinitions.generated'

/**
 * Display helpers backed by generated stat-registry metadata.
 */
const STAT_META = STAT_META_BY_ID as Partial<Record<string, StatDefinitionMeta>>

/**
 * Return generated metadata for a stat ID.
 */
export function getStatMeta(field: string): StatDefinitionMeta | undefined {
  return STAT_META[field]
}

/**
 * Return a user-facing stat label, falling back to the field ID.
 */
export function statLabel(field: string): string {
  return getStatMeta(field)?.label ?? field
}

/**
 * Return a stat icon from generated metadata.
 */
export function statIcon(field: string): string {
  return getStatMeta(field)?.icon ?? ''
}

/**
 * Return a stat default from generated metadata.
 */
export function statDefault(field: string, fallback: number = 0): number {
  return getStatMeta(field)?.default ?? fallback
}

/**
 * Return a stat minimum from generated metadata.
 */
export function statMin(field: string, fallback: number = 0): number {
  return getStatMeta(field)?.min ?? fallback
}

/**
 * Return a stat maximum from generated metadata.
 */
export function statMax(field: string, fallback: number = 100): number {
  return getStatMeta(field)?.max ?? fallback
}

/**
 * Convert unknown payload values into finite numbers.
 */
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

/**
 * Return a stat's normalized percentage within its configured range.
 */
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
