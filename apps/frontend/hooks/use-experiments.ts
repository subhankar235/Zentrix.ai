'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { experimentsApi } from '../lib/api/experiments';
import type { Recommendation } from '../types/types';

export const EXPERIMENTS_QUERY_KEY = ['experiments'] as const;

export function useExperimentsQuery() {
  return useQuery({
    queryKey: EXPERIMENTS_QUERY_KEY,
    queryFn: () => experimentsApi.list(),
  });
}

export function useExperimentDetailQuery(id: string | null | undefined) {
  return useQuery({
    queryKey: ['experiments', id],
    queryFn: () => (id ? experimentsApi.getById(id) : null),
    enabled: Boolean(id),
  });
}

export function useSimulateMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (recommendation: Recommendation) => experimentsApi.simulate(recommendation),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: EXPERIMENTS_QUERY_KEY });
    },
  });
}

export function useSeedDevCanaryMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (connectionId: string) => experimentsApi.seedDevCanary(connectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: EXPERIMENTS_QUERY_KEY });
    },
  });
}

export function useApproveExperimentMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) => experimentsApi.approve(id, notes),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: EXPERIMENTS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ['experiments', variables.id] });
    },
  });
}

export function useRejectExperimentMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) => experimentsApi.reject(id, reason),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: EXPERIMENTS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ['experiments', variables.id] });
    },
  });
}
