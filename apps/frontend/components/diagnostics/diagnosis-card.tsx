'use client'

import Link from 'next/link'
import { ChevronRight, AlertTriangle } from 'lucide-react'
import type { Diagnosis } from '@/types/types'
import { Card } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { ConfidenceMeter } from '@/components/confidence-meter'
import { rootCauseLabel } from '@/lib/labels'
import { relativeTime } from '@/lib/format'
import { getConnectionName } from '@/lib/mock-data'

export function DiagnosisCard({
    diagnosis,
    showConnection = false,
}: {
    diagnosis: Diagnosis
    showConnection?: boolean
}) {
    const d = diagnosis
    return (
        <Link href={`/diagnostics/${d.id}`} className="group block">
            <Card className="p-4 transition-colors group-hover:border-primary/40 group-hover:bg-muted/30">
                <div className="flex items-start gap-4">
                    <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                            <StatusBadge status={d.primaryRootCause} label={rootCauseLabel[d.primaryRootCause]} tone="primary" />
                            <StatusBadge status={d.status} dot />
                            {d.lowConfidence ? (
                                <StatusBadge status="low" label="Low confidence" tone="warning" />
                            ) : null}
                        </div>
                        <p className="font-medium text-balance">{d.title}</p>
                        <p className="line-clamp-2 max-w-2xl text-sm text-muted-foreground text-pretty">
                            {d.summary}
                        </p>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                            <span>
                                Object <code className="font-mono text-foreground/80">{d.affectedObject}</code>
                            </span>
                            {showConnection ? <span>{getConnectionName(d.connectionId)}</span> : null}
                            <span>Detected {relativeTime(d.detectedAtISO)}</span>
                            <span>
                                {d.contributingCauses.length} contributing{' '}
                                {d.contributingCauses.length === 1 ? 'cause' : 'causes'}
                            </span>
                        </div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2">
                        <div className="flex items-center gap-2">
                            {d.lowConfidence ? <AlertTriangle className="h-3.5 w-3.5 text-warning" /> : null}
                            <ConfidenceMeter value={d.confidencePct} size="sm" />
                        </div>
                        <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                    </div>
                </div>
            </Card>
        </Link>
    )
}
