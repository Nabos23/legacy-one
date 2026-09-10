'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import {
  Wrench,
  PlugZap,
  Upload,
  FileText,
  Trash2,
  Check,
  BookOpen,
  Database,
  ExternalLink,
  Sparkles,
  Loader2,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Plus,
  PenTool,
} from 'lucide-react'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Tabs, type TabItem } from '@/components/ui/tabs'
import { useToolRegistry } from '@/hooks/use-tool-registry'
import { useConnectors } from '@/hooks/use-connectors'
import { useConnectorStatuses } from '@/hooks/use-connector-statuses'
import { useDbConnections } from '@/hooks/use-db-connections'
import { useTeams } from '@/hooks/use-teams'
import { useUsers } from '@/hooks/use-users'
import { useAuth } from '@/contexts/auth-context'
import { useToast } from '@/hooks/use-toast'
import { projectsApi, promptGeneratorApi } from '@/lib/api'
import type { ProjectPublic, ToolRegistryPublic } from '@/types'
import { cn, formatToolName } from '@/lib/utils'

interface CreateProjectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (project: ProjectPublic) => void
}

type TabKey = 'details' | 'tools' | 'connectors' | 'files' | 'knowledge' | 'prompt'

const TABS: TabItem[] = [
  { value: 'details', label: '1. Details' },
  { value: 'tools', label: '2. Tools' },
  { value: 'connectors', label: '3. Connectors' },
  { value: 'files', label: '4. Skills & Files' },
  { value: 'knowledge', label: '5. Knowledge Base' },
  { value: 'prompt', label: '6. Prompt' },
]

const TAB_KEYS: TabKey[] = ['details', 'tools', 'connectors', 'files', 'knowledge', 'prompt']

const PROMPT_TEMPLATES = [
  {
    title: 'Customer Support',
    prompt:
      'You are a helpful customer support assistant. Be empathetic, concise, and always aim to resolve user inquiries accurately on first reply.',
  },
  {
    title: 'Data Analysis',
    prompt:
      'You are a data analysis expert. Analyze database queries, interpret trends, and formulate clear, actionable recommendations.',
  },
  {
    title: 'Code & Architecture Review',
    prompt:
      'You are a senior software architect. Review codebases, check for correctness, security, performance, and follow attached project skill guidelines.',
  },
  {
    title: 'General Assistant',
    prompt:
      'You are a versatile project assistant. Answer questions accurately and adhere strictly to all project instructions.',
  },
]

const SKILL_TEMPLATES = [
  {
    title: 'Project Skills (skills.md)',
    filename: 'skills.md',
    content: `# Project Guidelines & Skill Instructions

## Overview
Custom domain rules, architecture conventions, and execution guidelines for this project.

## Key Rules
1. Always follow the project architecture and coding patterns.
2. Verify all inputs and arguments before invoking tools.
3. Provide concise, structured explanations for all generated outputs.
`,
  },
  {
    title: 'Database Rules',
    filename: 'database_rules.md',
    content: `# Database Query & Mutation Guidelines

## Read Operations
- Always filter using indexed fields.
- Avoid large unbounded collection scans.

## Write Operations
- Verify document existence prior to mutating state.
- Preserve soft-delete conventions (\`is_deleted: false\`).
`,
  },
  {
    title: 'Code Reviewer',
    filename: 'code_reviewer.md',
    content: `# Code Review & Architecture Standards

## Quality Checklist
- Clean modular design with single responsibility.
- Explicit typing and full validation on API boundaries.
- Comprehensive error handling with descriptive log traces.
`,
  },
]

