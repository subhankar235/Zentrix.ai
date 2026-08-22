'use client'

import * as React from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, ArrowRight, FlaskConical } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { ConfidenceMeter } from '@/components/confidence-meter'
import { ErrorBanner, EmptyState } from '@/components/states'
import { EvidenceGraph } from '@/components/diagnostics/evidence-graph'
import { Timeline } from '@/components/diagnostics/timeline'
import { Button } from '@/components/ui/button'
import { getDiagnosis, getConnectionName, getConnection } from '@/lib/mock-data'
import { rootCauseLabel, recTypeLabel } from '@/lib/labels'
import { relativeTime } from '@/lib/format'

export default function DiagnosisDetailPage() {
  const params = useParams<{ id: string }>()
  const d = getDiagnosis(params.id)
  const conn = getConnection(params.id)
  const router = useRouter()

  // Deep links like /diagnostics/prod-orders-db mean "show me this database's
  // diagnoses" — bounce to the list, which is already scoped by the selector.
  React.useEffect(() => {
    if (!d && conn) router.replace('/diagnostics')
  }, [d, conn, router])

  if (!d) {
    if (conn) {
      return (
        <div className="space-y-6">
          <PageHeader title="Diagnostics" description="Redirecting…" />
        </div>
      )
    }
    return (
      <div className="space-y-6">
        <PageHeader title="Diagnosis not found" />
        <EmptyState
          title="This diagnosis does not exist"
          description="It may have been resolved and archived."
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/diagnostics">Back to diagnostics</Link>
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb={
          <Link href="/diagnostics" className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3 w-3" /> Diagnostics
          </Link>
        }
        title={d.title}
        description={d.summary}
        actions={
          <div className="flex flex-col items-end gap-1.5">
            <ConfidenceMeter value={d.confidencePct} size="lg" />
            <span className="text-xs text-muted-foreground">Overall confidence</span>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={d.primaryRootCause} label={`Primary: ${rootCauseLabel[d.primaryRootCause]}`} tone="primary" />
        <StatusBadge status={d.status} dot />
        <span className="text-xs text-muted-foreground">
          {getConnectionName(d.connectionId)} · object{' '}
          <code className="font-mono text-foreground/80">{d.affectedObject}</code> · detected{' '}
          {relativeTime(d.detectedAtISO)}
        </span>
      </div>

      {d.lowConfidence ? (
        <ErrorBanner
          tone="warning"
          title="Low-confidence diagnosis — human review recommended"
          description="Signals are consistent with multiple root causes. The agent has withheld auto-remediation and is requesting an operator decision before any change is simulated."
        />
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Causal evidence graph</CardTitle>
            </CardHeader>
            <CardContent>
              <EvidenceGraph nodes={d.evidenceNodes} edges={d.evidenceEdges} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Supporting evidence</CardTitle>
            </CardHeader>
            <CardContent className="px-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-y border-border text-left text-xs text-muted-foreground">
                      <th className="px-6 py-2 font-medium">Claim</th>
                      <th className="px-4 py-2 font-medium">Metric</th>
                      <th className="px-4 py-2 text-right font-medium">Value</th>
                      <th className="px-6 py-2 text-right font-medium">Rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.supportingEvidence.map((s) => (
                      <tr key={s.id} className="border-b border-border/60 last:border-0">
                        <td className="px-6 py-2.5 text-pretty">{s.claim}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{s.metric}</td>
                        <td className="tnum px-4 py-2.5 text-right font-medium">{s.value}</td>
                        <td className="px-6 py-2.5 text-right">
                          <StatusBadge status={s.rank} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Contributing causes</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {d.contributingCauses.map((c, i) => (
                <div key={i} className="space-y-1.5 border-b border-border/60 pb-4 last:border-0 last:pb-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{rootCauseLabel[c.rootCause]}</span>
                    <StatusBadge status={c.rank} />
                  </div>
                  <ConfidenceMeter value={c.confidencePct} size="sm" />
                  <p className="text-xs text-muted-foreground text-pretty">{c.summary}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <Timeline entries={d.timeline} />
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recommended remediations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {d.recommendations.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No remediation proposed. The agent is still gathering evidence.
            </p>
          ) : (
            d.recommendations.map((r) => (
              <div
                key={r.id}
                className="flex flex-col gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={r.type} label={recTypeLabel[r.type]} tone="info" />
                    <StatusBadge status={r.risk} label={`${r.risk} risk`} />
                    <span className="text-sm font-medium">{r.title}</span>
                  </div>
                  <p className="max-w-2xl text-xs text-muted-foreground text-pretty">{r.rationale}</p>
                  <p className="text-xs">
                    <span className="text-muted-foreground">Predicted impact: </span>
                    <span className="font-medium text-success">{r.predictedImpact}</span>
                    <span className="tnum ml-1 text-muted-foreground">±{r.uncertaintyPct}%</span>
                  </p>
                </div>
                {r.experimentId ? (
                  <Button asChild size="sm" className="shrink-0 gap-1.5">
                    <Link href={`/experiments/${r.experimentId}`}>
                      <FlaskConical className="h-3.5 w-3.5" />
                      View experiment
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                ) : (
                  <StatusBadge status="queued" label="Simulation queued" tone="neutral" />
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
