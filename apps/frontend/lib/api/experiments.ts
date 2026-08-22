import { apiClient } from './client';
import type { Experiment } from '../../types/types';
import { experiments as mockExperiments } from '../mock-data';

export const experimentsApi = {
  list: async (): Promise<Experiment[]> => {
    try {
      const data = await apiClient.get<Experiment[]>('/experiments');
      if (Array.isArray(data) && data.length > 0) return data;
      return mockExperiments;
    } catch (err) {
      console.warn('[experimentsApi.list] Falling back to mock data:', err);
      return mockExperiments;
    }
  },

  getById: async (id: string): Promise<Experiment> => {
    try {
      return await apiClient.get<Experiment>(`/experiments/${id}`);
    } catch (err) {
      console.warn(`[experimentsApi.getById] Falling back to mock for ${id}:`, err);
      const found = mockExperiments.find((e) => e.id === id);
      if (found) return found;
      throw err;
    }
  },

  simulate: async (recommendationId: string): Promise<{ experimentId: string; status: string }> => {
    try {
      return await apiClient.post(`/recommendations/${recommendationId}/simulate`);
    } catch (err) {
      console.warn('[experimentsApi.simulate] Falling back to simulated run:', err);
      return { experimentId: 'exp-shadow-' + Date.now(), status: 'SIMULATING' };
    }
  },

  approve: async (id: string, notes?: string): Promise<Experiment> => {
    try {
      return await apiClient.post<Experiment>(`/experiments/${id}/approve`, { notes });
    } catch (err) {
      console.warn(`[experimentsApi.approve] Falling back to local state for ${id}:`, err);
      const exp = mockExperiments.find((e) => e.id === id);
      if (exp) {
        exp.approvalState = 'APPROVED';
        exp.outcome = 'IN_PROGRESS';
        exp.approver = 'Lead DBA';
        return exp;
      }
      throw err;
    }
  },

  reject: async (id: string, reason?: string): Promise<Experiment> => {
    try {
      return await apiClient.post<Experiment>(`/experiments/${id}/reject`, { reason });
    } catch (err) {
      console.warn(`[experimentsApi.reject] Falling back to local state for ${id}:`, err);
      const exp = mockExperiments.find((e) => e.id === id);
      if (exp) {
        exp.approvalState = 'REJECTED';
        exp.outcome = 'ROLLBACK';
        exp.rollbackReason = reason || 'Rejected by operator';
        return exp;
      }
      throw err;
    }
  },
};
