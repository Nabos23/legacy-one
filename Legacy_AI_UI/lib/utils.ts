import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const truncate = (str: string, len: number) =>
  str.length > len ? str.slice(0, len) + '...' : str

export const stripMarkdown = (str: string): string =>
  str
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/(\*\*|__)(.*?)\1/g, '$2')
    .replace(/(\*|_)(.*?)\1/g, '$2')
    .replace(/`{1,3}([^`]*)`{1,3}/g, '$1')
    .replace(/\s+/g, ' ')
    .trim()

export const formatToolName = (name: string): string => {
  const trimmed = name?.trim() || ''
  if (!trimmed) return name
  const lower = trimmed.toLowerCase()
  if (
    lower === 'query_db_write' ||
    lower === 'query_write' ||
    lower === 'db_write' ||
    lower === 'query_mongo_write' ||
    lower === 'query_sql_write'
  ) return 'Write to database'
  if (
    lower === 'query_db_read' ||
    lower === 'query_read' ||
    lower === 'db_read' ||
    lower === 'query_mongo_read' ||
    lower === 'query_sql_read' ||
    lower === 'query_db'
  ) return 'Read from database'
  const cleaned = trimmed.replace(/[_-]+/g, ' ').trim().toLowerCase()
  return cleaned ? cleaned.charAt(0).toUpperCase() + cleaned.slice(1) : name
}

export const normalizeRoleName = (role: string): string => role.toLowerCase().replace(/\s+/g, '_')

export const isOrgManagerOrAbove = (role?: string | null): boolean => {
  if (!role) return false
  const normalized = normalizeRoleName(role)
  return ['org_admin', 'org_manager', 'super_admin', 'admin'].includes(normalized)
}

export const agentVisibilityLabel = (agent: {
  owner_scope: string
  allowed_user_ids?: string[]
  team_id?: string | null
}): string => {
  if (agent.owner_scope === 'user') return 'Personal'
  if (agent.owner_scope === 'selected_users') return `Selected users (${agent.allowed_user_ids?.length ?? 0})`
  if (agent.owner_scope === 'team') return 'Team'
  return 'Organization'
}

export const getInitials = (name: string) =>
  name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

export const formatDate = (date: string | Date): string => {
  const d = typeof date === 'string' ? new Date(date) : date
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export const AVATAR_COLORS = [
  'bg-violet-600',
  'bg-purple-600',
  'bg-fuchsia-600',
  'bg-pink-600',
  'bg-rose-600',
  'bg-red-600',
  'bg-orange-600',
  'bg-amber-500',
  'bg-yellow-500',
  'bg-lime-600',
  'bg-green-600',
  'bg-emerald-600',
  'bg-teal-600',
  'bg-cyan-600',
  'bg-sky-600',
  'bg-blue-600',
  'bg-indigo-600',
  'bg-violet-700',
  'bg-slate-600',
  'bg-zinc-600',
  'bg-stone-600',
  'bg-red-700',
  'bg-orange-700',
  'bg-cyan-700',
] as const

export const avatarColor = (name: string): string => {
  return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length]
}
