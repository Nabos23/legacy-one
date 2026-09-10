'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  Building2,
  ChevronDown,
  DollarSign,
  Timer,
  Eye,
  MessageSquare,
  X,
  ListFilter,
  Zap,
  CheckCircle,
  Download,
  Gauge,
  Layers,
  Users as UsersIcon,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useRouter } from 'next/navigation'
import { PageHeader } from '@/components/ui/page-header'
import { StatsCard } from '@/components/ui/stats-card'
import { DataTable } from '@/components/ui/data-table'
import { Pagination } from '@/components/ui/pagination'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { Tabs } from '@/components/ui/tabs'
import { useAuth } from '@/contexts/auth-context'
import { useRecentTraces, useTraceList, useTraceStats } from '@/hooks/use-tracing'
import { useSessions } from '@/hooks/use-sessions'
import { useAgents } from '@/hooks/use-agents'
import { useOrganizations } from '@/hooks/use-organizations'
import { useUsers } from '@/hooks/use-users'
import { tracingApi } from '@/lib/api'
import type { TracePublic, TraceDetail, TraceStats, SessionPublic, Page } from '@/types'
import { cn, formatDate, isOrgManagerOrAbove } from '@/lib/utils'

type TraceStatsUserBreakdown = TraceStats['user_breakdown'][number]

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const CHART_COLORS = ['#7c3aed', '#06b6d4', '#22c55e', '#f59e0b', '#52525b']
const CHART_TOOLTIP_STYLE = {
  background: 'var(--surface-2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
}

