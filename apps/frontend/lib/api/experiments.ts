import { apiClient } from './client';
import type { Experiment, Recommendation } from '../../types/types';

interface BackendExperiment {
  id: string;
  connection_id: string;
  diagnosis_id?: string | null;
  strategy: string;
  candidate_sql: string;
  baseline_latency: number;
  baseline_p95: number;
  baseline_cpu: number;
  baseline_io: number;
  candidate_latency: number;
  candidate_p95: number;
  candidate_cpu: number;
  candidate_io: number;
  predicted_latency_delta: number;
  actual_latency_delta?: number | null;
  statistical_significance: boolean;
  confidence_interval_low?: number | null;
  confidence_interval_high?: number | null;
  skeptic_findings?: Record<string, unknown> | null;
  policy_verdict: string;
  success: boolean;
  risk: string;
  rollback: boolean;
  status: string;
  created_at: string;
  updated_at: string;
}

function strategyType(strategy: string): Recommendation['type'] {
  if (strategy.includes('INDEX')) return 'INDEX';
  if (strategy.includes('ANALYZE') || strategy.includes('STATISTICS')) return 'STATISTICS';
  if (strategy.includes('VACUUM')) return 'VACUUM';
  if (strategy.includes('CONFIG')) return 'CONFIG';
  return 'QUERY_REWRITE';
}

function toExperiment(data: BackendExperiment): Experiment {
  const findings = data.skeptic_findings || {};
  const verification = (findings.verification || {}) as Record<string, unknown>;
  const policy = (findings.policy || {}) as Record<string, unknown>;
  const isFixture = findings.fixture === true;
  const baselineLatency = data.baseline_latency || (isFixture ? 100 : 0);
  const candidateLatency = data.candidate_latency || (isFixture ? 90 : 0);
  const baselineP95 = data.baseline_p95 || (isFixture ? 120 : 0);
  const candidateP95 = data.candidate_p95 || (isFixture ? 110 : 0);
  const riskFactors = (findings.risk_factors as string[] | undefined) || [];
  const verdict = (data.policy_verdict === 'APPROVE' ? 'VERIFIED' : data.policy_verdict) as Experiment['verdict'];
  const outcome: Experiment['outcome'] = data.status === 'ROLLED_BACK' || data.rollback
    ? 'ROLLBACK'
    : data.status === 'DEPLOYED'
      ? 'IN_PROGRESS'
      : data.status === 'APPROVED'
        ? 'IN_PROGRESS'
        : verdict === 'REJECTED'
          ? 'REJECTED'
          : 'AWAITING_APPROVAL';
  const currentStage = data.status === 'PENDING'
    ? 'HypoPG filter'
    : data.status === 'SIMULATED'
      ? 'Policy engine'
      : data.status === 'APPROVED' || data.status === 'DEPLOYED'
        ? 'Policy engine'
        : 'Policy engine';

  return {
    id: data.id,
    connectionId: data.connection_id,
    diagnosisId: data.diagnosis_id || undefined,
    candidate: data.candidate_sql,
    recommendationType: strategyType(data.strategy),
    verdict,
    outcome,
    approvalState: verdict === 'REJECTED' || data.status === 'REJECTED' || data.status === 'ROLLED_BACK'
      ? 'REJECTED'
      : data.status === 'APPROVED' || data.status === 'DEPLOYED'
      ? 'APPROVED'
      : 'PENDING_APPROVAL',
    createdAtISO: data.created_at,
    currentStage,
    comparisons: [
      { metric: 'Mean latency', unit: 'ms', baseline: baselineLatency, candidate: candidateLatency, betterWhenLower: true },
      { metric: 'P95 latency', unit: 'ms', baseline: baselineP95, candidate: candidateP95, betterWhenLower: true },
      { metric: 'CPU', unit: '', baseline: data.baseline_cpu, candidate: data.candidate_cpu, betterWhenLower: true },
      { metric: 'IO', unit: '', baseline: data.baseline_io, candidate: data.candidate_io, betterWhenLower: true },
    ],
    regressionRatePct: Number(verification.regression_rate || 0) * 100,
    ciLow: Number(data.confidence_interval_low || (isFixture ? -1 : 0)),
    ciHigh: Number(data.confidence_interval_high || (isFixture ? -0.1 : 0)),
    significance: data.statistical_significance ? 'SIGNIFICANT' : 'NOT_SIGNIFICANT',
    skepticFindings: riskFactors.map((concern) => ({
      concern,
      status: 'flagged' as const,
      note: 'Reported by the Skeptic Agent from the shadow replay.',
    })),
    policyChecks: [
      ...((policy.passed_rules as string[] | undefined) || []).map((rule) => ({ rule, passed: true })),
      ...((policy.violated_rules as string[] | undefined) || []).map((rule) => ({ rule, passed: false })),
    ],
    auditLog: [],
  };
}

export const experimentsApi = {
  seedDevCanary: async (connectionId: string): Promise<Experiment> => {
    const data = await apiClient.post<BackendExperiment>('/experiments/dev/seed-canary', {
      connection_id: connectionId,
      candidate_sql: 'ANALYZE;',
    });
    return toExperiment(data);
  },

  list: async (): Promise<Experiment[]> => {
    const data = await apiClient.get<BackendExperiment[]>('/experiments');
    return data.map(toExperiment);
  },

  getById: async (id: string): Promise<Experiment> => {
    const data = await apiClient.get<BackendExperiment>(`/experiments/${id}`);
    return toExperiment(data);
  },

  simulate: async (recommendation: Recommendation): Promise<Experiment> => {
    if (!recommendation.connectionId || !recommendation.diagnosisId || !recommendation.candidateSql) {
      throw new Error('Recommendation is missing its database, diagnosis, or candidate SQL');
    }
    const data = await apiClient.post<BackendExperiment>(`/recommendations/${recommendation.id}/simulate`, {
      strategy: recommendation.type === 'INDEX' ? 'CREATE_INDEX' : recommendation.type,
      candidate_sql: recommendation.candidateSql,
      connection_id: recommendation.connectionId,
      diagnosis_id: recommendation.diagnosisId,
    });
    return toExperiment(data);
  },

  approve: async (id: string, notes?: string): Promise<Experiment> => {
    await apiClient.post(`/recommendations/${id}/approve`, { action: 'APPROVE', reason: notes });
    await apiClient.post(`/experiments/${id}/deploy`);
    const data = await apiClient.get<BackendExperiment>(`/experiments/${id}`);
    return toExperiment(data);
  },

  reject: async (id: string, reason?: string): Promise<Experiment> => {
    await apiClient.post(`/recommendations/${id}/reject`, { action: 'REJECT', reason });
    const data = await apiClient.get<BackendExperiment>(`/experiments/${id}`);
    return toExperiment(data);
  },
};
