import { apiClient } from './client';
import type { Forecast, CalibrationBucket, MaePoint, BanditArm } from '../../types/types';
import { forecasts as mockForecasts } from '../mock-data';

export interface ModelPerformanceResponse {
  calibration: CalibrationBucket[];
  mae: MaePoint[];
  bandit: BanditArm[];
}

export const forecastsApi = {
  list: async (): Promise<Forecast[]> => {
    try {
      const data = await apiClient.get<Forecast[]>('/forecasts');
      if (Array.isArray(data) && data.length > 0) return data;
      return Object.values(mockForecasts);
    } catch (err) {
      console.warn('[forecastsApi.list] Falling back to mock data:', err);
      return Object.values(mockForecasts);
    }
  },

  getByConnectionId: async (connectionId: string): Promise<Forecast> => {
    try {
      return await apiClient.get<Forecast>(`/forecasts/${connectionId}`);
    } catch (err) {
      console.warn(`[forecastsApi.getByConnectionId] Falling back to mock for ${connectionId}:`, err);
      const found = mockForecasts[connectionId] || Object.values(mockForecasts)[0];
      return found;
    }
  },

  getModelPerformance: async (): Promise<ModelPerformanceResponse> => {
    try {
      return await apiClient.get<ModelPerformanceResponse>('/forecasts/models/performance');
    } catch (err) {
      console.warn('[forecastsApi.getModelPerformance] Falling back to mock performance:', err);
      const first = Object.values(mockForecasts)[0];
      return {
        calibration: first?.calibration || [],
        mae: first?.mae || [],
        bandit: first?.bandit || [],
      };
    }
  },
};
