import { apiClient } from './client';
import type { DatabaseConnection } from '../../types/types';

export interface CreateConnectionPayload {
  name: string;
  provider?: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password?: string;
  ssl_mode: string;
  connection_string?: string;
}

export interface ConnectionTestResult {
  success: boolean;
  reachability: boolean;
  credentials: boolean;
  pgStatStatements: boolean;
  readOnlyRole: boolean;
  message?: string;
  latencyMs?: number;
}

interface BackendConnection {
  id: string;
  name: string;
  provider?: string | null;
  host: string;
  port: number;
  database_name: string;
  username: string;
  is_active: boolean;
  permission_status?: Record<string, boolean> | null;
  last_checked_at?: string | null;
  created_at: string;
  updated_at: string;
}

function toProvider(provider?: string | null): DatabaseConnection['provider'] {
  if (provider?.toLowerCase().includes('rds')) return 'AWS RDS';
  if (provider?.toLowerCase().includes('supabase')) return 'Supabase';
  if (provider?.toLowerCase().includes('self')) return 'Self-hosted';
  return 'Neon';
}

function toConnection(data: BackendConnection): DatabaseConnection {
  const permissions = data.permission_status || {};
  const checked = Boolean(data.last_checked_at);
  const healthy =
    data.is_active &&
    Boolean(permissions.pg_stat_statements) &&
    Boolean(permissions.pg_stat_activity) &&
    Boolean(permissions.pg_stat_user_tables) &&
    Boolean(permissions.pg_statio_user_tables) &&
    Boolean(permissions.read_only_role);

  return {
    id: data.id,
    name: data.name,
    provider: toProvider(data.provider),
    host: data.host,
    region: '',
    status: healthy ? 'Connected' : 'Needs Attention',
    health: healthy ? 'Healthy' : 'Critical',
    lastCheckedISO: data.last_checked_at || data.updated_at || data.created_at,
    version: 'PostgreSQL',
    checks: {
      reachability: checked,
      credentials: checked,
      pgStatStatements: Boolean(permissions.pg_stat_statements),
      readOnlyRole: Boolean(permissions.read_only_role),
    },
    latencySparkline: [],
    activeProblems: undefined,
  };
}

export const connectionsApi = {
  list: async (): Promise<DatabaseConnection[]> => {
    const data = await apiClient.get<BackendConnection[]>('/connections');
    return data.map(toConnection);
  },

  getById: async (id: string): Promise<DatabaseConnection> => {
    const data = await apiClient.get<BackendConnection>(`/connections/${id}`);
    return toConnection(data);
  },

  create: async (payload: CreateConnectionPayload): Promise<DatabaseConnection> => {
    const data = await apiClient.post<BackendConnection>('/connections', payload);
    return toConnection(data);
  },

  testNewConnection: async (payload: CreateConnectionPayload): Promise<ConnectionTestResult> => {
    const data = await apiClient.post<{
      success: boolean;
      permissions: Record<string, boolean>;
      latency_ms?: number | null;
      error?: string | null;
    }>('/connections/test', payload);

    return {
      success: data.success,
      reachability: data.success || Boolean(data.latency_ms),
      credentials: data.success || Boolean(data.latency_ms),
      pgStatStatements: Boolean(data.permissions.pg_stat_statements),
      readOnlyRole: Boolean(data.permissions.read_only_role),
      latencyMs: data.latency_ms ?? undefined,
      message: data.error ?? undefined,
    };
  },

  testConnection: async (id: string): Promise<ConnectionTestResult> => {
    const data = await apiClient.post<{
      success: boolean;
      permissions: Record<string, boolean>;
      latency_ms?: number | null;
      error?: string | null;
    }>(`/connections/${id}/test`);

    return {
      success: data.success,
      reachability: data.success || Boolean(data.latency_ms),
      credentials: data.success || Boolean(data.latency_ms),
      pgStatStatements: Boolean(data.permissions.pg_stat_statements),
      readOnlyRole: Boolean(data.permissions.read_only_role),
      latencyMs: data.latency_ms ?? undefined,
      message: data.error ?? undefined,
    };
  },
};
