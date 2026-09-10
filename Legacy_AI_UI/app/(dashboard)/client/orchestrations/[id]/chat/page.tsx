'use client'

import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  ArrowLeft, ArrowUp, ChevronDown, ChevronLeft, ChevronRight, GitBranch, HelpCircle,
  MessageSquare, Plus, Wrench, Check, Split, Unplug, FileText, X as XIcon, Trash2,
  Image as ImageIcon, Loader2,
} from 'lucide-react'
import { ChatComposer } from '@/components/chat/chat-composer'
import { TypingIndicator } from '@/components/ui/typing-indicator'
import { ImageGeneration } from '@/components/ui/image-generation'
import { looksLikeImageGenAgent, truncatePromptForDisplay } from '@/lib/agent-image-gen'
import { Markdown } from '@/components/ui/markdown'
import { Progress } from '@/components/ui/progress'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { orchestrationsApi } from '@/lib/api/orchestrations'
import { chatApi, type ChatAttachmentResult } from '@/lib/api/chat'
import { ConnectorAuthErrorBanner } from '@/components/connectors/reconnect-button'
import { useToast } from '@/hooks/use-toast'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'
import { useSearchParams } from 'next/navigation'
import { cn } from '@/lib/utils'
import type {
  OrchestrationPublic,
  OrchestrationRunStatus,
  OrchestrationHistoryEntry,
  OrchestrationSessionBrief,
  BranchStatusPublic,
  PendingReauthInfo,
} from '@/types'

const TERMINAL_STATUSES = ['complete', 'failed', 'timeout', 'waiting_for_human', 'waiting_for_reauth']
const MAIN_THREAD = 'main'
const MAX_SPLIT_PANELS = 4
const POLL_INTERVAL_MS = 1200
const sleep = (ms: number) => new Promise(res => setTimeout(res, ms))

const FILE_ACCEPT = [
  '.pdf', '.docx', '.xlsx', '.pptx',
  '.txt', '.md', '.markdown', '.csv', '.tsv', '.log',
  '.html', '.htm', '.xml', '.json', '.yaml', '.yml',
  '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.c', '.cpp', '.h', '.hpp',
  '.cs', '.go', '.rs', '.rb', '.php', '.sql', '.sh', '.css', '.ini', '.toml',
  'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff',
].join(',')

// ── Local message model ────────────────────────────────────────────────────────

interface UserMessage {
  kind: 'user'
  id: string
  content: string
  timestamp: string
  branchId: string
}

interface NodeMessage {
  kind: 'node'
  id: string
  nodeName: string
  toolsCalled: string[]
  content: string
  timestamp: string
  branchId: string
}

interface HitlMessage {
  kind: 'hitl'
  id: string
  question: string
  answer?: string
  nodeName: string
  timestamp: string
  branchId: string
}

interface ReauthMessage {
  kind: 'reauth'
  id: string
  connectorId: string
  displayName: string
  providerId?: string
  nodeName: string
  timestamp: string
  branchId: string
  resolved?: boolean
}

type DisplayMessage = UserMessage | NodeMessage | HitlMessage | ReauthMessage

// ── Helpers ───────────────────────────────────────────────────────────────────

const makeId = () => `${Date.now()}-${Math.random()}`
const nowLabel = () =>
  new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const fmtTimestamp = (ts: string): string => {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts
  }
}

function historyEntryToMessage(entry: OrchestrationHistoryEntry): DisplayMessage | DisplayMessage[] {
  const branchId = entry.branch_id || MAIN_THREAD

  if (entry.type === 'user_input') {
    return {
      kind: 'user',
      id: makeId(),
      content: entry.user_input,
      timestamp: fmtTimestamp(entry.timestamp),
      branchId,
    } satisfies UserMessage
  }

  if (entry.type === 'node') {
    return {
      kind: 'node',
      id: makeId(),
      nodeName: entry.node_name,
      toolsCalled: entry.tools_called ?? [],
      content: entry.node_output,
      timestamp: fmtTimestamp(entry.timestamp),
      branchId,
    } satisfies NodeMessage
  }

  return {
    kind: 'hitl',
    id: makeId(),
    question: entry.node_output,
    answer: entry.user_input,
    nodeName: entry.node_name,
    timestamp: fmtTimestamp(entry.timestamp),
    branchId,
  } satisfies HitlMessage
}

function threadLabel(branchId: string, messages: DisplayMessage[], branchStatuses: BranchStatusPublic[]): string {
  if (branchId === MAIN_THREAD) return 'Main'
  const branch = branchStatuses.find(b => b.branch_id === branchId)
  if (branch?.label) return branch.label
  const first = messages.find(m => m.branchId === branchId && (m.kind === 'node' || m.kind === 'hitl' || m.kind === 'reauth'))
  if (first && (first.kind === 'node' || first.kind === 'hitl' || first.kind === 'reauth')) return first.nodeName
  return `Branch ${branchId.slice(0, 6)}`
}

// ── Message renderer (shared by merged view and split panels) ─────────────────

function stepKey(step: OrchestrationRunStatus['steps'][number], index?: number): string {
  const branchId = step.branch_id || MAIN_THREAD
  const stableId = (step as any).id || (step as any).step_id
  if (stableId) return `${stableId}-${branchId}`
  // Fall back to a content hash. Includes started_at (if present) to reduce
  // collisions when array ordering shifts between polls across branches.
  const startedAt = (step as any).started_at || ''
  return `${step.agent_id}-${step.agent_name}-${branchId}-${startedAt}-${step.output?.slice(0, 80) || ''}`
}

