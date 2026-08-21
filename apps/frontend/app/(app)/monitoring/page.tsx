'use client'

import * as React from 'react'
import { Activity, Pause, Play } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { MetricChart, type MetricSample } from '@/components/monitoring/metric-chart'
import { SlowQueryTable } from '@/components/monitoring/slow-query-table'
import { StatusBadge } from '@/components/status-badge'
import { EmptyState } from '@/components/states'
import { useSelectedDb } from '@/components/app-providers'
import { getConnection } from '@/lib/mock-data'
import { metricSpecs, seedSeries, nextValue, type MetricSpec } from '@/lib/live-metrics'
import type { DatabaseConnection } from '@/types/types'
import { Button } from '@/components/ui/button'

const WINDOWS = ['5m', '15m', '1h', '6h'] as const

export default function MonitoringPage() {
    const { selectedId } = useSelectedDb()
    const conn = getConnection(selectedId)

    if (!conn) {
        return (
            <div className="space-y-6">
                <PageHeader title="Live monitoring" />
                <EmptyState title="No database selected" description="Choose a connection to stream metrics." />
            </div>
        )
    }

    // Keyed by connection id so metric series state re-initializes cleanly per database.
    return <LiveMetrics key={conn.id} conn={conn} />
}

function LiveMetrics({ conn }: { conn: DatabaseConnection }) {
    const specs = React.useMemo<MetricSpec[]>(() => metricSpecs(conn.health), [conn])

    const [series, setSeries] = React.useState<Record<string, MetricSample[]>>(() => {
        const init: Record<string, MetricSample[]> = {}
        for (const spec of specs) init[spec.key] = seedSeries(conn.id, spec)
        return init
    })
    const [live, setLive] = React.useState(true)
    const [win, setWin] = React.useState<(typeof WINDOWS)[number]>('5m')

    // Live tick.
    React.useEffect(() => {
        if (!live) return
        const id = setInterval(() => {
            setSeries((prev) => {
                const next: Record<string, MetricSample[]> = {}
                for (const spec of specs) {
                    const arr = prev[spec.key] ?? []
                    if (arr.length === 0) {
                        next[spec.key] = arr
                        continue
                    }
                    const last = arr[arr.length - 1]
                    const nv = nextValue(spec, last.value)
                    next[spec.key] = [...arr.slice(1), { t: last.t + 1, value: nv }]
                }
                return next
            })
        }, 2000)
        return () => clearInterval(id)
    }, [live, specs])

    return (
        <div className="space-y-6">
            <PageHeader
                title="Live monitoring"
                description={`Real-time signal from ${conn.name}. Metrics stream from the read-only agent role every 2 seconds.`}
                actions={
                    <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
                            {WINDOWS.map((w) => (
                                <button
                                    key={w}
                                    onClick={() => setWin(w)}
                                    className={`rounded px-2 py-1 text-xs font-medium transition-colors ${win === w
                                            ? 'bg-secondary text-secondary-foreground'
                                            : 'text-muted-foreground hover:text-foreground'
                                        }`}
                                >
                                    {w}
                                </button>
                            ))}
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setLive((v) => !v)}
                            className="gap-1.5"
                        >
                            {live ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                            {live ? 'Pause' : 'Resume'}
                        </Button>
                    </div>
                }
            />

            <div className="flex flex-wrap items-center gap-3">
                <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span
                        className={`h-2 w-2 rounded-full ${live ? 'animate-pulse bg-success' : 'bg-muted-foreground'}`}
                    />
                    {live ? 'Streaming' : 'Paused'}
                </span>
                <StatusBadge status={conn.health} dot />
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Activity className="h-3.5 w-3.5" />
                    {conn.provider} · {conn.region} · {conn.version}
                </span>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {specs.map((spec) => {
                    const arr = series[spec.key] ?? []
                    const current = arr.length ? arr[arr.length - 1].value : spec.base
                    return (
                        <MetricChart
                            key={spec.key}
                            label={spec.label}
                            unit={spec.unit}
                            data={arr}
                            current={current}
                            tone={spec.tone}
                            threshold={spec.threshold}
                            format={
                                spec.key === 'throughput'
                                    ? (n) => Math.round(n).toLocaleString()
                                    : spec.key === 'connections'
                                        ? (n) => String(Math.round(n))
                                        : undefined
                            }
                        />
                    )
                })}
            </div>

            <SlowQueryTable
                connId={conn.id}
                stress={conn.health === 'Critical' ? 2.4 : conn.health === 'Degraded' ? 1.5 : 1}
            />
        </div>
    )
}
