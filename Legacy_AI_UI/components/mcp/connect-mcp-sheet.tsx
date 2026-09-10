'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  X, Plug, Loader2, CheckCircle2, AlertCircle,
  ExternalLink, Wrench, RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Badge } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { Tabs } from '@/components/ui/tabs'
import { mcpApi } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import { useAgents } from '@/hooks/use-agents'
import type { McpCatalogEntry, McpTestConnectionResult } from '@/types'
import { cn } from '@/lib/utils'

interface Props {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  preselectedAgentId?: string
}

function resolveTemplate(template: string, placeholders: Record<string, string>): string {
  return Object.entries(placeholders).reduce(
    (s, [k, v]) => s.replace(new RegExp(`<${k}>`, 'g'), v),
    template
  )
}

function isHttpUrl(s: string) {
  return s.startsWith('http://') || s.startsWith('https://')
}

export function ConnectMcpSheet({ open, onClose, onSuccess, preselectedAgentId }: Props) {
  const { user } = useAuth()
  const { data: agentsData } = useAgents(1, undefined, undefined, 100)
  const agents = agentsData?.items ?? []

  // Keep the sheet mounted for one exit-animation cycle instead of unmounting
  // instantly on close (AUDIT.md category 3/4 — a spatially-connected panel
  // needs to slide away, not teleport).
  const [visible, setVisible] = useState(open)
  const [closing, setClosing] = useState(false)
  useEffect(() => {
    if (open) {
      setVisible(true)
      setClosing(false)
      return
    }
    if (!visible) return
    setClosing(true)
    const t = setTimeout(() => {
      setVisible(false)
      setClosing(false)
    }, 220)
    return () => clearTimeout(t)
  }, [open, visible])

  const [tab, setTab] = useState<'catalog' | 'custom'>('catalog')

  // Catalog
  const [catalogSearch, setCatalogSearch] = useState('')
  const [catalog, setCatalog] = useState<McpCatalogEntry[]>([])
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [selectedEntry, setSelectedEntry] = useState<McpCatalogEntry | null>(null)

  // Custom
  const [connectionString, setConnectionString] = useState('')

  // Shared
  const [name, setName] = useState('')
  const [token, setToken] = useState('')
  const [description, setDescription] = useState('')
  const [agentId, setAgentId] = useState(preselectedAgentId ?? '')
  const [placeholders, setPlaceholders] = useState<Record<string, string>>({})

  // Test
  const [testResult, setTestResult] = useState<McpTestConnectionResult | null>(null)
  const [testLoading, setTestLoading] = useState(false)
  const [testError, setTestError] = useState('')

  // Save / OAuth
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [oauthLoading, setOauthLoading] = useState(false)
  const [oauthSent, setOauthSent] = useState(false)

  // Sync preselectedAgentId
  useEffect(() => {
    if (preselectedAgentId) setAgentId(preselectedAgentId)
  }, [preselectedAgentId])

  // Reset on open
  useEffect(() => {
    if (!open) return
    setTab('catalog')
    setCatalogSearch('')
    setSelectedEntry(null)
    setConnectionString('')
    setName('')
    setToken('')
    setDescription('')
    setAgentId(preselectedAgentId ?? '')
    setPlaceholders({})
    setTestResult(null)
    setTestError('')
    setSaveError('')
    setOauthSent(false)
  }, [open, preselectedAgentId])

  // Reset placeholders when entry changes; suggest its name if the user hasn't typed one
  useEffect(() => {
    if (!selectedEntry) { setPlaceholders({}); return }
    setPlaceholders(Object.fromEntries(selectedEntry.requires.map(k => [k, ''])))
    setName(n => n || selectedEntry.name)
  }, [selectedEntry])

  // Load catalog
  const loadCatalog = useCallback(async (q: string) => {
    setCatalogLoading(true)
    try {
      setCatalog(await mcpApi.catalog(q || undefined))
    } catch {
      setCatalog([])
    } finally {
      setCatalogLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open || tab !== 'catalog') return
    const t = setTimeout(() => loadCatalog(catalogSearch), 300)
    return () => clearTimeout(t)
  }, [open, tab, catalogSearch, loadCatalog])

  // Effective connection string for testing
  const effectiveConnString = useMemo(() => {
    if (tab === 'custom') return connectionString
    if (!selectedEntry) return ''
    return resolveTemplate(selectedEntry.connection_string, placeholders)
  }, [tab, connectionString, selectedEntry, placeholders])

  const canTest = effectiveConnString.trim().length > 0

  const handleTest = async () => {
    if (!canTest) return
    setTestLoading(true)
    setTestResult(null)
    setTestError('')
    try {
      const result = await mcpApi.testConnection({
        connection_string: effectiveConnString,
        token: token || undefined,
      })
      setTestResult(result)
    } catch (e) {
      setTestError(e instanceof Error ? e.message : 'Connection failed')
    } finally {
      setTestLoading(false)
    }
  }

  const handleSave = async () => {
    if (!user?.organization_id) return
    setSaving(true)
    setSaveError('')
    try {
      if (tab === 'catalog' && selectedEntry) {
        await mcpApi.create({
          organization_id: user.organization_id,
          agent_id: agentId || undefined,
          registry_key: selectedEntry.key,
          placeholders: Object.keys(placeholders).length > 0 ? placeholders : undefined,
          name: name.trim() || undefined,
          user_description: description || undefined,
          token: token || undefined,
        })
      } else {
        await mcpApi.create({
          organization_id: user.organization_id,
          agent_id: agentId || undefined,
          connection_string: connectionString,
          name: name.trim() || undefined,
          user_description: description || undefined,
          token: token || undefined,
        })
      }
      onSuccess()
      onClose()
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to connect server')
    } finally {
      setSaving(false)
    }
  }

  const handleOAuth = async () => {
    if (!user?.organization_id || !effectiveConnString) return
    setOauthLoading(true)
    setSaveError('')
    try {
      const { authorization_url } = await mcpApi.oauthStart({
        organization_id: user.organization_id,
        agent_id: agentId || undefined,
        connection_string: effectiveConnString,
        name: name.trim() || undefined,
        user_description: description || undefined,
      })
      window.open(authorization_url, '_blank', 'noopener,noreferrer')
      setOauthSent(true)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'OAuth flow failed')
    } finally {
      setOauthLoading(false)
    }
  }

  const showOAuth = isHttpUrl(effectiveConnString)

  if (!visible) return null

  return (
    <>
      <div
        className={cn('animate-fadeIn fixed inset-0 bg-black/50 z-40', closing && '[animation-direction:reverse]')}
        onClick={onClose}
      />
      <div
        className={cn(
          'animate-slideInRight fixed right-0 top-0 h-screen w-full max-w-[580px] bg-[var(--surface)] border-l border-[var(--border)] z-50 flex flex-col shadow-2xl',
          closing && '[animation-direction:reverse]',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)] shrink-0">
          <div className="flex items-center gap-2.5">
            <Plug className="w-4.5 h-4.5 text-violet-500" />
            <h2 className="text-[15px] font-semibold">Connect MCP Server</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="w-4 h-4" /></Button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Tab switcher */}
          <Tabs
            equalWidth
            className="w-full"
            value={tab}
            onChange={v => { setTab(v as typeof tab); setTestResult(null); setTestError('') }}
            tabs={[
              { value: 'catalog', label: 'Browse Catalog' },
              { value: 'custom', label: 'Custom URL / Command' },
            ]}
          />

          {/* ── Catalog tab ── */}
          {tab === 'catalog' && (
            <div className="space-y-3">
              <SearchInput
                placeholder="Search catalog…"
                value={catalogSearch}
                onChange={e => setCatalogSearch(e.target.value)}
              />

              {catalogLoading ? (
                <div className="flex justify-center py-8 text-[var(--text-3)]">
                  <Loader2 className="w-5 h-5 animate-spin" />
                </div>
              ) : catalog.length === 0 ? (
                <p className="text-center text-[13px] text-[var(--text-3)] py-8">
                  {catalogSearch ? 'No results' : 'No catalog entries available'}
                </p>
              ) : (
                <div className="grid grid-cols-1 gap-2">
                  {catalog.map(entry => (
                    <button
                      key={entry.key}
                      type="button"
                      onClick={() => setSelectedEntry(sel => sel?.key === entry.key ? null : entry)}
                      className={cn(
                        'w-full text-left p-3.5 rounded-[var(--radius-md)] border transition-[border-color,background-color]',
                        selectedEntry?.key === entry.key
                          ? 'border-violet-500/50 bg-violet-500/5'
                          : 'border-[var(--border)] hover:border-[var(--border-2)] bg-[var(--surface-2)]'
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <span className="text-[13px] font-semibold">{entry.name}</span>
                            {entry.category && (
                              <Badge variant="neutral" className="text-[10px]">{entry.category}</Badge>
                            )}
                            {entry.transport && (
                              <Badge variant="info" className="text-[10px]">{entry.transport}</Badge>
                            )}
                          </div>
                          <p className="text-[12px] text-[var(--text-3)] line-clamp-2">{entry.description}</p>
                          {entry.requires.length > 0 && (
                            <div className="flex gap-1 mt-2 flex-wrap">
                              {entry.requires.map(r => (
                                <span key={r} className="text-[10px] font-mono bg-amber-500/10 text-amber-500 border border-amber-500/20 rounded px-1.5 py-0.5">
                                  {r}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        {entry.homepage && (
                          <a
                            href={entry.homepage}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={e => e.stopPropagation()}
                            className="shrink-0 text-[var(--text-3)] hover:text-violet-500 transition-colors"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {/* Placeholder fields for selected entry */}
              {selectedEntry && selectedEntry.requires.length > 0 && (
                <div className="space-y-3 p-4 bg-[var(--surface-2)] rounded-[var(--radius-md)] border border-[var(--border)]">
                  <p className="text-[12px] font-semibold text-[var(--text-2)]">Required credentials</p>
                  {selectedEntry.requires.map(key => (
                    <div key={key}>
                      <label className="text-[12px] font-medium block mb-1.5 font-mono text-amber-500">{key}</label>
                      <Input
                        type={key.toLowerCase().includes('key') || key.toLowerCase().includes('secret') || key.toLowerCase().includes('token') ? 'password' : 'text'}
                        placeholder={`Enter ${key}`}
                        value={placeholders[key] ?? ''}
                        onChange={e => setPlaceholders(p => ({ ...p, [key]: e.target.value }))}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Custom tab ── */}
          {tab === 'custom' && (
            <div className="space-y-4">
              <div>
                <label className="text-[12.5px] font-semibold block mb-1.5">Connection string</label>
                <Input
                  placeholder="https://server.example.com/mcp  or  npx -y @scope/server"
                  value={connectionString}
                  onChange={e => { setConnectionString(e.target.value); setTestResult(null) }}
                  className="font-mono text-[12px]"
                />
                <p className="text-[11px] text-[var(--text-3)] mt-1">
                  HTTP(S) URL, SSE endpoint, WebSocket, or stdio command (npx / uvx / python …)
                </p>
              </div>
              <div>
                <label className="text-[12.5px] font-semibold block mb-1.5">Bearer token <span className="text-[var(--text-3)] font-normal">(optional)</span></label>
                <Input
                  type="password"
                  placeholder="sk-…"
                  value={token}
                  onChange={e => setToken(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* ── Shared: Name + Agent selector + description ── */}
          <div className="space-y-4">
            <div>
              <label className="text-[12.5px] font-semibold block mb-1.5">Name</label>
              <Input
                placeholder={tab === 'catalog' ? (selectedEntry?.name || 'Server name') : 'Custom MCP'}
                value={name}
                onChange={e => setName(e.target.value)}
              />
              <p className="text-[11px] text-[var(--text-3)] mt-1">
                Shown in your MCP Servers list — useful once you have more than one.
              </p>
            </div>

            <div>
              <label className="text-[12.5px] font-semibold block mb-1.5">
                Attach to agent <span className="text-[var(--text-3)] font-normal">(optional)</span>
              </label>
              <Select
                value={agentId}
                onValueChange={setAgentId}
                disabled={!!preselectedAgentId}
                placeholder="Connect standalone, or pick an agent to attach all tools to now…"
                className="text-[13px]"
                options={agents.map(a => ({ value: a.id!, label: a.name }))}
              />
              <p className="text-[11px] text-[var(--text-3)] mt-1">
                Leave blank to just connect the server — you can attach individual tools to
                any agent afterward.
              </p>
            </div>

            <div>
              <label className="text-[12.5px] font-semibold block mb-1.5">Description <span className="text-[var(--text-3)] font-normal">(optional)</span></label>
              <Input
                placeholder="What does this server do?"
                value={description}
                onChange={e => setDescription(e.target.value)}
              />
            </div>
          </div>

          {/* ── Test connection ── */}
          <div className="space-y-3">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleTest}
              disabled={!canTest || testLoading}
              className="gap-2"
            >
              {testLoading
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <RefreshCw className="w-3.5 h-3.5" />
              }
              Test Connection
            </Button>

            {testError && (
              <div className="flex items-start gap-2 p-3 rounded-[var(--radius-md)] bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-[13px] text-red-600 dark:text-red-400">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{testError}</span>
              </div>
            )}

            {testResult && (
              <div className={cn(
                'p-3 rounded-[var(--radius-md)] border',
                testResult.ok
                  ? 'bg-green-500/8 border-green-500/20'
                  : 'bg-red-500/8 border-red-500/20'
              )}>
                <div className="flex items-center gap-2 mb-2">
                  {testResult.ok
                    ? <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400" />
                    : <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
                  }
                  <span className="text-[13px] font-medium">
                    {testResult.ok
                      ? `Connected · ${testResult.transport ?? ''} · ${testResult.tool_count} tool${testResult.tool_count !== 1 ? 's' : ''}`
                      : testResult.error ?? 'Connection failed'
                    }
                  </span>
                </div>
                {testResult.ok && testResult.tools.length > 0 && (
                  <div className="space-y-1 mt-2">
                    {testResult.tools.map(tool => (
                      <div key={tool.name} className="flex items-start gap-2">
                        <Wrench className="w-3 h-3 text-violet-600 dark:text-violet-400 shrink-0 mt-0.5" />
                        <div>
                          <span className="text-[12px] font-mono font-medium text-violet-300">{tool.name}</span>
                          {tool.description && (
                            <span className="text-[11px] text-[var(--text-3)] ml-2">{tool.description}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* OAuth sent confirmation */}
          {oauthSent && (
            <div className="p-3 rounded-[var(--radius-md)] bg-violet-500/10 border border-violet-500/20 text-[13px] text-violet-300">
              Authorization opened in a new tab. Complete the flow there, then come back and refresh the server list.
            </div>
          )}

          {saveError && (
            <div className="flex items-start gap-2 p-3 rounded-[var(--radius-md)] bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-[13px] text-red-600 dark:text-red-400">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{saveError}</span>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="border-t border-[var(--border)] px-5 py-4 flex items-center gap-3 shrink-0">
          <Button variant="ghost" size="sm" onClick={onClose} className="mr-auto">Cancel</Button>

          {showOAuth && !oauthSent && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleOAuth}
              disabled={oauthLoading}
              className="gap-2"
            >
              {oauthLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ExternalLink className="w-3.5 h-3.5" />}
              Authorize with OAuth
            </Button>
          )}

          {oauthSent ? (
            <Button variant="primary" size="sm" onClick={() => { onSuccess(); onClose() }}>
              Done — refresh list
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              disabled={saving || (tab === 'catalog' && !selectedEntry) || (tab === 'custom' && !connectionString.trim())}
              className="gap-2"
            >
              {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Connect Server
            </Button>
          )}
        </div>
      </div>
    </>
  )
}
