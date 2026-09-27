import type { SessionEntry } from '@/types/os'

export type SessionSection =
  | 'Hoje'
  | 'Ontem'
  | 'Últimos 7 dias'
  | 'Mais antigas'

export const sessionTimestamp = (value?: number | string | null): number => {
  if (typeof value === 'number')
    return Number.isFinite(value) ? value * (value < 1e12 ? 1000 : 1) : 0
  if (!value) return 0
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : 0
}

export const sessionTime = (entry: SessionEntry): number =>
  sessionTimestamp(entry.updated_at) || sessionTimestamp(entry.created_at)

export const sessionSection = (
  timestamp: number,
  now: number
): SessionSection => {
  if (!timestamp) return 'Mais antigas'
  const date = new Date(timestamp)
  const today = new Date(now)
  const daysAgo = Math.round(
    (Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) -
      Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())) /
      86400000
  )
  if (daysAgo <= 0) return 'Hoje'
  if (daysAgo === 1) return 'Ontem'
  return daysAgo < 7 ? 'Últimos 7 dias' : 'Mais antigas'
}
