import type { HealthStatus } from '../types/types'

// Deterministic pseudo-random so each connection has a stable "personality".
function mulberry32(seed: number) {
    return function () {
        seed |= 0
        seed = (seed + 0x6d2b79f5) | 0
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }
}

function hash(str: string) {
    let h = 2166136261
    for (let i = 0; i < str.length; i++) {
        h ^= str.charCodeAt(i)
        h = Math.imul(h, 16777619)
    }
    return h >>> 0
}

export type MetricKey =
    | 'p50'
    | 'p95'
    | 'p99'
    | 'throughput'
    | 'errorRate'
    | 'connections'
    | 'cpu'
    | 'cacheHit'
    | 'lockWaits'

export interface MetricSpec {
    key: MetricKey
    label: string
    unit: string
    tone: 'primary' | 'success' | 'warning' | 'danger' | 'info'
    threshold?: number
    base: number
    jitter: number
    min: number
    max: number
}

// Baselines scale with health so a Critical db visibly runs hot.
export function metricSpecs(health: HealthStatus): MetricSpec[] {
    const stress = health === 'Critical' ? 2.4 : health === 'Degraded' ? 1.5 : 1
    return [
        { key: 'p50', label: 'Latency p50', unit: 'ms', tone: 'primary', base: 4.2 * stress, jitter: 0.6, min: 1, max: 60 },
        { key: 'p95', label: 'Latency p95', unit: 'ms', tone: 'info', threshold: 120, base: 38 * stress, jitter: 6, min: 5, max: 400 },
        { key: 'p99', label: 'Latency p99', unit: 'ms', tone: 'warning', threshold: 250, base: 88 * stress, jitter: 14, min: 10, max: 900 },
        { key: 'throughput', label: 'Throughput', unit: 'qps', tone: 'success', base: 3400 / stress, jitter: 220, min: 100, max: 8000 },
        { key: 'errorRate', label: 'Error rate', unit: '%', tone: 'danger', threshold: 1, base: 0.08 * stress * stress, jitter: 0.05, min: 0, max: 12 },
        { key: 'connections', label: 'Active conns', unit: '', tone: 'info', threshold: 180, base: 62 * stress, jitter: 8, min: 1, max: 300 },
        { key: 'cpu', label: 'CPU', unit: '%', tone: 'warning', threshold: 85, base: 34 * stress, jitter: 5, min: 2, max: 100 },
        { key: 'cacheHit', label: 'Cache hit', unit: '%', tone: 'success', base: 99.4 - (stress - 1) * 4, jitter: 0.3, min: 80, max: 100 },
        { key: 'lockWaits', label: 'Lock waits', unit: '/s', tone: 'danger', threshold: 20, base: 1.5 * stress * stress, jitter: 1.2, min: 0, max: 120 },
    ]
}

const POINTS = 40

export function seedSeries(connId: string, spec: MetricSpec): { t: number; value: number }[] {
    const rand = mulberry32(hash(connId + spec.key))
    const out: { t: number; value: number }[] = []
    let v = spec.base
    for (let i = 0; i < POINTS; i++) {
        v += (rand() - 0.5) * spec.jitter * 2
        v = Math.min(spec.max, Math.max(spec.min, v * 0.85 + spec.base * 0.15))
        out.push({ t: i, value: Number(v.toFixed(2)) })
    }
    return out
}

export function nextValue(spec: MetricSpec, prev: number): number {
    const drift = (Math.random() - 0.5) * spec.jitter * 2
    const meanRevert = (spec.base - prev) * 0.12
    const v = prev + drift + meanRevert
    return Number(Math.min(spec.max, Math.max(spec.min, v)).toFixed(2))
}
