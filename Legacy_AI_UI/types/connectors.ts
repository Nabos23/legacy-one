export interface ConnectorOAuthConfig {
  auth_url: string
  token_url: string
  scopes: string[]
  requires_credentials: boolean
  requires_signing_secret: boolean
}

export interface ConnectorSetupGuide {
  docs_url: string
  steps: string[]
}

export interface ConnectorRegistryItem {
  id: string
  provider_id: string
  name: string
  category: string
  description: string
  icon: string
  owner_scope: 'user' | 'organization'
  auth_type: 'oauth2' | 'bot_token' | 'api_key' | 'basic'
  oauth: ConnectorOAuthConfig | null
  setup_guide: ConnectorSetupGuide | null
  available_actions: string[]
  permissions?: Record<string, string[]> | null
  is_active: boolean
  is_visible: boolean
}

export interface ConnectorStatus {
  connected: boolean
  connection_id?: string
  metadata?: Record<string, string>
  connected_at?: string
  last_checked_at?: string
  last_error?: string | null
  consecutive_failures?: number | null
}

export interface ConnectorTestConnectionResult {
  ok: boolean
  error?: string | null
}

export interface ConnectorSetupInfo {
  has_credentials: boolean
  client_id?: string
  redirect_uri: string
  provider_id: string
  auth_type: string
}

export interface ConnectorCredentialsSave {
  client_id?: string
  client_secret?: string
  signing_secret?: string
  bot_token?: string
  api_key?: string
  subdomain?: string
}

export interface ConnectorRegistryPage {
  items: ConnectorRegistryItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ConnectorAuthUrlResponse {
  url: string
}

/** Client-only annotation: `checkFailed` means the status check itself
 * couldn't get an answer (after retrying) — distinct from `connected: false`,
 * which means the backend confirmed the connector is disconnected. */
export interface ConnectorStatusState extends ConnectorStatus {
  checkFailed?: boolean
}

export interface ConnectorWithStatus extends ConnectorRegistryItem {
  status: ConnectorStatusState | null
  statusLoading: boolean
}
