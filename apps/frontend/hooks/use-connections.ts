'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { connectionsApi, type CreateConnectionPayload } from '../lib/api/connections';

export const CONNECTIONS_QUERY_KEY = ['connections'] as const;

export function useConnectionsQuery() {
  return useQuery({
    queryKey: CONNECTIONS_QUERY_KEY,
    queryFn: () => connectionsApi.list(),
  });
}

export function useConnectionDetailQuery(id: string | null | undefined) {
  return useQuery({
    queryKey: ['connections', id],
    queryFn: () => (id ? connectionsApi.getById(id) : null),
    enabled: Boolean(id),
  });
}

export function useCreateConnectionMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateConnectionPayload) => connectionsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONNECTIONS_QUERY_KEY });
    },
  });
}

export function useTestConnectionMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => connectionsApi.testConnection(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['connections', id] });
      queryClient.invalidateQueries({ queryKey: CONNECTIONS_QUERY_KEY });
    },
  });
}

export function useTestNewConnectionMutation() {
  return useMutation({
    mutationFn: (payload: CreateConnectionPayload) => connectionsApi.testNewConnection(payload),
  });
}
