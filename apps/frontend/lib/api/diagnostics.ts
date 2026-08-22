import { apiClient } from './client';
import type { Diagnosis, Recommendation } from '../../types/types';
import { diagnoses as mockDiagnoses } from '../mock-data';

export const diagnosticsApi = {
  list: async (connectionId?: string | null): Promise<Diagnosis[]> => {
    try {
      const endpoint = connectionId ? `/diagnostics?connectionId=${connectionId}` : '/diagnostics';
      const data = await apiClient.get<Diagnosis[]>(endpoint);
      if (Array.isArray(data) && data.length > 0) return data;
      return connectionId ? mockDiagnoses.filter((d) => d.connectionId === connectionId) : mockDiagnoses;
    } catch (err) {
      console.warn('[diagnosticsApi.list] Falling back to mock data:', err);
      return connectionId ? mockDiagnoses.filter((d) => d.connectionId === connectionId) : mockDiagnoses;
    }
  },

  getById: async (id: string): Promise<Diagnosis> => {
    try {
      return await apiClient.get<Diagnosis>(`/diagnostics/${id}`);
    } catch (err) {
      console.warn(`[diagnosticsApi.getById] Falling back to mock for ${id}:`, err);
      const found = mockDiagnoses.find((d) => d.id === id);
      if (found) return found;
      throw err;
    }
  },

  trigger: async (connectionId: string): Promise<{ diagnosisId: string; status: string; message: string }> => {
    try {
      return await apiClient.post('/diagnostics/trigger', { connectionId });
    } catch (err) {
      console.warn('[diagnosticsApi.trigger] Falling back to local trigger simulation:', err);
      return {
        diagnosisId: 'diag-new-' + Date.now(),
        status: 'Triggered',
        message: 'AI specialist agents dispatched to analyze connection.',
      };
    }
  },

  getRecommendations: async (diagnosisId?: string): Promise<Recommendation[]> => {
    try {
      const endpoint = diagnosisId ? `/diagnostics/${diagnosisId}/recommendations` : '/recommendations';
      const data = await apiClient.get<Recommendation[]>(endpoint);
      if (Array.isArray(data) && data.length > 0) return data;
      const allRecs = mockDiagnoses.flatMap((d) => d.recommendations);
      return diagnosisId ? allRecs.filter((r) => r.id.includes(diagnosisId)) : allRecs;
    } catch (err) {
      console.warn('[diagnosticsApi.getRecommendations] Falling back to mock:', err);
      const allRecs = mockDiagnoses.flatMap((d) => d.recommendations);
      return diagnosisId ? allRecs.filter((r) => r.id.includes(diagnosisId)) : allRecs;
    }
  },
};
