'use client'

import { DashboardLayout } from '@/components/layout/dashboard-layout'
import { SidebarVariantProvider } from '@/contexts/sidebar-context'

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <SidebarVariantProvider variant="client">
      <DashboardLayout variant="client">{children}</DashboardLayout>
    </SidebarVariantProvider>
  )
}
