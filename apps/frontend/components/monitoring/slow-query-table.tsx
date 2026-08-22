'use client'

import * as React from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { EmptyState } from '@/components/ui/state-feedback'

import type { TelemetryQuery } from '@/lib/api/monitoring'

interface SlowQuery {
  id: string
  query: string
  calls: number
  meanMs: number
  p99Ms: number
  sharePct: number
}

function build(realQueries: TelemetryQuery[] = []): SlowQuery[] {
  const totalCalls = realQueries.reduce((acc, q) => acc + (q.calls || 0), 0) || 1
  return realQueries.map((q, i) => {
    const mean = q.mean_exec_time || 0
    const p99 = q.max_exec_time || mean
    const share = Number((((q.calls || 0) / totalCalls) * 100).toFixed(1))
    return {
      id: q.id || q.query_hash || `q-${i}`,
      query: q.query_text || '(query text unavailable)',
      calls: q.calls || 0,
      meanMs: Number(mean.toFixed(1)),
      p99Ms: Number(p99.toFixed(1)),
      sharePct: share,
    }
  }).sort((a, b) => b.p99Ms - a.p99Ms)
}

export function SlowQueryTable({
  realQueries,
}: {
  realQueries?: TelemetryQuery[]
}) {
  const rows = React.useMemo(() => build(realQueries), [realQueries])
  return (
    <Card className="overflow-hidden">
       <div className="flex items-center justify-between border-b border-border px-4 py-3">
         <h3 className="text-sm font-medium">Top statements by highest observed latency</h3>
        <span className="text-xs text-muted-foreground">via pg_stat_statements</span>
      </div>
      {rows.length === 0 ? <EmptyState title="No query telemetry returned" description="pg_stat_statements returned no statements for this snapshot." /> : null}
      {rows.length > 0 ? <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-4 py-2 font-medium">Statement</th>
              <th className="px-4 py-2 text-right font-medium">Calls</th>
              <th className="px-4 py-2 text-right font-medium">Mean</th>
               <th className="px-4 py-2 text-right font-medium">Highest observed</th>
               <th className="px-4 py-2 text-right font-medium">Share</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-border/60 last:border-0 hover:bg-muted/40">
                <td className="max-w-md px-4 py-2.5">
                  <code className="block truncate font-mono text-xs text-foreground/90">
                    {r.query}
                  </code>
                </td>
                <td className="tnum px-4 py-2.5 text-right text-muted-foreground">
                  {r.calls.toLocaleString()}
                </td>
                <td className="tnum px-4 py-2.5 text-right">{r.meanMs} ms</td>
                <td
                  className={cn(
                    'tnum px-4 py-2.5 text-right font-medium',
                    r.p99Ms > 200 ? 'text-danger' : r.p99Ms > 80 ? 'text-warning' : 'text-foreground',
                  )}
                >
                  {r.p99Ms} ms
                </td>
                <td className="px-4 py-2.5 text-right">
                  <span className="tnum text-muted-foreground">{r.sharePct}%</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div> : null}
    </Card>
  )
}
