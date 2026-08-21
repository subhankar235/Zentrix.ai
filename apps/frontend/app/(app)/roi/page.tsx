'use client'

import * as React from 'react'
import { DollarSign, Info } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { RoiCard } from '@/components/roi/roi-card'
import { EmptyState } from '@/components/states'
import { Card, CardContent } from '@/components/ui/card'
import { getConnections, getRoiEntries } from '@/lib/mock-data'
import { usd } from '@/lib/format'

export default function RoiPage() {
  const entries = React.useMemo(() => getRoiEntries(), [])
  const configured = entries.filter((e) => e.monthlySavingsUsd != null)
  const unconfigured = entries.length - configured.length
  const total = configured.reduce((sum, e) => sum + (e.monthlySavingsUsd ?? 0), 0)

  if (entries.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="Cost / ROI" />
        <EmptyState
          icon={DollarSign}
          title="No committed optimizations yet"
          description="Dollar impact appears here after an optimization passes its canary window and is committed."
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cost / performance analytics"
        description="Measured dollar impact of every committed optimization. Figures are computed from your configured cost model — never estimated client-side."
      />

      <Card>
        <CardContent>
          <div className="flex flex-wrap items-end justify-between gap-4 py-1">
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                Total estimated savings
              </p>
              <p className="tnum mt-1 text-3xl font-semibold text-success">{usd(total)}</p>
            </div>
            <div className="flex gap-8">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  Committed optimizations
                </p>
                <p className="tnum mt-1 text-xl font-semibold">{configured.length}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Databases</p>
                <p className="tnum mt-1 text-xl font-semibold">{getConnections().length}</p>
              </div>
            </div>
          </div>
          {unconfigured > 0 ? (
            <p className="mt-3 flex items-start gap-2 border-t border-border pt-3 text-xs text-muted-foreground text-pretty">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Excludes {unconfigured} committed optimization{unconfigured === 1 ? '' : 's'} with no
              configured pricing inputs — those cards show a fallback instead of a fabricated number.
            </p>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {entries.map((e) => (
          <RoiCard key={e.id} entry={e} showConnection />
        ))}
      </div>
    </div>
  )
}
