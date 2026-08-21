'use client'

import * as React from 'react'
import { Card } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { cn } from '@/lib/utils'

interface SlowQuery {
  id: string
  query: string
  calls: number
  meanMs: number
  p99Ms: number
  sharePct: number
  trend: 'up' | 'down' | 'flat'
}

function mulberry(seed: number) {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const QUERY_SHAPES = [
  'SELECT * FROM orders WHERE customer_id = $1 ORDER BY created_at DESC',
  'UPDATE inventory SET qty = qty - $1 WHERE sku = $2',
  'SELECT count(*) FROM events WHERE ts > now() - interval $1',
  'SELECT o.*, li.* FROM orders o JOIN line_items li ON li.order_id = o.id',
  'INSERT INTO audit_log (actor, action, payload) VALUES ($1, $2, $3)',
  'SELECT * FROM sessions WHERE token = $1 AND expires_at > now()',
  'DELETE FROM cache_entries WHERE expires_at < now()',
  'SELECT sku, sum(qty) FROM order_items GROUP BY sku ORDER BY 2 DESC',
]

function build(connId: string, stress: number): SlowQuery[] {
  let h = 0
  for (let i = 0; i < connId.length; i++) h = (h * 31 + connId.charCodeAt(i)) | 0
  const rand = mulberry(h)
  return QUERY_SHAPES.map((query, i): SlowQuery => {
    const mean = Number((6 + rand() * 90 * stress).toFixed(1))
    return {
      id: `q${i}`,
      query,
      calls: Math.round(400 + rand() * 48000),
      meanMs: mean,
      p99Ms: Number((mean * (2.5 + rand() * 3)).toFixed(1)),
      sharePct: Number((2 + rand() * 22).toFixed(1)),
      trend: rand() > 0.6 ? 'up' : rand() > 0.3 ? 'down' : 'flat',
    }
  }).sort((a, b) => b.p99Ms - a.p99Ms)
}

export function SlowQueryTable({
  connId,
  stress,
}: {
  connId: string
  stress: number
}) {
  const rows = React.useMemo(() => build(connId, stress), [connId, stress])
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="text-sm font-medium">Top statements by p99</h3>
        <span className="text-xs text-muted-foreground">via pg_stat_statements</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-4 py-2 font-medium">Statement</th>
              <th className="px-4 py-2 text-right font-medium">Calls</th>
              <th className="px-4 py-2 text-right font-medium">Mean</th>
              <th className="px-4 py-2 text-right font-medium">p99</th>
              <th className="px-4 py-2 text-right font-medium">% time</th>
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
                  <div className="flex items-center justify-end gap-2">
                    <span className="tnum text-muted-foreground">{r.sharePct}%</span>
                    <StatusBadge
                      status={r.trend}
                      label={r.trend === 'up' ? '▲' : r.trend === 'down' ? '▼' : '—'}
                      tone={r.trend === 'up' ? 'danger' : r.trend === 'down' ? 'success' : 'neutral'}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
