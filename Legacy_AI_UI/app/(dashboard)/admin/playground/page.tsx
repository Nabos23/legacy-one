'use client'

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useSearchParams } from 'next/navigation'
import {
  Plus, ExternalLink, Bot, Sparkles,
  MessageSquare, ChevronDown, ChevronLeft, ChevronRight, CheckCircle2, Building2, Pencil, Trash2,
  FileText, Image as ImageIcon, X as XIcon
} from 'lucide-react'
import { ChatComposer } from '@/components/chat/chat-composer'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog } from '@/components/ui/dialog'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { TypingIndicator } from '@/components/ui/typing-indicator'
import { ImageGeneration } from '@/components/ui/image-generation'
import { looksLikeImageGenAgent, truncatePromptForDisplay } from '@/lib/agent-image-gen'
import { Markdown } from '@/components/ui/markdown'
import { Progress } from '@/components/ui/progress'
import { useAgents } from '@/hooks/use-agents'
import { useSessions } from '@/hooks/use-sessions'
import { useChat } from '@/hooks/use-chat'
import { useToast } from '@/hooks/use-toast'
import { chatApi } from '@/lib/api'
import type { ChatAttachmentResult } from '@/lib/api/chat'
import { cn } from '@/lib/utils'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import { useOrganizations } from '@/hooks/use-organizations'
import { useAuth } from '@/contexts/auth-context'

const FILE_ACCEPT = [
  '.pdf', '.docx', '.xlsx', '.pptx',
  '.txt', '.md', '.markdown', '.csv', '.tsv', '.log',
  '.html', '.htm', '.xml', '.json', '.yaml', '.yml',
  '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.c', '.cpp', '.h', '.hpp',
  '.cs', '.go', '.rs', '.rb', '.php', '.sql', '.sh', '.css', '.ini', '.toml',
  'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff',
].join(',')

type PendingAttachment = ChatAttachmentResult

