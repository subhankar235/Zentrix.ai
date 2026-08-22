'use client';

import { useQuery } from '@tanstack/react-query';
import { roiApi } from '../lib/api/roi';

export function useRoiQuery(connectionId?: string | null) {
  return useQuery({
    queryKey: connectionId ? ['roi', { connectionId }] : ['roi'],
    queryFn: () => roiApi.list(connectionId),
  });
}

export function useRoiSummaryQuery() {
  return useQuery({
    queryKey: ['roi', 'summary'],
    queryFn: () => roiApi.getSummary(),
  });
}
