import type {
    ActivityItem,
    DatabaseConnection,
    Diagnosis,
    Experiment,
    Forecast,
    RoiEntry,
} from '../types/types'

// A fixed reference "now" so the mock data reads consistently.
const NOW = new Date('2026-08-21T14:30:00Z').getTime()
const min = 60_000
const hr = 60 * min
const day = 24 * hr
export const ago = (ms: number) => new Date(NOW - ms).toISOString()

function spark(base: number, jitter: number, n = 24, drift = 0): number[] {
    const out: number[] = []
    let seed = base
    for (let i = 0; i < n; i++) {
        seed += (Math.sin(i * 1.3) + Math.cos(i * 0.7)) * jitter * 0.4 + drift
        out.push(Math.max(0.1, Math.round((seed + (i % 3) * jitter * 0.15) * 100) / 100))
    }
    return out
}

export const connections: DatabaseConnection[] = [
    {
        id: 'prod-orders-db',
        name: 'prod-orders-db',
        provider: 'Neon',
        host: 'ep-cool-frost-12345.us-east-2.aws.neon.tech',
        region: 'us-east-2',
        status: 'Needs Attention',
        health: 'Critical',
        lastCheckedISO: ago(42_000),
        version: 'PostgreSQL 16.3',
        checks: {
            reachability: true,
            credentials: true,
            pgStatStatements: true,
            readOnlyRole: true,
        },
        latencySparkline: spark(48, 6, 24, 3.4),
        activeProblems: 3,
    },
    {
        id: 'analytics-warehouse',
        name: 'analytics-warehouse',
        provider: 'AWS RDS',
        host: 'analytics.cluster-abcd.us-east-1.rds.amazonaws.com',
        region: 'us-east-1',
        status: 'Connected',
        health: 'Degraded',
        lastCheckedISO: ago(18_000),
        version: 'PostgreSQL 15.6',
        checks: {
            reachability: true,
            credentials: true,
            pgStatStatements: true,
            readOnlyRole: true,
        },
        latencySparkline: spark(120, 14, 24, 1.1),
        activeProblems: 1,
    },
    {
        id: 'staging-db',
        name: 'staging-db',
        provider: 'Supabase',
        host: 'db.qwertyuiopasdfgh.supabase.co',
        region: 'us-west-1',
        status: 'Connected',
        health: 'Healthy',
        lastCheckedISO: ago(9_000),
        version: 'PostgreSQL 16.1',
        checks: {
            reachability: true,
            credentials: true,
            pgStatStatements: true,
            readOnlyRole: true,
        },
        latencySparkline: spark(22, 3, 24, -0.1),
        activeProblems: 0,
    },
]

