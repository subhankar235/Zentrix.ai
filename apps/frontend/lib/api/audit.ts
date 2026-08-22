import { apiClient } from './client';
import type { ActivityItem } from '../../types/types';
import { activity as mockActivity } from '../mock-data';

export const auditApi = {
  list: async (limit = 20): Promise<ActivityItem[]> => {
    try {
      const data = await apiClient.get<ActivityItem[]>(`/audit?limit=${limit}`);
      if (Array.isArray(data) && data.length > 0) return data;
      return mockActivity;
    } catch (err) {
      console.warn('[auditApi.list] Falling back to mock activity:', err);
      return mockActivity;
    }
  },
};
