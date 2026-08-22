'use client';

import * as React from 'react';
import { Check, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/app-providers';
import { useCreateConnectionMutation, useTestNewConnectionMutation } from '@/hooks/use-connections';
import type { CreateConnectionPayload } from '@/lib/api/connections';
import { cn } from '@/lib/utils';

type StepState = 'pending' | 'running' | 'pass' | 'fail';

const STEPS = [
  { key: 'reach', label: 'Reachability', detail: 'Opening TCP connection to host:port' },
  { key: 'creds', label: 'Credentials', detail: 'Authenticating role and database' },
  { key: 'ext', label: 'Required extension', detail: 'Checking pg_stat_statements is enabled' },
  { key: 'perms', label: 'Permission level', detail: 'Verifying read-only monitoring role' },
] as const;

export function AddConnectionDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const [mode, setMode] = React.useState<'string' | 'fields'>('string');
  const [connectionString, setConnectionString] = React.useState('');
  const [fields, setFields] = React.useState({
    name: '',
    host: '',
    port: 5432,
    database: '',
    username: '',
    password: '',
    ssl: true,
  });

  const [testing, setTesting] = React.useState(false);
  const [states, setStates] = React.useState<Record<string, StepState>>({});

  const createMutation = useCreateConnectionMutation();
  const testMutation = useTestNewConnectionMutation();

  if (!open) return null;

  function buildPayload(): CreateConnectionPayload {
    if (mode === 'string') {
      if (!connectionString.trim()) throw new Error('Enter a PostgreSQL connection string.');

      let parsed: URL;
      try {
        parsed = new URL(connectionString.trim());
      } catch {
        throw new Error('Enter a valid PostgreSQL connection string.');
      }

      const databaseName = decodeURIComponent(parsed.pathname.replace(/^\//, ''));
      if (!parsed.hostname || !databaseName || !parsed.username) {
        throw new Error('The connection string must include host, database, and username.');
      }

      return {
        name: fields.name.trim() || databaseName,
        provider: 'postgresql',
        host: parsed.hostname,
        port: Number(parsed.port || 5432),
        database_name: databaseName,
        username: decodeURIComponent(parsed.username),
        password: parsed.password ? decodeURIComponent(parsed.password) : undefined,
        ssl_mode: parsed.searchParams.get('sslmode') || 'require',
        connection_string: connectionString.trim(),
      };
    }

    if (!fields.name.trim() || !fields.host.trim() || !fields.database.trim() || !fields.username.trim()) {
      throw new Error('Name, host, database, and username are required.');
    }

    return {
      name: fields.name.trim(),
      provider: 'postgresql',
      host: fields.host.trim(),
      port: fields.port,
      database_name: fields.database.trim(),
      username: fields.username.trim(),
      password: fields.password || undefined,
      ssl_mode: fields.ssl ? 'require' : 'prefer',
    };
  }

  async function runTestAndSave() {
    setTesting(true);
    setStates(Object.fromEntries(STEPS.map((step) => [step.key, 'running'])));

    try {
      const payload = buildPayload();
      const result = await testMutation.mutateAsync(payload);
      const nextStates: Record<string, StepState> = {
        reach: result.reachability ? 'pass' : 'fail',
        creds: result.credentials ? 'pass' : 'fail',
        ext: result.pgStatStatements ? 'pass' : 'fail',
        perms: result.readOnlyRole ? 'pass' : 'fail',
      };
      setStates(nextStates);

      if (!result.success) {
        throw new Error(result.message || 'The database did not pass the required checks.');
      }

      await createMutation.mutateAsync(payload);
      setTesting(false);
      toast({
        kind: 'success',
        title: 'Database connection verified and registered',
        description: !result.pgStatStatements
          ? 'Connected, but enable pg_stat_statements to collect query-level telemetry.'
          : result.readOnlyRole
            ? 'Monitoring will read live PostgreSQL telemetry from this connection.'
            : 'Live telemetry is available, but use a dedicated read-only role before production use.',
      });
      onClose();
    } catch (err: unknown) {
      setTesting(false);
      setStates(Object.fromEntries(STEPS.map((step) => [step.key, 'fail'])));
      toast({
        kind: 'danger',
        title: 'Connection test failed',
        description: err instanceof Error ? err.message : 'Could not verify database credentials.',
      });
    }
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
                  mode === m ? 'bg-accent font-medium' : 'text-muted-foreground hover:text-foreground'
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
                value={connectionString}
                onChange={(e) => setConnectionString(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <label className="col-span-2 space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">Connection Name</span>
                <input
                  value={fields.name}
                  onChange={(e) => setFields((f) => ({ ...f, name: e.target.value }))}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
                />
              </label>
              <label className="col-span-2 space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">Host</span>
                <input
                  value={fields.host}
                  onChange={(e) => setFields((f) => ({ ...f, host: e.target.value }))}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
                />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">Port</span>
                <input
                  type="number"
                  value={fields.port}
                  onChange={(e) => setFields((f) => ({ ...f, port: parseInt(e.target.value) || 5432 }))}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
                />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">Database</span>
                <input
                  value={fields.database}
                  onChange={(e) => setFields((f) => ({ ...f, database: e.target.value }))}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
                />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">User</span>
                <input
                  value={fields.username}
                  onChange={(e) => setFields((f) => ({ ...f, username: e.target.value }))}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
                />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">Password</span>
                <input
                  type="password"
                  value={fields.password}
                  onChange={(e) => setFields((f) => ({ ...f, password: e.target.value }))}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
                />
              </label>
              <label className="col-span-2 flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={fields.ssl}
                  onChange={(e) => setFields((f) => ({ ...f, ssl: e.target.checked }))}
                  className="accent-primary"
                />
                Require SSL (sslmode=require)
              </label>
            </div>
          )}

          <div className="rounded-lg border border-border bg-background/40 p-3">
            <ol className="space-y-2.5">
              {STEPS.map((step) => {
                const s = states[step.key] ?? 'pending';
                return (
                  <li key={step.key} className="flex items-center gap-3">
                    <span
                      className={cn(
                        'flex h-5 w-5 items-center justify-center rounded-full border text-xs',
                        s === 'pass' && 'border-success/40 bg-success/15 text-success',
                        s === 'fail' && 'border-danger/40 bg-danger/15 text-danger',
                        s === 'running' && 'border-info/40 bg-info/15 text-info',
                        s === 'pending' && 'border-border text-muted-foreground'
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
                );
              })}
            </ol>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={runTestAndSave} disabled={testing}>
            {testing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Testing &amp; Registering…
              </>
            ) : (
              'Verify & Connect'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
