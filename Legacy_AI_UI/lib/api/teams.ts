import { api } from './client'
import type { Page, TeamPublic } from '@/types'

function buildTeamQuery(page: number, page_size: number, search?: string) {
  const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
  if (search) qs.set('search', search)
  return qs.toString()
}

export const teamsApi = {
  /** Super admin only — lists all teams across every org. */
  list: (page = 1, page_size = 10, search?: string) =>
    api.get<Page<TeamPublic>>(`/teams?${buildTeamQuery(page, page_size, search)}`),

  /** Any role with view permission — lists teams in a specific org. */
  listByOrg: (orgId: string, page = 1, page_size = 10, search?: string) =>
    api.get<Page<TeamPublic>>(`/teams/org/${orgId}?${buildTeamQuery(page, page_size, search)}`),

  get: (id: string) => api.get<TeamPublic>(`/teams/${id}`),

  /** Requires create_team permission — creates a team, optionally with initial members & permissions. */
  create: (body: { organization_id: string; name: string; description?: string; member_ids?: string[]; permissions?: string[] }) =>
    api.post<TeamPublic>('/teams', body),

  /** Requires edit_team permission — updates a team's name/description/permissions. */
  update: (id: string, body: { name?: string; description?: string; permissions?: string[] }) =>
    api.put<TeamPublic>(`/teams/${id}`, body),

  /** Requires delete_team permission — soft-deletes a team. Any agent assigned
   * to it reverts to organization-wide visibility. */
  remove: (id: string) => api.delete<void>(`/teams/${id}`),

  /** Requires edit_team permission — adds one or more org users to a team. */
  addMembers: (id: string, userIds: string[]) =>
    api.post<TeamPublic>(`/teams/${id}/members`, { user_ids: userIds }),

  /** Requires edit_team permission — removes a single member from a team. */
  removeMember: (id: string, userId: string) =>
    api.delete<TeamPublic>(`/teams/${id}/members/${userId}`),

  /** Fetch permissions granted to a team. */
  getPermissions: (id: string) => api.get<string[]>(`/teams/${id}/permissions`),

  /** Update permissions granted to a team. */
  updatePermissions: (id: string, permissions: string[]) =>
    api.put<TeamPublic>(`/teams/${id}/permissions`, { permissions }),
}
