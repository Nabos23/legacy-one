import { api } from './client'
import type { OrgRolePermissions } from '@/types'

export type EditableRole = 'org_manager' | 'user'

export const rolePermissionsApi = {
  /** Effective (override if customized, else global default) permissions for a role in this org. */
  get: (orgId: string, role: EditableRole) =>
    api.get<OrgRolePermissions>(`/organizations/${orgId}/roles/${role}/permissions`),

  /** Upserts this org's override for `role`. Never touches the global default other orgs use. */
  update: (orgId: string, role: EditableRole, permissionNames: string[]) =>
    api.put<OrgRolePermissions>(`/organizations/${orgId}/roles/${role}/permissions`, {
      permission_names: permissionNames,
    }),

  /** Removes this org's override for `role`, reverting it to the global default. */
  reset: (orgId: string, role: EditableRole) =>
    api.delete<OrgRolePermissions>(`/organizations/${orgId}/roles/${role}/permissions`),
}
