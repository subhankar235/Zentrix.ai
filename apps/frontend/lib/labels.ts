import type { RootCauseClass, Recommendation } from '../types/types'

export const rootCauseLabel: Record<RootCauseClass, string> = {
    STALE_STATISTICS: 'Stale statistics',
    PLAN_FLIP: 'Query plan flip',
    CARDINALITY_MISESTIMATION: 'Cardinality misestimation',
    LOCK_CONTENTION: 'Lock contention',
    INDEX_MISSING: 'Missing index',
    INDEX_UNUSED: 'Unused index',
    VACUUM_LAG: 'Autovacuum lag',
    BLOAT: 'Table / index bloat',
    BUFFER_PRESSURE: 'Buffer cache pressure',
    IO_SATURATION: 'I/O saturation',
    TEMP_SPILL: 'Temp file spill',
    CONNECTION_CONTENTION: 'Connection contention',
    CHECKPOINT_PRESSURE: 'Checkpoint pressure',
    UNKNOWN: 'Unknown',
}

export const recTypeLabel: Record<Recommendation['type'], string> = {
    INDEX: 'Index',
    STATISTICS: 'Statistics',
    CONFIG: 'Configuration',
    QUERY_REWRITE: 'Query rewrite',
    VACUUM: 'Vacuum',
}
