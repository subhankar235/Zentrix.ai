'use client'

import * as React from 'react'
import { Area, AreaChart, ResponsiveContainer, YAxis } from 'recharts'
import { CheckCircle2, Radio, Undo2 } from 'lucide-react'
import type { CanaryPoint } from '@/types/types'
import { subscribeToSse } from '@/lib/api/sse'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { cn } from '@/lib/utils'

type CanaryEvent = {
  status?: string
  metrics?: Record<string, number>
  rollback_reason?: string | null
}

export function CanaryLivePanel({
  experimentId,
  outcome = 'COMMIT',
  rollbackReason,
  onComplete,
}: {
  experimentId: string
  outcome?: 'COMMIT' | 'ROLLBACK'
  rollbackReason?: string
  onComplete?: () => void
}) {
  const [points, setPoints] = React.useState<CanaryPoint[]>([])
  const [liveStatus, setLiveStatus] = React.useState('RUNNING')
  const [liveRollbackReason, setLiveRollbackReason] = React.useState<string | undefined>(rollbackReason)

  React.useEffect(() => {
    return subscribeToSse<CanaryEvent>({
      endpoint: `/experiments/${experimentId}/canary/stream`,
      onMessage: (event) => {
        const metrics = event.metrics || {}
        setLiveStatus(event.status || 'RUNNING')
        if (event.rollback_reason) setLiveRollbackReason(event.rollback_reason)
        if (Object.keys(metrics).length) {
          setPoints((previous) => [
            ...previous,
            {
              t: previous.length + 1,
              p50: metrics.p50_ms,
              p95: metrics.p95_ms,
              p99: metrics.p99_ms,
              errorRate: metrics.error_rate,
              lockWaits: metrics.lock_wait_count,
              cpu: metrics.cpu_percent,
              throughput: metrics.throughput,
            },
          ])
        }
        if (event.status && event.status !== 'RUNNING') onComplete?.()
      },
    })
  }, [experimentId, onComplete])

  const finished = liveStatus !== 'RUNNING'
  const finalOutcome = liveStatus === 'ROLLED_BACK' ? 'ROLLBACK' : outcome

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <Radio className={cn('h-4 w-4', finished ? 'text-muted-foreground' : 'animate-pulse text-info')} />
            Live canary - monitoring window
          </CardTitle>
          <div className="flex items-center gap-2">
            {finished ? <StatusBadge status={finalOutcome} dot /> : <span className="text-xs text-muted-foreground">Waiting for live target metrics</span>}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {finished ? (
          finalOutcome === 'COMMIT' ? (
            <div className="flex items-start gap-3 rounded-lg border border-success/30 bg-success/10 p-4">
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
              <div>
                <p className="text-sm font-semibold text-success">Canary passed - COMMIT</p>
                <p className="mt-0.5 text-xs text-muted-foreground">Live guardrail metrics stayed within thresholds.</p>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-3 rounded-lg border border-danger/30 bg-danger/10 p-4">
              <Undo2 className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
              <div>
                <p className="text-sm font-semibold text-danger">Threshold breached - ROLLBACK</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{liveRollbackReason || 'The live target was automatically reverted.'}</p>
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
            <p className="mt-0.5 text-[11px] text-muted-foreground">from live SSE observations</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function CanaryTile({
  label, unit, dataKey, digits, points, tone,
}: {
  label: string
  unit: string
  dataKey: keyof Omit<CanaryPoint, 't'>
  digits: number
  points: CanaryPoint[]
  tone: string
}) {
  const value = points[points.length - 1]?.[dataKey]
  return (
    <div className="space-y-1 rounded-lg border border-border bg-background/40 p-3">
      <p className="truncate text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="tnum text-lg font-semibold leading-none">
        {typeof value !== 'number' ? <span className="text-muted-foreground/60">-</span> : value.toFixed(digits)}
        {unit ? <span className="ml-1 text-[11px] font-normal text-muted-foreground">{unit}</span> : null}
      </p>
      <div className="h-8">
        {points.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
              <YAxis hide domain={['dataMin - 1', 'dataMax + 1']} />
              <Area type="monotone" dataKey={dataKey} stroke={tone} strokeWidth={1.25} fill={tone} fillOpacity={0.12} isAnimationActive={false} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : null}
      </div>
    </div>
  )
}
