'use client'

import * as React from 'react'
import Link from 'next/link'
import { Lightbulb, ArrowRight, FlaskConical } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { Card } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { EmptyState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { useSelectedDb } from '@/components/app-providers'
import { getConnection, getAllDiagnoses, getDiagnosesForConnection } from '@/lib/mock-data'
import { rootCauseLabel, recTypeLabel } from '@/lib/labels'
import type { Recommendation, Diagnosis } from '@/types/types'

type Row = { rec: Recommendation; diagnosis: Diagnosis }

const TYPE_FILTERS: (Recommendation['type'] | 'ALL')[] = [
    'ALL',
    'INDEX',
    'STATISTICS',
    'CONFIG',
    'QUERY_REWRITE',
    'VACUUM',
]

export default function RecommendationsPage() {
    const { selectedId } = useSelectedDb()
    const conn = getConnection(selectedId)
    const [scope, setScope] = React.useState<'this' | 'all'>('this')
    const [typeFilter, setTypeFilter] = React.useState<Recommendation['type'] | 'ALL'>('ALL')

    const diagnoses = scope === 'all' ? getAllDiagnoses() : getDiagnosesForConnection(selectedId)
    const rows: Row[] = diagnoses.flatMap((d) => d.recommendations.map((rec) => ({ rec, diagnosis: d })))
    const filtered = rows
        .filter((r) => (typeFilter === 'ALL' ? true : r.rec.type === typeFilter))
        .sort((a, b) => a.rec.uncertaintyPct - b.rec.uncertaintyPct)

    const withExperiment = rows.filter((r) => r.rec.experimentId).length

    return (
        <div className="space-y-6">
            <PageHeader
                title="Recommendations"
                description={`Proposed remediations ranked by prediction certainty for ${scope === 'all' ? 'all databases' : conn?.name ?? 'this database'}. ${withExperiment} of ${rows.length} have an active experiment.`}
            />

            <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-0.5 rounded-md border border-border p-0.5">
                    {(['this', 'all'] as const).map((s) => (
                        <button
                            key={s}
                            onClick={() => setScope(s)}
                            className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${scope === s ? 'bg-secondary text-secondary-foreground' : 'text-muted-foreground hover:text-foreground'
                                }`}
                        >
                            {s === 'this' ? 'This database' : 'All databases'}
                        </button>
                    ))}
                </div>
                <div className="flex flex-wrap items-center gap-0.5 rounded-md border border-border p-0.5">
                    {TYPE_FILTERS.map((t) => (
                        <button
                            key={t}
                            onClick={() => setTypeFilter(t)}
                            className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${typeFilter === t ? 'bg-secondary text-secondary-foreground' : 'text-muted-foreground hover:text-foreground'
                                }`}
                        >
                            {t === 'ALL' ? 'All types' : recTypeLabel[t]}
                        </button>
                    ))}
                </div>
            </div>

            {filtered.length === 0 ? (
                <EmptyState
                    icon={Lightbulb}
                    title="No recommendations"
                    description="The agent proposes remediations only when a diagnosis reaches sufficient confidence."
                />
            ) : (
                <div className="grid grid-cols-1 gap-3">
                    {filtered.map(({ rec, diagnosis }) => (
                        <Card key={rec.id} className="p-4">
                            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                <div className="min-w-0 flex-1 space-y-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <StatusBadge status={rec.type} label={recTypeLabel[rec.type]} tone="info" />
                                        <StatusBadge status={rec.risk} label={`${rec.risk} risk`} />
                                        <span className="text-sm font-medium">{rec.title}</span>
                                    </div>
                                    <p className="max-w-3xl text-sm text-muted-foreground text-pretty">{rec.rationale}</p>
                                    <p className="text-xs text-muted-foreground">
                                        Addresses{' '}
                                        <Link
                                            href={`/diagnostics/${diagnosis.id}`}
                                            className="text-primary underline-offset-2 hover:underline"
                                        >
                                            {rootCauseLabel[diagnosis.primaryRootCause]}
                                        </Link>{' '}
                                        on <code className="font-mono text-foreground/80">{diagnosis.affectedObject}</code>
                                    </p>
                                </div>
                                <div className="flex items-center gap-6 lg:flex-col lg:items-end lg:gap-3">
                                    <div className="text-right">
                                        <p className="tnum text-lg font-semibold text-success">{rec.predictedImpact}</p>
                                        <p className="tnum text-xs text-muted-foreground">±{rec.uncertaintyPct}% uncertainty</p>
                                    </div>
                                    {rec.experimentId ? (
                                        <Button asChild size="sm" className="gap-1.5">
                                            <Link href={`/experiments/${rec.experimentId}`}>
                                                <FlaskConical className="h-3.5 w-3.5" />
                                                Experiment
                                                <ArrowRight className="h-3.5 w-3.5" />
                                            </Link>
                                        </Button>
                                    ) : (
                                        <StatusBadge status="queued" label="Simulation queued" tone="neutral" />
                                    )}
                                </div>
                            </div>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    )
}
