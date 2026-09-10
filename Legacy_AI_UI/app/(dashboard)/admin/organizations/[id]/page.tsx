'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Edit2, Building2, Users, Bot, Wrench, Database, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '@/components/ui/page-header'
import { StatsCard } from '@/components/ui/stats-card'
import { DataTable, type Column } from '@/components/ui/data-table'
import { organizationsApi, usersApi, agentsApi, toolsApi, dbConnectionsApi } from '@/lib/api'
import type { OrganizationPublic, UserPublic } from '@/types'
import { formatDate, avatarColor } from '@/lib/utils'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'

export default function OrganizationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [org, setOrg] = useState<OrganizationPublic | null>(null)
  useBreadcrumbLabel(id, org?.name)
  const [users, setUsers] = useState<UserPublic[]>([])
  const [counts, setCounts] = useState({ users: 0, agents: 0, tools: 0, dbConnections: 0 })
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    Promise.all([
      organizationsApi.get(id),
      usersApi.listByOrg(id, 1, 100).catch(() => ({ items: [], total: 0 })),
      agentsApi.listByOrg(id, 1, 1).catch(() => ({ items: [], total: 0 })),
      toolsApi.listByOrg(id, 1, 1).catch(() => ({ items: [], total: 0 })),
      dbConnectionsApi.listByOrg(id, 1, 1).catch(() => ({ items: [], total: 0 })),
    ])
      .then(([o, u, a, t, d]) => {
        setOrg(o)
        setUsers(u.items)
        setCounts({
          users: u.total ?? u.items.length,
          agents: a.total ?? a.items.length,
          tools: t.total ?? t.items.length,
          dbConnections: d.total ?? d.items.length,
        })
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 bg-white/[0.04] rounded w-1/3" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-[100px] bg-white/[0.04] rounded-xl" />)}
        </div>
        <div className="h-[240px] bg-white/[0.04] rounded-xl" />
      </div>
    )
  }

  if (notFound || !org) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--text-3)]">
        <Building2 className="w-10 h-10" />
        <p>Organization not found</p>
        <Link href="/admin/organizations"><Button variant="ghost" size="sm">Back to Organizations</Button></Link>
      </div>
    )
  }

  const userColumns: Column<UserPublic>[] = [
    {
      key: 'name',
      header: 'Name',
      render: row => (
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-full ${avatarColor(row.name)} flex items-center justify-center text-white text-xs font-semibold`}>
            {row.name.split(' ').map(n => n[0]).join('')}
          </div>
          <span className="font-medium">{row.name}</span>
        </div>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      render: row => <span className="text-[13px] text-[var(--text-2)]">{row.email}</span>,
    },
    {
      key: 'role',
      header: 'Role',
      render: row => (
        <Badge variant={row.role.includes('admin') ? 'primary' : 'neutral'} className="capitalize">{row.role}</Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Joined',
      render: row => <span className="text-[13px] text-[var(--text-3)]">{formatDate(row.created_at)}</span>,
    },
  ]

  return (
    <>
      <PageHeader
        title={org.name}
        description={org.description ?? 'Organization details'}
        actions={
          <div className="flex gap-2">
            <Link href="/admin/organizations">
              <Button variant="ghost" size="sm"><ArrowLeft className="w-4 h-4 mr-1" /> Organizations</Button>
            </Link>
            <Link href={`/admin/organizations/${id}/edit`}>
              <Button variant="secondary" size="sm"><Edit2 className="w-4 h-4 mr-1" /> Edit</Button>
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatsCard label="Users" value={counts.users} icon={Users} color="primary" />
        <StatsCard label="Agents" value={counts.agents} icon={Bot} color="info" />
        <StatsCard label="Tools" value={counts.tools} icon={Wrench} color="success" />
        <StatsCard label="DB Connections" value={counts.dbConnections} icon={Database} color="warning" />
      </div>

      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-12 lg:col-span-4 glass p-5 rounded-[var(--radius-lg)] space-y-4 h-fit">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-violet-600 flex items-center justify-center text-white">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <p className="text-[15px] font-semibold">{org.name}</p>
              <Badge variant="success">Active</Badge>
            </div>
          </div>
          {org.description && (
            <div>
              <p className="text-[11px] text-[var(--text-3)] uppercase tracking-wider mb-1">Description</p>
              <p className="text-[13px] text-[var(--text-2)]">{org.description}</p>
            </div>
          )}
          <div className="flex items-center gap-2 text-[12px] text-[var(--text-3)]">
            <Clock className="w-3.5 h-3.5" />
            <span>Created {formatDate(org.created_at)}</span>
          </div>
          <div className="text-[12px] text-[var(--text-3)] font-mono break-all">ID: {org.id}</div>
        </div>

        <div className="col-span-12 lg:col-span-8 glass rounded-[var(--radius-lg)] overflow-hidden h-fit">
          <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
            <h3 className="text-[14px] font-semibold">Members</h3>
            <Badge variant="neutral">{counts.users}</Badge>
          </div>
          <DataTable
            columns={userColumns}
            data={users}
            emptyMessage="No members in this organization yet."
          />
        </div>
      </div>
    </>
  )
}
