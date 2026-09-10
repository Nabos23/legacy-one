import { api } from './client'
import { API_BASE_URL } from '@/lib/config'

export type SlackAppSourceType = 'single_agent' | 'supervisor'

export interface SlackInstallation {
  id: string
  team_id: string
  team_name?: string | null
  organization_id?: string | null
  source_type?: SlackAppSourceType | null
  agent_id?: string | null
  is_enabled: boolean
  is_linked: boolean
  created_at: string
  updated_at: string
}

export interface SlackPendingInstallation {
  team_name?: string | null
  already_linked: boolean
}

export interface SlackLinkPayload {
  installation_id: string
  token: string
  organization_id: string
  source_type: SlackAppSourceType
  agent_id?: string | null
}

export interface SlackInstallationUpdatePayload {
  source_type?: SlackAppSourceType
  agent_id?: string | null
  is_enabled?: boolean
}

/** `/connector-apps/slack/install` is a plain redirect endpoint, not JSON --
 * navigate the browser to it directly (window.location.href), don't fetch it. */
export const SLACK_APP_INSTALL_URL = `${API_BASE_URL}/connector-apps/slack/install`

export const connectorAppsApi = {
  slack: {
    /** Public -- the visitor clicking the "finish setup" Slack DM link may
     * have no One-AI session yet, so this is a raw, header-less fetch
     * rather than the `api` wrapper (which would otherwise attach a stale
     * Authorization header if one happens to exist, and whose 401 handling
     * assumes an authenticated flow this page isn't part of). */
    async getPending(installationId: string, token: string): Promise<SlackPendingInstallation> {
      const res = await fetch(
        `${API_BASE_URL}/connector-apps/slack/installations/${installationId}/pending?token=${encodeURIComponent(token)}`
      )
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(body.detail ?? res.statusText)
      }
      return res.json()
    },

    link: (payload: SlackLinkPayload) =>
      api.post<SlackInstallation>('/connector-apps/slack/installations/link', payload),

    list: (organizationId: string) =>
      api.get<SlackInstallation[]>(`/connector-apps/slack/installations?organization_id=${organizationId}`),

    get: (installationId: string) =>
      api.get<SlackInstallation>(`/connector-apps/slack/installations/${installationId}`),

    update: (installationId: string, payload: SlackInstallationUpdatePayload) =>
      api.patch<SlackInstallation>(`/connector-apps/slack/installations/${installationId}`, payload),

    delete: (installationId: string) =>
      api.delete<void>(`/connector-apps/slack/installations/${installationId}`),
  },
}
