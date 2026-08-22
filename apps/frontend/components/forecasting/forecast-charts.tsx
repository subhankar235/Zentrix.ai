'use client'

import * as React from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { BanditArm, CalibrationBucket, ForecastPoint, MaePoint } from '@/types/types'
import { cn } from '@/lib/utils'

const axisStyle = { fontSize: 11, fill: 'var(--muted-foreground)' } as const

function pctTick(v: number) {
  return `${Math.round(v * 100)}%`
}

// ---------------- Degradation forecast curve ----------------

export function ForecastCurveChart({
  curve,
  thresholdDay,
}: {
  curve: ForecastPoint[]
  thresholdDay: number
}) {
  const data = React.useMemo(
    () =>
      curve.map((p) => ({
        ...p,
        bandSpan: Math.round((p.upper - p.lower) * 1000) / 1000,
      })),
    [curve],
  )

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -14 }}>
          <defs>
            <linearGradient id="forecast-band" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-3)" stopOpacity={0.25} />
              <stop offset="100%" stopColor="var(--chart-3)" stopOpacity={0.08} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="day"
            tick={axisStyle}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            tickFormatter={(d: number) => (d === 0 ? 'now' : `day ${d}`)}
          />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tick={axisStyle}
            tickLine={false}
            axisLine={false}
            tickFormatter={pctTick}
          />
          <Tooltip
            cursor={{ stroke: 'var(--border)' }}
            isAnimationActive={false}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload as ForecastPoint
              return (
                <div className="rounded-md border border-border bg-popover px-2.5 py-2 text-xs shadow-lg">
                  <p className="font-medium">{label === 0 ? 'Today' : `Day ${label}`}</p>
                  <p className="tnum mt-1">
                    Probability <span className="font-semibold">{(p.probability * 100).toFixed(0)}%</span>
                  </p>
                  <p className="tnum text-muted-foreground">
                    Range {(p.lower * 100).toFixed(0)}–{(p.upper * 100).toFixed(0)}%
                  </p>
                </div>
              )
            }}
          />
          <ReferenceLine
            x={thresholdDay}
            stroke="var(--warning)"
            strokeDasharray="4 4"
            label={{
              value: 'threshold',
              position: 'insideTopRight',
              fontSize: 10,
              fill: 'var(--warning)',
            }}
          />
          <Area
            dataKey="lower"
            stackId="band"
            stroke="none"
            fill="none"
            isAnimationActive={false}
          />
          <Area
            dataKey="bandSpan"
            stackId="band"
            stroke="none"
            fill="url(#forecast-band)"
            isAnimationActive={false}
          />
          <Line dataKey="probability" stroke="var(--chart-3)" strokeWidth={2} dot={false} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ---------------- Calibration chart ----------------

export function CalibrationChart({ buckets }: { buckets: CalibrationBucket[] }) {
  const data = buckets.map((b) => ({ ...b, label: `${b.predicted}%` }))
  return (
    <div className="h-52 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }} barGap={3}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={axisStyle}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
          />
          <YAxis
            domain={[0, 100]}
            tick={axisStyle}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `${v}%`}
          />
          <Tooltip
            cursor={{ fill: 'var(--muted)', opacity: 0.4 }}
            isAnimationActive={false}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null
              const b = payload[0].payload as CalibrationBucket & { label: string }
              return (
                <div className="rounded-md border border-border bg-popover px-2.5 py-2 text-xs shadow-lg">
                  <p className="font-medium">When we said {label} confident</p>
                  <p className="tnum mt-1">
                    Actually right <span className="font-semibold">{b.actual}%</span> of the time
                  </p>
                  <p className="tnum text-muted-foreground">{b.samples} predictions</p>
                </div>
              )
            }}
          />
          <Bar dataKey="predicted" name="Predicted confidence" fill="var(--chart-4)" radius={[3, 3, 0, 0]} maxBarSize={26} />
          <Bar dataKey="actual" name="Actual coverage" fill="var(--chart-2)" radius={[3, 3, 0, 0]} maxBarSize={26} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ---------------- MAE over model versions ----------------

export function MaeChart({ points }: { points: MaePoint[] }) {
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 6, right: 12, bottom: 0, left: -22 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="version" tick={axisStyle} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
          <YAxis
            domain={[0, 'auto']}
            tick={axisStyle}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => v.toFixed(2)}
          />
          <Tooltip
            cursor={{ stroke: 'var(--border)' }}
            isAnimationActive={false}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload as MaePoint
              return (
                <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs shadow-lg">
                  <span className="font-medium">{p.version}</span>{' '}
                  <span className="tnum text-muted-foreground">MAE {p.mae.toFixed(3)}</span>
                </div>
              )
            }}
          />
          <Line
            type="monotone"
            dataKey="mae"
            stroke="var(--chart-2)"
            strokeWidth={2}
            dot={{ r: 2.5, fill: 'var(--chart-2)' }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ---------------- Bandit / strategy selector ----------------

export function BanditPanel({ arms }: { arms: BanditArm[] }) {
  const sorted = [...arms].sort((a, b) => b.reward - a.reward)
  const best = sorted[0]

  return (
    <div className="space-y-2.5">
      {sorted.map((a) => (
        <div key={a.strategy} className="space-y-1">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span className={cn('truncate', a.strategy === best.strategy && 'font-medium')}>
              {a.strategy}
            </span>
            <span className="tnum shrink-0 text-muted-foreground">
              {(a.reward * 100).toFixed(0)}% · {a.pulls} pulls
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                'h-full rounded-full',
                a.strategy === best.strategy ? 'bg-success' : 'bg-primary/60',
              )}
              style={{ width: `${Math.round(a.reward * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
