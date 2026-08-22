import { apiClient } from './client';

export interface TelemetryQuery {
  id?: string;
  query_hash: string;
  queryid?: number;
  query_text?: string;
  calls: number;
  mean_exec_time: number;
  max_exec_time: number;
  min_exec_time?: number;
  total_exec_time?: number;
  rows?: number;
}

export interface TelemetrySummaryResponse {
  connection_id: string;
  window_start: string;
  window_end: string;
  total_queries: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  cache_hit_ratio: number | null;
  active_tables_count: number;
  query_telemetry_available: boolean;
  table_telemetry_available: boolean;
  top_queries: TelemetryQuery[];
  top_bloated_tables: unknown[];
}

export const monitoringApi = {
  getLiveSnapshot: async (connectionId: string): Promise<TelemetrySummaryResponse> => {
    return apiClient.get<TelemetrySummaryResponse>(`/connections/${connectionId}/telemetry`);
  },
};
