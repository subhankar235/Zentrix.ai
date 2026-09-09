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
    const data = await apiClient.get<{
      connection_id: string;
      degradation_probability: number;
      is_flagged_for_action: boolean;
      curve: Array<{ timestamp: string; horizon_hours?: number; predicted_probability: number; confidence_lower: number; confidence_upper: number }>;
      suggested_strategies: string[];
      threshold_probability: number;
      threshold_day?: number | null;
      model_version?: string;
      confidence?: number;
      data_quality?: string;
      headline: string;
      calibration: Array<{ bucket: string; predicted: number; actual: number; samples: number }>;
      mae: Array<{ version: string; mae: number }>;
      bandit: Array<{ strategy: string; reward: number; pulls: number }>;
    }>(`/forecasts/${connectionId}`);
    const threshold = data.threshold_probability || 0.4;
    return {
      connectionId: data.connection_id,
      headline: data.headline,
      isFlaggedForAction: data.is_flagged_for_action,
      thresholdDay: data.threshold_day ?? data.curve.findIndex((point) => point.predicted_probability >= threshold) / 4,
      thresholdProbability: threshold,
      suggestedStrategies: data.suggested_strategies,
      curve: data.curve.map((point, index) => ({
        day: point.horizon_hours != null
          ? point.horizon_hours / 24
          : index / 4,
        probability: point.predicted_probability,
        lower: point.confidence_lower,
        upper: point.confidence_upper,
      })),
      suggestions: [],
      calibration: data.calibration,
      mae: data.mae,
      bandit: data.bandit,
      confidence: data.confidence,
      dataQuality: data.data_quality,
    };
  },

  getModelPerformance: async (): Promise<ModelPerformanceResponse> => {
    return apiClient.get<ModelPerformanceResponse>('/models/performance');
  },
};
