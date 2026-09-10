import { api } from './client'
import type { OrgSettings, OrgSettingsUpdate } from '@/types'

export const settingsApi = {
  /** Fetch an organization's settings (backend applies defaults when unset). */
  get: (orgId: string) => api.get<OrgSettings>(`/organizations/${orgId}/settings`),

  /** Update (upsert) an organization's settings. */
  update: (orgId: string, body: OrgSettingsUpdate) =>
    api.put<OrgSettings>(`/organizations/${orgId}/settings`, body),
}
