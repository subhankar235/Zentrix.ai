'use client'

import * as React from 'react'
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export type MetricSample = { t: number; value: number }

const toneVar: Record<string, string> = {
  primary: 'var(--chart-1)',
  success: 'var(--chart-2)',
  warning: 'var(--chart-3)',
  danger: 'var(--chart-5)',
  info: 'var(--chart-4)',
}

function ChartTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean
  payload?: Array<{ value: number }>
  unit: string
}) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs shadow-lg">
      <span className="tnum font-semibold text-popover-foreground">
        {payload[0].value.toFixed(unit === 'ms' || unit === '%' ? 1 : 0)}
      </span>
      <span className="ml-1 text-muted-foreground">{unit}</span>
    </div>
  )
}

export function MetricChart({
  label,
  unit,
  data,
  current,
  tone = 'primary',
  threshold,
  format,
  className,
}: {
  label: string
  unit: string
  data: MetricSample[]
  current: number
  tone?: keyof typeof toneVar
  threshold?: number
  format?: (n: number) => string
  className?: string
}) {
  const gid = React.useId()
  const color = toneVar[tone]
  const breached = threshold != null && current >= threshold
  const display = format ? format(current) : current.toFixed(unit === 'ms' || unit === '%' ? 1 : 0)

  return (
    <Card className={cn('flex flex-col gap-3 p-4', className)}>
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {label}
          </span>
          {breached ? (
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-danger" />
          ) : null}
        </div>
        <div className="flex items-baseline gap-1">
          <span
            className={cn(
              'tnum text-lg font-semibold tabular-nums',
              breached ? 'text-danger' : 'text-foreground',
            )}
          >
            {display}
          </span>
          <span className="text-xs text-muted-foreground">{unit}</span>
        </div>
      </div>
      <div className="h-16 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="t" hide />
            <YAxis hide domain={['dataMin - 1', 'dataMax + 1']} />
            <Tooltip
              content={<ChartTooltip unit={unit} />}
              cursor={{ stroke: 'var(--border)', strokeWidth: 1 }}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#${gid})`}
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
