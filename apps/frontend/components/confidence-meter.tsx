import * as React from 'react'
import { cn } from '@/lib/utils'

function tone(pct: number) {
  if (pct >= 75) return { bar: 'bg-success', text: 'text-success' }
  if (pct >= 50) return { bar: 'bg-warning', text: 'text-warning' }
  return { bar: 'bg-danger', text: 'text-danger' }
}

export function ConfidenceMeter({
  value,
  size = 'md',
  showLabel = true,
  className,
}: {
  value: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  className?: string
}) {
  const t = tone(value)
  const height = size === 'lg' ? 'h-2.5' : size === 'sm' ? 'h-1.5' : 'h-2'
  const width = size === 'lg' ? 'w-full' : size === 'sm' ? 'w-16' : 'w-24'
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div
        className={cn('overflow-hidden rounded-full bg-muted', height, width)}
        role="meter"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Confidence"
      >
        <div className={cn('h-full rounded-full', t.bar)} style={{ width: `${value}%` }} />
      </div>
      {showLabel ? (
        <span className={cn('tnum text-xs font-semibold', t.text)}>{value}%</span>
      ) : null}
    </div>
  )
}
