import { apiClient } from './client';
import type {
  ContributingCause,
  Diagnosis,
  EvidenceEdge,
  EvidenceNode,
  Recommendation,
  SupportingEvidence,
  TimelineEntry,
} from '../../types/types';

interface BackendEvidenceNode {
  id: string;
  node_type: string;
  label: string;
  agent_domain: string;
  confidence: number;
  metadata_payload?: Record<string, unknown> | null;
}

interface BackendEvidenceEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  relation_type: string;
  weight: number;
  explanation?: string | null;
}

interface BackendDiagnosis {
  id: string;
  connection_id: string;
  title: string;
  primary_root_cause: string;
  contributing_factors?: Array<Record<string, unknown>> | null;
  severity: string;
  confidence: number;
  summary: string;
  validation_plan?: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
  evidence_graph?: {
    nodes: BackendEvidenceNode[];
    edges: BackendEvidenceEdge[];
  };
}

interface BackendRecommendation {
  id: string;
  diagnosis_id: string;
  connection_id: string;
  diagnosis_title: string;
  primary_root_cause: string;
  type: Recommendation['type'];
  title: string;
  rationale: string;
  predicted_impact: string;
  uncertainty_pct: number;
  risk: Recommendation['risk'];
  candidate_sql: string;
  table_name?: string | null;
  experiment_id?: string | null;
  rank?: number;
  score?: number;
  evidence?: string[];
  prerequisites?: string[];
  rollback_sql?: string | null;
  execution_mode?: string;
  requires_hypopg?: boolean;
  ml_status?: string;
}

function text(value: unknown, fallback: string): string {
  if (value == null) return fallback;
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch {
    return fallback;
  }
}

function toNode(node: BackendEvidenceNode): EvidenceNode {
  const metadata = node.metadata_payload || {};
  const normalizedType = node.node_type.toLowerCase();
  return {
    id: node.id,
    kind: normalizedType.includes('root') || normalizedType.includes('hypothesis') ? 'cause' : normalizedType === 'metric' ? 'symptom' : 'event',
    label: node.label,
    detail: text(metadata.detail || metadata.claim || metadata.evidence, `${node.agent_domain} evidence`),
    metric: metadata.metric ? String(metadata.metric) : undefined,
    value: metadata.value != null ? String(metadata.value) : undefined,
  };
}

function toTimeline(value: unknown): TimelineEntry[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!entry || typeof entry !== 'object') return [];
    const item = entry as Record<string, unknown>;
    const event = String(item.event || 'evidence');
    const icon: TimelineEntry['icon'] = event.includes('lock')
      ? 'lock'
      : event.includes('query')
        ? 'latency'
        : event.includes('plan')
          ? 'plan'
          : 'stats';
    return [{
      timeISO: text(item.timestamp, new Date().toISOString()),
      title: event.replaceAll('_', ' '),
      detail: item.latency_ms != null ? `Observed latency: ${item.latency_ms} ms.` : 'Captured from the live PostgreSQL target.',
      icon,
    } satisfies TimelineEntry];
  });
}

