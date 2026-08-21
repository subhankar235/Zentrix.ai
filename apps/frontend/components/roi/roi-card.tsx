import Link from 'next/link'
import { CircleHelp, TrendingDown } from 'lucide-react'
import type { RoiEntry } from '@/types/types'
import { Card } from '@/components/ui/card'
import { usd } from '@/lib/format'
import { getConnectionName } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

export function RoiCard({
  entry,
  showConnection = true,
}: {
  entry: RoiEntry
  showConnection?: boolean
}) {
  const configured = entry.monthlySavingsUsd != null

  return (
    <Card className={cn('p-4', !configured && 'opacity-75')}>
      <div className="space-y-2.5">
        <div className="flex items-start justify-between gap-3">
          <p className="min-w-0 text-sm font-medium text-balance">{entry.description}</p>
          <TrendingDown className="h-4 w-4 shrink-0 text-success" />
        </div>

        {showConnection ? (
          <Link
            href={`/forecasts/${entry.connectionId}`}
            className="block w-fit text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            {getConnectionName(entry.connectionId)}
          </Link>
        ) : null}

        <div className="flex items-end justify-between gap-3 pt-1">
          <span className="text-xs font-medium text-success">{entry.improvement}</span>
          {entry.monthlySavingsUsd != null ? (
            <p className="tnum text-xl font-semibold">
              ~{usd(entry.monthlySavingsUsd)}
              <span className="text-xs font-normal text-muted-foreground">/month</span>
            </p>
          ) : (
            <p className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted px-2 py-1 text-[11px] font-medium text-muted-foreground">
              <CircleHelp className="h-3.5 w-3.5" />
              Cost model not configured
            </p>
          )}
        </div>

        {!configured ? (
          <p className="border-t border-border/60 pt-2 text-[11px] leading-relaxed text-muted-foreground text-pretty">
            No pricing inputs are configured for this database (instance cost per hour and
            workload value), so no dollar figure is estimated.
          </p>
        ) : null}
      </div>
    </Card>
  )
}
