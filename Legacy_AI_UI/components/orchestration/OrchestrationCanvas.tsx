'use client'

import {
  useCallback,
  useEffect,
  useState,
  useRef,
  useMemo,
  type DragEvent,
} from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  BackgroundVariant,
  MiniMap,
  MarkerType,
  useReactFlow,
  type Connection,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  ArrowLeft,
  Plus,
  Save,
  MessageSquare,
  Loader2,
  Settings2,
  UserPlus,
  Info,
  Network,
  X,
  Maximize2,
  Minimize2,
  Eye,
  Compass,
  GitBranch,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Select } from '@/components/ui/select'
import { agentsApi } from '@/lib/api/agents'
import { orchestrationsApi } from '@/lib/api/orchestrations'
import { useToast } from '@/hooks/use-toast'
import { useTheme } from '@/contexts/theme-context'
import { useAuth } from '@/contexts/auth-context'
import { useUsers } from '@/hooks/use-users'
import { useTeams } from '@/hooks/use-teams'
import { agentVisibilityLabel } from '@/lib/utils'
import { AgentNode, type AgentNodeData } from './AgentNode'
import { SupervisorNode, type SupervisorNodeData } from './SupervisorNode'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import type {
  AgentPublic,
  AgentBriefPublic,
  AgentConnectionOut,
  OrchestrationMode,
  OrchestrationPublic,
  SupervisorConfig,
} from '@/types'

type OwnerScope = 'user' | 'organization' | 'selected_users' | 'team'

// ── Constants ──────────────────────────────────────────────────────────────────

const nodeTypes = { agentNode: AgentNode, supervisorNode: SupervisorNode }

/** Canvas-only id for the Supervisor. It is never sent to the API: the
 *  Supervisor is hardcoded in the backend, not an agent document, so it must be
 *  excluded from `sub_agent_ids` on save. */
const SUPERVISOR_NODE_ID = '__supervisor__'

const DEFAULT_SUPERVISOR_CONFIG: SupervisorConfig = {
  max_hops: 6,
  max_visits_per_agent: 3,
  max_consecutive_handbacks: 2,
  sticky_routing: true,
  allow_direct_answer: true,
  custom_instructions: '',
  model: null,
}

/** Supervisor-mode layout: the Supervisor on the left, every agent in a column
 *  to its right. There are no edges to lay out — routing is dynamic. */
function supervisorLayout(agentIds: string[]): Record<string, { x: number; y: number }> {
  const NODE_H = 140
  const V_GAP = 24
  const total = agentIds.length * NODE_H + Math.max(0, agentIds.length - 1) * V_GAP
  const startY = 260 - total / 2
  const positions: Record<string, { x: number; y: number }> = {
    [SUPERVISOR_NODE_ID]: { x: 60, y: 240 },
  }
  agentIds.forEach((id, i) => {
    positions[id] = { x: 400, y: startY + i * (NODE_H + V_GAP) }
  })
  return positions
}

function makeSupervisorNode(agentCount: number, position?: { x: number; y: number }): Node {
  const data: SupervisorNodeData = { agentCount }
  return {
    id: SUPERVISOR_NODE_ID,
    type: 'supervisorNode',
    position: position ?? { x: 60, y: 240 },
    data,
    deletable: false,
  }
}

const defaultEdgeOptions = {
  type: 'smoothstep',
  animated: true,
  style: { stroke: '#7c3aed', strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, color: '#7c3aed' },
  labelStyle: { fontSize: 11, fontWeight: 600, fill: '#7c3aed' },
  labelBgStyle: { fill: 'var(--surface)', fillOpacity: 0.9 },
  labelBgPadding: [4, 2] as [number, number],
  labelBgBorderRadius: 4,
}

// ── Layout ──────────────────────────────────────────────────────────────────────

