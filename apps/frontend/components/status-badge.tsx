import * as React from 'react'
import { cn } from '@/lib/utils'

type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'primary'

const toneClasses: Record<Tone, string> = {
  success: 'border-success/30 bg-success/10 text-success',
  warning: 'border-warning/30 bg-warning/10 text-warning',
  danger: 'border-danger/30 bg-danger/10 text-danger',
  info: 'border-info/30 bg-info/10 text-info',
  primary: 'border-primary/30 bg-primary/10 text-primary',
  neutral: 'border-border bg-muted text-muted-foreground',
}

// Central mapping from domain vocabulary -> tone. Learn the color language once.
const statusTone: Record<string, Tone> = {
  // verdicts
  VERIFIED: 'success',
  CONDITIONAL: 'warning',
  REJECTED: 'danger',
  // deployment outcome
  COMMIT: 'success',
  ROLLBACK: 'danger',
  IN_PROGRESS: 'info',
  AWAITING_APPROVAL: 'warning',
  // approval state
  PENDING_APPROVAL: 'warning',
  APPROVED: 'success',
  // causal rank
  PRIMARY: 'primary',
  CONTRIBUTING: 'info',
  CORRELATED: 'neutral',
  UNRELATED: 'neutral',
  // health / connection status
  Healthy: 'success',
  Connected: 'success',
  Degraded: 'warning',
  Testing: 'info',
  'Needs Attention': 'warning',
  Critical: 'danger',
  Failed: 'danger',
  Active: 'warning',
  Resolved: 'success',
  // risk
  Low: 'success',
  Medium: 'warning',
  High: 'danger',
}

export function statusToTone(status: string): Tone {
  return statusTone[status] ?? 'neutral'
}

export function StatusBadge({
  status,
  label,
  tone,
  dot = false,
  className,
}: {
  status: string
  label?: string
  tone?: Tone
  dot?: boolean
  className?: string
}) {
  const resolved = tone ?? statusToTone(status)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium tracking-wide whitespace-nowrap',
        toneClasses[resolved],
        className,
      )}
    >
      {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
      {label ?? status.replace(/_/g, ' ')}
    </span>
  )
}