function fmtTokens(n?: number) {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(0)}K`
  return String(n)
}

function heatColor(value: number, max: number) {
  if (value === 0) return 'rgba(124,58,237,0.05)'
  const ratio = max > 0 ? value / max : 0
  if (ratio < 0.33) return '#7c3aed40'
  if (ratio < 0.66) return '#7c3aed90'
  return '#7c3aedE6'
}

function formatValue(v: unknown) {
  if (v == null) return ''
  return typeof v === 'string' ? v : JSON.stringify(v, null, 2)
}

const TEXT_FIELD_KEYS = ['response', 'output', 'answer', 'message', 'content', 'text']

/** Pull the human-readable text out of an agent output payload (a plain
 * string, or an object like `{ response, agent }`), keeping any other
 * short string fields (e.g. `agent`) around to show as badges. Returns
 * null when the value isn't shaped like readable text, so callers can
 * fall back to a raw JSON dump. */
function extractDisplayText(value: unknown): { text: string; extra: [string, string][] } | null {
  if (typeof value === 'string' && value.trim()) {
    return { text: value, extra: [] }
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>
    const textKey = TEXT_FIELD_KEYS.find(k => typeof obj[k] === 'string' && (obj[k] as string).trim())
    if (textKey) {
      const extra = Object.entries(obj).filter(
        (entry): entry is [string, string] => entry[0] !== textKey && typeof entry[1] === 'string' && entry[1].trim().length > 0,
      )
      return { text: obj[textKey] as string, extra }
    }
  }
  return null
}

/** Strip markdown decoration (bold/italic/inline-code/headings) from agent
 * text while preserving real line breaks, so the trace detail sheet reads
 * like plain prose instead of raw markdown source. */
function cleanMarkdownText(text: string): string {
  return text
    .replace(/```([\s\S]*?)```/g, '$1')
    .replace(/(\*\*|__)([^*_]+?)\1/g, '$2')
    .replace(/\*([^\n*]+)\*/g, '$1')
    .replace(/`([^`\n]+)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .trim()
}

function LatencyBadge({ ms }: { ms?: number }) {
  if (!ms) return <span className="text-[var(--text-3)]">—</span>
  const variant = ms < 500 ? 'success' : ms < 2000 ? 'warning' : 'danger'
  return <Badge variant={variant}>{ms}ms</Badge>
}

function TraceDetailSheet({ trace: rawTrace, onClose }: { trace: TraceDetail | null; onClose: () => void }) {
  const [shown, setShown] = useState<TraceDetail | null>(rawTrace)
  const [closing, setClosing] = useState(false)
  useEffect(() => {
    if (rawTrace) {
      setShown(rawTrace)
      setClosing(false)
      return
    }
    if (!shown) return
    setClosing(true)
    const t = setTimeout(() => {
      setShown(null)
      setClosing(false)
    }, 220)
    return () => clearTimeout(t)
  }, [rawTrace, shown])

  if (!shown) return null
  const trace = shown
  return (
    <>
      <div
        className={cn('animate-fadeIn fixed inset-0 bg-black/40 z-40', closing && '[animation-direction:reverse]')}
        onClick={onClose}
      />
      <div
        className={cn(
          'animate-slideInRight fixed right-0 top-0 h-screen w-full max-w-[560px] bg-[var(--surface)] border-l border-[var(--border)] z-50 flex flex-col shadow-2xl overflow-y-auto',
          closing && '[animation-direction:reverse]',
        )}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)] sticky top-0 bg-[var(--surface)] z-10">
          <div>
            <span className="font-mono text-[11px] text-[var(--text-3)]">{trace.id}</span>
            <p className="text-[13px] text-[var(--text-3)] mt-0.5">{formatDate(trace.timestamp)}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>✕</Button>
        </div>

        <div className="p-5 space-y-5">
          <div className="flex flex-wrap gap-2">
            {trace.agent_name && <Badge variant="neutral" className="font-mono text-[10px]">agent: {trace.agent_name}</Badge>}
            {trace.session_id && <Badge variant="neutral" className="font-mono text-[10px]">session: {trace.session_id.slice(-8)}</Badge>}
          </div>

          <div className="flex gap-3 flex-wrap">
            <LatencyBadge ms={trace.latency} />
            {trace.total_cost != null && <Badge variant="neutral">${trace.total_cost.toFixed(4)}</Badge>}
          </div>

          {trace.input != null && (
            <div>
              <p className="text-[12px] font-medium mb-1.5 text-[var(--text-2)]">Input</p>
              <pre className="bg-[var(--surface-3)] font-mono text-[12px] p-4 rounded-[10px] max-h-[120px] overflow-y-auto whitespace-pre-wrap break-all text-[var(--text-1)]">
                {formatValue(trace.input)}
              </pre>
            </div>
          )}

          {trace.output != null && (() => {
            const display = extractDisplayText(trace.output)
            if (!display) {
              return (
                <div>
                  <p className="text-[12px] font-medium mb-1.5 text-[var(--text-2)]">Output</p>
                  <pre className="bg-[var(--surface-3)] font-mono text-[12px] p-4 rounded-[10px] max-h-[160px] overflow-y-auto whitespace-pre-wrap break-all text-[var(--text-1)]">
                    {formatValue(trace.output)}
                  </pre>
                </div>
              )
            }
            return (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-[12px] font-medium text-[var(--text-2)]">Output</p>
                  {display.extra.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {display.extra.map(([k, v]) => (
                        <Badge key={k} variant="neutral" className="text-[10px]">{k}: {v}</Badge>
                      ))}
                    </div>
                  )}
                </div>
                <div className="bg-[var(--surface-3)] text-[13px] leading-relaxed p-4 rounded-[10px] max-h-[260px] overflow-y-auto whitespace-pre-wrap text-[var(--text-1)]">
                  {cleanMarkdownText(display.text)}
                </div>
              </div>
            )
          })()}

          {trace.observations.length > 0 && (() => {
            const obs = trace.observations
            const maxLat = Math.max(1, ...obs.map(o => o.latency ?? 0))
            const byModel = new Map<string, { count: number; cost: number }>()
            obs.forEach(o => {
              if (!o.model) return
              const m = byModel.get(o.model) ?? { count: 0, cost: 0 }
              m.count += 1
              m.cost += o.calculated_total_cost ?? 0
              byModel.set(o.model, m)
            })
            const models = [...byModel.entries()]
            return (
              <div className="space-y-4">
                {models.length > 0 && (
                  <div>
                    <p className="text-[12px] font-medium mb-2 text-[var(--text-2)]">Models</p>
                    <div className="flex flex-wrap gap-2">
                      {models.map(([model, m]) => (
                        <div key={model} className="flex items-center gap-1.5 bg-[var(--surface-3)] rounded-lg px-2.5 py-1.5">
                          <Layers className="w-3.5 h-3.5 text-violet-500" />
                          <span className="text-[12px] font-medium">{model}</span>
                          <span className="text-[11px] text-[var(--text-3)]">×{m.count}</span>
                          {m.cost > 0 && <span className="text-[11px] text-[var(--text-3)]">· ${m.cost.toFixed(4)}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <p className="text-[12px] font-medium mb-2 text-[var(--text-2)]">Timeline</p>
                  <div className="space-y-1.5">
                    {obs.map(o => {
                      const lat = o.latency ?? 0
                      const pct = Math.max(2, Math.round((lat / maxLat) * 100))
                      return (
                        <div key={o.id} className="flex items-center gap-2">
                          <span className="text-[11px] text-[var(--text-3)] w-28 truncate shrink-0" title={o.name ?? o.type}>
                            {o.name ?? o.type}
                          </span>
                          <div className="flex-1 h-4 rounded bg-[var(--surface-3)] overflow-hidden">
                            <div className="h-full rounded bg-violet-500/70" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-[10px] font-mono text-[var(--text-3)] w-14 text-right shrink-0">
                            {lat ? `${lat}ms` : '—'}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            )
          })()}

          {trace.observations.length > 0 && (
            <div>
              <p className="text-[12px] font-medium mb-3 text-[var(--text-2)]">Observations ({trace.observations.length})</p>
              <div className="space-y-3">
                {trace.observations.map(obs => {
                  const usageEntries = obs.usage
                    ? Object.entries(obs.usage).filter(([, v]) => v != null)
                    : []
                  return (
                    <div key={obs.id} className="border border-[var(--border)] rounded-[10px] p-3">
                      <div className="flex items-start gap-3">
                        <Badge
                          variant={obs.type === 'generation' ? 'primary' : obs.type === 'span' ? 'info' : 'neutral'}
                          className="text-[10px] mt-0.5 shrink-0"
                        >
                          {obs.type}
                        </Badge>
                        <div className="flex-1 min-w-0">
                          <p className="text-[13px] font-medium truncate">{obs.name ?? obs.type}</p>
                          {obs.model && <p className="text-[11px] text-[var(--text-3)]">{obs.model}</p>}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {obs.calculated_total_cost != null && (
                            <span className="text-[11px] text-[var(--text-3)]">${obs.calculated_total_cost.toFixed(4)}</span>
                          )}
                          {obs.latency != null && <LatencyBadge ms={obs.latency} />}
                        </div>
                      </div>

                      {usageEntries.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2 pl-1">
                          {usageEntries.map(([k, v]) => (
                            <span key={k} className="text-[10px] font-mono text-[var(--text-3)] bg-[var(--surface-3)] rounded px-1.5 py-0.5">
                              {k}: {String(v)}
                            </span>
                          ))}
                        </div>
                      )}

                      {obs.input != null && (
                        <pre className="bg-[var(--surface-3)] font-mono text-[11px] p-2.5 mt-2 rounded-lg max-h-[90px] overflow-y-auto whitespace-pre-wrap break-all text-[var(--text-2)]">
                          {formatValue(obs.input).slice(0, 600)}
                        </pre>
                      )}
                      {obs.output != null && (
                        <pre className="bg-[var(--surface-3)] font-mono text-[11px] p-2.5 mt-2 rounded-lg max-h-[90px] overflow-y-auto whitespace-pre-wrap break-all text-[var(--text-2)]">
                          {formatValue(obs.output).slice(0, 600)}
                        </pre>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

export function TracingView({ basePath }: { basePath: '/client' | '/admin' }) {
  const router = useRouter()
  const { permissions, user } = useAuth()
  const isSuperAdmin = basePath === '/admin' && permissions?.is_super_admin
  const canViewOrgUsage = isOrgManagerOrAbove(user?.role) || Boolean(permissions?.is_super_admin)
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null)
  const [orgDropdownOpen, setOrgDropdownOpen] = useState(false)
  const orgDropdownRef = useRef<HTMLDivElement>(null)
  const { data: orgsData } = useOrganizations(1, undefined, 1000)
  const organizations = orgsData?.items ?? []
  const selectedOrg = selectedOrgId ? organizations.find(o => o.id === selectedOrgId) : null
  const effectiveOrgId = isSuperAdmin ? (selectedOrgId ?? undefined) : undefined

  useEffect(() => {
    if (!orgDropdownOpen) return
    const handler = (e: MouseEvent) => {
      if (orgDropdownRef.current && !orgDropdownRef.current.contains(e.target as Node)) {
        setOrgDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [orgDropdownOpen])

  // tab: overview (charts) | traces | sessions | users (org_admin/org_manager/super_admin only)
  const [tab, setTab] = useState<'overview' | 'traces' | 'sessions' | 'users'>('overview')
  const [tracePage, setTracePage] = useState(1)
  const [agentFilter, setAgentFilter] = useState('')
  const [sessionFilter, setSessionFilter] = useState<string | null>(null)
  const [userFilter, setUserFilter] = useState<string | null>(null)
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const { stats } = useTraceStats(undefined, effectiveOrgId)
  const { data: sessionsData, loading: sessionsLoading } = useSessions(effectiveOrgId)
  const { data: agentsData } = useAgents(1, effectiveOrgId)
  const { data: orgUsersData } = useUsers(1, effectiveOrgId, undefined, undefined, 100, {}, canViewOrgUsage)

  const userLabel = useMemo(() => {
    const map = new Map<string, string>()
    for (const u of orgUsersData?.items ?? []) {
      if (u.id) map.set(u.id, u.name || u.email)
    }
    for (const u of stats?.user_breakdown ?? []) {
      if (!map.has(u.user_id)) map.set(u.user_id, u.user_name || u.user_email || `${u.user_id.slice(-8)}`)
    }
    return (userId?: string | null) => (userId ? map.get(userId) ?? `${userId.slice(-8)}` : '—')
  }, [orgUsersData, stats])

  useEffect(() => {
    setTracePage(1)
    setAgentFilter('')
    setSessionFilter(null)
    setUserFilter(null)
  }, [selectedOrgId])

  const { data: tracesData, loading: tracesLoading } = useTraceList(
    {
      page: tracePage,
      agentId: agentFilter,
      sessionId: sessionFilter ?? undefined,
      userId: userFilter ?? undefined,
      orgId: effectiveOrgId,
    },
    tab === 'traces',
  )

  const { traces: allTraces } = useRecentTraces(effectiveOrgId, tab === 'overview')

  // ── Derived stats ─────────────────────────────────────────────────────────

  const avgLatency = useMemo(() => {
    const valid = allTraces.filter(t => t.latency != null && t.latency > 0)
    if (!valid.length) return null
    return Math.round(valid.reduce((s, t) => s + t.latency!, 0) / valid.length)
  }, [allTraces])

  const totalTokens = useMemo(() => {
    const i = stats?.total_input_tokens ?? 0
    const o = stats?.total_output_tokens ?? 0
    return i + o > 0 ? i + o : null
  }, [stats])

  // ── Chart data derived from allTraces ──────────────────────────────────────

  const executionData = useMemo(() => {
    const byDay = new Map<string, number>()
    for (const t of allTraces) {
      if (!t.timestamp) continue
      const d = new Date(t.timestamp)
      if (Number.isNaN(d.getTime())) continue
      const key = `${d.getMonth() + 1}/${d.getDate()}`
      byDay.set(key, (byDay.get(key) ?? 0) + 1)
    }
    return Array.from(byDay.entries()).map(([date, executions]) => ({ date, executions }))
  }, [allTraces])

  const responseTimeData = useMemo(() => {
    const agg = new Map<string, { total: number; count: number }>()
    for (const t of allTraces) {
      const name = t.agent_name || 'Unknown'
      if (t.latency == null) continue
      const cur = agg.get(name) ?? { total: 0, count: 0 }
      cur.total += t.latency
      cur.count += 1
      agg.set(name, cur)
    }
    return Array.from(agg.entries())
      .map(([agent, { total, count }]) => ({ agent, ms: Math.round(total / count) }))
      .sort((a, b) => b.ms - a.ms)
      .slice(0, 6)
  }, [allTraces])

  const breakdown = stats?.agent_breakdown ?? []

  const agentUsageData = useMemo(() => {
    const top = [...breakdown].sort((a, b) => b.trace_count - a.trace_count).slice(0, 5)
    const total = top.reduce((s, a) => s + a.trace_count, 0)
    return top.map((a, i) => ({
      name: a.agent_name,
      value: total > 0 ? Math.round((a.trace_count / total) * 100) : 0,
      color: CHART_COLORS[i % CHART_COLORS.length],
    }))
  }, [breakdown])

  const { heatmap, heatMax } = useMemo(() => {
    const grid: number[][] = DAYS.map(() => Array(24).fill(0))
    let max = 0
    for (const t of allTraces) {
      if (!t.timestamp) continue
      const d = new Date(t.timestamp)
      if (Number.isNaN(d.getTime())) continue
      const row = d.getDay()
      const hour = d.getHours()
      grid[row][hour] += 1
      if (grid[row][hour] > max) max = grid[row][hour]
    }
    return { heatmap: grid, heatMax: max }
  }, [allTraces])

  // ── Actions ────────────────────────────────────────────────────────────────

  const openTrace = async (id: string) => {
    setLoadingDetail(true)
    try {
      setSelectedTrace(await tracingApi.getTrace(id, effectiveOrgId))
    } catch {
      // ignore
    } finally {
      setLoadingDetail(false)
    }
  }

  const viewSessionTraces = (threadId: string) => {
    setSessionFilter(threadId)
    setAgentFilter('')
    setUserFilter(null)
    setTracePage(1)
    setTab('traces')
  }

  const viewUserTraces = (userId: string) => {
    setUserFilter(userId)
    setAgentFilter('')
    setSessionFilter(null)
    setTracePage(1)
    setTab('traces')
  }

  // ── Table columns ──────────────────────────────────────────────────────────

  const traceColumns = [
    {
      key: 'timestamp',
      header: 'Timestamp',
      render: (row: TracePublic) => (
        <span className="text-[12px] text-[var(--text-2)]" title={row.timestamp}>{formatDate(row.timestamp)}</span>
      ),
    },
    {
      key: 'agent',
      header: 'Agent',
      render: (row: TracePublic) => (
        <span className="text-[12px] font-mono text-[var(--text-2)]">{row.agent_name ?? '—'}</span>
      ),
    },
    // Who ran it — only meaningful for roles that can see more than their own traces.
    ...(canViewOrgUsage
      ? [
          {
            key: 'user',
            header: 'User',
            render: (row: TracePublic) => (
              <span className="text-[12px] text-[var(--text-2)] truncate max-w-[140px] block" title={row.user_id ?? undefined}>
                {userLabel(row.user_id)}
              </span>
            ),
          },
        ]
      : []),
    {
      key: 'latency',
      header: 'Latency',
      render: (row: TracePublic) => <LatencyBadge ms={row.latency} />,
    },
    {
      key: 'cost',
      header: 'Cost',
      render: (row: TracePublic) => (
        <span className="text-[13px] text-[var(--text-2)]">
          {row.total_cost != null ? `$${row.total_cost.toFixed(4)}` : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: TracePublic) => (
        <Button variant="ghost" size="xs" onClick={() => openTrace(row.id)} disabled={loadingDetail}>
          <Eye className="w-3.5 h-3.5" />
        </Button>
      ),
    },
  ]

  const sessionColumns = [
    {
      key: 'thread_id',
      header: 'Session ID',
      render: (row: SessionPublic) => (
        <Badge variant="neutral" className="font-mono text-[10px]">{row.thread_id.slice(-12)}</Badge>
      ),
    },
    {
      key: 'agents',
      header: 'Agents',
      render: (row: SessionPublic) => (
        <span className="text-[13px]">
          {row.available_agents && row.available_agents.length > 0
            ? row.available_agents.map(a => a.name).join(', ')
            : '—'}
        </span>
      ),
    },
    {
      key: 'started',
      header: 'Started',
      render: (row: SessionPublic) => (
        <span className="text-[12px] text-[var(--text-3)]">{row.created_at ? formatDate(row.created_at) : '—'}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: SessionPublic) => (
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="xs" title="View traces" onClick={() => viewSessionTraces(row.thread_id)}>
            <ListFilter className="w-3.5 h-3.5" />
          </Button>
          <Button variant="ghost" size="xs" title="Open in playground" onClick={() => router.push(`${basePath}/playground?session=${row.thread_id}`)}>
            <MessageSquare className="w-3.5 h-3.5" />
          </Button>
        </div>
      ),
    },
  ]

  const sessions = Array.isArray(sessionsData) ? sessionsData : []

  const userColumns = [
    {
      key: 'user',
      header: 'User',
      render: (row: TraceStatsUserBreakdown) => (
        <div className="min-w-0">
          <p className="text-[13px] font-medium truncate">{row.user_name || userLabel(row.user_id)}</p>
          {row.user_email && <p className="text-[11px] text-[var(--text-3)] truncate">{row.user_email}</p>}
        </div>
      ),
    },
    {
      key: 'trace_count',
      header: 'Executions',
      render: (row: TraceStatsUserBreakdown) => (
        <span className="text-[13px] text-[var(--text-2)]">{row.trace_count}</span>
      ),
    },
    {
      key: 'tokens',
      header: 'Tokens',
      render: (row: TraceStatsUserBreakdown) => (
        <span className="text-[13px] text-[var(--text-2)]">{fmtTokens(row.total_tokens)}</span>
      ),
    },
    {
      key: 'cost',
      header: 'Cost',
      render: (row: TraceStatsUserBreakdown) => (
        <span className="text-[13px] text-[var(--text-2)]">${row.total_cost.toFixed(4)}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: TraceStatsUserBreakdown) => (
        <Button variant="ghost" size="xs" title="View traces" onClick={() => viewUserTraces(row.user_id)}>
          <ListFilter className="w-3.5 h-3.5" />
        </Button>
      ),
    },
  ]

  const userBreakdown = stats?.user_breakdown ?? []

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-0">
        <PageHeader
          title="Observability"
          description="Monitor agent executions, usage, latency, and costs in real time."
        />

        {/* Org filter — super admin only */}
        {isSuperAdmin && (
          <div className="relative shrink-0 mt-1" ref={orgDropdownRef}>
            <button
              type="button"
              onClick={() => setOrgDropdownOpen(v => !v)}
              className="flex items-center gap-2 h-9 px-3 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] text-[13px] font-medium hover:bg-[var(--surface-2)] transition-colors"
            >
              <Building2 className="w-4 h-4 text-violet-500 shrink-0" />
              <span className="max-w-[160px] truncate">
                {selectedOrg ? selectedOrg.name : 'All Organizations'}
              </span>
              <ChevronDown className={`w-3.5 h-3.5 text-[var(--text-3)] transition-transform ${orgDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {orgDropdownOpen && (
              <div className="absolute right-0 top-full mt-1.5 z-50 w-56 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] shadow-lg py-1 animate-scaleIn origin-top-right">
                <button
                  type="button"
                  onClick={() => { setSelectedOrgId(null); setOrgDropdownOpen(false) }}
                  className="w-full flex items-center justify-between px-3 py-2 text-[13px] hover:bg-[var(--surface-2)] transition-colors"
                >
                  <span>All Organizations</span>
                  {!selectedOrgId && <span className="text-violet-500 text-[11px]">✓</span>}
                </button>
                {organizations.length > 0 && <div className="my-1 h-px bg-[var(--border)]" />}
                {organizations.map(org => (
                  <button
                    key={org.id}
                    type="button"
                    onClick={() => { setSelectedOrgId(org.id ?? null); setOrgDropdownOpen(false) }}
                    className="w-full flex items-center justify-between px-3 py-2 text-[13px] hover:bg-[var(--surface-2)] transition-colors"
                  >
                    <span className="truncate">{org.name}</span>
                    {selectedOrgId === org.id && <span className="text-violet-500 text-[11px] shrink-0 ml-2">✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-5">
        <StatsCard label="Total Executions" value={stats?.total_traces ?? 0}                                                  icon={Zap}        color="primary" />
        <StatsCard label="Input Tokens"     value={fmtTokens(stats?.total_input_tokens)}                                      icon={Timer}       color="info"    />
        <StatsCard label="Output Tokens"    value={fmtTokens(stats?.total_output_tokens)}                                     icon={CheckCircle} color="success" />
        <StatsCard label="Total Tokens"     value={fmtTokens(totalTokens ?? undefined)}                                       icon={Layers}      color="info"    />
        <StatsCard label="Avg Latency"      value={avgLatency != null ? `${avgLatency}ms` : '—'}                              icon={Gauge}       color="warning" />
        <StatsCard label="Est. Cost"        value={stats?.total_cost != null ? `$${stats.total_cost.toFixed(4)}` : '—'}       icon={DollarSign}  color="danger"  />
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <Tabs
          tabs={(canViewOrgUsage ? (['overview', 'traces', 'sessions', 'users'] as const) : (['overview', 'traces', 'sessions'] as const))
            .map(t => ({ value: t, label: t.charAt(0).toUpperCase() + t.slice(1) }))}
          value={tab}
          onChange={v => setTab(v as typeof tab)}
        />

        {/* Agent / user filters — only shown on traces tab */}
        {tab === 'traces' && (
          <div className="flex items-center gap-2 ml-3 flex-wrap">
            <Select
              value={agentFilter}
              onValueChange={v => { setAgentFilter(v); setTracePage(1) }}
              placeholder="All agents"
              className="h-9 w-44 text-[13px]"
              options={[
                { value: '', label: 'All agents' },
                ...(agentsData?.items.map(a => ({ value: a.id!, label: a.name })) ?? []),
              ]}
            />

            {canViewOrgUsage && (
              <Select
                value={userFilter ?? ''}
                onValueChange={v => { setUserFilter(v || null); setTracePage(1) }}
                placeholder="All users"
                className="h-9 w-44 text-[13px]"
                options={[
                  { value: '', label: 'All users' },
                  ...(orgUsersData?.items.map(u => ({ value: u.id!, label: u.name || u.email })) ?? []),
                ]}
              />
            )}

            {sessionFilter && (
              <span className="inline-flex items-center gap-1.5 text-[12px] bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300 rounded-full px-2.5 py-1">
                session: {sessionFilter.slice(-8)}
                <button type="button" onClick={() => { setSessionFilter(null); setTracePage(1) }}>
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── Overview tab ── */}
      {tab === 'overview' && (
        <>
          {/* Row 1 — Daily Executions + Usage by Agent */}
          <div className="grid grid-cols-12 gap-5 mb-5">
            <div className="col-span-12 lg:col-span-8 glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[15px] font-semibold">Daily Executions</h3>
                <Button variant="ghost" size="xs"><Download className="w-4 h-4" /></Button>
              </div>
              {executionData.length === 0 ? (
                <div className="h-[280px] flex items-center justify-center text-[13px] text-[var(--text-3)]">
                  No execution data yet
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={executionData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--text-3)' }} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--text-3)' }} allowDecimals={false} />
                    <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                    <Area type="monotone" dataKey="executions" stroke="#7c3aed" fill="rgba(124,58,237,0.15)" animationDuration={800} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="col-span-12 lg:col-span-4 glass p-5 rounded-[var(--radius-lg)]">
              <h3 className="text-[15px] font-semibold mb-4">Usage by Agent</h3>
              {agentUsageData.length === 0 ? (
                <div className="h-[200px] flex items-center justify-center text-[13px] text-[var(--text-3)]">
                  No agent activity yet
                </div>
              ) : (
                <>
                  <div className="relative">
                    <ResponsiveContainer width="100%" height={200}>
                      <PieChart>
                        <Pie data={agentUsageData} innerRadius={65} outerRadius={90} dataKey="value" stroke="none">
                          {agentUsageData.map(entry => (
                            <Cell key={entry.name} fill={entry.color} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                      <span className="text-[24px] font-bold">{breakdown.length}</span>
                      <span className="text-[12px] text-[var(--text-3)]">agents</span>
                    </div>
                  </div>
                  <div className="space-y-2 mt-2">
                    {agentUsageData.map(agent => (
                      <div key={agent.name} className="flex items-center justify-between text-[13px]">
                        <span className="flex items-center gap-2 min-w-0">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: agent.color }} />
                          <span className="truncate">{agent.name}</span>
                        </span>
                        <span className="text-[var(--text-3)] shrink-0">{agent.value}%</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Row 2 — Cost by Agent + Avg Response Time */}
          <div className="grid grid-cols-12 gap-5 mb-5">
            <div className="col-span-12 lg:col-span-6 glass p-5 rounded-[var(--radius-lg)]">
              <h3 className="text-[15px] font-semibold mb-4">Cost by Agent</h3>
              {breakdown.length === 0 ? (
                <div className="h-[220px] flex items-center justify-center text-[13px] text-[var(--text-3)]">
                  No cost data yet
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={[...breakdown]
                      .sort((a, b) => b.total_cost - a.total_cost)
                      .slice(0, 6)
                      .map(a => ({ agent: a.agent_name, cost: Number(a.total_cost.toFixed(4)) }))}
                    layout="vertical"
                    margin={{ left: 20 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 12, fill: 'var(--text-3)' }} tickFormatter={v => `$${v}`} />
                    <YAxis type="category" dataKey="agent" width={110} tick={{ fontSize: 12, fill: 'var(--text-3)' }} />
                    <Tooltip
                      contentStyle={CHART_TOOLTIP_STYLE}
                      formatter={(v) => [`$${Number(v).toFixed(4)}`, 'Cost']}
                    />
                    <Bar dataKey="cost" fill="#06b6d4" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="col-span-12 lg:col-span-6 glass p-5 rounded-[var(--radius-lg)]">
              <h3 className="text-[15px] font-semibold mb-4">Avg Response Time by Agent</h3>
              {responseTimeData.length === 0 ? (
                <div className="h-[220px] flex items-center justify-center text-[13px] text-[var(--text-3)]">
                  No latency data yet
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={responseTimeData} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 12, fill: 'var(--text-3)' }} unit="ms" />
                    <YAxis type="category" dataKey="agent" width={100} tick={{ fontSize: 12, fill: 'var(--text-3)' }} />
                    <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                    <Bar dataKey="ms" fill="#7c3aed" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Row 3 — Activity Heatmap (full width) */}
          <div className="grid grid-cols-12 gap-5">
            <div className="col-span-12 glass p-5 rounded-[var(--radius-lg)]">
              <h3 className="text-[15px] font-semibold mb-4">Activity by Time</h3>
              <div className="overflow-x-auto">
                <div className="min-w-[560px]">
                  <div className="flex gap-[3px] mb-1 pl-8">
                    {Array.from({ length: 24 }, (_, h) =>
                      h % 4 === 0 ? (
                        <span key={h} className="text-[10px] text-[var(--text-3)] w-5 text-center" style={{ marginLeft: h === 0 ? 0 : 60 }}>
                          {h}
                        </span>
                      ) : null
                    )}
                  </div>
                  {heatmap.map((row, ri) => (
                    <div key={ri} className="flex items-center gap-1 mb-1">
                      <span className="text-[10px] text-[var(--text-3)] w-7">{DAYS[ri]}</span>
                      <div className="flex gap-[3px]">
                        {row.map((value, hour) => (
                          <div
                            key={`${ri}-${hour}`}
                            title={`${DAYS[ri]} ${hour}:00 — ${value} executions`}
                            className="w-5 h-5 rounded-[3px] cursor-default"
                            style={{ background: heatColor(value, heatMax) }}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Traces tab ── */}
      {tab === 'traces' && (
        <>
          <DataTable
            columns={traceColumns}
            data={tracesData?.items ?? []}
            isLoading={tracesLoading}
            emptyIcon={Activity}
            emptyMessage="No traces yet"
            emptyDescription="Run an agent in the Playground to generate execution traces."
            emptyAction={
              <Button variant="primary" size="sm" onClick={() => router.push(`${basePath}/playground`)}>
                Open Playground
              </Button>
            }
          />
          {tracesData && tracesData.total > tracesData.page_size && (
            <Pagination page={tracePage} pageSize={tracesData.page_size} total={tracesData.total} onPageChange={setTracePage} />
          )}
        </>
      )}

      {/* ── Sessions tab ── */}
      {tab === 'sessions' && (
        <DataTable
          columns={sessionColumns as any}
          data={sessions}
          isLoading={sessionsLoading}
          emptyIcon={MessageSquare}
          emptyMessage="No sessions yet"
          emptyDescription="Start a conversation in the Playground to create your first session."
          emptyAction={
            <Button variant="primary" size="sm" onClick={() => router.push(`${basePath}/playground`)}>
              Open Playground
            </Button>
          }
        />
      )}

      {/* ── Users tab — org_admin/org_manager/super_admin only ── */}
      {tab === 'users' && canViewOrgUsage && (
        <DataTable
          columns={userColumns as any}
          data={userBreakdown}
          isLoading={!stats}
          emptyIcon={UsersIcon}
          emptyMessage="No usage yet"
          emptyDescription="Once members of this organization run agents, their usage will be broken down here."
        />
      )}

      <TraceDetailSheet trace={selectedTrace} onClose={() => setSelectedTrace(null)} />
    </>
  )
}
