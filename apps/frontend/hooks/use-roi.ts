'use client';

import { useQuery } from '@tanstack/react-query';
import { roiApi } from '../lib/api/roi';

export function useRoiQuery(connectionIds: string[] = []) {
  return useQuery({
    queryKey: ['roi', { connectionIds }],
    queryFn: () => roiApi.list(connectionIds),
    enabled: connectionIds.length > 0,
  });
}

export function useRoiSummaryQuery(connectionId?: string) {
  return useQuery({
    queryKey: ['roi', 'summary', connectionId],
    queryFn: () => roiApi.getSummary(connectionId as string),
    enabled: Boolean(connectionId),
  });
}
