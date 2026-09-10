import { api } from './client'
import type { UserPublic, Page } from '@/types'

export interface UserListFilters {
  organizationId?: string
  sortBy?: 'name' | 'email' | 'created_at'
  sortOrder?: 'asc' | 'desc'
}

function buildUserQuery(page: number, page_size: number, search?: string, role?: string, filters?: UserListFilters) {
  const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
  if (search) qs.set('search', search)
  if (role) qs.set('role', role)
  if (filters?.organizationId) qs.set('organization_id', filters.organizationId)
  if (filters?.sortBy) qs.set('sort_by', filters.sortBy)
  if (filters?.sortOrder) qs.set('sort_order', filters.sortOrder)
  return qs.toString()
}

export const usersApi = {
  /** Super admin only — lists all users across every org. Optional name/email search, role, and organization filter. */
  list: (page = 1, page_size = 10, search?: string, role?: string, filters?: UserListFilters) =>
    api.get<Page<UserPublic>>(`/users?${buildUserQuery(page, page_size, search, role, filters)}`),

  /** Any role with view permission — lists users in a specific org. Optional name/email search and role filter. */
  listByOrg: (orgId: string, page = 1, page_size = 10, search?: string, role?: string, filters?: UserListFilters) =>
    api.get<Page<UserPublic>>(
      `/organizations/${orgId}/users?${buildUserQuery(page, page_size, search, role, filters)}`
    ),

  /** Requires create_user permission — provisions a user in the caller's org */
  create: (body: {
    name: string
    email: string
    password: string
    role?: string
    organization_id?: string
  }) => api.post<UserPublic>('/auth/admin/users', body),

  /** Update the caller's own profile (currently: display name). */
  updateMe: (name: string) => api.patch<UserPublic>('/users/me', { name }),

  /** Requires edit_user permission — updates another user's name and/or role. */
  update: (id: string, body: { name?: string; role?: string }) =>
    api.patch<UserPublic>(`/users/${id}`, body),

  /** Requires delete_user permission — soft-deletes another user. */
  remove: (id: string) => api.delete<void>(`/users/${id}`),

  /** Upload/replace the caller's profile picture. Accepts PNG, JPEG, GIF, or WEBP. */
  uploadAvatar: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<UserPublic>('/users/me/avatar', form)
  },
}