function MessageBubble({ msg, onReconnected }: { msg: DisplayMessage; onReconnected?: (branchId: string) => void }) {
  if (msg.kind === 'user') {
    return (
      <div className="flex gap-3 group animate-in fade-in duration-200 flex-row-reverse">
        <div className="max-w-[80%] flex flex-col gap-1 items-end">
          <div className="px-4 py-3 text-[14px] leading-relaxed bg-violet-600 text-white rounded-2xl rounded-br-sm">
            <div className="whitespace-pre-wrap">{msg.content}</div>
          </div>
          <p className="text-[11px] text-[var(--text-3)] px-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {msg.timestamp}
          </p>
        </div>
      </div>
    )
  }

  if (msg.kind === 'node') {
    return (
      <div className="flex gap-3 group animate-in fade-in duration-200">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0 mt-0.5">
          <GitBranch className="w-3.5 h-3.5" />
        </div>
        <div className="max-w-[80%] flex flex-col gap-1 items-start">
          {msg.toolsCalled.length > 0 && (
            <div className="flex flex-wrap gap-1 px-1">
              {msg.toolsCalled.map((tool, index) => (
                <span
                  key={`${tool}-${index}`}
                  className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-violet-100 dark:bg-violet-500/15 text-violet-600 dark:text-violet-300 border border-violet-200 dark:border-violet-500/30"
                >
                  <Wrench className="w-2.5 h-2.5" />
                  {tool}
                </span>
              ))}
            </div>
          )}
          <div className="px-4 py-3 text-[14px] leading-relaxed bg-[var(--surface-2)] border border-[var(--border)] rounded-2xl rounded-bl-sm text-[var(--text-1)]">
            <Markdown content={msg.content} />
          </div>
          <p className="text-[11px] text-[var(--text-3)] px-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {msg.nodeName} · {msg.timestamp}
          </p>
        </div>
      </div>
    )
  }

  if (msg.kind === 'reauth') {
    return (
      <div className="flex gap-3 group animate-in fade-in duration-200">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white shrink-0 mt-0.5">
          <Unplug className="w-3.5 h-3.5" />
        </div>
        <div className="max-w-[80%] flex flex-col gap-1 items-start">
          <p className="text-[11px] font-semibold text-amber-500 px-1 uppercase tracking-wide">
            {msg.nodeName} needs a connector reconnected
          </p>
          {msg.resolved ? (
            <div className="px-4 py-3 text-[14px] leading-relaxed bg-[var(--surface-2)] border border-[var(--border)] rounded-2xl rounded-bl-sm text-[var(--text-2)]">
              {msg.displayName} reconnected — continuing…
            </div>
          ) : (
            <ConnectorAuthErrorBanner
              errors={[{ connector_id: msg.connectorId, provider_id: msg.providerId, display_name: msg.displayName }]}
              onReconnected={() => onReconnected?.(msg.branchId)}
            />
          )}
        </div>
      </div>
    )
  }

  // hitl
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-3 group animate-in fade-in duration-200">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white shrink-0 mt-0.5">
          <HelpCircle className="w-3.5 h-3.5" />
        </div>
        <div className="max-w-[80%] flex flex-col gap-1 items-start">
          <p className="text-[11px] font-semibold text-amber-500 px-1 uppercase tracking-wide">
            {msg.nodeName} needs your input
          </p>
          <div className="px-4 py-3 text-[14px] leading-relaxed bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-2xl rounded-bl-sm text-[var(--text-1)]">
            <Markdown content={msg.question} />
          </div>
          <p className="text-[11px] text-[var(--text-3)] px-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {msg.timestamp}
          </p>
        </div>
      </div>
      {msg.answer && msg.answer.trim() !== '' && (
        <div className="flex gap-3 group flex-row-reverse">
          <div className="max-w-[80%] flex flex-col gap-1 items-end">
            <div className="px-4 py-3 text-[14px] leading-relaxed bg-violet-600 text-white rounded-2xl rounded-br-sm">
              <div className="whitespace-pre-wrap">{msg.answer}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatusDot({ status }: { status?: string }) {
  const color =
    status === 'waiting_for_human' ? 'bg-amber-400' :
      status === 'waiting_for_reauth' ? 'bg-orange-400' :
        status === 'running' ? 'bg-cyan-400 animate-pulse' :
          status === 'complete' ? 'bg-emerald-400' :
            status === 'failed' ? 'bg-red-400' :
              'bg-[var(--text-3)]'
  return <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', color)} />
}

// ── Single conversation panel (used both unsplit, and per-thread when split) ──

function InlineBranchInput({
  branchId,
  disabled,
  onSend,
}: {
  branchId: string
  disabled?: boolean
  onSend: (text: string, branchId: string) => void
}) {
  const [value, setValue] = useState('')
  const send = () => {
    if (disabled) return
    const t = value.trim()
    if (!t) return
    onSend(t, branchId)
    setValue('')
  }
  return (
    <div className="flex items-end gap-2">
      <textarea
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
        placeholder="Type your answer..."
        rows={1}
        disabled={disabled}
        className="flex-1 bg-[var(--surface)] border border-amber-300 dark:border-amber-500/40 rounded-lg px-2.5 py-1.5 text-[13px] resize-none outline-none min-h-[20px] max-h-[100px] disabled:opacity-50"
      />
      <button
        onClick={send}
        disabled={disabled || !value.trim()}
        className={cn("w-7 h-7 rounded-md flex items-center justify-center shrink-0", value.trim() && !disabled ? "bg-amber-500 hover:bg-amber-600 text-white" : "bg-black/[0.05] dark:bg-white/[0.07] text-[var(--text-3)]")}
      >
        <ArrowUp className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

function ThreadPanel({
  branchId,
  label,
  branchStatus,
  messages,
  isTyping,
  currentAgent,
  onSend,
  onReconnected,
  compact,
}: {
  branchId: string
  label: string
  branchStatus?: BranchStatusPublic
  messages: DisplayMessage[]
  isTyping: boolean
  currentAgent: string | null
  onSend: (text: string, branchId: string) => void
  onReconnected: (branchId: string) => void
  compact: boolean
}) {
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const isWaiting = branchStatus?.status === 'waiting_for_human'
  const isReauthWaiting = branchStatus?.status === 'waiting_for_reauth'

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`
  }, [input])

  const send = () => {
    const text = input.trim()
    if (!text) return
    onSend(text, branchId)
    setInput('')
  }

  return (
    <div className="flex flex-col min-h-0 flex-1 border border-[var(--border)] rounded-xl overflow-hidden bg-[var(--surface)]">
      <div className="h-10 px-3 flex items-center gap-2 border-b border-[var(--border)] shrink-0 bg-[var(--surface-2)]">
        <StatusDot status={branchStatus?.status} />
        <p className="text-[12px] font-semibold text-[var(--text-1)] truncate">{label}</p>
      </div>

      <div className={cn("flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-4", compact ? "px-3 py-4" : "px-6 py-6")}>
        {messages.length === 0 && !isTyping && (
          <div className="flex-1 flex items-center justify-center text-center">
            <p className="text-[12px] text-[var(--text-3)]">No messages in this thread yet.</p>
          </div>
        )}
        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} onReconnected={onReconnected} />)}
        {isTyping && (branchStatus?.status === 'running' || branchStatus?.status === 'waiting_for_human' || (!branchStatus && branchId === MAIN_THREAD)) && (
          looksLikeImageGenAgent(currentAgent) ? (
            <div className="flex gap-3 animate-in fade-in duration-200">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0 mt-0.5">
                <GitBranch className="w-3.5 h-3.5" />
              </div>
              <ImageGeneration
                prompt={truncatePromptForDisplay(
                  [...messages].reverse().find((m): m is UserMessage => m.kind === 'user')?.content
                ) || undefined}
              />
            </div>
          ) : (
            <div className="flex gap-3 animate-in fade-in duration-200">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0 mt-0.5">
                <GitBranch className="w-3.5 h-3.5" />
              </div>
              <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2.5">
                <TypingIndicator />
                {currentAgent && (
                  <span className="text-[12px] font-medium text-violet-500 animate-pulse">{currentAgent}...</span>
                )}
              </div>
            </div>
          )
        )}
        <div ref={endRef} />
      </div>

      <div className="px-3 pb-3 pt-2 border-t border-[var(--border)] shrink-0 bg-[var(--surface)]">
        {isReauthWaiting ? (
          <>
            <div className="flex items-center gap-1.5 mb-1.5 px-0.5">
              <Unplug className="w-3 h-3 text-amber-500 shrink-0" />
              <p className="text-[11px] text-amber-500 font-medium">A connector needs to be reconnected to continue this thread.</p>
            </div>
            <ConnectorAuthErrorBanner
              errors={[{
                connector_id: branchStatus?.pending_reauth?.connector_id,
                provider_id: branchStatus?.pending_reauth?.provider_id,
                display_name: branchStatus?.pending_reauth?.display_name,
              }]}
              onReconnected={() => onReconnected(branchId)}
            />
          </>
        ) : isWaiting ? (
          <>
            <div className="flex items-center gap-1.5 mb-1.5 px-0.5">
              <HelpCircle className="w-3 h-3 text-amber-500 shrink-0" />
              <p className="text-[11px] text-amber-500 font-medium">Waiting for your answer to continue this thread.</p>
            </div>
            <div className="bg-[var(--surface-2)] border border-amber-300 dark:border-amber-500/40 rounded-lg px-3 py-2 flex items-end gap-2 focus-within:ring-2 focus-within:ring-amber-500/20">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder="Type your answer..."
                rows={1}
                className="flex-1 bg-transparent text-[13px] text-[var(--text-1)] placeholder:text-[var(--text-3)] resize-none outline-none min-h-[20px] max-h-[140px] py-0.5"
              />
              <button
                onClick={send}
                disabled={!input.trim()}
                className={cn(
                  "w-7 h-7 rounded-md flex items-center justify-center shrink-0 transition-colors",
                  input.trim() ? "bg-amber-500 hover:bg-amber-600 text-white" : "bg-black/[0.05] dark:bg-white/[0.07] text-[var(--text-3)]"
                )}
              >
                <ArrowUp className="w-3.5 h-3.5" />
              </button>
            </div>
          </>
        ) : (
          <p className="text-[11px] text-[var(--text-3)] text-center py-1">
            {branchStatus?.status === 'complete' ? 'This thread has finished.'
              : branchStatus?.status === 'failed' ? 'This thread failed.'
                : 'This thread is running — nothing to answer right now.'}
          </p>
        )}
      </div>
    </div>
  )
}

// ── Thread picker dropdown (header) ────────────────────────────────────────────

function ThreadPicker({
  threads,
  selected,
  onToggle,
  onClear,
}: {
  threads: { id: string; label: string; status?: string }[]
  selected: string[]
  onToggle: (id: string) => void
  onClear: () => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const filteredThreads = threads.filter(t => t.id !== MAIN_THREAD)

  if (filteredThreads.length === 0) return null

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className={cn(
          "flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-[12px] font-medium border transition-colors",
          selected.length > 0
            ? "border-violet-300 dark:border-violet-500/40 bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-300"
            : "border-[var(--border)] text-[var(--text-2)] hover:bg-black/[0.04] dark:hover:bg-white/[0.05]"
        )}
      >
        <Split className="w-3.5 h-3.5" />
        {selected.length > 0 ? `${selected.length} thread${selected.length > 1 ? 's' : ''}` : 'Threads'}
        <ChevronDown className="w-3 h-3" />
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-30 w-72 bg-[var(--surface)] rounded-xl shadow-lg border border-[var(--border)] overflow-hidden animate-in fade-in zoom-in-95 duration-150 origin-top-right">
          <div className="px-3 pt-3 pb-2 border-b border-[var(--border)] flex items-center justify-between">
            <p className="text-[10.5px] font-semibold uppercase tracking-widest text-[var(--text-3)]">
              Split view · up to {MAX_SPLIT_PANELS}
            </p>
            {selected.length > 0 && (
              <button onClick={onClear} className="text-[11px] text-violet-500 hover:text-violet-600">Clear</button>
            )}
          </div>
          <div className="p-2 max-h-72 overflow-y-auto custom-scrollbar">
            {filteredThreads.map(t => {
              const checked = selected.includes(t.id)
              const disabled = !checked && selected.length >= MAX_SPLIT_PANELS
              return (
                <button
                  key={t.id}
                  disabled={disabled}
                  onClick={() => onToggle(t.id)}
                  className={cn(
                    "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-colors text-left",
                    disabled ? "opacity-40 cursor-not-allowed" : "hover:bg-black/[0.03] dark:hover:bg-white/[0.04]",
                    checked && "bg-violet-50 dark:bg-violet-500/[0.08]"
                  )}
                >
                  <StatusDot status={t.status} />
                  <span className="flex-1 min-w-0 text-[13px] font-medium text-[var(--text-1)] truncate">{t.label}</span>
                  {checked && <Check className="w-3.5 h-3.5 text-violet-500 shrink-0" />}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function OrchestrationChatPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const { toast } = useToast()

  const [orch, setOrch] = useState<OrchestrationPublic | null>(null)
  useBreadcrumbLabel(id, orch?.name)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const searchParams = useSearchParams()
  const [sessionId, setSessionId] = useState<string | undefined>(
    () => searchParams.get('session') || undefined
  )
  const [hitlRunId, setHitlRunId] = useState<string | null>(null)
  const [reauthRunId, setReauthRunId] = useState<string | null>(null)
  const [currentAgent, setCurrentAgent] = useState<string | null>(null)
  const [sessions, setSessions] = useState<OrchestrationSessionBrief[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [branchStatuses, setBranchStatuses] = useState<BranchStatusPublic[]>([])
  const [selectedThreads, setSelectedThreads] = useState<string[]>([])
  const [branchMessages, setBranchMessages] = useState<Record<string, DisplayMessage[]>>({})
  const [activeRun, setActiveRun] = useState<string | null>(null)
  // Resuming a paused run (HITL answer, reauth, branch resume) reuses the
  // SAME run_id — setActiveRun(sameValue) is a no-op to React, so the poller
  // effect (keyed on activeRun) would never restart after the first pause.
  // Bumping this alongside setActiveRun forces the effect to re-run every
  // time, regardless of whether the run_id actually changed.
  const [pollGen, setPollGen] = useState(0)
  const restartPolling = (runId: string) => {
    finalizedRunsRef.current.delete(runId)
    setActiveRun(runId)
    setPollGen(g => g + 1)
  }
  const [branchTyping, setBranchTyping] = useState<Record<string, boolean>>({})
  const [attachments, setAttachments] = useState<ChatAttachmentResult[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{ filename: string; percent: number } | null>(null)
  const [deleteSessionTarget, setDeleteSessionTarget] = useState<OrchestrationSessionBrief | null>(null)
  const [deletingSession, setDeletingSession] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    if (mq.matches) setSidebarOpen(false)
  }, [])

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const isMountedRef = useRef(true)
  const renderedStepIndexesRef = useRef<Set<string>>(new Set())
  const historyLoadedRef = useRef(false)

  // Tracks the last-seen status per branch_id so the single poller below can
  // detect *which* branches changed on each tick and refetch only those —
  // this is what lets newly-spawned or sibling-completed branches (that
  // weren't the one the user just answered) pick up their messages without
  // requiring a manual page reload.
  const branchStatusSnapshotRef = useRef<Record<string, string>>({})
  // Prevents double-pushing the final/HITL message for a run that keeps
  // returning the same terminal status while we're still finishing up.
  const finalizedRunsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    isMountedRef.current = true
    return () => { isMountedRef.current = false }
  }, [])

  useEffect(() => {
    if (!messagesEndRef.current) return
    messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const [agentsPreloading, setAgentsPreloading] = useState(false)

  useEffect(() => {
    orchestrationsApi.get(id).then(setOrch).catch(() => toast.error('Failed to load orchestration'))
    refreshSessions()
  }, [id])

  // Pre-load session & warm up agents when opening a new chat window without session_id
  useEffect(() => {
    if (!id || sessionId) return
    setAgentsPreloading(true)
    orchestrationsApi.init(id)
      .then(res => {
        if (res.session_id) {
          setSessionId(res.session_id)
        }
      })
      .catch(() => { })
      .finally(() => setAgentsPreloading(false))
  }, [id, sessionId])

  const refreshSessions = useCallback(() => {
    setSessionsLoading(true)
    orchestrationsApi.listSessions(id)
      .then(res => setSessions(res.sessions))
      .catch(() => { })
      .finally(() => setSessionsLoading(false))
  }, [id])

  const handleDeleteSession = (e: React.MouseEvent, session: OrchestrationSessionBrief) => {
    e.stopPropagation()
    setDeleteSessionTarget(session)
  }

  const confirmDeleteSession = async () => {
    if (!deleteSessionTarget) return
    const sid = deleteSessionTarget.session_id
    setDeletingSession(true)
    try {
      await orchestrationsApi.deleteSession(id, sid)
      if (sessionId === sid) handleNewSession()
      setSessions(prev => prev.filter(s => s.session_id !== sid))
      setDeleteSessionTarget(null)
    } catch (err: any) {
      toast.error(err?.message || 'Failed to delete session')
    } finally {
      setDeletingSession(false)
    }
  }

  useEffect(() => {
    if (!sessionId || historyLoadedRef.current) return
    historyLoadedRef.current = true

    const loadHistory = async () => {
      try {
        const res = await orchestrationsApi.getSessionHistory(id, sessionId)
        if (!isMountedRef.current) return
        const loaded: DisplayMessage[] = []

        for (const entry of res.conversations ?? []) {
          const converted = historyEntryToMessage(entry)
          if (Array.isArray(converted)) loaded.push(...converted)
          else loaded.push(converted)
        }
        setMessages(loaded)

        if (res.pending_branches && res.pending_branches.length > 0) {
          setBranchStatuses(res.pending_branches)
          res.pending_branches.forEach(b => {
            branchStatusSnapshotRef.current[b.branch_id] = b.status
          })
        }

        const lastEntry = res.conversations?.at(-1)
        let runIdToSeed: string | null = null

        if (
          (!res.pending_branches || res.pending_branches.length === 0) &&
          lastEntry?.type === 'hitl' && !lastEntry.user_input && res.pending_run_id
        ) {
          setHitlRunId(res.pending_run_id)
          setActiveRun(res.pending_run_id)
          runIdToSeed = res.pending_run_id
        } else if (res.pending_run_id) {
          setActiveRun(res.pending_run_id)
          setHitlRunId(res.pending_run_id)
          runIdToSeed = res.pending_run_id
        }

        if (runIdToSeed) {
          try {
            const status = await orchestrationsApi.runStatus(id, runIdToSeed)
            for (const step of status.steps || []) {
              if (step.status === 'complete') {
                renderedStepIndexesRef.current.add(stepKey(step))
              }
            }
            // Seed branch messages for any branches already loaded from history
            // so the single poller below doesn't treat them as "new" and
            // re-fetch/re-render them from scratch on its first tick.
            ; (status.branches || []).forEach(b => {
              branchStatusSnapshotRef.current[b.branch_id] = b.status
            })
          } catch {
            // best-effort
          }
        }
      } catch {
        // ignore
      }
    }

    loadHistory()
  }, [id, sessionId])

  const pushMessage = useCallback((msg: DisplayMessage) =>
    setMessages(prev => [...prev, msg]), [])

  const pushBranchMessage = useCallback((msg: DisplayMessage) => {
    setBranchMessages(prev => {
      const existing = prev[msg.branchId] || []
      if (existing.some(m => m.id === msg.id)) return prev
      return { ...prev, [msg.branchId]: [...existing, msg] }
    })
  }, [])

  const renderNewSteps = useCallback((steps: OrchestrationRunStatus['steps']) => {
    steps.forEach((step, index) => {
      const branchId = step.branch_id || MAIN_THREAD
      const key = stepKey(step, index)

      if (renderedStepIndexesRef.current.has(key)) return
      // Only real turns render. This also excludes supervisor-mode 'handback'
      // steps — an agent telling the Supervisor "not my domain" is an internal
      // control transfer, not a message. /status filters them out as well; this
      // is the second line of defence, so keep the allowlist explicit rather
      // than widening it to "anything but running".
      if (step.status !== 'complete' && step.status !== 'running') return

      renderedStepIndexesRef.current.add(key)

      if (step.output && step.output.trim()) {
        const msg: DisplayMessage = {
          kind: 'node',
          id: makeId(),
          nodeName: step.agent_name,
          toolsCalled: [],
          content: step.output,
          timestamp: nowLabel(),
          branchId,
        }
        if (branchId === MAIN_THREAD) {
          pushMessage(msg)
        }
        pushBranchMessage(msg)
      }
    })
  }, [pushMessage, pushBranchMessage])

  // Refetch a branch's full message history from the backend. Used whenever
  // the single poller notices a branch's status changed — this is what
  // catches sibling branches completing, or brand-new branches spawning,
  // as a side effect of resuming a *different* branch.
  const refetchBranchMessages = useCallback(async (branchId: string) => {
    if (!sessionId || branchId === MAIN_THREAD) return
    try {
      const res = await orchestrationsApi.getBranchMessages(id, sessionId, branchId)
      const msgs: DisplayMessage[] = []
      for (const entry of res.conversations ?? []) {
        const converted = historyEntryToMessage(entry)
        if (Array.isArray(converted)) msgs.push(...converted)
        else msgs.push(converted)
      }
      setBranchMessages(prev => ({ ...prev, [branchId]: msgs }))
    } catch (e) {
      console.warn('Failed to refresh branch messages for', branchId, e)
    }
  }, [id, sessionId])

  // ── The single poller ─────────────────────────────────────────────────────
  // Everything that needs to react to run progress goes through this one
  // effect. handleSend/handleSendToBranch only kick off a run and set
  // activeRun; they never poll themselves, so there's exactly one interval
  // ever in flight for a given run.
  useEffect(() => {
    if (!activeRun) return
    let cancelled = false

    const finalize = async (status: OrchestrationRunStatus) => {
      if (finalizedRunsRef.current.has(activeRun)) return
      finalizedRunsRef.current.add(activeRun)

      if (status.status === 'waiting_for_human') {
        setHitlRunId(status.run_id)
        pushMessage({
          kind: 'hitl',
          id: makeId(),
          question: status.human_question || 'The agent needs your input.',
          nodeName: status.current_agent_name || 'Agent',
          timestamp: nowLabel(),
          branchId: MAIN_THREAD,
        })
      } else if (status.status === 'waiting_for_reauth') {
        setReauthRunId(status.run_id)
        pushMessage({
          kind: 'reauth',
          id: makeId(),
          connectorId: status.pending_reauth?.connector_id || '',
          displayName: status.pending_reauth?.display_name || 'A connector',
          providerId: status.pending_reauth?.provider_id || undefined,
          nodeName: status.current_agent_name || 'Agent',
          timestamp: nowLabel(),
          branchId: MAIN_THREAD,
        })
      } else if (status.status === 'complete') {
        setHitlRunId(null)
        setReauthRunId(null)
        if (sessionId) {
          try {
            const res = await orchestrationsApi.getSessionHistory(id, sessionId)
            const loaded: DisplayMessage[] = []
            for (const entry of res.conversations ?? []) {
              const converted = historyEntryToMessage(entry)
              if (Array.isArray(converted)) loaded.push(...converted)
              else loaded.push(converted)
            }
            setMessages(loaded)
          } catch {
            if (status.final_response) {
              pushMessage({
                kind: 'node',
                id: makeId(),
                nodeName: status.current_agent_name || 'Orchestration',
                toolsCalled: [],
                content: status.final_response,
                timestamp: nowLabel(),
                branchId: MAIN_THREAD,
              })
            }
          }

          if (status.branches && status.branches.length > 0) {
            await Promise.all(status.branches.map(b => refetchBranchMessages(b.branch_id)))
          }
        } else if (status.final_response) {
          pushMessage({
            kind: 'node',
            id: makeId(),
            nodeName: status.current_agent_name || 'Orchestration',
            toolsCalled: [],
            content: status.final_response,
            timestamp: nowLabel(),
            branchId: MAIN_THREAD,
          })
        }
      } else {
        setHitlRunId(null)
        setReauthRunId(null)
        const msg = status.status === 'timeout'
          ? 'The orchestration timed out.'
          : status.status === 'failed'
            ? 'The orchestration failed. Please try again.'
            : 'The orchestration is taking longer than expected. Please check back shortly.'
        pushMessage({
          kind: 'node',
          id: makeId(),
          nodeName: 'Orchestration',
          toolsCalled: [],
          content: msg,
          timestamp: nowLabel(),
          branchId: MAIN_THREAD,
        })
        if (status.status !== 'waiting_for_human') toast.error(msg)
      }

      refreshSessions()
      setIsTyping(false)
      setBranchTyping({})
    }

    const poll = async () => {
      const maxMs = (orch?.timeout_sec || 600) * 1000 + 15_000
      const startedAt = Date.now()

      while (!cancelled && isMountedRef.current) {
        let status: OrchestrationRunStatus
        try {
          status = await orchestrationsApi.runStatus(id, activeRun)
        } catch {
          await sleep(1500)
          continue
        }
        if (cancelled) break

        renderNewSteps(status.steps || [])
        setCurrentAgent(status.current_agent_name || null)

        const newBranches = status.branches || []
        setBranchStatuses(newBranches)

        // Diff against the last-seen status per branch. Any branch whose
        // status changed (or that's brand new) gets its messages refetched —
        // not just the branch the user happened to resume.
        const changedBranchIds: string[] = []
        for (const b of newBranches) {
          const prevStatus = branchStatusSnapshotRef.current[b.branch_id]
          if (prevStatus !== b.status) {
            changedBranchIds.push(b.branch_id)
            branchStatusSnapshotRef.current[b.branch_id] = b.status
          }
        }
        if (changedBranchIds.length > 0) {
          await Promise.all(changedBranchIds.map(bid => refetchBranchMessages(bid)))
          // A branch that just started running/waiting is no longer "sending".
          setBranchTyping(prev => {
            const next = { ...prev }
            changedBranchIds.forEach(bid => { next[bid] = false })
            return next
          })
        }

        const anyActive = newBranches.some(b => b.status === 'running')
        const runTerminal = TERMINAL_STATUSES.includes(status.status)
        const isDone = newBranches.length > 0 ? (runTerminal && !anyActive) : runTerminal

        if (isDone) {
          await finalize(status)
          break
        }

        if (Date.now() - startedAt > maxMs) {
          await finalize(status)
          break
        }

        await sleep(POLL_INTERVAL_MS)
      }
    }

    poll()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRun, pollGen])

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [input])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || isTyping || branchesActive) return
    setInput('')

    const userMsg: DisplayMessage = {
      kind: 'user',
      id: makeId(),
      content: text,
      timestamp: nowLabel(),
      branchId: MAIN_THREAD,
    }

    if (!hitlRunId) {
      pushMessage(userMsg)
    } else {
      setMessages(prev => {
        const updated = [...prev]
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].kind === 'hitl') {
            const hitlMsg = updated[i] as HitlMessage
            updated[i] = { ...hitlMsg, answer: text }
            break
          }
        }
        return updated
      })
    }

    setIsTyping(true)
    setCurrentAgent(null)
    const pendingAttachments = attachments
    setAttachments([])

    try {
      const isNewSession = !sessionId
      const start = hitlRunId
        ? await orchestrationsApi.resume(id, hitlRunId, text)
        : await orchestrationsApi.chat(id, text, sessionId, pendingAttachments)

      if (!sessionId && start.session_id) setSessionId(start.session_id)
      const runId = start.run_id || hitlRunId
      if (!runId) throw new Error('No run_id returned from the server.')

      if (isNewSession) {
        renderedStepIndexesRef.current = new Set()
        branchStatusSnapshotRef.current = {}
      }
      restartPolling(runId) // the single poller effect takes it from here
    } catch (err: any) {
      toast.error(err?.message || 'Failed to get response')
      pushMessage({
        kind: 'node',
        id: makeId(),
        nodeName: 'Orchestration',
        toolsCalled: [],
        content: 'An error occurred. Please try again.',
        timestamp: nowLabel(),
        branchId: MAIN_THREAD,
      })
      setIsTyping(false)
    }
  }

  const handleSendToBranch = async (text: string, branchId: string) => {
    if (!activeRun) return
    const userMsg: DisplayMessage = { kind: 'user', id: makeId(), content: text, timestamp: nowLabel(), branchId }
    if (branchId === MAIN_THREAD) {
      pushMessage(userMsg)
    } else {
      pushBranchMessage(userMsg)
    }
    setBranchTyping(prev => ({ ...prev, [branchId]: true }))

    try {
      const resumed = await orchestrationsApi.resume(id, activeRun, text, branchId)
      const newRunId = resumed.run_id || activeRun
      if (newRunId !== activeRun) renderedStepIndexesRef.current = new Set()
      restartPolling(newRunId) // always restart — resuming reuses the same run_id
      // The single poller effect (keyed on activeRun/pollGen) picks up this
      // branch's progress, refetches its messages on status change, and
      // refetches any *other* branch that changes as a side effect (new
      // spawns, sibling joins) too.
    } catch (err: any) {
      toast.error(err?.message || 'Failed to send answer to thread')
      setBranchTyping(prev => ({ ...prev, [branchId]: false }))
    }
  }

  // Called once ConnectorAuthErrorBanner reports the connector is reconnected
  // (main thread or a branch). There's no "answer" to send — just retry the
  // paused agent now that its tool call should succeed.
  const handleReauthResolved = async (branchId: string) => {
    setMessages(prev => prev.map(m =>
      m.kind === 'reauth' && m.branchId === branchId ? { ...m, resolved: true } : m
    ))
    setBranchMessages(prev => {
      const existing = prev[branchId]
      if (!existing) return prev
      return {
        ...prev,
        [branchId]: existing.map(m => (m.kind === 'reauth' ? { ...m, resolved: true } : m)),
      }
    })

    if (branchId === MAIN_THREAD) {
      if (!reauthRunId) return
      setIsTyping(true)
      try {
        const resumed = await orchestrationsApi.resume(id, reauthRunId, '')
        const runId = resumed.run_id || reauthRunId
        setReauthRunId(null)
        restartPolling(runId)
      } catch (err: any) {
        toast.error(err?.message || 'Failed to resume after reconnecting')
        setIsTyping(false)
      }
    } else {
      if (!activeRun) return
      setBranchTyping(prev => ({ ...prev, [branchId]: true }))
      try {
        const resumed = await orchestrationsApi.resume(id, activeRun, '', branchId)
        const newRunId = resumed.run_id || activeRun
        if (newRunId !== activeRun) renderedStepIndexesRef.current = new Set()
        restartPolling(newRunId)
      } catch (err: any) {
        toast.error(err?.message || 'Failed to resume thread after reconnecting')
        setBranchTyping(prev => ({ ...prev, [branchId]: false }))
      }
    }
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
          toast.info(`"${result.filename}" was long — attached the first ${(result.chars ?? 0).toLocaleString()} characters.`)
        }
      } catch (e: any) {
        toast.error(e?.message || `Could not attach "${file.name}"`)
      }
    }
    setUploading(false)
    setUploadProgress(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const removeAttachment = (idx: number) =>
    setAttachments(prev => prev.filter((_, i) => i !== idx))

  const handleNewSession = () => {
    setSessionId(undefined)
    setHitlRunId(null)
    setReauthRunId(null)
    setCurrentAgent(null)
    setMessages([])
    setBranchMessages({})
    setBranchStatuses([])
    setSelectedThreads([])
    setActiveRun(null)
    setBranchTyping({})
    renderedStepIndexesRef.current = new Set()
    branchStatusSnapshotRef.current = {}
    historyLoadedRef.current = false
  }

  const handleSelectSession = (sid: string) => {
    if (sid === sessionId) return
    setMessages([])
    setBranchMessages({})
    setSessionId(sid)
    setHitlRunId(null)
    setReauthRunId(null)
    setCurrentAgent(null)
    setBranchStatuses([])
    setSelectedThreads([])
    setActiveRun(null)
    setBranchTyping({})
    renderedStepIndexesRef.current = new Set()
    branchStatusSnapshotRef.current = {}
    historyLoadedRef.current = false
  }

  // ── Thread derivation ─────────────────────────────────────────────────────

  const availableThreads = useMemo(() => {
    const ids = new Set<string>()
    messages.forEach(m => { if (m.branchId !== MAIN_THREAD) ids.add(m.branchId) })
    branchStatuses.forEach(b => ids.add(b.branch_id))
    return Array.from(ids).map(bid => ({
      id: bid,
      label: threadLabel(bid, branchMessages[bid] || messages, branchStatuses),
      status: branchStatuses.find(b => b.branch_id === bid)?.status,
    }))
  }, [messages, branchStatuses, branchMessages])

  const toggleThread = (tid: string) => {
    setSelectedThreads(prev => {
      if (prev.includes(tid)) return prev.filter(x => x !== tid)
      if (prev.length >= MAX_SPLIT_PANELS) return prev
      const next = [...prev, tid]
      if (next.length > 0) setSidebarOpen(false)
      return next
    })
  }

  const isSplit = selectedThreads.length > 0
  const hasWaitingBranches = branchStatuses.some(b => b.status === 'waiting_for_human')
  const hasReauthBranches = branchStatuses.some(b => b.status === 'waiting_for_reauth')
  const branchesActive = branchStatuses.some(b =>
    b.status === 'running' || b.status === 'waiting_for_human' || b.status === 'waiting_for_reauth'
  )

  // Fetch messages for any newly-selected thread that we don't have yet.
  // (Ongoing refetches for status changes are handled by the single poller.)
  useEffect(() => {
    if (!sessionId || selectedThreads.length === 0) return
    const missing = selectedThreads.filter(tid => tid !== MAIN_THREAD && !branchMessages[tid])
    if (missing.length === 0) return
    Promise.all(missing.map(tid => refetchBranchMessages(tid)))
  }, [sessionId, selectedThreads, branchMessages, refetchBranchMessages])

  return (
    <div className="relative flex flex-1 min-h-0 overflow-hidden bg-[var(--surface)] font-sans text-[var(--text-1)]">

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
        "max-md:absolute max-md:inset-y-0 max-md:left-0",
        sidebarOpen ? "w-[272px]" : "w-0",
        !sidebarOpen && "max-md:hidden"
      )}>
        <div className="h-14 px-3 flex items-center gap-2 border-b border-[var(--border)] shrink-0 w-[272px]">
          <button
            onClick={handleNewSession}
            className="flex-1 flex items-center justify-center gap-1.5 h-8 bg-violet-600 hover:bg-violet-700 active:bg-violet-800 text-white text-[13px] font-medium rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New Session
          </button>
          <button
            onClick={() => setSidebarOpen(false)}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.06] transition-colors shrink-0"
            title="Collapse sidebar"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center justify-between px-4 pt-5 pb-1.5 w-[272px]">
          <span className="text-[10.5px] font-semibold tracking-widest text-[var(--text-3)] uppercase">History</span>
          {!sessionsLoading && sessions.length > 0 && (
            <span className="text-[11px] tabular-nums text-[var(--text-3)]">{sessions.length}</span>
          )}
        </div>

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
            sessions.map(s => {
              const active = s.session_id === sessionId
              return (
                <div
                  key={s.session_id}
                  className={cn(
                    'relative w-full px-3 py-2 flex items-center gap-2 rounded-lg transition-colors cursor-pointer group',
                    active ? 'bg-violet-50 dark:bg-violet-500/[0.08]' : 'hover:bg-black/[0.04] dark:hover:bg-white/[0.04]'
                  )}
                  onClick={() => handleSelectSession(s.session_id)}
                >
                  {active && <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-violet-500 rounded-r-full" />}
                  <div className="flex-1 min-w-0">
                    <p className={cn(
                      "text-[13px] font-medium truncate leading-snug transition-colors",
                      active ? "text-violet-700 dark:text-violet-300" : "text-[var(--text-2)] group-hover:text-[var(--text-1)]"
                    )}>
                      {s.name || 'Untitled session'}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={e => handleDeleteSession(e, s)}
                    title="Delete session"
                    className="p-1 rounded opacity-0 group-hover:opacity-100 shrink-0 hover:bg-red-50 dark:hover:bg-red-500/[0.12] text-[var(--text-3)] hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* ── Chat Area ───────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative bg-[var(--surface)]">

        <div className="h-14 flex items-center justify-between px-4 border-b border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-sm shrink-0 relative z-20">
          <div className="flex items-center gap-1.5 min-w-0">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.06] transition-colors shrink-0"
                title="Expand sidebar"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => router.push('/client/orchestrations')}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.06] transition-colors shrink-0"
              title="Back to orchestrations"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2.5 px-2.5 py-1.5 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0">
                <GitBranch className="w-4 h-4" />
              </div>
              <div className="text-left min-w-0">
                <p className="text-[14px] font-semibold text-[var(--text-1)] leading-tight truncate">
                  {orch?.name || 'Orchestration'}
                </p>
                <p className="text-[11px] text-[var(--text-3)] mt-0.5">
                  {!orch
                    ? 'Loading…'
                    : orch.mode === 'supervisor'
                      // Supervisor mode has no connections to count — routing is
                      // decided per request, not drawn.
                      ? `Supervisor · ${orch.agents.length} ${orch.agents.length === 1 ? 'agent' : 'agents'}`
                      : `${orch.agents.length} agents · ${orch.connections.length} connections`}
                </p>
              </div>
            </div>
          </div>

          <ThreadPicker
            threads={availableThreads}
            selected={selectedThreads}
            onToggle={toggleThread}
            onClear={() => setSelectedThreads([])}
          />
        </div>

        {isSplit ? (
          <>
            {hasWaitingBranches === false && branchStatuses.length === 0 && (
              <div className="px-4 pt-3">
                <p className="text-[11px] text-[var(--text-3)]">
                  Showing {selectedThreads.length} thread{selectedThreads.length > 1 ? 's' : ''} side by side.
                </p>
              </div>
            )}
            <div className={cn(
              "flex-1 min-h-0 grid gap-3 p-3",
              selectedThreads.length === 1 && "grid-cols-1",
              selectedThreads.length === 2 && "grid-cols-2",
              selectedThreads.length === 3 && "grid-cols-3",
              selectedThreads.length === 4 && "grid-cols-2 grid-rows-2",
            )}>
              {selectedThreads.map(tid => {
                const threadMessages = tid === MAIN_THREAD
                  ? messages.filter(m => m.branchId === MAIN_THREAD)
                  : (branchMessages[tid] || messages.filter(m => m.branchId === tid))

                const branchIsTyping = tid === MAIN_THREAD ? isTyping : (branchTyping[tid] ?? false)

                return (
                  <ThreadPanel
                    key={tid}
                    branchId={tid}
                    label={threadLabel(tid, threadMessages, branchStatuses)}
                    branchStatus={branchStatuses.find(b => b.branch_id === tid)}
                    messages={threadMessages}
                    isTyping={branchIsTyping}
                    currentAgent={currentAgent}
                    onSend={handleSendToBranch}
                    onReconnected={handleReauthResolved}
                    compact
                  />
                )
              })}
            </div>
          </>
        ) : (
          <>
            {/* Merged single-column view (default) */}
            <div className="flex-1 overflow-y-auto px-6 py-8 flex flex-col gap-5 relative z-10 scroll-smooth custom-scrollbar">
              {messages.length > 0 && (
                <div className="flex justify-center mb-2">
                  <span className="text-[11px] font-medium text-[var(--text-3)] px-3 py-1 bg-[var(--surface-2)] border border-[var(--border)] rounded-full">
                    Session history
                  </span>
                </div>
              )}

              {agentsPreloading && messages.length === 0 && (
                <div className="flex-1 flex flex-col items-center justify-center text-center animate-in fade-in duration-300">
                  <div className="w-12 h-12 rounded-2xl bg-violet-50 dark:bg-violet-500/[0.08] border border-violet-100 dark:border-violet-500/20 flex items-center justify-center text-violet-500 mb-4">
                    <Loader2 className="w-6 h-6 animate-spin text-violet-500 stroke-[2.5]" />
                  </div>
                  <p className="text-[15px] font-semibold text-[var(--text-1)] mb-1">Loading agents...</p>
                  <p className="text-[13px] text-[var(--text-3)] max-w-xs leading-relaxed">
                    Initializing agent graph topology and tools. You will be able to message in a moment.
                  </p>
                </div>
              )}

              {messages.length === 0 && !isTyping && !agentsPreloading && (
                <div className="flex-1 flex flex-col items-center justify-center text-center animate-in fade-in duration-500">
                  <div className="w-12 h-12 rounded-2xl bg-violet-50 dark:bg-violet-500/[0.08] border border-violet-100 dark:border-violet-500/20 flex items-center justify-center text-violet-500 mb-4">
                    <GitBranch className="w-6 h-6" />
                  </div>
                  <p className="text-[15px] font-semibold text-[var(--text-1)] mb-1">{orch?.name}</p>
                  <p className="text-[13px] text-[var(--text-3)] max-w-xs leading-relaxed">
                    Send a message to start an orchestrated multi-agent session.
                  </p>
                </div>
              )}

              {messages.filter(m => m.branchId === MAIN_THREAD).map(msg => (
                <MessageBubble key={msg.id} msg={msg} onReconnected={handleReauthResolved} />
              ))}

              {isTyping && (
                looksLikeImageGenAgent(currentAgent) ? (
                  <div className="flex gap-3 animate-in fade-in duration-200">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0 mt-0.5">
                      <GitBranch className="w-3.5 h-3.5" />
                    </div>
                    <ImageGeneration
                      prompt={truncatePromptForDisplay(
                        [...messages].reverse().find((m): m is UserMessage => m.branchId === MAIN_THREAD && m.kind === 'user')?.content
                      ) || undefined}
                    />
                  </div>
                ) : (
                  <div className="flex gap-3 animate-in fade-in duration-200">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shrink-0 mt-0.5">
                      <GitBranch className="w-3.5 h-3.5" />
                    </div>
                    <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2.5">
                      <TypingIndicator />
                      {currentAgent && (
                        <span className="text-[12px] font-medium text-violet-500 animate-pulse">{currentAgent} is working…</span>
                      )}
                    </div>
                  </div>
                )
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="px-6 pb-5 pt-3 border-t border-[var(--border)] relative z-10 bg-[var(--surface)]">
              <div className="max-w-3xl mx-auto">
                {branchesActive ? (
                  hasWaitingBranches || hasReauthBranches ? (
                    <div className="space-y-2">
                      {branchStatuses.filter(b => b.status === 'waiting_for_human').map(b => (
                        <div key={b.branch_id} className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-xl px-3 py-2.5">
                          <div className="flex items-center gap-2 mb-1.5">
                            <HelpCircle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                            <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wide">
                              {threadLabel(b.branch_id, branchMessages[b.branch_id] || messages.filter(m => m.branchId === b.branch_id), branchStatuses)} needs your input
                            </p>
                          </div>
                          <InlineBranchInput
                            branchId={b.branch_id}
                            disabled={branchTyping[b.branch_id]}
                            onSend={handleSendToBranch}
                          />
                        </div>
                      ))}
                      {branchStatuses.filter(b => b.status === 'waiting_for_reauth').map(b => (
                        <div key={b.branch_id} className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-xl px-3 py-2.5">
                          <div className="flex items-center gap-2 mb-1.5">
                            <Unplug className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                            <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wide">
                              {threadLabel(b.branch_id, branchMessages[b.branch_id] || messages.filter(m => m.branchId === b.branch_id), branchStatuses)} needs a connector reconnected
                            </p>
                          </div>
                          <ConnectorAuthErrorBanner
                            errors={[{
                              connector_id: b.pending_reauth?.connector_id,
                              provider_id: b.pending_reauth?.provider_id,
                              display_name: b.pending_reauth?.display_name,
                            }]}
                            onReconnected={() => handleReauthResolved(b.branch_id)}
                          />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 bg-[var(--surface-2)] border border-[var(--border)] rounded-xl px-4 py-3">
                      <TypingIndicator />
                      <p className="text-[12px] text-[var(--text-3)]">
                        Branches are still running — the main chat will unlock once they finish.
                      </p>
                    </div>
                  )
                ) : (
                  <>
                    {hitlRunId && (
                      <div className="flex items-center gap-2 mb-2 px-1">
                        <HelpCircle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                        <p className="text-[12px] text-amber-500 font-medium">Your reply will be sent directly to the paused agent — the pipeline will continue from where it stopped.</p>
                      </div>
                    )}
                    {reauthRunId && (
                      <div className="flex items-center gap-2 mb-2 px-1">
                        <Unplug className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                        <p className="text-[12px] text-amber-500 font-medium">Reconnect the connector above to continue, or send a message to retry.</p>
                      </div>
                    )}
                    {(attachments.length > 0 || uploadProgress) && (
                      <div className="flex flex-wrap items-center gap-1.5 mb-2 px-0.5">
                        {attachments.map((a, i) => (
                          <div
                            key={`${a.filename}-${i}`}
                            className="inline-flex items-center gap-1.5 max-w-[220px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg pl-2 pr-1 py-1 text-[11px]"
                            title={a.filename}
                          >
                            {a.kind === 'image' ? (
                              <ImageIcon className="w-3 h-3 text-violet-500 shrink-0" />
                            ) : (
                              <FileText className="w-3 h-3 text-violet-500 shrink-0" />
                            )}
                            <span className="truncate text-[var(--text-2)]">{a.filename}</span>
                            <button
                              onClick={() => removeAttachment(i)}
                              className="w-4 h-4 rounded flex items-center justify-center text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.06] dark:hover:bg-white/[0.08] shrink-0"
                            >
                              <XIcon className="w-2.5 h-2.5" />
                            </button>
                          </div>
                        ))}
                        {uploadProgress && (
                          <div className="flex items-center gap-2 max-w-[220px] w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-2.5 py-1.5">
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
                      disabled={agentsPreloading}
                      sendDisabled={isTyping || branchesActive}
                      onAttachClick={() => fileInputRef.current?.click()}
                      attachDisabled={uploading || isTyping || !!hitlRunId || agentsPreloading}
                      attachTitle={hitlRunId ? 'Answer the pending question before attaching a new file' : 'Attach a file (PDF, Office, text, code, or image)'}
                      placeholder={
                        agentsPreloading
                          ? 'Loading agents...'
                          : hitlRunId
                          ? 'Type your answer to continue the pipeline…'
                          : `Message ${orch?.name || 'the orchestration'}...`
                      }
                      tone={hitlRunId ? 'warning' : 'default'}
                    />
                  </>
                )}
                <p className="text-center text-[11px] text-[var(--text-3)] mt-2">
                  <kbd className="font-mono bg-[var(--surface-2)] border border-[var(--border)] px-1 py-px rounded text-[10px]">Enter</kbd> to send
                  {' · '}
                  <kbd className="font-mono bg-[var(--surface-2)] border border-[var(--border)] px-1 py-px rounded text-[10px]">Shift+Enter</kbd> for new line
                </p>
              </div>
            </div>
          </>
        )}
      </div>

      <Dialog
        open={!!deleteSessionTarget}
        onOpenChange={open => !open && setDeleteSessionTarget(null)}
        title="Delete Session"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteSessionTarget(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDeleteSession} disabled={deletingSession}>
              Delete
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Are you sure you want to delete{' '}
          <strong>{deleteSessionTarget?.name || 'this session'}</strong>? This will remove its
          conversation history and cannot be undone.
        </p>
      </Dialog>
    </div>
  )
}