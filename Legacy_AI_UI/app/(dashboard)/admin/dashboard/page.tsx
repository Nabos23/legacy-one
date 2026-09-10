'use client'

import Link from 'next/link'
import {
  Building2,
  Bot,
  Users,
  UserPlus,
  Settings,
  BarChart3,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatsCard } from '@/components/ui/stats-card'
import { DataTable, type Column } from '@/components/ui/data-table'
import { Badge } from '@/components/ui/badge'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { Separator } from '@/components/ui/separator'
import { IconTile } from '@/components/ui/icon-tile'
import { Reveal } from '@/components/ui/reveal'
import { useOrganizations } from '@/hooks/use-organizations'
import { useAgents } from '@/hooks/use-agents'
import { useUsers } from '@/hooks/use-users'
import { useTracing } from '@/hooks/use-tracing'
import { healthApi, type ServiceHealth } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { useEffect, useState } from 'react'
import type { OrganizationPublic } from '@/types'

export default function AdminDashboardPage() {
  const { data: orgsData } = useOrganizations()
  const { data: agentsData } = useAgents(1)
  const { data: usersData } = useUsers()
  const { data: tracesData } = useTracing(1)

  const [services, setServices] = useState<ServiceHealth[]>([])
  useEffect(() => {
    let active = true
    const run = () => healthApi.check().then(s => { if (active) setServices(s) }).catch(() => {})
    run()
    const id = setInterval(run, 30_000)
    return () => { active = false; clearInterval(id) }
  }, [])
  const allHealthy = services.length > 0 && services.every(s => s.status === 'active')

  const recentTraces = tracesData?.items ?? []
  const latencies = recentTraces.map(t => t.latency).filter((l): l is number => l != null)
  const avgResponse = latencies.length > 0
    ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
    : null
  const avgPct = avgResponse != null ? Math.max(8, Math.min(100, Math.round(100 - avgResponse / 30))) : 0

  const orgColumns: Column<OrganizationPublic>[] = [
    {
      key: 'name',
      header: 'Name',
      render: row => (
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-violet-600 dark:text-violet-400" />
          {row.name}
        </div>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: row => (
        <span className="text-[13px] text-[var(--text-3)]">{row.description ?? '—'}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: () => <Badge variant="success">Active</Badge>,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: row => <span className="text-[13px]">{formatDate(row.created_at)}</span>,
    },
  ]

  const quickActions = [
    { icon: UserPlus, color: 'success', label: 'Invite User', desc: 'Add a new platform user', href: '/admin/users/create' },
    { icon: Building2, color: 'primary', label: 'Create Org', desc: 'Register an organization', href: '/admin/organizations/create' },
    { icon: Settings, color: 'info', label: 'System Settings', desc: 'Configure platform', href: '/admin/settings' },
    { icon: BarChart3, color: 'warning', label: 'Observability', desc: 'View metrics & traces', href: '/admin/tracing' },
  ] as const

  return (
    <>
      <Reveal>
        <PageHeader title="Admin Dashboard" description="System overview and administrative controls" />
      </Reveal>

      <Reveal delay={60} className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        <StatsCard label="Total Organizations" value={orgsData?.total ?? 0} icon={Building2} color="info" href="/admin/organizations" />
        <StatsCard label="Total Users" value={usersData?.total ?? 0} icon={Users} color="primary" href="/admin/users" />
        <StatsCard label="Total Agents" value={agentsData?.total ?? 0} icon={Bot} color="success" href="/admin/agents" />
      </Reveal>

      <Reveal delay={120} className="grid grid-cols-12 gap-5 mb-5">
        <div className="col-span-12 lg:col-span-8 glass rounded-[var(--radius-lg)] overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
            <h3 className="text-[15px] font-semibold">Recent Organizations</h3>
            <Link href="/admin/organizations" className="text-[13px] text-violet-600 dark:text-violet-400 hover:underline">
              View all →
            </Link>
          </div>
          <DataTable columns={orgColumns} data={orgsData?.items ?? []} isLoading={!orgsData} emptyMessage="No organizations yet." />
        </div>

        <div className="col-span-12 lg:col-span-4 glass p-5 rounded-[var(--radius-lg)]">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[15px] font-semibold">System Status</h3>
            <Badge key={services.length === 0 ? 'checking' : allHealthy ? 'ok' : 'degraded'} className="animate-fadeIn" variant={allHealthy ? 'success' : services.length === 0 ? 'neutral' : 'danger'}>
              {services.length === 0 ? 'Checking…' : allHealthy ? 'All Operational' : 'Degraded'}
            </Badge>
          </div>
          <div key={services.length === 0 ? 'checking' : 'resolved'} className="animate-fadeIn space-y-3">
            {services.length === 0 ? (
              <p className="text-[13px] text-[var(--text-3)] py-2">Checking services…</p>
            ) : (
              services.map(s => (
                <div key={s.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StatusIndicator status={s.status === 'down' ? 'error' : s.status} />
                    <span className="text-[13px]">{s.name}</span>
                  </div>
                  <Badge variant={s.status === 'active' ? 'success' : 'danger'}>
                    {s.status === 'active' ? 'Operational' : 'Down'}
                  </Badge>
                </div>
              ))
            )}
          </div>
          <Separator className="my-4" />
          <div>
            <div className="flex justify-between text-[13px] mb-2">
              <span className="text-[var(--text-3)]">Avg Response</span>
              <span className="text-green-600 dark:text-green-400 font-medium">
                {avgResponse != null ? `${avgResponse}ms` : '—'}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-[var(--surface-3)] overflow-hidden">
              <div className="h-full bg-green-500 rounded-full transition-[width] duration-500" style={{ width: `${avgPct}%` }} />
            </div>
          </div>
        </div>
      </Reveal>

      <Reveal delay={180} className="grid grid-cols-12 gap-5">
        <div className="col-span-12 lg:col-span-6 glass rounded-[var(--radius-lg)]">
          <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
            <h3 className="text-[15px] font-semibold">Recent Activity</h3>
            <Link href="/admin/tracing" className="text-[13px] text-violet-600 dark:text-violet-400 hover:underline">
              View traces →
            </Link>
          </div>
          <div className="max-h-[280px] overflow-y-auto p-4 space-y-3">
            {recentTraces.length === 0 ? (
              <p className="text-[13px] text-[var(--text-3)] py-6 text-center">No agent executions yet.</p>
            ) : (
              recentTraces.slice(0, 8).map(trace => (
                <div key={trace.id} className="flex items-start gap-3">
                  <IconTile icon={Zap} color="primary" size="sm" />
                  <div className="min-w-0">
                    <p className="text-[13px] truncate">
                      <span className="font-medium">{trace.agent_name ?? 'Agent'}</span>
                      {trace.input ? ` — ${String(trace.input).slice(0, 50)}` : ' executed'}
                    </p>
                    <p className="text-[11px] text-[var(--text-3)] mt-0.5">{formatDate(trace.timestamp)}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="col-span-12 lg:col-span-6 glass p-5 rounded-[var(--radius-lg)]">
          <h3 className="text-[15px] font-semibold mb-4">Quick Actions</h3>
          <div className="grid grid-cols-2 gap-3">
            {quickActions.map(action => (
              <Link
                key={action.label}
                href={action.href}
                className="glass glass-hover p-4 rounded-[var(--radius-lg)] text-center block"
              >
                <IconTile icon={action.icon} color={action.color} className="mx-auto mb-2" />
                <p className="text-[14px] font-medium">{action.label}</p>
                <p className="text-[12px] text-[var(--text-3)] mt-1">{action.desc}</p>
              </Link>
            ))}
          </div>
        </div>
      </Reveal>
    </>
  )
}
