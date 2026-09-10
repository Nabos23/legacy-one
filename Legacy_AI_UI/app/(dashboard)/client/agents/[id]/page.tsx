'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Edit2, MessageSquare, Bot, Wrench, Clock, ExternalLink, Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '@/components/ui/page-header'
import { StatsCard } from '@/components/ui/stats-card'
import { DataTable } from '@/components/ui/data-table'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { agentsApi, tracingApi } from '@/lib/api'
import type { AgentPublic, TracePublic, TraceStats } from '@/types'
import { formatDate } from '@/lib/utils'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'
import { Activity, DollarSign, Timer, CheckCircle2 } from 'lucide-react'

function LatencyBadge({ ms }: { ms?: number }) {
  if (!ms) return <span className="text-[var(--text-3)]">—</span>
  const variant = ms < 500 ? 'success' : ms < 2000 ? 'warning' : 'danger'
  return <Badge variant={variant}>{ms}ms</Badge>
}

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [agent, setAgent] = useState<AgentPublic | null>(null)
  useBreadcrumbLabel(id, agent?.name)
  const [stats, setStats] = useState<TraceStats | null>(null)
  const [traces, setTraces] = useState<TracePublic[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      agentsApi.get(id),
      tracingApi.agentStats(id).catch(() => null),
      tracingApi.agentTraces(id).catch(() => ({ items: [] })),
    ])
      .then(([a, s, t]) => {
        setAgent(a)
        setStats(s)
        setTraces(t.items)
      })
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 bg-white/[0.04] rounded w-1/3" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <div key={i} className="h-[100px] bg-white/[0.04] rounded-xl" />)}
        </div>
        <div className="h-[240px] bg-white/[0.04] rounded-xl" />
      </div>
    )
  }

  if (!agent) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--text-3)]">
        <Bot className="w-10 h-10" />
        <p>Agent not found</p>
        <Link href="/client/agents"><Button variant="ghost" size="sm">Back to Agents</Button></Link>
      </div>
    )
  }

  const traceColumns = [
    {
      key: 'timestamp',
      header: 'When',
      render: (row: TracePublic) => <span className="text-[12px] text-[var(--text-3)]">{formatDate(row.timestamp)}</span>,
    },
    {
      key: 'input',
      header: 'Input',
      render: (row: TracePublic) => (
        <span className="text-[12px] font-mono text-[var(--text-3)] truncate max-w-[200px] block">
          {row.input ? String(row.input).slice(0, 60) : '—'}
        </span>
      ),
    },
    {
      key: 'latency',
      header: 'Latency',
      render: (row: TracePublic) => <LatencyBadge ms={row.latency} />,
    },

    {
      key: 'actions',
      header: '',
      render: () => (
        <Button variant="ghost" size="xs" onClick={() => router.push('/client/tracing')}>
          <Eye className="w-3.5 h-3.5" />
        </Button>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title={agent.name}
        description={agent.description ?? agent.user_description}
        actions={
          <div className="flex gap-2">
            <Link href="/client/agents">
              <Button variant="ghost" size="sm"><ArrowLeft className="w-4 h-4 mr-1" /> Agents</Button>
            </Link>
            <Link href={`/client/agents/${id}/edit`}>
              <Button variant="secondary" size="sm"><Edit2 className="w-4 h-4 mr-1" /> Edit</Button>
            </Link>
            <Button variant="primary" size="sm" onClick={() => router.push(`/client/playground?agent=${id}`)}>
              <MessageSquare className="w-4 h-4 mr-1" /> Chat
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-12 gap-5 mb-6">
        {/* Agent info */}
        <div className="col-span-12 lg:col-span-4 glass p-5 rounded-[var(--radius-lg)] space-y-4">
          <div className="flex items-center gap-3">
            <AgentAvatar
              name={agent.name}
              avatarType={agent.avatar_type}
              avatarValue={agent.avatar_value}
              avatarUrl={agent.avatar_url}
              size="md"
            />
            <div>
              <p className="text-[15px] font-semibold">{agent.name}</p>
              <StatusIndicator status="active" pulse label="Active" />
            </div>
          </div>
          {agent.prompt && (
            <div>
              <p className="text-[11px] text-[var(--text-3)] uppercase tracking-wider mb-1">System Prompt</p>
              <p className="text-[12px] font-mono text-[var(--text-2)] line-clamp-4 bg-[var(--surface-3)] p-3 rounded-lg">
                {agent.prompt}
              </p>
            </div>
          )}
          {agent.guardrails && (
            <div className="flex items-center gap-2">
              <Badge variant="success">Guardrails on</Badge>
            </div>
          )}
          <div className="flex items-center gap-2 text-[12px] text-[var(--text-3)]">
            <Wrench className="w-3.5 h-3.5" />
            <span>{agent.tool_ids?.length ?? 0} tools attached</span>
          </div>
          <div className="flex items-center gap-2 text-[12px] text-[var(--text-3)]">
            <Clock className="w-3.5 h-3.5" />
            <span>Created {formatDate(agent.created_at)}</span>
          </div>
        </div>

        {/* Stats */}
        <div className="col-span-12 lg:col-span-8 grid grid-cols-1 sm:grid-cols-2 gap-4 content-start">
          <StatsCard label="Total Executions" value={stats?.total_traces ?? 0} icon={Activity} color="primary" />
          <StatsCard label="Total Cost" value={stats?.total_cost != null ? `$${stats.total_cost.toFixed(4)}` : '$0.0000'} icon={DollarSign} color="warning" />
          <StatsCard label="Input Tokens" value={stats?.total_input_tokens ?? '—'} icon={Timer} color="info" />
          <StatsCard label="Output Tokens" value={stats?.total_output_tokens ?? '—'} icon={CheckCircle2} color="success" />
        </div>
      </div>

      {/* Recent traces */}
      <div className="glass rounded-[var(--radius-lg)] overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <h3 className="text-[14px] font-semibold">Recent Executions</h3>
          <Link href="/client/tracing" className="text-[12px] text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 flex items-center gap-1">
            View all <ExternalLink className="w-3 h-3" />
          </Link>
        </div>
        <DataTable
          columns={traceColumns}
          data={traces}
          emptyMessage="No executions yet. Chat with this agent to generate traces."
        />
      </div>
    </>
  )
}
