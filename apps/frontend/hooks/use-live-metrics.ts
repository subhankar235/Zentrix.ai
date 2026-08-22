'use client';

import { useQuery } from '@tanstack/react-query';
import { monitoringApi } from '../lib/api/monitoring';
import { useAppStore } from '../stores/use-app-store';

export function useLiveMetricsQuery(connectionId?: string | null) {
  const pollingIntervalMs = useAppStore((s) => s.pollingIntervalMs);
  const isLiveMode = useAppStore((s) => s.isLiveMode);

  return useQuery({
    queryKey: ['live-metrics', connectionId],
    queryFn: () => {
      if (!connectionId) throw new Error('A database connection is required');
      return monitoringApi.getLiveSnapshot(connectionId);
    },
    enabled: Boolean(connectionId),
    refetchInterval: isLiveMode && pollingIntervalMs > 0 ? pollingIntervalMs : false,
    refetchIntervalInBackground: false,
    staleTime: 1000,
  });
}
