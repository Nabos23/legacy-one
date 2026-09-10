'use client'

import { WidgetCreateForm } from '@/components/widget/WidgetCreateForm'

export default function AdminCreateWidgetPage() {
  return <WidgetCreateForm basePath="/admin/widgets" allowOrgSelect />
}
