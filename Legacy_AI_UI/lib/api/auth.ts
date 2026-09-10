import { api } from './client'
import type { TokenResponse, UserPublic, PermissionsResponse, AssignableRole, PermissionDefinition } from '@/types'

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }),

  register: (body: { name: string; email: string; password: string; organization_id?: string }) =>
    api.post<TokenResponse>('/auth/register', body),

  publicOrganizations: () => api.get<any[]>('/auth/organizations'),
  forgotPassword: (email: string) =>
    api.post<{ message: string; otp?: string }>('/auth/forgot-password', { email }),
  verifyOtp: (email: string, otp: string) =>
    api.post<{ message: string; otp: null }>('/auth/verify-otp', { email, otp }),
  resetPassword: (email: string, otp: string, new_password: string) =>
    api.post<{ message: string; otp: null }>('/auth/reset-password', { email, otp, new_password }),
  me: () => api.get<UserPublic>('/auth/me'),
  mePermissions: () => api.get<PermissionsResponse>('/auth/me/permissions'),
  assignableRoles: () => api.get<AssignableRole[]>('/auth/roles'),

  allRoles: () => api.get<AssignableRole[]>('/auth/roles/all'),

  permissionCatalog: () => api.get<PermissionDefinition[]>('/auth/permissions'),

  pendingApprovals: () => api.get<UserPublic[]>('/auth/pending-approvals'),
  updateApproval: (user_id: string, status: 'approved' | 'disapproved') =>
    api.post<UserPublic>('/auth/approval', { user_id, status }),

  logout: () => api.post<void>('/auth/logout', {}),
}
