'use client'

import * as React from 'react'
import { Check, Loader2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useToast } from '@/components/app-providers'
import { cn } from '@/lib/utils'

type StepState = 'pending' | 'running' | 'pass' | 'fail'

const STEPS = [
  { key: 'reach', label: 'Reachability', detail: 'Opening TCP connection to host:port' },
  { key: 'creds', label: 'Credentials', detail: 'Authenticating role and database' },
  { key: 'ext', label: 'Required extension', detail: 'Checking pg_stat_statements is enabled' },
  { key: 'perms', label: 'Permission level', detail: 'Verifying read-only monitoring role' },
] as const

export function AddConnectionDialog({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const { toast } = useToast()
  const [mode, setMode] = React.useState<'string' | 'fields'>('string')
  const [testing, setTesting] = React.useState(false)
  const [states, setStates] = React.useState<Record<string, StepState>>({})
  const timers = React.useRef<ReturnType<typeof setTimeout>[]>([])

  React.useEffect(() => {
    return () => timers.current.forEach(clearTimeout)
  }, [])

  if (!open) return null

  function runTest() {
    timers.current.forEach(clearTimeout)
    timers.current = []
    setTesting(true)
    setStates({})
    STEPS.forEach((step, i) => {
      timers.current.push(
        setTimeout(() => {
          setStates((prev) => ({ ...prev, [step.key]: 'running' }))
        }, i * 900),
      )
      timers.current.push(
        setTimeout(() => {
          setStates((prev) => ({ ...prev, [step.key]: 'pass' }))
          if (i === STEPS.length - 1) {
            setTesting(false)
            toast({
              kind: 'success',
              title: 'Connection test passed',
              description: 'All checks succeeded. The database is ready to monitor.',
            })
          }
        }, i * 900 + 700),
      )
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-background/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg overflow-hidden rounded-xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold">Add database connection</h2>
            <p className="text-xs text-muted-foreground">
              We connect with a read-only role and never store your data.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-accent"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          <div className="flex gap-1 rounded-md border border-border p-0.5 text-xs">
            {(['string', 'fields'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={cn(
                  'flex-1 rounded px-2 py-1.5 transition-colors',
                  mode === m ? 'bg-accent font-medium' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {m === 'string' ? 'Connection string' : 'Individual fields'}
              </button>
            ))}
          </div>

          {mode === 'string' ? (
            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-muted-foreground">Connection string</span>
              <input
                defaultValue="postgres://readonly@ep-new-db-9921.us-east-2.aws.neon.tech/main?sslmode=require"
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {[
                ['Host', 'ep-new-db-9921.us-east-2.aws.neon.tech'],
                ['Port', '5432'],
                ['Database', 'main'],
                ['User', 'readonly'],
                ['Password', '••••••••••'],
              ].map(([label, ph]) => (
                <label key={label} className={cn('space-y-1.5', label === 'Host' && 'col-span-2')}>
                  <span className="text-xs font-medium text-muted-foreground">{label}</span>
                  <input
                    defaultValue={ph}
                    type={label === 'Password' ? 'password' : 'text'}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
                  />
                </label>
              ))}
              <label className="col-span-2 flex items-center gap-2 text-xs">
                <input type="checkbox" defaultChecked className="accent-primary" />
                Require SSL (sslmode=require)
              </label>
            </div>
          )}

          <div className="rounded-lg border border-border bg-background/40 p-3">
            <ol className="space-y-2.5">
              {STEPS.map((step) => {
                const s = states[step.key] ?? 'pending'
                return (
                  <li key={step.key} className="flex items-center gap-3">
                    <span
                      className={cn(
                        'flex h-5 w-5 items-center justify-center rounded-full border text-xs',
                        s === 'pass' && 'border-success/40 bg-success/15 text-success',
                        s === 'fail' && 'border-danger/40 bg-danger/15 text-danger',
                        s === 'running' && 'border-info/40 bg-info/15 text-info',
                        s === 'pending' && 'border-border text-muted-foreground',
                      )}
                    >
                      {s === 'running' ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : s === 'pass' ? (
                        <Check className="h-3 w-3" />
                      ) : s === 'fail' ? (
                        <X className="h-3 w-3" />
                      ) : (
                        <span className="h-1.5 w-1.5 rounded-full bg-current" />
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-medium">{step.label}</p>
                      <p className="text-[11px] text-muted-foreground">{step.detail}</p>
                    </div>
                  </li>
                )
              })}
            </ol>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={runTest} disabled={testing}>
            {testing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Testing…
              </>
            ) : (
              'Test connection'
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
