'use client'

import { useMemo } from 'react'
import Link from 'next/link'
import { Plug, ChevronRight, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ConnectorLogo } from '@/components/connectors/connector-logo'
import { SettingsCard, SettingsCardHeader } from './settings-card'
import { useConnectors } from '@/hooks/use-connectors'
import { useConnectorStatuses } from '@/hooks/use-connector-statuses'

/** Summary of the caller's linked services, reusing the same registry/status hooks as the Connectors page. */
export function ConnectionsSection({ manageHref }: { manageHref: string }) {
  const { data: registry, loading: registryLoading } = useConnectors()
  const connectorIds = useMemo(() => registry.map(c => c.id), [registry])
  const { statuses } = useConnectorStatuses(connectorIds)

  return (
    <SettingsCard>
      <SettingsCardHeader
        icon={Plug}
        title="Connected Accounts"
        description="Services you've linked so agents can act on your behalf"
        action={
          <Link href={manageHref}>
            <Button variant="ghost" size="sm">
              Manage all
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </Link>
        }
      />

      {registryLoading ? (
        <p className="text-[13px] text-[var(--text-3)]">Loading connectors…</p>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          {registry.slice(0, 8).map(c => {
            const connected = statuses[c.id]?.connected
            return (
              <div
                key={c.id}
                className="flex items-center gap-3 p-3 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]"
              >
                <ConnectorLogo providerId={c.provider_id} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-medium text-[var(--text-1)] truncate">{c.name}</p>
                  <p className="text-[11px] text-[var(--text-3)] capitalize">{c.category}</p>
                </div>
                {connected ? (
                  <Badge variant="success" className="gap-1 shrink-0">
                    <Check className="w-3 h-3" /> Connected
                  </Badge>
                ) : (
                  <Badge variant="neutral" className="shrink-0">Not connected</Badge>
                )}
              </div>
            )
          })}
        </div>
      )}

      {!registryLoading && registry.length === 0 && (
        <p className="text-[13px] text-[var(--text-3)]">No connectors are available yet.</p>
      )}
    </SettingsCard>
  )
}

/** Live count of connected accounts, for a nav badge. */
export function useConnectedCount() {
  const { data: registry } = useConnectors()
  const connectorIds = useMemo(() => registry.map(c => c.id), [registry])
  const { statuses } = useConnectorStatuses(connectorIds)
  return Object.values(statuses).filter(s => s.connected).length
}