function toDiagnosis(data: BackendDiagnosis): Diagnosis {
  const graph = data.evidence_graph || { nodes: [], edges: [] };
  const validation = data.validation_plan || {};
  const rootCause = data.primary_root_cause.toUpperCase() as Diagnosis['primaryRootCause'];
  const contributingCauses: ContributingCause[] = (data.contributing_factors || []).map((item, index) => ({
    rootCause: text(item.cause || item.rootCause, 'UNKNOWN') as Diagnosis['primaryRootCause'],
    rank: index === 0 ? 'CONTRIBUTING' : 'CORRELATED',
    confidencePct: Math.round(Number(item.confidence || 0) * 100),
    summary: text(item.summary || item.agent, 'Observed supporting evidence from the live database.'),
  }));
  const modelOutputs = validation.model_outputs;
  const recommendations: Recommendation[] = [];
  const supportingEvidence: SupportingEvidence[] = Array.isArray(validation.supporting_evidence)
    ? validation.supporting_evidence.map((item, index) => {
        const evidence: Record<string, unknown> =
          typeof item === 'object' && item !== null ? (item as Record<string, unknown>) : { claim: item };
        return {
          id: `${data.id}-evidence-${index}`,
          claim: text(evidence.claim || evidence.metric, 'Live PostgreSQL evidence'),
          metric: text(evidence.metric, 'observed metric'),
          value: text(evidence.value, 'observed'),
          rank: index === 0 ? 'PRIMARY' : 'CONTRIBUTING',
        };
      })
    : [];

  return {
    id: data.id,
    connectionId: data.connection_id,
    title: data.title,
    primaryRootCause: rootCause,
    confidencePct: Math.round(Number(data.confidence || 0) * 100),
    status: data.status === 'RESOLVED'
      ? 'Resolved'
      : data.status === 'OBSERVED'
        ? 'Observed'
        : data.status === 'INSUFFICIENT_EVIDENCE'
          ? 'Needs Evidence'
          : 'Active',
    detectedAtISO: data.created_at,
    lowConfidence: Number(data.confidence || 0) < 0.5,
    summary: data.summary,
    affectedObject: text(validation.affected_object, 'database'),
    telemetrySource: validation.source ? String(validation.source) : undefined,
    capturedAtISO: validation.captured_at ? String(validation.captured_at) : undefined,
    telemetryWarnings: [
      ...(Array.isArray(validation.capture_errors)
        ? validation.capture_errors.map((item) => `Telemetry source unavailable: ${text((item as Record<string, unknown>).source, 'unknown')}`)
        : []),
      ...(Array.isArray(validation.plan_errors)
        ? validation.plan_errors.map(() => 'Some query plans could not be captured from the monitored database.')
        : []),
    ],
    modelResults:
      modelOutputs && typeof modelOutputs === 'object'
        ? (modelOutputs as Diagnosis['modelResults'])
        : undefined,
    contributingCauses,
    evidenceNodes: graph.nodes.map(toNode),
    evidenceEdges: graph.edges.map((edge): EvidenceEdge => ({ from: edge.source_node_id, to: edge.target_node_id })),
    timeline: toTimeline(validation.timeline),
    supportingEvidence,
    recommendations,
  };
}

export const diagnosticsApi = {
  list: async (connectionId?: string | null): Promise<Diagnosis[]> => {
    const endpoint = connectionId ? `/diagnostics?connectionId=${encodeURIComponent(connectionId)}` : '/diagnostics';
    const data = await apiClient.get<BackendDiagnosis[]>(endpoint);
    return data.map(toDiagnosis);
  },

  getById: async (id: string): Promise<Diagnosis> => {
    const data = await apiClient.get<BackendDiagnosis>(`/diagnostics/${id}`);
    return toDiagnosis(data);
  },

  trigger: async (connectionId: string): Promise<{ diagnosisId?: string; status?: string; message?: string }> => {
    const data = await apiClient.post<BackendDiagnosis>(`/diagnostics/trigger`, { connectionId });
    return {
      diagnosisId: data.id,
      status: data.status,
      message: 'Live PostgreSQL evidence analyzed and the diagnosis was persisted.',
    };
  },

  getRecommendations: async (diagnosisId?: string, connectionId?: string): Promise<Recommendation[]> => {
    const endpoint = diagnosisId
      ? `/diagnostics/${diagnosisId}/recommendations`
      : '/diagnostics/recommendations';
    const data = await apiClient.get<BackendRecommendation[]>(endpoint, {
      params: diagnosisId ? undefined : { connection_id: connectionId },
    });
    return data.map((item) => ({
      id: item.id,
      diagnosisId: item.diagnosis_id,
      connectionId: item.connection_id,
      diagnosisTitle: item.diagnosis_title,
      primaryRootCause: item.primary_root_cause.toUpperCase() as Recommendation['primaryRootCause'],
      type: item.type,
      title: item.title,
      rationale: item.rationale,
      predictedImpact: item.predicted_impact,
      uncertaintyPct: item.uncertainty_pct,
      risk: item.risk,
      candidateSql: item.candidate_sql,
      tableName: item.table_name || undefined,
      experimentId: item.experiment_id || undefined,
      rank: item.rank,
      score: item.score,
      evidence: item.evidence,
      prerequisites: item.prerequisites,
      rollbackSql: item.rollback_sql || undefined,
      executionMode: item.execution_mode,
      requiresHypopg: item.requires_hypopg,
      mlStatus: item.ml_status,
    }));
  },
};
