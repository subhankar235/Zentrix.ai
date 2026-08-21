import {
    Activity,
    BarChart3,
    GitBranch,
    Gauge,
    Lock,
    Trash2,
    type LucideIcon,
} from 'lucide-react'
import type { TimelineEntry } from '@/types/types'
import { absoluteTime, relativeTime } from '@/lib/format'

const iconMap: Record<TimelineEntry['icon'], LucideIcon> = {
    load: Activity,
    stats: BarChart3,
    plan: GitBranch,
    latency: Gauge,
    lock: Lock,
    vacuum: Trash2,
}

export function Timeline({ entries }: { entries: TimelineEntry[] }) {
    return (
        <ol className="relative space-y-5 pl-2">
            <span className="absolute bottom-2 left-[13px] top-2 w-px bg-border" aria-hidden="true" />
            {entries.map((e, i) => {
                const Icon = iconMap[e.icon]
                return (
                    <li key={i} className="relative flex gap-4">
                        <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-card">
                            <Icon className="h-3 w-3 text-muted-foreground" />
                        </span>
                        <div className="min-w-0 flex-1 -mt-0.5">
                            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                                <p className="text-sm font-medium">{e.title}</p>
                                <time
                                    className="tnum text-xs text-muted-foreground"
                                    title={absoluteTime(e.timeISO)}
                                    dateTime={e.timeISO}
                                >
                                    {relativeTime(e.timeISO)}
                                </time>
                            </div>
                            <p className="mt-0.5 text-sm text-muted-foreground text-pretty">{e.detail}</p>
                        </div>
                    </li>
                )
            })}
        </ol>
    )
}
