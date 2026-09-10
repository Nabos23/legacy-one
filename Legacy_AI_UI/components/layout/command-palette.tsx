'use client'

import { useEffect, useMemo, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  LayoutDashboard, Bot, Wrench, Database, Terminal,
  Activity, Settings, HelpCircle, Building2, Users,
  Plus, Search, ArrowRight, FolderKanban,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAgents } from '@/hooks/use-agents'
import { useOrganizations } from '@/hooks/use-organizations'
import { useTools } from '@/hooks/use-tools'

export interface CommandItem {
  id: string
  label: string
  path: string
  group: string
  icon: React.ReactNode
}

const CLIENT_PAGES: CommandItem[] = [
  { id: 'c-dash',      label: 'Dashboard',      path: '/client/dashboard',      group: 'Pages',   icon: <LayoutDashboard className="w-4 h-4" /> },
  { id: 'c-agents',    label: 'Agents',          path: '/client/agents',         group: 'Pages',   icon: <Bot className="w-4 h-4" /> },
  { id: 'c-projects',  label: 'Projects',        path: '/client/projects',       group: 'Pages',   icon: <FolderKanban className="w-4 h-4" /> },
  { id: 'c-tools',     label: 'Tools',           path: '/client/tools',          group: 'Pages',   icon: <Wrench className="w-4 h-4" /> },
  { id: 'c-db',        label: 'DB Connections',  path: '/client/db-connections', group: 'Pages',   icon: <Database className="w-4 h-4" /> },
  { id: 'c-play',      label: 'Playground',      path: '/client/playground',     group: 'Pages',   icon: <Terminal className="w-4 h-4" /> },
  { id: 'c-observability', label: 'Observability', path: '/client/tracing',        group: 'Pages',   icon: <Activity className="w-4 h-4" /> },
  { id: 'c-settings',     label: 'Settings',      path: '/client/settings',       group: 'Pages',   icon: <Settings className="w-4 h-4" /> },
  { id: 'c-help',      label: 'Help',            path: '/client/help',           group: 'Pages',   icon: <HelpCircle className="w-4 h-4" /> },
]

const ADMIN_PAGES: CommandItem[] = [
  { id: 'a-dash',     label: 'Dashboard',      path: '/admin/dashboard',     group: 'Pages', icon: <LayoutDashboard className="w-4 h-4" /> },
  { id: 'a-orgs',     label: 'Organizations',  path: '/admin/organizations', group: 'Pages', icon: <Building2 className="w-4 h-4" /> },
  { id: 'a-users',    label: 'Users',          path: '/admin/users',         group: 'Pages', icon: <Users className="w-4 h-4" /> },
  { id: 'a-agents',   label: 'Agents',         path: '/admin/agents',        group: 'Pages', icon: <Bot className="w-4 h-4" /> },
  { id: 'a-projects', label: 'Projects',       path: '/client/projects',     group: 'Pages', icon: <FolderKanban className="w-4 h-4" /> },
  { id: 'a-tools',    label: 'Tool Registry',  path: '/admin/tool-registry', group: 'Pages', icon: <Wrench className="w-4 h-4" /> },
  { id: 'a-play',     label: 'Playground',     path: '/admin/playground',    group: 'Pages', icon: <Terminal className="w-4 h-4" /> },
  { id: 'a-observability', label: 'Observability', path: '/admin/tracing',   group: 'Pages', icon: <Activity className="w-4 h-4" /> },
  { id: 'a-settings', label: 'Settings',       path: '/admin/settings',      group: 'Pages', icon: <Settings className="w-4 h-4" /> },
]

const CLIENT_ACTIONS: CommandItem[] = [
  { id: 'act-agent', label: 'Create Agent',  path: '/client/agents/create', group: 'Actions', icon: <Plus className="w-4 h-4" /> },
  { id: 'act-project', label: 'Projects',    path: '/client/projects',      group: 'Actions', icon: <FolderKanban className="w-4 h-4" /> },
  { id: 'act-tool',  label: 'Register Tool', path: '/client/tools/create',  group: 'Actions', icon: <Plus className="w-4 h-4" /> },
]

