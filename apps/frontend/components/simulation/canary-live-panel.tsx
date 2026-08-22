'use client'

import * as React from 'react'
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  YAxis,
} from 'recharts'
import { CheckCircle2, Radio, Undo2 } from 'lucide-react'
import type { CanaryPoint } from '@/types/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { cn } from '@/lib/utils'

const POINTS = 14
const TICK_MS = 700

type Seed = Pick<
  CanaryPoint,
  'p50' | 'p95' | 'p99' | 'errorRate' | 'lockWaits' | 'cpu' | 'throughput'
>

function next(prev: number, jitterPct: number, min = 0): number {
  const v = prev + prev * ((Math.random() - 0.48) * jitterPct)
  return Math.max(min, Math.round(v * 100) / 100)
}

export function CanaryLivePanel({
  seed,
  outcome = 'COMMIT',
  rollbackReason,
  onComplete,
}: {
  seed: Seed
  outcome?: 'COMMIT' | 'ROLLBACK'
  rollbackReason?: string
  onComplete?: () => void
}) {
  const [points, setPoints] = React.useState<CanaryPoint[]>([])
  const intervalRef = React.useRef<ReturnType<typeof setInterval> | null>(null)

  React.useEffect(() => {
    intervalRef.current = setInterval(() => {
      setPoints((prev) => {
        if (prev.length >= POINTS) return prev
        const last: CanaryPoint = prev[prev.length - 1] ?? { t: 0, ...seed }
        const np: CanaryPoint = {
          t: prev.length + 1,
          p50: next(last.p50, 0.08),
          p95: next(last.p95, 0.09),
          p99: next(last.p99, 0.1),
          errorRate: Math.round(next(last.errorRate, 0.5, 0) * 100) / 100,
          lockWaits: Math.max(0, Math.round(next(last.lockWaits, 0.3))),
          cpu: Math.min(100, Math.round(next(last.cpu, 0.06))),
          throughput: Math.round(next(last.throughput, 0.05)),
        }
        return [...prev, np]
      })
    }, TICK_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const finished = points.length >= POINTS
  const doneRef = React.useRef(false)

  React.useEffect(() => {
    if (!finished || doneRef.current) return
    doneRef.current = true
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    onComplete?.()
  }, [finished, onComplete])

  const progress = Math.min(1, points.length / POINTS)

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <Radio
              className={cn(
                'h-4 w-4',
                finished ? 'text-muted-foreground' : 'animate-pulse text-info',
              )}
            />
            Live canary — monitoring window
          </CardTitle>
          <div className="flex items-center gap-2">
            {finished ? (
              <StatusBadge status={outcome} dot />
            ) : (
              <span className="tnum text-xs text-muted-foreground">
                {(points.length * TICK_MS) / 1000}s / {(POINTS * TICK_MS) / 1000}s
              </span>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {!finished ? (
          <div className="h-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-info transition-all duration-500"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
        ) : null}

        {finished ? (
          outcome === 'COMMIT' ? (
            <div className="flex items-start gap-3 rounded-lg border border-success/30 bg-success/10 p-4">
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
              <div>
                <p className="text-sm font-semibold text-success">Canary passed — COMMIT</p>
                <p className="mt-0.5 text-xs text-muted-foreground text-pretty">
                  All guardrail metrics stayed within thresholds for the full window. The change is
                  promoted and the outcome is recorded in the audit trail.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-3 rounded-lg border border-danger/30 bg-danger/10 p-4">
              <Undo2 className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
              <div>
                <p className="text-sm font-semibold text-danger">Threshold breached — ROLLBACK</p>
                <p className="mt-0.5 text-xs text-muted-foreground text-pretty">
                  {rollbackReason ??
                    'Guardrail metrics breached policy limits during the window. The change was automatically reverted with no manual intervention required.'}
                </p>
              </div>
            </div>
          )
        ) : null}

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <CanaryTile label="p50 latency" unit="ms" dataKey="p50" digits={0} points={points} tone="var(--chart-1)" />
          <CanaryTile label="p95 latency" unit="ms" dataKey="p95" digits={0} points={points} tone="var(--chart-3)" />
          <CanaryTile label="p99 latency" unit="ms" dataKey="p99" digits={0} points={points} tone="var(--chart-5)" />
          <CanaryTile label="Error rate" unit="%" dataKey="errorRate" digits={2} points={points} tone="var(--chart-2)" />
          <CanaryTile label="Lock waits" unit="" dataKey="lockWaits" digits={0} points={points} tone="var(--chart-4)" />
          <CanaryTile label="CPU" unit="%" dataKey="cpu" digits={0} points={points} tone="var(--chart-1)" />
          <CanaryTile label="Throughput" unit="tps" dataKey="throughput" digits={0} points={points} tone="var(--chart-2)" />
          <div className="rounded-lg border border-border bg-background/40 p-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Samples</p>
            <p className="tnum mt-1 text-xl font-semibold">{points.length}</p>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              of {POINTS} in window
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function CanaryTile({
  label,
  unit,
  dataKey,
  digits,
  points,
  tone,
}: {
  label: string
  unit: string
  dataKey: keyof Omit<CanaryPoint, 't'>
  digits: number
  points: CanaryPoint[]
  tone: string
}) {
  const last = points[points.length - 1]
  const value = last ? last[dataKey] : null

  return (
    <div className="space-y-1 rounded-lg border border-border bg-background/40 p-3">
      <div className="flex items-baseline justify-between gap-1">
        <p className="truncate text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      </div>
      <p className="tnum text-lg font-semibold leading-none">
        {value == null ? (
          <span className="text-muted-foreground/60">—</span>
        ) : (
          value.toFixed(digits)
        )}
        {unit ? <span className="ml-1 text-[11px] font-normal text-muted-foreground">{unit}</span> : null}
      </p>
      <div className="h-8">
        {points.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
              <YAxis hide domain={['dataMin - 1', 'dataMax + 1']} />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={tone}
                strokeWidth={1.25}
                fill={tone}
                fillOpacity={0.12}
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : null}
      </div>
    </div>
  )
}
