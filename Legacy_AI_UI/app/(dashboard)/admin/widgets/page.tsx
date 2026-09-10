'use client'

import { WidgetsListView } from '@/components/widget/WidgetsListView'

export default function AdminWidgetsPage() {
  return <WidgetsListView basePath="/admin/widgets" showOrgFilter />
}
