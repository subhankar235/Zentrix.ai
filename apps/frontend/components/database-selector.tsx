'use client'

import * as React from 'react'
import { Check, ChevronsUpDown, Database } from 'lucide-react'
import { connections } from '@/lib/mock-data'
import { useSelectedDb } from '@/components/app-providers'
import { StatusBadge } from '@/components/status-badge'
import { cn } from '@/lib/utils'

export function DatabaseSelector() {
  const { selectedId, setSelectedId } = useSelectedDb()
  const [open, setOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)
  const selected = connections.find((c) => c.id === selectedId) ?? connections[0]

  React.useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full min-w-[220px] items-center gap-2 rounded-md border border-border bg-card px-2.5 py-1.5 text-left text-sm hover:bg-accent"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <Database className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="flex-1 truncate font-mono text-xs">{selected.name}</span>
        <StatusBadge status={selected.health} dot />
        <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      </button>

      {open ? (
        <div
          role="listbox"
          className="absolute left-0 top-full z-40 mt-1 w-72 overflow-hidden rounded-md border border-border bg-popover p-1 shadow-lg"
        >
          <p className="px-2 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Connected databases
          </p>
          {connections.map((c) => (
            <button
              key={c.id}
              type="button"
              role="option"
              aria-selected={c.id === selectedId}
              onClick={() => {
                setSelectedId(c.id)
                setOpen(false)
              }}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm hover:bg-accent',
                c.id === selectedId && 'bg-accent',
              )}
            >
              <Check
                className={cn(
                  'h-3.5 w-3.5 shrink-0',
                  c.id === selectedId ? 'opacity-100 text-primary' : 'opacity-0',
                )}
              />
              <span className="flex-1 truncate">
                <span className="block font-mono text-xs">{c.name}</span>
                <span className="block text-[11px] text-muted-foreground">
                  {c.provider} · {c.region}
                </span>
              </span>
              <StatusBadge status={c.health} dot />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
