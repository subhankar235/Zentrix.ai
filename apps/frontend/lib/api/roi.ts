import { apiClient } from './client';
import type { RoiEntry } from '../../types/types';

export interface RoiSummary {
  connection_id: string;
  total_monthly_savings_usd: number;
  total_compute_savings_usd: number;
  total_storage_savings_usd: number;
  total_io_savings_usd: number;
  optimizations_count: number;
  roi_breakdowns: Array<{
    id: string;
    experiment_id: string;
    connection_id: string;
    estimated_monthly_savings_usd: number;
    compute_savings_usd: number;
    storage_savings_usd: number;
    io_savings_usd: number;
    assumed_pricing_tier: string;
    frequency_per_day: number;
    calculation_details?: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
  }>;
}

export const roiApi = {
  list: async (connectionIds: string[]): Promise<RoiEntry[]> => {
    const summaries = await Promise.all(
      connectionIds.map((connectionId) => apiClient.get<RoiSummary>(`/roi/${connectionId}`)),
    );

    return summaries.flatMap((summary) => summary.roi_breakdowns.map((record) => ({
      id: record.id,
      connectionId: record.connection_id,
      description: 'Verified optimization',
      improvement: `Compute ${record.compute_savings_usd.toFixed(2)} USD + I/O ${record.io_savings_usd.toFixed(2)} USD monthly`,
      monthlySavingsUsd: record.estimated_monthly_savings_usd,
      committedAtISO: record.created_at,
    })));
  },

  getSummary: async (connectionId: string): Promise<RoiSummary> => {
    return apiClient.get<RoiSummary>(`/roi/${connectionId}`);
  },
};