export const diagnoses: Diagnosis[] = [
    {
        id: 'dg-4821',
        connectionId: 'prod-orders-db',
        title: 'Query regression on orders table after bulk import',
        primaryRootCause: 'PLAN_FLIP',
        confidencePct: 94,
        status: 'Active',
        detectedAtISO: ago(2 * hr + 12 * min),
        lowConfidence: false,
        summary:
            'A nightly bulk import invalidated planner statistics on orders, causing the planner to abandon idx_orders_customer_id in favor of a sequential scan. p95 latency on the customer order lookup rose from 41 ms to 612 ms.',
        affectedObject: 'orders',
        contributingCauses: [
            {
                rootCause: 'PLAN_FLIP',
                rank: 'PRIMARY',
                confidencePct: 94,
                summary:
                    'Planner switched from index scan to sequential scan at 02:14 UTC, coinciding with the latency spike.',
            },
            {
                rootCause: 'STALE_STATISTICS',
                rank: 'CONTRIBUTING',
                confidencePct: 88,
                summary:
                    'pg_stat reltuples for orders was 4.2M but last ANALYZE ran before a 1.1M-row bulk insert.',
            },
            {
                rootCause: 'CARDINALITY_MISESTIMATION',
                rank: 'CONTRIBUTING',
                confidencePct: 81,
                summary:
                    'Estimated rows for customer_id = $1 was 1 vs. actual 640, a 640x underestimate.',
            },
            {
                rootCause: 'BUFFER_PRESSURE',
                rank: 'CORRELATED',
                confidencePct: 34,
                summary:
                    'Cache hit ratio dipped to 96.1% during the incident but recovered independently.',
            },
        ],
        evidenceNodes: [
            { id: 'n1', kind: 'event', label: 'Bulk import (1.1M rows)', detail: 'Nightly ETL inserted 1,142,090 rows into orders at 02:03 UTC.', metric: 'rows_inserted', value: '1,142,090' },
            { id: 'n2', kind: 'cause', label: 'Stale statistics', detail: 'last_analyze predates the import; reltuples off by 27%.', metric: 'stats_age', value: '9h 41m' },
            { id: 'n3', kind: 'cause', label: 'Cardinality misestimate', detail: 'Row estimate 1 vs actual 640 for customer_id predicate.', metric: 'est_vs_actual', value: '1 → 640' },
            { id: 'n4', kind: 'cause', label: 'Plan flip', detail: 'Index scan → sequential scan on orders.', metric: 'plan_node', value: 'Seq Scan' },
            { id: 'n5', kind: 'symptom', label: 'Latency increase', detail: 'p95 for order lookup rose 41 ms → 612 ms.', metric: 'p95_latency', value: '612 ms' },
        ],
        evidenceEdges: [
            { from: 'n1', to: 'n2' },
            { from: 'n2', to: 'n3' },
            { from: 'n3', to: 'n4' },
            { from: 'n4', to: 'n5' },
        ],
        timeline: [
            { timeISO: ago(12 * hr + 27 * min), title: 'Bulk import started', detail: 'ETL job etl_orders_nightly began ingesting 1.1M rows.', icon: 'load' },
            { timeISO: ago(12 * hr + 9 * min), title: 'Statistics went stale', detail: 'reltuples drifted beyond 20% without an ANALYZE.', icon: 'stats' },
            { timeISO: ago(2 * hr + 14 * min), title: 'Planner flipped to seq scan', detail: 'auto_explain captured a plan change on the hot query.', icon: 'plan' },
            { timeISO: ago(2 * hr + 12 * min), title: 'Latency alert fired', detail: 'p95 crossed 500 ms threshold on orders lookup.', icon: 'latency' },
        ],
        supportingEvidence: [
            { id: 'e1', claim: 'Planner abandoned the index', metric: 'plan_hash change', value: '0x4f2a → 0x9b71', rank: 'PRIMARY' },
            { id: 'e2', claim: 'Statistics are stale', metric: 'now - last_analyze', value: '9h 41m', rank: 'CONTRIBUTING' },
            { id: 'e3', claim: 'Row estimate is far too low', metric: 'estimated / actual rows', value: '1 / 640', rank: 'CONTRIBUTING' },
            { id: 'e4', claim: 'Latency regressed sharply', metric: 'p95 exec time', value: '41 ms → 612 ms', rank: 'PRIMARY' },
            { id: 'e5', claim: 'Cache hit ratio dipped', metric: 'shared_buffers hit %', value: '99.2% → 96.1%', rank: 'CORRELATED' },
        ],
        recommendations: [
            {
                id: 'rec-1',
                type: 'STATISTICS',
                title: 'Run ANALYZE on orders and raise statistics target',
                rationale: 'Refresh planner statistics so cardinality estimates reflect the post-import row counts; increase default_statistics_target on customer_id to 500.',
                predictedImpact: '~78% p95 latency reduction',
                uncertaintyPct: 6,
                risk: 'Low',
                experimentId: 'exp-1007',
            },
            {
                id: 'rec-2',
                type: 'INDEX',
                title: 'Create composite index on orders(customer_id, created_at)',
                rationale: 'A covering index supports the lookup-and-sort pattern and makes the index scan resilient to future statistics drift.',
                predictedImpact: '~64% p95 latency reduction',
                uncertaintyPct: 9,
                risk: 'Medium',
                experimentId: 'exp-1008',
            },
        ],
    },
    {
        id: 'dg-4790',
        connectionId: 'prod-orders-db',
        title: 'Lock contention on order_items during checkout bursts',
        primaryRootCause: 'LOCK_CONTENTION',
        confidencePct: 87,
        status: 'Active',
        detectedAtISO: ago(6 * hr + 40 * min),
        lowConfidence: false,
        summary:
            'Row-level lock waits on order_items climbed during peak checkout traffic. A long-held transaction from the inventory reconciliation job blocks writers for up to 3.2s.',
        affectedObject: 'order_items',
        contributingCauses: [
            { rootCause: 'LOCK_CONTENTION', rank: 'PRIMARY', confidencePct: 87, summary: 'Up to 41 sessions waiting on the same tuple lock during bursts.' },
            { rootCause: 'CONNECTION_CONTENTION', rank: 'CONTRIBUTING', confidencePct: 62, summary: 'Pool saturation amplifies wait times as blocked sessions hold connections.' },
        ],
        evidenceNodes: [
            { id: 'n1', kind: 'event', label: 'Reconciliation job', detail: 'Long transaction holds FOR UPDATE lock on order_items.', metric: 'txn_duration', value: '3.2 s' },
            { id: 'n2', kind: 'cause', label: 'Lock waits', detail: '41 sessions queued on the same lock.', metric: 'waiting_sessions', value: '41' },
            { id: 'n3', kind: 'symptom', label: 'Checkout latency', detail: 'p99 checkout write latency reached 2,840 ms.', metric: 'p99_write', value: '2,840 ms' },
        ],
        evidenceEdges: [
            { from: 'n1', to: 'n2' },
            { from: 'n2', to: 'n3' },
        ],
        timeline: [
            { timeISO: ago(7 * hr), title: 'Reconciliation job started', detail: 'Batch job opened a long-lived transaction.', icon: 'lock' },
            { timeISO: ago(6 * hr + 45 * min), title: 'Lock queue grew', detail: 'Waiting sessions on order_items exceeded 30.', icon: 'lock' },
            { timeISO: ago(6 * hr + 40 * min), title: 'Latency alert fired', detail: 'p99 checkout latency crossed 2s.', icon: 'latency' },
        ],
        supportingEvidence: [
            { id: 'e1', claim: 'A long transaction holds the lock', metric: 'longest blocking txn', value: '3.2 s', rank: 'PRIMARY' },
            { id: 'e2', claim: 'Many sessions are queued', metric: 'pg_locks waiting', value: '41', rank: 'PRIMARY' },
            { id: 'e3', claim: 'Write latency regressed', metric: 'p99 write latency', value: '2,840 ms', rank: 'CONTRIBUTING' },
        ],
        recommendations: [
            {
                id: 'rec-3',
                type: 'QUERY_REWRITE',
                title: 'Batch the reconciliation job into smaller transactions',
                rationale: 'Chunk the reconciliation into 5k-row transactions with SKIP LOCKED to release locks between batches.',
                predictedImpact: '~71% reduction in lock wait time',
                uncertaintyPct: 12,
                risk: 'Medium',
                experimentId: 'exp-1005',
            },
        ],
    },
    {
        id: 'dg-4655',
        connectionId: 'analytics-warehouse',
        title: 'Sequential scans on large fact_events table',
        primaryRootCause: 'INDEX_MISSING',
        confidencePct: 91,
        status: 'Active',
        detectedAtISO: ago(1 * day + 3 * hr),
        lowConfidence: false,
        summary:
            'Dashboard aggregation queries scan the full 240M-row fact_events table because there is no index supporting the (tenant_id, event_date) filter. Mean execution time is 4.9s.',
        affectedObject: 'fact_events',
        contributingCauses: [
            { rootCause: 'INDEX_MISSING', rank: 'PRIMARY', confidencePct: 91, summary: 'No index covers the tenant/date filter used by 74% of analytics queries.' },
            { rootCause: 'TEMP_SPILL', rank: 'CONTRIBUTING', confidencePct: 58, summary: 'Sorts spill to disk because work_mem is exceeded during aggregation.' },
            { rootCause: 'IO_SATURATION', rank: 'CORRELATED', confidencePct: 40, summary: 'Read IOPS peaks correlate with the scan windows.' },
        ],
        evidenceNodes: [
            { id: 'n1', kind: 'cause', label: 'Missing index', detail: 'No index on (tenant_id, event_date).', metric: 'candidate_index', value: 'absent' },
            { id: 'n2', kind: 'cause', label: 'Sequential scan', detail: 'Full scan of 240M rows per query.', metric: 'rows_scanned', value: '240M' },
            { id: 'n3', kind: 'cause', label: 'Temp spill', detail: 'Sort spilled 1.8 GB to temp files.', metric: 'temp_bytes', value: '1.8 GB' },
            { id: 'n4', kind: 'symptom', label: 'Slow aggregation', detail: 'Mean exec time 4.9 s.', metric: 'mean_exec', value: '4,910 ms' },
        ],
        evidenceEdges: [
            { from: 'n1', to: 'n2' },
            { from: 'n2', to: 'n3' },
            { from: 'n3', to: 'n4' },
            { from: 'n2', to: 'n4' },
        ],
        timeline: [
            { timeISO: ago(1 * day + 6 * hr), title: 'Query pattern shifted', detail: 'New dashboard added tenant-scoped date filters.', icon: 'load' },
            { timeISO: ago(1 * day + 4 * hr), title: 'Seq scans detected', detail: 'pg_stat_statements flagged repeated full scans.', icon: 'plan' },
            { timeISO: ago(1 * day + 3 * hr), title: 'Latency alert fired', detail: 'Mean exec time crossed 3s.', icon: 'latency' },
        ],
        supportingEvidence: [
            { id: 'e1', claim: 'Queries scan the whole table', metric: 'rows scanned / call', value: '240,113,904', rank: 'PRIMARY' },
            { id: 'e2', claim: 'No supporting index exists', metric: 'matching indexes', value: '0', rank: 'PRIMARY' },
            { id: 'e3', claim: 'Sorts spill to disk', metric: 'temp bytes / call', value: '1.8 GB', rank: 'CONTRIBUTING' },
        ],
        recommendations: [
            {
                id: 'rec-4',
                type: 'INDEX',
                title: 'Create index on fact_events(tenant_id, event_date)',
                rationale: 'A B-tree index on the common filter columns converts the sequential scan to an index range scan and eliminates most temp spills.',
                predictedImpact: '~93% mean latency reduction',
                uncertaintyPct: 7,
                risk: 'Medium',
                experimentId: 'exp-1009',
            },
            {
                id: 'rec-5',
                type: 'CONFIG',
                title: 'Increase work_mem for analytics role to 256MB',
                rationale: 'Raising work_mem keeps aggregation sorts in memory, removing the 1.8 GB temp spill.',
                predictedImpact: '~22% additional latency reduction',
                uncertaintyPct: 15,
                risk: 'Low',
            },
        ],
    },
    {
        id: 'dg-4610',
        connectionId: 'prod-orders-db',
        title: 'Table bloat and vacuum lag on sessions',
        primaryRootCause: 'BLOAT',
        confidencePct: 83,
        status: 'Active',
        detectedAtISO: ago(2 * day + 5 * hr),
        lowConfidence: false,
        summary:
            'High-churn writes on the sessions table outpace autovacuum. Dead tuple ratio is 38% and the table is an estimated 2.4x its live size, inflating scan costs.',
        affectedObject: 'sessions',
        contributingCauses: [
            { rootCause: 'BLOAT', rank: 'PRIMARY', confidencePct: 83, summary: 'Estimated 58% wasted space from dead tuples.' },
            { rootCause: 'VACUUM_LAG', rank: 'CONTRIBUTING', confidencePct: 79, summary: 'Autovacuum falls behind during peak write bursts.' },
        ],
        evidenceNodes: [
            { id: 'n1', kind: 'event', label: 'High write churn', detail: 'sessions sees 3.1k updates/sec at peak.', metric: 'writes_sec', value: '3,100' },
            { id: 'n2', kind: 'cause', label: 'Vacuum lag', detail: 'Autovacuum cannot keep pace with dead tuple creation.', metric: 'dead_tuples', value: '4.9M' },
            { id: 'n3', kind: 'cause', label: 'Bloat', detail: 'Table is 2.4x its live size.', metric: 'bloat_ratio', value: '2.4x' },
            { id: 'n4', kind: 'symptom', label: 'Slower scans', detail: 'Sequential scans read 2.4x more pages.', metric: 'pages_read', value: '+140%' },
        ],
        evidenceEdges: [
            { from: 'n1', to: 'n2' },
            { from: 'n2', to: 'n3' },
            { from: 'n3', to: 'n4' },
        ],
        timeline: [
            { timeISO: ago(4 * day), title: 'Write volume increased', detail: 'A new feature doubled session updates.', icon: 'load' },
            { timeISO: ago(2 * day + 12 * hr), title: 'Autovacuum fell behind', detail: 'Dead tuples exceeded the autovacuum threshold continuously.', icon: 'vacuum' },
            { timeISO: ago(2 * day + 5 * hr), title: 'Bloat alert fired', detail: 'Estimated bloat crossed 2x.', icon: 'latency' },
        ],
        supportingEvidence: [
            { id: 'e1', claim: 'Dead tuples dominate the table', metric: 'n_dead_tup / n_live_tup', value: '38%', rank: 'PRIMARY' },
            { id: 'e2', claim: 'Autovacuum is lagging', metric: 'time since last autovacuum', value: '11h 20m', rank: 'CONTRIBUTING' },
            { id: 'e3', claim: 'Scans read excess pages', metric: 'heap pages / scan', value: '+140%', rank: 'CONTRIBUTING' },
        ],
        recommendations: [
            {
                id: 'rec-6',
                type: 'VACUUM',
                title: 'Tune autovacuum for sessions and run a one-time VACUUM',
                rationale: 'Lower autovacuum_vacuum_scale_factor to 0.02 for this table and schedule a maintenance-window VACUUM to reclaim space.',
                predictedImpact: '~46% scan cost reduction',
                uncertaintyPct: 14,
                risk: 'Low',
                experimentId: 'exp-1003',
            },
        ],
    },
    {
        id: 'dg-4588',
        connectionId: 'analytics-warehouse',
        title: 'Possible checkpoint pressure — insufficient telemetry',
        primaryRootCause: 'CHECKPOINT_PRESSURE',
        confidencePct: 41,
        status: 'Active',
        detectedAtISO: ago(3 * hr + 5 * min),
        lowConfidence: true,
        summary:
            'Intermittent write stalls may correlate with checkpoint activity, but only 90 minutes of telemetry have been collected since monitoring began on this connection. Confidence is low pending more history.',
        affectedObject: 'cluster-wide',
        contributingCauses: [
            { rootCause: 'CHECKPOINT_PRESSURE', rank: 'PRIMARY', confidencePct: 41, summary: 'Weak correlation between checkpoint writes and latency spikes; needs more samples.' },
            { rootCause: 'IO_SATURATION', rank: 'CORRELATED', confidencePct: 29, summary: 'Write IOPS elevated but within provisioned limits.' },
            { rootCause: 'UNKNOWN', rank: 'UNRELATED', confidencePct: 18, summary: 'Residual variance not yet explained by any known signal.' },
        ],
        evidenceNodes: [
            { id: 'n1', kind: 'cause', label: 'Checkpoint bursts', detail: 'checkpoints_timed vs checkpoints_req ratio is unusual, sample size small.', metric: 'checkpoints_req', value: '7 (90m)' },
            { id: 'n2', kind: 'symptom', label: 'Write stalls', detail: 'Two brief write latency spikes observed.', metric: 'stall_events', value: '2' },
        ],
        evidenceEdges: [{ from: 'n1', to: 'n2' }],
        timeline: [
            { timeISO: ago(90 * min), title: 'Monitoring began', detail: 'Telemetry collection started on this connection.', icon: 'load' },
            { timeISO: ago(40 * min), title: 'Possible correlation noted', detail: 'A stall coincided with a requested checkpoint.', icon: 'plan' },
        ],
        supportingEvidence: [
            { id: 'e1', claim: 'Limited history collected', metric: 'telemetry window', value: '90 min', rank: 'UNRELATED' },
            { id: 'e2', claim: 'Weak checkpoint correlation', metric: 'correlation coefficient', value: '0.38', rank: 'CORRELATED' },
        ],
        recommendations: [],
    },
]

