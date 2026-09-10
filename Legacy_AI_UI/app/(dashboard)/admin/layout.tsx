'use client'

import { DashboardLayout } from '@/components/layout/dashboard-layout'
import { SidebarVariantProvider } from '@/contexts/sidebar-context'

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <SidebarVariantProvider variant="admin">
      <DashboardLayout variant="admin">{children}</DashboardLayout>
    </SidebarVariantProvider>
  )
}
