'use client'

import * as React from 'react'
import { CheckCircle2, ShieldAlert, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ApprovalPanel({
  verdict,
  onApprove,
  onReject,
}: {
  verdict: 'VERIFIED' | 'CONDITIONAL' | 'REJECTED'
  onApprove: () => void
  onReject: () => void
}) {
  const [confirming, setConfirming] = React.useState(false)

  if (verdict === 'REJECTED') {
    return (
      <div className="rounded-lg border border-danger/30 bg-danger/5 p-4">
        <div className="flex items-start gap-3">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-danger">Not eligible for approval</p>
            <p className="text-xs text-muted-foreground text-pretty">
              The policy engine rejected this candidate. Approval is only available for VERIFIED or
              CONDITIONAL experiments.
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (confirming) {
    return (
      <div className="rounded-lg border border-warning/40 bg-warning/5 p-4">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <div className="min-w-0 flex-1 space-y-2">
            <p className="text-sm font-medium">Confirm production change</p>
            <p className="text-xs text-muted-foreground text-pretty">
              Approving starts a monitored canary deployment against the live database. This action
              is irreversible from this screen and will be permanently recorded in the audit trail.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button size="sm" onClick={onApprove}>
                Confirm approve
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3 rounded-lg border border-border p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium">Human approval required</p>
        {verdict === 'CONDITIONAL' ? (
          <span className="text-[11px] font-medium uppercase tracking-wide text-warning">
            Conditional — review flagged checks
          </span>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground text-pretty">
        This candidate passed automated verification. Your decision (either way) is recorded in the
        audit trail with your identity and an exact timestamp.
      </p>
      <div className="flex gap-2">
        <Button size="sm" onClick={() => setConfirming(true)}>
          Approve deployment
        </Button>
        <Button size="sm" variant="destructive" onClick={onReject}>
          Reject
        </Button>
      </div>
    </div>
  )
}

export function RejectedBanner() {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/40 p-4">
      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
      <div>
        <p className="text-sm font-medium">Rejected — no deployment occurred</p>
        <p className="mt-0.5 text-xs text-muted-foreground text-pretty">
          The candidate was closed without touching production. The full decision trail remains
          available in the audit log below.
        </p>
      </div>
    </div>
  )
}
