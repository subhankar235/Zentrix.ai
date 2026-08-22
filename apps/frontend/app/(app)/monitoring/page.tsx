'use client';

import * as React from 'react';
import { useSearchParams } from 'next/navigation';
import { Activity, Pause, Play } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import { MetricChart } from '@/components/monitoring/metric-chart';
import { SlowQueryTable } from '@/components/monitoring/slow-query-table';
import { StatusBadge } from '@/components/status-badge';
import { Button } from '@/components/ui/button';
import { LoadingState, EmptyState } from '@/components/ui/state-feedback';
import { useConnectionsQuery } from '@/hooks/use-connections';
import { useLiveMetricsQuery } from '@/hooks/use-live-metrics';
import { useAppStore } from '@/stores/use-app-store';
import type { DatabaseConnection } from '@/types/types';

export default function MonitoringPage() {
  return (
    <React.Suspense fallback={<LoadingState message="Loading monitoring view..." />}>
      <MonitoringContent />
    </React.Suspense>
  );
}

function MonitoringContent() {
  const { data: connections = [], isLoading, isError: connectionsError } = useConnectionsQuery();
  const searchParams = useSearchParams();
  const queryConnectionId = searchParams.get('connectionId');
  const storeSelectedId = useAppStore((s) => s.selectedConnectionId);
  const selectedId = queryConnectionId || storeSelectedId || connections[0]?.id;
  const setSelectedId = useAppStore((s) => s.setSelectedConnectionId);

  React.useEffect(() => {
    if (queryConnectionId) setSelectedId(queryConnectionId);
  }, [queryConnectionId, setSelectedId]);

  const conn = connections.find((c) => c.id === selectedId) || connections[0];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Live monitoring" />
        <LoadingState message="Connecting to telemetry stream..." />
      </div>
    );
  }

  if (connectionsError) {
    return (
      <div className="space-y-6">
        <PageHeader title="Live monitoring" />
        <EmptyState
          title="Could not load database connections"
          description="The monitoring API is unavailable. Confirm the backend is running and reload this page."
        />
      </div>
    );
  }

  if (!conn) {
    return (
      <div className="space-y-6">
        <PageHeader title="Live monitoring" />
        <EmptyState title="No database selected" description="Add or select a database connection to stream live telemetry metrics." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <span className="text-xs text-muted-foreground font-medium">Selected Connection:</span>
        <select
          value={conn.id}
          onChange={(e) => setSelectedId(e.target.value)}
          className="h-8 rounded-md border border-border bg-background px-2 text-xs outline-none focus:ring-2 focus:ring-ring font-mono"
        >
          {connections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.provider})
            </option>
          ))}
        </select>
      </div>

      <LiveMetrics key={conn.id} conn={conn} />
    </div>
  );
}

function LiveMetrics({ conn }: { conn: DatabaseConnection }) {
  const isLive = useAppStore((s) => s.isLiveMode);
  const setIsLive = useAppStore((s) => s.setIsLiveMode);
  const pollingIntervalMs = useAppStore((s) => s.pollingIntervalMs);
  const setPollingIntervalMs = useAppStore((s) => s.setPollingIntervalMs);
  const { data: snapshot, isError, error } = useLiveMetricsQuery(conn.id);

  if (isError) {
    return (
      <EmptyState
        title="Could not read live telemetry"
        description={error instanceof Error ? error.message : 'The selected database telemetry request failed.'}
      />
    );
  }

  if (!snapshot) return <LoadingState message="Reading live PostgreSQL telemetry..." />;

  const hasTelemetry =
    snapshot.query_telemetry_available ||
    snapshot.table_telemetry_available ||
    snapshot.top_queries.length > 0 ||
    snapshot.active_tables_count > 0;
  const pointTime = Date.parse(snapshot.window_end);
  const point = (value: number | null | undefined) =>
    value == null || Number.isNaN(pointTime) ? [] : [{ t: pointTime, value }];
  const series = {
    avg: point(snapshot.avg_latency_ms),
    slowest: point(snapshot.p95_latency_ms),
    cache: point(snapshot.cache_hit_ratio == null ? null : snapshot.cache_hit_ratio * 100),
    queries: point(snapshot.total_queries),
    tables: point(snapshot.active_tables_count),
  };
  const metricCards: Array<{
    key: keyof typeof series;
    label: string;
    unit: string;
    value: number;
    tone: 'primary' | 'danger' | 'success' | 'info' | 'warning';
  }> = [
    { key: 'avg' as const, label: 'Average latency', unit: 'ms', value: snapshot.avg_latency_ms, tone: 'primary' as const },
    { key: 'slowest' as const, label: 'Highest observed latency', unit: 'ms', value: snapshot.p95_latency_ms, tone: 'danger' as const },
    ...(snapshot.cache_hit_ratio == null
      ? []
      : [{ key: 'cache' as const, label: 'Cache hit ratio', unit: '%', value: snapshot.cache_hit_ratio * 100, tone: 'success' as const }]),
    { key: 'queries' as const, label: 'Statement calls', unit: '', value: snapshot.total_queries, tone: 'info' as const },
    { key: 'tables' as const, label: 'Active tables', unit: '', value: snapshot.active_tables_count, tone: 'warning' as const },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Live monitoring"
        description={`Live signal from ${conn.name}. Values come directly from PostgreSQL system views and refresh every ${pollingIntervalMs / 1000}s.`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={pollingIntervalMs}
              onChange={(e) => setPollingIntervalMs(Number(e.target.value))}
              className="h-8 rounded-md border border-border bg-background px-2 text-xs font-medium outline-none"
            >
              <option value={2000}>Poll: 2s</option>
              <option value={5000}>Poll: 5s</option>
              <option value={10000}>Poll: 10s</option>
            </select>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsLive(!isLive)}
              className="gap-1.5"
            >
              {isLive ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
              {isLive ? 'Pause' : 'Resume'}
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <span
            className={`h-2 w-2 rounded-full ${isLive ? 'animate-pulse bg-success' : 'bg-muted-foreground'}`}
          />
          {isLive ? 'Live Streaming' : 'Polling Paused'}
        </span>
        <StatusBadge status={conn.health} dot />
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Activity className="h-3.5 w-3.5" />
          {conn.provider}{conn.region ? ` · ${conn.region}` : ''}{conn.version ? ` · ${conn.version}` : ''}
        </span>
        <span className="text-xs text-muted-foreground">
          Query stats: {snapshot.query_telemetry_available ? 'available' : 'unavailable'}
        </span>
      </div>

      {hasTelemetry ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {metricCards.map((metric) => (
            <MetricChart
              key={metric.key}
              label={metric.label}
              unit={metric.unit}
              data={series[metric.key] ?? []}
              current={metric.value}
              tone={metric.tone}
              format={metric.unit === '' ? (n) => Math.round(n).toLocaleString() : undefined}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No telemetry available yet"
          description="The connection is valid, but PostgreSQL has not returned query or table statistics for this snapshot."
        />
      )}

      <SlowQueryTable
        realQueries={snapshot?.top_queries}
      />
    </div>
  );
}
