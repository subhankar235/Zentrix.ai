'use client'

import * as React from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronRight, FlaskConical, Scale, Search } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { Card } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { EmptyState } from '@/components/states'
import { getConnections, getConnectionName, getExperiments } from '@/lib/mock-data'
import { absoluteTime, relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { DeploymentOutcome, Verdict } from '@/types/types'

const VERDICTS: (Verdict | 'All')[] = ['All', 'VERIFIED', 'CONDITIONAL', 'REJECTED']
const OUTCOMES: (DeploymentOutcome | 'All')[] = [
  'All',
  'COMMIT',
  'ROLLBACK',
  'AWAITING_APPROVAL',
  'IN_PROGRESS',
]

export default function ExperimentsPage() {
  const all = getExperiments()
  const connectionsList = getConnections()

  const [dbFilter, setDbFilter] = React.useState<string>('all')
  const [verdict, setVerdict] = React.useState<Verdict | 'All'>('All')
  const [outcome, setOutcome] = React.useState<DeploymentOutcome | 'All'>('All')
  const [query, setQuery] = React.useState('')
  const [newestFirst, setNewestFirst] = React.useState(true)
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set())

  const rows = all
    .filter((e) => (dbFilter === 'all' ? true : e.connectionId === dbFilter))
    .filter((e) => (verdict === 'All' ? true : e.verdict === verdict))
    .filter((e) => (outcome === 'All' ? true : e.outcome === outcome))
    .filter((e) => (query ? e.candidate.toLowerCase().includes(query.toLowerCase()) : true))
    .sort((a, b) =>
      newestFirst
        ? b.createdAtISO.localeCompare(a.createdAtISO)
        : a.createdAtISO.localeCompare(b.createdAtISO),
    )

  const awaiting = all.filter((e) => e.outcome === 'AWAITING_APPROVAL').length
  const committed = all.filter((e) => e.outcome === 'COMMIT').length
  const rolledBack = all.filter((e) => e.outcome === 'ROLLBACK').length

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Optimization history"
        description="Every experiment the system has ever run, including approvals, commits, and rollbacks. This is the trust ledger — no production-facing action happens outside of it."
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total experiments" value={all.length} />
        <Stat label="Awaiting approval" value={awaiting} tone="text-warning" />
        <Stat label="Committed" value={committed} tone="text-success" />
        <Stat label="Rolled back" value={rolledBack} tone="text-danger" />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={dbFilter}
          onChange={(e) => setDbFilter(e.target.value)}
          className="h-8 rounded-md border border-border bg-background px-2 text-xs outline-none focus:ring-2 focus:ring-ring"
          aria-label="Filter by database"
        >
          <option value="all">All databases</option>
          {connectionsList.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <Segmented
          value={verdict}
          onChange={(v) => setVerdict(v as Verdict | 'All')}
          options={VERDICTS.map((v) => ({ value: v, label: v === 'All' ? 'All verdicts' : v }))}
        />
        <Segmented
          value={outcome}
          onChange={(v) => setOutcome(v as DeploymentOutcome | 'All')}
          options={OUTCOMES.map((o) => ({
            value: o,
            label: o === 'All' ? 'All outcomes' : o.replace(/_/g, ' '),
          }))}
        />
        <button
          onClick={() => setNewestFirst((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <Scale className="h-3.5 w-3.5" />
          {newestFirst ? 'Newest first' : 'Oldest first'}
        </button>
        <label className="relative ml-auto">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search candidates…"
            className="h-8 w-56 rounded-md border border-border bg-background pl-8 pr-3 text-xs outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
          />
        </label>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          icon={FlaskConical}
          title="No experiments match"
          description="Adjust the filters or search to see historical optimization experiments."
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="w-8 px-3 py-2.5"></th>
                  <th className="px-3 py-2.5 font-medium">Candidate</th>
                  <th className="px-3 py-2.5 font-medium">Verdict</th>
                  <th className="px-3 py-2.5 font-medium">Outcome</th>
                  <th className="hidden px-3 py-2.5 font-medium md:table-cell">Approver</th>
                  <th className="px-3 py-2.5 text-right font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => {
                  const open = expanded.has(e.id)
                  return (
                    <React.Fragment key={e.id}>
                      <tr className="border-b border-border/60 transition-colors last:border-0 hover:bg-muted/30">
                        <td className="px-3 py-2.5">
                          <button
                            onClick={() => toggle(e.id)}
                            aria-label={open ? 'Collapse audit log' : 'Expand audit log'}
                            className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                          >
                            {open ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </button>
                        </td>
                        <td className="max-w-md px-3 py-2.5">
                          <Link
                            href={`/experiments/${e.id}`}
                            className="block truncate font-medium hover:text-primary"
                          >
                            {e.candidate}
                          </Link>
                          <span className="text-xs text-muted-foreground">
                            {getConnectionName(e.connectionId)}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <StatusBadge status={e.verdict} />
                        </td>
                        <td className="px-3 py-2.5">
                          <StatusBadge status={e.outcome} dot={e.outcome === 'IN_PROGRESS'} />
                        </td>
                        <td className="hidden px-3 py-2.5 text-muted-foreground md:table-cell">
                          {e.approver ?? '—'}
                        </td>
                        <td
                          className="tnum whitespace-nowrap px-3 py-2.5 text-right text-muted-foreground"
                          title={absoluteTime(e.createdAtISO)}
                        >
                          {relativeTime(e.createdAtISO)}
                        </td>
                      </tr>
                      {open ? (
                        <tr className="border-b border-border/60 bg-muted/20 last:border-0">
                          <td colSpan={6} className="px-6 py-4">
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                              Audit log
                            </p>
                            <ol className="space-y-1.5">
                              {e.auditLog.map((a, i) => (
                                <li key={i} className="flex flex-wrap items-baseline gap-x-3 text-xs">
                                  <time
                                    className="tnum w-28 shrink-0 text-muted-foreground"
                                    dateTime={a.timeISO}
                                    title={a.timeISO}
                                  >
                                    {absoluteTime(a.timeISO)} UTC
                                  </time>
                                  <span className="font-mono text-[11px] text-info">{a.actor}</span>
                                  <span className="text-foreground/90">{a.action}</span>
                                </li>
                              ))}
                            </ol>
                          </td>
                        </tr>
                      ) : null}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <Card size="sm">
      <div className="p-3">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={cn('tnum mt-1 text-xl font-semibold', tone)}>{value}</p>
      </div>
    </Card>
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
          className={`rounded px-2 py-1 text-xs font-medium whitespace-nowrap transition-colors ${value === o.value
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
