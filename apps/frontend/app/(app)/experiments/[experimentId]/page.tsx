'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { StatusBadge } from '@/components/status-badge';
import { LoadingState, EmptyState } from '@/components/ui/state-feedback';
import { Button } from '@/components/ui/button';
import { PipelineStepper } from '@/components/simulation/pipeline-stepper';
import { ApprovalPanel } from '@/components/simulation/approval-panel';
import { CanaryLivePanel } from '@/components/simulation/canary-live-panel';
import { useToast } from '@/components/app-providers';
import {
  useExperimentDetailQuery,
  useApproveExperimentMutation,
  useRejectExperimentMutation,
} from '@/hooks/use-experiments';
import { useConnectionsQuery } from '@/hooks/use-connections';
import { absoluteTime, deltaPct, relativeTime } from '@/lib/format';

export default function ExperimentDetailPage() {
  const params = useParams<{ experimentId: string }>();
  const { data: exp, isLoading, isError } = useExperimentDetailQuery(params.experimentId);
  const { data: connections = [] } = useConnectionsQuery();
  const { toast } = useToast();

  const approveMutation = useApproveExperimentMutation();
  const rejectMutation = useRejectExperimentMutation();

  const conn = connections.find((c) => c.id === exp?.connectionId);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Experiment detail" />
        <LoadingState message="Loading statistical verification and policy verdict..." />
      </div>
    );
  }

  if (isError || !exp) {
    return (
      <div className="space-y-6">
        <PageHeader title="Experiment not found" />
        <EmptyState
          title="This experiment does not exist"
          description="It may have been archived or deleted."
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/experiments">Back to history</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const completed = exp.outcome === 'COMMIT' || exp.outcome === 'ROLLBACK';
  const canaryRunning = exp.approvalState === 'APPROVED' && exp.outcome === 'IN_PROGRESS';
  const awaitingApproval =
    exp.approvalState === 'PENDING_APPROVAL' && exp.outcome === 'AWAITING_APPROVAL';

  async function handleApprove() {
    if (!exp) return;
    try {
      await approveMutation.mutateAsync({ id: exp.id, notes: 'Approved by Lead DBA' });
      toast({
        kind: 'success',
        title: 'Approval recorded',
        description: 'Canary deployment started. The audit trail has been updated.',
      });
    } catch (err: unknown) {
      toast({
        kind: 'danger',
        title: 'Approval failed',
        description: err instanceof Error ? err.message : 'Could not record approval.',
      });
    }
  }

  async function handleReject() {
    if (!exp) return;
    try {
      await rejectMutation.mutateAsync({ id: exp.id, reason: 'Rejected by operator' });
      toast({
        kind: 'warning',
        title: 'Experiment rejected',
        description: 'No deployment will proceed. The candidate optimization has been marked rejected.',
      });
    } catch (err: unknown) {
      toast({
        kind: 'danger',
        title: 'Rejection failed',
        description: err instanceof Error ? err.message : 'Could not record rejection.',
      });
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb={
          <Link href="/experiments" className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3 w-3" /> Optimization history
          </Link>
        }
        title={`Experiment ${exp.id}`}
        description={`Candidate optimization verification for ${conn?.name || exp.connectionId}.`}
      />

      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={exp.verdict} dot />
        <StatusBadge status={exp.outcome} />
        <span className="text-xs text-muted-foreground">
          Created {relativeTime(exp.createdAtISO)} ({absoluteTime(exp.createdAtISO)})
        </span>
      </div>

      <Card className={exp.verdict === 'VERIFIED' ? 'border-success/40 bg-success/5' : 'border-warning/40 bg-warning/5'}>
        <CardContent className="pt-4">
          <p className="text-sm font-semibold">
            {exp.verdict === 'VERIFIED' ? 'Verification passed' : exp.verdict === 'CONDITIONAL' ? 'Verification needs more evidence' : 'Verification blocked this change'}
          </p>
           <p className="mt-1 text-xs text-muted-foreground">
             {exp.verdict === 'VERIFIED'
               ? exp.approvalState === 'APPROVED' || exp.outcome === 'IN_PROGRESS'
                 ? 'Human approval was recorded. The canary is now being monitored before final commit.'
                 : 'The candidate improved the shadow workload and passed the deterministic safety checks. Production still requires explicit approval.'
              : exp.verdict === 'CONDITIONAL'
                ? 'The candidate may be promising, but the sample is too small for approval. Run more telemetry or replay samples.'
                : exp.outcome === 'ROLLBACK'
                  ? 'This change was deployed and then automatically rolled back after a canary safety threshold was breached.'
                  : 'The candidate was not approved for production. Review the benchmark, confidence interval, regression rate, and failed policy rules below.'}
          </p>
        </CardContent>
      </Card>

      <PipelineStepper currentStage={exp.currentStage} completed={completed} />

      {awaitingApproval && (
        <ApprovalPanel
          verdict={exp.verdict}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}

      {canaryRunning && (
        <CanaryLivePanel
          experimentId={exp.id}
          outcome={exp.outcome === 'COMMIT' || exp.outcome === 'ROLLBACK' ? exp.outcome : 'COMMIT'}
          rollbackReason={exp.rollbackReason}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Baseline vs Candidate Benchmark</CardTitle>
          <CardDescription>
            Bootstrap confidence intervals (N=10,000 resamples). Significance: {exp.significance}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="pb-2 text-left font-medium">Metric</th>
                  <th className="pb-2 text-right font-medium">Baseline</th>
                  <th className="pb-2 text-right font-medium">Candidate</th>
                  <th className="pb-2 text-right font-medium">Delta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {exp.comparisons.map((c) => {
                  const d = deltaPct(c.baseline, c.candidate, c.betterWhenLower);
                  return (
                    <tr key={c.metric}>
                      <td className="py-2.5 font-medium">{c.metric}</td>
                      <td className="py-2.5 text-right font-mono text-muted-foreground">
                        {c.baseline} {c.unit}
                      </td>
                      <td className="py-2.5 text-right font-mono font-medium">
                        {c.candidate} {c.unit}
                      </td>
                      <td className="py-2.5 text-right font-mono">
                        <span className={d.improved ? 'text-success font-medium' : 'text-danger font-medium'}>
                          {d.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