export const experiments: Experiment[] = [
    {
        id: 'exp-1009',
        connectionId: 'analytics-warehouse',
        diagnosisId: 'dg-4655',
        candidate: 'Create index on fact_events(tenant_id, event_date)',
        recommendationType: 'INDEX',
        verdict: 'VERIFIED',
        outcome: 'AWAITING_APPROVAL',
        approvalState: 'PENDING_APPROVAL',
        createdAtISO: ago(35 * min),
        currentStage: 'Policy engine',
        comparisons: [
            { metric: 'Mean latency', unit: 'ms', baseline: 4910, candidate: 342, betterWhenLower: true },
            { metric: 'p95 latency', unit: 'ms', baseline: 8120, candidate: 690, betterWhenLower: true },
            { metric: 'p99 latency', unit: 'ms', baseline: 11400, candidate: 1120, betterWhenLower: true },
            { metric: 'CPU', unit: '%', baseline: 74, candidate: 31, betterWhenLower: true },
            { metric: 'Read I/O', unit: 'MB/s', baseline: 480, candidate: 42, betterWhenLower: true },
        ],
        regressionRatePct: 0.4,
        ciLow: 88.2,
        ciHigh: 95.1,
        significance: 'Improvement is statistically significant (p < 0.001); the 95% CI for latency reduction excludes zero.',
        skepticFindings: [
            { concern: 'Write amplification', status: 'pass', note: 'Index adds ~6% write overhead, within budget.' },
            { concern: 'Storage growth', status: 'flagged', note: 'Index adds an estimated 3.1 GB; monitor disk headroom.' },
            { concern: 'Cache pressure', status: 'pass', note: 'Working set still fits in shared_buffers.' },
            { concern: 'Lock contention', status: 'pass', note: 'CREATE INDEX CONCURRENTLY avoids blocking writes.' },
            { concern: 'Parameter sensitivity', status: 'pass', note: 'Gains hold across work_mem 64–256MB.' },
        ],
        policyChecks: [
            { rule: 'p95 improvement > 15%', passed: true },
            { rule: 'Regression rate < 5%', passed: true },
            { rule: 'CI excludes zero', passed: true },
            { rule: 'No skeptic blocker (only warnings)', passed: true },
            { rule: 'Storage growth < 5 GB', passed: true },
        ],
        auditLog: [
            { actor: 'system', action: 'Experiment created from dg-4655 rec-4', timeISO: ago(35 * min) },
            { actor: 'system', action: 'Shadow simulation completed', timeISO: ago(20 * min) },
            { actor: 'system', action: 'Verdict computed: VERIFIED', timeISO: ago(12 * min) },
        ],
    },
    {
        id: 'exp-1008',
        connectionId: 'prod-orders-db',
        diagnosisId: 'dg-4821',
        candidate: 'Create composite index on orders(customer_id, created_at)',
        recommendationType: 'INDEX',
        verdict: 'CONDITIONAL',
        outcome: 'AWAITING_APPROVAL',
        approvalState: 'PENDING_APPROVAL',
        createdAtISO: ago(1 * hr + 50 * min),
        currentStage: 'Policy engine',
        comparisons: [
            { metric: 'Mean latency', unit: 'ms', baseline: 220, candidate: 96, betterWhenLower: true },
            { metric: 'p95 latency', unit: 'ms', baseline: 612, candidate: 214, betterWhenLower: true },
            { metric: 'p99 latency', unit: 'ms', baseline: 940, candidate: 380, betterWhenLower: true },
            { metric: 'CPU', unit: '%', baseline: 52, candidate: 44, betterWhenLower: true },
            { metric: 'Write throughput', unit: 'tps', baseline: 1850, candidate: 1760, betterWhenLower: false },
        ],
        regressionRatePct: 3.9,
        ciLow: 51.2,
        ciHigh: 72.8,
        significance: 'Improvement is significant, but write throughput regresses ~4.9%, keeping the verdict CONDITIONAL.',
        skepticFindings: [
            { concern: 'Write amplification', status: 'flagged', note: 'Composite index reduces insert throughput ~4.9%.' },
            { concern: 'Storage growth', status: 'pass', note: 'Adds ~640 MB, well within budget.' },
            { concern: 'Cache pressure', status: 'pass', note: 'Negligible change to hit ratio.' },
            { concern: 'Lock contention', status: 'pass', note: 'Built with CONCURRENTLY.' },
            { concern: 'Parameter sensitivity', status: 'flagged', note: 'Gains shrink under low random_page_cost tuning.' },
        ],
        policyChecks: [
            { rule: 'p95 improvement > 15%', passed: true },
            { rule: 'Regression rate < 5%', passed: true },
            { rule: 'CI excludes zero', passed: true },
            { rule: 'No skeptic blocker (only warnings)', passed: false },
            { rule: 'Write throughput regression < 3%', passed: false },
        ],
        auditLog: [
            { actor: 'system', action: 'Experiment created from dg-4821 rec-2', timeISO: ago(1 * hr + 50 * min) },
            { actor: 'system', action: 'Shadow simulation completed', timeISO: ago(1 * hr + 30 * min) },
            { actor: 'system', action: 'Verdict computed: CONDITIONAL', timeISO: ago(1 * hr + 18 * min) },
        ],
    },
    {
        id: 'exp-1007',
        connectionId: 'prod-orders-db',
        diagnosisId: 'dg-4821',
        candidate: 'Run ANALYZE on orders and raise statistics target to 500',
        recommendationType: 'STATISTICS',
        verdict: 'VERIFIED',
        outcome: 'IN_PROGRESS',
        approvalState: 'APPROVED',
        approver: 'maya.chen',
        createdAtISO: ago(2 * hr + 2 * min),
        currentStage: 'Policy engine',
        comparisons: [
            { metric: 'Mean latency', unit: 'ms', baseline: 220, candidate: 58, betterWhenLower: true },
            { metric: 'p95 latency', unit: 'ms', baseline: 612, candidate: 134, betterWhenLower: true },
            { metric: 'p99 latency', unit: 'ms', baseline: 940, candidate: 210, betterWhenLower: true },
            { metric: 'CPU', unit: '%', baseline: 52, candidate: 38, betterWhenLower: true },
        ],
        regressionRatePct: 0.2,
        ciLow: 74.1,
        ciHigh: 82.6,
        significance: 'Improvement is highly significant (p < 0.001); no measured regressions.',
        skepticFindings: [
            { concern: 'Write amplification', status: 'pass', note: 'Statistics change adds no write overhead.' },
            { concern: 'Storage growth', status: 'pass', note: 'No storage impact.' },
            { concern: 'Plan stability', status: 'pass', note: 'Plan is stable across sampled parameter values.' },
            { concern: 'ANALYZE cost', status: 'pass', note: 'ANALYZE completes in 2.1s, negligible impact.' },
        ],
        policyChecks: [
            { rule: 'p95 improvement > 15%', passed: true },
            { rule: 'Regression rate < 5%', passed: true },
            { rule: 'CI excludes zero', passed: true },
            { rule: 'No skeptic blocker', passed: true },
        ],
        auditLog: [
            { actor: 'system', action: 'Experiment created from dg-4821 rec-1', timeISO: ago(2 * hr + 2 * min) },
            { actor: 'system', action: 'Verdict computed: VERIFIED', timeISO: ago(1 * hr + 40 * min) },
            { actor: 'maya.chen', action: 'Approved for canary deployment', timeISO: ago(22 * min) },
            { actor: 'system', action: 'Canary monitoring window started', timeISO: ago(20 * min) },
        ],
    },
    {
        id: 'exp-1005',
        connectionId: 'prod-orders-db',
        diagnosisId: 'dg-4790',
        candidate: 'Batch reconciliation job with SKIP LOCKED (5k rows/txn)',
        recommendationType: 'QUERY_REWRITE',
        verdict: 'VERIFIED',
        outcome: 'COMMIT',
        approvalState: 'APPROVED',
        approver: 'dev.okonkwo',
        createdAtISO: ago(1 * day + 4 * hr),
        completedAtISO: ago(1 * day + 2 * hr),
        currentStage: 'Policy engine',
        comparisons: [
            { metric: 'Lock wait time', unit: 'ms', baseline: 3200, candidate: 210, betterWhenLower: true },
            { metric: 'p99 write latency', unit: 'ms', baseline: 2840, candidate: 410, betterWhenLower: true },
            { metric: 'Waiting sessions', unit: '', baseline: 41, candidate: 4, betterWhenLower: true },
            { metric: 'Job duration', unit: 's', baseline: 38, candidate: 52, betterWhenLower: true },
        ],
        regressionRatePct: 1.1,
        ciLow: 66.4,
        ciHigh: 78.9,
        significance: 'Lock wait reduction is significant; job runtime grows modestly, an accepted trade-off.',
        skepticFindings: [
            { concern: 'Correctness under SKIP LOCKED', status: 'pass', note: 'All rows eventually processed; no skips across two runs.' },
            { concern: 'Job runtime', status: 'flagged', note: 'Runtime grows from 38s to 52s.' },
            { concern: 'Lock contention', status: 'pass', note: 'Peak waiting sessions dropped 41 → 4.' },
        ],
        policyChecks: [
            { rule: 'Lock wait improvement > 50%', passed: true },
            { rule: 'Regression rate < 5%', passed: true },
            { rule: 'Correctness preserved', passed: true },
        ],
        auditLog: [
            { actor: 'system', action: 'Experiment created from dg-4790 rec-3', timeISO: ago(1 * day + 4 * hr) },
            { actor: 'system', action: 'Verdict computed: VERIFIED', timeISO: ago(1 * day + 3 * hr) },
            { actor: 'dev.okonkwo', action: 'Approved for canary deployment', timeISO: ago(1 * day + 2 * hr + 40 * min) },
            { actor: 'system', action: 'Canary succeeded — COMMIT', timeISO: ago(1 * day + 2 * hr) },
        ],
    },
    {
        id: 'exp-1003',
        connectionId: 'prod-orders-db',
        diagnosisId: 'dg-4610',
        candidate: 'Tune autovacuum for sessions and run one-time VACUUM',
        recommendationType: 'VACUUM',
        verdict: 'VERIFIED',
        outcome: 'COMMIT',
        approvalState: 'APPROVED',
        approver: 'maya.chen',
        createdAtISO: ago(2 * day + 4 * hr),
        completedAtISO: ago(2 * day + 1 * hr),
        currentStage: 'Policy engine',
        comparisons: [
            { metric: 'Bloat ratio', unit: 'x', baseline: 2.4, candidate: 1.1, betterWhenLower: true },
            { metric: 'Scan cost', unit: 'ms', baseline: 180, candidate: 96, betterWhenLower: true },
            { metric: 'Dead tuple %', unit: '%', baseline: 38, candidate: 6, betterWhenLower: true },
        ],
        regressionRatePct: 0.0,
        ciLow: 40.2,
        ciHigh: 52.1,
        significance: 'Scan cost reduction is significant with no measured regressions.',
        skepticFindings: [
            { concern: 'VACUUM I/O impact', status: 'flagged', note: 'One-time VACUUM raises I/O for ~9 min; run in maintenance window.' },
            { concern: 'Long-term churn', status: 'pass', note: 'Tuned thresholds keep dead tuples under 8%.' },
        ],
        policyChecks: [
            { rule: 'Bloat reduction > 30%', passed: true },
            { rule: 'Regression rate < 5%', passed: true },
            { rule: 'Maintenance window scheduled', passed: true },
        ],
        auditLog: [
            { actor: 'system', action: 'Experiment created from dg-4610 rec-6', timeISO: ago(2 * day + 4 * hr) },
            { actor: 'system', action: 'Verdict computed: VERIFIED', timeISO: ago(2 * day + 3 * hr) },
            { actor: 'maya.chen', action: 'Approved for maintenance window', timeISO: ago(2 * day + 1 * hr + 30 * min) },
            { actor: 'system', action: 'Canary succeeded — COMMIT', timeISO: ago(2 * day + 1 * hr) },
        ],
    },
    {
        id: 'exp-0998',
        connectionId: 'analytics-warehouse',
        candidate: 'Drop unused index idx_events_legacy_source',
        recommendationType: 'INDEX',
        verdict: 'REJECTED',
        outcome: 'ROLLBACK',
        approvalState: 'APPROVED',
        approver: 'dev.okonkwo',
        createdAtISO: ago(3 * day + 6 * hr),
        completedAtISO: ago(3 * day + 5 * hr),
        currentStage: 'Policy engine',
        comparisons: [
            { metric: 'Write throughput', unit: 'tps', baseline: 920, candidate: 940, betterWhenLower: false },
            { metric: 'p95 read latency', unit: 'ms', baseline: 88, candidate: 143, betterWhenLower: true },
            { metric: 'Storage', unit: 'GB', baseline: 812, candidate: 810, betterWhenLower: true },
        ],
        regressionRatePct: 9.2,
        ciLow: -14.0,
        ciHigh: 4.2,
        significance: 'A read path unexpectedly depended on the index; p95 read latency regressed 62%. CI includes zero.',
        skepticFindings: [
            { concern: 'Hidden read dependency', status: 'flagged', note: 'A reporting query used the index despite low pg_stat_user_indexes counts.' },
            { concern: 'Write throughput', status: 'pass', note: 'Small write improvement as expected.' },
        ],
        policyChecks: [
            { rule: 'No read regression > 10%', passed: false },
            { rule: 'CI excludes zero', passed: false },
            { rule: 'No skeptic blocker', passed: false },
        ],
        rollbackReason: 'Canary p95 read latency exceeded baseline by 62%; policy auto-reverted the change within the monitoring window.',
        auditLog: [
            { actor: 'system', action: 'Experiment created', timeISO: ago(3 * day + 6 * hr) },
            { actor: 'system', action: 'Verdict computed: REJECTED', timeISO: ago(3 * day + 5 * hr + 30 * min) },
            { actor: 'dev.okonkwo', action: 'Overrode to canary despite REJECTED verdict', timeISO: ago(3 * day + 5 * hr + 12 * min) },
            { actor: 'system', action: 'Canary breached threshold — ROLLBACK', timeISO: ago(3 * day + 5 * hr) },
        ],
    },
    {
        id: 'exp-0990',
        connectionId: 'prod-orders-db',
        candidate: 'Increase shared_buffers to 8GB',
        recommendationType: 'CONFIG',
        verdict: 'CONDITIONAL',
        outcome: 'COMMIT',
        approvalState: 'APPROVED',
        approver: 'maya.chen',
        createdAtISO: ago(5 * day),
        completedAtISO: ago(4 * day + 22 * hr),
        currentStage: 'Policy engine',
        comparisons: [
            { metric: 'Cache hit ratio', unit: '%', baseline: 98.1, candidate: 99.4, betterWhenLower: false },
            { metric: 'p95 latency', unit: 'ms', baseline: 74, candidate: 61, betterWhenLower: true },
            { metric: 'Free memory', unit: 'GB', baseline: 12, candidate: 5, betterWhenLower: false },
        ],
        regressionRatePct: 2.0,
        ciLow: 8.1,
        ciHigh: 24.3,
        significance: 'Cache hit ratio improves meaningfully; reduced memory headroom keeps the verdict CONDITIONAL.',
        skepticFindings: [
            { concern: 'Memory headroom', status: 'flagged', note: 'Free memory drops to 5 GB; monitor under peak load.' },
            { concern: 'Restart required', status: 'flagged', note: 'Change needs a restart; scheduled in maintenance window.' },
        ],
        policyChecks: [
            { rule: 'p95 improvement > 10%', passed: true },
            { rule: 'Regression rate < 5%', passed: true },
            { rule: 'Memory headroom > 4 GB', passed: true },
        ],
        auditLog: [
            { actor: 'system', action: 'Experiment created', timeISO: ago(5 * day) },
            { actor: 'system', action: 'Verdict computed: CONDITIONAL', timeISO: ago(4 * day + 23 * hr) },
            { actor: 'maya.chen', action: 'Approved for maintenance window', timeISO: ago(4 * day + 22 * hr + 20 * min) },
            { actor: 'system', action: 'Canary succeeded — COMMIT', timeISO: ago(4 * day + 22 * hr) },
        ],
    },
    {
        id: 'exp-0975',
        connectionId: 'staging-db',
        candidate: 'Rewrite N+1 order lookup into a single JOIN',
        recommendationType: 'QUERY_REWRITE',
        verdict: 'VERIFIED',
        outcome: 'COMMIT',
        approvalState: 'APPROVED',
        approver: 'dev.okonkwo',
        createdAtISO: ago(7 * day),
        completedAtISO: ago(6 * day + 21 * hr),
        currentStage: 'Policy engine',
        comparisons: [
            { metric: 'Mean latency', unit: 'ms', baseline: 310, candidate: 44, betterWhenLower: true },
            { metric: 'Query count', unit: '/req', baseline: 51, candidate: 1, betterWhenLower: true },
            { metric: 'CPU', unit: '%', baseline: 40, candidate: 22, betterWhenLower: true },
        ],
        regressionRatePct: 0.0,
        ciLow: 82.0,
        ciHigh: 91.5,
        significance: 'Collapsing 51 queries into one yields a highly significant improvement with no regressions.',
        skepticFindings: [
            { concern: 'Result equivalence', status: 'pass', note: 'Row-for-row output matches the original across fixtures.' },
            { concern: 'Plan complexity', status: 'pass', note: 'Single hash join, stable across parameters.' },
        ],
        policyChecks: [
            { rule: 'Latency improvement > 15%', passed: true },
            { rule: 'Result equivalence verified', passed: true },
            { rule: 'CI excludes zero', passed: true },
        ],
        auditLog: [
            { actor: 'system', action: 'Experiment created', timeISO: ago(7 * day) },
            { actor: 'system', action: 'Verdict computed: VERIFIED', timeISO: ago(6 * day + 23 * hr) },
            { actor: 'dev.okonkwo', action: 'Approved for canary deployment', timeISO: ago(6 * day + 21 * hr + 30 * min) },
            { actor: 'system', action: 'Canary succeeded — COMMIT', timeISO: ago(6 * day + 21 * hr) },
        ],
    },
]

