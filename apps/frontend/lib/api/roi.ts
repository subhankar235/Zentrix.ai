import { apiClient } from './client';
import type { RoiEntry } from '../../types/types';

export interface RoiSummary {
  totalMonthlySavingsUsd: number;
  totalAnnualProjectedUsd: number;
  verifiedOptimizationsCount: number;
  averageLatencyReductionPct: number;
}

export const roiApi = {
  list: async (connectionId?: string | null): Promise<RoiEntry[]> => {
    const endpoint = connectionId ? `/roi?connectionId=${connectionId}` : '/roi';
    return apiClient.get<RoiEntry[]>(endpoint);
  },

  getSummary: async (): Promise<RoiSummary> => {
    return apiClient.get<RoiSummary>('/roi/summary');
  },
};
