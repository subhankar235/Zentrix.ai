import Link from 'next/link'
import { ArrowUpRight } from 'lucide-react'
import type { DatabaseConnection } from '@/types/types'
import { Card } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { Sparkline } from '@/components/sparkline'
import { relativeTime } from '@/lib/format'
import { useSelectedDb } from '@/components/app-providers'

function healthTone(h: DatabaseConnection['health']) {
    return h === 'Healthy' ? 'success' : h === 'Degraded' ? 'warning' : 'danger'
}

export function ConnectionSummaryCard({ conn }: { conn: DatabaseConnection }) {
    const latest = conn.latencySparkline[conn.latencySparkline.length - 1]
    const { setSelectedId } = useSelectedDb()
    return (
        <Card className="flex flex-col gap-4 p-4 transition-colors hover:border-primary/40">
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                    <Link
                        href="/monitoring"
                        onClick={() => setSelectedId(conn.id)}
                        className="flex items-center gap-1 font-mono text-sm font-medium hover:text-primary"
                    >
                        <span className="truncate">{conn.name}</span>
                        <ArrowUpRight className="h-3.5 w-3.5 shrink-0 opacity-60" />
                    </Link>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                        {conn.provider} · {conn.region}
                    </p>
                </div>
                <StatusBadge status={conn.health} dot tone={healthTone(conn.health)} />
            </div>

            <div className="flex items-end justify-between gap-3">
                <div>
                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground">p95 latency</p>
                    <p className="tnum text-2xl font-semibold">
                        {latest}
                        <span className="ml-1 text-sm font-normal text-muted-foreground">ms</span>
                    </p>
                </div>
                <Sparkline
                    data={conn.latencySparkline}
                    width={120}
                    height={36}
                    tone={conn.health === 'Healthy' ? 'success' : conn.health === 'Degraded' ? 'warning' : 'danger'}
                />
            </div>

            <div className="flex items-center justify-between border-t border-border pt-3 text-xs">
                <span className="text-muted-foreground">Checked {relativeTime(conn.lastCheckedISO)}</span>
                {conn.activeProblems > 0 ? (
                    <Link
                        href="/diagnostics"
                        onClick={() => setSelectedId(conn.id)}
                        className="font-medium text-warning hover:underline"
                    >
                        {conn.activeProblems} active {conn.activeProblems === 1 ? 'problem' : 'problems'}
                    </Link>
                ) : (
                    <span className="text-success">No active problems</span>
                )}
            </div>
        </Card>
    )
}
