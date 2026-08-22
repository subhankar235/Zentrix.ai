'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { diagnosticsApi } from '../lib/api/diagnostics';

export const DIAGNOSTICS_QUERY_KEY = ['diagnostics'] as const;

export function useDiagnosticsQuery(connectionId?: string | null) {
  return useQuery({
    queryKey: connectionId ? ['diagnostics', { connectionId }] : DIAGNOSTICS_QUERY_KEY,
    queryFn: () => diagnosticsApi.list(connectionId),
  });
}

export function useDiagnosisDetailQuery(id: string | null | undefined) {
  return useQuery({
    queryKey: ['diagnostics', id],
    queryFn: () => (id ? diagnosticsApi.getById(id) : null),
    enabled: Boolean(id),
  });
}

export function useRecommendationsQuery(diagnosisId?: string) {
  return useQuery({
    queryKey: ['recommendations', diagnosisId || 'all'],
    queryFn: () => diagnosticsApi.getRecommendations(diagnosisId),
  });
}

export function useTriggerDiagnosisMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (connectionId: string) => diagnosticsApi.trigger(connectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DIAGNOSTICS_QUERY_KEY });
    },
  });
}
