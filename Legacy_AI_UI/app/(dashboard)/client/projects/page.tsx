'use client'

import { useState, useRef, useEffect } from 'react'
import {
  Plus,
  Wrench,
  PlugZap,
  Sparkles,
  Trash2,
  ArrowUp,
  FolderKanban,
  Settings2,
  RotateCcw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/search-input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Markdown } from '@/components/ui/markdown'
import { TypingIndicator } from '@/components/ui/typing-indicator'
import { ConnectorAuthErrorBanner } from '@/components/connectors/reconnect-button'
import { CreateProjectDialog } from '@/components/projects/create-project-dialog'
import { EditProjectDialog } from '@/components/projects/edit-project-dialog'
import { ProjectFilesDialog } from '@/components/projects/project-files-dialog'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Pagination } from '@/components/ui/pagination'
import { useProjects } from '@/hooks/use-projects'
import { useProjectChat } from '@/hooks/use-project-chat'
import { useAuth } from '@/contexts/auth-context'
import { useToast } from '@/hooks/use-toast'
import { projectsApi } from '@/lib/api'
import type { ProjectPublic } from '@/types'
import { cn, formatDate } from '@/lib/utils'

export default function ProjectsPage() {
  const { user } = useAuth()
  const { toast } = useToast()

  const [search, setSearch] = useState('')
  const [pageSize, setPageSize] = useState(10)
  const { data: projectsData, loading: projectsLoading, page, setPage, refetch: refetchProjects, updateLocal, removeLocal } =
    useProjects(1, undefined, search, pageSize)

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const handlePageSizeChange = (size: number) => {
    setPageSize(size)
    setPage(1)
  }

  const projects = projectsData?.items ?? []

  // Active selected project
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const selectedProject = projects.find((p) => p.id === selectedProjectId) || null

  // Auto-select first project if available and none selected
  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) {
      setSelectedProjectId(projects[0].id || null)
    }
  }, [projects, selectedProjectId])

  // Modals state
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [filesOpen, setFilesOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ProjectPublic | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Chat input
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const {
    messages,
    isTyping,
    liveActivity,
    error: chatError,
    sendMessage,
    clearMessages,
  } = useProjectChat({
    projectId: selectedProjectId,
  })

  // Auto-resize textarea
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [input])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping, liveActivity])

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || isTyping) return
    const text = input.trim()
    setInput('')
    if (inputRef.current) inputRef.current.style.height = 'auto'
    await sendMessage(text)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleProjectCreated = (newProject: ProjectPublic) => {
    refetchProjects()
    setSelectedProjectId(newProject.id || null)
  }

  const handleProjectUpdated = (updatedProject: ProjectPublic) => {
    if (updatedProject.id) {
      updateLocal(updatedProject.id, updatedProject)
    }
  }

  const handleDeleteProject = async () => {
    if (!deleteTarget?.id) return
    setDeleting(true)
    try {
      await projectsApi.delete(deleteTarget.id)
      toast.success(`Project "${deleteTarget.name}" deleted.`)
      removeLocal(deleteTarget.id)
      if (selectedProjectId === deleteTarget.id) {
        setSelectedProjectId(null)
      }
      setDeleteTarget(null)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete project')
    } finally {
      setDeleting(false)
    }
  }

  const handleClearChat = async () => {
    await clearMessages()
    toast.success('Project chat history cleared.')
  }

  return (
    <div className="flex h-full w-full overflow-hidden bg-[var(--surface)]">
      {/* ------------------------------------------------------------- */}
      {/* LEFT PANEL: PROJECTS LIST */}
      {/* ------------------------------------------------------------- */}
      <div className="w-80 md:w-96 flex-col border-r border-[var(--border)] bg-[var(--surface)] flex shrink-0">
        {/* Header */}
        <div className="h-14 px-4 border-b border-[var(--border)] flex items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2">
            <FolderKanban size={18} className="text-primary shrink-0" />
            <h2 className="font-semibold text-sm text-foreground">Projects</h2>
            <Badge variant="neutral" className="text-[11px] font-mono h-5 px-1.5">
              {projects.length}
            </Badge>
          </div>
          <Button
            size="sm"
            onClick={() => setCreateOpen(true)}
            className="h-8 text-xs gap-1.5 px-2.5 shadow-xs"
          >
            <Plus size={14} />
            <span>New Project</span>
          </Button>
        </div>

        {/* Search */}
        <div className="p-2.5 border-b border-border/60">
          <SearchInput
            placeholder="Search projects..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
        </div>

        {/* Project Items List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
          {projectsLoading && projects.length === 0 ? (
            <div className="text-center p-6 text-xs text-muted-foreground">Loading projects...</div>
          ) : projects.length === 0 ? (
            <div className="text-center p-6 border border-dashed rounded-lg bg-card/20 m-2">
              <FolderKanban size={24} className="mx-auto text-muted-foreground mb-2 opacity-50" />
              <p className="text-xs font-semibold text-foreground">No projects found</p>
              <p className="text-[11px] text-muted-foreground mt-1">Create your first project to start chatting.</p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setCreateOpen(true)}
                className="mt-3 text-xs h-7"
              >
                <Plus size={12} className="mr-1" /> Create Project
              </Button>
            </div>
          ) : (
            projects.map((project) => {
              const isSelected = selectedProjectId === project.id
              const filesCount = project.files?.length || 0
              const toolsCount = project.tool_ids?.length || 0
              const connectorsCount = project.connector_ids?.length || 0

              return (
                <div
                  key={project.id}
                  onClick={() => {
                    if (selectedProjectId !== project.id) {
                      setSelectedProjectId(project.id || null)
                    }
                  }}
                  className={cn(
                    'group relative flex flex-col gap-1.5 p-3 rounded-xl border text-left cursor-pointer transition-all',
                    isSelected
                      ? 'bg-primary/10 border-primary/60 shadow-xs ring-1 ring-primary/20'
                      : 'bg-card/60 hover:bg-card border-border/80 hover:border-border text-foreground',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex flex-col truncate">
                      <span className="font-semibold text-xs text-foreground truncate">
                        {project.name}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {formatDate(project.created_at)}
                      </span>
                    </div>

                    {/* Action buttons on hover */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setDeleteTarget(project)
                        }}
                        className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 size={12} />
                      </Button>
                    </div>
                  </div>

                  {project.description && (
                    <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                      {project.description}
                    </p>
                  )}

                  <div className="flex items-center gap-1.5 flex-wrap pt-1">
                    {filesCount > 0 && (
                      <Badge variant="neutral" className="text-[10px] h-4.5 px-1.5 gap-1 bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20">
                        <Sparkles size={10} />
                        {filesCount} skill{filesCount > 1 ? 's' : ''}
                      </Badge>
                    )}
                    {toolsCount > 0 && (
                      <Badge variant="outline" className="text-[10px] h-4.5 px-1.5 gap-1 text-muted-foreground">
                        <Wrench size={10} />
                        {toolsCount}
                      </Badge>
                    )}
                    {connectorsCount > 0 && (
                      <Badge variant="outline" className="text-[10px] h-4.5 px-1.5 gap-1 text-muted-foreground">
                        <PlugZap size={10} />
                        {connectorsCount}
                      </Badge>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>

        {projectsData && projectsData.total > pageSize && (
          <Pagination
            page={page}
            pageSize={pageSize}
            total={projectsData.total}
            onPageChange={setPage}
            onPageSizeChange={handlePageSizeChange}
            pageSizeOptions={[5, 10, 20, 50]}
          />
        )}
      </div>

      {/* ------------------------------------------------------------- */}
      {/* RIGHT PANEL: PROJECT CHAT WORKSPACE */}
      {/* ------------------------------------------------------------- */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative bg-[var(--surface)]">
        {selectedProject ? (
          <>
            {/* Top Project Bar */}
            <div className="h-14 flex items-center justify-between px-5 border-b border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-sm shrink-0 relative z-20 gap-4">
              <div className="flex flex-col truncate">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-sm text-foreground truncate">
                    {selectedProject.name}
                  </h3>
                  <Badge variant="outline" className="text-[10px] font-normal">
                    Project Mode
                  </Badge>
                </div>
                {selectedProject.description ? (
                  <p className="text-xs text-muted-foreground truncate max-w-xl">
                    {selectedProject.description}
                  </p>
                ) : (
                  <p className="text-[11px] text-muted-foreground italic">No description</p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setFilesOpen(true)}
                  className="h-8 text-xs gap-1.5"
                >
                  <Sparkles size={13} className="text-amber-500" />
                  <span>Skills & Files ({selectedProject.files?.length || 0})</span>
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditOpen(true)}
                  className="h-8 text-xs gap-1.5"
                >
                  <Settings2 size={13} />
                  <span>Settings</span>
                </Button>

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleClearChat}
                  title="Clear Project Chat History"
                  className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                >
                  <RotateCcw size={14} />
                </Button>
              </div>
            </div>

            {/* Conversation Scroll Area */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-8 max-w-md mx-auto">
                  <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-3 shadow-xs">
                    <FolderKanban size={24} />
                  </div>
                  <h4 className="font-semibold text-base text-foreground">
                    Chat with {selectedProject.name}
                  </h4>
                  <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                    This project is equipped with its custom system prompt, {selectedProject.files?.length || 0} attached skill(s), and connected tools. Send a message to start working!
                  </p>

                  <div className="grid grid-cols-1 gap-2 w-full mt-6 text-left">
                    <div
                      onClick={() => sendMessage('Hello! What skills and tools do you have available in this project?')}
                      className="p-2.5 rounded-lg border border-border/80 bg-card/40 hover:bg-card hover:border-primary/40 text-xs text-muted-foreground hover:text-foreground cursor-pointer transition-all"
                    >
                      💡 "What skills and tools do you have in this project?"
                    </div>
                    <div
                      onClick={() => sendMessage('Review our project guidelines and summarize key execution steps.')}
                      className="p-2.5 rounded-lg border border-border/80 bg-card/40 hover:bg-card hover:border-primary/40 text-xs text-muted-foreground hover:text-foreground cursor-pointer transition-all"
                    >
                      📋 "Review our project guidelines and summarize key steps."
                    </div>
                  </div>
                </div>
              ) : (
                messages.map((msg, index) => {
                  const isUser = msg.role === 'user'

                  return (
                    <div
                      key={msg.id || index}
                      className={cn(
                        'flex gap-3 max-w-3xl',
                        isUser ? 'ml-auto justify-end' : 'mr-auto justify-start',
                      )}
                    >
                      <div className="flex flex-col gap-1 max-w-[85%]">
                        {!isUser && (
                          <span className="text-[11px] font-semibold text-foreground/80 px-1">
                            {selectedProject.name}
                          </span>
                        )}
                        <div
                          className={cn(
                            'p-3.5 rounded-2xl text-xs leading-relaxed',
                            isUser
                              ? 'bg-primary text-primary-foreground rounded-tr-xs shadow-xs'
                              : 'bg-card border border-border/80 text-foreground rounded-tl-xs shadow-2xs',
                          )}
                        >
                          {isUser ? (
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                          ) : (
                            <Markdown content={msg.content} />
                          )}
                        </div>

                        {/* Auth Errors Banner if any */}
                        {msg.auth_errors && msg.auth_errors.length > 0 && (
                          <ConnectorAuthErrorBanner errors={msg.auth_errors} />
                        )}

                        <span
                          className={cn(
                            'text-[10px] text-muted-foreground px-1',
                            isUser ? 'text-right' : 'text-left',
                          )}
                        >
                          {formatDate(msg.timestamp)}
                        </span>
                      </div>
                    </div>
                  )
                })
              )}

              {/* Live Tool Activity & Typing */}
              {isTyping && (
                <div className="flex flex-col gap-1 max-w-xl">
                  <span className="text-[11px] font-semibold text-foreground/80 px-1">
                    {selectedProject.name}
                  </span>
                  <div className="flex items-center gap-2 p-3 bg-card border border-border/80 rounded-2xl rounded-tl-xs text-xs text-muted-foreground shadow-2xs">
                    {liveActivity ? (
                      <div className="flex items-center gap-2 text-primary font-medium">
                        <Wrench size={13} className="animate-spin text-primary" />
                        <span>Using {liveActivity.label}...</span>
                      </div>
                    ) : (
                      <TypingIndicator />
                    )}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Chat Input Box */}
            <div className="p-4 border-t border-border/80 bg-card/20 shrink-0">
              <form
                onSubmit={handleSend}
                className="flex items-end gap-2 max-w-4xl mx-auto bg-card border border-border rounded-2xl p-2 shadow-xs focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/10 transition-all"
              >
                <Textarea
                  ref={inputRef}
                  placeholder={`Message ${selectedProject.name}... (Press Enter to send, Shift+Enter for new line)`}
                  value={input}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  className="flex-1 resize-none border-0 focus-visible:ring-0 text-xs bg-transparent min-h-[36px] max-h-[160px] py-2 px-2"
                />

                <Button
                  type="submit"
                  size="sm"
                  disabled={!input.trim() || isTyping}
                  className="h-8 w-8 p-0 rounded-xl shrink-0 shadow-xs"
                >
                  <ArrowUp size={15} />
                </Button>
              </form>
            </div>
          </>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center p-8 text-muted-foreground">
            <FolderKanban size={36} className="mb-3 opacity-40" />
            <h3 className="font-semibold text-base text-foreground">No Project Selected</h3>
            <p className="text-xs max-w-sm mt-1">
              Select a project from the left list to start chatting or create a new project.
            </p>
            <Button
              size="sm"
              onClick={() => setCreateOpen(true)}
              className="mt-4 text-xs gap-1.5"
            >
              <Plus size={14} />
              <span>Create New Project</span>
            </Button>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------- */}
      {/* MODALS */}
      {/* ------------------------------------------------------------- */}
      <CreateProjectDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={handleProjectCreated}
      />

      <EditProjectDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        project={selectedProject}
        onUpdated={handleProjectUpdated}
      />

      <ProjectFilesDialog
        open={filesOpen}
        onOpenChange={setFilesOpen}
        project={selectedProject}
        onFilesChanged={handleProjectUpdated}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`Delete Project "${deleteTarget?.name}"?`}
        description="This will remove the project and its attached skills from your organization. This action cannot be undone."
        confirmLabel={deleting ? 'Deleting...' : 'Delete Project'}
        loading={deleting}
        danger={true}
        onConfirm={handleDeleteProject}
      />
    </div>
  )
}