function forecastCurve(peak: number, crossDay: number): Forecast['curve'] {
    const out: Forecast['curve'] = []
    for (let d = 0; d <= 14; d++) {
        const p = Math.min(peak, 0.04 + (peak - 0.04) * (1 - Math.exp(-d / (crossDay * 0.9))))
        const band = 0.06 + d * 0.006
        out.push({
            day: d,
            probability: Math.round(p * 1000) / 1000,
            lower: Math.round(Math.max(0, p - band) * 1000) / 1000,
            upper: Math.round(Math.min(1, p + band) * 1000) / 1000,
        })
    }
    return out
}

export const forecasts: Record<string, Forecast> = {
    'prod-orders-db': {
        connectionId: 'prod-orders-db',
        headline: '61% probability of index-effectiveness degradation within 5 days',
        thresholdDay: 5,
        thresholdProbability: 0.61,
        curve: forecastCurve(0.82, 5),
        suggestions: [
            {
                id: 'fc-rec-1',
                type: 'STATISTICS',
                title: 'Schedule nightly ANALYZE on orders after ETL',
                rationale: 'Preempt the recurring statistics drift that drives plan flips after the bulk import.',
                predictedImpact: 'Prevents ~2 plan-flip incidents/week',
                uncertaintyPct: 11,
                risk: 'Low',
            },
            {
                id: 'fc-rec-2',
                type: 'INDEX',
                title: 'Pre-create covering index before Q4 traffic ramp',
                rationale: 'Forecast shows index pressure crossing threshold as order volume grows into Q4.',
                predictedImpact: 'Maintains p95 under 150 ms at 2x load',
                uncertaintyPct: 18,
                risk: 'Medium',
            },
        ],
        calibration: [
            { predicted: 55, actual: 52, samples: 210 },
            { predicted: 65, actual: 61, samples: 188 },
            { predicted: 75, actual: 77, samples: 164 },
            { predicted: 85, actual: 83, samples: 142 },
            { predicted: 95, actual: 93, samples: 96 },
        ],
        mae: [
            { version: 'v0.1', mae: 0.214 },
            { version: 'v0.2', mae: 0.171 },
            { version: 'v0.3', mae: 0.158 },
            { version: 'v0.4', mae: 0.132 },
            { version: 'v0.5', mae: 0.121 },
            { version: 'v0.6', mae: 0.104 },
        ],
        bandit: [
            { strategy: 'Statistics refresh', reward: 0.82, pulls: 41 },
            { strategy: 'Index creation', reward: 0.74, pulls: 33 },
            { strategy: 'Query rewrite', reward: 0.69, pulls: 22 },
            { strategy: 'Vacuum tuning', reward: 0.58, pulls: 18 },
            { strategy: 'Config change', reward: 0.44, pulls: 14 },
            { strategy: 'Do nothing', reward: 0.21, pulls: 9 },
        ],
    },
    'analytics-warehouse': {
        connectionId: 'analytics-warehouse',
        headline: '38% probability of scan-cost degradation within 7 days',
        thresholdDay: 7,
        thresholdProbability: 0.38,
        curve: forecastCurve(0.58, 8),
        suggestions: [
            {
                id: 'fc-rec-3',
                type: 'INDEX',
                title: 'Add partitioning on fact_events by event_date',
                rationale: 'Range partitioning bounds scan cost as the table grows past 300M rows.',
                predictedImpact: 'Caps mean latency growth at ~5%/quarter',
                uncertaintyPct: 22,
                risk: 'High',
            },
        ],
        calibration: [
            { predicted: 55, actual: 49, samples: 120 },
            { predicted: 65, actual: 66, samples: 104 },
            { predicted: 75, actual: 71, samples: 88 },
            { predicted: 85, actual: 88, samples: 61 },
            { predicted: 95, actual: 90, samples: 40 },
        ],
        mae: [
            { version: 'v0.1', mae: 0.242 },
            { version: 'v0.2', mae: 0.205 },
            { version: 'v0.3', mae: 0.221 },
            { version: 'v0.4', mae: 0.169 },
            { version: 'v0.5', mae: 0.148 },
        ],
        bandit: [
            { strategy: 'Index creation', reward: 0.79, pulls: 28 },
            { strategy: 'Config change', reward: 0.61, pulls: 19 },
            { strategy: 'Query rewrite', reward: 0.55, pulls: 15 },
            { strategy: 'Vacuum tuning', reward: 0.4, pulls: 11 },
            { strategy: 'Do nothing', reward: 0.24, pulls: 7 },
        ],
    },
    'staging-db': {
        connectionId: 'staging-db',
        headline: '9% probability of degradation within 14 days — low risk',
        thresholdDay: 14,
        thresholdProbability: 0.09,
        curve: forecastCurve(0.14, 12),
        suggestions: [],
        calibration: [
            { predicted: 55, actual: 57, samples: 44 },
            { predicted: 65, actual: 63, samples: 38 },
            { predicted: 75, actual: 79, samples: 26 },
            { predicted: 85, actual: 82, samples: 19 },
            { predicted: 95, actual: 96, samples: 12 },
        ],
        mae: [
            { version: 'v0.1', mae: 0.198 },
            { version: 'v0.2', mae: 0.166 },
            { version: 'v0.3', mae: 0.151 },
            { version: 'v0.4', mae: 0.139 },
            { version: 'v0.5', mae: 0.118 },
        ],
        bandit: [
            { strategy: 'Do nothing', reward: 0.71, pulls: 20 },
            { strategy: 'Statistics refresh', reward: 0.52, pulls: 12 },
            { strategy: 'Index creation', reward: 0.48, pulls: 8 },
        ],
    },
}

