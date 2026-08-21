'use client'

import * as React from 'react'
import { PageHeader } from '@/components/page-header'
import { ConnectionSummaryCard } from '@/components/dashboard/connection-summary-card'
import { ActiveProblemsList } from '@/components/dashboard/active-problems-list'
import { ActivityFeed } from '@/components/dashboard/activity-feed'
import { Card, CardContent } from '@/components/ui/card'
import { getConnections, getActiveDiagnoses, getActivity, getExperiments } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

export default function DashboardPage() {
  const [healthy, setHealthy] = React.useState(false)
  const connections = getConnections()
  const activeDiagnoses = healthy ? [] : getActiveDiagnoses()
  const activity = getActivity()
  const awaitingApproval = getExperiments().filter((e) => e.outcome === 'AWAITING_APPROVAL').length

  const totalProblems = activeDiagnoses.length
  const criticalDbs = connections.filter((c) => c.health === 'Critical').length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fleet overview"
        description="Health, active problems, and recent automated activity across every connected database."
        actions={
          <div className="flex items-center gap-1 rounded-md border border-border p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setHealthy(false)}
              className={cn(
                'rounded px-2.5 py-1 transition-colors',
                !healthy ? 'bg-accent font-medium' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              Live data
            </button>
            <button
              type="button"
              onClick={() => setHealthy(true)}
              className={cn(
                'rounded px-2.5 py-1 transition-colors',
                healthy ? 'bg-accent font-medium' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              Healthy state
            </button>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Databases</p>
            <p className="tnum mt-1 text-2xl font-semibold">{connections.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Active problems</p>
            <p className={cn('tnum mt-1 text-2xl font-semibold', totalProblems > 0 && 'text-warning')}>
              {totalProblems}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Critical</p>
            <p className={cn('tnum mt-1 text-2xl font-semibold', criticalDbs > 0 && 'text-danger')}>
              {healthy ? 0 : criticalDbs}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Awaiting approval</p>
            <p className="tnum mt-1 text-2xl font-semibold text-info">{awaitingApproval}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {connections.map((c) => (
          <ConnectionSummaryCard
            key={c.id}
            conn={healthy ? { ...c, health: 'Healthy', activeProblems: 0 } : c}
          />
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Active problems</h2>
          <ActiveProblemsList diagnoses={activeDiagnoses} />
        </section>
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Activity</h2>
          <ActivityFeed items={activity} />
        </section>
      </div>
    </div>
  )
}
