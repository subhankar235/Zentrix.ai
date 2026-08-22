export function relativeTime(iso: string): string {
  const timestamp = new Date(iso).getTime()
  if (!Number.isFinite(timestamp)) return 'unknown'

  const diff = Math.max(0, Date.now() - timestamp)
  const s = Math.round(diff / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  return `${d}d ago`
}

export function absoluteTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  })
}

export function pct(n: number, digits = 0): string {
  return `${n.toFixed(digits)}%`
}

export function usd(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

export function num(n: number): string {
  return n.toLocaleString('en-US')
}

export function deltaPct(baseline: number, candidate: number, betterWhenLower: boolean): {
  label: string
  improved: boolean
} {
  if (baseline === 0) return { label: '—', improved: false }
  const change = ((candidate - baseline) / baseline) * 100
  const improved = betterWhenLower ? change < 0 : change > 0
  const sign = change > 0 ? '+' : ''
  return { label: `${sign}${change.toFixed(1)}%`, improved }
}
