import Link from 'next/link'
import { Check, X, ExternalLink } from 'lucide-react'
import type { DatabaseConnection } from '@/types/types'
import { Card } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'

function CheckRow({ ok, label }: { ok: boolean; label: string }) {
    return (
        <li className="flex items-center gap-2 text-xs">
            <span
                className={cn(
                    'flex h-4 w-4 items-center justify-center rounded-full',
                    ok ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger',
                )}
            >
                {ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
            </span>
            <span className={ok ? 'text-foreground' : 'text-danger'}>{label}</span>
        </li>
    )
}

export function ConnectionCard({
    conn,
    selected,
    onSelect,
}: {
    conn: DatabaseConnection
    selected?: boolean
    onSelect?: () => void
}) {
    return (
        <Card
            className={cn(
                'cursor-pointer p-4 transition-colors hover:border-primary/40',
                selected && 'border-primary/60 ring-1 ring-primary/30',
            )}
            onClick={onSelect}
        >
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                    <p className="truncate font-mono text-sm font-medium">{conn.name}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                        {conn.provider} · {conn.version}
                    </p>
                </div>
                <StatusBadge status={conn.status} dot />
            </div>

            <p className="mt-2 truncate font-mono text-[11px] text-muted-foreground">{conn.host}</p>

            <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5">
                <CheckRow ok={conn.checks.reachability} label="Reachable" />
                <CheckRow ok={conn.checks.credentials} label="Credentials valid" />
                <CheckRow ok={conn.checks.pgStatStatements} label="pg_stat_statements" />
                <CheckRow ok={conn.checks.readOnlyRole} label="read-only role" />
            </ul>

            <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-xs">
                <span className="text-muted-foreground">Polled {relativeTime(conn.lastCheckedISO)}</span>
                <Link
                    href={`/monitoring/${conn.id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 font-medium text-primary hover:underline"
                >
                    Monitoring <ExternalLink className="h-3 w-3" />
                </Link>
            </div>
        </Card>
    )
}
