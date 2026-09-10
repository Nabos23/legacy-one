'use client'

import { useState, useEffect } from 'react'
import { Copy, Check, Loader2, ExternalLink, PlugZap, XCircle } from 'lucide-react'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { connectorsApi } from '@/lib/api/connectors'
import type { ConnectorRegistryItem, ConnectorSetupInfo, ConnectorStatusState } from '@/types/connectors'
import { ConnectorLogo } from './connector-logo'
import { humanizeConnectorError } from './connector-card'
import { formatDate } from '@/lib/utils'

const SCOPE_LABELS: Record<string, Record<string, string>> = {
  slack: {
    'channels:read': 'View public channels',
    'channels:history': 'Read public channel messages',
    'chat:write': 'Send messages',
    'files:read': 'View files',
    'files:write': 'Upload files',
    'users:read': 'View workspace members',
    'reactions:write': 'Add emoji reactions',
    'pins:write': 'Pin messages',
  },
  gmail: {
    'https://www.googleapis.com/auth/gmail.readonly': 'Read your email',
    'https://www.googleapis.com/auth/gmail.send': 'Send email on your behalf',
    'https://www.googleapis.com/auth/gmail.modify': 'Read, send, and manage your email',
  },
  'google-drive': {
    'https://www.googleapis.com/auth/drive': 'Full access to your Drive files',
    'https://www.googleapis.com/auth/drive.readonly': 'Read your Drive files',
    'https://www.googleapis.com/auth/drive.file': 'Access files you open with this app',
  },
  onedrive: {
    'Files.ReadWrite.All': 'Read and write all files',
    'Files.Read.All': 'Read all files',
    'offline_access': 'Stay connected when you’re not active',
  },
  hubspot: {
    'crm.objects.contacts.read': 'Read contacts',
    'crm.objects.contacts.write': 'Create and edit contacts',
    'crm.objects.deals.read': 'Read deals',
    'crm.objects.deals.write': 'Create and edit deals',
  },
}

const capitalize = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s)

function humanizeScope(scope: string): string {
  if (scope.startsWith('http')) {
    const last = scope.split('/').filter(Boolean).pop() ?? scope
    return last.split(/[._]/).map(capitalize).join(' ')
  }
  if (scope.includes(':')) {
    return scope.split(':').map(part => part.split(/[_.]/).map(capitalize).join(' ')).join(': ')
  }
  return scope.replace(/([a-z])([A-Z])/g, '$1 $2').split(/[._]/).map(capitalize).join(' ')
}

function scopeLabel(providerId: string, scope: string): string {
  return SCOPE_LABELS[providerId]?.[scope] ?? humanizeScope(scope)
}

interface ConnectorSetupDialogProps {
  connector: ConnectorRegistryItem
  status?: ConnectorStatusState | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onConnected: () => void
  onAuthorize?: (url: string) => void
}

