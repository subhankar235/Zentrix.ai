'use client';

import * as React from 'react';
import Link from 'next/link';
import { ArrowRight, FlaskConical } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import { Card } from '@/components/ui/card';
import { StatusBadge } from '@/components/status-badge';
import { Button } from '@/components/ui/button';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/state-feedback';
import { useToast } from '@/components/app-providers';
import { useConnectionsQuery } from '@/hooks/use-connections';
import { useDiagnosticsQuery } from '@/hooks/use-diagnostics';
import { useSimulateMutation } from '@/hooks/use-experiments';
import { useAppStore } from '@/stores/use-app-store';
import { rootCauseLabel, recTypeLabel } from '@/lib/labels';
import type { Recommendation, Diagnosis } from '@/types/types';

type Row = { rec: Recommendation; diagnosis: Diagnosis };

const TYPE_FILTERS: (Recommendation['type'] | 'ALL')[] = [
  'ALL',
  'INDEX',
  'STATISTICS',
  'CONFIG',
  'QUERY_REWRITE',
  'VACUUM',
];

export default function RecommendationsPage() {
  const { toast } = useToast();
  const { data: connections = [] } = useConnectionsQuery();
  const selectedId = useAppStore((s) => s.selectedConnectionId) || connections[0]?.id;
  const conn = connections.find((c) => c.id === selectedId);

  const [scope, setScope] = React.useState<'this' | 'all'>('this');
  const [typeFilter, setTypeFilter] = React.useState<Recommendation['type'] | 'ALL'>('ALL');

  const {
    data: diagnoses = [],
    isLoading,
    isError,
    refetch,
  } = useDiagnosticsQuery(scope === 'all' ? null : selectedId);

  const simulateMutation = useSimulateMutation();

  const rows: Row[] = diagnoses.flatMap((d) => d.recommendations.map((rec) => ({ rec, diagnosis: d })));
  const filtered = rows
    .filter((r) => (typeFilter === 'ALL' ? true : r.rec.type === typeFilter))
    .sort((a, b) => a.rec.uncertaintyPct - b.rec.uncertaintyPct);

  const withExperiment = rows.filter((r) => r.rec.experimentId).length;

  const handleSimulate = async (recId: string) => {
    try {
      await simulateMutation.mutateAsync(recId);
      toast({
        kind: 'success',
        title: 'Simulation Dispatched',
        description: 'Executing HypoPG candidate in isolated shadow DB environment.',
      });
    } catch (err: unknown) {
      toast({
        kind: 'danger',
        title: 'Simulation Failed',
        description: err instanceof Error ? err.message : 'Could not start shadow simulation.',
      });
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Recommendations" description="Proposed remediations ranked by prediction certainty." />
        <LoadingState message="Loading candidate optimizations..." />
      </div>
    );
  }

  if (isError && rows.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="Recommendations" description="Proposed remediations ranked by prediction certainty." />
        <ErrorState
          title="Failed to load recommendations"
          message="Could not query candidate remediations."
          onRetry={() => refetch()}
        />
      </div>
    );
  }

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
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                scope === s ? 'bg-secondary text-secondary-foreground' : 'text-muted-foreground hover:text-foreground'
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
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                typeFilter === t ? 'bg-secondary text-secondary-foreground' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {t === 'ALL' ? 'All types' : recTypeLabel[t] || t}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
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
                    <StatusBadge status={rec.type} label={recTypeLabel[rec.type] || rec.type} tone="info" />
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
                      {rootCauseLabel[diagnosis.primaryRootCause] || diagnosis.primaryRootCause}
                    </Link>{' '}
                    · predicted impact <span className="font-medium text-foreground">{rec.predictedImpact}</span>
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {rec.experimentId ? (
                    <Button variant="outline" size="sm" asChild className="gap-1">
                      <Link href={`/experiments/${rec.experimentId}`}>
                        <FlaskConical className="h-3.5 w-3.5" /> View experiment
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => handleSimulate(rec.id)}
                      disabled={simulateMutation.isPending}
                      className="gap-1"
                    >
                      <FlaskConical className="h-3.5 w-3.5" />
                      Simulate
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
