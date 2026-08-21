'use client'

import * as React from 'react'
import type { EvidenceNode, EvidenceEdge } from '@/types/types'
import { cn } from '@/lib/utils'

const COLUMN_ORDER: EvidenceNode['kind'][] = ['event', 'cause', 'symptom']
const COLUMN_LABEL: Record<EvidenceNode['kind'], string> = {
    event: 'Trigger',
    cause: 'Mechanism',
    symptom: 'Observed symptom',
}
const kindTone: Record<EvidenceNode['kind'], string> = {
    event: 'border-info/40 bg-info/5',
    cause: 'border-primary/50 bg-primary/10',
    symptom: 'border-warning/40 bg-warning/5',
}

const NODE_W = 176
const NODE_H = 74
const COL_GAP = 72
const ROW_GAP = 20

export function EvidenceGraph({
    nodes,
    edges,
}: {
    nodes: EvidenceNode[]
    edges: EvidenceEdge[]
}) {
    const columns = COLUMN_ORDER.map((kind) => nodes.filter((n) => n.kind === kind))
    const maxRows = Math.max(...columns.map((c) => c.length), 1)
    const width = COLUMN_ORDER.length * NODE_W + (COLUMN_ORDER.length - 1) * COL_GAP
    const height = maxRows * NODE_H + (maxRows - 1) * ROW_GAP

    const pos = React.useMemo(() => {
        const map = new Map<string, { x: number; y: number }>()
        columns.forEach((col, ci) => {
            const colHeight = col.length * NODE_H + (col.length - 1) * ROW_GAP
            const offsetY = (height - colHeight) / 2
            col.forEach((node, ri) => {
                map.set(node.id, {
                    x: ci * (NODE_W + COL_GAP),
                    y: offsetY + ri * (NODE_H + ROW_GAP),
                })
            })
        })
        return map
    }, [columns, height])

    return (
        <div className="overflow-x-auto">
            <div className="relative mx-auto" style={{ width, height, minWidth: width }}>
                <svg
                    className="pointer-events-none absolute inset-0"
                    width={width}
                    height={height}
                    aria-hidden="true"
                >
                    <defs>
                        <marker
                            id="evidence-arrow"
                            viewBox="0 0 10 10"
                            refX="9"
                            refY="5"
                            markerWidth="6"
                            markerHeight="6"
                            orient="auto-start-reverse"
                        >
                            <path d="M0,0 L10,5 L0,10 z" fill="var(--border)" />
                        </marker>
                    </defs>
                    {edges.map((e, i) => {
                        const from = pos.get(e.from)
                        const to = pos.get(e.to)
                        if (!from || !to) return null
                        const x1 = from.x + NODE_W
                        const y1 = from.y + NODE_H / 2
                        const x2 = to.x
                        const y2 = to.y + NODE_H / 2
                        const mx = (x1 + x2) / 2
                        return (
                            <path
                                key={i}
                                d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`}
                                fill="none"
                                stroke="var(--border)"
                                strokeWidth={1.5}
                                markerEnd="url(#evidence-arrow)"
                            />
                        )
                    })}
                </svg>
                {nodes.map((n) => {
                    const p = pos.get(n.id)
                    if (!p) return null
                    return (
                        <div
                            key={n.id}
                            className={cn(
                                'absolute flex flex-col justify-center gap-1 rounded-lg border p-3 shadow-sm',
                                kindTone[n.kind],
                            )}
                            style={{ left: p.x, top: p.y, width: NODE_W, height: NODE_H }}
                        >
                            <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                                {COLUMN_LABEL[n.kind]}
                            </span>
                            <span className="text-xs font-medium leading-tight text-foreground text-pretty">
                                {n.label}
                            </span>
                            {n.metric ? (
                                <span className="tnum text-[11px] text-muted-foreground">
                                    {n.metric}: <span className="text-foreground/90">{n.value}</span>
                                </span>
                            ) : (
                                <span className="line-clamp-1 text-[11px] text-muted-foreground">{n.detail}</span>
                            )}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
