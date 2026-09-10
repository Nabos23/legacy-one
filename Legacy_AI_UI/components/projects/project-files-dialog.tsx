'use client'

import { useState, useEffect, useRef } from 'react'
import {
  Upload,
  FileText,
  Trash2,
  Eye,
  Sparkles,
  FileCode,
  File as FileIcon,
  X,
  Loader2,
  Plus,
  Edit3,
} from 'lucide-react'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Markdown } from '@/components/ui/markdown'
import { useToast } from '@/hooks/use-toast'
import { projectsApi } from '@/lib/api'
import type { ProjectFilePublic, ProjectPublic } from '@/types'
import { cn } from '@/lib/utils'

interface ProjectFilesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  project: ProjectPublic | null
  onFilesChanged: (updatedProject: ProjectPublic) => void
}

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
]

export function ProjectFilesDialog({ open, onOpenChange, project, onFilesChanged }: ProjectFilesDialogProps) {
  const { toast } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [files, setFiles] = useState<ProjectFilePublic[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [previewFile, setPreviewFile] = useState<ProjectFilePublic | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  // Creation State for New Skill
  const [isCreatingSkill, setIsCreatingSkill] = useState(false)
  const [newSkillFilename, setNewSkillFilename] = useState('skills.md')
  const [newSkillContent, setNewSkillContent] = useState(SKILL_TEMPLATES[0].content)
  const [savingSkill, setSavingSkill] = useState(false)

  const loadFiles = async () => {
    if (!project?.id) return
    setLoading(true)
    try {
      const list = await projectsApi.listFiles(project.id)
      setFiles(list)
    } catch {
      toast.error('Failed to load project files')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open && project?.id) {
      loadFiles()
      setPreviewFile(null)
      setIsCreatingSkill(false)
      setNewSkillFilename('skills.md')
      setNewSkillContent(SKILL_TEMPLATES[0].content)
    }
  }, [open, project?.id])

  const processUploadFiles = async (uploadList: File[]) => {
    if (!project?.id || uploadList.length === 0) return

    setUploading(true)
    try {
      for (const file of uploadList) {
        await projectsApi.uploadFile(project.id, file)
      }
      toast.success(`${uploadList.length} file(s) uploaded and saved to project!`)
      await loadFiles()
      const refreshed = await projectsApi.get(project.id)
      onFilesChanged(refreshed)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return
    const uploadList = Array.from(e.target.files)
    await processUploadFiles(uploadList)
  }

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files) {
      const uploadList = Array.from(e.dataTransfer.files)
      await processUploadFiles(uploadList)
    }
  }

  const handleSaveCreatedSkill = async () => {
    if (!project?.id) return
    const rawName = newSkillFilename.trim() || 'skills.md'
    const filename = rawName.includes('.') ? rawName : `${rawName}.md`

    if (!newSkillContent.trim()) {
      toast.error('Please enter skill markdown content')
      return
    }

    setSavingSkill(true)
    try {
      const blob = new Blob([newSkillContent], { type: 'text/markdown' })
      const file = new File([blob], filename, { type: 'text/markdown' })
      await projectsApi.uploadFile(project.id, file)
      toast.success(`Skill file "${filename}" created and attached to project!`)
      setIsCreatingSkill(false)
      await loadFiles()
      const refreshed = await projectsApi.get(project.id)
      onFilesChanged(refreshed)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to create skill file')
    } finally {
      setSavingSkill(false)
    }
  }

  const handleDeleteFile = async (fileId: string) => {
    if (!project?.id) return
    try {
      await projectsApi.deleteFile(project.id, fileId)
      toast.success('File deleted.')
      if (previewFile?.id === fileId) {
        setPreviewFile(null)
      }
      await loadFiles()
      const refreshed = await projectsApi.get(project.id)
      onFilesChanged(refreshed)
    } catch {
      toast.error('Failed to delete file')
    }
  }

  const getFileIcon = (fileType: string) => {
    switch (fileType) {
      case 'skill':
        return <Sparkles size={16} className="text-amber-500 shrink-0" />
      case 'markdown':
      case 'text':
        return <FileText size={16} className="text-blue-500 shrink-0" />
      case 'code':
        return <FileCode size={16} className="text-emerald-500 shrink-0" />
      default:
        return <FileIcon size={16} className="text-muted-foreground shrink-0" />
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Skills & Files: ${project?.name || ''}`}
      size="2xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <span className="text-xs text-muted-foreground">
            {files.length} file(s) attached to this project
          </span>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3 py-1">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileInputChange}
          disabled={uploading}
        />

        <p className="text-xs text-muted-foreground">
          Domain skills, guidelines, and reference files saved in MongoDB and injected directly into the project runtime prompt.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-[300px_1fr] gap-4 h-[500px]">
          {/* LEFT: Files List & Action Buttons */}
          <div className="flex flex-col h-full min-h-0 border-r pr-4">
            <div className="flex items-center justify-between gap-2 shrink-0 mb-1">
              <span className="text-xs font-semibold text-foreground">Attachments ({files.length})</span>
              <div className="flex items-center gap-1.5">
                <Button
                  size="sm"
                  variant={isCreatingSkill ? 'primary' : 'outline'}
                  className="h-7 text-xs gap-1 px-2.5 shadow-xs"
                  onClick={() => {
                    setIsCreatingSkill(true)
                    setPreviewFile(null)
                  }}
                >
                  <Plus size={13} />
                  <span>Write Skill</span>
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs gap-1 px-2.5"
                  disabled={uploading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  {uploading ? (
                    <>
                      <Loader2 size={12} className="animate-spin" />
                      <span>Uploading...</span>
                    </>
                  ) : (
                    <>
                      <Upload size={12} />
                      <span>Upload</span>
                    </>
                  )}
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 min-h-0">
              {loading ? (
                <div className="flex items-center justify-center p-8 text-xs text-muted-foreground gap-2">
                  <Loader2 size={14} className="animate-spin" />
                  <span>Loading files...</span>
                </div>
              ) : files.length === 0 ? (
                <div
                  onDragOver={(e) => {
                    e.preventDefault()
                    setIsDragging(true)
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                  onClick={() => {
                    setIsCreatingSkill(true)
                    setPreviewFile(null)
                  }}
                  className={cn(
                    'text-center p-6 border-2 border-dashed rounded-xl bg-card/30 cursor-pointer transition-all flex flex-col items-center justify-center gap-1.5',
                    isDragging
                      ? 'border-primary bg-primary/10'
                      : 'border-border hover:border-primary/50 hover:bg-card/50',
                  )}
                >
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-1">
                    <Sparkles size={18} />
                  </div>
                  <p className="text-xs font-semibold text-foreground">
                    Create a skill or upload files
                  </p>
                  <p className="text-[11px] text-muted-foreground max-w-xs leading-relaxed">
                    Click <strong>Write Skill</strong> to create <span className="font-mono text-primary font-medium">skills.md</span> directly or drop existing files here.
                  </p>
                </div>
              ) : (
                <>
                  <div
                    onDragOver={(e) => {
                      e.preventDefault()
                      setIsDragging(true)
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                    className={cn(
                      'p-2 rounded-lg border-2 border-dashed text-center transition-all cursor-pointer text-[11px]',
                      isDragging
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border/60 hover:border-border text-muted-foreground hover:text-foreground',
                    )}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    + Drop more files or click to upload
                  </div>

                  {files.map((file) => {
                    const isSelected = !isCreatingSkill && previewFile?.id === file.id
                    return (
                      <div
                        key={file.id}
                        onClick={() => {
                          setPreviewFile(file)
                          setIsCreatingSkill(false)
                        }}
                        className={cn(
                          'flex items-center justify-between p-2.5 rounded-xl border text-xs cursor-pointer transition-all',
                          isSelected
                            ? 'bg-primary/10 border-primary shadow-xs ring-1 ring-primary/20'
                            : 'bg-card border-border hover:bg-muted/40',
                        )}
                      >
                        <div className="flex items-center gap-2.5 truncate min-w-0 pr-2">
                          {getFileIcon(file.file_type)}
                          <div className="flex flex-col truncate">
                            <span className="font-medium text-foreground truncate">{file.filename}</span>
                            <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                              <span className="capitalize">{file.file_type}</span>
                              <span>•</span>
                              <span>{(file.file_size / 1024).toFixed(1)} KB</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-1 shrink-0">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDeleteFile(file.id)
                            }}
                            className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 size={12} />
                          </Button>
                        </div>
                      </div>
                    )
                  })}
                </>
              )}
            </div>
          </div>

          {/* RIGHT: Write Skill Editor OR File Content Preview */}
          <div className="flex flex-col h-full overflow-hidden bg-card/40 rounded-xl border p-4">
            {isCreatingSkill ? (
              <div className="flex flex-col h-full space-y-3">
                <div className="flex items-center justify-between pb-2 border-b">
                  <div className="flex items-center gap-2">
                    <Sparkles size={16} className="text-amber-500" />
                    <span className="font-semibold text-xs text-foreground">Create Skill File</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-muted-foreground"
                    onClick={() => setIsCreatingSkill(false)}
                  >
                    <X size={13} />
                  </Button>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex-1">
                    <label className="text-[11px] font-semibold text-foreground block mb-1">
                      File Name
                    </label>
                    <Input
                      placeholder="e.g. skills.md, database_rules.md"
                      value={newSkillFilename}
                      onChange={(e) => setNewSkillFilename(e.target.value)}
                      className="h-8 text-xs font-mono bg-background"
                    />
                  </div>

                  <div className="flex items-center gap-1.5 flex-wrap self-end">
                    <span className="text-[10px] text-muted-foreground mr-0.5">Presets:</span>
                    {SKILL_TEMPLATES.map((tmpl) => (
                      <button
                        key={tmpl.title}
                        type="button"
                        onClick={() => {
                          setNewSkillFilename(tmpl.filename)
                          setNewSkillContent(tmpl.content)
                        }}
                        className="px-2 py-0.5 rounded border border-border/80 bg-card hover:bg-muted text-[10px] font-medium text-foreground transition-colors"
                      >
                        {tmpl.title}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex-1 flex flex-col min-h-0">
                  <label className="text-[11px] font-semibold text-foreground mb-1 block">
                    Markdown Skill Instructions
                  </label>
                  <Textarea
                    placeholder="# Project Skills\n\n## Instructions\nWrite custom execution guidelines..."
                    value={newSkillContent}
                    onChange={(e) => setNewSkillContent(e.target.value)}
                    className="flex-1 font-mono text-xs leading-relaxed bg-background resize-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-1 border-t">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsCreatingSkill(false)}
                    disabled={savingSkill}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSaveCreatedSkill}
                    disabled={savingSkill}
                    className="gap-1.5 px-3"
                  >
                    {savingSkill ? (
                      <>
                        <Loader2 size={13} className="animate-spin" />
                        <span>Saving...</span>
                      </>
                    ) : (
                      <>
                        <Plus size={14} />
                        <span>Save Skill to Project</span>
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ) : previewFile ? (
              <div className="flex flex-col h-full min-h-0 overflow-hidden">
                <div className="flex items-center justify-between pb-2 mb-2 border-b shrink-0">
                  <div className="flex items-center gap-2 truncate">
                    {getFileIcon(previewFile.file_type)}
                    <span className="font-semibold text-xs text-foreground truncate">{previewFile.filename}</span>
                    <Badge variant="neutral" className="text-[10px] capitalize">
                      {previewFile.file_type}
                    </Badge>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-muted-foreground"
                    onClick={() => setPreviewFile(null)}
                  >
                    <X size={13} />
                  </Button>
                </div>

                <div className="flex-1 overflow-y-auto pr-2 text-xs text-foreground min-h-0">
                  {previewFile.content ? (
                    previewFile.file_type === 'skill' || previewFile.file_type === 'markdown' ? (
                      <div className="text-xs leading-relaxed space-y-2">
                        <Markdown content={previewFile.content} />
                      </div>
                    ) : (
                      <pre className="p-3 bg-muted/50 rounded font-mono text-[11px] whitespace-pre-wrap">
                        {previewFile.content}
                      </pre>
                    )
                  ) : (
                    <p className="text-muted-foreground italic p-4 text-center">
                      Binary or non-text document (file size: {(previewFile.file_size / 1024).toFixed(1)} KB).
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center p-6 text-muted-foreground">
                <Eye size={28} className="mb-2 opacity-50" />
                <p className="text-xs font-medium text-foreground">No file selected for preview</p>
                <p className="text-[11px] mt-1 text-muted-foreground max-w-xs">
                  Click on an attached file from the list to preview its contents, or click <strong>Write Skill</strong> to author a new <code className="bg-muted px-1 py-0.5 rounded font-mono text-foreground">skills.md</code>.
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setIsCreatingSkill(true)}
                  className="mt-3 text-xs gap-1.5"
                >
                  <Plus size={13} />
                  <span>Write New Skill</span>
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </Dialog>
  )
}