export default function PlaygroundPage() {
  const searchParams = useSearchParams()
  const { permissions } = useAuth()
  
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null)
  const [isOrgDropdownOpen, setIsOrgDropdownOpen] = useState(false)
  const { data: orgsData } = useOrganizations(1, undefined, 1000)
  const organizations = orgsData?.items ?? []
  const currentOrg = selectedOrgId ? organizations.find(o => o.id === selectedOrgId) : null
  
  const effectiveOrgId = permissions?.is_super_admin ? (selectedOrgId || undefined) : undefined
  // Agent switcher needs every agent in the org, not a paginated slice —
  // 100 is the server's max page size (backend/core/constants.py).
  const { data: agentsData, loading: agentsLoading } = useAgents(1, effectiveOrgId, undefined, 100)
  
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const { data: sessions, loading: sessionsLoading, refetch: refetchSessions, updateSessionName, renameSession, removeSession } = useSessions(effectiveOrgId, selectedAgentId || undefined)
  const [isAgentDropdownOpen, setIsAgentDropdownOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null)
  const [draftName, setDraftName] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<{ thread_id: string; name?: string | null } | null>(null)
  const [deleting, setDeleting] = useState(false)

  // The history panel is an inline column on desktop but an overlay on mobile;
  // start it closed on small screens so it doesn't crush the chat pane.
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    if (mq.matches) setSidebarOpen(false)
  }, [])

  useEffect(() => {
    setSelectedAgentId(null)
  }, [effectiveOrgId])
  
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState<PendingAttachment[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{ filename: string; percent: number } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const { toast } = useToast()

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [input])

  const handleSessionCreated = useCallback((newSessionId: string) => {
    setSelectedSessionId(newSessionId)
    refetchSessions()
  }, [refetchSessions])

  const handleSessionTitle = useCallback((threadId: string, name: string) => {
    updateSessionName(threadId, name)
  }, [updateSessionName])

  const selectedSession = sessions?.find(s => s.thread_id === selectedSessionId)
  const chatOrgId = selectedSession ? selectedSession.organization_id : effectiveOrgId

  const chat = useChat({
    sessionId: selectedSessionId,
    agentId: selectedAgentId,
    orgId: chatOrgId,
    onSessionCreated: handleSessionCreated,
    onSessionTitle: handleSessionTitle,
  })

  const agents = agentsData?.items ?? []

  // Initialize selected agent from query params if possible
  useEffect(() => {
    const agentParam = searchParams.get('agent')
    if (agentParam && agents.length > 0 && selectedAgentId === null) {
      setSelectedAgentId(agentParam)
    }
  }, [agents, searchParams])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.messages])

  useEffect(() => {
    if (chat.error) toast.error(chat.error)
  }, [chat.error])

  const agentById = useMemo(() => new Map(agents.map(a => [a.id, a])), [agents])
  const currentAgent = selectedAgentId ? agentById.get(selectedAgentId) ?? null : null
  const isSupervisorSession = selectedAgentId === null
  const isImageGenAgent = !isSupervisorSession
    && looksLikeImageGenAgent(currentAgent?.name, currentAgent?.description)
  const displayedPrompt = truncatePromptForDisplay(
    [...chat.messages].reverse().find(m => m.role === 'user')?.content
  )

  const handleSend = () => {
    if ((!input.trim() && attachments.length === 0) || chat.isTyping || uploading) return
    chat.send(input, attachments.length ? attachments : undefined)
    setInput('')
    setAttachments([])
  }

  const handleFilesSelected = async (files: FileList | null) => {
    if (!files?.length) return
    setUploading(true)
    for (const file of Array.from(files)) {
      setUploadProgress({ filename: file.name, percent: 0 })
      try {
        const result = await chatApi.processAttachment(file, percent =>
          setUploadProgress({ filename: file.name, percent }),
        )
        setAttachments(prev => [...prev, result])
        if (result.kind === 'document' && result.truncated) {
          toast.info(
            `"${result.filename}" was long — attached the first ${(result.chars ?? 0).toLocaleString()} characters.`,
          )
        }
      } catch (e) {
        toast.error(e instanceof Error ? e.message : `Could not read "${file.name}"`)
      }
    }
    setUploading(false)
    setUploadProgress(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const removeAttachment = (idx: number) =>
    setAttachments(prev => prev.filter((_, i) => i !== idx))

  const handleNewChat = () => {
    setSelectedSessionId(null)
    setAttachments([])
    chat.reset()
  }

  const startRename = (threadId: string, currentName: string | null | undefined) => {
    setEditingSessionId(threadId)
    setDraftName(currentName || '')
  }

  const commitRename = async (threadId: string) => {
    const name = draftName.trim()
    setEditingSessionId(null)
    const current = sessions?.find(s => s.thread_id === threadId)
    // No-op (and no PATCH) when blank or unchanged — also guards the
    // Enter-then-blur double fire, since the optimistic update makes the
    // second call see an unchanged name.
    if (!name || name === current?.name) return
    try {
      await renameSession(threadId, name)
      toast.success('Session renamed')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to rename session')
    }
  }

  const handleDelete = (e: React.MouseEvent, session: { thread_id: string; name?: string | null }) => {
    e.stopPropagation()
    setDeleteTarget(session)
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    const threadId = deleteTarget.thread_id
    setDeleting(true)
    try {
      await removeSession(threadId)
      if (selectedSessionId === threadId) {
        setSelectedSessionId(null)
        chat.reset()
      }
      setDeleteTarget(null)
    } catch {
      toast.error('Failed to delete session')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="relative flex flex-1 min-h-0 overflow-hidden bg-[var(--surface)] font-sans text-[var(--text-1)]">

      {/* Mobile overlay backdrop — only visible when the history panel is open on small screens */}
      {sidebarOpen && (
        <div
          className="md:hidden fixed inset-0 top-[56px] z-20 bg-black/40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <div className={cn(
        "flex flex-col shrink-0 min-h-0 bg-[var(--surface)] border-r border-[var(--border)] z-30 overflow-hidden",
        "transition-[width] duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)]",
        // On mobile the panel floats over the chat instead of consuming layout width.
        "max-md:absolute max-md:inset-y-0 max-md:left-0",
        sidebarOpen ? "w-[272px]" : "w-0",
        !sidebarOpen && "max-md:hidden"
      )}>

        {/* Sidebar header */}
        <div className="h-14 px-3 flex items-center gap-2 border-b border-[var(--border)] shrink-0 w-[272px]">
          <button
            onClick={handleNewChat}
            className="flex-1 flex items-center justify-center gap-1.5 h-8 bg-violet-600 hover:bg-violet-700 active:bg-violet-800 text-white text-[13px] font-medium rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New Chat
          </button>
          <button
            onClick={() => setSidebarOpen(false)}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.06] transition-colors shrink-0"
            title="Collapse sidebar"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>

        {/* Section label */}
        <div className="flex items-center justify-between px-4 pt-5 pb-1.5 w-[272px]">
          <span className="text-[10.5px] font-semibold tracking-widest text-[var(--text-3)] uppercase">History</span>
          {!sessionsLoading && sessions.length > 0 && (
            <span className="text-[11px] tabular-nums text-[var(--text-3)]">{sessions.length}</span>
          )}
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-2 pb-4 space-y-px w-[272px]">
          {sessionsLoading ? (
            <div className="px-3 py-3 space-y-3">
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className="flex flex-col gap-1.5 animate-pulse">
                  <div className="h-3 bg-black/[0.06] dark:bg-white/[0.07] rounded w-3/4" />
                  <div className="h-2 bg-black/[0.04] dark:bg-white/[0.04] rounded w-2/5" />
                </div>
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <div className="px-4 py-12 text-center">
              <MessageSquare className="w-5 h-5 mx-auto mb-2 text-[var(--text-3)] opacity-30" />
              <p className="text-[12px] text-[var(--text-3)]">No sessions yet</p>
            </div>
          ) : (
            sessions.map(session => {
              const isEditing = editingSessionId === session.thread_id
              return (
                <div
                  key={session.thread_id}
                  className={cn(
                    'relative w-full px-3 py-2 flex items-center gap-2 rounded-lg transition-colors cursor-pointer group',
                    selectedSessionId === session.thread_id
                      ? 'bg-violet-50 dark:bg-violet-500/[0.08]'
                      : 'hover:bg-black/[0.04] dark:hover:bg-white/[0.04]'
                  )}
                  onClick={() => !isEditing && setSelectedSessionId(session.thread_id)}
                >
                  {selectedSessionId === session.thread_id && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-violet-500 rounded-r-full" />
                  )}
                  <div className="flex-1 min-w-0">
                    {isEditing ? (
                      <input
                        autoFocus
                        value={draftName}
                        onChange={e => setDraftName(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') { e.preventDefault(); commitRename(session.thread_id) }
                          else if (e.key === 'Escape') { setEditingSessionId(null) }
                        }}
                        onBlur={() => commitRename(session.thread_id)}
                        onClick={e => e.stopPropagation()}
                        className="w-full bg-transparent border-b border-violet-600 dark:border-violet-400 text-[13px] font-medium text-[var(--text-1)] outline-none py-px"
                      />
                    ) : (
                      <p className={cn(
                        "text-[13px] font-medium truncate leading-snug transition-colors",
                        selectedSessionId === session.thread_id
                          ? "text-violet-700 dark:text-violet-300"
                          : "text-[var(--text-2)] group-hover:text-[var(--text-1)]"
                      )}>
                        {session.name || 'New Session'}
                      </p>
                    )}
                  </div>
                  {!isEditing && (
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                      <button
                        type="button"
                        onClick={e => { e.stopPropagation(); startRename(session.thread_id, session.name) }}
                        aria-label="Rename session"
                        className="p-1 rounded hover:bg-black/[0.07] dark:hover:bg-white/[0.1] text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors"
                      >
                        <Pencil className="w-3 h-3" />
                      </button>
                      <button
                        type="button"
                        onClick={e => handleDelete(e, session)}
                        aria-label="Delete session"
                        className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-500/[0.12] text-[var(--text-3)] hover:text-red-500 transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* ── Chat Area ───────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative bg-[var(--surface)]">

        {/* Chat header */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-sm shrink-0 relative z-20">
          <div className="flex items-center gap-1.5">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.06] transition-colors"
                title="Expand sidebar"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            )}

            <div className="flex items-center gap-3">
              {/* Org picker (super admin only) */}
              {permissions?.is_super_admin && (
                <div className="relative">
                  <button
                    onClick={() => setIsOrgDropdownOpen(!isOrgDropdownOpen)}
                    className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-black/[0.04] dark:hover:bg-white/[0.05] transition-colors"
                  >
                    <div className="w-7 h-7 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center text-[var(--text-2)] shrink-0">
                      <Building2 className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex items-center gap-1.5">
                      <p className="text-[13px] font-medium text-[var(--text-1)] max-w-[110px] truncate">
                        {currentOrg?.name || 'All Orgs'}
                      </p>
                      <ChevronDown className="w-3.5 h-3.5 text-[var(--text-3)]" />
                    </div>
                  </button>
                  {isOrgDropdownOpen && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setIsOrgDropdownOpen(false)} />
                      <div className="absolute top-full left-0 mt-1.5 w-60 bg-[var(--surface)] rounded-xl shadow-lg border border-[var(--border)] overflow-hidden z-20 animate-in fade-in zoom-in-95 duration-150 origin-top-left">
                        <div className="p-2 border-b border-[var(--border)]">
                          <button
                            onClick={() => { setSelectedOrgId(null); setIsOrgDropdownOpen(false) }}
                            className={cn("w-full flex items-center justify-between px-2.5 py-2 rounded-lg transition-colors text-left", !selectedOrgId ? "bg-black/[0.05] dark:bg-white/[0.07]" : "hover:bg-black/[0.03] dark:hover:bg-white/[0.04]")}
                          >
                            <p className="text-[13px] font-medium text-[var(--text-1)]">All Organizations</p>
                            {!selectedOrgId && <CheckCircle2 className="w-3.5 h-3.5 text-violet-500 shrink-0" />}
                          </button>
                        </div>
                        <div className="p-2 max-h-[280px] overflow-y-auto custom-scrollbar">
                          {organizations.map(org => (
                            <button
                              key={org.id}
                              onClick={() => { setSelectedOrgId(org.id!); setIsOrgDropdownOpen(false) }}
                              className={cn("w-full flex items-center justify-between px-2.5 py-2 rounded-lg transition-colors text-left", selectedOrgId === org.id ? "bg-black/[0.05] dark:bg-white/[0.07]" : "hover:bg-black/[0.03] dark:hover:bg-white/[0.04]")}
                            >
                              <p className="text-[13px] font-medium text-[var(--text-1)] truncate">{org.name}</p>
                              {selectedOrgId === org.id && <CheckCircle2 className="w-3.5 h-3.5 text-violet-500 shrink-0" />}
                            </button>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}

              {permissions?.is_super_admin && (
                <div className="w-px h-5 bg-[var(--border)]" />
              )}

              {/* Agent picker */}
              <div className="relative">
                <button
                  onClick={() => setIsAgentDropdownOpen(!isAgentDropdownOpen)}
                  className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-black/[0.04] dark:hover:bg-white/[0.05] transition-colors"
                >
                  {isSupervisorSession ? (
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0">
                      <Sparkles className="w-4 h-4" />
                    </div>
                  ) : currentAgent ? (
                    <AgentAvatar
                      name={currentAgent.name}
                      avatarType={currentAgent.avatar_type}
                      avatarValue={currentAgent.avatar_value}
                      avatarUrl={currentAgent.avatar_url}
                      size="sm"
                      shape="rounded"
                    />
                  ) : null}
                  <div className="text-left">
                    <div className="flex items-center gap-1.5">
                      <p className="text-[14px] font-semibold text-[var(--text-1)] leading-tight">
                        {isSupervisorSession ? 'Supervisor' : currentAgent?.name}
                      </p>
                      <ChevronDown className="w-3.5 h-3.5 text-[var(--text-3)]" />
                    </div>
                    <div className="flex items-center gap-1 mt-0.5">
                      <StatusIndicator status="active" pulse />
                      <span className="text-[11px] text-emerald-500 font-medium">Online</span>
                    </div>
                  </div>
                </button>

                {isAgentDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setIsAgentDropdownOpen(false)} />
                    <div className="absolute top-full left-0 mt-1.5 w-72 bg-[var(--surface)] rounded-xl shadow-lg border border-[var(--border)] overflow-hidden z-20 animate-in fade-in zoom-in-95 duration-150 origin-top-left">
                      <div className="px-3 pt-3 pb-2 border-b border-[var(--border)]">
                        <p className="text-[10.5px] font-semibold uppercase tracking-widest text-[var(--text-3)] mb-2">Switch Agent</p>
                        <button
                          onClick={() => { setSelectedAgentId(null); setIsAgentDropdownOpen(false) }}
                          className={cn(
                            "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-colors text-left",
                            "animate-in fade-in slide-in-from-top-1 fill-mode-both",
                            isSupervisorSession ? "bg-violet-50 dark:bg-violet-500/[0.08]" : "hover:bg-black/[0.04] dark:hover:bg-white/[0.05]"
                          )}
                          style={{ animationDelay: '20ms', animationDuration: '220ms' }}
                        >
                          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0">
                            <Sparkles className="w-3.5 h-3.5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-[13px] font-medium text-[var(--text-1)]">Supervisor</p>
                            <p className="text-[11px] text-[var(--text-3)] truncate">General overarching AI</p>
                          </div>
                          {isSupervisorSession && <CheckCircle2 className="w-3.5 h-3.5 text-violet-500 shrink-0" />}
                        </button>
                      </div>
                      <div className="p-2 max-h-[280px] overflow-y-auto custom-scrollbar">
                        {agents.map((agent, index) => (
                          <button
                            key={agent.id}
                            onClick={() => { setSelectedAgentId(agent.id!); setIsAgentDropdownOpen(false) }}
                            className={cn(
                              "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-colors text-left",
                              "animate-in fade-in slide-in-from-top-1 fill-mode-both",
                              selectedAgentId === agent.id ? "bg-black/[0.05] dark:bg-white/[0.07]" : "hover:bg-black/[0.03] dark:hover:bg-white/[0.04]"
                            )}
                            style={{ animationDelay: `${60 + index * 35}ms`, animationDuration: '220ms' }}
                          >
                            <AgentAvatar
                              name={agent.name}
                              avatarType={agent.avatar_type}
                              avatarValue={agent.avatar_value}
                              avatarUrl={agent.avatar_url}
                              size="xs"
                              shape="rounded"
                              className="w-7 h-7"
                            />
                            <div className="flex-1 min-w-0">
                              <p className="text-[13px] font-medium text-[var(--text-1)]">{agent.name}</p>
                              <p className="text-[11px] text-[var(--text-3)] truncate">{agent.description || 'Specific agent'}</p>
                            </div>
                            {selectedAgentId === agent.id && <CheckCircle2 className="w-3.5 h-3.5 text-violet-500 shrink-0" />}
                          </button>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-8 flex flex-col gap-5 relative z-10 scroll-smooth custom-scrollbar">
          {chat.messages.length > 0 && (
            <div className="flex justify-center mb-2">
              <span className="text-[11px] font-medium text-[var(--text-3)] px-3 py-1 bg-[var(--surface-2)] border border-[var(--border)] rounded-full">
                Session history
              </span>
            </div>
          )}

          {chat.messages.length === 0 && !chat.isTyping && (
            <div className="flex-1 flex flex-col items-center justify-center text-center animate-in fade-in duration-500">
              {isSupervisorSession ? (
                <div className="w-12 h-12 rounded-2xl bg-violet-50 dark:bg-violet-500/[0.08] border border-violet-100 dark:border-violet-500/20 flex items-center justify-center text-violet-500 mb-4">
                  <Sparkles className="w-6 h-6" />
                </div>
              ) : currentAgent ? (
                <AgentAvatar
                  name={currentAgent.name}
                  avatarType={currentAgent.avatar_type}
                  avatarValue={currentAgent.avatar_value}
                  avatarUrl={currentAgent.avatar_url}
                  size="md"
                  shape="rounded"
                  className="rounded-2xl mb-4"
                />
              ) : null}
              <p className="text-[15px] font-semibold text-[var(--text-1)] mb-1">
                {isSupervisorSession ? 'Supervisor Session' : currentAgent?.name}
              </p>
              <p className="text-[13px] text-[var(--text-3)] max-w-xs leading-relaxed">
                {isSupervisorSession
                  ? 'Send a message to start a session across all agents.'
                  : currentAgent?.description || 'Send a message to begin.'}
              </p>
            </div>
          )}

          {chat.messages.map(msg => {
            const isUser = msg.role === 'user'
            const msgAgent = (msg as any).agent_id ? agentById.get((msg as any).agent_id) : currentAgent
            const useSupervisorStyle = !(msg as any).agent_id && msg.role === 'assistant'

            return (
              <div key={msg.id} className={cn('flex gap-3 group animate-in fade-in duration-200', isUser && 'flex-row-reverse')}>
                {!isUser && (
                  useSupervisorStyle ? (
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0 mt-0.5">
                      <Sparkles className="w-3.5 h-3.5" />
                    </div>
                  ) : msgAgent ? (
                    <AgentAvatar
                      name={msgAgent.name}
                      avatarType={msgAgent.avatar_type}
                      avatarValue={msgAgent.avatar_value}
                      avatarUrl={msgAgent.avatar_url}
                      size="xs"
                      shape="rounded"
                      className="w-7 h-7 mt-0.5"
                    />
                  ) : (
                    <div className="w-7 h-7 rounded-lg bg-[var(--surface-3)] flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="w-3.5 h-3.5" />
                    </div>
                  )
                )}
                <div className={cn('max-w-[70%] flex flex-col gap-1', isUser ? 'items-end' : 'items-start')}>
                  {isUser && msg.attachments && msg.attachments.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 justify-end">
                      {msg.attachments.map((name, i) => (
                        <div
                          key={`${name}-${i}`}
                          className="flex items-center gap-1.5 max-w-[220px] bg-violet-500/10 border border-violet-500/25 rounded-lg px-2 py-1"
                        >
                          <FileText className="w-3.5 h-3.5 text-violet-500 shrink-0" />
                          <span className="text-[12px] text-[var(--text-1)] truncate" title={name}>{name}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {(msg.content || !isUser) && (
                    <div className={cn(
                      'px-4 py-3 text-[14px] leading-relaxed',
                      isUser
                        ? 'bg-violet-600 text-white rounded-2xl rounded-br-sm'
                        : 'bg-[var(--surface-2)] border border-[var(--border)] rounded-2xl rounded-bl-sm text-[var(--text-1)]'
                    )}>
                      {isUser ? (
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      ) : (
                        <Markdown content={msg.content} />
                      )}
                    </div>
                  )}
                  <div className={cn('flex items-center gap-2 px-1 opacity-0 group-hover:opacity-100 transition-opacity', isUser ? 'flex-row-reverse' : '')}>
                    <p className="text-[11px] text-[var(--text-3)]">{msg.timestamp}</p>
                    {msg.trace_id && (
                      <a
                        href="/admin/tracing"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-[11px] text-violet-500 hover:text-violet-600 transition-colors"
                      >
                        Trace <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            )
          })}

          {chat.isTyping && isImageGenAgent && chat.liveActivity?.type !== 'tool_call' && (
            <div className="flex gap-3 animate-in fade-in duration-200">
              {currentAgent ? (
                <AgentAvatar
                  name={currentAgent.name}
                  avatarType={currentAgent.avatar_type}
                  avatarValue={currentAgent.avatar_value}
                  avatarUrl={currentAgent.avatar_url}
                  size="xs"
                  shape="rounded"
                  className="w-7 h-7 mt-0.5"
                />
              ) : (
                <div className="w-7 h-7 rounded-lg bg-[var(--surface-3)] flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5" />
                </div>
              )}
              <ImageGeneration prompt={displayedPrompt || undefined} />
            </div>
          )}

          {chat.isTyping && !(isImageGenAgent && chat.liveActivity?.type !== 'tool_call') && (
            <div className="flex gap-3 animate-in fade-in duration-200">
              {isSupervisorSession ? (
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0 mt-0.5">
                  <Sparkles className="w-3.5 h-3.5" />
                </div>
              ) : currentAgent ? (
                <AgentAvatar
                  name={currentAgent.name}
                  avatarType={currentAgent.avatar_type}
                  avatarValue={currentAgent.avatar_value}
                  avatarUrl={currentAgent.avatar_url}
                  size="xs"
                  shape="rounded"
                  className="w-7 h-7 mt-0.5"
                />
              ) : (
                <div className="w-7 h-7 rounded-lg bg-[var(--surface-3)] flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5" />
                </div>
              )}
              <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2.5">
                <TypingIndicator />
                {chat.liveActivity && (
                  <span key={chat.liveActivity.label} className="text-[12px] font-medium text-violet-500 animate-pulse">
                    {chat.liveActivity.label.startsWith('Initializing')
                      ? `${chat.liveActivity.label}...`
                      : chat.liveActivity.type === 'routing'
                      ? `Routing to ${chat.liveActivity.label}...`
                      : `Querying ${chat.liveActivity.label}...`}
                  </span>
                )}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-6 pb-5 pt-3 border-t border-[var(--border)] relative z-10 bg-[var(--surface)]">
          <div className="max-w-3xl mx-auto">
            {/* Attachment chips for documents queued to send with the next message */}
            {(attachments.length > 0 || uploading) && (
              <div className="flex flex-wrap gap-2 mb-2">
                {attachments.map((att, i) => (
                  <div
                    key={`${att.filename}-${i}`}
                    className="flex items-center gap-1.5 max-w-[240px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg pl-2 pr-1 py-1"
                  >
                    {att.kind === 'image' ? (
                      <ImageIcon className="w-3.5 h-3.5 text-violet-500 shrink-0" />
                    ) : (
                      <FileText className="w-3.5 h-3.5 text-violet-500 shrink-0" />
                    )}
                    <span className="text-[12px] text-[var(--text-1)] truncate" title={att.filename}>{att.filename}</span>
                    <button
                      onClick={() => removeAttachment(i)}
                      className="w-5 h-5 flex items-center justify-center rounded text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.06] dark:hover:bg-white/[0.08] shrink-0"
                      title="Remove"
                    >
                      <XIcon className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                {uploadProgress && (
                  <div className="flex items-center gap-2 max-w-[240px] w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-2.5 py-1.5">
                    <FileText className="w-3.5 h-3.5 text-violet-500 shrink-0" />
                    <Progress
                      value={uploadProgress.percent}
                      label={uploadProgress.filename}
                      showValue={false}
                      className="min-w-0"
                    />
                  </div>
                )}
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept={FILE_ACCEPT}
              multiple
              className="hidden"
              onChange={e => handleFilesSelected(e.target.files)}
            />
            <ChatComposer
              textareaRef={inputRef}
              value={input}
              onChange={setInput}
              onSend={handleSend}
              sendDisabled={(!input.trim() && attachments.length === 0) || chat.isTyping || uploading}
              hasContent={input.trim().length > 0 || attachments.length > 0}
              onAttachClick={() => fileInputRef.current?.click()}
              attachDisabled={uploading || chat.isTyping}
              placeholder={isSupervisorSession ? 'Message supervisor...' : `Message ${currentAgent?.name ?? 'agent'}...`}
            />
            <p className="text-center text-[11px] text-[var(--text-3)] mt-2">
              <kbd className="font-mono bg-[var(--surface-2)] border border-[var(--border)] px-1 py-px rounded text-[10px]">Enter</kbd> to send
              {' · '}
              <kbd className="font-mono bg-[var(--surface-2)] border border-[var(--border)] px-1 py-px rounded text-[10px]">Shift+Enter</kbd> for new line
            </p>
          </div>
        </div>
      </div>

      <Dialog
        open={!!deleteTarget}
        onOpenChange={open => !open && setDeleteTarget(null)}
        title="Delete Chat"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete} disabled={deleting}>
              {deleting ? 'Deleting…' : 'Delete'}
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Are you sure you want to delete{' '}
          <strong>{deleteTarget?.name || 'this chat'}</strong>? This action cannot be undone.
        </p>
      </Dialog>
    </div>
  )
}