export function CreateProjectDialog({ open, onOpenChange, onCreated }: CreateProjectDialogProps) {
  const { user } = useAuth()
  const { toast } = useToast()

  // Capabilities Hooks
  const { data: toolsData } = useToolRegistry(1, 100, { isActive: true, sortBy: 'name', sortOrder: 'asc' })
  const allTools = toolsData?.items ?? []

  const { data: allConnectors } = useConnectors()
  const { statuses: connectorStatuses } = useConnectorStatuses(allConnectors.map((c) => c.id))

  const { data: dbConnectionsData, loading: dbConnectionsLoading } = useDbConnections(1, user?.organization_id, 100)
  const dbConnections = (dbConnectionsData?.items ?? []).filter(
    (conn) => !user?.organization_id || conn.organization_id === user.organization_id,
  )

  const [activeTab, setActiveTab] = useState<TabKey>('details')
  const [submitting, setSubmitting] = useState(false)
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false)

  // Form State
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [guardrails, setGuardrails] = useState('')
  const [selectedTools, setSelectedTools] = useState<string[]>([])
  const [toolDbConnectionIds, setToolDbConnectionIds] = useState<Record<string, string>>({})
  const [selectedConnectors, setSelectedConnectors] = useState<string[]>([])
  const [connectorPermissions, setConnectorPermissions] = useState<Record<string, Record<string, boolean>>>({})
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([])
  const [ownerScope, setOwnerScope] = useState<'organization' | 'user' | 'team' | 'selected_users'>('organization')
  const [teamId, setTeamId] = useState('')
  const [allowedUserIds, setAllowedUserIds] = useState<string[]>([])
  const [userSearch, setUserSearch] = useState('')

  // Teams & Users Data
  const { data: teamsData } = useTeams(1, user?.organization_id, undefined, 100)
  const orgTeams = teamsData?.items ?? []

  const { data: usersData } = useUsers(1, user?.organization_id, undefined, undefined, 100)
  const orgUsers = usersData?.items ?? []
  const filteredOrgUsers = orgUsers.filter((u) =>
    `${u.name || ''} ${u.email || ''}`.toLowerCase().includes(userSearch.toLowerCase()),
  )

  // Skill / File Creation State in Tab 4
  const [fileCreationMode, setFileCreationMode] = useState<'create' | 'upload'>('create')
  const [newSkillFilename, setNewSkillFilename] = useState('skills.md')
  const [newSkillContent, setNewSkillContent] = useState(SKILL_TEMPLATES[0].content)

  // Filter searches
  const [toolSearch, setToolSearch] = useState('')
  const [connectorSearch, setConnectorSearch] = useState('')

  // Reset form on open
  useEffect(() => {
    if (open) {
      setName('')
      setDescription('')
      setSystemPrompt('')
      setGuardrails('')
      setSelectedTools([])
      setToolDbConnectionIds({})
      setSelectedConnectors([])
      setConnectorPermissions({})
      setUploadedFiles([])
      setOwnerScope('organization')
      setTeamId('')
      setAllowedUserIds([])
      setUserSearch('')
      setActiveTab('details')
      setToolSearch('')
      setConnectorSearch('')
      setFileCreationMode('create')
      setNewSkillFilename('skills.md')
      setNewSkillContent(SKILL_TEMPLATES[0].content)
    }
  }, [open])

  // Helper functions for DB tools
  const isRawDbTool = (tool: ToolRegistryPublic) =>
    ['query_mongo_read', 'query_sql_read', 'query_mongo_write', 'query_sql_write'].includes(tool.name)

  const isAskHumanTool = (tool: ToolRegistryPublic) => tool.name === 'ask_human'

  const readDbTools = allTools.filter((t) => ['query_mongo_read', 'query_sql_read'].includes(t.name))
  const writeDbTools = allTools.filter((t) => ['query_mongo_write', 'query_sql_write'].includes(t.name))

  const isReadDbChecked = readDbTools.some((t) => t.id && selectedTools.includes(t.id))
  const isWriteDbChecked = writeDbTools.some((t) => t.id && selectedTools.includes(t.id))

  const readDbConnId = readDbTools.map((t) => t.id && toolDbConnectionIds[t.id]).find(Boolean) || ''
  const writeDbConnId = writeDbTools.map((t) => t.id && toolDbConnectionIds[t.id]).find(Boolean) || ''

  const toggleVirtualDbTool = (mode: 'read' | 'write', currentlyChecked: boolean) => {
    const targetTools = mode === 'read' ? readDbTools : writeDbTools
    const targetIds = targetTools.map((t) => t.id!).filter(Boolean)

    if (currentlyChecked) {
      setSelectedTools((prev) => prev.filter((id) => !targetIds.includes(id)))
      setToolDbConnectionIds((prev) => {
        const next = { ...prev }
        targetIds.forEach((id) => delete next[id])
        return next
      })
    } else {
      setSelectedTools((prev) => Array.from(new Set([...prev, ...targetIds])))
      const defaultConnId = dbConnections[0]?.id || ''
      if (defaultConnId) {
        setToolDbConnectionIds((prev) => {
          const next = { ...prev }
          targetIds.forEach((id) => {
            next[id] = defaultConnId
          })
          return next
        })
      }
    }
  }

  const selectDbConnectionForMode = (mode: 'read' | 'write', connId: string) => {
    const targetTools = mode === 'read' ? readDbTools : writeDbTools
    const targetIds = targetTools.map((t) => t.id!).filter(Boolean)
    setToolDbConnectionIds((prev) => {
      const next = { ...prev }
      targetIds.forEach((id) => {
        next[id] = connId
      })
      return next
    })
  }

  const toggleStandardTool = (toolId: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolId) ? prev.filter((id) => id !== toolId) : [...prev, toolId],
    )
  }

  const toggleConnector = (connectorId: string) => {
    setSelectedConnectors((prev) =>
      prev.includes(connectorId) ? prev.filter((id) => id !== connectorId) : [...prev, connectorId],
    )
  }

  const handleFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const filesArray = Array.from(e.target.files)
      setUploadedFiles((prev) => [...prev, ...filesArray])
    }
  }

  const handleAddCreatedSkill = () => {
    const rawName = newSkillFilename.trim() || 'skills.md'
    const filename = rawName.includes('.') ? rawName : `${rawName}.md`

    if (!newSkillContent.trim()) {
      toast.error('Please enter markdown skill instructions')
      return
    }

    const blob = new Blob([newSkillContent], { type: 'text/markdown' })
    const file = new File([blob], filename, { type: 'text/markdown' })

    setUploadedFiles((prev) => {
      const filtered = prev.filter((f) => f.name !== filename)
      return [...filtered, file]
    })

    toast.success(`Attached "${filename}" to project skills!`)
  }

  const removeFile = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const dbConnectionLabel = (conn: any) =>
    conn.name || `${conn.type?.toUpperCase()}: ${conn.database || conn.host || 'Connection'}`

  // AI Prompt Generation
  const handleGeneratePrompt = async () => {
    if (!name.trim()) {
      toast.error('Please enter a project name first in Tab 1')
      setActiveTab('details')
      return
    }
    setIsGeneratingPrompt(true)
    try {
      const res = await promptGeneratorApi.generate(
        name.trim(),
        description.trim() || `An AI workspace project named ${name.trim()}`,
      )
      setSystemPrompt(res.prompt)
      if (res.guardrails) {
        setGuardrails(res.guardrails)
      }
      toast.success('System prompt and guardrails generated with AI!')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to generate prompt')
    } finally {
      setIsGeneratingPrompt(false)
    }
  }

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error('Project Name is required')
      setActiveTab('details')
      return
    }

    if (!user?.organization_id) {
      toast.error('No organization selected')
      return
    }

    // Validate DB tool connections
    if (isReadDbChecked && !readDbConnId && dbConnections.length > 0) {
      toast.error('Please select a database connection for Read from Database')
      setActiveTab('tools')
      return
    }
    if (isWriteDbChecked && !writeDbConnId && dbConnections.length > 0) {
      toast.error('Please select a database connection for Write to Database')
      setActiveTab('tools')
      return
    }

    // Validate Visibility scope
    if (ownerScope === 'selected_users' && allowedUserIds.length === 0) {
      toast.error('Please select at least one user for Selected Users visibility')
      setActiveTab('details')
      return
    }
    if (ownerScope === 'team' && !teamId) {
      toast.error('Please select a team for Team visibility')
      setActiveTab('details')
      return
    }

    setSubmitting(true)
    try {
      const newProject = await projectsApi.create({
        organization_id: user.organization_id,
        name: name.trim(),
        description: description.trim() || undefined,
        system_prompt: systemPrompt.trim(),
        guardrails: guardrails.trim() || undefined,
        tool_ids: selectedTools,
        connector_ids: selectedConnectors,
        connector_permissions: Object.keys(connectorPermissions).length > 0 ? (connectorPermissions as any) : undefined,
        owner_scope: ownerScope,
        allowed_user_ids: ownerScope === 'selected_users' ? allowedUserIds : undefined,
        team_id: ownerScope === 'team' ? teamId || undefined : undefined,
      })

      // Upload skills / files if provided
      if (newProject.id && uploadedFiles.length > 0) {
        for (const file of uploadedFiles) {
          try {
            await projectsApi.uploadFile(newProject.id, file)
          } catch (fileErr) {
            console.error(`Failed to upload ${file.name}:`, fileErr)
          }
        }
      }

      const refreshed = newProject.id ? await projectsApi.get(newProject.id) : newProject
      toast.success(`Project "${refreshed.name}" created successfully!`)
      onCreated(refreshed)
      onOpenChange(false)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to create project')
    } finally {
      setSubmitting(false)
    }
  }

  // Non-DB tools (exclude DB tools and internal ask_human which is always active)
  const nonDbTools = allTools.filter((t) => t.is_active && !isRawDbTool(t) && !isAskHumanTool(t))
  const filteredStandardTools = nonDbTools.filter((t) =>
    `${t.name} ${t.description ?? ''} ${t.type}`.toLowerCase().includes(toolSearch.toLowerCase()),
  )

  // Virtual DB tools
  const virtualTools = [
    {
      id: 'virtual_db_read',
      name: 'Read from database',
      description: 'Execute read-only queries against your connected organization database.',
      mode: 'read' as const,
      isChecked: isReadDbChecked,
      connId: readDbConnId,
    },
    {
      id: 'virtual_db_write',
      name: 'Write to database',
      description: 'Execute write queries and data mutations against your organization database.',
      mode: 'write' as const,
      isChecked: isWriteDbChecked,
      connId: writeDbConnId,
    },
  ]

  const filteredVirtualTools = virtualTools.filter((vt) =>
    `${vt.name} ${vt.description}`.toLowerCase().includes(toolSearch.toLowerCase()),
  )

  // Filter connected connectors only
  const connectedConnectors = allConnectors.filter((c) => connectorStatuses[c.id]?.connected)
  const filteredConnectedConnectors = connectedConnectors.filter((c) =>
    `${c.name} ${c.category} ${c.description || ''}`.toLowerCase().includes(connectorSearch.toLowerCase()),
  )

  const currentTabIndex = TAB_KEYS.indexOf(activeTab)
  const handlePrevTab = () => {
    if (currentTabIndex > 0) setActiveTab(TAB_KEYS[currentTabIndex - 1])
  }
  const handleNextTab = () => {
    if (currentTabIndex < TAB_KEYS.length - 1) setActiveTab(TAB_KEYS[currentTabIndex + 1])
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Create New Project"
      size="2xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{selectedTools.length}</span> tool(s) •{' '}
            <span className="font-medium text-foreground">{selectedConnectors.length}</span> connector(s) •{' '}
            <span className="font-medium text-foreground">{uploadedFiles.length}</span> file(s)
          </div>

          <div className="flex items-center gap-2">
            {currentTabIndex > 0 && (
              <Button variant="ghost" size="sm" onClick={handlePrevTab} className="gap-1">
                <ChevronLeft size={14} />
                <span>Back</span>
              </Button>
            )}

            {currentTabIndex < TAB_KEYS.length - 1 ? (
              <Button variant="secondary" size="sm" onClick={handleNextTab} className="gap-1">
                <span>Next</span>
                <ChevronRight size={14} />
              </Button>
            ) : null}

            <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} className="min-w-[130px]">
              {submitting ? 'Creating...' : 'Create Project'}
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4 py-1">
        <p className="text-xs text-muted-foreground">
          Configure a collaborative AI workspace equipped with specialized tools, verified connectors, and uploaded domain skills.
        </p>

        {/* 6 TABS IN ONE SINGLE LINE */}
        <Tabs
          tabs={TABS}
          value={activeTab}
          onChange={(v) => setActiveTab(v as TabKey)}
          className="w-full grid grid-cols-6 gap-1"
        />

        {/* TAB 1: DETAILS */}
        {activeTab === 'details' && (
          <div className="pt-2 space-y-4 min-h-[380px]">
            <div>
              <label className="text-xs font-semibold text-foreground mb-1 block">
                Project Name <span className="text-destructive">*</span>
              </label>
              <Input
                placeholder="e.g. Migration Assistant, Financial Analyzer, Support Workspace"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-foreground mb-1 block">Description</label>
              <Textarea
                placeholder="Briefly describe the purpose, objectives, and scope of this project..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-foreground mb-1 block">Workspace Visibility</label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-1.5">
                <div
                  onClick={() => setOwnerScope('organization')}
                  className={cn(
                    'p-3 rounded-xl border text-xs cursor-pointer transition-all',
                    ownerScope === 'organization'
                      ? 'bg-primary/10 border-primary/60 text-foreground ring-1 ring-primary/20'
                      : 'bg-card border-border hover:bg-muted/40 text-muted-foreground',
                  )}
                >
                  <div className="font-semibold text-foreground">Organization</div>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    Everyone in org
                  </p>
                </div>

                <div
                  onClick={() => setOwnerScope('user')}
                  className={cn(
                    'p-3 rounded-xl border text-xs cursor-pointer transition-all',
                    ownerScope === 'user'
                      ? 'bg-primary/10 border-primary/60 text-foreground ring-1 ring-primary/20'
                      : 'bg-card border-border hover:bg-muted/40 text-muted-foreground',
                  )}
                >
                  <div className="font-semibold text-foreground">Personal</div>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    Only you
                  </p>
                </div>

                <div
                  onClick={() => setOwnerScope('team')}
                  className={cn(
                    'p-3 rounded-xl border text-xs cursor-pointer transition-all',
                    ownerScope === 'team'
                      ? 'bg-primary/10 border-primary/60 text-foreground ring-1 ring-primary/20'
                      : 'bg-card border-border hover:bg-muted/40 text-muted-foreground',
                  )}
                >
                  <div className="font-semibold text-foreground">Team</div>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    Specific team
                  </p>
                </div>

                <div
                  onClick={() => setOwnerScope('selected_users')}
                  className={cn(
                    'p-3 rounded-xl border text-xs cursor-pointer transition-all',
                    ownerScope === 'selected_users'
                      ? 'bg-primary/10 border-primary/60 text-foreground ring-1 ring-primary/20'
                      : 'bg-card border-border hover:bg-muted/40 text-muted-foreground',
                  )}
                >
                  <div className="font-semibold text-foreground">Selected Users</div>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    Specific people
                  </p>
                </div>
              </div>

              {/* TEAM SELECTOR */}
              {ownerScope === 'team' && (
                <div className="mt-3 p-3 rounded-xl border border-border/80 bg-card/40 space-y-1.5">
                  <label className="text-[11px] font-semibold text-foreground block">
                    Select Target Team <span className="text-destructive">*</span>
                  </label>
                  <Select
                    value={teamId}
                    onValueChange={setTeamId}
                    options={orgTeams.map((t) => ({ value: t.id!, label: t.name }))}
                    placeholder="Choose a team..."
                    className="h-8 text-xs bg-background"
                  />
                  {orgTeams.length === 0 && (
                    <p className="text-[11px] text-destructive mt-1">
                      No teams found in this organization. Create teams in Organization Settings.
                    </p>
                  )}
                </div>
              )}

              {/* SELECTED USERS SELECTOR */}
              {ownerScope === 'selected_users' && (
                <div className="mt-3 p-3 rounded-xl border border-border/80 bg-card/40 space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-semibold text-foreground">
                      Authorized Members ({allowedUserIds.length} selected) <span className="text-destructive">*</span>
                    </label>
                  </div>
                  <SearchInput
                    placeholder="Search organization members..."
                    value={userSearch}
                    onChange={(e) => setUserSearch(e.target.value)}
                  />
                  <div className="max-h-32 overflow-y-auto space-y-1 pr-1">
                    {filteredOrgUsers.length === 0 ? (
                      <p className="text-[11px] text-muted-foreground p-2 text-center">
                        No matching organization members.
                      </p>
                    ) : (
                      filteredOrgUsers.map((u) => {
                        const isChecked = allowedUserIds.includes(u.id!)
                        return (
                          <div
                            key={u.id}
                            onClick={() =>
                              setAllowedUserIds((prev) =>
                                isChecked ? prev.filter((id) => id !== u.id) : [...prev, u.id!],
                              )
                            }
                            className={cn(
                              'flex items-center gap-2 p-2 rounded-lg border text-xs cursor-pointer transition-all',
                              isChecked
                                ? 'bg-primary/10 border-primary/60 text-foreground'
                                : 'bg-card border-border/60 hover:bg-muted/40 text-muted-foreground',
                            )}
                          >
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {}}
                              className="w-3.5 h-3.5 accent-primary"
                            />
                            <span className="font-medium text-foreground truncate">
                              {u.name || u.email}
                              {u.id === user?.id ? ' (You)' : ''}
                            </span>
                            <span className="text-[10px] text-muted-foreground truncate">{u.email}</span>
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: TOOLS */}
        {activeTab === 'tools' && (
          <div className="pt-2 space-y-4 min-h-[380px]">
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1">
                <SearchInput
                  placeholder="Search available tools..."
                  value={toolSearch}
                  onChange={(e) => setToolSearch(e.target.value)}
                />
              </div>
              <div className="text-xs text-muted-foreground">
                Selected: <Badge variant="primary" className="ml-1">{selectedTools.length}</Badge>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 max-h-[340px] overflow-y-auto pr-1">
              {/* Virtual Database Tools */}
              {filteredVirtualTools.map((vt) => (
                <div
                  key={vt.id}
                  onClick={() => toggleVirtualDbTool(vt.mode, vt.isChecked)}
                  className={cn(
                    'flex flex-col p-3 rounded-xl border text-xs cursor-pointer transition-all',
                    vt.isChecked
                      ? 'bg-primary/10 border-primary/60 text-foreground ring-1 ring-primary/20'
                      : 'bg-card border-border hover:bg-muted/40 text-muted-foreground',
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <input
                      type="checkbox"
                      checked={vt.isChecked}
                      onChange={() => {}}
                      className="mt-0.5 w-4 h-4 accent-primary"
                    />
                    <Database size={15} className="text-primary mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <span className="font-semibold text-foreground block">{vt.name}</span>
                      <p className="text-[11px] text-muted-foreground mt-0.5">{vt.description}</p>

                      {vt.isChecked && (
                        <div className="mt-2.5" onClick={(e) => e.stopPropagation()}>
                          <label className="text-[10px] font-semibold text-foreground block mb-1">
                            Target Database Connection:
                          </label>
                          <Select
                            value={vt.connId}
                            onValueChange={(val) => selectDbConnectionForMode(vt.mode, val)}
                            options={dbConnections.map((conn) => ({
                              value: conn.id!,
                              label: dbConnectionLabel(conn),
                            }))}
                            placeholder={dbConnectionsLoading ? 'Loading connections...' : 'Select database connection'}
                            disabled={dbConnectionsLoading || dbConnections.length === 0}
                            className="h-7 text-xs bg-background"
                          />
                          {dbConnections.length === 0 && !dbConnectionsLoading && (
                            <p className="text-[10px] text-destructive mt-1">
                              No DB connections in this org. Connect one in Database Connections.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {/* Standard Non-DB Tools */}
              {filteredStandardTools.map((tool) => {
                const isSelected = selectedTools.includes(tool.id || '')
                return (
                  <div
                    key={tool.id}
                    onClick={() => tool.id && toggleStandardTool(tool.id)}
                    className={cn(
                      'flex items-start gap-2.5 p-3 rounded-xl border text-xs cursor-pointer transition-all',
                      isSelected
                        ? 'bg-primary/10 border-primary/60 text-foreground ring-1 ring-primary/20'
                        : 'bg-card border-border hover:bg-muted/40 text-muted-foreground',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}}
                      className="mt-0.5 w-4 h-4 accent-primary"
                    />
                    <Wrench size={14} className="text-primary mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <span className="font-semibold text-foreground block">
                        {formatToolName(tool.name)}
                      </span>
                      <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                        {tool.description || 'Custom organization tool'}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* TAB 3: CONNECTORS */}
        {activeTab === 'connectors' && (
          <div className="pt-2 space-y-4 min-h-[380px]">
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1">
                <SearchInput
                  placeholder="Search connected integrations..."
                  value={connectorSearch}
                  onChange={(e) => setConnectorSearch(e.target.value)}
                />
              </div>
              <Link href="/client/connectors" target="_blank">
                <Button variant="ghost" size="sm" className="text-xs text-primary gap-1 h-8 px-2.5">
                  <span>+ Connect more integrations</span>
                  <ExternalLink size={12} />
                </Button>
              </Link>
            </div>

            {filteredConnectedConnectors.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-8 rounded-xl border border-dashed border-border bg-card/40 text-center space-y-2.5">
                <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center text-amber-500">
                  <PlugZap size={20} />
                </div>
                <h4 className="text-sm font-semibold text-foreground">No Connected Integrations Found</h4>
                <p className="text-xs text-muted-foreground max-w-sm">
                  Connect third-party services (Shopify, ClickUp, Slack, GitHub, etc.) to allow this project to query and interact with live workflows.
                </p>
                <Link href="/client/connectors" target="_blank">
                  <Button size="sm" variant="secondary" className="text-xs gap-1.5 mt-1">
                    <span>Manage Integrations</span>
                    <ExternalLink size={12} />
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 max-h-[340px] overflow-y-auto pr-1">
                {filteredConnectedConnectors.map((connector) => {
                  const isSelected = selectedConnectors.includes(connector.id)
                  const permCategories = connector.permissions ? Object.keys(connector.permissions) : ['read', 'write', 'delete']
                  const connPerms = connectorPermissions[connector.provider_id] || {}

                  return (
                    <div
                      key={connector.id}
                      onClick={() => toggleConnector(connector.id)}
                      className={cn(
                        'flex flex-col p-3 rounded-xl border text-xs cursor-pointer transition-all',
                        isSelected
                          ? 'bg-primary/10 border-primary/60 text-foreground ring-1 ring-primary/20'
                          : 'bg-card border-border hover:bg-muted/40 text-muted-foreground',
                      )}
                    >
                      <div className="flex items-start gap-2.5">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}}
                          className="mt-0.5 w-4 h-4 accent-primary"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 truncate">
                            <span className="font-semibold text-foreground truncate">{connector.name}</span>
                            <span className="inline-flex items-center gap-1 text-[9px] font-medium text-green-600 dark:text-green-400 shrink-0">
                              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                              Connected
                            </span>
                          </div>
                          <p className="text-[10px] text-muted-foreground truncate mt-0.5">
                            {connector.description || connector.provider_id}
                          </p>
                        </div>
                      </div>

                      {/* Granular Permissions Checkboxes */}
                      {isSelected && (
                        <div
                          className="mt-2.5 border-t border-border/60 pt-2 space-y-1.5"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <span className="text-[10px] font-semibold text-foreground block">
                            Granted Permissions:
                          </span>
                          <div className="flex gap-3 flex-wrap">
                            {permCategories.map((action) => {
                              const currentVal = connPerms[action] !== undefined ? connPerms[action] : true
                              return (
                                <label key={action} className="flex items-center gap-1.5 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={currentVal}
                                    onChange={(e) => {
                                      const checked = e.target.checked
                                      setConnectorPermissions((prev) => {
                                        const existing = prev[connector.provider_id] || {}
                                        const base: Record<string, boolean> = {}
                                        for (const cat of permCategories) {
                                          base[cat] = existing[cat] !== undefined ? existing[cat] : true
                                        }
                                        base[action] = checked
                                        return {
                                          ...prev,
                                          [connector.provider_id]: base,
                                        }
                                      })
                                    }}
                                    className="w-3.5 h-3.5 accent-primary rounded"
                                  />
                                  <span className="text-[10px] font-medium text-foreground capitalize">
                                    {action}
                                  </span>
                                </label>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: SKILLS & FILES */}
        {activeTab === 'files' && (
          <div className="pt-2 space-y-4 min-h-[380px]">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <label className="text-xs font-semibold text-foreground block">
                  Project Skills & Domain Files
                </label>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Write custom markdown instructions (e.g. <code className="bg-muted px-1 py-0.5 rounded text-foreground font-mono text-[10px]">skills.md</code>) or upload existing files.
                </p>
              </div>

              {/* Mode Switcher */}
              <div className="flex items-center p-0.5 bg-muted rounded-lg border border-border shrink-0 self-start sm:self-auto">
                <button
                  type="button"
                  onClick={() => setFileCreationMode('create')}
                  className={cn(
                    'px-3 py-1 text-xs font-medium rounded-md transition-all',
                    fileCreationMode === 'create'
                      ? 'bg-card text-foreground shadow-xs'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  ✏️ Write Skill (.md)
                </button>
                <button
                  type="button"
                  onClick={() => setFileCreationMode('upload')}
                  className={cn(
                    'px-3 py-1 text-xs font-medium rounded-md transition-all',
                    fileCreationMode === 'upload'
                      ? 'bg-card text-foreground shadow-xs'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  📁 Upload Files
                </button>
              </div>
            </div>

            {/* WRITE SKILL MODE */}
            {fileCreationMode === 'create' ? (
              <div className="p-3.5 rounded-xl border border-border bg-card/40 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex-1 max-w-sm">
                    <label className="text-[11px] font-semibold text-foreground block mb-1">
                      File Name
                    </label>
                    <Input
                      placeholder="e.g. skills.md, database_rules.md"
                      value={newSkillFilename}
                      onChange={(e) => setNewSkillFilename(e.target.value)}
                      className="h-8 text-xs font-mono"
                    />
                  </div>

                  <div className="flex items-center gap-1.5 flex-wrap self-end">
                    <span className="text-[10px] text-muted-foreground mr-1">Presets:</span>
                    {SKILL_TEMPLATES.map((tmpl) => (
                      <button
                        key={tmpl.title}
                        type="button"
                        onClick={() => {
                          setNewSkillFilename(tmpl.filename)
                          setNewSkillContent(tmpl.content)
                        }}
                        className="px-2 py-1 rounded border border-border/80 bg-card hover:bg-muted text-[10px] font-medium text-foreground transition-colors"
                      >
                        {tmpl.title}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[11px] font-semibold text-foreground">
                      Markdown Skill Instructions
                    </label>
                    <span className="text-[10px] text-muted-foreground">
                      Automatically injected into the AI system prompt
                    </span>
                  </div>
                  <Textarea
                    placeholder="# Project Skills\n\n## Instructions\nWrite custom execution guidelines..."
                    value={newSkillContent}
                    onChange={(e) => setNewSkillContent(e.target.value)}
                    rows={6}
                    className="font-mono text-xs leading-relaxed bg-background"
                  />
                </div>

                <div className="flex justify-end">
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleAddCreatedSkill}
                    className="h-8 text-xs gap-1.5 px-3 shadow-xs"
                  >
                    <Plus size={14} />
                    <span>Attach Skill File</span>
                  </Button>
                </div>
              </div>
            ) : (
              /* UPLOAD FILES MODE */
              <label className="border-2 border-dashed border-border hover:border-primary/50 rounded-2xl p-6 flex flex-col items-center justify-center text-center cursor-pointer bg-card/30 hover:bg-card/60 transition-all block">
                <Upload size={24} className="text-primary mb-2 opacity-80" />
                <span className="text-xs font-medium text-foreground">Click to upload files or drag & drop</span>
                <span className="text-[10px] text-muted-foreground mt-0.5">
                  Supports markdown, skills.md, txt, code, pdf, json, and csv
                </span>
                <input
                  type="file"
                  multiple
                  onChange={handleFilesSelected}
                  className="hidden"
                  accept=".md,.txt,.py,.js,.ts,.tsx,.json,.pdf,.csv,.doc,.docx"
                />
              </label>
            )}

            {/* ATTACHED FILES LIST */}
            {uploadedFiles.length > 0 && (
              <div className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1">
                <span className="text-[11px] font-semibold text-foreground block">
                  Attached Files ({uploadedFiles.length})
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {uploadedFiles.map((file, i) => (
                    <div
                      key={`${file.name}-${i}`}
                      className="flex items-center justify-between p-2 rounded-lg border border-border/80 bg-card/60 text-xs"
                    >
                      <div className="flex items-center gap-2 truncate min-w-0 pr-1">
                        <Sparkles size={13} className="text-amber-500 shrink-0" />
                        <span className="font-medium text-foreground truncate">{file.name}</span>
                        <span className="text-[10px] text-muted-foreground shrink-0">
                          ({(file.size / 1024).toFixed(1)} KB)
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeFile(i)}
                        className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive shrink-0"
                      >
                        <Trash2 size={12} />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: KNOWLEDGE BASE */}
        {activeTab === 'knowledge' && (
          <div className="pt-2 space-y-4 min-h-[380px]">
            <div className="p-6 rounded-2xl border border-border bg-card/30 flex flex-col items-center justify-center text-center space-y-2">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                <BookOpen size={18} />
              </div>
              <h4 className="text-sm font-semibold text-foreground">Knowledge Base (RAG Ready)</h4>
              <p className="text-xs text-muted-foreground max-w-md leading-relaxed">
                Vector knowledge base semantic search datasets are supported. You can attach project skill files in Tab 4 or configure enterprise vector sources.
              </p>
              <Badge variant="outline" className="mt-2 text-[11px]">
                Ready for Retrieval Augmented Generation
              </Badge>
            </div>
          </div>
        )}

        {/* TAB 6: PROMPT & GUIDELINES */}
        {activeTab === 'prompt' && (
          <div className="pt-2 space-y-4 min-h-[380px]">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-foreground">
                  System Prompt and Project Guidelines
                </label>
                <button
                  type="button"
                  onClick={handleGeneratePrompt}
                  disabled={isGeneratingPrompt || !name.trim()}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-xs disabled:opacity-40 disabled:cursor-not-allowed"
                  title={!name.trim() ? 'Enter a project name in Tab 1 first' : 'Generate system prompt and guidelines using AI'}
                >
                  {isGeneratingPrompt ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5" />
                  )}
                  {isGeneratingPrompt ? 'Generating...' : 'Generate with AI'}
                </button>
              </div>

              <Textarea
                placeholder="You are an expert project assistant. Follow all project instructions, attached skills, and organization guidelines..."
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={5}
                className="font-mono text-xs leading-relaxed"
              />
            </div>

            {/* Prompt Templates */}
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">
                Prompt Templates (Click to apply)
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {PROMPT_TEMPLATES.map((template) => (
                  <div
                    key={template.title}
                    onClick={() => setSystemPrompt(template.prompt)}
                    className="p-2.5 rounded-xl border border-border/80 bg-card/40 hover:bg-card hover:border-primary/40 cursor-pointer text-left transition-all"
                  >
                    <span className="font-semibold text-xs text-foreground block">{template.title}</span>
                    <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">{template.prompt}</p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-foreground">
                  Guardrails (Optional)
                </label>
                <span className="text-[11px] text-muted-foreground">
                  Safety constraints and boundaries
                </span>
              </div>
              <Textarea
                placeholder="e.g. Never execute destructive write operations without explicit confirmation."
                value={guardrails}
                onChange={(e) => setGuardrails(e.target.value)}
                rows={2}
                className="text-xs"
              />
            </div>
          </div>
        )}
      </div>
    </Dialog>
  )
}
