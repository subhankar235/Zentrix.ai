'use client';

import { useQuery } from '@tanstack/react-query';
import { forecastsApi } from '../lib/api/forecasts';

export const FORECASTS_QUERY_KEY = ['forecasts'] as const;

export function useForecastsQuery() {
  return useQuery({
    queryKey: FORECASTS_QUERY_KEY,
    queryFn: () => forecastsApi.list(),
  });
}

export function useForecastDetailQuery(connectionId: string | null | undefined) {
  const targetId = connectionId || 'prod-orders-db';
  return useQuery({
    queryKey: ['forecasts', targetId],
    queryFn: () => forecastsApi.getByConnectionId(targetId),
  });
}

export function useModelPerformanceQuery() {
  return useQuery({
    queryKey: ['forecasts', 'models', 'performance'],
    queryFn: () => forecastsApi.getModelPerformance(),
  });
}
