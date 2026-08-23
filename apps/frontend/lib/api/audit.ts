import { apiClient } from './client';
import type { ActivityItem } from '../../types/types';

interface BackendAuditLog {
  id: string;
  user_id?: string | null;
  connection_id?: string | null;
  action_type: string;
  target_entity: string;
  target_id?: string | null;
  details?: Record<string, unknown> | null;
  timestamp: string;
}

interface BackendAuditResponse {
  total: number;
  items: BackendAuditLog[];
}

function mapActionKind(actionType: string): ActivityItem['kind'] {
  const norm = actionType.toUpperCase();
  if (norm.includes('ROLLBACK')) return 'rollback';
  if (norm.includes('COMMIT') || norm.includes('APPLIED') || norm.includes('CANARY_SUCCESS')) return 'commit';
  if (norm.includes('APPROV')) return 'approve';
  if (norm.includes('FORECAST')) return 'forecast';
  return 'diagnose';
}

function formatAuditMessage(log: BackendAuditLog): string {
  const details = log.details || {};
  if (log.action_type === 'DIAGNOSIS_GENERATED') {
    const cause = details.primary_root_cause ? String(details.primary_root_cause) : 'issues';
    return `Root cause analysis completed: ${cause} detected.`;
  }
  if (log.action_type === 'CANARY_START') {
    return 'Guarded canary deployment started on live database.';
  }
  if (log.action_type === 'CANARY_COMMIT') {
    return 'Canary verification succeeded; changes committed.';
  }
  if (log.action_type === 'CANARY_ROLLBACK') {
    return 'Canary regression threshold breached; automated rollback executed.';
  }
  if (log.action_type === 'RECOMMENDATION_APPROVED') {
    return 'Candidate optimization approved for canary deployment.';
  }
  return `${log.action_type.replace(/_/g, ' ').toLowerCase()} on ${log.target_entity}.`;
}

export const auditApi = {
  list: async (limit = 20): Promise<ActivityItem[]> => {
    try {
      const data = await apiClient.get<BackendAuditResponse | BackendAuditLog[]>(`/audit/logs?limit=${limit}`);
      const logs = Array.isArray(data) ? data : (data?.items || []);
      return logs.map((log) => ({
        id: log.id,
        timeISO: log.timestamp || new Date().toISOString(),
        connectionId: log.connection_id || 'system',
        message: formatAuditMessage(log),
        kind: mapActionKind(log.action_type),
      }));
    } catch (err) {
      console.warn('[auditApi.list] Failed to fetch live audit logs:', err);
      return [];
    }
  },
};

