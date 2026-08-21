'use client'

import * as React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Activity,
  CircleGauge,
  DollarSign,
  FlaskConical,
  LayoutDashboard,
  Plug,
  ShieldCheck,
  Stethoscope,
  TrendingUp,
} from 'lucide-react'
import { useSelectedDb } from '@/components/app-providers'
import { DatabaseSelector } from '@/components/database-selector'
import { connections } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

type NavItem = {
  label: string
  icon: React.ComponentType<{ className?: string }>
  href: (dbId: string) => string
  match: (path: string) => boolean
}

const nav: NavItem[] = [
  {
    label: 'Dashboard',
    icon: LayoutDashboard,
    href: () => '/dashboard',
    match: (p) => p === '/dashboard',
  },
  {
    label: 'Connections',
    icon: Plug,
    href: () => '/connections',
    match: (p) => p.startsWith('/connections'),
  },
  {
    label: 'Monitoring',
    icon: CircleGauge,
    href: () => '/monitoring',
    match: (p) => p.startsWith('/monitoring'),
  },
  {
    label: 'Diagnostics',
    icon: Stethoscope,
    href: () => '/diagnostics',
    match: (p) => p.startsWith('/diagnostics'),
  },
  {
    label: 'Experiments',
    icon: FlaskConical,
    href: () => '/experiments',
    match: (p) => p.startsWith('/experiments'),
  },
  {
    label: 'Forecasts',
    icon: TrendingUp,
    href: (id) => `/forecasts/${id}`,
    match: (p) => p.startsWith('/forecasts'),
  },
  {
    label: 'Cost / ROI',
    icon: DollarSign,
    href: () => '/roi',
    match: (p) => p.startsWith('/roi'),
  },
]

function activeProblemCount() {
  return connections.reduce((sum, c) => sum + c.activeProblems, 0)
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { selectedId } = useSelectedDb()
  const problems = activeProblemCount()

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
        <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/15 text-primary">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold">Aegis</p>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
              AI DBA
            </p>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 p-2">
          {nav.map((item) => {
            const active = item.match(pathname)
            const Icon = item.icon
            return (
              <Link
                key={item.label}
                href={item.href(selectedId)}
                className={cn(
                  'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                  active
                    ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            )
          })}
        </nav>
        <div className="border-t border-sidebar-border p-3">
          <div className="flex items-center gap-2 rounded-md bg-sidebar-accent/40 px-3 py-2">
            <Activity className="h-4 w-4 text-warning" />
            <div className="leading-tight">
              <p className="tnum text-sm font-semibold">{problems}</p>
              <p className="text-[10px] text-muted-foreground">active problems</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-60">
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
          <div className="flex items-center gap-2 lg:hidden">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <span className="text-sm font-semibold">Aegis</span>
          </div>
          <div className="hidden sm:block">
            <DatabaseSelector />
          </div>
          <div className="flex flex-1 items-center justify-end gap-3">
            <Link
              href="/dashboard"
              className="relative flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-accent"
            >
              <Activity className="h-3.5 w-3.5 text-warning" />
              <span className="tnum">{problems}</span>
              <span className="hidden sm:inline">active</span>
              {problems > 0 ? (
                <span className="absolute -right-1 -top-1 flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-danger opacity-70" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-danger" />
                </span>
              ) : null}
            </Link>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
                MC
              </div>
              <div className="hidden leading-tight md:block">
                <p className="text-xs font-medium">Maya Chen</p>
                <p className="text-[10px] text-muted-foreground">SRE · Owner</p>
              </div>
            </div>
          </div>
        </header>

        {/* Mobile db selector */}
        <div className="border-b border-border p-3 sm:hidden">
          <DatabaseSelector />
        </div>

        <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  )
}