export const roiEntries: RoiEntry[] = [
    {
        id: 'roi-1',
        connectionId: 'prod-orders-db',
        description: 'Batch reconciliation job with SKIP LOCKED',
        improvement: '-93% lock wait time',
        monthlySavingsUsd: 186,
        committedAtISO: ago(1 * day + 2 * hr),
    },
    {
        id: 'roi-2',
        connectionId: 'prod-orders-db',
        description: 'Autovacuum tuning + one-time VACUUM on sessions',
        improvement: '-46% scan cost',
        monthlySavingsUsd: 94,
        committedAtISO: ago(2 * day + 1 * hr),
    },
    {
        id: 'roi-3',
        connectionId: 'prod-orders-db',
        description: 'Increase shared_buffers to 8GB',
        improvement: '-18% p95 latency',
        monthlySavingsUsd: 240,
        committedAtISO: ago(4 * day + 22 * hr),
    },
    {
        id: 'roi-4',
        connectionId: 'staging-db',
        description: 'Rewrite N+1 order lookup into a single JOIN',
        improvement: '-86% mean latency',
        monthlySavingsUsd: null, // cost model not configured for staging
        committedAtISO: ago(6 * day + 21 * hr),
    },
    {
        id: 'roi-5',
        connectionId: 'analytics-warehouse',
        description: 'Right-size instance after query optimization',
        improvement: '-1 instance size',
        monthlySavingsUsd: 512,
        committedAtISO: ago(9 * day),
    },
]

