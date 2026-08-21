'use client'

import * as React from 'react'
import { connections } from '@/lib/mock-data'

// ---------------- Selected database context ----------------

type DbContextValue = {
  selectedId: string
  setSelectedId: (id: string) => void
}

const DbContext = React.createContext<DbContextValue | null>(null)

export function useSelectedDb() {
  const ctx = React.useContext(DbContext)
  if (!ctx) throw new Error('useSelectedDb must be used within AppProviders')
  return ctx
}

// ---------------- Toast context ----------------

export type ToastKind = 'success' | 'info' | 'warning' | 'danger'
export type Toast = { id: number; title: string; description?: string; kind: ToastKind }

type ToastContextValue = {
  toast: (t: Omit<Toast, 'id'>) => void
}

const ToastContext = React.createContext<ToastContextValue | null>(null)

export function useToast() {
  const ctx = React.useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within AppProviders')
  return ctx
}

const kindStyles: Record<ToastKind, string> = {
  success: 'border-success/40 [&_[data-accent]]:bg-success',
  info: 'border-info/40 [&_[data-accent]]:bg-info',
  warning: 'border-warning/40 [&_[data-accent]]:bg-warning',
  danger: 'border-danger/40 [&_[data-accent]]:bg-danger',
}

function ToastViewport({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className={`pointer-events-auto flex items-stretch gap-3 overflow-hidden rounded-lg border bg-popover p-3 pl-0 shadow-lg animate-in slide-in-from-bottom-2 fade-in ${kindStyles[t.kind]}`}
        >
          <div data-accent className="w-1 shrink-0 rounded-full" />
          <div className="min-w-0 py-0.5">
            <p className="text-sm font-medium text-popover-foreground">{t.title}</p>
            {t.description ? (
              <p className="mt-0.5 text-xs text-muted-foreground">{t.description}</p>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  )
}

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [selectedId, setSelectedId] = React.useState(connections[0].id)
  const [toasts, setToasts] = React.useState<Toast[]>([])

  const toast = React.useCallback((t: Omit<Toast, 'id'>) => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { ...t, id }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((x) => x.id !== id))
    }, 4000)
  }, [])

  const dbValue = React.useMemo(() => ({ selectedId, setSelectedId }), [selectedId])
  const toastValue = React.useMemo(() => ({ toast }), [toast])

  return (
    <DbContext.Provider value={dbValue}>
      <ToastContext.Provider value={toastValue}>
        {children}
        <ToastViewport toasts={toasts} />
      </ToastContext.Provider>
    </DbContext.Provider>
  )
}
