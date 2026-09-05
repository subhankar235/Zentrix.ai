import { apiClient } from './client';
import type { Forecast, CalibrationBucket, MaePoint, BanditArm } from '../../types/types';

export interface ModelPerformanceResponse {
  calibration: CalibrationBucket[];
  mae: MaePoint[];
  bandit: BanditArm[];
}

export const forecastsApi = {
  list: async (): Promise<Forecast[]> => {
    return apiClient.get<Forecast[]>('/forecasts');
  },

  getByConnectionId: async (connectionId: string): Promise<Forecast> => {
    return apiClient.get<Forecast>(`/forecasts/${connectionId}`);
  },

  getModelPerformance: async (): Promise<ModelPerformanceResponse> => {
    return apiClient.get<ModelPerformanceResponse>('/forecasts/models/performance');
  },
};
