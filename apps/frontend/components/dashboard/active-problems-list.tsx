import Link from 'next/link'
import { ChevronRight } from 'lucide-react'
import type { Diagnosis } from '@/types/types'
import { Card } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { ConfidenceMeter } from '@/components/confidence-meter'
import { EmptyState } from '@/components/states'
import { relativeTime } from '@/lib/format'
import { getConnectionName } from '@/lib/mock-data'

export function ActiveProblemsList({ diagnoses }: { diagnoses: Diagnosis[] }) {
    if (diagnoses.length === 0) {
        return (
            <Card>
                <EmptyState
                    title="No active problems"
                    description="Your databases look healthy. New diagnoses will appear here the moment telemetry crosses a threshold."
                    className="border-0"
                />
            </Card>
        )
    }

    return (
        <Card className="overflow-hidden">
            <div className="hidden grid-cols-[1fr_auto_auto_auto] items-center gap-4 border-b border-border px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground md:grid">
                <span>Problem</span>
                <span>Root cause</span>
                <span className="w-28">Confidence</span>
                <span className="w-20 text-right">Detected</span>
            </div>
            <ul className="divide-y divide-border">
                {diagnoses.map((d) => (
                    <li key={d.id}>
                        <Link
                            href={`/diagnostics/${d.id}`}
                            className="grid grid-cols-1 items-center gap-2 px-4 py-3 hover:bg-accent/50 md:grid-cols-[1fr_auto_auto_auto] md:gap-4"
                        >
                            <div className="min-w-0">
                                <p className="truncate text-sm font-medium">{d.title}</p>
                                <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                                    <span className="font-mono">{getConnectionName(d.connectionId)}</span>
                                    {d.lowConfidence ? (
                                        <span className="text-warning">· low confidence</span>
                                    ) : null}
                                </p>
                            </div>
                            <StatusBadge status={d.primaryRootCause} tone="primary" />
                            <div className="md:w-28">
                                <ConfidenceMeter value={d.confidencePct} size="sm" />
                            </div>
                            <div className="flex items-center justify-between gap-1 md:w-20 md:justify-end">
                                <span className="text-xs text-muted-foreground">{relativeTime(d.detectedAtISO)}</span>
                                <ChevronRight className="hidden h-4 w-4 text-muted-foreground md:block" />
                            </div>
                        </Link>
                    </li>
                ))}
            </ul>
        </Card>
    )
}
