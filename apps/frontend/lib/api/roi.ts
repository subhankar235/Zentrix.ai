import { apiClient } from './client';
import type { RoiEntry } from '../../types/types';
import { roiEntries as mockRoiEntries } from '../mock-data';

export interface RoiSummary {
  totalMonthlySavingsUsd: number;
  totalAnnualProjectedUsd: number;
  verifiedOptimizationsCount: number;
  averageLatencyReductionPct: number;
}

export const roiApi = {
  list: async (connectionId?: string | null): Promise<RoiEntry[]> => {
    try {
      const endpoint = connectionId ? `/roi?connectionId=${connectionId}` : '/roi';
      const data = await apiClient.get<RoiEntry[]>(endpoint);
      if (Array.isArray(data) && data.length > 0) return data;
      return connectionId ? mockRoiEntries.filter((r) => r.connectionId === connectionId) : mockRoiEntries;
    } catch (err) {
      console.warn('[roiApi.list] Falling back to mock data:', err);
      return connectionId ? mockRoiEntries.filter((r) => r.connectionId === connectionId) : mockRoiEntries;
    }
  },

  getSummary: async (): Promise<RoiSummary> => {
    try {
      return await apiClient.get<RoiSummary>('/roi/summary');
    } catch (err) {
      console.warn('[roiApi.getSummary] Falling back to mock summary:', err);
      const configured = mockRoiEntries.filter((e) => e.monthlySavingsUsd != null);
      const totalMonthly = configured.reduce((sum, e) => sum + (e.monthlySavingsUsd ?? 0), 0);
      return {
        totalMonthlySavingsUsd: totalMonthly,
        totalAnnualProjectedUsd: totalMonthly * 12,
        verifiedOptimizationsCount: configured.length,
        averageLatencyReductionPct: 38.5,
      };
    }
  },
};
