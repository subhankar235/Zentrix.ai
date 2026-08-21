'use client'

import * as React from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import {
  ArrowLeft,
  CheckCircle2,
  CircleDashed,
  FlaskConical,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { EmptyState, ErrorBanner } from '@/components/states'
import { Button } from '@/components/ui/button'
import { PipelineStepper } from '@/components/simulation/pipeline-stepper'
import { ApprovalPanel, RejectedBanner } from '@/components/simulation/approval-panel'
import { CanaryLivePanel } from '@/components/simulation/canary-live-panel'
import { useToast } from '@/components/app-providers'
import { ago, getConnectionName, getExperiment } from '@/lib/mock-data'
import { absoluteTime, deltaPct, relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Experiment } from '@/types/types'

export default function ExperimentDetailPage() {
  const params = useParams<{ experimentId: string }>()
  const original = getExperiment(params.experimentId)
  const [exp, setExp] = React.useState<Experiment | undefined>(original)
  const { toast } = useToast()

  if (!exp) {
    return (
      <div className="space-y-6">
        <PageHeader title="Experiment not found" />
        <EmptyState
          icon={FlaskConical}
          title="This experiment does not exist"
          description="It may have been archived."
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/experiments">Back to history</Link>
            </Button>
          }
        />
      </div>
    )
  }

  const completed = exp.outcome === 'COMMIT' || exp.outcome === 'ROLLBACK'
  const canaryRunning = exp.approvalState === 'APPROVED' && exp.outcome === 'IN_PROGRESS'
  const awaitingApproval =
    exp.approvalState === 'PENDING_APPROVAL' && exp.outcome === 'AWAITING_APPROVAL'
  const rejectedByUser = exp.approvalState === 'REJECTED'

  // Seed canary metrics from the simulated candidate values.
  const seedFrom = (key: string) => exp.comparisons.find((c) => c.metric.toLowerCase().includes(key))
  const seed = {
    p50: seedFrom('mean')?.candidate ?? 58,
    p95: seedFrom('p95')?.candidate ?? 134,
    p99: seedFrom('p99')?.candidate ?? 210,
    errorRate: 0.02,
    lockWaits: 2,
    cpu: seedFrom('cpu')?.candidate ?? 38,
    throughput: seedFrom('throughput')?.candidate ?? 1800,
  }

  function handleApprove() {
    setExp((prev) =>
      prev
        ? {
          ...prev,
          approvalState: 'APPROVED',
          outcome: 'IN_PROGRESS',
          approver: 'maya.chen',
          auditLog: [
            ...prev.auditLog,
            { actor: 'maya.chen', action: 'Approved for canary deployment', timeISO: ago(0) },
            { actor: 'system', action: 'Canary monitoring window started', timeISO: ago(0) },
          ],
        }
        : prev,
    )
    toast({
      kind: 'success',
      title: 'Approval recorded',
      description: 'Canary deployment started. The audit trail has been updated.',
    })
  }

  function handleReject() {
    setExp((prev) =>
      prev
        ? {
          ...prev,
          approvalState: 'REJECTED',
          auditLog: [
            ...prev.auditLog,
            { actor: 'maya.chen', action: 'Rejected candidate — no deployment', timeISO: ago(0) },
          ],
        }
        : prev,
    )
    toast({
      kind: 'warning',
      title: 'Recommendation rejected',
      description: 'No changes will be made to production.',
    })
  }

  function handleCanaryComplete() {
    setExp((prev) =>
      prev && !prev.rollbackReason
        ? {
          ...prev,
          outcome: 'COMMIT',
          completedAtISO: ago(0),
          auditLog: [
            ...prev.auditLog,
            { actor: 'system', action: 'Canary succeeded — COMMIT', timeISO: ago(0) },
          ],
        }
        : prev,
    )
    toast({
      kind: 'success',
      title: 'Canary committed',
      description: 'The optimization is now live and the outcome is recorded in the ledger.',
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb={
          <Link href="/experiments" className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3 w-3" /> Optimization history
          </Link>
        }
        title={exp.candidate}
        description={`${getConnectionName(exp.connectionId)} · proposed ${relativeTime(exp.createdAtISO)}${exp.completedAtISO ? ` · completed ${relativeTime(exp.completedAtISO)}` : ''
          }`}
        actions={
          <div className="flex flex-col items-end gap-1.5">
            <StatusBadge status={exp.verdict} dot />
            <StatusBadge status={exp.outcome} />
          </div>
        }
      />

      {exp.rollbackReason ? (
        <ErrorBanner
          title="Auto-rolled back by policy"
          description={exp.rollbackReason}
        />
      ) : null}

      <Card>
        <CardHeader className="border-b [.border-b]:pb-3">
          <CardTitle>Pipeline</CardTitle>
          <CardDescription>
            Every candidate passes six independent gates before it may touch production.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PipelineStepper currentStage={exp.currentStage} completed={completed || rejectedByUser} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.5fr_1fr]">
        {/* Verification report */}
        <Card>
          <CardHeader className="border-b [.border-b]:pb-3">
            <CardTitle>Verification report</CardTitle>
            <CardDescription>Shadow-database simulation vs. live baseline.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ComparisonTable comparisons={exp.comparisons} />

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-border bg-background/40 p-3">
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  Bootstrap 95% CI (improvement)
                </p>
                <p className="tnum mt-1 text-sm font-semibold">
                  [{exp.ciLow.toFixed(1)}%, {exp.ciHigh.toFixed(1)}%]
                  {exp.ciLow > 0 ? (
                    <span className="ml-2 text-xs font-normal text-success">excludes zero</span>
                  ) : (
                    <span className="ml-2 text-xs font-normal text-danger">includes zero</span>
                  )}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-background/40 p-3">
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  Regression rate
                </p>
                <p
                  className={cn(
                    'tnum mt-1 text-sm font-semibold',
                    exp.regressionRatePct >= 5 ? 'text-danger' : 'text-success',
                  )}
                >
                  {exp.regressionRatePct.toFixed(1)}%
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    of sampled workloads regressed
                  </span>
                </p>
              </div>
            </div>

            <p className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground text-pretty">
              <ShieldAlert className="mr-1.5 inline h-3.5 w-3.5 align-[-2px]" />
              {exp.significance}
            </p>
          </CardContent>
        </Card>

        <div className="space-y-6">
          {/* Skeptic findings */}
          <Card>
            <CardHeader className="border-b [.border-b]:pb-3">
              <CardTitle>Skeptic findings</CardTitle>
              <CardDescription>Adversarial checks for what could go wrong.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {exp.skepticFindings.map((f, i) => (
                <div key={i} className="flex items-start gap-2.5">
                  {f.status === 'pass' ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                  ) : (
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {f.concern}{' '}
                      <span
                        className={cn(
                          'text-[10px] font-semibold uppercase tracking-wide',
                          f.status === 'pass' ? 'text-muted-foreground' : 'text-warning',
                        )}
                      >
                        {f.status === 'pass' ? 'pass' : 'flagged'}
                      </span>
                    </p>
                    <p className="text-xs text-muted-foreground text-pretty">{f.note}</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Policy verdict */}
          <Card>
            <CardHeader className="border-b [.border-b]:pb-3">
              <CardTitle>Policy verdict</CardTitle>
              <CardDescription>Deterministic thresholds — no judgment calls.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {exp.policyChecks.map((c, i) => (
                <div key={i} className="flex items-center justify-between gap-2 text-sm">
                  <span className="min-w-0 text-pretty">{c.rule}</span>
                  {c.passed ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 text-danger" />
                  )}
                </div>
              ))}
              <div className="flex items-center justify-between border-t border-border pt-3">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  Overall verdict
                </span>
                <StatusBadge status={exp.verdict} dot />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Approval / canary / terminal states */}
      {awaitingApproval ? (
        <Card>
          <CardHeader className="border-b [.border-b]:pb-3">
            <CardTitle>Deployment decision</CardTitle>
          </CardHeader>
          <CardContent>
            <ApprovalPanel verdict={exp.verdict} onApprove={handleApprove} onReject={handleReject} />
          </CardContent>
        </Card>
      ) : null}

      {rejectedByUser ? <RejectedBanner /> : null}

      {canaryRunning ? (
        <CanaryLivePanel key={exp.id} seed={seed} onComplete={handleCanaryComplete} />
      ) : null}

      {completed && exp.outcome === 'COMMIT' ? (
        <div className="flex items-start gap-3 rounded-lg border border-success/30 bg-success/10 p-4">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
          <div>
            <p className="text-sm font-semibold text-success">Canary passed — COMMIT</p>
            <p className="mt-0.5 text-xs text-muted-foreground text-pretty">
              All guardrail metrics stayed within thresholds for the full window. The change was
              promoted{exp.completedAtISO ? ` ${relativeTime(exp.completedAtISO)}` : ''}.
            </p>
          </div>
        </div>
      ) : null}

      {completed && exp.outcome === 'ROLLBACK' ? (
        <Card>
          <CardContent className="pt-1 text-xs text-muted-foreground">
            The monitoring window closed with an automatic rollback. Live metrics from the window are
            retained in the audit log above.
          </CardContent>
        </Card>
      ) : null}

      {/* Audit log */}
      <Card>
        <CardHeader className="border-b [.border-b]:pb-3">
          <CardTitle>Audit trail</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-2.5">
            {exp.auditLog.map((a, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-x-3 text-xs">
                <span className="inline-flex w-5 justify-center">
                  <CircleDashed className="h-3 w-3 text-muted-foreground/60" />
                </span>
                <time
                  className="tnum w-28 shrink-0 text-muted-foreground"
                  dateTime={a.timeISO}
                  title={absoluteTime(a.timeISO)}
                >
                  {absoluteTime(a.timeISO)} UTC
                </time>
                <span className="font-mono text-[11px] text-info">{a.actor}</span>
                <span className="text-foreground/90">{a.action}</span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  )
}

function ComparisonTable({
  comparisons,
}: {
  comparisons: Experiment['comparisons']
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="px-4 py-2 font-medium">Metric</th>
            <th className="px-3 py-2 text-right font-medium">Baseline</th>
            <th className="px-3 py-2 text-right font-medium">Candidate</th>
            <th className="px-4 py-2 text-right font-medium">Δ</th>
          </tr>
        </thead>
        <tbody>
          {comparisons.map((c) => {
            const delta = deltaPct(c.baseline, c.candidate, c.betterWhenLower)
            return (
              <tr key={c.metric} className="border-b border-border/60 last:border-0">
                <td className="px-4 py-2.5">{c.metric}</td>
                <td className="tnum px-3 py-2.5 text-right text-muted-foreground">
                  {c.baseline.toLocaleString()} {c.unit}
                </td>
                <td className="tnum px-3 py-2.5 text-right font-medium">
                  {c.candidate.toLocaleString()} {c.unit}
                </td>
                <td
                  className={cn(
                    'tnum px-4 py-2.5 text-right font-semibold',
                    delta.improved ? 'text-success' : 'text-danger',
                  )}
                >
                  {delta.label}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
