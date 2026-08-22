import {
    CheckCircle2,
    GitCommitHorizontal,
    RotateCcw,
    Stethoscope,
    TrendingUp,
} from 'lucide-react'
import type { ActivityItem } from '@/types/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { relativeTime } from '@/lib/format'
import { getConnectionName } from '@/lib/mock-data'

const iconFor: Record<ActivityItem['kind'], { icon: React.ComponentType<{ className?: string }>; tone: string }> = {
    approve: { icon: CheckCircle2, tone: 'text-success' },
    commit: { icon: GitCommitHorizontal, tone: 'text-success' },
    rollback: { icon: RotateCcw, tone: 'text-danger' },
    forecast: { icon: TrendingUp, tone: 'text-info' },
    diagnose: { icon: Stethoscope, tone: 'text-warning' },
}

export function ActivityFeed({ items }: { items: ActivityItem[] }) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Recent activity</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <ul className="divide-y divide-border">
                    {items.map((item) => {
                        const { icon: Icon, tone } = iconFor[item.kind]
                        return (
                            <li key={item.id} className="flex gap-3 px-4 py-3">
                                <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tone}`} />
                                <div className="min-w-0">
                                    <p className="text-sm text-pretty">{item.message}</p>
                                    <p className="mt-0.5 text-xs text-muted-foreground">
                                        <span className="font-mono">{getConnectionName(item.connectionId)}</span> ·{' '}
                                        {relativeTime(item.timeISO)}
                                    </p>
                                </div>
                            </li>
                        )
                    })}
                </ul>
            </CardContent>
        </Card>
    )
}
