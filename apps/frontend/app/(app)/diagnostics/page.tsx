'use client'

import * as React from 'react'
import { Stethoscope } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { DiagnosisCard } from '@/components/diagnostics/diagnosis-card'
import { EmptyState } from '@/components/states'
import { useSelectedDb } from '@/components/app-providers'
import { getConnection, getAllDiagnoses, getDiagnosesForConnection } from '@/lib/mock-data'

type Scope = 'this' | 'all'
type StatusFilter = 'all' | 'Active' | 'Resolved'

export default function DiagnosticsPage() {
  const { selectedId } = useSelectedDb()
  const conn = getConnection(selectedId)
  const [scope, setScope] = React.useState<Scope>('this')
  const [status, setStatus] = React.useState<StatusFilter>('all')
  const [onlyLow, setOnlyLow] = React.useState(false)

  const base = scope === 'all' ? getAllDiagnoses() : getDiagnosesForConnection(selectedId)
  const list = base
    .filter((d) => (status === 'all' ? true : d.status === status))
    .filter((d) => (onlyLow ? d.lowConfidence : true))
    .sort((a, b) => b.confidencePct - a.confidencePct)

  const active = base.filter((d) => d.status === 'Active').length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Diagnostics"
        description={`Root-cause analyses across ${scope === 'all' ? 'all connected databases' : conn?.name ?? 'this database'}. ${active} active.`}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          value={scope}
          onChange={(v) => setScope(v as Scope)}
          options={[
            { value: 'this', label: 'This database' },
            { value: 'all', label: 'All databases' },
          ]}
        />
        <Segmented
          value={status}
          onChange={(v) => setStatus(v as StatusFilter)}
          options={[
            { value: 'all', label: 'All' },
            { value: 'Active', label: 'Active' },
            { value: 'Resolved', label: 'Resolved' },
          ]}
        />
        <button
          onClick={() => setOnlyLow((v) => !v)}
          className={`rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors ${
            onlyLow
              ? 'border-warning/40 bg-warning/10 text-warning'
              : 'border-border text-muted-foreground hover:text-foreground'
          }`}
        >
          Low confidence only
        </button>
      </div>

      {list.length === 0 ? (
        <EmptyState
          icon={Stethoscope}
          title="No diagnoses match"
          description="The agent has not surfaced any root-cause analyses for this filter. Healthy databases produce no findings."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {list.map((d) => (
            <DiagnosisCard key={d.id} diagnosis={d} showConnection={scope === 'all'} />
          ))}
        </div>
      )}
    </div>
  )
}

function Segmented({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div className="flex items-center gap-0.5 rounded-md border border-border p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            value === o.value
              ? 'bg-secondary text-secondary-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
