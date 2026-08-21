import { AppProviders } from '@/components/app-providers'
import { AppShell } from '@/components/app-shell'

export default function AppGroupLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AppProviders>
      <AppShell>{children}</AppShell>
    </AppProviders>
  )
}