export function ConnectorSetupDialog({
  connector,
  status,
  open,
  onOpenChange,
  onConnected,
  onAuthorize,
}: ConnectorSetupDialogProps) {
  const [setupInfo, setSetupInfo] = useState<ConnectorSetupInfo | null>(null)
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [signingSecret, setSigningSecret] = useState('')
  const [botToken, setBotToken] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [subdomain, setSubdomain] = useState('')
  const [saving, setSaving] = useState(false)
  const [redirecting, setRedirecting] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; error?: string | null } | null>(null)

  const API_KEY_HINTS: Record<string, { label: string; placeholder: string; hint: string }> = {
    'telegram':  { label: 'Bot Token',     placeholder: '123456789:ABC-DEF…',       hint: 'Get your bot token from @BotFather on Telegram — send /newbot and follow the prompts.' },
    'stripe':    { label: 'Secret Key',    placeholder: 'sk_live_…',                hint: 'Find it in Stripe Dashboard → Developers → API keys.' },
    'twilio':    { label: 'Credentials',   placeholder: 'ACCOUNT_SID:AUTH_TOKEN',   hint: 'Format: your Account SID, colon, then Auth Token.' },
    'aws-s3':    { label: 'Credentials',   placeholder: 'ACCESS_KEY:SECRET_KEY:REGION', hint: 'Format: Access Key ID, colon, Secret Access Key, colon, region (e.g. us-east-1).' },
    'whatsapp':    { label: 'Credentials',   placeholder: 'ACCESS_TOKEN:PHONE_NUMBER_ID',      hint: 'Format: permanent access token, colon, then Phone Number ID from Meta dashboard.' },
    'servicenow':  { label: 'Credentials',   placeholder: 'USERNAME:PASSWORD:INSTANCE',         hint: 'Format: username, colon, password, colon, your instance name (e.g. mycompany from mycompany.service-now.com).' },
    'shopify':     { label: 'Credentials',   placeholder: 'ACCESS_TOKEN:STORE_SUBDOMAIN',       hint: 'Format: Admin API access token from your custom app, colon, then your store subdomain (e.g. my-store from my-store.myshopify.com).' },
    'bamboohr':    { label: 'Credentials',   placeholder: 'API_KEY:SUBDOMAIN',                  hint: 'Format: your API key (from My Account → API Keys), colon, then your company subdomain (e.g. mycompany from mycompany.bamboohr.com).' },
    'greenhouse':  { label: 'API Key',       placeholder: 'your-harvest-api-key',               hint: 'Harvest API key from Greenhouse → Settings → Dev Center → API Credential Management.' },
    'datadog':     { label: 'Credentials',   placeholder: 'API_KEY:APP_KEY',                    hint: 'Format: API key, colon, Application key — both from Datadog Organization Settings.' },
    'sendgrid':    { label: 'API Key',       placeholder: 'SG.xxxxxxxxxxxxxxxx',                hint: 'SendGrid API key from Settings → API Keys. Needs at least Mail Send and Stats permissions.' },
  }

  useEffect(() => {
    if (!open) return
    setError(null)
    connectorsApi.getSetupInfo(connector.id).then(info => {
      setSetupInfo(info)
    }).catch(() => setError('Failed to load setup info.'))
  }, [open, connector.id])

  useEffect(() => {
    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        setSaving(false)
        setRedirecting(false)
      }
    }
    window.addEventListener('pageshow', handlePageShow)
    return () => window.removeEventListener('pageshow', handlePageShow)
  }, [])

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      setTestResult(await connectorsApi.testConnection(connector.id))
    } catch {
      setTestResult({ ok: false, error: 'Request failed' })
    } finally {
      setTesting(false)
    }
  }

  const copyRedirectUri = () => {
    if (setupInfo?.redirect_uri) {
      navigator.clipboard.writeText(setupInfo.redirect_uri)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleSaveAndConnect = async () => {
    setError(null)
    setSaving(true)
    try {
      if (connector.auth_type === 'oauth2') {
        await connectorsApi.configure(connector.id, {
          client_id: clientId,
          client_secret: clientSecret,
          signing_secret: signingSecret || undefined,
          subdomain: subdomain || undefined,
          bot_token: requiresBotToken ? botToken : undefined,
        })
        const { url } = await connectorsApi.getAuthUrl(connector.id)
        if (onAuthorize) {
          setSaving(false)
          onAuthorize(url)
          onOpenChange(false)
        } else {
          setRedirecting(true)
          window.location.href = url
        }
      } else if (connector.auth_type === 'bot_token') {
        await connectorsApi.configure(connector.id, { bot_token: botToken })
        onConnected()
        onOpenChange(false)
      } else if (connector.auth_type === 'api_key') {
        await connectorsApi.configure(connector.id, { api_key: apiKey })
        onConnected()
        onOpenChange(false)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Setup failed. Please try again.'
      setError(msg)
      setSaving(false)
      setRedirecting(false)
    }
  }

  const requiresSigningSecret = connector.oauth?.requires_signing_secret ?? false
  const requiresSubdomain = connector.provider_id === 'zendesk' || connector.provider_id === 'shopify'
  const requiresBotToken = connector.provider_id === 'discord'
  const isOAuth = connector.auth_type === 'oauth2'
  const isBotToken = connector.auth_type === 'bot_token'
  const isApiKey = connector.auth_type === 'api_key'
  const guide = connector.setup_guide
  const apiKeyHint = API_KEY_HINTS[connector.provider_id]

  const canSubmit = isOAuth
    ? clientId.trim() && clientSecret.trim()
      && (!requiresSigningSecret || signingSecret.trim())
      && (!requiresSubdomain || subdomain.trim())
      && (!requiresBotToken || botToken.trim())
    : isBotToken
    ? botToken.trim()
    : apiKey.trim()

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Connect ${connector.name}`}
      size="md"
      footer={
        <div className="flex items-center justify-end gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button
            onClick={handleSaveAndConnect}
            disabled={!canSubmit || saving || redirecting}
          >
            {redirecting ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Redirecting…</>
            ) : saving ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving…</>
            ) : isOAuth ? (
              'Save & Authorize'
            ) : (
              'Connect'
            )}
          </Button>
        </div>
      }
    >
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <ConnectorLogo providerId={connector.provider_id} size="md" />
          <div>
            <p className="font-semibold text-[var(--text-1)]">{connector.name}</p>
            <p className="text-[13px] text-[var(--text-3)]">{connector.description}</p>
          </div>
        </div>

        {status?.connected && (
          <div className="rounded-lg bg-black/[0.03] dark:bg-white/[0.03] border border-[var(--border)] p-3 space-y-2">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <p className="text-[12px] text-[var(--text-2)]">
                {status.connected_at ? `Connected ${formatDate(status.connected_at)}` : 'Connected'}
                {status.last_checked_at && (
                  <span className="text-[var(--text-3)]"> · Last checked {formatDate(status.last_checked_at)}</span>
                )}
              </p>
              <Button variant="outline" size="xs" onClick={handleTestConnection} disabled={testing}>
                {testing
                  ? <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
                  : <PlugZap className="w-3 h-3 mr-1.5" />
                }
                Test connection
              </Button>
            </div>
            {testResult && (
              testResult.ok ? (
                <p className="flex items-center gap-1.5 text-[12px] text-green-600 dark:text-green-400">
                  <Check className="w-3.5 h-3.5" /> Connection is healthy
                </p>
              ) : (
                <p className="flex items-center gap-1.5 text-[12px] text-red-500 dark:text-red-400">
                  <XCircle className="w-3.5 h-3.5" />
                  {testResult.error ? humanizeConnectorError(testResult.error) : 'Test failed'}
                </p>
              )
            )}
          </div>
        )}

        {error && (
          <p className="text-[13px] text-red-500 bg-red-500/10 px-3 py-2 rounded-lg">{error}</p>
        )}

        {/* Setup guide */}
        {guide && (
          <div className="rounded-xl border border-blue-200/60 dark:border-blue-800/40 bg-blue-50/60 dark:bg-blue-950/20 p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[12px] font-semibold text-blue-700 dark:text-blue-300 uppercase tracking-wide">
                Setup instructions
              </p>
              <a
                href={guide.docs_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[11px] text-blue-600 dark:text-blue-400 hover:underline shrink-0"
              >
                Open {connector.name} dashboard
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <ol className="space-y-2">
              {guide.steps.map((step, i) => (
                <li key={i} className="flex gap-2.5">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 text-[10px] font-bold flex items-center justify-center mt-0.5">
                    {i + 1}
                  </span>
                  <span className="text-[12px] text-blue-900 dark:text-blue-200 leading-relaxed">
                    {step}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {isOAuth && (
          <>
            {/* Redirect URI */}
            <div className="space-y-1.5">
              <label className="text-[12px] font-medium text-[var(--text-2)]">
                Redirect URI <span className="text-[var(--text-3)]">(copy this into your OAuth app)</span>
              </label>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-[12px] bg-black/5 dark:bg-white/5 px-3 py-2 rounded-lg border border-[var(--border)] truncate text-[var(--text-2)]">
                  {setupInfo?.redirect_uri ?? '…'}
                </code>
                <Button variant="outline" size="icon-xs" onClick={copyRedirectUri}>
                  {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                </Button>
              </div>
            </div>

            {/* Subdomain (Zendesk & Shopify) */}
            {requiresSubdomain && (
              <div className="space-y-1.5">
                <label className="text-[12px] font-medium text-[var(--text-2)]">
                  {connector.provider_id === 'shopify' ? 'Store Subdomain' : 'Subdomain'}
                </label>
                <Input
                  value={subdomain}
                  onChange={e => setSubdomain(e.target.value)}
                  placeholder={
                    connector.provider_id === 'shopify'
                      ? 'my-store (the part before .myshopify.com)'
                      : 'mycompany (the part before .zendesk.com)'
                  }
                  autoComplete="off"
                />
                <p className="text-[11px] text-[var(--text-3)]">
                  Your {connector.name} URL is{' '}
                  <strong>
                    {subdomain || (connector.provider_id === 'shopify' ? 'my-store' : 'mycompany')}
                  </strong>
                  .{connector.provider_id === 'shopify' ? 'myshopify' : 'zendesk'}.com
                </p>
              </div>
            )}

            {/* Client ID */}
            <div className="space-y-1.5">
              <label className="text-[12px] font-medium text-[var(--text-2)]">Client ID</label>
              <Input
                value={clientId}
                onChange={e => setClientId(e.target.value)}
                placeholder="Paste your Client ID"
                autoComplete="off"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[12px] font-medium text-[var(--text-2)]">Client Secret</label>
              <Input
                type="password"
                value={clientSecret}
                onChange={e => setClientSecret(e.target.value)}
                placeholder="Paste your Client Secret"
                autoComplete="off"
              />
            </div>
            {requiresBotToken && (
              <div className="space-y-1.5">
                <label className="text-[12px] font-medium text-[var(--text-2)]">Bot Token</label>
                <Input
                  type="password"
                  value={botToken}
                  onChange={e => setBotToken(e.target.value)}
                  placeholder="Paste your bot token"
                  autoComplete="off"
                />
                <p className="text-[11px] text-[var(--text-3)]">
                  From Developer Portal → your app → Bot → Reset Token. Required for the bot to send messages, create channels, etc. — separate from the Client ID/Secret above.
                </p>
              </div>
            )}

            {requiresSigningSecret && (
              <div className="space-y-1.5">
                <label className="text-[12px] font-medium text-[var(--text-2)]">
                  Signing Secret
                </label>
                <Input
                  type="password"
                  value={signingSecret}
                  onChange={e => setSigningSecret(e.target.value)}
                  placeholder="Paste your Signing Secret"
                  autoComplete="off"
                />
                <p className="text-[11px] text-[var(--text-3)]">
                  Used to verify incoming webhook requests from {connector.name}.
                </p>
              </div>
            )}
          </>
        )}

        {isBotToken && (
          <div className="space-y-1.5">
            <label className="text-[12px] font-medium text-[var(--text-2)]">Bot Token</label>
            <Input
              type="password"
              value={botToken}
              onChange={e => setBotToken(e.target.value)}
              placeholder="Paste your bot token"
              autoComplete="off"
            />
            <p className="text-[11px] text-[var(--text-3)]">
              Create a bot in {connector.name} and paste its token here.
            </p>
          </div>
        )}

        {isApiKey && (
          <div className="space-y-1.5">
            <label className="text-[12px] font-medium text-[var(--text-2)]">
              {apiKeyHint?.label ?? 'API Key'}
            </label>
            <Input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder={apiKeyHint?.placeholder ?? 'Paste your API key'}
              autoComplete="off"
            />
            {apiKeyHint?.hint && (
              <p className="text-[11px] text-[var(--text-3)]">{apiKeyHint.hint}</p>
            )}
          </div>
        )}

        {isOAuth && connector.oauth?.scopes && connector.oauth.scopes.length > 0 && (
          <div className="rounded-lg bg-black/[0.03] dark:bg-white/[0.03] border border-[var(--border)] p-3">
            <p className="text-[11px] font-medium text-[var(--text-2)] mb-1.5">Required scopes</p>
            <div className="flex flex-wrap gap-1.5">
              {connector.oauth.scopes.map(s => (
                <span
                  key={s}
                  title={s}
                  className="text-[10px] bg-violet-500/10 text-violet-600 dark:text-violet-400 px-2 py-0.5 rounded-full"
                >
                  {scopeLabel(connector.provider_id, s)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Dialog>
  )
}