const ADMIN_ACTIONS: CommandItem[] = [
  { id: 'act-agent-a', label: 'Create Agent',        path: '/admin/agents/create',        group: 'Actions', icon: <Plus className="w-4 h-4" /> },
  { id: 'act-project-a', label: 'Projects',          path: '/client/projects',            group: 'Actions', icon: <FolderKanban className="w-4 h-4" /> },
  { id: 'act-org',     label: 'Create Organization', path: '/admin/organizations/create', group: 'Actions', icon: <Plus className="w-4 h-4" /> },
  { id: 'act-toolreg', label: 'Add Tool Type',       path: '/admin/tool-registry/create', group: 'Actions', icon: <Plus className="w-4 h-4" /> },
]

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  variant?: 'client' | 'admin'
}

export function CommandPalette({ open, onOpenChange, variant = 'client' }: CommandPaletteProps) {
  if (!open) return null
  return <CommandPaletteInner onOpenChange={onOpenChange} variant={variant} />
}

function CommandPaletteInner({
  onOpenChange,
  variant,
}: {
  onOpenChange: (open: boolean) => void
  variant: 'client' | 'admin'
}) {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const isAdmin = variant === 'admin'
  const base = isAdmin ? '/admin' : '/client'

  // Loaded lazily — this component only mounts while the palette is open.
  const { data: agentsData } = useAgents(1, undefined, undefined, 50)
  const { data: orgsData } = useOrganizations(1, undefined, 50)
  const { data: toolsData } = useTools(1, undefined, 50)

  const staticItems = useMemo(
    () => (isAdmin ? [...ADMIN_PAGES, ...ADMIN_ACTIONS] : [...CLIENT_PAGES, ...CLIENT_ACTIONS]),
    [isAdmin],
  )

  const q = query.toLowerCase().trim()

  const filteredStatic = useMemo(() => {
    if (!q) return staticItems
    return staticItems.filter(i => i.label.toLowerCase().includes(q) || i.path.toLowerCase().includes(q))
  }, [staticItems, q])

  const dynamicItems = useMemo<CommandItem[]>(() => {
    if (!q) return []
    const items: CommandItem[] = []
    ;(agentsData?.items ?? [])
      .filter(a => a.name.toLowerCase().includes(q))
      .slice(0, 5)
      .forEach(a =>
        items.push({ id: `agent-${a.id}`, label: a.name, path: `${base}/agents/${a.id}`, group: 'Agents', icon: <Bot className="w-4 h-4" /> }),
      )
    if (isAdmin) {
      ;(orgsData?.items ?? [])
        .filter(o => o.name.toLowerCase().includes(q))
        .slice(0, 5)
        .forEach(o =>
          items.push({ id: `org-${o.id}`, label: o.name, path: `/admin/organizations/${o.id}`, group: 'Organizations', icon: <Building2 className="w-4 h-4" /> }),
        )
    } else {
      ;(toolsData?.items ?? [])
        .filter(t => (t.name ?? t.user_description ?? '').toLowerCase().includes(q))
        .slice(0, 5)
        .forEach(t =>
          items.push({ id: `tool-${t.id}`, label: t.name ?? (t.user_description || 'Tool'), path: `/client/tools/${t.id}`, group: 'Tools', icon: <Wrench className="w-4 h-4" /> }),
        )
    }
    return items
  }, [q, agentsData, orgsData, toolsData, isAdmin, base])

  const filtered = useMemo(() => [...filteredStatic, ...dynamicItems], [filteredStatic, dynamicItems])

  const groups = useMemo(() => {
    const map = new Map<string, CommandItem[]>()
    for (const item of filtered) {
      if (!map.has(item.group)) map.set(item.group, [])
      map.get(item.group)!.push(item)
    }
    return map
  }, [filtered])

  const navigate = useCallback((item: CommandItem) => {
    router.push(item.path)
    onOpenChange(false)
    setQuery('')
    setSelectedIndex(0)
  }, [router, onOpenChange])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onOpenChange(false); return }
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIndex(i => Math.min(i + 1, filtered.length - 1)) }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIndex(i => Math.max(i - 1, 0)) }
      if (e.key === 'Enter' && filtered[selectedIndex]) { e.preventDefault(); navigate(filtered[selectedIndex]) }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [filtered, selectedIndex, navigate, onOpenChange])

  let flatIndex = -1

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[100] bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />

      {/* Palette panel */}
      <div className="fixed top-[18vh] left-1/2 -translate-x-1/2 z-[101]
        w-[580px] max-w-[calc(100vw-2rem)]
        rounded-2xl overflow-hidden
        bg-white/92 dark:bg-[#111122]/96
        backdrop-blur-2xl
        border border-black/[0.08] dark:border-white/[0.1]
        shadow-[0_24px_80px_rgba(0,0,0,0.15)] dark:shadow-[0_24px_80px_rgba(0,0,0,0.7)]">
        {/* No entrance animation — command palettes are opened many times per
            session; AUDIT.md names this exact case as "100+/day -> no animation, ever". */}

        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3.5
          border-b border-black/[0.07] dark:border-white/[0.07]">
          <Search className="w-4 h-4 text-[var(--text-3)] shrink-0" />
          <input
            autoFocus
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search pages, agents, actions..."
            className="flex-1 bg-transparent text-[14px] text-[var(--text-1)]
              outline-none placeholder:text-[var(--text-3)]"
          />
          <kbd className="text-[10px] px-1.5 py-0.5 rounded-md font-mono
            bg-black/[0.06] dark:bg-white/[0.08]
            border border-black/[0.08] dark:border-white/[0.1]
            text-[var(--text-3)]">
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[360px] overflow-y-auto p-1.5">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-10 text-[var(--text-3)]">
              <Search className="w-8 h-8 opacity-30" />
              <p className="text-[13px]">No results for &ldquo;{query}&rdquo;</p>
            </div>
          ) : (
            Array.from(groups.entries()).map(([group, items]) => (
              <div key={group} className="mb-1">
                <p className="text-[10.5px] font-bold tracking-[0.1em] uppercase
                  text-[var(--text-3)] px-3 pt-2.5 pb-1">
                  {group}
                </p>
                {items.map(item => {
                  flatIndex += 1
                  const idx = flatIndex
                  const isSelected = idx === selectedIndex
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => navigate(item)}
                      className={cn(
                        'flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-left',
                        'transition-[background-color,color] duration-150 group',
                        isSelected
                          ? 'bg-violet-100 dark:bg-violet-500/15 text-violet-700 dark:text-violet-300'
                          : 'text-[var(--text-2)] hover:bg-black/[0.04] dark:hover:bg-white/[0.05] hover:text-[var(--text-1)]'
                      )}
                    >
                      <span className={cn(
                        'shrink-0',
                        isSelected ? 'text-violet-600 dark:text-violet-400' : 'text-[var(--text-3)]'
                      )}>
                        {item.icon}
                      </span>
                      <span className="text-[13.5px] font-medium flex-1 truncate">{item.label}</span>
                      <span className="text-[11px] text-[var(--text-3)] font-mono hidden sm:block truncate max-w-[200px]">
                        {item.path}
                      </span>
                      <ArrowRight className={cn(
                        'w-3.5 h-3.5 shrink-0 transition-opacity',
                        isSelected ? 'opacity-100 text-violet-500' : 'opacity-0 group-hover:opacity-40'
                      )} />
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer hint */}
        <div className="flex items-center justify-between px-4 py-2.5
          border-t border-black/[0.06] dark:border-white/[0.06]
          bg-black/[0.02] dark:bg-white/[0.02]">
          <div className="flex items-center gap-3">
            {[['↑↓', 'Navigate'], ['↵', 'Open'], ['Esc', 'Close']].map(([key, label]) => (
              <div key={key} className="flex items-center gap-1.5">
                <kbd className="text-[9px] px-1.5 py-0.5 rounded font-mono
                  bg-black/[0.06] dark:bg-white/[0.08]
                  border border-black/[0.08] dark:border-white/[0.1]
                  text-[var(--text-3)]">
                  {key}
                </kbd>
                <span className="text-[11px] text-[var(--text-3)]">{label}</span>
              </div>
            ))}
          </div>
          <span className="text-[11px] text-[var(--text-3)]">{filtered.length} result{filtered.length !== 1 ? 's' : ''}</span>
        </div>
      </div>
    </>
  )
}

export function useCommandPalette() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(o => !o)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  return { open, setOpen }
}
