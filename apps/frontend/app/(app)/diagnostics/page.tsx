'use client';

import * as React from 'react';
import { Play } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import { DiagnosisCard } from '@/components/diagnostics/diagnosis-card';
import { Button } from '@/components/ui/button';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/state-feedback';
import { useToast } from '@/components/app-providers';
import { useConnectionsQuery } from '@/hooks/use-connections';
import { useDiagnosticsQuery, useTriggerDiagnosisMutation } from '@/hooks/use-diagnostics';
import { useAppStore } from '@/stores/use-app-store';

type Scope = 'this' | 'all';
type StatusFilter = 'all' | 'Active' | 'Resolved';

export default function DiagnosticsPage() {
  const { toast } = useToast();
  const { data: connections = [] } = useConnectionsQuery();
  const selectedId = useAppStore((s) => s.selectedConnectionId) || connections[0]?.id;
  const conn = connections.find((c) => c.id === selectedId);

  const [scope, setScope] = React.useState<Scope>('this');
  const [status, setStatus] = React.useState<StatusFilter>('all');
  const [onlyLow, setOnlyLow] = React.useState(false);

  const {
    data: rawDiagnoses = [],
    isLoading,
    isError,
    refetch,
  } = useDiagnosticsQuery(scope === 'all' ? null : selectedId);

  const triggerMutation = useTriggerDiagnosisMutation();

  const list = rawDiagnoses
    .filter((d) => (status === 'all' ? true : d.status === status))
    .filter((d) => (onlyLow ? d.lowConfidence : true))
    .sort((a, b) => b.confidencePct - a.confidencePct);

  const active = rawDiagnoses.filter((d) => d.status === 'Active').length;

  const handleTrigger = async () => {
    if (!selectedId) return;
    try {
      const res = await triggerMutation.mutateAsync(selectedId);
      toast({
        kind: 'info',
        title: 'Diagnostic Dispatched',
        description: res.message || 'AI agents are gathering evidence from query plans and lock telemetry.',
      });
    } catch (err: unknown) {
      toast({
        kind: 'danger',
        title: 'Trigger Failed',
        description: err instanceof Error ? err.message : 'Could not dispatch diagnosis.',
      });
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Diagnostics" description="Root-cause analyses across monitored databases." />
        <LoadingState message="Querying agent diagnostic reports and evidence graphs..." />
      </div>
    );
  }

  if (isError && rawDiagnoses.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="Diagnostics" description="Root-cause analyses across monitored databases." />
        <ErrorState
          title="Failed to load diagnostics"
          message="Could not retrieve diagnostic records from the backend API."
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Diagnostics"
        description={`Root-cause analyses across ${scope === 'all' ? 'all connected databases' : conn?.name ?? 'this database'}. ${active} active.`}
        actions={
          <Button
            onClick={handleTrigger}
            disabled={triggerMutation.isPending}
            className="gap-1.5"
          >
            <Play className="h-3.5 w-3.5" />
            {triggerMutation.isPending ? 'Analyzing Fleet…' : 'Run Diagnostics'}
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          value={scope}
          onChange={(v) => setScope(v as Scope)}
          options={[
            { value: 'this', label: 'This database' },
            { value: 'all', label: 'All databases' },
          ]}
        />
        <Segmented
          value={status}
          onChange={(v) => setStatus(v as StatusFilter)}
          options={[
            { value: 'all', label: 'All' },
            { value: 'Active', label: 'Active' },
            { value: 'Resolved', label: 'Resolved' },
          ]}
        />
        <button
          onClick={() => setOnlyLow((v) => !v)}
          className={`rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors ${
            onlyLow
              ? 'border-warning/40 bg-warning/10 text-warning'
              : 'border-border text-muted-foreground hover:text-foreground'
          }`}
        >
          Low confidence only
        </button>
      </div>

      {list.length === 0 ? (
        <EmptyState
          title="No diagnoses match"
          description="The agent has not surfaced any root-cause analyses for this filter. Healthy databases produce no findings."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {list.map((d) => (
            <DiagnosisCard key={d.id} diagnosis={d} showConnection={scope === 'all'} />
          ))}
        </div>
      )}
    </div>
  );
}

function Segmented({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="flex items-center gap-0.5 rounded-md border border-border p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            value === o.value
              ? 'bg-secondary text-secondary-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
