'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Edit2, Wrench, Clock, Bot, Hash, Building2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '@/components/ui/page-header'
import { toolsApi } from '@/lib/api'
import type { ToolPublic } from '@/types'
import { formatDate } from '@/lib/utils'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'

export default function ToolDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [tool, setTool] = useState<ToolPublic | null>(null)
  useBreadcrumbLabel(id, tool?.name || tool?.user_description)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    toolsApi.get(id)
      .then(setTool)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 bg-white/[0.04] rounded w-1/3" />
        <div className="h-[240px] bg-white/[0.04] rounded-xl" />
      </div>
    )
  }

  if (notFound || !tool) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--text-3)]">
        <Wrench className="w-10 h-10" />
        <p>Tool not found</p>
        <Link href="/client/tools"><Button variant="ghost" size="sm">Back to Tools</Button></Link>
      </div>
    )
  }

  const displayName = tool.name ?? (tool.user_description || tool.tool_id)

  return (
    <>
      <PageHeader
        title={displayName}
        description={tool.user_description ?? 'Tool details'}
        actions={
          <div className="flex gap-2">
            <Link href="/client/tools">
              <Button variant="ghost" size="sm"><ArrowLeft className="w-4 h-4 mr-1" /> Tools</Button>
            </Link>
            <Link href={`/client/tools/${id}/edit`}>
              <Button variant="secondary" size="sm"><Edit2 className="w-4 h-4 mr-1" /> Edit</Button>
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-12 lg:col-span-5 glass p-5 rounded-[var(--radius-lg)] space-y-4 h-fit">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-violet-600 flex items-center justify-center text-white">
              <Wrench className="w-6 h-6" />
            </div>
            <div>
              <p className="text-[15px] font-semibold">{displayName}</p>
              <Badge variant="success">Active</Badge>
            </div>
          </div>

          {tool.user_description && (
            <div>
              <p className="text-[11px] text-[var(--text-3)] uppercase tracking-wider mb-1">Description</p>
              <p className="text-[13px] text-[var(--text-2)]">{tool.user_description}</p>
            </div>
          )}

          <div className="flex items-center gap-2 text-[12px] text-[var(--text-3)]">
            <Clock className="w-3.5 h-3.5" />
            <span>Created {formatDate(tool.created_at)}</span>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-7 glass p-5 rounded-[var(--radius-lg)] space-y-4 h-fit">
          <h3 className="text-[14px] font-semibold">Configuration</h3>

          <div className="flex items-start gap-3">
            <Hash className="w-4 h-4 text-[var(--text-3)] mt-0.5" />
            <div className="min-w-0">
              <p className="text-[11px] text-[var(--text-3)] uppercase tracking-wider">Registry ID</p>
              <p className="text-[13px] font-mono text-[var(--text-2)] break-all">{tool.tool_id}</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <Bot className="w-4 h-4 text-[var(--text-3)] mt-0.5" />
            <div className="min-w-0">
              <p className="text-[11px] text-[var(--text-3)] uppercase tracking-wider">Linked Agent</p>
              <p className="text-[13px] text-[var(--text-2)] break-all">{tool.agent_name || tool.agent_id || '—'}</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <Building2 className="w-4 h-4 text-[var(--text-3)] mt-0.5" />
            <div className="min-w-0">
              <p className="text-[11px] text-[var(--text-3)] uppercase tracking-wider">Organization</p>
              <p className="text-[13px] font-mono text-[var(--text-2)] break-all">{tool.organization_id}</p>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
