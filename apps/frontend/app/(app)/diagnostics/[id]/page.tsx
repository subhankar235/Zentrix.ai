'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, FlaskConical } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatusBadge } from '@/components/status-badge';
import { ConfidenceMeter } from '@/components/confidence-meter';
import { ErrorBanner } from '@/components/states';
import { LoadingState, EmptyState } from '@/components/ui/state-feedback';
import { EvidenceGraph } from '@/components/diagnostics/evidence-graph';
import { Timeline } from '@/components/diagnostics/timeline';
import { Button } from '@/components/ui/button';
import { useDiagnosisDetailQuery } from '@/hooks/use-diagnostics';
import { useConnectionsQuery } from '@/hooks/use-connections';
import { rootCauseLabel, recTypeLabel } from '@/lib/labels';
import { relativeTime } from '@/lib/format';

export default function DiagnosisDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: d, isLoading, isError } = useDiagnosisDetailQuery(params.id);
  const { data: connections = [] } = useConnectionsQuery();

  const conn = connections.find((c) => c.id === d?.connectionId);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Diagnosis report" />
        <LoadingState message="Loading causal evidence tree and timeline..." />
      </div>
    );
  }

  if (isError || !d) {
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
    );
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
        <StatusBadge status={d.primaryRootCause} label={`Primary: ${rootCauseLabel[d.primaryRootCause] || d.primaryRootCause}`} tone="primary" />
        <StatusBadge status={d.status} dot />
        <span className="text-xs text-muted-foreground">
          {conn?.name || d.connectionId} · object{' '}
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
              <CardTitle>Evidence timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <Timeline entries={d.timeline} />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Candidate Optimizations</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {d.recommendations.map((r) => (
                <div key={r.id} className="rounded-lg border border-border p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <StatusBadge status={r.type} label={recTypeLabel[r.type] || r.type} tone="info" />
                    <span className="text-xs font-medium text-muted-foreground">{r.risk} risk</span>
                  </div>
                  <p className="text-xs font-semibold">{r.title}</p>
                  <p className="text-xs text-muted-foreground">{r.rationale}</p>
                  <div className="pt-2">
                    <Button size="sm" variant="outline" className="w-full gap-1" asChild>
                      <Link href={`/experiments/${r.experimentId || 'new'}`}>
                        <FlaskConical className="h-3.5 w-3.5" />
                        Simulate &amp; Verify
                      </Link>
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