export const activity: ActivityItem[] = [
    { id: 'a1', timeISO: ago(20 * min), connectionId: 'prod-orders-db', message: 'Statistics refresh on orders approved by maya.chen — canary in progress', kind: 'approve' },
    { id: 'a2', timeISO: ago(35 * min), connectionId: 'analytics-warehouse', message: 'New VERIFIED experiment awaiting approval: index on fact_events', kind: 'diagnose' },
    { id: 'a3', timeISO: ago(2 * hr + 12 * min), connectionId: 'prod-orders-db', message: 'Plan-flip regression detected on orders lookup (94% confidence)', kind: 'diagnose' },
    { id: 'a4', timeISO: ago(3 * hr), connectionId: 'analytics-warehouse', message: 'Forecast risk crossed threshold — scan-cost degradation likely', kind: 'forecast' },
    { id: 'a5', timeISO: ago(1 * day + 2 * hr), connectionId: 'prod-orders-db', message: 'Reconciliation batching committed — lock waits down 93%', kind: 'commit' },
    { id: 'a6', timeISO: ago(3 * day + 5 * hr), connectionId: 'analytics-warehouse', message: 'Drop-index change auto-rolled back — read regression detected', kind: 'rollback' },
]

// ---- Lightweight accessors (a stand-in for a typed API client) ----

export const getConnections = () => connections
export const getConnection = (id: string) => connections.find((c) => c.id === id)
export const getDiagnosesForConnection = (id: string) =>
    diagnoses.filter((d) => d.connectionId === id)
export const getAllDiagnoses = () => diagnoses
export const getActiveDiagnoses = () => diagnoses.filter((d) => d.status === 'Active')
export const getDiagnosis = (id: string) => diagnoses.find((d) => d.id === id)
export const getExperiments = () => experiments
export const getExperiment = (id: string) => experiments.find((e) => e.id === id)
export const getExperimentsForConnection = (id: string) =>
    experiments.filter((e) => e.connectionId === id)
export const getForecast = (id: string) => forecasts[id]
export const getRoiEntries = () => roiEntries
export const getActivity = () => activity
export const getConnectionName = (id: string) =>
    connections.find((c) => c.id === id)?.name ?? id
