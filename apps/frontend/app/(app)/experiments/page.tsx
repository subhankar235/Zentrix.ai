'use client';

import * as React from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronRight, Search } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import { Card } from '@/components/ui/card';
import { StatusBadge } from '@/components/status-badge';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/state-feedback';
import { Button } from '@/components/ui/button';
import { useExperimentsQuery } from '@/hooks/use-experiments';
import { useConnectionsQuery } from '@/hooks/use-connections';
import { absoluteTime, relativeTime } from '@/lib/format';
import type { DeploymentOutcome, Verdict } from '@/types/types';

const VERDICTS: (Verdict | 'All')[] = ['All', 'VERIFIED', 'CONDITIONAL', 'REJECTED'];
const OUTCOMES: (DeploymentOutcome | 'All')[] = [
  'All',
  'COMMIT',
  'ROLLBACK',
  'AWAITING_APPROVAL',
  'IN_PROGRESS',
];

export default function ExperimentsPage() {
  const { data: all = [], isLoading, isError, refetch } = useExperimentsQuery();
  const { data: connectionsList = [] } = useConnectionsQuery();

  const [dbFilter, setDbFilter] = React.useState<string>('all');
  const [verdict, setVerdict] = React.useState<Verdict | 'All'>('All');
  const [outcome, setOutcome] = React.useState<DeploymentOutcome | 'All'>('All');
  const [query, setQuery] = React.useState('');
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());

  const rows = all
    .filter((e) => (dbFilter === 'all' ? true : e.connectionId === dbFilter))
    .filter((e) => (verdict === 'All' ? true : e.verdict === verdict))
    .filter((e) => (outcome === 'All' ? true : e.outcome === outcome))
    .filter((e) => (query ? e.candidate.toLowerCase().includes(query.toLowerCase()) : true))
    .sort((a, b) => b.createdAtISO.localeCompare(a.createdAtISO));

  const awaiting = all.filter((e) => e.outcome === 'AWAITING_APPROVAL').length;
  const committed = all.filter((e) => e.outcome === 'COMMIT').length;
  const rolledBack = all.filter((e) => e.outcome === 'ROLLBACK').length;

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Optimization history" />
        <LoadingState message="Loading experiment ledgers and verification verdicts..." />
      </div>
    );
  }

  if (isError && all.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="Optimization history" />
        <ErrorState
          title="Failed to load experiments"
          message="Could not load verification records from the backend API."
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Optimization history"
        description="Every experiment the system has ever run, including approvals, commits, and rollbacks. This is the trust ledger — no production-facing action happens outside of it."
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total experiments" value={all.length} />
        <Stat label="Awaiting approval" value={awaiting} tone="text-warning" />
        <Stat label="Committed" value={committed} tone="text-success" />
        <Stat label="Rolled back" value={rolledBack} tone="text-danger" />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={dbFilter}
          onChange={(e) => setDbFilter(e.target.value)}
          className="h-8 rounded-md border border-border bg-background px-2 text-xs outline-none focus:ring-2 focus:ring-ring"
          aria-label="Filter by database"
        >
          <option value="all">All databases</option>
          {connectionsList.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <Segmented
          value={verdict}
          onChange={(v) => setVerdict(v as Verdict | 'All')}
          options={VERDICTS.map((v) => ({ value: v, label: v === 'All' ? 'All verdicts' : v }))}
        />
        <Segmented
          value={outcome}
          onChange={(v) => setOutcome(v as DeploymentOutcome | 'All')}
          options={OUTCOMES.map((o) => ({
            value: o,
            label: o === 'All' ? 'All outcomes' : o.replace(/_/g, ' '),
          }))}
        />

        <div className="relative ml-auto flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search candidate queries…"
            className="h-8 w-full rounded-md border border-border bg-background pl-8 pr-2 text-xs outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No experiments match"
          description="Try relaxing your filters."
        />
      ) : (
        <div className="divide-y divide-border rounded-lg border border-border bg-card">
          {rows.map((e) => {
            const isExp = expanded.has(e.id);
            const conn = connectionsList.find((c) => c.id === e.connectionId);
            return (
              <div key={e.id} className="p-4 transition-colors hover:bg-muted/30">
                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => toggle(e.id)}
                        className="rounded p-0.5 text-muted-foreground hover:bg-accent"
                        aria-label={isExp ? 'Collapse' : 'Expand'}
                      >
                        {isExp ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </button>
                      <StatusBadge status={e.verdict} dot />
                      <StatusBadge status={e.outcome} />
                      <span className="font-mono text-xs font-semibold">{e.id}</span>
                      <span className="text-xs text-muted-foreground">· {conn?.name || e.connectionId}</span>
                    </div>
                    <p className="mt-1 font-mono text-xs text-foreground/90 truncate">{e.candidate}</p>
                  </div>
                  <div className="flex items-center gap-3 self-end md:self-center">
                    <span className="text-xs text-muted-foreground" title={absoluteTime(e.createdAtISO)}>
                      {relativeTime(e.createdAtISO)}
                    </span>
                    <Button variant="outline" size="sm" asChild>
                      <Link href={`/experiments/${e.id}`}>View report</Link>
                    </Button>
                  </div>
                </div>

                {isExp && (
                  <div className="mt-3 border-t border-border/60 pt-3 text-xs space-y-2 text-muted-foreground">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div>
                        <span className="font-medium text-foreground">Significance:</span> {e.significance}
                      </div>
                      <div>
                        <span className="font-medium text-foreground">Regression Rate:</span> {e.regressionRatePct}%
                      </div>
                      <div>
                        <span className="font-medium text-foreground">95% CI:</span> [{e.ciLow}ms, {e.ciHigh}ms]
                      </div>
                      <div>
                        <span className="font-medium text-foreground">Approver:</span> {e.approver || '—'}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone = 'text-foreground' }: { label: string; value: number; tone?: string }) {
  return (
    <Card>
      <div className="p-4">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={`tnum mt-1 text-2xl font-semibold ${tone}`}>{value}</p>
      </div>
    </Card>
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
