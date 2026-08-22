// Domain vocabulary for the AI Database Administrator.

export type RootCauseClass =
  | 'STALE_STATISTICS'
  | 'PLAN_FLIP'
  | 'CARDINALITY_MISESTIMATION'
  | 'LOCK_CONTENTION'
  | 'INDEX_MISSING'
  | 'INDEX_UNUSED'
  | 'VACUUM_LAG'
  | 'BLOAT'
  | 'BUFFER_PRESSURE'
  | 'IO_SATURATION'
  | 'TEMP_SPILL'
  | 'CONNECTION_CONTENTION'
  | 'CHECKPOINT_PRESSURE'
  | 'UNKNOWN'

export type CausalRank = 'PRIMARY' | 'CONTRIBUTING' | 'CORRELATED' | 'UNRELATED'

export type Verdict = 'VERIFIED' | 'CONDITIONAL' | 'REJECTED'

export type DeploymentOutcome =
  | 'COMMIT'
  | 'ROLLBACK'
  | 'IN_PROGRESS'
  | 'AWAITING_APPROVAL'

export type ApprovalState = 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED'

export type DbProvider = 'Neon' | 'AWS RDS' | 'Supabase' | 'Self-hosted'

export type ConnectionStatus =
  | 'Connected'
  | 'Testing'
  | 'Failed'
  | 'Needs Attention'

export type HealthStatus = 'Healthy' | 'Degraded' | 'Critical'

export interface DatabaseConnection {
  id: string
  name: string
  provider: DbProvider
  host: string
  region: string
  status: ConnectionStatus
  health: HealthStatus
  lastCheckedISO: string
  version: string
  checks: {
    reachability: boolean
    credentials: boolean
    pgStatStatements: boolean
    readOnlyRole: boolean
  }
  latencySparkline: number[]
  activeProblems: number
}

export interface Recommendation {
  id: string
  type: 'INDEX' | 'STATISTICS' | 'CONFIG' | 'QUERY_REWRITE' | 'VACUUM'
  title: string
  rationale: string
  predictedImpact: string
  uncertaintyPct: number
  risk: 'Low' | 'Medium' | 'High'
  experimentId?: string
}

export interface EvidenceNode {
  id: string
  label: string
  kind: 'event' | 'cause' | 'symptom'
  detail: string
  metric?: string
  value?: string
}

export interface EvidenceEdge {
  from: string
  to: string
}

export interface TimelineEntry {
  timeISO: string
  title: string
  detail: string
  icon: 'load' | 'stats' | 'plan' | 'latency' | 'lock' | 'vacuum'
}

export interface SupportingEvidence {
  id: string
  claim: string
  metric: string
  value: string
  rank: CausalRank
}

export interface ContributingCause {
  rootCause: RootCauseClass
  rank: CausalRank
  confidencePct: number
  summary: string
}

export interface Diagnosis {
  id: string
  connectionId: string
  title: string
  primaryRootCause: RootCauseClass
  confidencePct: number
  status: 'Active' | 'Resolved'
  detectedAtISO: string
  lowConfidence: boolean
  summary: string
  affectedObject: string
  contributingCauses: ContributingCause[]
  evidenceNodes: EvidenceNode[]
  evidenceEdges: EvidenceEdge[]
  timeline: TimelineEntry[]
  supportingEvidence: SupportingEvidence[]
  recommendations: Recommendation[]
}

export type PipelineStage =
  | 'HypoPG filter'
  | 'ML prediction'
  | 'Shadow DB simulation'
  | 'Statistical verification'
  | 'Skeptic review'
  | 'Policy engine'

export interface MetricComparison {
  metric: string
  unit: string
  baseline: number
  candidate: number
  betterWhenLower: boolean
}

export interface SkepticFinding {
  concern: string
  status: 'pass' | 'flagged'
  note: string
}

export interface PolicyCheck {
  rule: string
  passed: boolean
}

export interface CanaryPoint {
  t: number
  p50: number
  p95: number
  p99: number
  errorRate: number
  lockWaits: number
  cpu: number
  throughput: number
}

export interface Experiment {
  id: string
  connectionId: string
  diagnosisId?: string
  candidate: string
  recommendationType: Recommendation['type']
  verdict: Verdict
  outcome: DeploymentOutcome
  approvalState: ApprovalState
  approver?: string
  createdAtISO: string
  completedAtISO?: string
  currentStage: PipelineStage
  comparisons: MetricComparison[]
  regressionRatePct: number
  ciLow: number
  ciHigh: number
  significance: string
  skepticFindings: SkepticFinding[]
  policyChecks: PolicyCheck[]
  rollbackReason?: string
  auditLog: { actor: string; action: string; timeISO: string }[]
}

export interface ForecastPoint {
  day: number
  probability: number
  lower: number
  upper: number
}

export interface CalibrationBucket {
  predicted: number
  actual: number
  samples: number
}

export interface MaePoint {
  version: string
  mae: number
}

export interface BanditArm {
  strategy: string
  reward: number
  pulls: number
}

export interface Forecast {
  connectionId: string
  headline: string
  thresholdDay: number
  thresholdProbability: number
  curve: ForecastPoint[]
  suggestions: Recommendation[]
  calibration: CalibrationBucket[]
  mae: MaePoint[]
  bandit: BanditArm[]
}

export interface RoiEntry {
  id: string
  connectionId: string
  description: string
  improvement: string
  monthlySavingsUsd: number | null // null => cost model not configured
  committedAtISO: string
}

export interface ActivityItem {
  id: string
  timeISO: string
  connectionId: string
  message: string
  kind: 'approve' | 'commit' | 'rollback' | 'forecast' | 'diagnose'
}