function autoLayout(
  mainId: string,
  agentIds: string[],
  connections: AgentConnectionOut[],
): Record<string, { x: number; y: number }> {
  if (agentIds.length === 0) return {}

  const NODE_W = 220
  const NODE_H = 140
  const H_GAP = 80
  const V_GAP = 24

  const adj: Record<string, Set<string>> = {}
  agentIds.forEach(id => { adj[id] = new Set() })
  connections.forEach(c => {
    if (adj[c.from_agent_id]) adj[c.from_agent_id].add(c.to_agent_id)
  })

  const levels: Record<string, number> = {}
  const visited = new Set<string>()
  const queue: string[] = []
  const start = agentIds.includes(mainId) ? mainId : agentIds[0]
  levels[start] = 0
  visited.add(start)
  queue.push(start)

  while (queue.length) {
    const curr = queue.shift()!
    for (const next of adj[curr] ?? []) {
      if (!visited.has(next)) {
        visited.add(next)
        levels[next] = levels[curr] + 1
        queue.push(next)
      }
    }
  }
  agentIds.forEach(id => { if (levels[id] === undefined) levels[id] = 0 })

  const groups: Record<number, string[]> = {}
  agentIds.forEach(id => {
    const l = levels[id]
    if (!groups[l]) groups[l] = []
    groups[l].push(id)
  })

  const positions: Record<string, { x: number; y: number }> = {}
  Object.entries(groups).forEach(([ls, ids]) => {
    const level = Number(ls)
    const x = 60 + level * (NODE_W + H_GAP)
    const total = ids.length * NODE_H + (ids.length - 1) * V_GAP
    const startY = 260 - total / 2
    ids.forEach((id, i) => {
      positions[id] = { x, y: startY + i * (NODE_H + V_GAP) }
    })
  })
  return positions
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface OrchestrationCanvasProps {
  orchestrationId?: string
  initialName?: string
  initialDescription?: string
  initialOrch?: OrchestrationPublic
  orgAgents: AgentPublic[]
  orgId: string
  onBack: () => void
  onSaved: (orch: OrchestrationPublic) => void
  onChat?: () => void
}

// ── Create Agent Modal ──────────────────────────────────────────────────────────

function CreateAgentModal({
  orgId,
  onCreated,
  onClose,
}: {
  orgId: string
  onCreated: (agent: AgentPublic) => void
  onClose: () => void
}) {
  const { toast } = useToast()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [prompt, setPrompt] = useState('')
  const [guardrails, setGuardrails] = useState('')
  const [loading, setLoading] = useState(false)

  const handleCreate = async () => {
    if (!name.trim()) { toast.error('Agent name is required'); return }
    setLoading(true)
    try {
      const agent = await agentsApi.create({
        organization_id: orgId,
        name: name.trim(),
        description: description.trim() || undefined,
        prompt: prompt.trim(),
        guardrails: guardrails.trim(),
      })
      toast.success(`Agent "${agent.name}" created`)
      onCreated(agent)
    } catch (err: any) {
      toast.error(err?.message || 'Failed to create agent')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fadeIn fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="animate-scaleIn w-full max-w-md mx-4 bg-[var(--surface)] rounded-2xl border border-[var(--border)] shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-[var(--border)]">
          <h2 className="text-[16px] font-bold text-[var(--text-1)]">Create New Agent</h2>
          <button onClick={onClose} className="p-1 rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--surface-3)] transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 space-y-4">
          <div className="space-y-1">
            <label className="text-[12px] font-semibold text-[var(--text-2)]">Name *</label>
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Research Agent" className="rounded-xl" />
          </div>
          <div className="space-y-1">
            <label className="text-[12px] font-semibold text-[var(--text-2)]">Description</label>
            <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="What does this agent do?" className="rounded-xl" />
          </div>
          <div className="space-y-1">
            <label className="text-[12px] font-semibold text-[var(--text-2)]">System Prompt</label>
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              rows={4}
              placeholder="You are a helpful assistant..."
              className="w-full text-[13px] bg-[var(--surface-2)] border border-[var(--border)] rounded-xl px-3 py-2.5 text-[var(--text-1)] placeholder:text-[var(--text-3)] outline-none focus:ring-2 focus:ring-violet-500/30 resize-none"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[12px] font-semibold text-[var(--text-2)]">Guardrails</label>
            <Input value={guardrails} onChange={e => setGuardrails(e.target.value)} placeholder="Optional safety constraints" className="rounded-xl" />
          </div>
        </div>
        <div className="flex gap-3 p-5 pt-0">
          <Button variant="outline" onClick={onClose} className="flex-1 rounded-xl">Cancel</Button>
          <Button
            onClick={handleCreate}
            disabled={loading}
            className="flex-1 pl-3 pr-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-xl"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <span className="mr-1 flex size-5 items-center justify-center rounded-full bg-white/20">
                <Plus className="w-3 h-3" />
              </span>
            )}
            {loading ? 'Creating…' : 'Create'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── Settings Popover ───────────────────────────────────────────────────────────

function EdgeLabelPanel({
  edge,
  onChange,
  onClose,
}: {
  edge: Edge
  onChange: (label: string) => void
  onClose: () => void
}) {
  const [value, setValue] = useState((edge.label as string) || '')

  return (
    <div className="animate-scaleIn origin-top absolute top-4 left-1/2 -translate-x-1/2 z-30 w-72 bg-[var(--surface)] rounded-2xl border border-[var(--border)] shadow-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-bold text-[var(--text-1)]">Branch Label</span>
        <button onClick={onClose} className="p-0.5 text-[var(--text-3)] hover:text-[var(--text-1)]">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="space-y-1">
        <Input
          value={value}
          onChange={e => setValue(e.target.value)}
          onBlur={() => onChange(value)}
          onKeyDown={e => { if (e.key === 'Enter') { onChange(value); onClose() } }}
          placeholder="e.g. Research path"
          className="rounded-xl text-[13px]"
          autoFocus
        />
        <p className="text-[11px] text-[var(--text-3)]">
          Shown as this branch's name during fan-out runs. Leave blank to use the agent's name.
        </p>
      </div>
    </div>
  )
}

function VisibilityPopover({
  ownerScope,
  teamId,
  allowedUserIds,
  orgUsers,
  orgTeams,
  userSearch,
  onUserSearchChange,
  onChange,
  onClose,
}: {
  ownerScope: OwnerScope
  teamId: string
  allowedUserIds: string[]
  orgUsers: { id?: string; name: string; email: string }[]
  orgTeams: { id?: string; name: string }[]
  userSearch: string
  onUserSearchChange: (val: string) => void
  onChange: (patch: { ownerScope?: OwnerScope; teamId?: string; allowedUserIds?: string[] }) => void
  onClose: () => void
}) {
  const filteredUsers = orgUsers.filter(u =>
    `${u.name} ${u.email}`.toLowerCase().includes(userSearch.toLowerCase())
  )

  return (
    <div className="animate-scaleIn origin-top-right absolute right-0 top-12 z-30 w-72 bg-[var(--surface)] rounded-2xl border border-[var(--border)] shadow-xl p-4 space-y-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[13px] font-bold text-[var(--text-1)]">Visibility</span>
        <button onClick={onClose} className="p-0.5 text-[var(--text-3)] hover:text-[var(--text-1)]">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="space-y-1">
        <Select
          value={ownerScope}
          onValueChange={v => onChange({ ownerScope: v as OwnerScope })}
          className="rounded-xl text-[13px]"
          options={[
            { value: 'organization', label: 'Organization — visible to everyone in the org' },
            { value: 'selected_users', label: 'Selected users — visible to specific people only' },
            { value: 'team', label: 'Team — visible to members of a specific team' },
            { value: 'user', label: 'Personal — only visible to you' },
          ]}
        />
      </div>

      {ownerScope === 'team' && (
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-[var(--text-2)] uppercase tracking-wider">Team</label>
          <Select
            value={teamId}
            onValueChange={v => onChange({ teamId: v })}
            className="rounded-xl text-[13px]"
            options={orgTeams.map(t => ({ value: t.id!, label: t.name }))}
            placeholder="Select a team"
          />
          {orgTeams.length === 0 && (
            <p className="text-[11px] text-[var(--text-3)]">No teams yet in this organization.</p>
          )}
        </div>
      )}

      {ownerScope === 'selected_users' && (
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-[var(--text-2)] uppercase tracking-wider">
            Visible to ({allowedUserIds.length} selected)
          </label>
          <SearchInput
            value={userSearch}
            onChange={e => onUserSearchChange(e.target.value)}
            placeholder="Search users..."
          />
          <div className="max-h-40 overflow-y-auto space-y-1 border border-[var(--border)] rounded-xl p-1.5">
            {filteredUsers.length === 0 ? (
              <p className="text-[11px] text-[var(--text-3)] p-2">No other users found.</p>
            ) : (
              filteredUsers.map(u => {
                const selected = allowedUserIds.includes(u.id!)
                return (
                  <label key={u.id} className="flex items-center gap-2 p-1.5 rounded-lg cursor-pointer hover:bg-[var(--surface-2)]">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => onChange({
                        allowedUserIds: selected
                          ? allowedUserIds.filter(id => id !== u.id)
                          : [...allowedUserIds, u.id!],
                      })}
                      className="w-3.5 h-3.5 accent-violet-600"
                    />
                    <span className="text-[12px] text-[var(--text-1)] truncate">{u.name}</span>
                    <span className="text-[11px] text-[var(--text-3)] truncate">{u.email}</span>
                  </label>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function SettingsPopover({
  maxDepth,
  timeoutSec,
  supervised,
  supervisorConfig,
  onChange,
  onSupervisorChange,
  onClose,
}: {
  maxDepth: number
  timeoutSec: number
  supervised: boolean
  supervisorConfig: SupervisorConfig
  onChange: (key: 'maxDepth' | 'timeoutSec', val: number) => void
  onSupervisorChange: (patch: Partial<SupervisorConfig>) => void
  onClose: () => void
}) {
  return (
    <div className="animate-scaleIn origin-top-right absolute right-0 top-12 z-30 w-72 max-h-[70vh] overflow-y-auto custom-scrollbar bg-[var(--surface)] rounded-2xl border border-[var(--border)] shadow-xl p-4 space-y-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[13px] font-bold text-[var(--text-1)]">Safety Settings</span>
        <button onClick={onClose} className="p-0.5 text-[var(--text-3)] hover:text-[var(--text-1)]">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Max depth bounds nested calls along drawn edges — meaningless when the
          Supervisor routes dynamically, where max_hops plays that role. */}
      {!supervised && (
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-[var(--text-2)] uppercase tracking-wider">Max Depth (1-20)</label>
          <Input
            type="number" min={1} max={20} value={maxDepth}
            onChange={e => onChange('maxDepth', Number(e.target.value))}
            className="rounded-xl text-[13px]"
          />
          <p className="text-[11px] text-[var(--text-3)]">Max nested agent calls</p>
        </div>
      )}

      <div className="space-y-1">
        <label className="text-[11px] font-semibold text-[var(--text-2)] uppercase tracking-wider">Timeout (seconds)</label>
        <Input
          type="number" min={10} max={3600} value={timeoutSec}
          onChange={e => onChange('timeoutSec', Number(e.target.value))}
          className="rounded-xl text-[13px]"
        />
        <p className="text-[11px] text-[var(--text-3)]">Total run time limit</p>
      </div>

      {supervised && (
        <div className="space-y-4 pt-3 border-t border-[var(--border)]">
          <span className="text-[13px] font-bold text-[var(--text-1)]">Supervisor</span>

          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-[var(--text-2)] uppercase tracking-wider">Max Agents Per Turn (1-50)</label>
            <Input
              type="number" min={1} max={50} value={supervisorConfig.max_hops}
              onChange={e => onSupervisorChange({ max_hops: Number(e.target.value) })}
              className="rounded-xl text-[13px]"
            />
            <p className="text-[11px] text-[var(--text-3)]">
              How many agents one request may pass through
            </p>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-[var(--text-2)] uppercase tracking-wider">Max Declines In A Row (1-10)</label>
            <Input
              type="number" min={1} max={10} value={supervisorConfig.max_consecutive_handbacks}
              onChange={e => onSupervisorChange({ max_consecutive_handbacks: Number(e.target.value) })}
              className="rounded-xl text-[13px]"
            />
            <p className="text-[11px] text-[var(--text-3)]">
              An agent given a request outside its domain hands it back to the
              Supervisor. This caps how many may decline before giving up.
            </p>
          </div>

          <label className="flex items-start gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={supervisorConfig.sticky_routing}
              onChange={e => onSupervisorChange({ sticky_routing: e.target.checked })}
              className="mt-0.5 accent-violet-600"
            />
            <span className="space-y-0.5">
              <span className="block text-[12px] font-medium text-[var(--text-1)]">
                Prefer the last agent
              </span>
              <span className="block text-[11px] text-[var(--text-3)]">
                Tell the Supervisor who handled the previous turn, so it favours
                them while the topic hasn't changed.
              </span>
            </span>
          </label>

          <label className="flex items-start gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={supervisorConfig.allow_direct_answer}
              onChange={e => onSupervisorChange({ allow_direct_answer: e.target.checked })}
              className="mt-0.5 accent-violet-600"
            />
            <span className="space-y-0.5">
              <span className="block text-[12px] font-medium text-[var(--text-1)]">
                Let the Supervisor answer directly
              </span>
              <span className="block text-[11px] text-[var(--text-3)]">
                Allows short replies to greetings and off-topic messages without
                routing. Turn off to make the Supervisor route or decline only.
              </span>
            </span>
          </label>

          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-[var(--text-2)] uppercase tracking-wider">Routing Instructions</label>
            <textarea
              value={supervisorConfig.custom_instructions}
              onChange={e => onSupervisorChange({ custom_instructions: e.target.value })}
              rows={3}
              placeholder="e.g. Prefer the HR agent for anything about people."
              className="w-full px-3 py-2 text-[12px] bg-[var(--surface-2)] border border-[var(--border)] rounded-xl outline-none focus:ring-2 focus:ring-violet-500/30 text-[var(--text-1)] placeholder:text-[var(--text-3)] resize-none"
            />
            <p className="text-[11px] text-[var(--text-3)]">
              Optional guidance added to the Supervisor's routing prompt
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Canvas Inner (uses RF hooks — must be inside ReactFlowProvider) ────────────

interface CanvasInnerProps extends OrchestrationCanvasProps {
  initNodes: Node[]
  initEdges: Edge[]
  allOrgAgents: AgentPublic[]
  initialMaxDepth: number
  initialTimeoutSec: number
  initialOwnerScope: OwnerScope
  initialAllowedUserIds: string[]
  initialTeamId: string
  initialMode: OrchestrationMode
  initialSupervisorConfig: SupervisorConfig
}

function CanvasInner({
  orchestrationId,
  initialName = '',
  initialDescription = '',
  initialMaxDepth,
  initialTimeoutSec,
  initialOwnerScope,
  initialAllowedUserIds,
  initialTeamId,
  initialMode,
  initialSupervisorConfig,
  initNodes,
  initEdges,
  allOrgAgents: initialOrgAgents,
  orgId,
  onBack,
  onSaved,
  onChat,
}: CanvasInnerProps) {
  const { toast } = useToast()
  const { theme } = useTheme()
  const { user } = useAuth()
  const { screenToFlowPosition } = useReactFlow()

  const isSuperAdmin = user?.role === 'super_admin' || user?.role === 'super admin'
  const isOrgAdmin = user?.role === 'org_admin' || user?.role === 'org admin' || user?.role === 'admin'
  const isOrgManager = user?.role === 'org_manager' || user?.role === 'org manager'
  const canChooseVisibility = isSuperAdmin || isOrgAdmin || isOrgManager

  const containerRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    const onFullscreenChange = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange)
  }, [])

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      containerRef.current?.requestFullscreen()
    }
  }, [])

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)
  const [name, setName] = useState(initialName)
  const [description, setDescription] = useState(initialDescription)
  const [mode, setMode] = useState<OrchestrationMode>(initialMode)
  const [supervisorConfig, setSupervisorConfig] = useState<SupervisorConfig>(initialSupervisorConfig)
  const supervised = mode === 'supervisor'
  const [maxDepth, setMaxDepth] = useState(initialMaxDepth)
  const [timeoutSec, setTimeoutSec] = useState(initialTimeoutSec)
  const [ownerScope, setOwnerScope] = useState<OwnerScope>(initialOwnerScope)
  const [allowedUserIds, setAllowedUserIds] = useState<string[]>(initialAllowedUserIds)
  const [teamId, setTeamId] = useState(initialTeamId)
  const [userSearch, setUserSearch] = useState('')
  const [saving, setSaving] = useState(false)
  const [search, setSearch] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [showVisibility, setShowVisibility] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)

  const effectiveOwnerScope = canChooseVisibility ? ownerScope : 'user'
  const { data: orgUsersData } = useUsers(1, orgId || undefined, undefined, undefined, 100, {}, canChooseVisibility)
  const orgUsers = (orgUsersData?.items ?? []).filter(u => u.id !== user?.id)
  const { data: orgTeamsData } = useTeams(1, orgId || undefined, undefined, 100, canChooseVisibility)
  const orgTeams = orgTeamsData?.items ?? []
  // Keep newly-created agents separate so we can merge them with the live prop
  const [extraAgents, setExtraAgents] = useState<AgentPublic[]>([])
  // allOrgAgents is a live prop — merging with extraAgents ensures the panel
  // updates both when the parent's API call resolves AND when the user creates
  // a new agent inline
  const orgAgents = useMemo(
    () => [...initialOrgAgents, ...extraAgents],
    [initialOrgAgents, extraAgents],
  )

  const canvasNodeIds = useMemo(() => new Set(nodes.map(n => n.id)), [nodes])

  const panelAgents = useMemo(
    () =>
      orgAgents.filter(
        a =>
          !canvasNodeIds.has(a.id!) &&
          (!search || a.name.toLowerCase().includes(search.toLowerCase())),
      ),
    [orgAgents, canvasNodeIds, search],
  )
  const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    setSelectedEdgeId(edge.id)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedEdgeId(null)
  }, [])

  const updateEdgeLabel = useCallback((edgeId: string, label: string) => {
    setEdges(eds => eds.map(e => e.id === edgeId ? { ...e, label, data: { ...e.data, label } } : e))
  }, [setEdges])

  const selectedEdge = edges.find(e => e.id === selectedEdgeId) || null

  // ── Connection handling ──────────────────────────────────────────────────────

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const isValidConnection = useCallback(
    (connection: any): boolean => {
      if (connection.source === connection.target) return false
      return !edges.some(
        (e: Edge) => e.source === connection.source && e.target === connection.target,
      )
    },
    [edges],
  )

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges(eds => addEdge(connection, eds))
    },
    [setEdges],
  )

  // ── Drag-from-panel ──────────────────────────────────────────────────────────

  const onDragStart = (e: DragEvent, agent: AgentPublic) => {
    e.dataTransfer.setData('agentId', agent.id!)
    e.dataTransfer.setData('agentName', agent.name)
    e.dataTransfer.setData('agentDesc', agent.description || '')
    e.dataTransfer.effectAllowed = 'move'
  }

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const addAgentToCanvas = useCallback(
    (agent: AgentPublic, position?: { x: number; y: number }) => {
      setNodes(nds => {
        if (nds.some(n => n.id === agent.id)) return nds // already on canvas

        const existingAgents = nds.filter(n => n.id !== SUPERVISOR_NODE_ID)
        const resolvedPosition =
          position ??
          (supervised
            ? // Stack to the right of the Supervisor rather than from the origin.
              { x: 400, y: 140 + existingAgents.length * 164 }
            : {
                // Cascading grid fallback for click-to-add, where there's no drop
                // coordinate to place the node at.
                x: 100 + (nds.length % 4) * 220,
                y: 100 + Math.floor(nds.length / 4) * 140,
              })
        const nodeData: AgentNodeData = {
          name: agent.name,
          description: agent.description || undefined,
          // The first agent added is the entry point by default — but in
          // supervisor mode the Supervisor already is.
          isMain: !supervised && existingAgents.length === 0,
          supervised,
        }
        const newNode: Node = {
          id: agent.id!,
          type: 'agentNode',
          position: resolvedPosition,
          data: nodeData,
        }
        return [...nds, newNode]
      })
    },
    [setNodes, supervised],
  )

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault()
      const agentId = e.dataTransfer.getData('agentId')
      const agentName = e.dataTransfer.getData('agentName')
      const agentDesc = e.dataTransfer.getData('agentDesc')
      if (!agentId) return

      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      addAgentToCanvas({ id: agentId, name: agentName, description: agentDesc || undefined } as AgentPublic, position)
    },
    [screenToFlowPosition, addAgentToCanvas],
  )

  // ── Mode ──────────────────────────────────────────────────────────────────────

  const agentNodes = useMemo(() => nodes.filter(n => n.id !== SUPERVISOR_NODE_ID), [nodes])

  /** Switching mode restructures the canvas, because the two modes mean
   *  different things: sequential is a graph you draw, supervisor is a roster the
   *  Supervisor routes across. Going supervisor therefore drops the edges. */
  const changeMode = useCallback((next: OrchestrationMode) => {
    if (next === mode) return
    if (next === 'supervisor') {
      const agents = nodes.filter(n => n.id !== SUPERVISOR_NODE_ID)
      if (edges.length > 0 &&
          !window.confirm(
            'Supervisor mode routes each request dynamically, so the connections you drew ' +
            'no longer apply and will be removed. Continue?',
          )) {
        return
      }
      const positions = supervisorLayout(agents.map(n => n.id))
      setEdges([])
      setSelectedEdgeId(null)
      setNodes([
        makeSupervisorNode(agents.length, positions[SUPERVISOR_NODE_ID]),
        ...agents.map(n => ({ ...n, position: positions[n.id] ?? n.position })),
      ])
    } else {
      setNodes(nds => nds.filter(n => n.id !== SUPERVISOR_NODE_ID))
    }
    setMode(next)
  }, [mode, nodes, edges.length, setNodes, setEdges])

  // Keep the Supervisor node's agent count in step as agents come and go.
  useEffect(() => {
    if (!supervised) return
    setNodes(nds => {
      const count = nds.filter(n => n.id !== SUPERVISOR_NODE_ID).length
      return nds.map(n =>
        n.id === SUPERVISOR_NODE_ID && (n.data as SupervisorNodeData).agentCount !== count
          ? { ...n, data: { ...n.data, agentCount: count } }
          : n,
      )
    })
  }, [supervised, nodes.length, setNodes])

  // ── Save ──────────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!name.trim()) { toast.error('Name is required'); return }
    const mainNode = nodes.find(n => (n.data as unknown as AgentNodeData).isMain)
    if (!supervised && !mainNode) {
      toast.error('Mark an agent as the Entry Point before saving')
      return
    }
    if (supervised && agentNodes.length === 0) {
      toast.error('Connect at least one agent for the Supervisor to route to')
      return
    }
    if (canChooseVisibility && ownerScope === 'selected_users' && allowedUserIds.length === 0) {
      toast.error('Select at least one user for the Visibility setting')
      return
    }
    if (canChooseVisibility && ownerScope === 'team' && !teamId) {
      toast.error('Select a team for the Visibility setting')
      return
    }

    const connections = supervised ? [] : edges.map(e => ({
      from_agent_id: e.source,
      to_agent_id: e.target,
      label: (e.label as string) || undefined,
    }))
    // The Supervisor is hardcoded server-side, so it is never an agent id.
    const sub_agent_ids = agentNodes.map(n => n.id)

    setSaving(true)
    try {
      let result: OrchestrationPublic
      const payload = {
        name: name.trim(),
        description: description.trim() || undefined,
        mode,
        main_agent_id: supervised ? undefined : mainNode!.id,
        sub_agent_ids,
        connections,
        supervisor_config: supervised ? supervisorConfig : undefined,
        max_depth: maxDepth,
        timeout_sec: timeoutSec,
        owner_scope: effectiveOwnerScope,
        allowed_user_ids: effectiveOwnerScope === 'selected_users' ? allowedUserIds : undefined,
        team_id: effectiveOwnerScope === 'team' ? teamId : undefined,
      }

      if (orchestrationId) {
        result = await orchestrationsApi.update(orchestrationId, payload)
        toast.success('Orchestration updated')
      } else {
        result = await orchestrationsApi.create(payload)
        toast.success('Orchestration created!')
      }
      onSaved(result)
    } catch (err: any) {
      toast.error(err?.message || 'Failed to save orchestration')
    } finally {
      setSaving(false)
    }
  }

  // ── Create Agent inline ───────────────────────────────────────────────────────

  const handleAgentCreated = (agent: AgentPublic) => {
    setExtraAgents(prev => [agent, ...prev])
    setShowCreateModal(false)
  }

  // In supervisor mode the Supervisor is the entry point, so there is nothing
  // for the user to designate.
  const hasMain = supervised || nodes.some(n => (n.data as unknown as AgentNodeData).isMain)

  return (
    <div ref={containerRef} className="flex flex-col h-full bg-[var(--surface)]">
      {/* ── Top Toolbar ── */}
      <div className="h-14 shrink-0 flex items-center gap-3 px-4 border-b border-[var(--border)] bg-[var(--surface)]">
        <button
          onClick={onBack}
          className="p-2 rounded-xl hover:bg-[var(--surface-3)] text-[var(--text-2)] hover:text-[var(--text-1)] transition-colors shrink-0"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-2 flex-1 min-w-0">
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Orchestration name…"
            className="text-[15px] font-bold text-[var(--text-1)] bg-transparent outline-none placeholder:text-[var(--text-3)] min-w-0 w-48"
          />
          <span className="text-[var(--text-3)] shrink-0">·</span>
          <input
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Description (optional)"
            className="text-[13px] text-[var(--text-2)] bg-transparent outline-none placeholder:text-[var(--text-3)] flex-1 min-w-0"
          />
        </div>

        {/* Node count badge */}
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-[11px] text-[var(--text-3)]">
            {supervised
              ? `Supervisor · ${agentNodes.length} ${agentNodes.length === 1 ? 'agent' : 'agents'}`
              : `${nodes.length} agents · ${edges.length} connections`}
          </span>
        </div>

        {/* Visibility */}
        {canChooseVisibility && (
          <div className="relative shrink-0">
            <button
              onClick={() => setShowVisibility(s => !s)}
              title="Visibility"
              className={`flex items-center gap-1.5 px-2.5 py-2 rounded-xl transition-colors text-[12px] font-medium ${showVisibility ? 'bg-violet-100 dark:bg-violet-500/20 text-violet-600' : 'hover:bg-[var(--surface-3)] text-[var(--text-2)]'}`}
            >
              <Eye className="w-4 h-4" />
              {agentVisibilityLabel({ owner_scope: ownerScope, allowed_user_ids: allowedUserIds, team_id: teamId })}
            </button>
            {showVisibility && (
              <VisibilityPopover
                ownerScope={ownerScope}
                teamId={teamId}
                allowedUserIds={allowedUserIds}
                orgUsers={orgUsers}
                orgTeams={orgTeams}
                userSearch={userSearch}
                onUserSearchChange={setUserSearch}
                onChange={patch => {
                  if (patch.ownerScope !== undefined) setOwnerScope(patch.ownerScope)
                  if (patch.teamId !== undefined) setTeamId(patch.teamId)
                  if (patch.allowedUserIds !== undefined) setAllowedUserIds(patch.allowedUserIds)
                }}
                onClose={() => setShowVisibility(false)}
              />
            )}
          </div>
        )}

        {/* Mode */}
        <div className="flex items-center gap-0.5 p-0.5 rounded-xl bg-[var(--surface-3)] shrink-0">
          {([
            ['sequential', 'Flow', GitBranch, 'Draw the path: Start → Agent A → Agent B → End'],
            ['supervisor', 'Supervisor', Compass, 'A Supervisor routes each request to the right agent'],
          ] as const).map(([value, label, Icon, title]) => (
            <button
              key={value}
              onClick={() => changeMode(value)}
              title={title}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-[10px] text-[12px] font-medium transition-colors ${
                mode === value
                  ? 'bg-[var(--surface)] text-violet-600 shadow-sm'
                  : 'text-[var(--text-3)] hover:text-[var(--text-1)]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Settings */}
        <div className="relative shrink-0">
          <button
            onClick={() => setShowSettings(s => !s)}
            className={`p-2 rounded-xl transition-colors ${showSettings ? 'bg-violet-100 dark:bg-violet-500/20 text-violet-600' : 'hover:bg-[var(--surface-3)] text-[var(--text-2)]'}`}
          >
            <Settings2 className="w-4 h-4" />
          </button>
          {showSettings && (
            <SettingsPopover
              maxDepth={maxDepth}
              timeoutSec={timeoutSec}
              supervised={supervised}
              supervisorConfig={supervisorConfig}
              onChange={(k, v) => k === 'maxDepth' ? setMaxDepth(v) : setTimeoutSec(v)}
              onSupervisorChange={patch => setSupervisorConfig(c => ({ ...c, ...patch }))}
              onClose={() => setShowSettings(false)}
            />
          )}
        </div>

        {onChat && orchestrationId && (
          <Button
            size="sm"
            variant="outline"
            onClick={onChat}
            className="rounded-xl gap-1.5 shrink-0"
          >
            <MessageSquare className="w-3.5 h-3.5" /> Chat
          </Button>
        )}

        <button
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          className="p-2 rounded-xl hover:bg-[var(--surface-3)] text-[var(--text-2)] hover:text-[var(--text-1)] transition-colors shrink-0"
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>

        <Button
          size="sm"
          onClick={handleSave}
          disabled={saving}
          className="bg-violet-600 hover:bg-violet-700 text-white rounded-xl gap-1.5 shrink-0"
        >
          {saving
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Save className="w-3.5 h-3.5" />}
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </div>

      {/* ── Body ── */}
      <div className="flex flex-1 min-h-0">
        {/* ── Left Panel ── */}
        <div className="w-72 shrink-0 flex flex-col border-r border-[var(--border)] bg-[var(--surface-2)]">
          <div className="p-4 border-b border-[var(--border)]">
            <p className="text-[11px] font-bold text-[var(--text-2)] uppercase tracking-wider mb-3">Agent Library</p>
            <SearchInput
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search agents…"
            />
          </div>

          <div className="p-3 border-b border-[var(--border)]">
            <button
              onClick={() => setShowCreateModal(true)}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border-2 border-dashed border-[var(--border)] text-[12px] font-medium text-[var(--text-3)] hover:border-violet-400 hover:text-violet-600 dark:hover:border-violet-500 dark:hover:text-violet-400 transition-colors"
            >
              <UserPlus className="w-3.5 h-3.5" />
              Create New Agent
            </button>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2">
            {panelAgents.length === 0 && (
              <div className="py-8 text-center">
                <p className="text-[12px] text-[var(--text-3)]">
                  {orgAgents.length === 0
                    ? 'No agents in your org yet'
                    : canvasNodeIds.size >= orgAgents.length
                      ? 'All agents are on the canvas'
                      : 'No agents match your search'}
                </p>
              </div>
            )}
            {panelAgents.map(agent => (
              <div
                key={agent.id}
                draggable
                onDragStart={e => onDragStart(e, agent)}
                onClick={() => addAgentToCanvas(agent)}
                title="Click to add to canvas, or drag to place it precisely"
                className="flex items-center gap-3 p-3 bg-[var(--surface)] rounded-xl border border-[var(--border)] cursor-grab active:cursor-grabbing hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-sm transition-[border-color,box-shadow]"
              >
                <AgentAvatar
                  name={agent.name}
                  avatarType={agent.avatar_type}
                  avatarValue={agent.avatar_value}
                  avatarUrl={agent.avatar_url}
                  size="sm"
                  shape="rounded"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] font-semibold text-[var(--text-1)] truncate">{agent.name}</p>
                  {agent.description && (
                    <p className="text-[11px] text-[var(--text-3)] truncate">{agent.description}</p>
                  )}
                </div>
                <div className="text-[var(--text-3)] text-[10px] shrink-0">⠿</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── React Flow Canvas ── */}
        <div className="flex-1 relative">
          {selectedEdge && (
            <EdgeLabelPanel
              edge={selectedEdge}
              onChange={label => updateEdgeLabel(selectedEdge.id, label)}
              onClose={() => setSelectedEdgeId(null)}
            />
          )}
          {agentNodes.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-10">
              <div className="text-center text-[var(--text-3)]">
                <div className="w-16 h-16 rounded-2xl border-2 border-dashed border-[var(--border)] flex items-center justify-center mx-auto mb-4">
                  <Plus className="w-6 h-6" />
                </div>
                <p className="text-[14px] font-semibold mb-1 text-[var(--text-1)]">Drag agents here</p>
                <p className="text-[12px]">
                  {supervised
                    ? 'Drag from the left panel · The Supervisor routes to whichever agent fits'
                    : 'Drag from the left panel · Connect nodes by dragging from a handle'}
                </p>
              </div>
            </div>
          )}

          {!hasMain && nodes.length > 0 && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 px-4 py-2 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-xl text-[12px] text-amber-700 dark:text-amber-400 shadow-sm">
              <Info className="w-3.5 h-3.5 shrink-0" />
              Click "Set as Entry Point" on an agent to designate where the workflow starts
            </div>
          )}

          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            isValidConnection={isValidConnection}
            // Supervisor mode has no edges to draw — routing is decided per
            // request, so hand-drawn connections would be misleading.
            nodesConnectable={!supervised}
            edgesFocusable={!supervised}
            nodeTypes={nodeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            fitView
            fitViewOptions={{ padding: 0.3 }}
            deleteKeyCode={['Backspace', 'Delete']}
            className={theme === 'dark' ? 'dark bg-[var(--surface-2)]' : 'bg-[var(--surface-2)]'}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="currentColor"
              className="text-[var(--border)]"
            />
            <Controls
              className="!border !border-[var(--border)] !rounded-xl !shadow-sm !overflow-hidden"
              showInteractive={false}
            />
            <MiniMap
              nodeColor={() => '#7c3aed'}
              maskColor="var(--minimap-mask, rgba(0,0,0,0.06))"
              bgColor="var(--surface)"
              className="!border !border-[var(--border)] !rounded-xl !shadow-sm"
              pannable
            />
          </ReactFlow>
        </div>
      </div>

      {showCreateModal && (
        <CreateAgentModal
          orgId={orgId}
          onCreated={handleAgentCreated}
          onClose={() => setShowCreateModal(false)}
        />
      )}
    </div>
  )
}

// ── Exported component ─────────────────────────────────────────────────────────

export function OrchestrationCanvas(props: OrchestrationCanvasProps) {
  const { initialOrch, orgAgents } = props

  const savedMode: OrchestrationMode = initialOrch?.mode ?? 'sequential'

  const [initNodes, initEdges] = useMemo(() => {
    if (!initialOrch || initialOrch.agents.length === 0) {
      // A brand-new supervisor orchestration still shows its Supervisor.
      return [savedMode === 'supervisor' ? [makeSupervisorNode(0)] : [], []] as [Node[], Edge[]]
    }

    const agentIds = initialOrch.agents.map(a => a.agent_id)
    const supervised = savedMode === 'supervisor'
    const positions = supervised
      ? supervisorLayout(agentIds)
      : autoLayout(initialOrch.main_agent_id ?? '', agentIds, initialOrch.connections)

    const nodes: Node[] = initialOrch.agents.map(a => {
      const d: AgentNodeData = {
        name: a.name,
        description: a.description,
        isMain: !supervised && a.agent_id === initialOrch.main_agent_id,
        supervised,
      }
      return {
        id: a.agent_id,
        type: 'agentNode',
        position: positions[a.agent_id] ?? { x: 100, y: 100 },
        data: d,
      }
    })
    if (supervised) {
      nodes.unshift(makeSupervisorNode(agentIds.length, positions[SUPERVISOR_NODE_ID]))
    }

    // Supervisor mode persists no connections, so there is nothing to restore.
    const edges: Edge[] = supervised ? [] : initialOrch.connections.map((c, i) => ({
      id: `e-${c.from_agent_id}-${c.to_agent_id}-${i}`,
      source: c.from_agent_id,
      target: c.to_agent_id,
      label: c.label || undefined,
      ...defaultEdgeOptions,
    }))

    return [nodes, edges]
  }, [initialOrch?.id, savedMode])

  return (
    <ReactFlowProvider>
      {/* The builder is drag-and-drop (drag agents in, drag between handles to
          connect) which needs a pointer and real screen space — not workable on a
          phone. Gate it behind a clear notice on small screens rather than ship a
          broken canvas. */}
      <div className="lg:hidden flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
        <div className="flex size-14 items-center justify-center rounded-2xl bg-violet-500/10 text-violet-600 dark:text-violet-400">
          <Network className="size-7" />
        </div>
        <div className="space-y-1.5">
          <h2 className="text-lg font-semibold text-[var(--text-1)]">
            Best on a larger screen
          </h2>
          <p className="max-w-sm text-sm text-[var(--text-3)]">
            The orchestration builder connects agents by dragging between them, which
            needs a mouse and more room than a phone. Open this on a desktop to build
            or edit orchestrations.
          </p>
        </div>
        {props.onBack && (
          <Button variant="outline" size="sm" onClick={props.onBack}>
            <ArrowLeft className="mr-1.5 size-4" />
            Go back
          </Button>
        )}
      </div>

      <div className="hidden h-full lg:block">
        <CanvasInner
          {...props}
          initNodes={initNodes}
          initEdges={initEdges}
          allOrgAgents={orgAgents}
          initialName={props.initialOrch?.name ?? props.initialName ?? ''}
          initialDescription={props.initialOrch?.description ?? props.initialDescription ?? ''}
          initialMaxDepth={props.initialOrch?.max_depth ?? 5}
          initialTimeoutSec={props.initialOrch?.timeout_sec ?? 600}
          initialOwnerScope={props.initialOrch?.owner_scope ?? 'organization'}
          initialAllowedUserIds={props.initialOrch?.allowed_user_ids ?? []}
          initialTeamId={props.initialOrch?.team_id ?? ''}
          initialMode={savedMode}
          initialSupervisorConfig={
            props.initialOrch?.supervisor_config ?? DEFAULT_SUPERVISOR_CONFIG
          }
        />
      </div>
    </ReactFlowProvider>
  )
}
