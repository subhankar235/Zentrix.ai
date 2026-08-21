'use client'

import * as React from 'react'
import Link from 'next/link'
import { Check, Plus, X } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { ConnectionCard } from '@/components/connections/connection-card'
import { AddConnectionDialog } from '@/components/connections/add-connection-dialog'
import { getConnections } from '@/lib/mock-data'
import { absoluteTime, relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'

export default function ConnectionsPage() {
  const connections = getConnections()
  const [selectedId, setSelectedId] = React.useState(connections[0].id)
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const selected = connections.find((c) => c.id === selectedId)!

  const checklist: [string, boolean][] = [
    ['Host reachable over TLS', selected.checks.reachability],
    ['Credentials authenticated', selected.checks.credentials],
    ['pg_stat_statements enabled', selected.checks.pgStatStatements],
    ['Read-only monitoring role', selected.checks.readOnlyRole],
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Connections"
        description="Databases Zentrix monitors. Each connection uses a read-only role and requires pg_stat_statements."
        actions={
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" /> Add connection
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <div className="grid gap-3 sm:grid-cols-2">
          {connections.map((c) => (
            <ConnectionCard
              key={c.id}
              conn={c}
              selected={c.id === selectedId}
              onSelect={() => setSelectedId(c.id)}
            />
          ))}
        </div>

        <Card className="h-fit">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="font-mono">{selected.name}</CardTitle>
            <StatusBadge status={selected.status} dot />
          </CardHeader>
          <CardContent className="space-y-4">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
              <div>
                <dt className="text-muted-foreground">Provider</dt>
                <dd className="mt-0.5 font-medium">{selected.provider}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Region</dt>
                <dd className="mt-0.5 font-medium">{selected.region}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Engine</dt>
                <dd className="mt-0.5 font-medium">{selected.version}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Last poll</dt>
                <dd className="mt-0.5 font-medium" title={absoluteTime(selected.lastCheckedISO)}>
                  {relativeTime(selected.lastCheckedISO)}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Host</dt>
                <dd className="mt-0.5 break-all font-mono text-[11px]">{selected.host}</dd>
              </div>
            </dl>

            <div>
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Extension &amp; permission checks
              </p>
              <ul className="space-y-2">
                {checklist.map(([label, ok]) => (
                  <li key={label} className="flex items-center gap-2 text-xs">
                    <span
                      className={cn(
                        'flex h-4 w-4 items-center justify-center rounded-full',
                        ok ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger',
                      )}
                    >
                      {ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                    </span>
                    {label}
                  </li>
                ))}
              </ul>
            </div>

            <Button variant="outline" className="w-full" asChild>
              <Link href={`/monitoring/${selected.id}`}>View live monitoring</Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      <AddConnectionDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </div>
  )
}
